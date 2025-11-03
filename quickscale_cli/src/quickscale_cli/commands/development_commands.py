"""Development lifecycle commands for QuickScale projects."""

import re
import subprocess
import sys

import click

from quickscale_cli.utils.docker_utils import (
    get_docker_compose_command,
    get_port_from_env,
    is_docker_running,
    is_interactive,
    is_port_available,
    wait_for_port_release,
)
from quickscale_cli.utils.project_manager import (
    get_web_container_name,
    is_in_quickscale_project,
)


@click.command()
@click.option("--build", is_flag=True, help="Rebuild containers before starting")
@click.option("--no-cache", is_flag=True, help="Build without using cache")
def up(build: bool, no_cache: bool) -> None:
    """Start Docker services for development."""
    # Check if in QuickScale project
    if not is_in_quickscale_project():
        click.secho(
            "❌ Error: Not in a QuickScale project directory", fg="red", err=True
        )
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

    # Check if required port is available BEFORE calling docker-compose
    port = get_port_from_env()
    if not is_port_available(port):
        click.secho(f"❌ Error: Port {port} is already in use", fg="red", err=True)
        click.echo(
            f"\n💡 To resolve this issue, try one of the following:\n"
            f"   1. If you just ran 'quickscale down': Wait 5-10 seconds for docker-proxy to release the port\n"
            f"   2. Stop and cleanup: quickscale down && sleep 5 && quickscale up\n"
            f"   3. Check for other containers: docker ps -a | grep {port}\n"
            f"   4. Find and kill the process using the port:\n"
            f"      • Check what's using it: sudo netstat -tulpn | grep :{port}\n"
            f"      • If it's docker-proxy: wait a few seconds and try again\n"
            f"      • If it's another process: sudo lsof -ti:{port} | xargs kill -9\n"
            f"   5. Change the port in .env file: PORT=8001",
            err=True,
        )
        sys.exit(1)

    try:
        compose_cmd = get_docker_compose_command()
        cmd = compose_cmd + ["up", "-d"]

        if build or no_cache:
            cmd.append("--build")

        if no_cache:
            cmd.append("--no-cache")

        click.echo("🚀 Starting Docker services...")
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        click.secho("✅ Services started successfully!", fg="green", bold=True)
        click.echo("💡 Tip: Use 'quickscale logs' to view service logs")

    except subprocess.CalledProcessError as e:
        # Check for port conflict in error output
        # Docker error format: "Bind for 0.0.0.0:8000 failed: port is already allocated"
        # Check both stdout and stderr since docker-compose may output to either
        error_output = e.stderr if e.stderr else ""
        stdout_output = e.stdout if e.stdout else ""
        full_output = error_output + stdout_output

        port_conflict_match = re.search(
            r"Bind for [\d.]+:(\d+) failed: port is already allocated",
            full_output,
            re.IGNORECASE,
        )

        if port_conflict_match:
            conflict_port = port_conflict_match.group(1)
            click.secho(
                f"❌ Error: Port {conflict_port} is already in use",
                fg="red",
                err=True,
            )
            click.echo(
                f"\n💡 To resolve this issue, try one of the following:\n"
                f"   1. Stop existing containers: quickscale down\n"
                f"   2. Remove orphaned containers: docker-compose down --remove-orphans\n"
                f"   3. Find and kill the process: lsof -ti:{conflict_port} | xargs kill -9\n"
                f"   4. Find process details: sudo lsof -i:{conflict_port}\n"
                f"   5. Or use: sudo fuser -k {conflict_port}/tcp",
                err=True,
            )
        else:
            click.secho(
                f"❌ Error: Failed to start services (exit code: {e.returncode})",
                fg="red",
                err=True,
            )
            if full_output:
                click.echo(f"\nError output:\n{full_output}", err=True)
            click.echo(
                "💡 Tip: Check Docker logs with 'quickscale logs' for details",
                err=True,
            )
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\n⚠️  Interrupted by user")
        sys.exit(130)


@click.command()
@click.option("--volumes", is_flag=True, help="Remove volumes as well")
def down(volumes: bool) -> None:
    """Stop Docker services."""
    if not is_in_quickscale_project():
        click.secho(
            "❌ Error: Not in a QuickScale project directory", fg="red", err=True
        )
        click.echo("💡 Tip: Navigate to a project directory", err=True)
        sys.exit(1)

    if not is_docker_running():
        click.secho("❌ Error: Docker is not running", fg="red", err=True)
        click.echo("💡 Tip: Start Docker Desktop or the Docker daemon", err=True)
        sys.exit(1)

    try:
        compose_cmd = get_docker_compose_command()
        cmd = compose_cmd + ["down", "--remove-orphans"]

        if volumes:
            cmd.append("--volumes")

        click.echo("🛑 Stopping Docker services...")
        subprocess.run(cmd, check=True)

        # Wait for Docker's proxy process to fully release ports
        # docker-proxy can take a few seconds to release ports after containers stop
        port = get_port_from_env()
        click.echo(f"⏳ Waiting for port {port} to be released...")
        if not wait_for_port_release(port, timeout=5.0):
            click.echo(
                f"⚠️  Warning: Port {port} still in use after 5 seconds. "
                f"Wait a moment before running 'quickscale up'.",
                err=True,
            )
        else:
            click.echo(f"✅ Port {port} released")

        click.secho("✅ Services stopped successfully!", fg="green")

    except subprocess.CalledProcessError as e:
        click.secho(
            f"❌ Error: Failed to stop services (exit code: {e.returncode})",
            fg="red",
            err=True,
        )
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\n⚠️  Interrupted by user")
        sys.exit(130)


@click.command()
@click.option(
    "-c", "--command", "cmd", help="Run a single command instead of interactive shell"
)
def shell(cmd: str | None) -> None:
    """Open an interactive bash shell in the web container."""
    if not is_in_quickscale_project():
        click.secho(
            "❌ Error: Not in a QuickScale project directory", fg="red", err=True
        )
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
                result = subprocess.run(
                    docker_cmd, capture_output=True, text=True, check=True
                )
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
            click.secho(
                f"❌ Error: Command failed (exit code: {e.returncode})",
                fg="red",
                err=True,
            )
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        click.echo("\n⚠️  Exited shell")
        sys.exit(0)


@click.command(context_settings=dict(ignore_unknown_options=True))
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def manage(args: tuple) -> None:
    """Run Django management commands in the web container."""
    if not is_in_quickscale_project():
        click.secho(
            "❌ Error: Not in a QuickScale project directory", fg="red", err=True
        )
        click.echo("💡 Tip: Navigate to a project directory", err=True)
        sys.exit(1)

    if not is_docker_running():
        click.secho("❌ Error: Docker is not running", fg="red", err=True)
        click.echo("💡 Tip: Start Docker Desktop or the Docker daemon", err=True)
        sys.exit(1)

    if not args:
        click.secho(
            "❌ Error: No Django management command specified", fg="red", err=True
        )
        click.echo(
            "💡 Tip: Run 'quickscale manage help' to see available commands", err=True
        )
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
            result = subprocess.run(
                docker_cmd, capture_output=True, text=True, check=True
            )
            if result.stdout:
                click.echo(result.stdout, nl=False)
            if result.stderr:
                click.echo(result.stderr, nl=False, err=True)

    except subprocess.CalledProcessError as e:
        if e.returncode == 1:
            click.secho(
                "❌ Error: Container not running or command failed", fg="red", err=True
            )
            click.echo("💡 Tip: Start services with 'quickscale up' first", err=True)
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        click.echo("\n⚠️  Interrupted by user")
        sys.exit(130)


@click.command()
@click.argument("service", required=False)
@click.option("-f", "--follow", is_flag=True, help="Follow log output")
@click.option(
    "--tail", default=None, help="Number of lines to show from the end of the logs"
)
@click.option("--timestamps", is_flag=True, help="Show timestamps")
def logs(service: str | None, follow: bool, tail: str | None, timestamps: bool) -> None:
    """View Docker service logs."""
    if not is_in_quickscale_project():
        click.secho(
            "❌ Error: Not in a QuickScale project directory", fg="red", err=True
        )
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
            f"❌ Error: Failed to retrieve logs (exit code: {e.returncode})",
            fg="red",
            err=True,
        )
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\n⚠️  Stopped following logs")
        sys.exit(0)


@click.command()
def ps() -> None:
    """Show service status."""
    if not is_in_quickscale_project():
        click.secho(
            "❌ Error: Not in a QuickScale project directory", fg="red", err=True
        )
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
