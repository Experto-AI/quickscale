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

from quickscale_cli.commands._module_shared import _UpdatePathSnapshot

import quickscale_core.project_state_manager as _project_state_manager
import quickscale_core.apply as _apply
import quickscale_cli.commands.module_output as _module_output
import quickscale_cli.commands._module_update_io as _module_update_io
import quickscale_core.schema.state_schema as _state_schema
import quickscale_core.manifest.loader_errors as _loader_errors
import quickscale_core.utils.git_errors as _git_errors
import quickscale_core.schema.config_schema as _config_schema
import quickscale_cli.commands._module_shared as _module_shared
import quickscale_cli.commands.contract_vintage as _contract_vintage
import quickscale_core.config as _config
import quickscale_core.advisory_lock as _advisory_lock
import quickscale_core.utils.git_repo as _git_repo
import quickscale_core.utils.git_subtree as _git_subtree
import quickscale_cli.commands._module_embed as _module_embed


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


def _load_update_recovery_state(project_path: Path) -> Any | None:
    """Load the optional apply recovery snapshot used by update guardrails.

    Returns the embedded applied-state (:class:`QuickScaleState`) when the
    recovery ledger file exists and is valid, or ``None`` when the file
    does not exist.  Malformed content raises :class:`LedgerError` which
    is surfaced as a :class:`RuntimeError`.
    """
    mgr = _apply.LedgerManager(project_path)
    if not mgr.ledger_file.exists():
        return None

    try:
        ledger = mgr.load()
    except _apply.LedgerError as error:
        raise RuntimeError(
            "Failed to load .quickscale/apply-recovery.yml: "
            f"{error}. Fix or clear the recovery snapshot before updating modules."
        ) from error

    if ledger is None:
        return None
    return ledger.applied_state


def _check_local_pre_pull_guard(
    project_path: Path,
    module_name: str,
    applied_state: Any,
) -> bool:
    """Block known-local unsafe updates before any subtree pull starts."""
    if applied_state is not None:
        module_state = applied_state.modules.get(module_name)
        if module_state is None:
            _module_output._report_local_pre_pull_guard_block(
                module_name,
                [
                    "",
                    ".quickscale/state.yml does not list this module as installed.",
                    "Reconcile local tracking with 'quickscale apply' before updating.",
                    "This guard uses only verified local state and does not predict remote compatibility.",
                ],
            )
            return False

        recovery_state = _load_update_recovery_state(project_path)
        if recovery_state is not None and module_name in recovery_state.modules:
            _module_output._report_local_pre_pull_guard_block(
                module_name,
                [
                    "",
                    "Pending .quickscale/apply-recovery.yml still references this module.",
                    "Finish or clear the local apply recovery flow before running 'quickscale update'.",
                    "This guard uses only verified local state and does not predict remote compatibility.",
                ],
            )
            return False
    else:
        module_state = None

    quickscale_config_path = project_path / "quickscale.yml"
    if not quickscale_config_path.exists() or module_state is None:
        return True

    try:
        desired_config = _config_schema.validate_config(
            quickscale_config_path.read_text()
        )
    except Exception as error:
        click.secho(
            "❌ Cannot update: quickscale.yml pre-pull check failed because the local desired state could not be validated.",
            fg="red",
            bold=True,
            err=True,
        )
        click.echo(f"Reason: {error}", err=True)
        click.echo(
            "💡 Fix quickscale.yml or run 'quickscale apply' to reconcile before updating.",
            err=True,
        )
        return False

    desired_module = desired_config.modules.get(module_name)
    if desired_module is None:
        _module_output._report_local_pre_pull_guard_block(
            module_name,
            [
                "",
                "quickscale.yml no longer includes this installed module.",
                f"Run 'quickscale remove {module_name}' or reconcile desired state with 'quickscale apply' before updating.",
                "This guard uses only verified local state and does not predict remote compatibility.",
            ],
        )
        return False

    desired_options = desired_module.options or {}
    applied_options = module_state.options or {}
    if desired_options == applied_options:
        return True

    drift_lines = [
        "",
        "Local desired state differs from applied module options.",
        "Run 'quickscale apply' before updating so local module configuration is reconciled first.",
        "Detected local-only option drift:",
    ]
    for option_name in sorted(set(desired_options) | set(applied_options)):
        old_value = applied_options.get(option_name)
        new_value = desired_options.get(option_name)
        if old_value == new_value:
            continue
        drift_lines.append(
            f"  • {module_name}.{option_name}: applied={old_value!r}, desired={new_value!r}"
        )
    drift_lines.append(
        "This guard uses only verified local state and does not predict remote compatibility."
    )
    _module_output._report_local_pre_pull_guard_block(module_name, drift_lines)
    return False


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


def _update_single_module(
    name: str, info: Any, default_remote: str, no_preview: bool
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

        if not _check_local_pre_pull_guard(project_path, name, applied_state):
            return False

        # Phase 2.3b: resolve the source ref once and reuse it for both
        # the subtree pull and state persistence (CR-PLAN-004).
        try:
            source_ref = _git_repo.resolve_remote_ref(default_remote, info.branch)
        except _git_errors.GitError as ref_error:
            click.secho(
                f"❌ Failed to resolve source ref for {name}: {ref_error}",
                fg="red",
                err=True,
                bold=True,
            )
            click.echo(
                "💡 Check network connectivity and remote branch availability.",
                err=True,
            )
            return False

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


@click.command()
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
def update(
    no_preview: bool,
    acknowledge_contract_vintage: bool,
    confirm_contract_adoption: bool,
) -> None:
    r"""
    Update all installed QuickScale modules to their latest versions.

    \b
    Examples:
      quickscale update           # Update with diff preview
      quickscale update --no-preview  # Update without preview

    \b
    This command:
      - Reads installed modules from .quickscale/config.yml
      - Updates ONLY modules you've explicitly installed
      - Shows a diff preview before updating (unless --no-preview)
      - Updates the installed version in config after successful update
            - Commits each successful module update before continuing
    """
    try:
        _module_shared._validate_update_environment()

        # Load consolidated state. ProjectStateManager.load_state() performs
        # read-through import of legacy config.yml tracking fields when
        # state.yml lacks consolidated tracking metadata.
        project_path = Path.cwd()
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
            return

        _contract_vintage.enforce_shipped_contract_vintage(
            state,
            state.modules,
            operation="'quickscale update'",
            acknowledged=acknowledge_contract_vintage or confirm_contract_adoption,
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

        # Acquire advisory lock after confirmation but before mutation.
        lock = _advisory_lock.AdvisoryLock(project_path, operation="update")
        try:
            lock.acquire()
        except _advisory_lock.AdvisoryLockContentionError as error:
            click.secho(f"❌ {error}", fg="red", err=True)
            raise click.Abort() from error

        failed_modules: list[str] = []
        updated_modules: list[str] = []
        wiring_failed = False
        try:
            pre_update_head = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
                ["git", "rev-parse", "HEAD"],  # noqa: S607 - PATH-resolved executable by design
                cwd=project_path,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except subprocess.CalledProcessError:
            # ``_validate_update_environment`` already required a git
            # repository; without a resolvable HEAD there is no committed
            # state to roll back to, so partial-failure rollback is skipped.
            pre_update_head = ""

        try:
            # Update each module
            for name, module_state in state.modules.items():
                if not _update_single_module(
                    name,
                    module_state,
                    "https://github.com/Experto-AI/quickscale.git",
                    no_preview,
                ):
                    failed_modules.append(name)
                    break
                updated_modules.append(name)

            # Regenerate the managed wiring once every module pull succeeded.
            # Regeneration validates every embedded manifest against the
            # running core version, so it cannot run between the pulls of a
            # mixed-version set.  A failed regeneration restores the
            # pre-update wiring and its hash records, then aborts the command.
            if not failed_modules:
                # Any failure in this post-pull phase — loading state,
                # regenerating, recording hashes, or committing the wiring —
                # must be treated as a failed update so the modules committed
                # by the pulls above are rolled back with it.
                try:
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
                except Exception as error:  # noqa: BLE001 - rollback below
                    wiring_failed = True
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

            # Record the confirmed adoption only after every module mutation
            # (the subtree pulls need a clean tree) and while the advisory lock
            # is still held, then commit it so the next command's clean-tree
            # check still passes (SA207).
            if confirm_contract_adoption and not failed_modules and not wiring_failed:
                refreshed_state = _project_state_manager.ProjectStateManager(
                    project_path
                ).load_state()
                if refreshed_state is not None:
                    _contract_vintage.record_contract_adoption(
                        refreshed_state, project_path
                    )
                    _module_update_io._commit_contract_adoption()

            if failed_modules or wiring_failed:
                # A post-pull failure must not leave the modules committed
                # before it paired with the pre-update managed wiring.  The
                # rollback runs under the same advisory lock that protects the
                # update, so a concurrent update cannot interleave with it.
                _module_update_io._roll_back_partial_module_update(
                    project_path,
                    pre_update_head,
                    updated_modules,
                    state.project.package,
                )
        finally:
            lock.release()

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
