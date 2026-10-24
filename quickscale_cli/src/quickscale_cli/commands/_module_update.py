"""Module update flow, local guards, and the update command.

Implementation detail of :mod:`quickscale_cli.commands.module_commands`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import click

from quickscale_cli.cli_help import QuickScaleCommand
from quickscale_cli.commands._module_shared import _UpdatePathSnapshot
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
import quickscale_cli.commands._module_update_seal as _module_update_seal


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
) -> bool:
    """Update a single module via git subtree pull."""
    click.echo(f"\n📥 Updating {name} module...")
    project_path = Path.cwd()

    try:
        # Phase 2.3b: ensure authoritative state exists before any mutation.
        # For config-only / non-consolidated projects, materialize state.yml
        # from quickscale.yml + legacy config.yml.  Abort if authoritative
        # project metadata (slug/package/theme) cannot be derived.
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
            return False

        if not _module_update_guard._check_local_pre_pull_guard(
            project_path, name, applied_state
        ):
            return False

        # SA204(e)/(g): capture the applied migration content identity before
        # the pull so the pull cannot replace it: an equal version label must
        # keep it, and from the migration freeze vintage on every pull must.
        # A vintage before the freeze is a release upgrade whose database
        # handling is the documented fresh-database path, so it compares
        # nothing there.
        applied_version = (
            applied_state.modules[name].version
            if applied_state is not None and name in applied_state.modules
            else None
        )
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
            return False
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
                return False

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

                # Sync generated-project dependencies after subtree pull so
                # the pinned compatible version range travels with the
                # updated module.yml (SA9.1).  Uses repin mode so existing
                # pre-SA9.1 path-style entries are corrected to the bounded
                # range (REV-001).  Failure triggers a full rollback
                # (REV-002).
                #
                # Pass ALL installed modules' options so shared-dependency
                # repinning picks the highest required compatible floor
                # across modules, not just the updated one (SA9.1-REV-004).
                all_modules_options: dict[str, dict[str, Any] | None] = {}
                for m_name in applied_state.modules:
                    m_state = applied_state.modules.get(m_name)
                    all_modules_options[m_name] = m_state.options if m_state else {}
                if not _module_embed._sync_module_dependencies(
                    project_path, all_modules_options
                ):
                    raise RuntimeError(f"Failed to sync dependency entries for {name}")

                _module_shared._sync_state_module_version(
                    project_path,
                    name,
                    installed_version,
                    commit_sha=source_ref,
                    branch=seal.branch,
                )

                _module_update_io._commit_module_update(name, info.prefix)
            except Exception as error:
                rollback_error = _rollback_failed_module_update(project_path, snapshots)
                if rollback_error is not None:
                    raise RuntimeError(rollback_error) from error
                raise

        click.secho(f"✅ Updated {name} successfully", fg="green")

        if output and not no_preview:
            click.echo("\n📋 Changes summary:")
            click.echo(output[:500])  # Show first 500 chars

        return True

    except Exception as error:
        _report_module_update_error(name, error)
        return False


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
) -> tuple[list[str], list[str]]:
    """Update each installed module in order; stop at the first failure."""
    failed_modules: list[str] = []
    updated_modules: list[str] = []
    for name, module_state in state.modules.items():
        plan = (seal_plans or {}).get(name)
        if plan is None:
            updated = _update_single_module(
                name,
                module_state,
                _MODULE_UPDATE_REMOTE,
                no_preview,
            )
        else:
            updated = _update_single_module(
                name,
                module_state,
                _MODULE_UPDATE_REMOTE,
                no_preview,
                seal_plan=plan,
            )
        if not updated:
            failed_modules.append(name)
            break
        updated_modules.append(name)
    return failed_modules, updated_modules


def _regenerate_update_wiring(project_path: Path) -> bool:
    """Regenerate the managed wiring after every pull; True on success."""
    try:
        # Any failure in this post-pull phase — loading state, regenerating,
        # recording hashes, or committing the wiring — must be treated as a
        # failed update so the modules committed by the pulls above are rolled
        # back with it.
        refreshed_state = _project_state_manager.ProjectStateManager(
            project_path
        ).load_state()
        if refreshed_state is None:
            raise _state_schema.StateError(
                "authoritative project state could not be loaded"
            )
        wiring_success, wiring_message = (
            _module_update_io._regenerate_and_record_managed_wiring(
                project_path,
                refreshed_state.project.package,
            )
        )
        if not wiring_success:
            raise RuntimeError(wiring_message)
        _module_update_io._commit_regenerated_managed_wiring(
            refreshed_state.project.package
        )
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


def _record_confirmed_update_adoption(project_path: Path, *, enabled: bool) -> None:
    """Record and commit the confirmed contract adoption when enabled.

    It runs only after every module mutation (the subtree pulls need a clean
    tree) and while the advisory lock is still held, then commits it so the
    next command's clean-tree check still passes (SA207).
    """
    if not enabled:
        return
    refreshed_state = _project_state_manager.ProjectStateManager(
        project_path
    ).load_state()
    if refreshed_state is None:
        return
    _contract_vintage.record_contract_adoption(refreshed_state, project_path)
    _module_update_io._commit_contract_adoption()


def _run_update_under_lock(
    state: Any,
    project_path: Path,
    *,
    no_preview: bool,
    confirm_contract_adoption: bool,
    allow_local_changes: bool,
) -> tuple[list[str], list[str], bool, bool]:
    """Run the locked update sequence.

    Returns ``(failed, updated, lock_failed, wiring_failed)``.
    """
    lock = _acquire_update_lock(project_path)
    try:
        # The hand-edit check runs under the lock, after the last read of
        # state and before the first pull, so it judges the tree the update
        # is about to replace.
        _module_update_guard._enforce_no_local_module_changes(
            state,
            project_path,
            allow_local_changes=allow_local_changes,
        )

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
            return [failed_name], [], False, False

        pre_update_head = _resolve_pre_update_head(project_path)
        failed_modules, updated_modules = _update_all_modules(
            state, no_preview=no_preview, seal_plans=seal_plans
        )

        # Refresh the lockfile once the whole set's dependency entries are
        # final.  A failure is a post-pull failure and rolls the set back.
        lock_failed = False
        if not failed_modules:
            lock_failed = not _module_update_io._refresh_update_lockfile(project_path)

        # Regenerate the managed wiring once every module pull succeeded.
        # Regeneration validates every embedded manifest against the running
        # core version, so it cannot run between the pulls of a mixed-version
        # set.  A failed regeneration restores the pre-update wiring and its
        # hash records, then aborts the command.
        wiring_failed = False
        if not failed_modules and not lock_failed:
            wiring_failed = not _regenerate_update_wiring(project_path)

        _record_confirmed_update_adoption(
            project_path,
            enabled=(
                confirm_contract_adoption
                and not failed_modules
                and not lock_failed
                and not wiring_failed
            ),
        )

        if failed_modules or lock_failed or wiring_failed:
            # A post-pull failure must not leave the modules committed before
            # it paired with the pre-update managed wiring.  The failed
            # module's own pull is restored too: its subtree pull committed
            # before the failure, so a refusal must not leave the rejected
            # content as the effective HEAD.  The rollback runs under the same
            # advisory lock that protects the update, so a concurrent update
            # cannot interleave with it.
            _module_update_io._roll_back_partial_module_update(
                project_path,
                pre_update_head,
                [*updated_modules, *failed_modules],
                state.project.package,
            )
    finally:
        lock.release()
    return failed_modules, updated_modules, lock_failed, wiring_failed


def _report_update_outcome(
    failed_modules: list[str],
    updated_modules: list[str],
    *,
    lock_failed: bool,
    wiring_failed: bool,
) -> None:
    """Print the failure report or the success banner for a finished update."""
    if failed_modules:
        click.secho(
            "\n❌ Module update stopped due to failure",
            fg="red",
            bold=True,
            err=True,
        )
        click.echo(
            f"Failed module(s): {', '.join(failed_modules)}",
            err=True,
        )
        if updated_modules:
            click.echo(
                "The modules updated before the failure were rolled back; "
                "fix the failure and re-run 'quickscale update'.",
                err=True,
            )
        raise click.Abort()

    if lock_failed:
        click.secho(
            "\n❌ Module update finished without a refreshed poetry.lock",
            fg="red",
            bold=True,
            err=True,
        )
        if updated_modules:
            click.echo(
                "The modules updated before the failure were rolled back; "
                "fix the dependency error and re-run 'quickscale update'.",
                err=True,
            )
        raise click.Abort()

    if wiring_failed:
        click.secho(
            "\n❌ Module update finished without regenerated managed wiring",
            fg="red",
            bold=True,
            err=True,
        )
        if updated_modules:
            click.echo(
                "The modules updated before the failure were rolled back; "
                "fix the failure and re-run 'quickscale update'.",
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
      - Refreshes poetry.lock after the module set's dependencies change
      - Commits each successful module update before continuing
    """
    try:
        _module_shared._validate_update_environment()

        project_path = Path.cwd()
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

        (
            failed_modules,
            updated_modules,
            lock_failed,
            wiring_failed,
        ) = _run_update_under_lock(
            state,
            project_path,
            no_preview=no_preview,
            confirm_contract_adoption=confirm_contract_adoption,
            allow_local_changes=allow_local_changes,
        )

        _report_update_outcome(
            failed_modules,
            updated_modules,
            lock_failed=lock_failed,
            wiring_failed=wiring_failed,
        )

    except _git_errors.GitError as e:
        click.secho(f"❌ Git error: {e}", fg="red", err=True)
        raise click.Abort()
    except click.Abort:
        raise
    except click.ClickException:
        raise
    except Exception as e:
        click.secho(f"❌ Unexpected error: {e}", fg="red", err=True)
        raise click.Abort()
