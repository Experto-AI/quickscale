"""Add-module flow for the plan command.

Implementation detail of :mod:`quickscale_cli.commands.plan_command`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from pathlib import Path
from typing import Any


from quickscale_core.contracts.module_catalog import ModuleCatalogEntry
from quickscale_core.schema.config_schema import QuickScaleConfig
from quickscale_core.schema.state_schema import QuickScaleState

import quickscale_cli.commands.plan_selection as _plan_selection
import quickscale_cli.commands._plan_shared as _plan_shared
import quickscale_core.schema.config_schema as _config_schema
import quickscale_core.utils.theme_validation as _theme_validation
import quickscale_core.schema.state_schema as _state_schema
import quickscale_cli.commands._plan_validation as _plan_validation
import click
import quickscale_core.contracts.module_catalog as _module_catalog


def _display_current_modules(existing_modules: list[str]) -> None:
    """Display currently installed modules"""
    click.echo("\n📦 Current Modules:")
    if existing_modules:
        for module in existing_modules:
            click.secho(f"   ✓ {module} (installed)", fg="green")
    else:
        click.echo("   (none installed)")


def _get_available_modules(
    existing_modules: list[str],
    *,
    include_experimental: bool = False,
) -> list[ModuleCatalogEntry]:
    """Get modules that are not yet installed.

    Returns:
        List of (module_id, description) tuples for available modules
    """
    available: list[ModuleCatalogEntry] = []
    for entry in _plan_selection._get_module_choices(
        include_experimental=include_experimental
    ):
        if entry.name not in existing_modules:
            available.append(entry)
    return available


def _display_available_modules(available: list[ModuleCatalogEntry]) -> None:
    """Display available modules for adding"""
    click.echo("\n📦 Available Modules to Add:")
    for i, entry in enumerate(available, start=1):
        click.echo(f"  {i}. {_plan_selection._format_module_choice(entry)}")


def _get_module_by_index_from_available(
    idx: int, available: list[ModuleCatalogEntry]
) -> ModuleCatalogEntry | None:
    """Get module ID by index from available list (0-based)."""
    if 0 <= idx < len(available):
        return available[idx]
    return None


def _get_module_by_name_from_available(
    name: str, available: list[ModuleCatalogEntry]
) -> ModuleCatalogEntry | None:
    """Get module ID by name from available list (case-insensitive)."""
    for entry in available:
        if name.lower() == entry.name.lower():
            return entry
    return None


def _parse_add_module_selection(
    choice: str, available: list[ModuleCatalogEntry]
) -> list[str]:
    """Parse module selection for add mode.

    Returns:
        List of selected module IDs

    Raises:
        ValueError: If selection is invalid
    """
    if not choice.strip():
        return []

    selected: list[str] = []
    parts = [p.strip() for p in choice.split(",")]

    for part in parts:
        selected_entry = None
        if part.isdigit():
            selected_entry = _get_module_by_index_from_available(
                int(part) - 1, available
            )
            if selected_entry is None:
                raise ValueError(f"Invalid number: {part}")
        else:
            selected_entry = _get_module_by_name_from_available(part, available)
            if selected_entry is None:
                raise ValueError(f"Unknown or already installed module: {part}")

        assert selected_entry is not None  # noqa: S101 - internal invariant guaranteed by the caller
        if not selected_entry.ready:
            raise ValueError(
                _module_catalog.get_module_readiness_reason(selected_entry.name)
                or f"Unknown or already installed module: {part}"
            )

        module_id = selected_entry.name
        if module_id not in selected:
            selected.append(module_id)

    return selected


def _select_modules_to_add(
    existing_modules: list[str],
    *,
    include_experimental: bool = False,
) -> list[str]:
    """Interactive module selection for adding to existing project

    Shows which modules are already installed and lets user select new ones.

    Args:
        existing_modules: List of module names already applied

    Returns:
        List of newly selected module names

    """
    _display_current_modules(existing_modules)

    available = _get_available_modules(
        existing_modules,
        include_experimental=include_experimental,
    )

    if not available:
        click.echo("\n📦 Available Modules to Add:")
        click.echo("   All modules are already installed!")
        return []

    _display_available_modules(available)

    click.echo(
        "\n  Enter numbers separated by commas (e.g., 1,3), or press Enter to skip"
    )

    while True:
        choice = click.prompt(
            "Select modules to add",
            default="",
            show_default=False,
        )

        try:
            return _parse_add_module_selection(choice, available)
        except ValueError as e:
            click.secho(f"Invalid selection: {e}. Please try again.", fg="red")


def _prepare_added_module_data(
    project_path: Path,
    all_existing: list[str],
    new_modules: list[str],
    existing_config: QuickScaleConfig | None,
    *,
    configure_modules: bool,
) -> tuple[list[str], dict[str, dict[str, Any]], list[str]]:
    """Prepare module options and required modules for add mode."""
    existing_options = _plan_shared._get_existing_module_options(
        project_path, existing_config
    )
    all_modules = _plan_shared._merge_module_names(all_existing, new_modules)

    if configure_modules:
        existing_options.update(
            _plan_shared._configure_selected_modules(
                new_modules,
                existing_options,
                new_modules=set(new_modules),
            )
        )
    else:
        for module_name in new_modules:
            existing_options.setdefault(module_name, {})

    all_modules, existing_options, required_modules = (
        _plan_shared._materialize_required_module_configs(
            all_modules,
            existing_options,
        )
    )
    if required_modules:
        new_modules = _plan_shared._merge_module_names(new_modules, required_modules)
        # Run required modules through registry-backed configurators so that
        # billing/CRM planner flows invoke configurators for required
        # notifications/orgs in the same planning pass.
        if configure_modules:
            existing_options.update(
                _plan_shared._configure_selected_modules(
                    required_modules,
                    existing_options,
                    new_modules=set(required_modules),
                )
            )

    return all_modules, existing_options, new_modules


def _build_add_config(
    existing_config: QuickScaleConfig | None,
    state: QuickScaleState | None,
    all_modules: list[str],
    module_options: dict[str, dict[str, Any]],
) -> QuickScaleConfig:
    """Build the desired configuration for add mode."""
    if existing_config is not None:
        docker_config = existing_config.docker
        project_config = existing_config.project
    else:
        assert state is not None  # noqa: S101 - internal invariant guaranteed by the caller
        docker_config = _config_schema.DockerConfig(
            start=False, build=False, create_superuser=False
        )
        project_config = _config_schema.ProjectConfig(
            slug=state.project.slug,
            package=state.project.package,
            theme=state.project.theme,
        )

    return _config_schema.QuickScaleConfig(
        version="1",
        project=project_config,
        modules=_plan_shared._build_module_configs(all_modules, module_options),
        docker=docker_config,
    )


def _preview_and_save_added_config(
    project_path: Path,
    yaml_content: str,
    new_modules: list[str],
) -> None:
    """Preview and save the updated configuration for add mode."""
    click.echo("\n" + "=" * 50)
    click.echo("📋 Updated Configuration:")
    click.echo("=" * 50)
    click.echo(yaml_content)
    click.echo("=" * 50)

    click.echo("\n🆕 New modules to add:")
    for module in new_modules:
        click.secho(f"   + {module}", fg="green")

    if not click.confirm("\n💾 Save updated configuration?", default=True):
        click.echo("❌ Cancelled")
        raise click.Abort()

    config_path = project_path / "quickscale.yml"
    with open(config_path, "w") as f:
        f.write(yaml_content)

    click.secho(f"\n✅ Configuration updated: {config_path}", fg="green", bold=True)

    click.echo("\n📋 Next steps:")
    click.echo("  quickscale apply     # Apply configuration to add modules")


def _handle_add_modules(
    project_path: Path,
    existing_config: QuickScaleConfig | None,
    *,
    include_experimental: bool = False,
    configure_modules: bool = False,
) -> None:
    """Handle --add flag: add modules to existing project

    Args:
        project_path: Path to the project directory
        existing_config: Current configuration if available

    """
    # Run read-only theme preflight before any mutation.
    try:
        _theme_validation.validate_theme_preflight(project_path)
    except _theme_validation.ThemeValidationError as exc:
        click.secho(
            "\n❌ Theme validation failed before module add:",
            fg="red",
            err=True,
            bold=True,
        )
        for line in str(exc).splitlines():
            click.echo(f"  • {line}", err=True)
        click.echo(
            "\n💡 Only 'showcase_react' is supported. "
            "Update project.theme in quickscale.yml to 'showcase_react'.",
            err=True,
        )
        raise click.Abort()

    click.echo("\n🔧 Adding modules to existing project")
    click.echo(f"   Project: {project_path}")

    all_existing = _plan_shared._collect_existing_modules(project_path, existing_config)

    # Select new modules to add
    new_modules = _select_modules_to_add(
        all_existing,
        include_experimental=include_experimental,
    )

    if not new_modules:
        click.echo("\n✅ No new modules selected")
        return

    state_manager = _state_schema.StateManager(project_path)
    state = state_manager.load()
    if existing_config is None and state is None:
        click.secho(
            "\n❌ Cannot add modules: No configuration or state found",
            fg="red",
            err=True,
        )
        raise click.Abort()

    all_modules, existing_options, new_modules = _prepare_added_module_data(
        project_path,
        all_existing,
        new_modules,
        existing_config,
        configure_modules=configure_modules,
    )
    config = _build_add_config(
        existing_config,
        state,
        all_modules,
        existing_options,
    )

    yaml_content = _plan_validation._validate_existing_project_config_or_abort(config)
    _preview_and_save_added_config(project_path, yaml_content, new_modules)
