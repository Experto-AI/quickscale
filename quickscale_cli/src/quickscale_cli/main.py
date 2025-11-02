"""QuickScale CLI - Main entry point for project generation commands."""

from pathlib import Path

import click

import quickscale_cli
import quickscale_core
from quickscale_cli.commands.deployment_commands import deploy
from quickscale_cli.commands.development_commands import (
    down,
    logs,
    manage,
    ps,
    shell,
    up,
)
from quickscale_cli.commands.module_commands import embed, push, update
from quickscale_cli.utils.dependency_utils import (
    check_all_dependencies,
)
from quickscale_core.generator import ProjectGenerator


class InitCommand(click.Command):
    """Custom init command with enhanced error messages."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        """Override parse_args to provide better error messages."""
        try:
            return super().parse_args(ctx, args)
        except click.MissingParameter as e:
            if "project_name" in str(e).lower() or "PROJECT_NAME" in str(e):
                click.secho("\n❌ Error: PROJECT_NAME is required", fg="red", err=True)
                click.echo("\n💡 Usage examples:", err=True)
                click.echo("   quickscale init myapp", err=True)
                click.echo("   quickscale init myapp --theme showcase_html", err=True)
                click.echo("\n📖 For more help, run: quickscale init --help", err=True)
                ctx.exit(2)
            raise


@click.group()
@click.version_option(version=quickscale_cli.__version__, prog_name="quickscale")
def cli() -> None:
    """QuickScale - Compose your Django SaaS."""
    pass


@cli.command()
def version() -> None:
    """Show version information for CLI and core packages."""
    click.echo(f"QuickScale CLI v{quickscale_cli.__version__}")
    click.echo(f"QuickScale Core v{quickscale_core.__version__}")


# Register development commands
cli.add_command(up)
cli.add_command(down)
cli.add_command(shell)
cli.add_command(manage)
cli.add_command(logs)
cli.add_command(ps)

# Register deployment commands
cli.add_command(deploy)

# Register module management commands
cli.add_command(embed)
cli.add_command(update)
cli.add_command(push)


@cli.command(cls=InitCommand)
@click.argument("project_name", required=True, metavar="PROJECT_NAME")
@click.option(
    "--theme",
    type=click.Choice(
        ["showcase_html", "showcase_htmx", "showcase_react"], case_sensitive=False
    ),
    default="showcase_html",
    help="Theme to use for the project (default: showcase_html)",
)
def init(project_name: str, theme: str) -> None:
    """
    Generate a new Django project with production-ready configurations.

    Creates a complete Django application with Docker, PostgreSQL, testing,
    CI/CD, and security best practices. The generated project is yours to own
    and customize.

    \b
    Examples:
      quickscale init myapp
      quickscale init myapp --theme showcase_html

    \b
    Available themes:
      showcase_html    Pure HTML + CSS (default, production-ready)
      showcase_htmx    HTMX + Alpine.js (coming in v0.67.0)
      showcase_react   React + TypeScript SPA (coming in v0.68.0)
    """
    # Step 1: Check system dependencies BEFORE generation
    click.echo("🔍 Checking system dependencies...")
    all_deps = check_all_dependencies()

    # Display dependency status
    required_ok = True
    optional_missing = []

    for dep in all_deps:
        if dep.installed:
            version_str = f" (v{dep.version})" if dep.version else ""
            click.secho(f"  ✅ {dep.name}{version_str}", fg="green")
        elif dep.required:
            click.secho(f"  ❌ {dep.name} - REQUIRED", fg="red", err=True)
            click.echo(f"     Purpose: {dep.purpose}", err=True)
            required_ok = False
        else:
            optional_missing.append(dep)

    # Show optional dependencies that are missing
    if optional_missing:
        click.echo("\n⚠️  Optional dependencies not found:")
        for dep in optional_missing:
            click.secho(f"  ⚠️  {dep.name}", fg="yellow")
            click.echo(f"     Purpose: {dep.purpose}")

    # Fail if required dependencies are missing
    if not required_ok:
        click.echo("\n❌ Missing required dependencies. Please install them first:")
        click.echo("\n📦 Installation instructions:")
        click.echo("   Python 3.11+: https://www.python.org/downloads/")
        click.echo("   Poetry: curl -sSL https://install.python-poetry.org | python3 -")
        raise click.Abort()

    click.echo("")

    try:
        # Validate theme availability
        if theme in ["showcase_htmx", "showcase_react"]:
            click.secho(
                f"❌ Error: Theme '{theme}' is not yet implemented", fg="red", err=True
            )
            click.echo(
                f"\n💡 The '{theme}' theme is planned for a future release:", err=True
            )
            click.echo("   - showcase_htmx: Coming in v0.67.0", err=True)
            click.echo("   - showcase_react: Coming in v0.68.0", err=True)
            click.echo("\n📖 For now, use the default 'showcase_html' theme", err=True)
            raise click.Abort()

        # Initialize generator with theme
        generator = ProjectGenerator(theme=theme)

        # Generate project in current directory
        output_path = Path.cwd() / project_name

        click.echo(f"🚀 Generating project: {project_name}")
        click.echo(f"🎨 Using theme: {theme}")
        generator.generate(project_name, output_path)

        # Success message
        click.secho(
            f"\n✅ Created project: {project_name} (theme: {theme})",
            fg="green",
            bold=True,
        )

        # Next steps instructions (manual setup)
        click.echo("\n📋 Next steps:")
        click.echo(f"  cd {project_name}")
        click.echo(" ")
        click.echo("  # Optional: Embed modules, example: auth")
        click.echo(
            "  # NOTE: requires git and must be done BEFORE poetry install + migrate"
        )
        click.echo("  git init")
        click.echo("  git add -A")
        click.echo(f"  git commit -m 'Initial {project_name} commit'")
        click.echo("  quickscale embed --module auth")
        click.echo(" ")
        click.echo("  # Install dependencies and run migrations")
        click.echo("  poetry install")
        click.echo("  poetry run python manage.py migrate")
        click.echo(" ")
        click.echo("  # Optional: Start development server with Docker and PostgreSQL:")
        click.echo("  quickscale up")
        click.echo(
            "  # Optional (alternative): Start development server without Docker (using SQLite):"
        )
        click.echo("  poetry run python manage.py runserver")
        click.echo(" ")
        click.echo("\n📖 See README.md for more details")

    except click.Abort:
        # Re-raise click.Abort without catching it as a generic exception
        raise
    except ValueError as e:
        # Invalid project name
        click.secho(f"❌ Error: {e}", fg="red", err=True)
        click.echo("\n💡 Tip: Project name must be a valid Python identifier", err=True)
        click.echo("   - Use only letters, numbers, and underscores", err=True)
        click.echo("   - Cannot start with a number", err=True)
        click.echo("   - Cannot use Python reserved keywords", err=True)
        raise click.Abort()
    except FileExistsError as e:
        # Directory already exists
        click.secho(f"❌ Error: {e}", fg="red", err=True)
        click.echo(
            "\n💡 Tip: Choose a different project name or remove the existing directory",
            err=True,
        )
        raise click.Abort()
    except PermissionError as e:
        # Permission issues
        click.secho(f"❌ Error: {e}", fg="red", err=True)
        click.echo(
            "\n💡 Tip: Check directory permissions or try a different location",
            err=True,
        )
        raise click.Abort()
    except Exception as e:
        # Unexpected errors
        click.secho(f"❌ Unexpected error: {e}", fg="red", err=True)
        click.echo("\n🐛 This is a bug. Please report it at:", err=True)
        click.echo("   https://github.com/Experto-AI/quickscale/issues", err=True)
        raise


if __name__ == "__main__":
    cli()
