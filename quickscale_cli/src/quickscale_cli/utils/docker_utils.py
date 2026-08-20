"""Docker interaction utilities for QuickScale CLI."""

import socket
import subprocess
import sys
import time
from pathlib import Path


class DockerComposePluginRequiredError(RuntimeError):
    """Raised when the Docker Compose v2 plugin is unavailable."""


def is_interactive() -> bool:
    """Check if running in an interactive terminal (has TTY)."""
    return sys.stdout.isatty() and sys.stdin.isatty()


def is_docker_running() -> bool:
    """Check if Docker daemon is running."""
    try:
        subprocess.run(["docker", "info"], capture_output=True, check=True, timeout=5)
        return True
    except (
        subprocess.SubprocessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return False


def find_docker_compose() -> Path | None:
    """Locate docker-compose.yml in current directory."""
    compose_file = Path("docker-compose.yml")
    return compose_file if compose_file.exists() else None


def get_docker_compose_command() -> list[str]:
    """Get the Docker Compose v2 command."""
    try:
        subprocess.run(
            ["docker", "compose", "version"], capture_output=True, check=True, timeout=2
        )
    except (
        subprocess.SubprocessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ) as error:
        raise DockerComposePluginRequiredError(
            "Docker Compose v2 is required. Install or update Docker so the "
            "'docker compose' command is available."
        ) from error

    return ["docker", "compose"]


def get_container_status(container_name: str) -> str | None:
    """Get status of a specific container."""
    try:
        result = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                f"name={container_name}",
                "--format",
                "{{.Status}}",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return result.stdout.strip() or None
    except subprocess.SubprocessError, subprocess.TimeoutExpired:
        return None


def exec_in_container(
    container_name: str, command: list[str], interactive: bool = False
) -> int:
    """Execute command in a container."""
    cmd = ["docker", "exec"]
    if interactive:
        cmd.append("-it")
    cmd.append(container_name)
    cmd.extend(command)

    try:
        result = subprocess.run(cmd)
        return result.returncode
    except subprocess.SubprocessError:
        return 1


def get_running_containers() -> list[str]:
    """Get list of running QuickScale containers."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        containers = [c for c in result.stdout.strip().split("\n") if c]
        return containers
    except subprocess.SubprocessError, subprocess.TimeoutExpired:
        return []


def is_port_available(port: int, host: str = "0.0.0.0") -> bool:
    """Check if a port is available for binding.

    This is more accurate than checking for listening processes because it
    actually attempts to bind to the port, which is what Docker will do.

    Args:
        port: Port number to check
        host: Host address (default: 0.0.0.0 to match Docker behavior)

    Returns:
        True if port is available, False if already in use
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        sock.bind((host, port))
        sock.close()
        return True
    except OSError:
        # Port is already in use
        sock.close()
        return False


def wait_for_port_release(
    port: int, timeout: float = 5.0, interval: float = 0.2
) -> bool:
    """Wait for a port to become available.

    Docker's proxy process may take a few seconds to fully release ports
    after containers are stopped, especially on slower systems.

    Args:
        port: Port number to wait for
        timeout: Maximum time to wait in seconds (default: 5.0 for docker-proxy cleanup)
        interval: Time between checks in seconds

    Returns:
        True if port became available, False if timeout
    """
    elapsed = 0.0
    while elapsed < timeout:
        if is_port_available(port):
            return True
        time.sleep(interval)
        elapsed += interval
    return False


def get_port_from_env() -> int:
    """Get the Docker port from the environment.

    Returns the docker-compose-aligned default (8000) only when ``PORT`` is
    unset. A present but non-numeric ``PORT`` is treated as a configuration
    error and raises ``ValueError``.
    """
    import os

    # Check PORT environment variable (matches docker-compose.yml)
    port_str = os.environ.get("PORT", "8000")
    try:
        return int(port_str)
    except ValueError as error:
        raise ValueError(
            f"PORT environment variable must be an integer, got {port_str!r}"
        ) from error


# ---------------------------------------------------------------------------
# Stale Compose volume detection
# ---------------------------------------------------------------------------
# Compose derives its project name from the project directory and prefixes
# every named volume with it.  A freshly generated project whose slug matches
# a previously-used one therefore silently reattaches to the old database,
# and Django then fails with an opaque ``InconsistentMigrationHistory``
# because the leftover schema predates the modules embedded this time.


def compose_project_name(project_path: Path) -> str:
    """Return the Compose project name derived from *project_path*.

    Mirrors Compose's normalization: lowercase, with every character outside
    ``[a-z0-9_-]`` replaced by an underscore and leading separators dropped.
    """
    normalized = "".join(
        char if char.isalnum() or char in "_-" else "_"
        for char in project_path.resolve().name.lower()
    )
    return normalized.lstrip("_-")


def compose_declared_volume_names(compose_file: Path) -> list[str]:
    """Return the top-level named volumes declared in a Compose file.

    Parsed with a minimal line reader rather than a YAML dependency so the
    helper stays usable wherever the CLI runs.  Returns an empty list when the
    file is unreadable or declares no top-level ``volumes:`` block.
    """
    try:
        lines = compose_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    volumes: list[str] = []
    in_volumes_block = False
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line[:1].isspace():
            # A new top-level key ends any volumes block we were reading.
            in_volumes_block = stripped.rstrip(":") == "volumes"
            continue
        if not in_volumes_block:
            continue
        # Only first-level entries under `volumes:` name a volume; deeper
        # indentation carries that volume's own options.
        indent = len(line) - len(line.lstrip())
        if indent > 2:
            continue
        name = stripped.split(":", 1)[0].strip()
        if name and name not in volumes:
            volumes.append(name)
    return volumes


def list_existing_volumes(names: list[str]) -> list[str]:
    """Return the subset of *names* that currently exist as Docker volumes."""
    if not names:
        return []
    try:
        result = subprocess.run(
            ["docker", "volume", "ls", "--format", "{{.Name}}"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (
        subprocess.SubprocessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return []

    existing = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    return [name for name in names if name in existing]


def find_stale_project_volumes(project_path: Path) -> list[str]:
    """Return pre-existing Compose volumes belonging to *project_path*.

    Meaningful only for a project whose database has never been provisioned
    by this checkout: any hit is a leftover from an earlier project that
    happened to use the same directory name.
    """
    compose_file = project_path / "docker-compose.yml"
    if not compose_file.exists():
        return []

    project_name = compose_project_name(project_path)
    if not project_name:
        return []

    candidates = [
        f"{project_name}_{volume}"
        for volume in compose_declared_volume_names(compose_file)
    ]
    return list_existing_volumes(candidates)


def remove_volumes(names: list[str]) -> tuple[list[str], list[str]]:
    """Remove Docker volumes, returning ``(removed, failed)`` name lists."""
    removed: list[str] = []
    failed: list[str] = []
    for name in names:
        try:
            result = subprocess.run(
                ["docker", "volume", "rm", name],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
        except (
            subprocess.SubprocessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ):
            failed.append(name)
            continue
        if result.returncode == 0:
            removed.append(name)
        else:
            failed.append(name)
    return removed, failed


def compose_down(project_path: Path) -> bool:
    """Stop and remove this project's Compose containers (volumes untouched).

    Containers left behind by an earlier project of the same name keep its
    volumes attached, so they must be released before the volumes can be
    removed.  Returns True when Compose reports success.
    """
    try:
        compose_cmd = get_docker_compose_command()
    except DockerComposePluginRequiredError:
        return False

    try:
        result = subprocess.run(
            compose_cmd + ["down", "--remove-orphans"],
            cwd=project_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    except (
        subprocess.SubprocessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return False
    return result.returncode == 0
