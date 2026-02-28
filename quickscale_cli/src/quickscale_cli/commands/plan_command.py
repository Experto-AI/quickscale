"""Plan command for interactive project configuration

Implements `quickscale plan <name>` - interactive wizard that creates quickscale.yml
Also supports `--add` and `--reconfigure` flags for existing projects.
"""

import keyword
import re
from pathlib import Path

import click

from quickscale_cli.module_catalog import get_module_entries
from quickscale_cli.schema.config_schema import (
    DockerConfig,
    ModuleConfig,
    ProjectConfig,
    QuickScaleConfig,
    generate_yaml,
    validate_config,
)
from quickscale_cli.schema.state_schema import QuickScaleState, StateManager
from quickscale_core.utils.file_utils import validate_project_name

# Available themes for selection
AVAILABLE_THEMES = [
    ("showcase_react", "React + TypeScript + shadcn/ui (default, production-ready)"),
    ("showcase_html", "Pure HTML + CSS (simpler alternative)"),
    ("showcase_htmx", "HTMX + Alpine.js (coming in v0.78.0)"),
]


def _get_module_choices(
    *, include_experimental: bool = False
) -> list[tuple[str, str, bool]]:
    """Return module choices with experimental marker."""
    entries = get_module_entries(include_experimental=include_experimental)
    return [(entry.name, entry.description, entry.experimental) for entry in entries]


def _get_theme_by_index(idx: int) -> str | None:
    """Get theme ID by index (0-based)"""
    if 0 <= idx < len(AVAILABLE_THEMES):
        return AVAILABLE_THEMES[idx][0]
    return None


def _get_theme_by_name(name: str) -> str | None:
    """Get theme ID by name (case-insensitive)"""
    for theme_id, _ in AVAILABLE_THEMES:
        if name.lower() == theme_id.lower():
            return theme_id
    return None


def _confirm_unimplemented_theme(theme_id: str) -> bool:
    """Confirm use of unimplemented theme"""
    if theme_id in ("showcase_html", "showcase_react"):
        return True

    click.secho(
        f"\n⚠️  Theme '{theme_id}' is not yet implemented. "
        "It will be available in a future release (v0.78.0).",
        fg="yellow",
    )
    return click.confirm("Use this theme anyway?", default=False)


def _select_theme() -> str:
    """Interactive theme selection"""
    click.echo("\n🎨 Select a theme for your project:")
    for i, (tid, description) in enumerate(AVAILABLE_THEMES, start=1):
        status = " ⚠️  not yet implemented" if tid == "showcase_htmx" else ""
        click.echo(f"  {i}. {tid} - {description}{status}")

    while True:
        choice = click.prompt(
            "\nEnter theme number or name",
            default="1",
            show_default=True,
        )

        # Try numeric choice first
        theme_id: str | None
        if choice.isdigit():
            theme_id = _get_theme_by_index(int(choice) - 1)
        else:
            theme_id = _get_theme_by_name(choice)

        if theme_id is not None and _confirm_unimplemented_theme(theme_id):
            return theme_id

        if theme_id is None:
            click.secho("Invalid choice. Please try again.", fg="red")


def _parse_module_choice(
    part: str, available_modules: list[tuple[str, str, bool]]
) -> str | None:
    """Parse a single module choice (number or name).

    Returns:
        Module ID if valid, None otherwise

    Raises:
        ValueError: If choice is invalid
    """
    if part.isdigit():
        idx = int(part) - 1
        if 0 <= idx < len(available_modules):
            return available_modules[idx][0]
        raise ValueError(f"Invalid number: {part}")

    # Handle module name
    for module_id, _, _ in available_modules:
        if part.lower() == module_id.lower():
            return module_id

    raise ValueError(f"Unknown module: {part}")


def _parse_module_selection(
    choice: str,
    available_modules: list[tuple[str, str, bool]],
) -> list[str]:
    """Parse comma-separated module selection.

    Returns:
        List of unique module IDs

    Raises:
        ValueError: If any choice is invalid
    """
    if not choice.strip():
        return []

    selected: list[str] = []
    parts = [p.strip() for p in choice.split(",")]

    for part in parts:
        module_id = _parse_module_choice(part, available_modules)
        if module_id and module_id not in selected:
            selected.append(module_id)

    return selected


def _select_modules(*, include_experimental: bool = False) -> list[str]:
    """Interactive module selection"""
    available_modules = _get_module_choices(include_experimental=include_experimental)
    click.echo("\n📦 Select modules to embed (optional):")
    for i, (module_id, description, experimental) in enumerate(
        available_modules,
        start=1,
    ):
        experimental_label = " (experimental)" if experimental else ""
        click.echo(f"  {i}. {module_id} - {description}{experimental_label}")

    click.echo(
        "\n  Enter numbers separated by commas (e.g., 1,3), or press Enter to skip"
    )

    while True:
        choice = click.prompt(
            "Select modules",
            default="",
            show_default=False,
        )

        try:
            return _parse_module_selection(choice, available_modules)
        except ValueError as e:
            click.secho(f"Invalid selection: {e}. Please try again.", fg="red")


def _configure_docker() -> tuple[bool, bool, bool]:
    """Interactive Docker configuration"""
    click.echo("\n🐳 Docker Configuration:")
    start = click.confirm("  Start Docker services after apply?", default=True)
    build = click.confirm("  Build Docker images?", default=True) if start else False
    create_superuser = (
        click.confirm(
            "  Create Django superuser on first startup?",
            default=False,
        )
        if start
        else False
    )
    return start, build, create_superuser


def _detect_existing_project() -> tuple[Path | None, QuickScaleConfig | None]:
    """Detect if we're in an existing QuickScale project

    Returns:
        Tuple of (project_path, existing_config) if project found, (None, None) otherwise

    """
    cwd = Path.cwd()

    # Check for quickscale.yml in current directory
    config_path = cwd / "quickscale.yml"
    state_path = cwd / ".quickscale" / "state.yml"

    if config_path.exists():
        try:
            yaml_content = config_path.read_text()
            config = validate_config(yaml_content)
            return cwd, config
        except Exception:
            # Config exists but is invalid - treat as existing project anyway
            return cwd, None
    elif state_path.exists():
        # State exists but no config - project exists but config is missing
        return cwd, None

    return None, None


def _get_applied_modules(project_path: Path) -> list[str]:
    """Get list of modules already applied to the project

    Returns:
        List of module names that have been applied

    """
    state_manager = StateManager(project_path)
    state = state_manager.load()

    if state is None:
        return []

    return list(state.modules.keys())


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
) -> list[tuple[str, str]]:
    """Get modules that are not yet installed.

    Returns:
        List of (module_id, description) tuples for available modules
    """
    available = []
    for module_id, description, _ in _get_module_choices(
        include_experimental=include_experimental
    ):
        if module_id not in existing_modules:
            available.append((module_id, description))
    return available


def _display_available_modules(available: list[tuple[str, str]]) -> None:
    """Display available modules for adding"""
    click.echo("\n📦 Available Modules to Add:")
    for i, (module_id, description) in enumerate(available, start=1):
        click.echo(f"  {i}. {module_id} - {description}")


def _get_module_by_index_from_available(
    idx: int, available: list[tuple[str, str]]
) -> str | None:
    """Get module ID by index from available list (0-based)."""
    if 0 <= idx < len(available):
        return available[idx][0]
    return None


def _get_module_by_name_from_available(
    name: str, available: list[tuple[str, str]]
) -> str | None:
    """Get module ID by name from available list (case-insensitive)."""
    for module_id, _ in available:
        if name.lower() == module_id.lower():
            return module_id
    return None


def _parse_add_module_selection(
    choice: str, available: list[tuple[str, str]]
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
        module_id = None
        if part.isdigit():
            module_id = _get_module_by_index_from_available(int(part) - 1, available)
            if module_id is None:
                raise ValueError(f"Invalid number: {part}")
        else:
            module_id = _get_module_by_name_from_available(part, available)
            if module_id is None:
                raise ValueError(f"Unknown or already installed module: {part}")

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


def _handle_add_modules(
    project_path: Path,
    existing_config: QuickScaleConfig | None,
    *,
    include_experimental: bool = False,
) -> None:
    """Handle --add flag: add modules to existing project

    Args:
        project_path: Path to the project directory
        existing_config: Current configuration if available

    """
    click.echo("\n🔧 Adding modules to existing project")
    click.echo(f"   Project: {project_path}")

    # Get already applied modules
    applied_modules = _get_applied_modules(project_path)

    # Also include modules in config but not yet applied
    config_modules = list(existing_config.modules.keys()) if existing_config else []
    all_existing = list(set(applied_modules + config_modules))

    # Select new modules to add
    new_modules = _select_modules_to_add(
        all_existing,
        include_experimental=include_experimental,
    )

    if not new_modules:
        click.echo("\n✅ No new modules selected")
        return

    # Load or create config
    if existing_config:
        config = existing_config
    else:
        # Create minimal config from state
        state_manager = StateManager(project_path)
        state = state_manager.load()

        if state is None:
            click.secho(
                "\n❌ Cannot add modules: No configuration or state found",
                fg="red",
                err=True,
            )
            raise click.Abort()

        config = QuickScaleConfig(
            version="1",
            project=ProjectConfig(
                slug=state.project.slug,
                package=state.project.package,
                theme=state.project.theme,
            ),
            modules={
                name: ModuleConfig(name=name, options={})
                for name in state.modules.keys()
            },
            docker=DockerConfig(start=False, build=False, create_superuser=False),
        )

    # Add new modules to config
    for module_id in new_modules:
        config.modules[module_id] = ModuleConfig(name=module_id, options={})

    # Generate YAML
    yaml_content = generate_yaml(config)

    # Preview configuration
    click.echo("\n" + "=" * 50)
    click.echo("📋 Updated Configuration:")
    click.echo("=" * 50)
    click.echo(yaml_content)
    click.echo("=" * 50)

    # Highlight new modules
    click.echo("\n🆕 New modules to add:")
    for module in new_modules:
        click.secho(f"   + {module}", fg="green")

    # Confirm save
    if not click.confirm("\n💾 Save updated configuration?", default=True):
        click.echo("❌ Cancelled")
        raise click.Abort()

    # Save configuration
    config_path = project_path / "quickscale.yml"
    with open(config_path, "w") as f:
        f.write(yaml_content)

    click.secho(f"\n✅ Configuration updated: {config_path}", fg="green", bold=True)

    # Next steps
    click.echo("\n📋 Next steps:")
    click.echo("  quickscale apply     # Apply configuration to add modules")


def _get_project_info_for_reconfig(
    state: QuickScaleState | None,
    existing_config: QuickScaleConfig | None,
    project_path: Path,
) -> tuple[str, str, str]:
    """Get project slug, package, and theme for reconfiguration.

    Returns:
        Tuple of (project_slug, package_name, current_theme)
    """
    if state:
        return state.project.slug, state.project.package, state.project.theme
    if existing_config:
        return (
            existing_config.project.slug,
            existing_config.project.package,
            existing_config.project.theme,
        )
    project_slug = project_path.name
    return project_slug, project_slug.replace("-", "_"), "showcase_react"


def _collect_existing_modules(
    project_path: Path, existing_config: QuickScaleConfig | None
) -> list[str]:
    """Collect all existing modules from state and config."""
    applied_modules = _get_applied_modules(project_path)
    config_modules = list(existing_config.modules.keys()) if existing_config else []
    return list(set(applied_modules + config_modules))


def _display_reconfig_modules_status(
    all_existing: list[str], applied_modules: list[str]
) -> None:
    """Display currently configured modules."""
    click.echo("\n📦 Module Configuration:")
    if all_existing:
        click.echo("   Currently configured modules:")
        for module in all_existing:
            status = "(applied)" if module in applied_modules else "(pending)"
            click.secho(f"   ✓ {module} {status}", fg="green")


def _handle_reconfigure(
    project_path: Path,
    existing_config: QuickScaleConfig | None,
    *,
    include_experimental: bool = False,
) -> None:
    """Handle --reconfigure flag: reconfigure existing project

    Args:
        project_path: Path to the project directory
        existing_config: Current configuration if available

    """
    click.echo("\n🔧 Reconfiguring existing project")
    click.echo(f"   Project: {project_path}")

    # Load state for project info
    state_manager = StateManager(project_path)
    state = state_manager.load()

    if state is None and existing_config is None:
        click.secho(
            "\n❌ Cannot reconfigure: No configuration or state found",
            fg="red",
            err=True,
        )
        raise click.Abort()

    # Get current project info
    project_slug, project_package, current_theme = _get_project_info_for_reconfig(
        state, existing_config, project_path
    )

    click.echo(f"\n📁 Project: {project_slug}")
    click.echo(f"   Package: {project_package}")
    click.secho(f"   Theme: {current_theme} (locked after creation)", fg="cyan")

    # Get applied modules
    applied_modules = _get_applied_modules(project_path)
    all_existing = _collect_existing_modules(project_path, existing_config)
    _display_reconfig_modules_status(all_existing, applied_modules)

    # Ask if user wants to add more modules
    if click.confirm("\n   Add more modules?", default=False):
        new_modules = _select_modules_to_add(
            all_existing,
            include_experimental=include_experimental,
        )
        all_modules = all_existing + new_modules
    else:
        all_modules = all_existing

    # Configure Docker
    docker_start, docker_build, docker_create_superuser = _configure_docker()

    # Build configuration
    modules = {
        module_id: ModuleConfig(name=module_id, options={}) for module_id in all_modules
    }

    config = QuickScaleConfig(
        version="1",
        project=ProjectConfig(
            slug=project_slug,
            package=project_package,
            theme=current_theme,
        ),
        modules=modules,
        docker=DockerConfig(
            start=docker_start,
            build=docker_build,
            create_superuser=docker_create_superuser,
        ),
    )

    # Generate YAML
    yaml_content = generate_yaml(config)

    # Preview configuration
    click.echo("\n" + "=" * 50)
    click.echo("📋 Updated Configuration:")
    click.echo("=" * 50)
    click.echo(yaml_content)
    click.echo("=" * 50)

    # Confirm save
    if not click.confirm("\n💾 Save configuration?", default=True):
        click.echo("❌ Cancelled")
        raise click.Abort()

    # Save configuration
    config_path = project_path / "quickscale.yml"
    with open(config_path, "w") as f:
        f.write(yaml_content)

    click.secho(f"\n✅ Configuration saved: {config_path}", fg="green", bold=True)

    # Next steps
    click.echo("\n📋 Next steps:")
    click.echo("  quickscale apply     # Apply configuration changes")


def _handle_existing_project_mode(
    add_modules: bool,
    reconfigure: bool,
    *,
    include_experimental: bool = False,
) -> bool:
    """Handle --add and --reconfigure flags for existing projects.

    Returns:
        True if handled (should return from plan), False to continue with new project
    """
    if not add_modules and not reconfigure:
        return False

    project_path, existing_config = _detect_existing_project()
    if project_path is None:
        click.secho(
            "\n❌ Not in a QuickScale project directory",
            fg="red",
            err=True,
        )
        click.echo(
            "   Run this command from a directory with quickscale.yml or .quickscale/state.yml",
            err=True,
        )
        raise click.Abort()

    if add_modules:
        _handle_add_modules(
            project_path,
            existing_config,
            include_experimental=include_experimental,
        )
    else:
        _handle_reconfigure(
            project_path,
            existing_config,
            include_experimental=include_experimental,
        )

    return True


def _validate_new_project_slug(slug: str | None) -> str:
    """Validate project slug for new projects.

    Returns:
        Validated project slug

    Raises:
        click.Abort: If name is invalid
    """
    if not slug:
        click.secho(
            "\n❌ Error: PROJECT_SLUG is required for new projects",
            fg="red",
            err=True,
        )
        click.echo("\n💡 Usage examples:", err=True)
        click.echo(
            "   quickscale plan myapp              # Create new project", err=True
        )
        click.echo(
            "   quickscale plan --add              # Add modules to existing", err=True
        )
        click.echo(
            "   quickscale plan --reconfigure      # Reconfigure existing", err=True
        )
        raise click.Abort()

    is_valid, error_message = validate_project_name(slug)
    if not is_valid:
        click.secho(
            f"\n❌ Error: '{slug}' is not a valid project slug",
            fg="red",
            err=True,
        )
        click.echo(f"   {error_message}", err=True)
        raise click.Abort()

    return slug


def _validate_package_name(package_name: str) -> None:
    """Validate explicit project package value."""
    if not package_name:
        raise ValueError("Package name cannot be empty")
    if not package_name.isidentifier():
        raise ValueError("Package name must be a valid Python identifier")
    if keyword.iskeyword(package_name):
        raise ValueError(f"'{package_name}' is a Python keyword and cannot be used")
    if not re.match(r"^[a-z][a-z0-9_]*$", package_name):
        raise ValueError(
            "Package name must start with a lowercase letter and use only lowercase "
            "letters, numbers, and underscores"
        )


def _resolve_project_package(slug: str, explicit_package: str | None) -> str:
    """Resolve package from option or prompt."""
    default_package = slug.replace("-", "_")
    package_name = explicit_package
    if package_name is None:
        package_name = click.prompt(
            "\nPython package name",
            default=default_package,
            show_default=True,
        )

    try:
        _validate_package_name(package_name)
    except ValueError as e:
        click.secho(f"\n❌ Error: {e}", fg="red", err=True)
        raise click.Abort() from e
    return package_name


def _determine_output_path_for_plan(slug: str, output: str | None) -> Path:
    """Determine output path for configuration file."""
    if output:
        return Path(output)
    return Path.cwd() / slug / "quickscale.yml"


def _check_output_path_exists(output_path: Path) -> None:
    """Check if output path exists and confirm overwrite."""
    if not output_path.exists():
        return

    click.secho(
        f"\n⚠️  Configuration file already exists: {output_path}",
        fg="yellow",
    )
    if not click.confirm("Overwrite?", default=False):
        click.echo("❌ Cancelled")
        raise click.Abort()


def _save_config_with_validation(yaml_content: str, output_path: Path) -> None:
    """Validate and save configuration."""
    try:
        validate_config(yaml_content)
    except Exception as e:
        click.secho(f"\n❌ Configuration validation failed: {e}", fg="red", err=True)
        raise click.Abort()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        f.write(yaml_content)


@click.command()
@click.argument("slug", required=False, metavar="PROJECT_SLUG")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output path for quickscale.yml (default: <slug>/quickscale.yml)",
)
@click.option(
    "--package",
    type=str,
    help="Explicit Python package name (default: slug with '-' replaced by '_')",
)
@click.option(
    "--add",
    "add_modules",
    is_flag=True,
    help="Add modules to existing project",
)
@click.option(
    "--reconfigure",
    is_flag=True,
    help="Reconfigure existing project options",
)
@click.option(
    "--include-experimental",
    is_flag=True,
    help="Show and allow experimental modules (billing, teams)",
)
def plan(
    slug: str | None,
    output: str | None,
    package: str | None,
    add_modules: bool,
    reconfigure: bool,
    include_experimental: bool,
) -> None:
    """
    Create or update a project configuration via interactive wizard.

    Creates a quickscale.yml file with your project configuration.
    Run 'quickscale apply' afterwards to generate or update the project.

    \b
    Examples:
      quickscale plan my-app                # Create new project config
      quickscale plan my-app --package my_app
      quickscale plan my-app -o ./config.yml  # Custom output path
      quickscale plan --add                # Add modules to existing project
      quickscale plan --reconfigure        # Reconfigure existing project

    \b
    New project wizard:
      - Theme selection (showcase_html, showcase_htmx, showcase_react)
      - Module selection (auth, blog, listings, etc.)
            - Docker configuration (start, build, create superuser)

    \b
    Existing project modes:
      --add          Add new modules to existing configuration
      --reconfigure  Modify Docker options and add modules
    """
    # Handle --add or --reconfigure flags
    if _handle_existing_project_mode(
        add_modules,
        reconfigure,
        include_experimental=include_experimental,
    ):
        return

    # Validate and prepare for new project
    validated_slug = _validate_new_project_slug(slug)
    resolved_package = _resolve_project_package(validated_slug, package)

    click.echo("\n🚀 QuickScale Project Planner")
    click.echo(f"   Creating configuration for: {validated_slug}")
    click.echo(f"   Package: {resolved_package}")

    output_path = _determine_output_path_for_plan(validated_slug, output)
    _check_output_path_exists(output_path)

    # Interactive wizard
    theme = _select_theme()
    selected_modules = _select_modules(include_experimental=include_experimental)
    docker_start, docker_build, docker_create_superuser = _configure_docker()

    # Build configuration
    modules = {
        module_id: ModuleConfig(name=module_id, options={})
        for module_id in selected_modules
    }

    config = QuickScaleConfig(
        version="1",
        project=ProjectConfig(
            slug=validated_slug,
            package=resolved_package,
            theme=theme,
        ),
        modules=modules,
        docker=DockerConfig(
            start=docker_start,
            build=docker_build,
            create_superuser=docker_create_superuser,
        ),
    )

    # Generate YAML
    yaml_content = generate_yaml(config)

    # Preview configuration
    click.echo("\n" + "=" * 50)
    click.echo("📋 Configuration Preview:")
    click.echo("=" * 50)
    click.echo(yaml_content)
    click.echo("=" * 50)

    # Confirm save
    if not click.confirm("\n💾 Save configuration?", default=True):
        click.echo("❌ Cancelled")
        raise click.Abort()

    # Save with validation
    _save_config_with_validation(yaml_content, output_path)

    click.secho(f"\n✅ Configuration saved to {output_path}", fg="green", bold=True)

    # Next steps
    click.echo("\n📋 Next steps:")
    if output_path.parent.name == validated_slug:
        click.echo(f"  cd {validated_slug}")
        click.echo("  quickscale apply")
    else:
        click.echo(f"  quickscale apply {output_path}")
