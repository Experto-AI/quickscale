"""QuickScale CLI - Main entry point for project generation commands."""

import click

import quickscale_cli
import quickscale_core


@click.group()
@click.version_option(version=quickscale_cli.__version__, prog_name="quickscale")
def cli() -> None:
    """QuickScale - Django SaaS Project Generator."""
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
    click.echo(f"🚀 Generating project: {project_name}")
    click.echo("⚠️  Project generation not yet implemented (v0.52.0 foundation phase)")
    click.echo("📋 Coming in v0.53.0: Template system")
    click.echo("📋 Coming in v0.54.0: Full project generation")


if __name__ == "__main__":
    cli()
