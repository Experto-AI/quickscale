"""Plan command for interactive project configuration

Implements `quickscale plan <name>` - interactive wizard that creates quickscale.yml
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


@click.command()
@click.argument("name", required=True, metavar="PROJECT_NAME")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output path for quickscale.yml (default: <name>/quickscale.yml)",
)
def plan(name: str, output: str | None) -> None:
    """
    Create a project configuration via interactive wizard.

    Creates a quickscale.yml file with your project configuration.
    Run 'quickscale apply' afterwards to generate the project.

    \b
    Examples:
      quickscale plan myapp
      quickscale plan myapp --output ./myapp/quickscale.yml

    \b
    The wizard will guide you through:
      - Theme selection (showcase_html, showcase_htmx, showcase_react)
      - Module selection (auth, blog, listings, etc.)
      - Docker configuration (start, build)
    """
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
