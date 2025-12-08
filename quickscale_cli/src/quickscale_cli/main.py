"""QuickScale CLI - Main entry point for project generation commands."""

import click

import quickscale_cli
import quickscale_core
from quickscale_cli.commands.apply_command import apply
from quickscale_cli.commands.deployment_commands import deploy
from quickscale_cli.commands.development_commands import (
    down,
    logs,
    manage,
    ps,
    shell,
    up,
)
from quickscale_cli.commands.module_commands import push, update
from quickscale_cli.commands.plan_command import plan
from quickscale_cli.commands.remove_command import remove
from quickscale_cli.commands.status_command import status


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
cli.add_command(update)
cli.add_command(push)

# Register plan/apply commands
cli.add_command(plan)
cli.add_command(apply)
cli.add_command(status)

# Register remove command
cli.add_command(remove)


if __name__ == "__main__":
    cli()
