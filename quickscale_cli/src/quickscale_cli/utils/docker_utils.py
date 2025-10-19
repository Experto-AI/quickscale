"""Docker interaction utilities for QuickScale CLI."""

import subprocess
import sys
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
        subprocess.run(["docker-compose", "--version"], capture_output=True, check=True, timeout=2)
        return ["docker-compose"]
    except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired):
        # Fall back to docker compose (newer Docker versions)
        return ["docker", "compose"]


def get_container_status(container_name: str) -> str | None:
    """Get status of a specific container."""
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"name={container_name}", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return result.stdout.strip() or None
    except (subprocess.SubprocessError, subprocess.TimeoutExpired):
        return None


def exec_in_container(container_name: str, command: list[str], interactive: bool = False) -> int:
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
