"""QuickScale CLI - Main entry point for project generation commands."""

from pathlib import Path

import click

import quickscale_cli
import quickscale_core
from quickscale_core.generator import ProjectGenerator


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


@cli.command()
@click.argument("project_name")
def init(project_name: str) -> None:
    """Generate a new Django project with production-ready configurations."""
    try:
        # Initialize generator
        generator = ProjectGenerator()

        # Generate project in current directory
        output_path = Path.cwd() / project_name

        click.echo(f"🚀 Generating project: {project_name}")
        generator.generate(project_name, output_path)

        # Success message
        click.secho(f"\n✅ Created project: {project_name}", fg="green", bold=True)

        # Next steps instructions
        click.echo("\n📋 Next steps:")
        click.echo(f"  cd {project_name}")
        click.echo("  # Recommended: use Poetry for dependency management")
        click.echo("  poetry install")
        click.echo("  poetry run python manage.py migrate")
        click.echo("  poetry run python manage.py runserver")
        click.echo("\n📖 See README.md for more details")

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
            "\n💡 Tip: Choose a different project name or remove the existing directory", err=True
        )
        raise click.Abort()
    except PermissionError as e:
        # Permission issues
        click.secho(f"❌ Error: {e}", fg="red", err=True)
        click.echo("\n💡 Tip: Check directory permissions or try a different location", err=True)
        raise click.Abort()
    except Exception as e:
        # Unexpected errors
        click.secho(f"❌ Unexpected error: {e}", fg="red", err=True)
        click.echo("\n🐛 This is a bug. Please report it at:", err=True)
        click.echo("   https://github.com/Experto-AI/quickscale/issues", err=True)
        raise


if __name__ == "__main__":
    cli()
