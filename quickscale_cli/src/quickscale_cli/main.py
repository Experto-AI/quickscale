"""
QuickScale CLI - Main Entry Point

Ultra-simple CLI for QuickScale Django project generator.
MVP focuses on single command: `quickscale init <project>`
"""

import click

import quickscale_cli
import quickscale_core


@click.group()
@click.version_option(version=quickscale_cli.__version__, prog_name="quickscale")
def cli():
    """
    QuickScale - Django SaaS Project Generator

    Generate production-ready Django projects in seconds.

    MVP Command:
      quickscale init <project>  Generate a new Django project

    For more information, visit: https://github.com/Experto-AI/quickscale
    """
    pass


@cli.command()
def version():
    """Show version information."""
    click.echo(f"QuickScale CLI v{quickscale_cli.__version__}")
    click.echo(f"QuickScale Core v{quickscale_core.__version__}")


@cli.command()
@click.argument("project_name")
def init(project_name):
    """
    Generate a new Django project.

    PROJECT_NAME: Name of the project to create

    Example:
      quickscale init myapp

    This will create a new Django project with production-ready configurations.
    """
    click.echo(f"🚀 Generating project: {project_name}")
    click.echo("⚠️  Project generation not yet implemented (v0.52.0 foundation phase)")
    click.echo("📋 Coming in v0.53.0: Template system")
    click.echo("📋 Coming in v0.54.0: Full project generation")


if __name__ == "__main__":
    cli()
