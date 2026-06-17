"""Module management commands for QuickScale CLI."""

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import click

from quickscale_cli.module_catalog import get_module_names, get_module_readiness_reason
from quickscale_cli.schema.config_schema import validate_config
from quickscale_cli.schema.state_schema import StateError, StateManager
from quickscale_cli.utils.module_dependency_sync import (
    DependencySyncError,
    resolve_embedded_module_install_path as _resolve_install_path_from_dependency_sync,
    sync_project_module_dependencies,
)

from quickscale_core.config import (
    ConfigError,
    add_module,
    load_config,
    normalize_installed_version,
    remove_module,
)
from quickscale_core.advisory_lock import (
    AdvisoryLock,
    AdvisoryLockContentionError,
)
from quickscale_core.project_state import (
    ProjectStateManager,
    check_version_drift,
)
from quickscale_core.manifest.loader import ManifestError, get_manifest_for_module
from quickscale_core.utils.git_utils import (
    GitError,
    check_remote_branch_exists,
    is_git_repo,
    is_working_directory_clean,
    resolve_remote_ref,
    run_git_subtree_add,
    run_git_subtree_pull,
    run_git_subtree_push,
)

from .module_config import (
    APPLY_MODULE_EXECUTION_MODE,
    MODULE_CONFIGURATOR_REGISTRY,
    STANDALONE_MODULE_EXECUTION_MODE,
    ModuleExecutionMode,
    assess_auth_migration_state,
    format_auth_migration_remediation,
)

# Available modules (including experimental for explicit CLI usage).
AVAILABLE_MODULES = get_module_names(include_experimental=True)


@dataclass(frozen=True)
class _UpdatePathSnapshot:
    """Filesystem snapshot used to roll back module update mutations."""

    path: Path
    backup_path: Path | None
    existed: bool
    is_dir: bool


def _validate_git_environment() -> bool:
    """Validate git repository state for module operations.

    Returns:
        True if valid, False otherwise
    """
    if not is_git_repo():
        click.secho("❌ Error: Not a git repository", fg="red", err=True)
        click.echo("\n💡 Tip: Run 'git init' to initialize a git repository", err=True)
        return False

    if not is_working_directory_clean():
        click.secho(
            "❌ Error: Working directory has uncommitted changes",
            fg="red",
            err=True,
        )
        click.echo(
            "\n💡 Tip: Commit or stash your changes before embedding modules",
            err=True,
        )
        return False

    return True


def _validate_module_not_exists(project_path: Path, module: str) -> bool:
    """Check if module already exists.

    Returns:
        True if module doesn't exist, False if it does
    """
    module_dir = project_path / "modules" / module
    if module_dir.exists():
        click.secho(
            f"❌ Error: Module '{module}' already exists at {module_dir}",
            fg="red",
            err=True,
        )
        click.echo("\n💡 Tip: Remove the existing module directory first", err=True)
        return False
    return True


def _validate_remote_branch(remote: str, branch: str, module: str) -> bool:
    """Check if branch exists on remote.

    Returns:
        True if branch exists, False otherwise
    """
    click.echo(f"🔍 Checking if {branch} exists on remote...")

    if not check_remote_branch_exists(remote, branch):
        click.secho(
            f"❌ Error: Module '{module}' is not yet implemented",
            fg="red",
            err=True,
        )
        click.echo(
            f"\n💡 The '{module}' module infrastructure is ready but contains "
            "only placeholder files.",
            err=True,
        )
        click.echo(
            f"\n📖 Branch '{branch}' does not exist on remote: {remote}", err=True
        )
        return False
    return True


def _check_auth_module_migrations(
    project_path: Path,
    non_interactive: bool,
    allow_unverifiable_auth_state: bool = False,
) -> bool:
    """Check if auth module can be embedded safely.

    Returns:
        True if safe to proceed, False if blocked
    """
    assessment = assess_auth_migration_state(project_path)
    if assessment.compatible:
        return True

    if assessment.unverifiable and allow_unverifiable_auth_state:
        click.secho(
            "\n⚠️  Auth module migration state could not be verified",
            fg="yellow",
            bold=True,
        )
        click.echo(f"\nReason: {assessment.reason}")
        click.echo(
            "\nContinuing because apply is configured to allow unverifiable "
            "migration state checks."
        )
        click.echo(
            "If your database already has baseline Django auth/admin/session/"
            "contenttypes migrations, a destructive reset may still be required."
        )
        click.echo("")
        click.echo(format_auth_migration_remediation(project_path))
        return True

    click.secho(
        "\n⚠️  Auth module migration guardrail triggered",
        fg="yellow",
        bold=True,
    )
    click.echo(f"\nReason: {assessment.reason}")
    click.echo(
        "\n❌ The auth module sets AUTH_USER_MODEL and must be embedded before "
        "incompatible baseline migrations."
    )
    click.echo("")
    click.echo(format_auth_migration_remediation(project_path))

    if non_interactive:
        click.secho(
            "\n❌ Cannot embed auth module in non-interactive mode when "
            f"state is {assessment.status}.",
            fg="red",
            err=True,
        )
        return False

    click.echo(
        "\n❓ Continue anyway? (only if you intentionally accept data-loss remediation)"
    )
    if not click.confirm("Continue?", default=False):
        click.echo("\n❌ Embedding cancelled")
        return False

    return True


def _resolve_embedded_module_install_path(
    project_path: Path,
    module: str,
) -> Path | None:
    """Return the installable package path for an embedded module, if any."""
    return _resolve_install_path_from_dependency_sync(project_path, module)


def _read_embedded_module_version(project_path: Path, module: str) -> str:
    """Read the canonical installed version from the embedded module manifest."""
    manifest = get_manifest_for_module(project_path, module, strict=True)
    assert manifest is not None
    normalized = normalize_installed_version(manifest.version)
    return normalized or manifest.version


def _sync_state_module_version(
    project_path: Path,
    module: str,
    version: str,
    *,
    commit_sha: str | None = None,
) -> None:
    """Mirror embedded module versions and provenance into applied state.

    Updates ``state.modules[module].version`` and, when *commit_sha* is
    provided, ``state.modules[module].commit_sha``.  The state file must
    already contain the module entry; modules absent from state are
    silently skipped (callers should ensure state is materialized first).
    """
    state_manager = StateManager(project_path)
    state = state_manager.load()
    if state is None or module not in state.modules:
        return

    state.modules[module].version = version
    if commit_sha is not None:
        state.modules[module].commit_sha = commit_sha
    state_manager.save(state)


def _warn_version_drift_for_update(
    project_path: Path,
    config: Any,
) -> list[Any]:
    """Surface module version drift between state and legacy config.

    The drift between ``.quickscale/state.yml`` and ``.quickscale/config.yml``
    is non-fatal: the update flow rewrites both sources, so warnings here
    are informational. They signal that an external process changed
    ``config.yml`` after the last apply.
    """
    manager = ProjectStateManager(project_path)
    try:
        state = manager.load_state()
    except StateError as error:
        click.secho(
            f"⚠️  Could not read .quickscale/state.yml for drift check: {error}",
            fg="yellow",
        )
        return []

    drift = check_version_drift(state, config)
    if not drift:
        return []

    click.secho(
        "\n⚠️  Module version drift between .quickscale/state.yml and "
        ".quickscale/config.yml:",
        fg="yellow",
        bold=True,
    )
    for warning in drift:
        click.echo(f"  • {warning.message}")
    click.echo(
        "\n💡 Update will reconcile .quickscale/config.yml to the freshly "
        "installed state-managed version. The drift is informational and not fatal.",
    )
    return drift


def _validate_module_readiness(
    module: str,
    *,
    execution_mode: ModuleExecutionMode = STANDALONE_MODULE_EXECUTION_MODE,
) -> bool:
    """Reject non-public modules from standalone embed/update flows."""
    readiness_reason = get_module_readiness_reason(module)
    if readiness_reason is None:
        return True

    click.secho(f"❌ Error: {readiness_reason}", fg="red", err=True)
    click.echo(
        "\n💡 Placeholder directories remain in the repository for documentation and "
        "future work only.",
        err=True,
    )
    return False


def _cleanup_failed_apply_embed(project_path: Path, module: str) -> None:
    """Best-effort cleanup for apply embeds that fail after subtree add."""
    module_path = project_path / "modules" / module
    try:
        if module_path.is_dir():
            shutil.rmtree(module_path)
        elif module_path.exists():
            module_path.unlink()
    except OSError as error:
        click.secho(
            f"⚠️  Failed to remove partial apply embed at {module_path}: {error}",
            fg="yellow",
        )

    try:
        remove_module(module, project_path)
    except OSError as error:
        click.secho(
            "⚠️  Failed to remove legacy tracking for partial apply embed "
            f"'{module}': {error}",
            fg="yellow",
        )


def _perform_module_embed(
    project_path: Path,
    module: str,
    remote: str,
    branch: str,
    config: dict[str, Any],
    *,
    sync_dependencies: bool = True,
    install_dependencies: bool = True,
    execution_mode: ModuleExecutionMode = STANDALONE_MODULE_EXECUTION_MODE,
) -> bool:
    """Execute the actual module embedding.

    Returns:
        True if successful, False otherwise
    """
    prefix = f"modules/{module}"
    click.echo(f"\n📦 Embedding {module} module from {branch}...")

    run_git_subtree_add(prefix=prefix, remote=remote, branch=branch, squash=True)

    try:
        installed_version = _read_embedded_module_version(project_path, module)
    except ManifestError as error:
        click.secho(
            f"\n❌ Embedded module manifest error: {error}",
            fg="red",
            err=True,
            bold=True,
        )
        click.echo(
            "\n💡 Fix the embedded module.yml or remove the partial module embed "
            "before continuing.",
            err=True,
        )
        if execution_mode == APPLY_MODULE_EXECUTION_MODE:
            _cleanup_failed_apply_embed(project_path, module)
        return False

    if execution_mode != APPLY_MODULE_EXECUTION_MODE:
        add_module(
            module_name=module,
            prefix=prefix,
            branch=branch,
            version=installed_version,
            project_path=project_path,
        )

    try:
        # Apply module-specific configuration
        configurator_entry = MODULE_CONFIGURATOR_REGISTRY.get(module)
        if configurator_entry is not None and config:
            if execution_mode == STANDALONE_MODULE_EXECUTION_MODE:
                configurator_entry.apply(project_path, config)
            else:
                configurator_entry.apply(
                    project_path, config, execution_mode=execution_mode
                )
    except Exception as error:
        if execution_mode == APPLY_MODULE_EXECUTION_MODE:
            _cleanup_failed_apply_embed(project_path, module)
            click.secho(
                f"\n❌ Apply embed failed for {module}: {error}",
                fg="red",
                err=True,
                bold=True,
            )
            return False
        raise

    if sync_dependencies:
        if not _sync_module_dependencies(project_path, module, config):
            if execution_mode == APPLY_MODULE_EXECUTION_MODE:
                _cleanup_failed_apply_embed(project_path, module)
            return False

    if (
        install_dependencies
        and _resolve_embedded_module_install_path(project_path, module) is not None
    ):
        if not _install_module_dependencies(project_path, module):
            if execution_mode == APPLY_MODULE_EXECUTION_MODE:
                _cleanup_failed_apply_embed(project_path, module)
            return False

    if execution_mode == APPLY_MODULE_EXECUTION_MODE:
        try:
            add_module(
                module_name=module,
                prefix=prefix,
                branch=branch,
                version=installed_version,
                project_path=project_path,
            )
        except Exception as error:
            _cleanup_failed_apply_embed(project_path, module)
            click.secho(
                f"\n❌ Failed to update legacy module tracking for {module}: {error}",
                fg="red",
                err=True,
                bold=True,
            )
            return False

    # Success message
    module_dir = project_path / "modules" / module
    click.secho(f"\n✅ Module '{module}' embedded successfully!", fg="green", bold=True)
    click.echo(f"   Location: {module_dir}")
    click.echo(f"   Branch: {branch}")

    return True


def embed_module(
    module: str,
    project_path: Path | None = None,
    remote: str = "https://github.com/Experto-AI/quickscale.git",
    non_interactive: bool = True,
    allow_unverifiable_auth_state: bool = False,
    skip_auth_migration_check: bool = False,
    sync_dependencies: bool = True,
    install_dependencies: bool = True,
    *,
    execution_mode: ModuleExecutionMode = STANDALONE_MODULE_EXECUTION_MODE,
) -> bool:
    """
    Embed a QuickScale module into a project via git subtree.

    This is the internal function used by `quickscale apply` to embed modules.
    It handles git subtree operations, module configuration, and dependency installation.

    Args:
        module: Module name to embed (auth, billing, teams, blog, listings)
        project_path: Path to the project directory. If None, uses current directory.
        remote: Git remote URL (default: QuickScale repository)
        non_interactive: Use default configuration without prompts
        allow_unverifiable_auth_state: Continue when auth migration state
            cannot be verified (used by quickscale apply for fresh projects)
        skip_auth_migration_check: Skip auth migration guardrail entirely
            (used by quickscale apply for freshly generated projects)
        sync_dependencies: Sync missing pyproject.toml dependency entries for the
            embedded module
        install_dependencies: Run `poetry install` after dependency sync
        execution_mode: Internal embedding mode used to control when managed
            wiring regeneration happens

    Returns:
        True if embedding succeeded, False otherwise

    Raises:
        GitError: If git operations fail
        click.Abort: If validation fails or user cancels

    """
    if project_path is None:
        project_path = Path.cwd()

    # Change to project directory for git operations
    original_cwd = Path.cwd()
    try:
        import os

        os.chdir(project_path)

        # Validation steps
        if not _validate_git_environment():
            return False

        if not _validate_module_not_exists(project_path, module):
            return False

        if not _validate_module_readiness(
            module,
            execution_mode=execution_mode,
        ):
            return False

        branch = f"splits/{module}-module"
        if not _validate_remote_branch(remote, branch, module):
            return False

        # Auth module special check
        if module == "auth" and not skip_auth_migration_check:
            if not _check_auth_module_migrations(
                project_path,
                non_interactive,
                allow_unverifiable_auth_state,
            ):
                return False

        # Interactive module configuration
        config: dict[str, Any] = {}
        configurator_entry = MODULE_CONFIGURATOR_REGISTRY.get(module)
        if configurator_entry is not None:
            config = configurator_entry.configure(non_interactive=non_interactive)

        # Perform embedding
        return _perform_module_embed(
            project_path,
            module,
            remote,
            branch,
            config,
            sync_dependencies=sync_dependencies,
            install_dependencies=install_dependencies,
            execution_mode=execution_mode,
        )

    except GitError as e:
        click.secho(f"❌ Git error: {e}", fg="red", err=True)
        return False
    except Exception as e:
        click.secho(f"❌ Unexpected error: {e}", fg="red", err=True)
        return False
    finally:
        # Always restore original directory
        import os

        os.chdir(original_cwd)


def _install_module_dependencies(project_path: Path, module: str) -> bool:
    """Install dependencies for a module.

    Args:
        project_path: Path to the project directory
        module: Module name

    Returns:
        True if installation succeeded, False otherwise
    """
    click.echo("\n📦 Installing dependencies...")
    try:
        module_dir = project_path / "modules" / module

        # Verify module was actually embedded
        if not module_dir.exists():
            click.secho(
                f"❌ Error: Module directory not found at {module_dir}",
                fg="red",
                err=True,
            )
            click.echo(
                "   The git subtree add may have failed. Check the output above.",
                err=True,
            )
            return False

        target_path = _resolve_embedded_module_install_path(project_path, module)
        if target_path is None:
            click.echo(
                f"  • No installable Python package detected for {module}; skipping Poetry install."
            )
            return True

        click.echo("  • Refreshing poetry.lock...")
        lock_result = subprocess.run(
            ["poetry", "lock"],
            cwd=project_path,
            capture_output=True,
            text=True,
        )

        if lock_result.returncode != 0:
            _print_installation_error(
                project_path,
                module,
                lock_result,
                command_name="poetry lock",
            )
            return False

        click.secho("  ✅ poetry.lock refreshed", fg="green")

        click.echo("  • Installing all dependencies...")
        result = subprocess.run(
            ["poetry", "install"],
            cwd=project_path,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            _print_installation_error(
                project_path,
                module,
                result,
            )
            return False

        click.secho("  ✅ Dependencies installed successfully", fg="green")
        return True

    except Exception as e:
        click.secho(
            f"\n❌ Unexpected error during dependency installation: {e}",
            fg="red",
            err=True,
        )
        click.echo(
            f"\n💡 Try running 'poetry install' manually in {project_path}",
            err=True,
        )
        return False


def _print_installation_error(
    project_path: Path,
    module: str,
    result: subprocess.CompletedProcess[str],
    *,
    command_name: str = "poetry install",
) -> None:
    """Print detailed installation error message."""
    click.secho(
        f"\n❌ Failed to run {command_name} for {module} module",
        fg="red",
        err=True,
        bold=True,
    )
    click.echo("\n📋 Error output (stderr):", err=True)
    click.echo(result.stderr, err=True)
    click.echo("\n📋 Standard output (stdout):", err=True)
    click.echo(result.stdout, err=True)

    click.echo("\n💡 To fix this manually:", err=True)
    click.echo(f"   1. cd {project_path}", err=True)
    click.echo("   2. poetry lock", err=True)
    click.echo("   3. poetry install", err=True)
    click.echo("   4. poetry run python manage.py migrate", err=True)


def _sync_module_dependencies(
    project_path: Path,
    module: str,
    config: dict[str, Any] | None = None,
) -> bool:
    """Sync missing project dependency entries for an embedded module."""
    click.echo("\n📦 Syncing dependency entries...")

    try:
        sync_result = sync_project_module_dependencies(
            project_path,
            {module: config or {}},
        )
    except (DependencySyncError, ManifestError) as error:
        click.secho(
            f"\n❌ Failed to sync {module} dependency entries",
            fg="red",
            err=True,
            bold=True,
        )
        click.echo(f"\n📋 Error: {error}", err=True)
        click.echo("\n💡 To fix this manually:", err=True)
        click.echo(f"   1. Ensure modules/{module}/module.yml is valid", err=True)
        click.echo(
            f"   2. Ensure modules/{module}/pyproject.toml contains matching Poetry dependency versions",
            err=True,
        )
        click.echo("   3. Re-run the embed/apply command", err=True)
        return False

    if sync_result.added_package_dependencies:
        click.echo(
            "  • Added package dependencies: "
            + ", ".join(sync_result.added_package_dependencies)
        )
    if sync_result.added_path_dependencies:
        click.echo(
            "  • Added module path dependencies: "
            + ", ".join(sync_result.added_path_dependencies)
        )
    if not sync_result.changed:
        click.echo("  • Dependency entries already in sync.")

    click.secho("  ✅ Dependency entries synced", fg="green")
    return True


def _validate_update_environment() -> None:
    """Validate git environment for update command.

    Raises:
        click.Abort: If validation fails
    """
    if not is_git_repo():
        click.secho("❌ Error: Not a git repository", fg="red", err=True)
        click.echo("\n💡 Tip: This command must be run from a git repository", err=True)
        raise click.Abort()

    if not is_working_directory_clean():
        click.secho(
            "❌ Error: Working directory has uncommitted changes",
            fg="red",
            err=True,
        )
        click.echo(
            "\n💡 Tip: Commit or stash your changes before updating modules",
            err=True,
        )
        raise click.Abort()


def _remove_update_path(path: Path) -> None:
    """Remove a file or directory if it exists."""
    if not path.exists():
        return

    if path.is_dir():
        shutil.rmtree(path)
        return

    path.unlink()


def _snapshot_update_path(
    path: Path,
    backup_root: Path,
    label: str,
) -> _UpdatePathSnapshot:
    """Snapshot a file or directory before a module update mutates it."""
    if not path.exists():
        return _UpdatePathSnapshot(
            path=path,
            backup_path=None,
            existed=False,
            is_dir=False,
        )

    backup_path = backup_root / label
    if path.is_dir():
        shutil.copytree(path, backup_path)
        return _UpdatePathSnapshot(
            path=path,
            backup_path=backup_path,
            existed=True,
            is_dir=True,
        )

    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_path)
    return _UpdatePathSnapshot(
        path=path,
        backup_path=backup_path,
        existed=True,
        is_dir=False,
    )


def _restore_update_snapshot(snapshot: _UpdatePathSnapshot) -> None:
    """Restore a single module update snapshot."""
    if not snapshot.existed:
        _remove_update_path(snapshot.path)
        return

    if snapshot.backup_path is None:
        raise RuntimeError(f"Missing rollback payload for {snapshot.path}")

    _remove_update_path(snapshot.path)
    if snapshot.is_dir:
        shutil.copytree(snapshot.backup_path, snapshot.path)
        return

    snapshot.path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(snapshot.backup_path, snapshot.path)


def _restore_update_snapshots(snapshots: list[_UpdatePathSnapshot]) -> None:
    """Restore all module update snapshots in reverse mutation order."""
    for snapshot in reversed(snapshots):
        _restore_update_snapshot(snapshot)


def _record_update_mutation_snapshots(
    project_path: Path,
    module_prefix: str,
    backup_root: Path,
) -> list[_UpdatePathSnapshot]:
    """Snapshot every artifact a subtree update may mutate locally."""
    snapshot_targets = [
        ("module-tree", project_path / module_prefix),
        ("legacy-config-yml", project_path / ".quickscale" / "config.yml"),
        ("state-yml", project_path / ".quickscale" / "state.yml"),
    ]
    return [
        _snapshot_update_path(path, backup_root, label)
        for label, path in snapshot_targets
    ]


def _refresh_git_index_after_update_rollback(
    project_path: Path,
    snapshots: list[_UpdatePathSnapshot],
) -> bool:
    """Best-effort index refresh so restored files do not remain staged."""
    tracked_paths = [
        str(snapshot.path.relative_to(project_path))
        for snapshot in snapshots
        if snapshot.path.exists() or snapshot.existed
    ]
    if not tracked_paths:
        return True

    result = subprocess.run(
        ["git", "add", "-A", *tracked_paths],
        cwd=project_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return True

    click.secho(
        "⚠️  Rollback restored files, but QuickScale could not refresh the git index.",
        fg="yellow",
        err=True,
    )
    if result.stderr:
        click.echo(result.stderr.strip(), err=True)
    return False


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
    manager = ProjectStateManager(project_path)

    # If state.yml already has consolidated sections, just load and return.
    if manager._state_file_has_consolidated_sections():
        return manager.load_state()

    # If state.yml exists but lacks consolidated sections, check whether
    # it is at least parseable.  A malformed state.yml must surface as
    # StateError (not silently fall through to quickscale.yml).
    if manager.state_file.exists():
        try:
            existing = manager._state_manager.load()
        except StateError:
            raise  # Let caller surface the malformed-state error.
        if existing is not None:
            # Parseable but non-consolidated — materialize.
            return manager.materialize_authoritative_state()

    # No state.yml at all — try quickscale.yml for project metadata.
    return manager.materialize_authoritative_state()


def _load_update_recovery_state(project_path: Path) -> Any | None:
    """Load the optional apply recovery snapshot used by update guardrails."""
    recovery_path = project_path / ".quickscale" / "apply-recovery.yml"
    if not recovery_path.exists():
        return None

    recovery_manager = StateManager(project_path)
    recovery_manager.state_file = recovery_path
    try:
        return recovery_manager.load()
    except StateError as error:
        raise RuntimeError(
            "Failed to load .quickscale/apply-recovery.yml: "
            f"{error}. Fix or clear the recovery snapshot before updating modules."
        ) from error


def _report_local_pre_pull_guard_block(
    module_name: str,
    lines: list[str],
) -> None:
    """Report a bounded local pre-pull guard block for module update."""
    click.secho(
        f"⚠️  Pre-pull local guard blocked update for {module_name}",
        fg="yellow",
        err=True,
        bold=True,
    )
    for line in lines:
        click.echo(line, err=True)


def _check_local_pre_pull_guard(
    project_path: Path,
    module_name: str,
    applied_state: Any,
) -> bool:
    """Block known-local unsafe updates before any subtree pull starts."""
    if applied_state is not None:
        module_state = applied_state.modules.get(module_name)
        if module_state is None:
            _report_local_pre_pull_guard_block(
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
            _report_local_pre_pull_guard_block(
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
        desired_config = validate_config(quickscale_config_path.read_text())
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
        _report_local_pre_pull_guard_block(
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
    _report_local_pre_pull_guard_block(module_name, drift_lines)
    return False


def _rollback_failed_module_update(
    project_path: Path,
    snapshots: list[_UpdatePathSnapshot],
) -> str | None:
    """Restore recorded module update snapshots after a failed mutation."""
    try:
        _restore_update_snapshots(snapshots)
    except Exception as rollback_error:
        return f"Rollback also failed: {rollback_error}"

    _refresh_git_index_after_update_rollback(project_path, snapshots)
    click.secho("✅ Restored pre-pull update snapshot", fg="green")
    return None


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
            source_ref = resolve_remote_ref(default_remote, info.branch)
        except GitError as ref_error:
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
                snapshots = _record_update_mutation_snapshots(
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
                output = run_git_subtree_pull(
                    prefix=info.prefix,
                    remote=default_remote,
                    branch=source_ref,
                    squash=True,
                )

                installed_version = _read_embedded_module_version(project_path, name)
                _sync_state_module_version(
                    project_path,
                    name,
                    installed_version,
                    commit_sha=source_ref,
                )

                _commit_module_update(name, info.prefix)
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

    except StateError as error:
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
        return False
    except ManifestError as e:
        click.secho(f"❌ Failed to update {name}: {e}", fg="red", err=True)
        click.echo(
            f"💡 Fix modules/{name}/module.yml or remove and re-embed the module.",
            err=True,
        )
        return False
    except GitError as e:
        click.secho(f"❌ Failed to update {name}: {e}", fg="red", err=True)
        click.echo(f"💡 Tip: Check for conflicts in modules/{name}/", err=True)
        return False
    except RuntimeError as e:
        click.secho(f"❌ Failed to update {name}: {e}", fg="red", err=True)
        return False
    except Exception as e:
        click.secho(f"❌ Failed to update {name}: {e}", fg="red", err=True)
        return False


def _commit_module_update(module_name: str, module_prefix: str) -> None:
    """Create a commit for a successfully updated module."""
    tracked_paths = [module_prefix]
    config_path = Path(".quickscale") / "config.yml"
    if config_path.exists():
        tracked_paths.append(str(config_path))
    state_path = Path(".quickscale") / "state.yml"
    if state_path.exists():
        tracked_paths.append(str(state_path))

    try:
        subprocess.run(
            ["git", "add", *tracked_paths],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to stage {module_name} update commit: {e.stderr}")

    cached_diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        capture_output=True,
        text=True,
    )

    if cached_diff.returncode == 0:
        click.echo(f"ℹ️  No staged changes detected for {module_name}; skipping commit")
        return

    if cached_diff.returncode != 1:
        raise GitError("Failed to inspect staged changes before module update commit")

    commit_message = f"chore(modules): update {module_name} module"
    try:
        subprocess.run(
            ["git", "commit", "-m", commit_message],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to commit {module_name} update: {e.stderr}")


@click.command()
@click.option(
    "--no-preview",
    is_flag=True,
    help="Skip diff preview before updating",
)
def update(no_preview: bool) -> None:
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
        _validate_update_environment()

        # Load consolidated state. ProjectStateManager.load_state() performs
        # read-through import of legacy config.yml tracking fields when
        # state.yml lacks consolidated tracking metadata.
        project_path = Path.cwd()
        manager = ProjectStateManager(project_path)
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

        # Surface module version drift between state and legacy config.
        # Non-fatal: update reconciles both files at the end.
        try:
            legacy_config = load_config()
        except ConfigError:
            legacy_config = None
        _warn_version_drift_for_update(project_path, legacy_config)

        for name in state.modules:
            if not _validate_module_readiness(name):
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
        lock = AdvisoryLock(project_path, operation="update")
        try:
            lock.acquire()
        except AdvisoryLockContentionError as error:
            click.secho(f"❌ {error}", fg="red", err=True)
            raise click.Abort() from error

        failed_modules: list[str] = []

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
            raise click.Abort()

        click.secho("\n🎉 Module update complete!", fg="green", bold=True)

    except GitError as e:
        click.secho(f"❌ Git error: {e}", fg="red", err=True)
        raise click.Abort()
    except click.Abort:
        raise
    except Exception as e:
        click.secho(f"❌ Unexpected error: {e}", fg="red", err=True)
        raise click.Abort()


@click.command()
@click.option(
    "--module",
    required=True,
    type=click.Choice(AVAILABLE_MODULES, case_sensitive=False),
    help="Module name to push changes for",
)
@click.option(
    "--branch",
    help="Feature branch name (default: feature/<module>-improvements)",
)
@click.option(
    "--remote",
    default="https://github.com/Experto-AI/quickscale.git",
    help="Git remote URL (default: QuickScale repository)",
)
def push(module: str, branch: str, remote: str) -> None:
    r"""
    Push your local module changes to a feature branch for contribution.

    \b
    Examples:
      quickscale push --module auth
      quickscale push --module auth --branch feature/fix-email-validation

    \b
    Workflow:
      1. This command pushes your changes to a feature branch
      2. You'll need to create a pull request manually on GitHub
      3. Maintainers review and merge to main branch
      4. Auto-split updates the module's split branch

    \b
    Note: You must have write access to the repository to push.
    For external contributions, fork the repository first.
    """
    try:
        # Validate git repository
        if not is_git_repo():
            click.secho("❌ Error: Not a git repository", fg="red", err=True)
            raise click.Abort()

        # Check if module is installed using consolidated state.
        # ProjectStateManager.load_state() performs read-through import of
        # legacy config.yml tracking fields when state.yml lacks consolidated
        # tracking metadata, so this works for both new and legacy projects.
        project_path = Path.cwd()
        manager = ProjectStateManager(project_path)
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
                "'quickscale push'.",
                err=True,
            )
            raise click.Abort() from error

        if state is None or module not in state.modules:
            click.secho(
                f"❌ Error: Module '{module}' is not installed", fg="red", err=True
            )
            click.echo(
                "\n💡 Tip: Add the module first with 'quickscale plan --add'",
                err=True,
            )
            raise click.Abort()

        module_state = state.modules[module]
        prefix = module_state.prefix

        if not prefix:
            click.secho(
                f"❌ Error: Module '{module}' has no recorded prefix in state",
                fg="red",
                err=True,
            )
            click.echo(
                "\n💡 Re-run 'quickscale apply' to consolidate module tracking "
                "metadata into .quickscale/state.yml.",
                err=True,
            )
            raise click.Abort()

        # Default branch name
        if not branch:
            branch = f"feature/{module}-improvements"

        # Show what will be pushed
        click.echo(f"📤 Preparing to push changes for module: {module}")
        click.echo(f"   Local prefix: {prefix}")
        click.echo(f"   Target branch: {branch}")
        click.echo(f"   Remote: {remote}")

        # Confirm push
        if not click.confirm("\n❓ Continue with push?"):
            click.echo("❌ Push cancelled")
            return

        # Push subtree
        click.echo(f"\n🚀 Pushing to {branch}...")
        run_git_subtree_push(prefix=prefix, remote=remote, branch=branch)

        # Success message
        click.secho("\n✅ Changes pushed successfully!", fg="green", bold=True)
        click.echo("\n📋 Next steps:")
        click.echo("  1. Create a pull request on GitHub:")
        click.echo(f"     https://github.com/Experto-AI/quickscale/pull/new/{branch}")
        click.echo("  2. Describe your changes and submit for review")
        click.echo("  3. After merge, the split branch will auto-update")

    except GitError as e:
        click.secho(f"❌ Git error: {e}", fg="red", err=True)
        click.echo(
            "\n💡 Tip: Make sure you have write access to the repository", err=True
        )
        raise click.Abort()
    except Exception as e:
        click.secho(f"❌ Unexpected error: {e}", fg="red", err=True)
        raise click.Abort()
