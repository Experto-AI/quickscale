"""Docker interaction utilities for QuickScale CLI."""

import socket
import subprocess
import sys
import time
from pathlib import Path


def is_interactive() -> bool:
    """Check if running in an interactive terminal (has TTY)."""
    return sys.stdout.isatty() and sys.stdin.isatty()


def is_docker_running() -> bool:
    """Check if Docker daemon is running."""
    try:
        subprocess.run(["docker", "info"], capture_output=True, check=True, timeout=5)
        return True
    except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def find_docker_compose() -> Path | None:
    """Locate docker-compose.yml in current directory."""
    compose_file = Path("docker-compose.yml")
    return compose_file if compose_file.exists() else None


def get_docker_compose_command() -> list[str]:
    """Get the appropriate docker compose command."""
    # Try docker-compose first, fall back to docker compose
    try:
        subprocess.run(
            ["docker-compose", "--version"], capture_output=True, check=True, timeout=2
        )
        return ["docker-compose"]
    except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired):
        # Fall back to docker compose (newer Docker versions)
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
    except (subprocess.SubprocessError, subprocess.TimeoutExpired):
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
    except (subprocess.SubprocessError, subprocess.TimeoutExpired):
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
    """Get the port number from docker-compose.yml environment or default."""
    import os

    # Check PORT environment variable (matches docker-compose.yml)
    port_str = os.environ.get("PORT", "8000")
    try:
        return int(port_str)
    except ValueError:
        return 8000
