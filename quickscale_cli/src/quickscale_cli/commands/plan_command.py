"""Plan command for interactive project configuration

Implements `quickscale plan <name>` - interactive wizard that creates quickscale.yml
Also supports `--add` and `--reconfigure` flags for existing projects.
"""

from pathlib import Path

import click

from quickscale_cli.schema.config_schema import (
    DockerConfig,
    ModuleConfig,
    ProjectConfig,
    QuickScaleConfig,
    generate_yaml,
    validate_config,
)
from quickscale_cli.schema.state_schema import StateManager

# Available themes for selection
AVAILABLE_THEMES = [
    ("showcase_html", "Pure HTML + CSS (default, production-ready)"),
    ("showcase_htmx", "HTMX + Alpine.js (coming in v0.70.0)"),
    ("showcase_react", "React + TypeScript SPA (coming in v0.71.0)"),
]

# Available modules for selection
AVAILABLE_MODULES = [
    ("auth", "Authentication with django-allauth"),
    ("blog", "Markdown-powered blog with categories and RSS"),
    ("listings", "Generic listings for marketplace verticals"),
    ("billing", "Stripe integration (placeholder)"),
    ("teams", "Multi-tenancy and team management (placeholder)"),
]


def _select_theme() -> str:
    """Interactive theme selection"""
    click.echo("\n🎨 Select a theme for your project:")
    for i, (theme_id, description) in enumerate(AVAILABLE_THEMES, start=1):
        status = " ⚠️  not yet implemented" if theme_id != "showcase_html" else ""
        click.echo(f"  {i}. {theme_id} - {description}{status}")

    while True:
        choice = click.prompt(
            "\nEnter theme number or name",
            default="1",
            show_default=True,
        )

        # Handle numeric choice
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(AVAILABLE_THEMES):
                theme_id = AVAILABLE_THEMES[idx][0]
                # Warn about unimplemented themes
                if theme_id != "showcase_html":
                    click.secho(
                        f"\n⚠️  Theme '{theme_id}' is not yet implemented. "
                        "It will be available in a future release.",
                        fg="yellow",
                    )
                    if not click.confirm("Use this theme anyway?", default=False):
                        continue
                return theme_id
        else:
            # Handle theme name
            for theme_id, _ in AVAILABLE_THEMES:
                if choice.lower() == theme_id.lower():
                    if theme_id != "showcase_html":
                        click.secho(
                            f"\n⚠️  Theme '{theme_id}' is not yet implemented. "
                            "It will be available in a future release.",
                            fg="yellow",
                        )
                        if not click.confirm("Use this theme anyway?", default=False):
                            break
                    return theme_id

        click.secho("Invalid choice. Please try again.", fg="red")


def _select_modules() -> list[str]:
    """Interactive module selection"""
    click.echo("\n📦 Select modules to embed (optional):")
    for i, (module_id, description) in enumerate(AVAILABLE_MODULES, start=1):
        placeholder = " (placeholder)" if module_id in ("billing", "teams") else ""
        click.echo(f"  {i}. {module_id} - {description}{placeholder}")

    click.echo(
        "\n  Enter numbers separated by commas (e.g., 1,3), or press Enter to skip"
    )

    while True:
        choice = click.prompt(
            "Select modules",
            default="",
            show_default=False,
        )

        if not choice.strip():
            return []

        selected = []
        try:
            parts = [p.strip() for p in choice.split(",")]
            for part in parts:
                if part.isdigit():
                    idx = int(part) - 1
                    if 0 <= idx < len(AVAILABLE_MODULES):
                        module_id = AVAILABLE_MODULES[idx][0]
                        if module_id not in selected:
                            selected.append(module_id)
                    else:
                        raise ValueError(f"Invalid number: {part}")
                else:
                    # Handle module name
                    found = False
                    for module_id, _ in AVAILABLE_MODULES:
                        if part.lower() == module_id.lower():
                            if module_id not in selected:
                                selected.append(module_id)
                            found = True
                            break
                    if not found:
                        raise ValueError(f"Unknown module: {part}")
            return selected
        except ValueError as e:
            click.secho(f"Invalid selection: {e}. Please try again.", fg="red")


def _configure_docker() -> tuple[bool, bool]:
    """Interactive Docker configuration"""
    click.echo("\n🐳 Docker Configuration:")
    start = click.confirm("  Start Docker services after apply?", default=True)
    build = click.confirm("  Build Docker images?", default=True) if start else False
    return start, build


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


def _select_modules_to_add(existing_modules: list[str]) -> list[str]:
    """Interactive module selection for adding to existing project

    Shows which modules are already installed and lets user select new ones.

    Args:
        existing_modules: List of module names already applied

    Returns:
        List of newly selected module names

    """
    click.echo("\n📦 Current Modules:")
    if existing_modules:
        for module in existing_modules:
            click.secho(f"   ✓ {module} (installed)", fg="green")
    else:
        click.echo("   (none installed)")

    click.echo("\n📦 Available Modules to Add:")
    available = []
    for i, (module_id, description) in enumerate(AVAILABLE_MODULES, start=1):
        if module_id in existing_modules:
            continue
        available.append((module_id, description))
        placeholder = " (placeholder)" if module_id in ("billing", "teams") else ""
        click.echo(f"  {len(available)}. {module_id} - {description}{placeholder}")

    if not available:
        click.echo("   All modules are already installed!")
        return []

    click.echo(
        "\n  Enter numbers separated by commas (e.g., 1,3), or press Enter to skip"
    )

    while True:
        choice = click.prompt(
            "Select modules to add",
            default="",
            show_default=False,
        )

        if not choice.strip():
            return []

        selected = []
        try:
            parts = [p.strip() for p in choice.split(",")]
            for part in parts:
                if part.isdigit():
                    idx = int(part) - 1
                    if 0 <= idx < len(available):
                        module_id = available[idx][0]
                        if module_id not in selected:
                            selected.append(module_id)
                    else:
                        raise ValueError(f"Invalid number: {part}")
                else:
                    # Handle module name
                    found = False
                    for module_id, _ in available:
                        if part.lower() == module_id.lower():
                            if module_id not in selected:
                                selected.append(module_id)
                            found = True
                            break
                    if not found:
                        raise ValueError(f"Unknown or already installed module: {part}")
            return selected
        except ValueError as e:
            click.secho(f"Invalid selection: {e}. Please try again.", fg="red")


def _handle_add_modules(
    project_path: Path, existing_config: QuickScaleConfig | None
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
    new_modules = _select_modules_to_add(all_existing)

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
            project=ProjectConfig(name=state.project.name, theme=state.project.theme),
            modules={
                name: ModuleConfig(name=name, options={})
                for name in state.modules.keys()
            },
            docker=DockerConfig(start=False, build=False),
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


def _handle_reconfigure(
    project_path: Path, existing_config: QuickScaleConfig | None
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
    if state:
        project_name = state.project.name
        current_theme = state.project.theme
    elif existing_config:
        project_name = existing_config.project.name
        current_theme = existing_config.project.theme
    else:
        project_name = project_path.name
        current_theme = "showcase_html"

    click.echo(f"\n📁 Project: {project_name}")
    click.secho(f"   Theme: {current_theme} (locked after creation)", fg="cyan")

    # Get applied modules
    applied_modules = _get_applied_modules(project_path)
    config_modules = list(existing_config.modules.keys()) if existing_config else []
    all_existing = list(set(applied_modules + config_modules))

    # Select modules (can add new ones or keep existing)
    click.echo("\n📦 Module Configuration:")
    if all_existing:
        click.echo("   Currently configured modules:")
        for module in all_existing:
            status = "(applied)" if module in applied_modules else "(pending)"
            click.secho(f"   ✓ {module} {status}", fg="green")

    # Ask if user wants to add more modules
    if click.confirm("\n   Add more modules?", default=False):
        new_modules = _select_modules_to_add(all_existing)
        all_modules = all_existing + new_modules
    else:
        all_modules = all_existing

    # Configure Docker
    docker_start, docker_build = _configure_docker()

    # Build configuration
    modules = {
        module_id: ModuleConfig(name=module_id, options={}) for module_id in all_modules
    }

    config = QuickScaleConfig(
        version="1",
        project=ProjectConfig(name=project_name, theme=current_theme),
        modules=modules,
        docker=DockerConfig(start=docker_start, build=docker_build),
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


@click.command()
@click.argument("name", required=False, metavar="PROJECT_NAME")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output path for quickscale.yml (default: <name>/quickscale.yml)",
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
def plan(
    name: str | None, output: str | None, add_modules: bool, reconfigure: bool
) -> None:
    """
    Create or update a project configuration via interactive wizard.

    Creates a quickscale.yml file with your project configuration.
    Run 'quickscale apply' afterwards to generate or update the project.

    \b
    Examples:
      quickscale plan myapp                # Create new project config
      quickscale plan myapp -o ./config.yml  # Custom output path
      quickscale plan --add                # Add modules to existing project
      quickscale plan --reconfigure        # Reconfigure existing project

    \b
    New project wizard:
      - Theme selection (showcase_html, showcase_htmx, showcase_react)
      - Module selection (auth, blog, listings, etc.)
      - Docker configuration (start, build)

    \b
    Existing project modes:
      --add          Add new modules to existing configuration
      --reconfigure  Modify Docker options and add modules
    """
    # Handle --add flag for existing project
    if add_modules:
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
        _handle_add_modules(project_path, existing_config)
        return

    # Handle --reconfigure flag for existing project
    if reconfigure:
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
        _handle_reconfigure(project_path, existing_config)
        return

    # For new project, name is required
    if not name:
        click.secho(
            "\n❌ Error: PROJECT_NAME is required for new projects",
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
    click.echo("\n🚀 QuickScale Project Planner")
    click.echo(f"   Creating configuration for: {name}")

    # Validate project name
    if not name.isidentifier():
        click.secho(
            f"\n❌ Error: '{name}' is not a valid project name",
            fg="red",
            err=True,
        )
        click.echo(
            "   Project name must be a valid Python identifier "
            "(letters, numbers, underscores, not starting with a number)",
            err=True,
        )
        raise click.Abort()

    # Determine output path
    if output:
        output_path = Path(output)
    else:
        output_path = Path.cwd() / name / "quickscale.yml"

    # Check if output path exists
    if output_path.exists():
        click.secho(
            f"\n⚠️  Configuration file already exists: {output_path}",
            fg="yellow",
        )
        if not click.confirm("Overwrite?", default=False):
            click.echo("❌ Cancelled")
            raise click.Abort()

    # Interactive wizard
    theme = _select_theme()
    selected_modules = _select_modules()
    docker_start, docker_build = _configure_docker()

    # Build configuration
    modules = {
        module_id: ModuleConfig(name=module_id, options={})
        for module_id in selected_modules
    }

    config = QuickScaleConfig(
        version="1",
        project=ProjectConfig(name=name, theme=theme),
        modules=modules,
        docker=DockerConfig(start=docker_start, build=docker_build),
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

    # Validate before saving (sanity check)
    try:
        validate_config(yaml_content)
    except Exception as e:
        click.secho(f"\n❌ Configuration validation failed: {e}", fg="red", err=True)
        raise click.Abort()

    # Create output directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save configuration
    with open(output_path, "w") as f:
        f.write(yaml_content)

    click.secho(f"\n✅ Configuration saved to {output_path}", fg="green", bold=True)

    # Next steps
    click.echo("\n📋 Next steps:")
    if output_path.parent.name == name:
        click.echo(f"  cd {name}")
        click.echo("  quickscale apply")
    else:
        click.echo(f"  quickscale apply {output_path}")
