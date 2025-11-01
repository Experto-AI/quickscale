"""Project state detection and management utilities."""

from pathlib import Path
from typing import Any

from .docker_utils import find_docker_compose, get_running_containers


def get_project_state() -> dict[str, Any]:
    """Get comprehensive project state including directory and containers."""
    try:
        current_dir = Path.cwd()
    except OSError:
        return {
            "has_project": False,
            "project_dir": None,
            "project_name": None,
            "containers": [],
        }

    compose_file = find_docker_compose()
    has_project = compose_file is not None
    containers = get_running_containers() if has_project else []

    return {
        "has_project": has_project,
        "project_dir": current_dir if has_project else None,
        "project_name": current_dir.name if has_project else None,
        "containers": containers,
        "compose_file": compose_file,
    }


def is_in_quickscale_project() -> bool:
    """Check if current directory is a QuickScale project."""
    return find_docker_compose() is not None


def get_web_container_name() -> str:
    """Get the name of the web container (dynamically detected)."""
    project_name = Path.cwd().name
    containers = get_running_containers()

    # Try different naming patterns used by Docker Compose
    # Examples: test59_web, test59-web-1, test59_web_1
    for container in containers:
        if project_name in container and "web" in container:
            return container

    # Fallback to common patterns if no running container found
    return f"{project_name}-web-1"


def get_db_container_name() -> str:
    """Get the name of the database container (dynamically detected)."""
    project_name = Path.cwd().name
    containers = get_running_containers()

    # Try different naming patterns used by Docker Compose
    # Examples: test59_db, test59-db-1, test59_db_1
    for container in containers:
        if project_name in container and "db" in container:
            return container

    # Fallback to common patterns if no running container found
    return f"{project_name}-db-1"
