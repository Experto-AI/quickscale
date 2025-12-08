"""Remove command for removing embedded modules

Implements `quickscale remove <module>` - removes an embedded module from a project
"""

import shutil
from pathlib import Path

import click
import yaml

from quickscale_cli.schema.state_schema import QuickScaleState, StateManager


def _update_quickscale_yml(project_path: Path, module_name: str) -> bool:
    """Remove module from quickscale.yml configuration"""
    config_path = project_path / "quickscale.yml"
    if not config_path.exists():
        return True  # No config file to update

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)

        if config and "modules" in config and module_name in config["modules"]:
            del config["modules"][module_name]

            with open(config_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        return True
    except Exception:
        return False


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


def _update_settings_py(project_path: Path, module_name: str) -> tuple[bool, str]:
    """Remove module configuration from settings.py"""
    # QuickScale uses settings/base.py structure
    settings_path = project_path / project_path.name / "settings" / "base.py"

    if not settings_path.exists():
        return True, "Settings file not found (skipped)"

    try:
        content = settings_path.read_text()

        # Look for the module configuration block and remove it
        # This is a best-effort removal - complex configurations may need manual cleanup
        module_app_name = f"quickscale_modules_{module_name}"

        # Simple approach: remove lines containing the module reference
        lines = content.splitlines()
        new_lines = []
        skip_until_empty = False

        for line in lines:
            if module_app_name in line:
                skip_until_empty = True
                continue
            if skip_until_empty and line.strip() == "":
                skip_until_empty = False
            if not skip_until_empty:
                new_lines.append(line)

        new_content = "\n".join(new_lines)

        # Only write if we made changes
        if new_content != content:
            settings_path.write_text(new_content)
            return True, "Removed module references from settings.py"

        return True, "No module references found in settings.py"

    except Exception as e:
        return False, f"Failed to update settings.py: {e}"


def _update_urls_py(project_path: Path, module_name: str) -> tuple[bool, str]:
    """Remove module URLs from urls.py"""
    urls_path = project_path / project_path.name / "urls.py"

    if not urls_path.exists():
        return True, "URLs file not found (skipped)"

    try:
        content = urls_path.read_text()

        # Look for the module URL include and remove it
        module_app_name = f"quickscale_modules_{module_name}"

        lines = content.splitlines()
        new_lines = [line for line in lines if module_app_name not in line]

        new_content = "\n".join(new_lines)

        # Only write if we made changes
        if new_content != content:
            urls_path.write_text(new_content)
            return True, "Removed module URLs from urls.py"

        return True, "No module URLs found in urls.py"

    except Exception as e:
        return False, f"Failed to update urls.py: {e}"


def _check_module_exists(
    project_path: Path, module_name: str, state_manager: StateManager
) -> tuple[bool, bool, QuickScaleState | None]:
    """Check if module exists in state or filesystem

    Returns:
        Tuple of (in_state, in_filesystem, state)
    """
    module_path = project_path / "modules" / module_name
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
    click.echo("  • Update quickscale.yml (if exists)")
    click.echo("  • Clean up settings.py and urls.py references")

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
    state: QuickScaleState | None, module_name: str, state_manager: StateManager
) -> None:
    """Remove module from state and save"""
    if not (state and module_name in state.modules):
        return

    del state.modules[module_name]
    try:
        state_manager.save(state)
        click.secho("  ✅ Updated .quickscale/state.yml", fg="green")
    except Exception as e:
        click.secho(f"  ⚠️  Failed to update state: {e}", fg="yellow")


def _perform_removal_steps(
    project_path: Path,
    module_name: str,
    state: QuickScaleState | None,
    state_manager: StateManager,
) -> None:
    """Execute all removal steps"""
    click.echo("\n🔧 Removing module...")

    # Step 1: Remove module directory
    success, message = _remove_module_directory(project_path, module_name)
    _log_step_result(success, message, is_error=True)

    # Step 2: Update state.yml
    _update_state_for_removal(state, module_name, state_manager)

    # Step 3: Update quickscale.yml
    yml_success = _update_quickscale_yml(project_path, module_name)
    _log_step_result(
        yml_success,
        "Updated quickscale.yml" if yml_success else "Failed to update quickscale.yml",
    )

    # Step 4: Update settings.py
    success, message = _update_settings_py(project_path, module_name)
    _log_step_result(success, message)

    # Step 5: Update urls.py
    success, message = _update_urls_py(project_path, module_name)
    _log_step_result(success, message)


def _show_success_message(module_name: str, keep_data: bool) -> None:
    """Display success message and next steps"""
    click.secho(
        f"\n✅ Module '{module_name}' removed successfully!", fg="green", bold=True
    )

    click.echo("\n📋 Next steps:")
    click.echo("  1. Review settings.py for any remaining module references")
    click.echo("  2. Review urls.py for any remaining module URL includes")
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
      4. Clean up settings.py and urls.py references (best effort)

    \b
    ⚠️  WARNING: This may cause data loss!
    Module database tables and migrations will remain, but the module code
    will be removed. To change immutable configuration options, remove the
    module and re-embed with new options.
    """
    project_path = Path.cwd()
    state_manager = StateManager(project_path)

    # Check if module exists
    module_in_state, module_in_filesystem, state = _check_module_exists(
        project_path, module_name, state_manager
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
    _perform_removal_steps(project_path, module_name, state, state_manager)

    # Success
    _show_success_message(module_name, keep_data)
