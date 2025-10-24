"""QuickScale CLI - Main entry point for project generation commands."""

from pathlib import Path

import click

import quickscale_cli
import quickscale_core
from quickscale_cli.commands.deployment_commands import deploy
from quickscale_cli.commands.development_commands import down, logs, manage, ps, shell, up
from quickscale_core.generator import ProjectGenerator


class InitCommand(click.Command):
    """Custom init command with enhanced error messages."""

    def parse_args(self, ctx, args):
        """Override parse_args to provide better error messages."""
        try:
            return super().parse_args(ctx, args)
        except click.MissingParameter as e:
            if "project_name" in str(e).lower() or "PROJECT_NAME" in str(e):
                click.secho("\n❌ Error: PROJECT_NAME is required", fg="red", err=True)
                click.echo("\n💡 Usage examples:", err=True)
                click.echo("   quickscale init myapp", err=True)
                click.echo("   quickscale init myapp --theme starter_html", err=True)
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


@cli.command(cls=InitCommand)
@click.argument("project_name", required=True, metavar="PROJECT_NAME")
@click.option(
    "--theme",
    type=click.Choice(["starter_html", "starter_htmx", "starter_react"], case_sensitive=False),
    default="starter_html",
    help="Theme to use for the project (default: starter_html)",
)
def init(project_name: str, theme: str) -> None:
    """
    Generate a new Django project with production-ready configurations.

    \b
    Examples:
      quickscale init myapp                       # Create project with default HTML theme
      quickscale init myapp --theme starter_html  # Explicitly specify HTML theme

    \b
    Choose from available themes:
      - starter_html: Pure HTML + CSS (default, production-ready)
      - starter_htmx: HTMX + Alpine.js (coming in v0.67.0)
      - starter_react: React + TypeScript SPA (coming in v0.68.0)
    """
    try:
        # Validate theme availability
        if theme in ["starter_htmx", "starter_react"]:
            click.secho(f"❌ Error: Theme '{theme}' is not yet implemented", fg="red", err=True)
            click.echo(f"\n💡 The '{theme}' theme is planned for a future release:", err=True)
            click.echo("   - starter_htmx: Coming in v0.67.0", err=True)
            click.echo("   - starter_react: Coming in v0.68.0", err=True)
            click.echo("\n📖 For now, use the default 'starter_html' theme", err=True)
            raise click.Abort()

        # Initialize generator with theme
        generator = ProjectGenerator(theme=theme)

        # Generate project in current directory
        output_path = Path.cwd() / project_name

        click.echo(f"🚀 Generating project: {project_name}")
        click.echo(f"🎨 Using theme: {theme}")
        generator.generate(project_name, output_path)

        # Success message
        click.secho(f"\n✅ Created project: {project_name} (theme: {theme})", fg="green", bold=True)

        # Next steps instructions
        click.echo("\n📋 Next steps:")
        click.echo(f"  cd {project_name}")
        click.echo("  # Recommended: use Poetry for dependency management")
        click.echo("  poetry install")
        click.echo("  poetry run python manage.py migrate")
        click.echo("  poetry run python manage.py runserver")
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
