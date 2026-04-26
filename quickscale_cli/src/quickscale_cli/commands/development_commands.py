"""Development lifecycle commands for QuickScale projects."""

import json
import re
import subprocess
import sys
from pathlib import Path

import click

from quickscale_cli.schema.config_schema import QuickScaleConfig
from quickscale_cli.utils.docker_utils import (
    get_docker_compose_command,
    get_port_from_env,
    is_docker_running,
    is_interactive,
    is_port_available,
    wait_for_port_release,
)
from quickscale_cli.utils.project_manager import (
    get_backend_container_name,
    get_project_config,
    is_in_quickscale_project,
    ProjectConfigLoadError,
)


def _validate_project_and_docker() -> bool:
    """Validate that we're in a QuickScale project and Docker is running.

    Returns:
        True if validation passes, exits with code 1 otherwise.
    """
    if not is_in_quickscale_project():
        click.secho(
            "❌ Error: Not in a QuickScale project directory", fg="red", err=True
        )
        if (Path.cwd() / "quickscale.yml").exists():
            click.echo(
                "💡 Tip: Found quickscale.yml but project files are not generated yet. "
                "Run 'quickscale apply' first.",
                err=True,
            )
        else:
            click.echo(
                "💡 Tip: Navigate to a generated project directory "
                "(contains docker-compose.yml)",
                err=True,
            )
        sys.exit(1)

    if not is_docker_running():
        click.secho("❌ Error: Docker is not running", fg="red", err=True)
        click.echo("💡 Tip: Start Docker Desktop or the Docker daemon", err=True)
        sys.exit(1)

    return True


def _show_port_conflict_error(port: int | str) -> None:
    """Display user-friendly error message for port conflicts."""
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


def _run_docker_compose_up(compose_cmd: list, build: bool, no_cache: bool) -> None:
    """Execute docker-compose up with appropriate flags."""
    if build or no_cache:
        cmd = compose_cmd + ["--progress", "plain", "up", "-d"]
    else:
        cmd = compose_cmd + ["up", "-d"]

    if build or no_cache:
        cmd.append("--build")

    if no_cache:
        cmd.append("--no-cache")

    click.echo("🚀 Starting Docker services...")

    if build or no_cache:
        click.echo("📦 Building Docker images...")
        click.echo("")
        subprocess.run(cmd, check=True, text=True)
    else:
        subprocess.run(cmd, check=True, capture_output=True, text=True)

    click.secho("✅ Services started successfully!", fg="green", bold=True)
    click.echo("💡 Tip: Use 'quickscale logs' to view service logs")


def _handle_up_error(error: subprocess.CalledProcessError) -> None:
    """Handle docker-compose up errors with user-friendly messages."""
    error_output = error.stderr if error.stderr else ""
    stdout_output = error.stdout if error.stdout else ""
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
            f"❌ Error: Failed to start services (exit code: {error.returncode})",
            fg="red",
            err=True,
        )
        if full_output:
            click.echo(f"\nError output:\n{full_output}", err=True)
        click.echo(
            "💡 Tip: Check Docker logs with 'quickscale logs' for details",
            err=True,
        )


def _run_migrations_after_up() -> None:
    """Run Django migrations in backend container after services start"""
    click.echo("⏳ Applying database migrations...")
    container_name = get_backend_container_name()
    _run_docker_exec_command(
        container_name,
        ["python", "manage.py", "migrate"],
        capture=True,
    )
    click.secho("✅ Database migrations applied", fg="green")


def _superuser_exists_in_backend(container_name: str) -> bool | None:
    """Check whether a Django superuser already exists

    Returns:
        True when at least one superuser exists
        False when no superuser exists
        None when status cannot be verified reliably
    """
    check_cmd = [
        "docker",
        "exec",
        container_name,
        "python",
        "manage.py",
        "shell",
        "-c",
        (
            "from django.contrib.auth import get_user_model; import sys; "
            "sys.exit(0 if get_user_model().objects.filter(is_superuser=True).exists() else 1)"
        ),
    ]
    result = subprocess.run(check_cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return True

    stdout_output = (result.stdout or "").strip()
    stderr_output = (result.stderr or "").strip()

    if result.returncode == 1 and not stdout_output and not stderr_output:
        return False

    return None


def _handle_superuser_after_up(config: QuickScaleConfig | None) -> None:
    """Create superuser if configured and one does not already exist"""
    if config is None or config.docker is None:
        return

    if not getattr(config.docker, "create_superuser", False):
        return

    container_name = get_backend_container_name()
    superuser_exists = _superuser_exists_in_backend(container_name)
    interactive_session = is_interactive()

    if superuser_exists is True:
        click.echo("ℹ️  Superuser already exists. Skipping createsuperuser step.")
        return

    if superuser_exists is None:
        click.secho("⚠️  Could not verify superuser status.", fg="yellow")
        if not interactive_session:
            click.echo("   Run: quickscale manage createsuperuser")
            return
        click.echo("   Proceeding with interactive superuser creation.")
    elif not interactive_session:
        click.secho(
            "⚠️  Superuser creation is enabled but requires interactive input.",
            fg="yellow",
        )
        click.echo("   Run: quickscale manage createsuperuser")
        return

    click.echo("👤 Creating Django superuser...")
    _run_docker_exec_command(
        container_name,
        ["python", "manage.py", "createsuperuser"],
        capture=False,
    )


def _command_contains(error: subprocess.CalledProcessError, *tokens: str) -> bool:
    """Check whether error command contains all tokens"""
    cmd = error.cmd
    if isinstance(cmd, list):
        cmd_text = " ".join(str(part) for part in cmd)
    else:
        cmd_text = str(cmd)
    return all(token in cmd_text for token in tokens)


@click.command()
@click.option("--build", is_flag=True, help="Rebuild containers before starting")
@click.option("--no-cache", is_flag=True, help="Build without using cache")
def up(build: bool, no_cache: bool) -> None:
    """Start Docker services for development."""
    _validate_project_and_docker()

    # Load config to check for default build behavior
    try:
        config = get_project_config(strict=True)
    except ProjectConfigLoadError as error:
        click.secho("❌ Error: quickscale.yml is invalid", fg="red", err=True)
        click.echo(str(error), err=True)
        click.echo(
            "💡 Tip: Fix quickscale.yml before running 'quickscale up'.",
            err=True,
        )
        sys.exit(1)

    should_build = build
    if not build and config and config.docker:
        should_build = config.docker.build

    # Check if dependencies changed and suggest rebuild
    if not should_build and _dependencies_changed_since_last_build():
        click.secho(
            "⚠️  Warning: Dependencies may have changed since last Docker build",
            fg="yellow",
            bold=True,
        )
        click.echo(
            "   This can happen after embedding modules or updating dependencies.\n"
            "   If you encounter import errors, rebuild the image:\n"
        )
        click.secho("   quickscale down && quickscale up --build\n", fg="cyan")

    # Check if required port is available BEFORE calling docker-compose
    port = get_port_from_env()
    if not is_port_available(port):
        _show_port_conflict_error(port)
        sys.exit(1)

    try:
        compose_cmd = get_docker_compose_command()
        _run_docker_compose_up(compose_cmd, should_build, no_cache)

        # Update build timestamp if build was performed
        if should_build:
            _update_last_build_timestamp()

        _run_migrations_after_up()
        _handle_superuser_after_up(config)

    except subprocess.CalledProcessError as e:
        if _command_contains(e, "manage.py", "migrate"):
            click.secho(
                "❌ Error: Services started but database migration failed",
                fg="red",
                err=True,
            )
            if e.stderr:
                click.echo(f"\nError output:\n{e.stderr}", err=True)
            click.echo(
                "💡 Tip: Run 'quickscale manage migrate' and inspect logs with 'quickscale logs backend'",
                err=True,
            )
        elif _command_contains(e, "manage.py", "createsuperuser"):
            click.secho(
                "❌ Error: Services started but superuser creation failed",
                fg="red",
                err=True,
            )
            click.echo(
                "💡 Tip: Run 'quickscale manage createsuperuser' manually", err=True
            )
        else:
            _handle_up_error(e)
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\n⚠️  Interrupted by user")
        sys.exit(130)


@click.command()
@click.option("--volumes", is_flag=True, help="Remove volumes as well")
def down(volumes: bool) -> None:
    """Stop Docker services."""
    _validate_project_and_docker()

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


def _run_docker_exec_command(
    container_name: str, cmd_args: list[str], capture: bool = False
) -> None:
    """Run a command in a docker container with appropriate TTY handling."""
    docker_cmd = ["docker", "exec"]
    if is_interactive():
        docker_cmd.append("-it")
    docker_cmd.extend([container_name] + cmd_args)

    if is_interactive() or not capture:
        subprocess.run(docker_cmd, check=True)
    else:
        result = subprocess.run(docker_cmd, capture_output=True, text=True, check=True)
        if result.stdout:
            click.echo(result.stdout, nl=False)
        if result.stderr:
            click.echo(result.stderr, nl=False, err=True)


@click.command()
@click.option(
    "-c", "--command", "cmd", help="Run a single command instead of interactive shell"
)
def shell(cmd: str | None) -> None:
    """Open an interactive bash shell in the backend container."""
    _validate_project_and_docker()

    try:
        container_name = get_backend_container_name()

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
            _run_docker_exec_command(container_name, ["bash"])

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
    """Run Django management commands in the backend container."""
    _validate_project_and_docker()

    if not args:
        click.secho(
            "❌ Error: No Django management command specified", fg="red", err=True
        )
        click.echo(
            "💡 Tip: Run 'quickscale manage help' to see available commands", err=True
        )
        sys.exit(1)

    try:
        container_name = get_backend_container_name()
        cmd_args = ["python", "manage.py"] + list(args)
        _run_docker_exec_command(container_name, cmd_args, capture=True)

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
    _validate_project_and_docker()

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
    _validate_project_and_docker()

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


def _get_build_state_file() -> Path:
    """Get path to build state tracking file."""
    return Path.cwd() / ".quickscale" / "build_state.json"


def _dependencies_changed_since_last_build() -> bool:
    """
    Check if pyproject.toml or poetry.lock changed since last Docker build.

    Returns
    -------
        True if dependencies may have changed, False otherwise
    """
    build_state_file = _get_build_state_file()
    pyproject_file = Path.cwd() / "pyproject.toml"
    poetry_lock_file = Path.cwd() / "poetry.lock"

    # If build state file doesn't exist, we can't determine if changed
    # (likely first time running, or old project)
    if not build_state_file.exists():
        return False

    # If dependency files don't exist, something is wrong but don't warn
    if not pyproject_file.exists() or not poetry_lock_file.exists():
        return False

    try:
        with open(build_state_file) as f:
            build_state = json.load(f)

        last_pyproject_mtime: float = build_state.get("pyproject_mtime", 0)
        last_poetry_lock_mtime: float = build_state.get("poetry_lock_mtime", 0)

        current_pyproject_mtime = pyproject_file.stat().st_mtime
        current_poetry_lock_mtime = poetry_lock_file.stat().st_mtime

        # Return True if either file changed since last build
        changed: bool = (
            current_pyproject_mtime > last_pyproject_mtime
            or current_poetry_lock_mtime > last_poetry_lock_mtime
        )
        return changed

    except (json.JSONDecodeError, KeyError, OSError):
        # If we can't read state, don't warn (fail safe)
        return False


def _update_last_build_timestamp() -> None:
    """Update build state file with current dependency file timestamps."""
    build_state_file = _get_build_state_file()
    pyproject_file = Path.cwd() / "pyproject.toml"
    poetry_lock_file = Path.cwd() / "poetry.lock"

    # Ensure .quickscale directory exists
    build_state_file.parent.mkdir(parents=True, exist_ok=True)

    # Get current timestamps
    pyproject_mtime = pyproject_file.stat().st_mtime if pyproject_file.exists() else 0
    poetry_lock_mtime = (
        poetry_lock_file.stat().st_mtime if poetry_lock_file.exists() else 0
    )

    # Write build state
    build_state = {
        "pyproject_mtime": pyproject_mtime,
        "poetry_lock_mtime": poetry_lock_mtime,
    }

    with open(build_state_file, "w") as f:
        json.dump(build_state, f, indent=2)
