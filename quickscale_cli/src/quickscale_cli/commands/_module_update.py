"""Module update flow, local guards, and the update command.

Implementation detail of :mod:`quickscale_cli.commands.module_commands`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

import io
import shutil
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import click
import yaml

from quickscale_cli.cli_help import QuickScaleCommand
from quickscale_cli.commands._module_shared import _UpdatePathSnapshot
from quickscale_cli.commands._module_update_journal import (
    _ModuleUpdateTarget,
    _UpdateJournalError,
)
from quickscale_cli.commands._module_update_identity import (
    _collect_update_migration_identity,
    _get_update_migration_issues,
    _is_frozen_update_vintage,
    _update_migration_identity_reason,
    _UpdateMigrationIdentityError,
)

import quickscale_core as _quickscale_core
import quickscale_core.project_state_manager as _project_state_manager
import quickscale_cli.commands._module_update_io as _module_update_io
import quickscale_core.schema.state_schema as _state_schema
import quickscale_core.manifest.loader_errors as _loader_errors
import quickscale_core.utils.git_errors as _git_errors
import quickscale_cli.commands._module_shared as _module_shared
import quickscale_cli.commands.contract_vintage as _contract_vintage
import quickscale_core.config as _config
import quickscale_core.advisory_lock as _advisory_lock
import quickscale_core.utils.git_subtree as _git_subtree
import quickscale_cli.commands._module_embed as _module_embed
import quickscale_cli.commands._module_update_guard as _module_update_guard
import quickscale_cli.commands._module_update_journal as _module_update_journal
import quickscale_core.project_state_hashes as _project_state_hashes
from quickscale_core.generator.project_blocks import (
    managed_region_paths,
    strip_managed_region_content,
)
import quickscale_cli.commands._module_update_seal as _module_update_seal
import quickscale_cli.utils.module_provenance as _module_provenance


_MODULE_UPDATE_REMOTE = "https://github.com/Experto-AI/quickscale.git"


def _ensure_authoritative_state_for_update(
    project_path: Path,
) -> Any | None:
    """Ensure authoritative ``state.yml`` is available before update mutations.

    For config-only / non-consolidated projects, this materializes
    ``state.yml`` from ``quickscale.yml`` and legacy ``config.yml`` before
    any git mutation begins.  Returns the loaded (or freshly materialized)
    :class:`QuickScaleState`, or ``None`` when authoritative metadata
    cannot be derived.

    The update path must abort before git mutation when this returns
    ``None`` — synthetic project metadata must never be written.

    Raises:
        StateError: When ``state.yml`` exists but is malformed.  The
            caller's existing ``StateError`` handler surfaces this.
    """
    manager = _project_state_manager.ProjectStateManager(project_path)

    # If state.yml already has consolidated sections, just load and return.
    if manager._state_file_has_consolidated_sections():
        return manager.load_state()

    # If state.yml exists but lacks consolidated sections, check whether
    # it is at least parseable.  A malformed state.yml must surface as
    # StateError (not silently fall through to quickscale.yml).
    if manager.state_file.exists():
        try:
            existing = manager._state_manager.load()
        except _state_schema.StateError:
            raise  # Let caller surface the malformed-state error.
        if existing is not None:
            # Parseable but non-consolidated — materialize.
            return manager.materialize_authoritative_state()

    # No state.yml at all — try quickscale.yml for project metadata.
    return manager.materialize_authoritative_state()


def _rollback_failed_module_update(
    project_path: Path,
    snapshots: list[_UpdatePathSnapshot],
) -> str | None:
    """Restore recorded module update snapshots after a failed mutation."""
    try:
        _module_update_io._restore_update_snapshots(snapshots)
    except Exception as rollback_error:
        return f"Rollback also failed: {rollback_error}"

    _module_update_io._refresh_git_index_after_update_rollback(project_path, snapshots)
    click.secho("✅ Restored pre-pull update snapshot", fg="green")
    return None


def _report_module_update_error(name: str, error: Exception) -> None:
    """Preserve the update command's type-specific failure reports."""
    if isinstance(error, _state_schema.StateError):
        click.secho(
            f"❌ Failed to load .quickscale/state.yml: {error}",
            fg="red",
            err=True,
        )
        click.echo(
            "💡 Fix .quickscale/state.yml or regenerate it with 'quickscale apply' "
            "before updating modules.",
            err=True,
        )
        return

    click.secho(f"❌ Failed to update {name}: {error}", fg="red", err=True)
    if isinstance(error, _loader_errors.ManifestError):
        click.echo(
            f"💡 Fix modules/{name}/module.yml or remove and re-embed the module.",
            err=True,
        )
    elif isinstance(error, _git_errors.GitError):
        click.echo(f"💡 Tip: Check for conflicts in modules/{name}/", err=True)
    elif isinstance(error, _loader_errors.ModuleVersionMismatchError):
        click.echo(
            "\n💡 Update QuickScale to the latest version before updating modules.",
            err=True,
        )
    elif isinstance(error, _UpdateMigrationIdentityError):
        click.echo(
            "\n💡 An update must keep every applied migration file "
            "byte-identical — under an unchanged version label, and on every "
            "pull from the migration freeze vintage on: replacing one would "
            "leave the database's applied schema unidentified. Reconcile the "
            "embedded module content before updating, or move to the new "
            "content through a fresh database.",
            err=True,
        )
    elif isinstance(error, _module_update_seal._UpdateSealError):
        click.echo(
            "\n💡 An update pulls only content that matches the module's "
            "immutable release tag for this QuickScale version. If you "
            "maintain the release, publish the split branch and seal the tag, "
            "then retry; otherwise update QuickScale to a released version.",
            err=True,
        )


def _update_single_module(
    name: str,
    info: Any,
    default_remote: str,
    no_preview: bool,
    *,
    seal_plan: _module_update_seal._UpdateSealPlan | None = None,
    resume: bool = False,
) -> _ModuleUpdateTarget | None:
    """Pull one module to its verified target and return its provenance.

    This is the per-module transport step of the journaled set transaction
    (SA319 (b)): it verifies the seal, pulls the subtree, and checks the
    applied migration identity.  It deliberately does not write state or
    commit tracking files; the set finalization writes ``state.yml`` once and
    commits once after every pull succeeded.
    """
    click.echo(f"\n📥 Updating {name} module...")
    project_path = Path.cwd()

    try:
        # A resume is already authorized by the journal: the transaction owns
        # the module and tracking paths until it completes or is abandoned.
        if not resume and not _module_update_guard._check_local_pre_pull_guard(
            project_path, name, info
        ):
            return None

        # SA204(e)/(g): capture the applied migration content identity before
        # the pull so the pull cannot replace it: an equal version label must
        # keep it, and from the migration freeze vintage on every pull must.
        # A vintage before the freeze is a release upgrade whose database
        # handling is the documented fresh-database path, so it compares
        # nothing there.
        applied_version = info.version if info is not None else None
        applied_migrations = (
            _collect_update_migration_identity(project_path, info.prefix)
            if applied_version is not None
            else None
        )

        # SA319 (a): resolve the sealed tag and prove the canonical split
        # branch tip still carries its tree before the first pull.  The
        # command preflights the whole set and passes the plan in; a direct
        # call resolves its own module first.  The resolved branch SHA is
        # reused for both the subtree pull and state persistence
        # (CR-PLAN-004), so the pull cannot drift after verification.
        try:
            seal = seal_plan or _module_update_seal._resolve_update_seal(
                default_remote,
                name,
                _quickscale_core.__version__,
            )
        except _module_update_seal._UpdateSealError as seal_error:
            _report_module_update_error(name, seal_error)
            return None
        source_ref = seal.branch_sha

        with TemporaryDirectory(prefix="quickscale-module-update-") as temp_dir:
            try:
                snapshots = _module_update_io._record_update_mutation_snapshots(
                    project_path,
                    info.prefix,
                    Path(temp_dir),
                )
            except (OSError, shutil.Error) as snapshot_error:
                click.secho(
                    f"❌ Failed to create pre-update snapshot for {name}: {snapshot_error}",
                    fg="red",
                    err=True,
                )
                click.echo(
                    "💡 Check disk space and permissions, then retry.",
                    err=True,
                )
                return None

            pre_pull_head = _resolve_pre_update_head(project_path)
            try:
                # Phase 2.3b (CR-M5-P3-005): bind the subtree pull to the
                # exact resolved commit SHA so the pulled content matches
                # the commit_sha persisted to state.yml.  Passing the branch
                # name here would allow the pull to drift if the remote
                # branch advances between resolve_remote_ref and subtree.
                #
                # CR-M5-P3-007: ``git subtree pull <remote> <40-char SHA>
                # --squash`` is verified to work on Git 2.43.0+ because
                # ``git fetch <url> <hex>`` officially supports fully-spelled
                # hex object names and git-subtree forwards the ref to
                # ``git fetch``.  See the hermetic integration proof in
                # ``quickscale_core/tests/test_git_utils.py``
                # (TestSubtreePullWithCommitSha).
                output = _git_subtree.run_git_subtree_pull(
                    prefix=info.prefix,
                    remote=default_remote,
                    branch=source_ref,
                    squash=True,
                )

                installed_version = _module_shared._read_embedded_module_version(
                    project_path, name
                )

                # SA204(g): from the freeze vintage on, a pull must not change
                # applied migration content, and it must not proceed while
                # that content cannot be identified: a frozen project has no
                # fresh-database escape hatch, so an unknown identity refuses
                # the pull instead of silently authorizing it.
                if applied_migrations is None and _is_frozen_update_vintage(
                    applied_version
                ):
                    raise _UpdateMigrationIdentityError(
                        "the applied migration content identity could not be "
                        f"established for the frozen vintage '{applied_version}': "
                        "restore the embedded module tree before updating"
                    )

                # SA204(e)/(g): an applied migration file must survive the
                # pull byte-identical — under an unchanged version label, and
                # on every pull from the migration freeze vintage on — so a
                # rewrite or removal raises the identity refusal.
                identity_reason = _update_migration_identity_reason(
                    applied_version, installed_version
                )
                if identity_reason is not None:
                    migration_issues = _get_update_migration_issues(
                        applied_migrations,
                        _collect_update_migration_identity(project_path, info.prefix),
                    )
                    if migration_issues:
                        raise _UpdateMigrationIdentityError(
                            f"applied migration content changed {identity_reason}: "
                            + "; ".join(migration_issues)
                        )
            except Exception as error:
                # A pull that committed is the recorded target: leave it in
                # place so the journaled transaction can re-check it on the
                # next run.  Re-pulling an already merged split commit would
                # not reapply its content.  A pull that failed before its
                # commit is restored from the snapshot as before.
                if _resolve_pre_update_head(project_path) == pre_pull_head:
                    rollback_error = _rollback_failed_module_update(
                        project_path, snapshots
                    )
                    if rollback_error is not None:
                        raise RuntimeError(rollback_error) from error
                else:
                    click.secho(
                        f"ℹ️  {name}'s pull committed; the recorded set is kept "
                        "for the next update to resume.",
                        fg="yellow",
                    )
                raise

        click.secho(f"✅ Updated {name} successfully", fg="green")

        if output and not no_preview:
            click.echo("\n📋 Changes summary:")
            click.echo(output[:500])  # Show first 500 chars

        return _ModuleUpdateTarget(
            name=name,
            version=installed_version,
            branch=seal.branch,
            commit_sha=source_ref,
        )

    except Exception as error:
        _report_module_update_error(name, error)
        return None


def _load_update_state(project_path: Path) -> Any:
    """Load authoritative state, aborting on failure or no installed modules.

    Returns None when the command should stop because nothing is installed.
    """
    manager = _project_state_manager.ProjectStateManager(project_path)
    try:
        state = manager.load_state()
    except Exception as error:
        click.secho(
            f"❌ Failed to load .quickscale/state.yml: {error}",
            fg="red",
            err=True,
        )
        click.echo(
            "💡 Fix or restore .quickscale/state.yml before running "
            "'quickscale update'.",
            err=True,
        )
        raise click.Abort() from error

    if state is None or not state.modules:
        click.secho("✅ No modules installed. Nothing to update.", fg="green")
        click.echo("\n💡 Tip: Add modules with 'quickscale plan --add'")
        return None
    return state


def _validate_update_preconditions(
    state: Any, project_path: Path, *, acknowledged: bool
) -> None:
    """Enforce contract vintage, warn on drift, and validate module readiness."""
    _contract_vintage.enforce_shipped_contract_vintage(
        state,
        state.modules,
        operation="'quickscale update'",
        acknowledged=acknowledged,
    )

    # Surface module version drift between state and legacy config.
    # Non-fatal: update reconciles both files at the end.
    try:
        legacy_config = _config.load_config()
    except _config.ConfigError:
        legacy_config = None
    _module_shared._warn_version_drift_for_update(project_path, legacy_config)

    for name in state.modules:
        if not _module_shared._validate_module_readiness(name):
            raise click.Abort()


def _acquire_update_lock(project_path: Path) -> Any:
    """Acquire the update advisory lock, aborting on contention."""
    lock = _advisory_lock.AdvisoryLock(project_path, operation="update")
    try:
        lock.acquire()
    except _advisory_lock.AdvisoryLockContentionError as error:
        click.secho(f"❌ {error}", fg="red", err=True)
        raise click.Abort() from error
    return lock


def _resolve_pre_update_head(project_path: Path) -> str:
    """Return the pre-update HEAD, or an empty string when unresolvable."""
    try:
        return subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            ["git", "rev-parse", "HEAD"],  # noqa: S607 - PATH-resolved executable by design
            cwd=project_path,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        # ``_validate_update_environment`` already required a git repository;
        # without a resolvable HEAD there is no committed state to roll back
        # to, so partial-failure rollback is skipped.
        return ""


def _update_all_modules(
    state: Any,
    *,
    no_preview: bool,
    seal_plans: dict[str, _module_update_seal._UpdateSealPlan] | None = None,
) -> tuple[list[str], list[_ModuleUpdateTarget]]:
    """Pull each installed module in order; stop at the first failure."""
    failed_modules: list[str] = []
    updated_modules: list[_ModuleUpdateTarget] = []
    for name, module_state in state.modules.items():
        plan = (seal_plans or {}).get(name)
        updated = _update_single_module(
            name,
            module_state,
            _MODULE_UPDATE_REMOTE,
            no_preview,
            seal_plan=plan,
        )
        if updated is None:
            failed_modules.append(name)
            break
        updated_modules.append(updated)
    return failed_modules, updated_modules


def _module_matches_target(
    project_path: Path,
    target: _ModuleUpdateTarget,
) -> bool | None:
    """Return whether the module tree matches the target, or ``None`` if unknown."""
    drift = _module_provenance.detect_module_content_drift(
        project_path, target.name, target.commit_sha
    )
    if not drift.verifiable:
        try:
            _module_update_seal._fetch_remote_commit(
                _MODULE_UPDATE_REMOTE, target.commit_sha
            )
        except _git_errors.GitError:
            return None
        drift = _module_provenance.detect_module_content_drift(
            project_path, target.name, target.commit_sha
        )
    if not drift.verifiable:
        return None
    return not drift.has_changes


def _restore_module_from_baseline(
    project_path: Path,
    pre_update_head: str,
    module_name: str,
) -> bool:
    """Restore one module tree from the journal's pre-update commit.

    Only a module whose pull did not commit can be restored to a clean tree:
    a committed pull would leave staged differences against HEAD, so a retry
    cannot pull over it.  Returns ``False`` when the module path is not in the
    baseline or the restoration is not clean.
    """
    module_prefix = f"modules/{module_name}"
    if not _module_update_io._path_in_commit(
        project_path, pre_update_head, module_prefix
    ):
        return False
    _module_update_io._remove_update_path(project_path / module_prefix)
    restored = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
        ["git", "checkout", pre_update_head, "--", module_prefix],  # noqa: S607 - PATH-resolved executable by design
        cwd=project_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if restored.returncode != 0:
        return False
    status = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
        ["git", "status", "--porcelain", "--", module_prefix],  # noqa: S607 - PATH-resolved executable by design
        cwd=project_path,
        capture_output=True,
        text=True,
        check=False,
    )
    return status.returncode == 0 and not status.stdout.strip()


def _region_only_difference(
    project_path: Path, journal: Any, relative_path: str
) -> bool:
    """Return whether *relative_path* differs only inside managed regions."""
    baseline = _module_update_io._read_commit_path(
        project_path, journal.pre_update_head, relative_path
    )
    if baseline is None:
        return False
    current_path = project_path / relative_path
    if not current_path.is_file():
        return False
    current = current_path.read_text(encoding="utf-8")
    return strip_managed_region_content(current) == strip_managed_region_content(
        baseline
    )


def _journal_dirty_paths(
    project_path: Path, journal: Any, package: str | None
) -> list[str]:
    """Return dirty paths outside the interrupted transaction's own outputs."""
    allowed_prefixes = {f"modules/{target.name}" for target in journal.targets}
    allowed_prefixes.update(
        {
            str(_module_update_journal.UPDATE_JOURNAL_RELATIVE_PATH),
            # The advisory lock is created while this check runs; it is a
            # transient QuickScale artifact, not operator work.
            str(Path(".quickscale") / "state.lock"),
            ".quickscale/state.yml",
            ".quickscale/config.yml",
            "pyproject.toml",
            "poetry.lock",
        }
    )
    if package:
        allowed_prefixes.update(
            {
                f"{package}/settings/modules.py",
                f"{package}/urls_modules.py",
                f"{package}/quickscale_managed",
                *_project_state_hashes.DEFAULT_MANAGED_PROJECT_PATHS,
            }
        )
    status = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
        [  # noqa: S607 - PATH-resolved executable by design
            "git",
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
        cwd=project_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if status.returncode != 0:
        raise _UpdateJournalError(
            "Cannot inspect the working tree while resuming the interrupted "
            "update; fix the repository state and retry."
        )
    region_paths = set(managed_region_paths())
    dirty: list[str] = []
    for line in status.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = path.strip('"')
        if any(
            path == prefix or path.startswith(prefix + "/")
            for prefix in allowed_prefixes
        ):
            continue
        if path in region_paths and _region_only_difference(
            project_path, journal, path
        ):
            continue
        dirty.append(path)
    return dirty


def _baseline_migration_identity(
    project_path: Path,
    pre_update_head: str,
    module_prefix: str,
) -> dict[str, str] | None:
    """Read a module's applied migration hashes from the pre-update commit."""
    archived = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
        ["git", "archive", "--format=tar", f"{pre_update_head}:{module_prefix}"],  # noqa: S607 - PATH-resolved executable by design
        cwd=project_path,
        capture_output=True,
        check=False,
    )
    if archived.returncode != 0:
        return None
    module_name = Path(module_prefix).name
    with TemporaryDirectory(prefix="quickscale-update-baseline-") as temp_dir:
        extracted = Path(temp_dir) / module_name
        extracted.mkdir()
        with tarfile.open(fileobj=io.BytesIO(archived.stdout), mode="r:") as archive:
            archive.extractall(extracted, filter="data")
        return _collect_update_migration_identity(Path(temp_dir), module_name)


def _resume_identity_guard(
    project_path: Path,
    state: Any,
    target: _ModuleUpdateTarget,
    pre_update_head: str,
    installed_version: str,
) -> None:
    """Re-run the applied migration-content guard for an already-pulled module.

    A crash can leave a module at its target after the pull but before (or
    during) the identity check.  Skipping the module on content alone would
    silently accept a rewrite the original run refused, so compare the
    baseline's applied hashes with the target's.
    """
    module_state = state.modules.get(target.name)
    applied_version = module_state.version if module_state is not None else None
    reason = _update_migration_identity_reason(applied_version, installed_version)
    if reason is None:
        return
    module_prefix = f"modules/{target.name}"
    applied_identity = _baseline_migration_identity(
        project_path, pre_update_head, module_prefix
    )
    if applied_identity is None and _is_frozen_update_vintage(applied_version):
        raise _UpdateJournalError(
            "the applied migration content identity could not be established "
            f"for the frozen vintage '{applied_version}': restore the embedded "
            "module tree before updating"
        )
    issues = _get_update_migration_issues(
        applied_identity,
        _collect_update_migration_identity(project_path, module_prefix),
    )
    if issues:
        raise _UpdateJournalError(
            f"applied migration content changed {reason}: " + "; ".join(issues)
        )


def _journal_seal_plan(target: _ModuleUpdateTarget) -> Any:
    """Build the pull seam for one recorded target without re-resolving it."""
    return _module_update_seal._UpdateSealPlan(
        module=target.name,
        version=target.version,
        tag=f"splits/{target.name}-module/{target.version}",
        tag_sha=target.commit_sha,
        branch=target.branch,
        branch_sha=target.commit_sha,
    )


def _journal_baseline_package(
    project_path: Path,
    pre_update_head: str,
) -> str | None:
    """Resolve the project package from the journal's pre-update baseline."""
    archived = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
        ["git", "show", f"{pre_update_head}:.quickscale/state.yml"],  # noqa: S607 - PATH-resolved executable by design
        cwd=project_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if archived.returncode == 0:
        try:
            document = yaml.safe_load(archived.stdout) or {}
        except yaml.YAMLError:
            document = {}
        package = (
            document.get("project", {}).get("package")
            if isinstance(document, dict)
            else None
        )
        if isinstance(package, str) and package:
            return package

    desired = project_path / "quickscale.yml"
    if desired.exists():
        try:
            document = yaml.safe_load(desired.read_text()) or {}
        except yaml.YAMLError:
            document = {}
        package = (
            document.get("project", {}).get("package")
            if isinstance(document, dict)
            else None
        )
        if isinstance(package, str) and package:
            return package
    return None


def _journal_transaction_complete(
    project_path: Path,
    journal: Any,
    state: Any,
) -> bool:
    """Return whether the interrupted transaction already committed its set."""
    head = _resolve_pre_update_head(project_path)
    if not head or head == journal.pre_update_head:
        return False
    committed = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
        [  # noqa: S607 - PATH-resolved executable by design
            "git",
            "log",
            "--format=%B",
            f"{journal.pre_update_head}..HEAD",
        ],
        cwd=project_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if committed.returncode != 0 or journal.transaction_id not in committed.stdout:
        # Only this transaction's set commit carries its id; an unrelated
        # commit after the journal was written is not proof of finalization.
        return False
    for target in journal.targets:
        module_state = state.modules.get(target.name)
        if module_state is None or module_state.commit_sha != target.commit_sha:
            return False
        if _module_matches_target(project_path, target) is not True:
            return False

    status = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],  # noqa: S607 - PATH-resolved executable by design
        cwd=project_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if status.returncode != 0:
        return False
    for line in status.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = path.strip('"')
        if path == str(_module_update_journal.UPDATE_JOURNAL_RELATIVE_PATH):
            continue
        if path == str(Path(".quickscale") / "state.lock"):
            continue
        return False
    return True


def _resume_journaled_update(
    project_path: Path,
    journal: Any,
    *,
    confirm_contract_adoption: bool,
) -> _UpdateOutcome:
    """Complete the module set recorded by an interrupted update.

    Completed pulls are left in place: re-pulling an already merged split
    commit would make Git report the target as integrated without reapplying
    its content.  The transaction's tracking files are restored to the
    journal's baseline, modules not yet at their target are pulled, and the
    set is finalized with one state write and one commit.
    """
    if not _module_update_io._commit_exists(project_path, journal.pre_update_head):
        raise _UpdateJournalError(
            "The journal records a pre-pull commit that is not in this "
            "repository. Reconcile the module set manually, then remove the "
            "journal before pulling again."
        )
    if not _module_update_io._is_ancestor(project_path, journal.pre_update_head):
        raise _UpdateJournalError(
            "The journal's pre-pull commit is not reachable from HEAD, so its "
            "module set cannot be restored safely. Reconcile the module set "
            "manually, then remove the journal."
        )

    # A crash after the set commit but before the journal clear left a
    # completed transaction.  Verify it against the recorded targets and the
    # committed tree, then clear the journal without undoing the adoption or
    # writing a second set commit.
    try:
        current_state = _project_state_manager.ProjectStateManager(
            project_path
        ).load_state()
    except Exception:  # noqa: BLE001 - a missing/corrupt state is handled below
        current_state = None
    if current_state is not None and _journal_transaction_complete(
        project_path, journal, current_state
    ):
        _module_update_journal._clear_update_journal(project_path)
        click.secho(
            "✅ The interrupted module update already completed; cleared its journal.",
            fg="green",
        )
        return _UpdateOutcome(
            [], [target.name for target in journal.targets], False, False
        )

    package = _journal_baseline_package(project_path, journal.pre_update_head)
    if package is None:
        raise _UpdateJournalError(
            "The journal's pre-update project package could not be resolved. "
            "Fix .quickscale/state.yml or quickscale.yml and re-run "
            "'quickscale update'."
        )

    click.secho(
        "\n⚠️  Resuming the interrupted module update...",
        fg="yellow",
        bold=True,
    )

    # Refuse unrelated operator work before any restoration can stage or
    # commit it.  The transaction's own tracking outputs are allowed; an
    # unrelated staged file would otherwise ride into the restoration commit.
    dirty_paths = _journal_dirty_paths(project_path, journal, package)
    if dirty_paths:
        raise _UpdateJournalError(
            "Uncommitted changes outside the interrupted update's files block "
            "its resume: " + ", ".join(dirty_paths) + ". Commit or stash "
            "them, then re-run 'quickscale update'."
        )

    # The interrupted run may have written tracking files before its commit.
    # Restore them to the pre-update baseline so the pulls and the migration
    # identity guard judge the same applied state the original run used.
    if not _module_update_io._roll_back_partial_module_update(
        project_path,
        journal.pre_update_head,
        [],
        package,
    ):
        raise _UpdateJournalError(
            "The interrupted update's tracking files could not be restored. "
            "Fix the repository state and re-run 'quickscale update'."
        )
    state = _ensure_authoritative_state_for_update(project_path)
    if state is None:
        raise _UpdateJournalError(
            "The interrupted update's state could not be loaded after "
            "restoring its baseline. Fix .quickscale/state.yml and re-run "
            "'quickscale update'."
        )

    targets: list[_ModuleUpdateTarget] = []
    failed_modules: list[str] = []
    for target in journal.targets:
        matches = _module_matches_target(project_path, target)
        if matches is None:
            raise _UpdateJournalError(
                f"The recorded target {target.commit_sha[:12]} for "
                f"{target.name!r} is not readable from the project or the "
                "module remote. Reconcile the module set manually."
            )
        if matches:
            try:
                version = _module_shared._read_embedded_module_version(
                    project_path, target.name
                )
            except Exception as error:  # noqa: BLE001 - report as a journal failure
                raise _UpdateJournalError(
                    f"The recorded target for {target.name!r} has an invalid "
                    f"embedded manifest: {error}. Reconcile the module set "
                    "before retrying."
                ) from error
            _resume_identity_guard(
                project_path,
                state,
                target,
                journal.pre_update_head,
                version,
            )
            targets.append(
                _ModuleUpdateTarget(
                    name=target.name,
                    version=version,
                    branch=target.branch,
                    commit_sha=target.commit_sha,
                )
            )
            continue

        module_state = state.modules.get(target.name)
        if module_state is None:
            raise _UpdateJournalError(
                f"The interrupted update's state does not list {target.name!r}. "
                "Reconcile .quickscale/state.yml and retry."
            )
        if not _restore_module_from_baseline(
            project_path, journal.pre_update_head, target.name
        ):
            raise _UpdateJournalError(
                f"{target.name!r} has committed content that differs from both "
                "its baseline and its recorded target. Reconcile the module "
                "set manually."
            )
        result = _update_single_module(
            target.name,
            module_state,
            _MODULE_UPDATE_REMOTE,
            no_preview=True,
            seal_plan=_journal_seal_plan(target),
            resume=True,
        )
        if result is None:
            failed_modules.append(target.name)
            break
        if _module_matches_target(project_path, target) is not True:
            raise _UpdateJournalError(
                f"{target.name!r} did not reach its recorded target "
                f"{target.commit_sha[:12]}. Reconcile the module set manually."
            )
        targets.append(result)

    if failed_modules:
        return _UpdateOutcome(
            failed_modules,
            [target.name for target in targets],
            False,
            False,
            "The interrupted module set could not be completed",
        )
    return _finalize_update_set(
        project_path,
        state,
        targets,
        confirm_contract_adoption=confirm_contract_adoption,
        transaction_id=journal.transaction_id,
    )


def _regenerate_update_wiring(project_path: Path, state: Any) -> bool:
    """Regenerate the managed wiring after every pull; True on success.

    The refreshed hash records are written into *state*, which the caller
    saves once with the module provenance.  Any failure restores the
    pre-update wiring and is treated as a failed set.
    """
    try:
        wiring_success, wiring_message = (
            _module_update_io._regenerate_and_record_managed_wiring(
                project_path,
                state.project.package,
                state,
            )
        )
        if not wiring_success:
            raise RuntimeError(wiring_message)
        click.echo("  ✅ Regenerated managed module wiring")
    except Exception as error:  # noqa: BLE001 - rollback is handled by the caller
        click.secho(
            f"❌ Failed to regenerate managed module wiring: {error}",
            fg="red",
            err=True,
        )
        click.echo(
            "💡 Fix the module manifests, then run "
            "'quickscale apply' to regenerate the managed wiring.",
            err=True,
        )
        return False
    return True


@dataclass(frozen=True)
class _UpdateOutcome:
    """Reportable result of the locked update sequence."""

    failed_modules: list[str]
    updated_modules: list[str]
    lock_failed: bool
    wiring_failed: bool
    set_failed: str | None = None


def _preflight_local_guards(
    project_path: Path,
    state: Any,
) -> str | None:
    """Run every module's local pre-pull guard before writing the journal.

    A refusal here must leave no journal: the documented repair is
    ``quickscale apply``, and a pending journal would make apply refuse it.
    Returns the failing module name, or ``None`` when every module passes.
    """
    for name, module_state in state.modules.items():
        if not _module_update_guard._check_local_pre_pull_guard(
            project_path, name, module_state
        ):
            return str(name)
    return None


def _format_required_module_error(offenders: list[tuple[str, str]]) -> str:
    """Format a required-module refusal for the update command."""
    pairs = ", ".join(
        f"'{dependant}' requires '{required}'" for dependant, required in offenders
    )
    return (
        f"Installed modules are missing a required module: {pairs}. "
        "Run 'quickscale apply' to add the required module, or remove the "
        "dependant first; the transaction is not started until the installed "
        "set satisfies every requirement."
    )


def _missing_required_module_error(
    project_path: Path,
    state: Any,
    seal_plans: dict[str, _module_update_seal._UpdateSealPlan],
) -> str | None:
    """Return a required-module gap before any pull or journal write.

    An update that cannot satisfy the installed set's (or the target
    manifests') ``required_modules`` must not start a transaction: the
    documented repair is ``quickscale apply`` to add the required module, and
    a pending journal would make apply refuse it.  Checking before the journal
    keeps that repair reachable.
    """
    installed = set(state.modules)
    offenders: list[tuple[str, str]] = []

    def _collect(document: Any, name: str, source: str) -> str | None:
        if not isinstance(document, dict):
            return f"{source} is not a YAML mapping"
        required_modules = document.get("required_modules", [])
        if not isinstance(required_modules, list):
            return f"{source} has a non-list required_modules"
        for required in required_modules:
            if not isinstance(required, str):
                return f"{source} has a non-string required_modules entry"
            if required not in installed:
                pair = (name, required)
                if pair not in offenders:
                    offenders.append(pair)
        return None

    # The installed manifests are always readable; check them before any
    # target object is needed, so a local gap is reported as itself.
    for name in sorted(installed):
        local_manifest = project_path / "modules" / name / "module.yml"
        if not local_manifest.exists():
            continue
        try:
            document = yaml.safe_load(local_manifest.read_text())
        except yaml.YAMLError as error:
            return (
                f"Cannot update: the manifest for {name!r} is not valid YAML: "
                f"{error}. Reconcile the module set before retrying."
            )
        problem = _collect(document, name, f"the manifest for {name!r}")
        if problem is not None:
            return f"Cannot update: {problem}. Reconcile the module set."
    if offenders:
        return _format_required_module_error(offenders)

    for name in sorted(installed):
        plan = seal_plans.get(name)
        if plan is None:
            continue
        result = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            ["git", "show", f"{plan.branch_sha}:module.yml"],  # noqa: S607 - PATH-resolved executable by design
            cwd=project_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            # The seal may equal the branch tip, so the preflight had no
            # reason to fetch the target object.  Fetch it before deciding
            # the requirement is absent; an unreadable target fails closed.
            try:
                _module_update_seal._fetch_remote_commit(
                    _MODULE_UPDATE_REMOTE, plan.branch_sha
                )
            except _git_errors.GitError as error:
                return (
                    f"Cannot update: the target manifest for {name!r} "
                    f"({plan.branch_sha[:12]}) could not be read: {error}. "
                    "Reconcile the module set before retrying."
                )
            result = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
                ["git", "show", f"{plan.branch_sha}:module.yml"],  # noqa: S607 - PATH-resolved executable by design
                cwd=project_path,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                return (
                    f"Cannot update: the target manifest for {name!r} "
                    f"({plan.branch_sha[:12]}) could not be read. "
                    "Reconcile the module set before retrying."
                )
        try:
            document = yaml.safe_load(result.stdout)
        except yaml.YAMLError as error:
            return (
                f"Cannot update: the target manifest for {name!r} "
                f"({plan.branch_sha[:12]}) is not valid YAML: {error}. "
                "Reconcile the module set before retrying."
            )
        problem = _collect(
            document,
            name,
            f"the target manifest for {name!r} ({plan.branch_sha[:12]})",
        )
        if problem is not None:
            return f"Cannot update: {problem}. Reconcile the module set."

    if not offenders:
        return None
    return _format_required_module_error(offenders)


def _finalize_update_set(
    project_path: Path,
    state: Any,
    targets: list[_ModuleUpdateTarget],
    *,
    confirm_contract_adoption: bool,
    transaction_id: str | None = None,
) -> _UpdateOutcome:
    """Write the set's state once, commit it once, and clear the journal."""
    for target in targets:
        _module_shared._apply_state_module_version(
            state,
            target.name,
            target.version,
            commit_sha=target.commit_sha,
            branch=target.branch,
        )

    all_modules_options: dict[str, dict[str, Any] | None] = {
        module_name: (module_state.options if module_state else {})
        for module_name, module_state in state.modules.items()
    }
    if not _module_embed._sync_module_dependencies(project_path, all_modules_options):
        return _UpdateOutcome(
            [],
            [target.name for target in targets],
            False,
            False,
            "Failed to sync dependency entries for the updated module set",
        )
    if not _module_update_io._refresh_update_lockfile(project_path):
        return _UpdateOutcome([], [target.name for target in targets], True, False)
    if not _regenerate_update_wiring(project_path, state):
        return _UpdateOutcome([], [target.name for target in targets], False, True)

    adoption = (
        _contract_vintage.apply_contract_adoption(state)
        if confirm_contract_adoption
        else None
    )
    _project_state_manager.ProjectStateManager(project_path).save_state(state)
    _module_update_io._commit_module_update_set(
        [target.name for target in targets],
        state.project.package,
        transaction_id=transaction_id,
    )
    if adoption is not None:
        _contract_vintage.report_contract_adoption(adoption)
    _module_update_journal._clear_update_journal(project_path)
    return _UpdateOutcome([], [target.name for target in targets], False, False)


def _run_update_under_lock(
    state: Any,
    project_path: Path,
    *,
    no_preview: bool,
    confirm_contract_adoption: bool,
    allow_local_changes: bool,
) -> _UpdateOutcome:
    """Run the locked journaled update sequence."""
    lock = _acquire_update_lock(project_path)
    try:
        journal = _module_update_journal._load_update_journal(project_path)
        if journal is not None:
            return _resume_journaled_update(
                project_path,
                journal,
                confirm_contract_adoption=confirm_contract_adoption,
            )

        # Phase 2.3b: materialize authoritative state before any mutation.
        # The set-scoped call replaces the old per-module materialization, so
        # the whole transaction reads the same state exactly once.
        applied_state = _ensure_authoritative_state_for_update(project_path)
        if applied_state is None:
            click.secho(
                "❌ Cannot update: authoritative project metadata "
                "(slug/package/theme) could not be derived from "
                ".quickscale/state.yml or quickscale.yml.",
                fg="red",
                err=True,
                bold=True,
            )
            click.echo(
                "💡 Fix quickscale.yml or regenerate state with "
                "'quickscale apply' before updating modules.",
                err=True,
            )
            raise click.Abort()
        state = applied_state

        # The hand-edit check runs under the lock, after the last read of
        # state and before the first pull, so it judges the tree the update
        # is about to replace.
        _module_update_guard._enforce_no_local_module_changes(
            state,
            project_path,
            allow_local_changes=allow_local_changes,
        )

        local_guard_failure = _preflight_local_guards(project_path, state)
        if local_guard_failure is not None:
            return _UpdateOutcome([local_guard_failure], [], False, False)

        # SA319 (a): verify every installed module's sealed tag and split
        # branch tree before the first pull.  A failure aborts the set
        # without mutating any module.
        seal_plans, seal_failure = _module_update_seal._preflight_update_seals(
            state,
            _MODULE_UPDATE_REMOTE,
            _quickscale_core.__version__,
        )
        if seal_failure is not None:
            failed_name, seal_error = seal_failure
            _report_module_update_error(failed_name, seal_error)
            return _UpdateOutcome([failed_name], [], False, False)

        required_error = _missing_required_module_error(project_path, state, seal_plans)
        if required_error is not None:
            return _UpdateOutcome([], [], False, False, required_error)

        pre_update_head = _resolve_pre_update_head(project_path)
        if not pre_update_head:
            raise _UpdateJournalError(
                "Cannot update: the project has no resolvable HEAD to record "
                "for resumption."
            )

        # SA319 (b): record the whole set before the first pull.  A process
        # that dies mid-set leaves this journal for the next update to resume.
        journal = _module_update_journal._write_update_journal(
            project_path,
            pre_update_head=pre_update_head,
            targets=tuple(
                _ModuleUpdateTarget(
                    name=plan.module,
                    version=plan.version,
                    branch=plan.branch,
                    commit_sha=plan.branch_sha,
                )
                for plan in seal_plans.values()
            ),
        )

        failed_modules, updated_modules = _update_all_modules(
            state, no_preview=no_preview, seal_plans=seal_plans
        )
        if failed_modules:
            # Completed pulls stay in place and the journal remains, so the
            # next update resumes the recorded set instead of re-pulling an
            # already merged split commit.
            return _UpdateOutcome(
                failed_modules,
                [target.name for target in updated_modules],
                False,
                False,
            )
        return _finalize_update_set(
            project_path,
            state,
            updated_modules,
            confirm_contract_adoption=confirm_contract_adoption,
            transaction_id=journal.transaction_id,
        )
    finally:
        lock.release()


def _report_update_outcome(outcome: _UpdateOutcome) -> None:
    """Print the failure report or the success banner for a finished update."""
    if outcome.failed_modules:
        click.secho(
            "\n❌ Module update stopped due to failure",
            fg="red",
            bold=True,
            err=True,
        )
        click.echo(
            f"Failed module(s): {', '.join(outcome.failed_modules)}",
            err=True,
        )
        if outcome.updated_modules:
            click.echo(
                "The recorded module set is kept; fix the failure and re-run "
                "'quickscale update' to resume it.",
                err=True,
            )
        raise click.Abort()

    if outcome.set_failed:
        click.secho(
            f"\n❌ {outcome.set_failed}",
            fg="red",
            bold=True,
            err=True,
        )
        if outcome.updated_modules:
            click.echo(
                "The recorded module set is kept; fix the failure and re-run "
                "'quickscale update' to resume it.",
                err=True,
            )
        raise click.Abort()

    if outcome.lock_failed:
        click.secho(
            "\n❌ Module update finished without a refreshed poetry.lock",
            fg="red",
            bold=True,
            err=True,
        )
        if outcome.updated_modules:
            click.echo(
                "The recorded module set is kept; fix the failure and re-run "
                "'quickscale update' to resume it.",
                err=True,
            )
        raise click.Abort()

    if outcome.wiring_failed:
        click.secho(
            "\n❌ Module update finished without regenerated managed wiring",
            fg="red",
            bold=True,
            err=True,
        )
        if outcome.updated_modules:
            click.echo(
                "The recorded module set is kept; fix the failure and re-run "
                "'quickscale update' to resume it.",
                err=True,
            )
        raise click.Abort()

    click.secho("\n🎉 Module update complete!", fg="green", bold=True)


@click.command(cls=QuickScaleCommand)
@click.option(
    "--no-preview",
    is_flag=True,
    help="Skip diff preview before updating",
)
@click.option(
    "--acknowledge-contract-vintage",
    is_flag=True,
    help="Proceed after manually adopting every required generated-file contract.",
)
@click.option(
    "--confirm-contract-adoption",
    is_flag=True,
    help=(
        "Record the generated-project contract adoption in .quickscale/state.yml "
        "and proceed."
    ),
)
@_module_update_guard.allow_local_changes_option
def update(
    no_preview: bool,
    acknowledge_contract_vintage: bool,
    confirm_contract_adoption: bool,
    allow_local_changes: bool,
) -> None:
    r"""
    Update all installed QuickScale modules to their latest versions.

    \b
    This command:
      - Reads installed modules from .quickscale/state.yml
      - Refuses modules whose files were edited since their recorded commit,
        or whose recorded tree cannot be verified
      - Verifies every module's sealed release tag and split-branch tree
        before the first pull
      - Updates ONLY modules you've explicitly installed
      - Shows a diff preview before updating (unless --no-preview)
      - Journals the set before the first pull, writes state.yml once, and
        commits the updated module set once
      - Refreshes poetry.lock after the module set's dependencies change
      - Restores an interrupted update's recorded set on the next run
    """
    try:
        _module_shared._validate_update_environment()

        project_path = Path.cwd()
        pending = _module_update_journal._update_journal_path(project_path).exists()
        state = None
        if pending:
            # Recovery must not depend on the current state: an interrupted
            # tracking restore can leave state.yml temporarily absent.
            click.secho(
                "⚠️  An interrupted module update is pending; resuming it.",
                fg="yellow",
                bold=True,
            )
            if not click.confirm("\n❓ Continue with update?"):
                click.echo("❌ Update cancelled")
                return
        else:
            state = _load_update_state(project_path)
            if state is None:
                return

            _validate_update_preconditions(
                state,
                project_path,
                acknowledged=acknowledge_contract_vintage or confirm_contract_adoption,
            )

            # Show installed modules
            click.echo(f"📦 Found {len(state.modules)} installed module(s):")
            for name, module_state in state.modules.items():
                click.echo(f"  - {name} ({module_state.version})")

            if not no_preview:
                click.echo("\n🔍 Preview mode: Changes will be shown before updating")

            # Confirm update
            if not click.confirm("\n❓ Continue with update?"):
                click.echo("❌ Update cancelled")
                return

        outcome = _run_update_under_lock(
            state,
            project_path,
            no_preview=no_preview,
            confirm_contract_adoption=confirm_contract_adoption,
            allow_local_changes=allow_local_changes,
        )
        _report_update_outcome(outcome)

    except _git_errors.GitError as e:
        click.secho(f"❌ Git error: {e}", fg="red", err=True)
        raise click.Abort()
    except click.Abort:
        raise
    except click.ClickException:
        raise
    except _UpdateJournalError as e:
        click.secho(f"❌ {e}", fg="red", err=True)
        raise click.Abort() from e
    except Exception as e:
        click.secho(f"❌ Unexpected error: {e}", fg="red", err=True)
        raise click.Abort()
