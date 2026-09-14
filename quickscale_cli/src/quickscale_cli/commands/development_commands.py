"""Development lifecycle commands for QuickScale projects."""

import os
import re
import subprocess
import sys
from pathlib import Path

import click

from quickscale_core.schema.config_schema import QuickScaleConfig
from quickscale_core.utils.theme_validation import (
    ThemeValidationError,
    validate_theme_preflight,
)
from quickscale_cli.utils.docker_utils import (
    BackendImageIdentityError,
    DockerComposePluginRequiredError,
    build_backend_child_environment,
    build_backend_image_identity,
    find_stale_project_volumes,
    get_docker_compose_command,
    get_port_from_env,
    is_docker_running,
    is_interactive,
    is_port_available,
    wait_for_port_release,
)
from quickscale_cli.utils.development_state import (
    _dependencies_changed_since_last_build,
    _get_build_state_file,  # noqa: F401 - preserve the historical private seam
    _update_last_build_timestamp,
)
from quickscale_cli.utils.project_manager import (
    get_backend_container_name,
    get_project_config,
    is_in_quickscale_project,
    ProjectConfigLoadError,
)


VERIFY_COMPOSE_PROJECT_ENV_VAR = "QUICKSCALE_VERIFY_COMPOSE_PROJECT"
_VERIFY_COMPOSE_PROJECT_PATTERN = re.compile(r"qs-sa117b-[0-9a-f]{32}\Z")
_PRIVILEGED_DJANGO_COMMANDS = frozenset(
    {"migrate", "createcachetable", "migrate_billing_to_orgs"}
)


def _validated_verifier_compose_project() -> str | None:
    """Return the exact verifier-owned Compose identity, if present."""
    marker = os.environ.get(VERIFY_COMPOSE_PROJECT_ENV_VAR)
    if marker is None or _VERIFY_COMPOSE_PROJECT_PATTERN.fullmatch(marker) is None:
        return None
    return marker


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


def _show_compose_v2_required_error() -> None:
    """Display a user-friendly error when Docker Compose v2 is unavailable."""
    click.secho(
        "❌ Error: Docker Compose v2 plugin is required",
        fg="red",
        err=True,
    )
    click.echo(
        "💡 Tip: Install or update Docker so the 'docker compose' command is "
        "available. QuickScale keeps the generated 'docker-compose.yml' file "
        "name, but the CLI uses the Docker Compose v2 plugin.",
        err=True,
    )


def _require_docker_compose_command() -> list[str]:
    """Return the Docker Compose v2 command or exit with remediation text."""
    try:
        return get_docker_compose_command()
    except DockerComposePluginRequiredError:
        _show_compose_v2_required_error()
        sys.exit(1)


def _validate_theme_preflight_for_up() -> None:
    """Run the read-only theme preflight and display its up remediation."""
    try:
        validate_theme_preflight(
            Path.cwd(),
            allow_recovery_checkpoint=True,
        )
    except ThemeValidationError as exc:
        exc_text = str(exc)
        click.secho(
            "\n❌ Theme validation failed:",
            fg="red",
            err=True,
            bold=True,
        )
        for line in exc_text.splitlines():
            click.echo(f"  • {line}", err=True)
        click.echo(
            "\n💡 Update project.theme to 'showcase_react' in all present "
            "configuration files before running 'quickscale up'.",
            err=True,
        )
        sys.exit(1)


def _backend_compose_environment(project_path: Path | None = None) -> dict[str, str]:
    """Build the isolated Compose environment for a generated project."""
    root = project_path or Path.cwd()
    environment = os.environ.copy()
    if not ((root / "Dockerfile").exists() or (root / "docker-compose.yml").exists()):
        return environment
    try:
        image_identity = build_backend_image_identity(root)
        return build_backend_child_environment(
            image_identity,
            base_environment=environment,
            project_path=root,
        )
    except BackendImageIdentityError as error:
        click.secho("❌ Error: Backend image identity is invalid", fg="red", err=True)
        click.echo(str(error), err=True)
        sys.exit(1)
    except ValueError as error:
        click.secho("❌ Error: Docker resource prefix is invalid", fg="red", err=True)
        click.echo(str(error), err=True)
        sys.exit(1)


def _run_docker_compose_up(
    compose_cmd: list,
    build: bool,
    no_cache: bool,
    *,
    environment: dict[str, str] | None = None,
) -> None:
    """Execute docker compose up with appropriate flags."""
    project_name = _validated_verifier_compose_project()
    compose_prefix = compose_cmd + (
        ["--project-name", project_name] if project_name else []
    )
    if build or no_cache:
        cmd = compose_prefix + ["--progress", "plain", "up", "-d"]
    else:
        cmd = compose_prefix + ["up", "-d"]

    if build or no_cache:
        cmd.append("--build")

    click.echo("🚀 Starting Docker services...")

    show_output = build or no_cache
    if show_output:
        click.echo("📦 Building Docker images...")
        click.echo("")
    if no_cache:
        _execute_compose_up(
            [*compose_prefix, "--progress", "plain", "build", "--no-cache"],
            show_output=True,
            environment=environment,
        )
    _execute_compose_up(cmd, show_output=show_output, environment=environment)

    click.secho("✅ Services started successfully!", fg="green", bold=True)
    click.echo("💡 Tip: Use 'quickscale logs' to view service logs")


def _execute_compose_up(
    cmd: list[str],
    *,
    show_output: bool,
    environment: dict[str, str] | None,
) -> None:
    """Run one prepared Compose command with the requested output policy."""
    child_environment = dict(environment or os.environ)
    if show_output:
        subprocess.run(cmd, check=True, text=True, env=child_environment)
        return
    subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        env=child_environment,
    )


def _handle_up_error(error: subprocess.CalledProcessError) -> None:
    """Handle docker compose up errors with user-friendly messages."""
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
            f"   2. Remove orphaned containers: docker compose down --remove-orphans\n"
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
        privileged_command="migrate",
    )
    click.secho("✅ Database migrations applied", fg="green")


_SUPERUSER_SENTINEL = "QUICKSCALE_SUPERUSER="


def _superuser_exists_in_backend(container_name: str) -> bool | None:
    """Check whether a Django superuser already exists.

    The probe prints an explicit ``QUICKSCALE_SUPERUSER=1`` or ``=0`` sentinel
    to stdout so that the reader can determine the result without relying on
    exit codes or stream emptiness (Django 5.2+ emits an auto-import banner to
    stdout on every ``manage.py shell`` invocation).

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
            "from django.contrib.auth import get_user_model; "
            "import sys; "
            "exists = get_user_model().objects.filter(is_superuser=True).exists(); "
            "print(f'QUICKSCALE_SUPERUSER={int(exists)}'); "
            "sys.exit(0)"
        ),
    ]
    result = subprocess.run(check_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None

    for line in reversed((result.stdout or "").splitlines()):
        stripped = line.strip()
        if stripped.startswith(_SUPERUSER_SENTINEL):
            value = stripped[len(_SUPERUSER_SENTINEL) :]
            if value == "1":
                return True
            if value == "0":
                return False
            return None
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


def _is_inconsistent_migration_history(error: subprocess.CalledProcessError) -> bool:
    """Return whether a failed migrate reported InconsistentMigrationHistory."""
    output = (error.stderr or "") + (error.stdout or "")
    return "InconsistentMigrationHistory" in output


def _show_inconsistent_migration_history_help() -> None:
    """Explain the leftover-volume cause of an inconsistent migration history.

    Compose names volumes after the project directory, so a project reusing an
    earlier project's directory name attaches to that project's database.  Its
    recorded migration history predates the modules embedded now (a swapped
    ``AUTH_USER_MODEL`` in particular), and Django refuses to continue.
    """
    stale_volumes = find_stale_project_volumes(Path.cwd())
    click.echo(
        "\n💡 This usually means the database predates the modules embedded in "
        "this project.\n"
        "   Docker volumes are named after the project directory, so a new "
        "project reuses\n"
        "   the database of any earlier project with the same name.",
        err=True,
    )
    if stale_volumes:
        click.echo("\n   Volumes currently attached to this project:", err=True)
        for volume in stale_volumes:
            click.echo(f"     • {volume}", err=True)
    click.echo(
        "\n   To start from a clean database (destroys its contents):\n"
        "     quickscale down\n"
        "     docker volume rm "
        + (" ".join(stale_volumes) if stale_volumes else "<project>_postgres_data")
        + "\n"
        "     quickscale up\n"
        "\n   To keep the data instead, inspect it with 'quickscale logs backend' "
        "and reconcile\n   the migration history manually.",
        err=True,
    )


def _handle_up_process_error(error: subprocess.CalledProcessError) -> None:
    """Report a failed post-start action or Compose invocation."""
    if _command_contains(error, "manage.py", "migrate"):
        click.secho(
            "❌ Error: Services started but database migration failed",
            fg="red",
            err=True,
        )
        if error.stderr:
            click.echo(f"\nError output:\n{error.stderr}", err=True)
        if _is_inconsistent_migration_history(error):
            _show_inconsistent_migration_history_help()
        else:
            click.echo(
                "💡 Tip: Run 'quickscale manage migrate' and inspect logs with 'quickscale logs backend'",
                err=True,
            )
        return

    if _command_contains(error, "manage.py", "createsuperuser"):
        click.secho(
            "❌ Error: Services started but superuser creation failed",
            fg="red",
            err=True,
        )
        click.echo("💡 Tip: Run 'quickscale manage createsuperuser' manually", err=True)
        return

    _handle_up_error(error)


def _load_up_config(build: bool) -> tuple[QuickScaleConfig | None, bool]:
    """Load the strict project config and resolve the requested build mode."""
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
    return config, should_build


def _warn_about_changed_dependencies(should_build: bool) -> None:
    """Warn when dependencies changed and the selected mode will not rebuild."""
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


def _run_up_services(
    config: QuickScaleConfig | None,
    should_build: bool,
    no_cache: bool,
    compose_environment: dict[str, str],
) -> None:
    """Start services and run the post-start Django commands."""
    try:
        compose_cmd = _require_docker_compose_command()
        _run_docker_compose_up(
            compose_cmd,
            should_build,
            no_cache,
            environment=compose_environment,
        )

        # Update build timestamp if build was performed
        if should_build:
            _update_last_build_timestamp()

        _run_migrations_after_up()
        _handle_superuser_after_up(config)

    except subprocess.CalledProcessError as error:
        _handle_up_process_error(error)
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\n⚠️  Interrupted by user")
        sys.exit(130)


@click.command()
@click.option("--build", is_flag=True, help="Rebuild containers before starting")
@click.option("--no-cache", is_flag=True, help="Build without using cache")
def up(build: bool, no_cache: bool) -> None:
    """Start Docker services for development."""
    # Run read-only theme preflight before any Docker/compose/port probe.
    # The recovery ledger (.quickscale/apply-recovery.yml) is an internal
    # apply checkpoint that may carry a ``__checkpoint__`` placeholder
    # theme before the real project state is saved. The validator's explicit
    # up-only opt-in accepts that placeholder; other recovery themes fail closed.
    _validate_theme_preflight_for_up()

    _validate_project_and_docker()

    config, should_build = _load_up_config(build)
    # Compute the stable identity after strict configuration validation and
    # before the port probe or any Compose invocation.
    compose_environment = _backend_compose_environment()
    _warn_about_changed_dependencies(should_build)

    # Check if required port is available BEFORE calling docker compose.
    port = get_port_from_env()
    if not is_port_available(port):
        _show_port_conflict_error(port)
        sys.exit(1)

    _run_up_services(config, should_build, no_cache, compose_environment)


@click.command()
@click.option("--volumes", is_flag=True, help="Remove volumes as well")
def down(volumes: bool) -> None:
    """Stop Docker services."""
    _validate_project_and_docker()

    try:
        compose_cmd = _require_docker_compose_command()
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
    container_name: str,
    cmd_args: list[str],
    capture: bool = False,
    privileged_command: str | None = None,
) -> None:
    """Run a command in a docker container with appropriate TTY handling.

    Args:
        container_name: Name of the target container.
        cmd_args: Command and arguments to execute inside the container.
        capture: When True, capture and echo output instead of streaming.
        privileged_command: A sanctioned privileged Django command (one of
            ``_PRIVILEGED_DJANGO_COMMANDS``).  Only then is
            ``RUNTIME_DATABASE_URL`` cleared, so the command runs under the
            superuser ``DATABASE_URL`` with the matching
            ``QUICKSCALE_PRIVILEGED_COMMAND`` exemption.  Every other command
            keeps the restricted runtime role: the orgs BYPASSRLS boot guard
            rejects a superuser connection for anything outside that set.
    """
    docker_cmd = ["docker", "exec"]
    if privileged_command is not None:
        if privileged_command not in _PRIVILEGED_DJANGO_COMMANDS:
            raise ValueError(f"Not a privileged Django command: {privileged_command!r}")
        docker_cmd.extend(
            [
                "-e",
                "RUNTIME_DATABASE_URL=",
                "-e",
                f"QUICKSCALE_PRIVILEGED_COMMAND={privileged_command}",
            ]
        )
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
        _run_docker_exec_command(
            container_name,
            cmd_args,
            capture=True,
            privileged_command=args[0]
            if args[0] in _PRIVILEGED_DJANGO_COMMANDS
            else None,
        )

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
        compose_cmd = _require_docker_compose_command()
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
        compose_cmd = _require_docker_compose_command()
        cmd = compose_cmd + ["ps"]
        subprocess.run(cmd, check=True)

    except subprocess.CalledProcessError as e:
        click.secho(
            f"❌ Error: Failed to get service status (exit code: {e.returncode})",
            fg="red",
            err=True,
        )
        sys.exit(1)
