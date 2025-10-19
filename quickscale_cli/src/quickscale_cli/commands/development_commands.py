"""Development lifecycle commands for QuickScale projects."""

import subprocess
import sys

import click

from quickscale_cli.utils.docker_utils import (
    get_docker_compose_command,
    is_docker_running,
    is_interactive,
)
from quickscale_cli.utils.project_manager import get_web_container_name, is_in_quickscale_project


@click.command()
@click.option("--build", is_flag=True, help="Rebuild containers before starting")
@click.option("--no-cache", is_flag=True, help="Build without using cache")
def up(build: bool, no_cache: bool) -> None:
    """Start Docker services for development."""
    # Check if in QuickScale project
    if not is_in_quickscale_project():
        click.secho("❌ Error: Not in a QuickScale project directory", fg="red", err=True)
        click.echo(
            "💡 Tip: Navigate to a project directory or run 'quickscale init <name>' to create one",
            err=True,
        )
        sys.exit(1)

    # Check if Docker is running
    if not is_docker_running():
        click.secho("❌ Error: Docker is not running", fg="red", err=True)
        click.echo("💡 Tip: Start Docker Desktop or the Docker daemon", err=True)
        sys.exit(1)

    try:
        compose_cmd = get_docker_compose_command()
        cmd = compose_cmd + ["up", "-d"]

        if build or no_cache:
            cmd.append("--build")

        if no_cache:
            cmd.append("--no-cache")

        click.echo("🚀 Starting Docker services...")
        subprocess.run(cmd, check=True)
        click.secho("✅ Services started successfully!", fg="green", bold=True)
        click.echo("💡 Tip: Use 'quickscale logs' to view service logs")

    except subprocess.CalledProcessError as e:
        click.secho(
            f"❌ Error: Failed to start services (exit code: {e.returncode})", fg="red", err=True
        )
        click.echo("💡 Tip: Check Docker logs with 'quickscale logs' for details", err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\n⚠️  Interrupted by user")
        sys.exit(130)


@click.command()
@click.option("--volumes", is_flag=True, help="Remove volumes as well")
def down(volumes: bool) -> None:
    """Stop Docker services."""
    if not is_in_quickscale_project():
        click.secho("❌ Error: Not in a QuickScale project directory", fg="red", err=True)
        click.echo("💡 Tip: Navigate to a project directory", err=True)
        sys.exit(1)

    if not is_docker_running():
        click.secho("❌ Error: Docker is not running", fg="red", err=True)
        click.echo("💡 Tip: Start Docker Desktop or the Docker daemon", err=True)
        sys.exit(1)

    try:
        compose_cmd = get_docker_compose_command()
        cmd = compose_cmd + ["down"]

        if volumes:
            cmd.append("--volumes")

        click.echo("🛑 Stopping Docker services...")
        subprocess.run(cmd, check=True)
        click.secho("✅ Services stopped successfully!", fg="green")

    except subprocess.CalledProcessError as e:
        click.secho(
            f"❌ Error: Failed to stop services (exit code: {e.returncode})", fg="red", err=True
        )
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\n⚠️  Interrupted by user")
        sys.exit(130)


@click.command()
@click.option("-c", "--command", "cmd", help="Run a single command instead of interactive shell")
def shell(cmd: str | None) -> None:
    """Open an interactive bash shell in the web container."""
    if not is_in_quickscale_project():
        click.secho("❌ Error: Not in a QuickScale project directory", fg="red", err=True)
        click.echo("💡 Tip: Navigate to a project directory", err=True)
        sys.exit(1)

    if not is_docker_running():
        click.secho("❌ Error: Docker is not running", fg="red", err=True)
        click.echo("�� Tip: Start Docker Desktop or the Docker daemon", err=True)
        sys.exit(1)

    try:
        container_name = get_web_container_name()

        if cmd:
            # Run single command (non-interactive)
            docker_cmd = ["docker", "exec", container_name, "bash", "-c", cmd]
            if is_interactive():
                subprocess.run(docker_cmd, check=True)
            else:
                result = subprocess.run(docker_cmd, capture_output=True, text=True, check=True)
                if result.stdout:
                    click.echo(result.stdout, nl=False)
                if result.stderr:
                    click.echo(result.stderr, nl=False, err=True)
        else:
            # Interactive shell - only use -it if we have a TTY
            docker_cmd = ["docker", "exec"]
            if is_interactive():
                docker_cmd.append("-it")
            docker_cmd.extend([container_name, "bash"])
            subprocess.run(docker_cmd, check=True)

    except subprocess.CalledProcessError as e:
        if e.returncode == 1:
            click.secho("❌ Error: Container not running", fg="red", err=True)
            click.echo("💡 Tip: Start services with 'quickscale up' first", err=True)
        else:
            click.secho(f"❌ Error: Command failed (exit code: {e.returncode})", fg="red", err=True)
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        click.echo("\n⚠️  Exited shell")
        sys.exit(0)


@click.command(context_settings=dict(ignore_unknown_options=True))
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def manage(args: tuple) -> None:
    """Run Django management commands in the web container."""
    if not is_in_quickscale_project():
        click.secho("❌ Error: Not in a QuickScale project directory", fg="red", err=True)
        click.echo("💡 Tip: Navigate to a project directory", err=True)
        sys.exit(1)

    if not is_docker_running():
        click.secho("❌ Error: Docker is not running", fg="red", err=True)
        click.echo("💡 Tip: Start Docker Desktop or the Docker daemon", err=True)
        sys.exit(1)

    if not args:
        click.secho("❌ Error: No Django management command specified", fg="red", err=True)
        click.echo("💡 Tip: Run 'quickscale manage help' to see available commands", err=True)
        sys.exit(1)

    try:
        container_name = get_web_container_name()
        docker_cmd = ["docker", "exec"]

        # Only use -it flags if we have an interactive terminal (TTY)
        if is_interactive():
            docker_cmd.append("-it")

        docker_cmd.extend([container_name, "python", "manage.py"] + list(args))

        # In interactive mode, let subprocess inherit stdio
        # In non-interactive mode (tests), capture and echo output for Click
        if is_interactive():
            subprocess.run(docker_cmd, check=True)
        else:
            result = subprocess.run(docker_cmd, capture_output=True, text=True, check=True)
            if result.stdout:
                click.echo(result.stdout, nl=False)
            if result.stderr:
                click.echo(result.stderr, nl=False, err=True)

    except subprocess.CalledProcessError as e:
        if e.returncode == 1:
            click.secho("❌ Error: Container not running or command failed", fg="red", err=True)
            click.echo("💡 Tip: Start services with 'quickscale up' first", err=True)
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        click.echo("\n⚠️  Interrupted by user")
        sys.exit(130)


@click.command()
@click.argument("service", required=False)
@click.option("-f", "--follow", is_flag=True, help="Follow log output")
@click.option("--tail", default=None, help="Number of lines to show from the end of the logs")
@click.option("--timestamps", is_flag=True, help="Show timestamps")
def logs(service: str | None, follow: bool, tail: str | None, timestamps: bool) -> None:
    """View Docker service logs."""
    if not is_in_quickscale_project():
        click.secho("❌ Error: Not in a QuickScale project directory", fg="red", err=True)
        click.echo("💡 Tip: Navigate to a project directory", err=True)
        sys.exit(1)

    if not is_docker_running():
        click.secho("❌ Error: Docker is not running", fg="red", err=True)
        click.echo("�� Tip: Start Docker Desktop or the Docker daemon", err=True)
        sys.exit(1)

    try:
        compose_cmd = get_docker_compose_command()
        cmd = compose_cmd + ["logs"]

        if follow:
            cmd.append("--follow")

        if tail:
            cmd.extend(["--tail", tail])

        if timestamps:
            cmd.append("--timestamps")

        if service:
            cmd.append(service)

        subprocess.run(cmd, check=True)

    except subprocess.CalledProcessError as e:
        click.secho(
            f"❌ Error: Failed to retrieve logs (exit code: {e.returncode})", fg="red", err=True
        )
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\n⚠️  Stopped following logs")
        sys.exit(0)


@click.command()
def ps() -> None:
    """Show service status."""
    if not is_in_quickscale_project():
        click.secho("❌ Error: Not in a QuickScale project directory", fg="red", err=True)
        click.echo("💡 Tip: Navigate to a project directory", err=True)
        sys.exit(1)

    if not is_docker_running():
        click.secho("❌ Error: Docker is not running", fg="red", err=True)
        click.echo("💡 Tip: Start Docker Desktop or the Docker daemon", err=True)
        sys.exit(1)

    try:
        compose_cmd = get_docker_compose_command()
        cmd = compose_cmd + ["ps"]
        subprocess.run(cmd, check=True)

    except subprocess.CalledProcessError as e:
        click.secho(
            f"❌ Error: Failed to get service status (exit code: {e.returncode})",
            fg="red",
            err=True,
        )
        sys.exit(1)
