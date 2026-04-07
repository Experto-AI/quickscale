"""Remove command for removing embedded modules

Implements `quickscale remove <module>` - removes an embedded module from a project
"""

import copy
import shutil
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

import click

from quickscale_cli.schema.config_schema import (
    QuickScaleConfig,
    generate_yaml,
    validate_config,
)
from quickscale_cli.schema.state_schema import QuickScaleState, StateManager
from quickscale_cli.utils.module_wiring_manager import regenerate_managed_wiring
from quickscale_core.config.module_config import (
    load_config as load_legacy_module_config,
)
from quickscale_core.config.module_config import remove_module as remove_legacy_module


_APPLY_RECOVERY_FILENAME = "apply-recovery.yml"


@dataclass(frozen=True)
class PathSnapshot:
    """Filesystem snapshot used to roll back remove mutations."""

    path: Path
    backup_path: Path | None
    existed: bool
    is_dir: bool


@dataclass(frozen=True)
class RemovalPlan:
    """Validated removal plan built before any mutation occurs."""

    state: QuickScaleState | None
    updated_state: QuickScaleState | None
    state_needs_update: bool
    apply_recovery_state: QuickScaleState | None
    updated_apply_recovery_state: QuickScaleState | None
    apply_recovery_needs_update: bool
    apply_recovery_needs_delete: bool
    qs_config: QuickScaleConfig | None
    updated_qs_config: QuickScaleConfig | None
    config_needs_update: bool
    legacy_tracking_needs_update: bool
    project_package: str
    remaining_modules: list[str]


def _load_quickscale_config(project_path: Path) -> QuickScaleConfig | None:
    """Strictly load quickscale.yml when present."""
    config_path = project_path / "quickscale.yml"
    if not config_path.exists():
        return None

    try:
        return validate_config(config_path.read_text())
    except Exception as error:
        raise click.ClickException(f"Failed to load quickscale.yml: {error}") from error


def _load_state(
    project_path: Path, state_manager: StateManager
) -> QuickScaleState | None:
    """Strictly load .quickscale/state.yml when present."""
    del project_path
    try:
        return state_manager.load()
    except Exception as error:
        raise click.ClickException(
            f"Failed to load .quickscale/state.yml: {error}"
        ) from error


def apply_recovery_path(project_path: Path) -> Path:
    """Return .quickscale/apply-recovery.yml path."""
    return project_path / ".quickscale" / _APPLY_RECOVERY_FILENAME


def _get_apply_recovery_state_manager(project_path: Path) -> StateManager:
    """Return a state manager bound to .quickscale/apply-recovery.yml."""
    recovery_manager = StateManager(project_path)
    recovery_manager.state_file = apply_recovery_path(project_path)
    return recovery_manager


def _load_apply_recovery_state(project_path: Path) -> QuickScaleState | None:
    """Strictly load .quickscale/apply-recovery.yml when present."""
    try:
        return _get_apply_recovery_state_manager(project_path).load()
    except Exception as error:
        raise click.ClickException(
            f"Failed to load .quickscale/{_APPLY_RECOVERY_FILENAME}: {error}"
        ) from error


def _load_legacy_tracking(project_path: Path) -> set[str]:
    """Strictly load legacy module tracking when present."""
    try:
        legacy_config = load_legacy_module_config(project_path)
    except Exception as error:
        raise click.ClickException(
            f"Failed to load .quickscale/config.yml: {error}"
        ) from error

    return set(legacy_config.modules.keys())


def _resolve_project_package(
    qs_config: QuickScaleConfig | None,
    state: QuickScaleState | None,
) -> str:
    """Resolve the generated project package from strict preflight inputs."""
    if qs_config is not None:
        return qs_config.project.package

    if state is not None:
        return state.project.package

    raise click.ClickException(
        "Unable to resolve project identity. Expected quickscale.yml or "
        ".quickscale/state.yml with project.slug and project.package."
    )


def _build_updated_quickscale_config(
    qs_config: QuickScaleConfig | None,
    module_name: str,
) -> tuple[QuickScaleConfig | None, bool]:
    """Return the updated desired config plus whether a write is required."""
    if qs_config is None:
        return None, False

    updated_config = copy.deepcopy(qs_config)
    removed = updated_config.modules.pop(module_name, None) is not None
    return updated_config, removed


def _build_updated_state(
    state: QuickScaleState | None,
    module_name: str,
) -> tuple[QuickScaleState | None, bool]:
    """Return the updated applied state plus whether a write is required."""
    if state is None:
        return None, False

    updated_state = copy.deepcopy(state)
    removed = updated_state.modules.pop(module_name, None) is not None
    return updated_state, removed


def _apply_recovery_snapshot_is_obsolete(
    recovery_state: QuickScaleState,
    authoritative_state: QuickScaleState | None,
) -> bool:
    """Return whether a recovery snapshot would no longer affect apply planning."""
    if not recovery_state.modules:
        return True

    if authoritative_state is None:
        return False

    return recovery_state.modules == authoritative_state.modules


def _build_updated_apply_recovery_state(
    recovery_state: QuickScaleState | None,
    authoritative_state: QuickScaleState | None,
    module_name: str,
) -> tuple[QuickScaleState | None, bool, bool]:
    """Return the updated recovery snapshot plus whether to write or clear it."""
    if recovery_state is None:
        return None, False, False

    updated_recovery_state = copy.deepcopy(recovery_state)
    removed = updated_recovery_state.modules.pop(module_name, None) is not None
    if not removed:
        return recovery_state, False, False

    if _apply_recovery_snapshot_is_obsolete(
        updated_recovery_state,
        authoritative_state,
    ):
        return None, False, True

    return updated_recovery_state, True, False


def _discover_embedded_modules(project_path: Path) -> set[str]:
    """Discover embedded module directories present on disk."""
    modules_dir = project_path / "modules"
    if not modules_dir.exists():
        return set()

    return {
        path.name
        for path in modules_dir.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    }


def _remaining_modules_after_removal(
    project_path: Path,
    state: QuickScaleState | None,
    removed_module: str,
) -> list[str]:
    """Compute remaining installed modules after removing a module."""
    remaining_modules: set[str] = set()
    if state is not None:
        remaining_modules.update(state.modules.keys())

    remaining_modules.update(_discover_embedded_modules(project_path))
    remaining_modules.discard(removed_module)
    return sorted(remaining_modules)


def _managed_wiring_paths(project_path: Path, project_package: str) -> list[Path]:
    """Return managed wiring artifacts that remove may mutate."""
    package_dir = project_path / project_package
    return [
        package_dir / "settings" / "modules.py",
        package_dir / "urls_modules.py",
        package_dir / "quickscale_managed",
    ]


def _remove_path(path: Path) -> None:
    """Remove a file or directory if it exists."""
    if not path.exists():
        return

    if path.is_dir():
        shutil.rmtree(path)
        return

    path.unlink()


def _snapshot_path(path: Path, backup_root: Path, label: str) -> PathSnapshot:
    """Snapshot a file or directory before mutating it."""
    if not path.exists():
        return PathSnapshot(path=path, backup_path=None, existed=False, is_dir=False)

    backup_path = backup_root / label
    if path.is_dir():
        shutil.copytree(path, backup_path)
        return PathSnapshot(
            path=path, backup_path=backup_path, existed=True, is_dir=True
        )

    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_path)
    return PathSnapshot(path=path, backup_path=backup_path, existed=True, is_dir=False)


def _restore_snapshot(snapshot: PathSnapshot) -> None:
    """Restore a single file or directory snapshot."""
    if not snapshot.existed:
        _remove_path(snapshot.path)
        return

    if snapshot.backup_path is None:
        raise RuntimeError(f"Missing rollback payload for {snapshot.path}")

    _remove_path(snapshot.path)
    if snapshot.is_dir:
        shutil.copytree(snapshot.backup_path, snapshot.path)
        return

    snapshot.path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(snapshot.backup_path, snapshot.path)


def _restore_snapshots(snapshots: list[PathSnapshot]) -> None:
    """Restore all recorded snapshots in reverse mutation order."""
    for snapshot in reversed(snapshots):
        _restore_snapshot(snapshot)


def _record_mutation_snapshots(
    project_path: Path,
    module_name: str,
    plan: RemovalPlan,
    backup_root: Path,
) -> list[PathSnapshot]:
    """Snapshot every artifact this remove slice may mutate."""
    snapshot_targets: list[tuple[str, Path]] = [
        ("module-dir", project_path / "modules" / module_name),
        (
            "managed-settings-modules",
            project_path / plan.project_package / "settings" / "modules.py",
        ),
        (
            "managed-urls-modules",
            project_path / plan.project_package / "urls_modules.py",
        ),
        ("managed-package", project_path / plan.project_package / "quickscale_managed"),
    ]

    if plan.config_needs_update:
        snapshot_targets.append(("quickscale-yml", project_path / "quickscale.yml"))
    if plan.state_needs_update:
        snapshot_targets.append(("state-yml", state_manager_path(project_path)))
    if plan.apply_recovery_needs_update or plan.apply_recovery_needs_delete:
        snapshot_targets.append(
            ("apply-recovery-yml", apply_recovery_path(project_path))
        )
    if plan.legacy_tracking_needs_update:
        snapshot_targets.append(("legacy-config-yml", legacy_config_path(project_path)))

    return [
        _snapshot_path(path, backup_root, label) for label, path in snapshot_targets
    ]


def state_manager_path(project_path: Path) -> Path:
    """Return .quickscale/state.yml path."""
    return project_path / ".quickscale" / "state.yml"


def legacy_config_path(project_path: Path) -> Path:
    """Return .quickscale/config.yml path."""
    return project_path / ".quickscale" / "config.yml"


def _update_quickscale_yml(
    project_path: Path,
    updated_config: QuickScaleConfig | None,
) -> None:
    """Persist the updated desired configuration."""
    if updated_config is None:
        return

    config_path = project_path / "quickscale.yml"
    config_path.write_text(generate_yaml(updated_config))


def _update_apply_recovery_state(
    project_path: Path,
    updated_state: QuickScaleState | None,
) -> None:
    """Persist the updated apply recovery snapshot."""
    if updated_state is None:
        return

    _get_apply_recovery_state_manager(project_path).save(updated_state)


def _clear_apply_recovery_state(project_path: Path) -> None:
    """Remove any obsolete apply recovery snapshot."""
    recovery_path = apply_recovery_path(project_path)
    if not recovery_path.exists():
        return

    recovery_path.unlink()


def _remove_module_directory(project_path: Path, module_name: str) -> tuple[bool, str]:
    """Remove the module directory from the project"""
    module_path = project_path / "modules" / module_name

    if not module_path.exists():
        return True, f"Module directory not found (already removed): {module_path}"

    try:
        shutil.rmtree(module_path)
        return True, f"Removed module directory: {module_path}"
    except Exception as e:
        return False, f"Failed to remove module directory: {e}"


def _regenerate_managed_wiring_after_removal(
    project_path: Path,
    remaining_modules: list[str],
    project_package: str,
) -> tuple[bool, str]:
    """Regenerate managed module wiring from remaining modules."""
    success, message = regenerate_managed_wiring(
        project_path,
        module_names=remaining_modules,
        project_package=project_package,
    )
    if success:
        return True, "Regenerated managed module wiring files"
    return False, f"Failed to regenerate managed wiring files: {message}"


def _check_module_exists(
    project_path: Path,
    module_name: str,
    state_manager: StateManager,
    state: QuickScaleState | None = None,
) -> tuple[bool, bool, QuickScaleState | None]:
    """Check if module exists in state or filesystem

    Returns:
        Tuple of (in_state, in_filesystem, state)
    """
    module_path = project_path / "modules" / module_name
    if state is None:
        state = state_manager.load()

    module_in_state = state is not None and module_name in state.modules
    module_in_filesystem = module_path.exists()

    return module_in_state, module_in_filesystem, state


def _show_module_not_found_error(
    module_name: str, state: QuickScaleState | None
) -> None:
    """Display error when module is not found"""
    click.secho(
        f"❌ Module '{module_name}' is not installed in this project",
        fg="red",
        err=True,
    )
    click.echo("\n💡 Installed modules:", err=True)
    if state and state.modules:
        for name in state.modules:
            click.echo(f"   - {name}", err=True)
    else:
        click.echo("   (none)", err=True)


def _show_removal_warning(module_name: str, keep_data: bool) -> None:
    """Display warning about module removal"""
    click.secho(
        f"\n⚠️  WARNING: You are about to remove the '{module_name}' module",
        fg="yellow",
        bold=True,
    )
    click.echo("\nThis action will:")
    click.echo(f"  • Remove modules/{module_name}/ directory")
    click.echo("  • Update .quickscale/state.yml")
    click.echo("  • Update .quickscale/config.yml")
    click.echo("  • Update quickscale.yml (if exists)")
    click.echo("  • Update .quickscale/apply-recovery.yml (if pending)")
    click.echo("  • Regenerate managed module wiring files")

    if not keep_data:
        click.secho(
            "\n🚨 DATABASE WARNING: This does NOT remove database tables!",
            fg="red",
            bold=True,
        )
        click.echo("   Module migrations and data will remain in your database.")
        click.echo(
            "   To fully remove module data, run reverse migrations BEFORE removing:"
        )
        click.echo(f"   python manage.py migrate quickscale_modules_{module_name} zero")

    click.echo("\n💡 To change immutable options, re-embed after removal:")
    click.echo(f"   quickscale plan --add {module_name}")
    click.echo("   quickscale apply")


def _log_step_result(success: bool, message: str, is_error: bool = False) -> None:
    """Log the result of a removal step"""
    if is_error:
        icon = "✅" if success else "❌"
        color = "green" if success else "red"
    else:
        icon = "✅" if success else "⚠️ "
        color = "green" if success else "yellow"
    click.secho(f"  {icon} {message}", fg=color)


def _update_state_for_removal(
    updated_state: QuickScaleState | None,
    state_manager: StateManager,
) -> None:
    """Persist the updated applied state."""
    if updated_state is None:
        return

    state_manager.save(updated_state)


def _build_removal_plan(
    project_path: Path,
    module_name: str,
    state_manager: StateManager,
) -> RemovalPlan:
    """Load all required state before mutating the project."""
    state = _load_state(project_path, state_manager)
    apply_recovery_state = _load_apply_recovery_state(project_path)
    qs_config = _load_quickscale_config(project_path)
    legacy_modules = _load_legacy_tracking(project_path)

    project_package = _resolve_project_package(qs_config, state)
    package_dir = project_path / project_package
    if not package_dir.exists():
        raise click.ClickException(f"Python package directory not found: {package_dir}")

    updated_state, state_needs_update = _build_updated_state(state, module_name)
    (
        updated_apply_recovery_state,
        apply_recovery_needs_update,
        apply_recovery_needs_delete,
    ) = _build_updated_apply_recovery_state(
        apply_recovery_state,
        updated_state,
        module_name,
    )
    updated_qs_config, config_needs_update = _build_updated_quickscale_config(
        qs_config,
        module_name,
    )
    remaining_modules = _remaining_modules_after_removal(
        project_path,
        updated_state,
        module_name,
    )

    return RemovalPlan(
        state=state,
        updated_state=updated_state,
        state_needs_update=state_needs_update,
        apply_recovery_state=apply_recovery_state,
        updated_apply_recovery_state=updated_apply_recovery_state,
        apply_recovery_needs_update=apply_recovery_needs_update,
        apply_recovery_needs_delete=apply_recovery_needs_delete,
        qs_config=qs_config,
        updated_qs_config=updated_qs_config,
        config_needs_update=config_needs_update,
        legacy_tracking_needs_update=module_name in legacy_modules,
        project_package=project_package,
        remaining_modules=remaining_modules,
    )


def _rollback_failed_removal(
    snapshots: list[PathSnapshot],
    error: Exception,
) -> click.ClickException:
    """Restore all mutated artifacts after a failed removal attempt."""
    try:
        _restore_snapshots(snapshots)
    except Exception as rollback_error:
        return click.ClickException(
            f"Remove failed: {error}. Rollback also failed: {rollback_error}"
        )

    _log_step_result(True, "Restored rollback snapshot", is_error=True)
    return click.ClickException(f"Remove failed: {error}")


def _perform_removal_steps(
    project_path: Path,
    module_name: str,
    plan: RemovalPlan,
    state_manager: StateManager,
) -> None:
    """Execute the transactional removal steps."""
    click.echo("\n🔧 Removing module...")

    with TemporaryDirectory(prefix="quickscale-remove-") as temp_dir:
        snapshots = _record_mutation_snapshots(
            project_path,
            module_name,
            plan,
            Path(temp_dir),
        )

        try:
            if plan.config_needs_update:
                _update_quickscale_yml(project_path, plan.updated_qs_config)
                _log_step_result(True, "Updated quickscale.yml", is_error=True)

            if plan.state_needs_update:
                _update_state_for_removal(plan.updated_state, state_manager)
                _log_step_result(True, "Updated .quickscale/state.yml", is_error=True)

            if plan.apply_recovery_needs_update:
                _update_apply_recovery_state(
                    project_path,
                    plan.updated_apply_recovery_state,
                )
                _log_step_result(
                    True,
                    f"Updated .quickscale/{_APPLY_RECOVERY_FILENAME}",
                    is_error=True,
                )
            elif plan.apply_recovery_needs_delete:
                _clear_apply_recovery_state(project_path)
                _log_step_result(
                    True,
                    f"Cleared obsolete .quickscale/{_APPLY_RECOVERY_FILENAME}",
                    is_error=True,
                )

            if plan.legacy_tracking_needs_update:
                remove_legacy_module(module_name, project_path)
                _log_step_result(True, "Updated .quickscale/config.yml", is_error=True)

            success, message = _remove_module_directory(project_path, module_name)
            if not success:
                raise RuntimeError(message)
            _log_step_result(True, message, is_error=True)

            success, message = _regenerate_managed_wiring_after_removal(
                project_path,
                plan.remaining_modules,
                plan.project_package,
            )
            if not success:
                raise RuntimeError(message)
            _log_step_result(True, message, is_error=True)
        except Exception as error:
            raise _rollback_failed_removal(snapshots, error) from error


def _show_success_message(module_name: str, keep_data: bool) -> None:
    """Display success message and next steps"""
    click.secho(
        f"\n✅ Module '{module_name}' removed successfully!", fg="green", bold=True
    )

    click.echo("\n📋 Next steps:")
    click.echo("  1. Review managed wiring files for expected module list")
    click.echo("  2. Run quickscale apply to reconcile any remaining config drift")
    if not keep_data:
        click.echo(f"  3. If needed, manually remove database tables for {module_name}")
    click.echo("\n💡 To re-embed with different options:")
    click.echo(f"   quickscale plan --add {module_name}")
    click.echo("   quickscale apply")


@click.command()
@click.argument("module_name")
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Skip confirmation prompt",
)
@click.option(
    "--keep-data",
    is_flag=True,
    help="Keep database tables (don't run reverse migrations)",
)
def remove(module_name: str, force: bool, keep_data: bool) -> None:
    """
    Remove an embedded module from the project.

    \b
    Examples:
      quickscale remove auth
      quickscale remove auth --force
      quickscale remove billing --keep-data

    \b
    This command will:
      1. Remove the module directory from modules/
      2. Update .quickscale/state.yml
      3. Update quickscale.yml (if exists)
            4. Update or clear .quickscale/apply-recovery.yml when needed
            5. Regenerate managed module wiring files

    \b
    ⚠️  WARNING: This may cause data loss!
    Module database tables and migrations will remain, but the module code
    will be removed. To change immutable configuration options, remove the
    module and re-embed with new options.
    """
    project_path = Path.cwd()
    state_manager = StateManager(project_path)
    plan = _build_removal_plan(project_path, module_name, state_manager)

    # Check if module exists
    module_in_state, module_in_filesystem, state = _check_module_exists(
        project_path,
        module_name,
        state_manager,
        plan.state,
    )

    if not module_in_state and not module_in_filesystem:
        _show_module_not_found_error(module_name, state)
        raise click.Abort()

    # Show warning
    _show_removal_warning(module_name, keep_data)

    if not force:
        if not click.confirm(f"\n❓ Remove module '{module_name}'?", default=False):
            click.echo("❌ Cancelled")
            raise click.Abort()

    # Remove module
    _perform_removal_steps(project_path, module_name, plan, state_manager)

    # Success
    _show_success_message(module_name, keep_data)
