"""Project state detection and management utilities."""

import os
from pathlib import Path
from typing import Any

from quickscale_core.schema.config_schema import QuickScaleConfig, validate_config
from .docker_utils import (
    RESOURCE_PREFIX_ENV_VAR,
    find_docker_compose,
    get_resource_prefix,
    get_running_containers,
)


class ProjectConfigLoadError(ValueError):
    """Raised when a strict quickscale.yml read must fail explicitly."""


def get_project_config(*, strict: bool = False) -> QuickScaleConfig | None:
    """Load and validate quickscale.yml from current directory if it exists."""
    config_path = Path.cwd() / "quickscale.yml"
    if not config_path.exists():
        return None
    try:
        return validate_config(config_path.read_text())
    except Exception as error:
        if strict:
            raise ProjectConfigLoadError(f"Invalid quickscale.yml: {error}") from error
        return None


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


def _container_name_candidates(prefix: str, service: str) -> tuple[str, ...]:
    """Return only complete, known Compose naming forms for one service."""
    return (
        f"{prefix}_{service}",
        f"{prefix}-{service}-1",
        f"{prefix}_{service}_1",
    )


def _get_service_container_name(service: str) -> str:
    """Resolve one service without substring or cross-project matching."""
    explicit_prefix = os.environ.get(RESOURCE_PREFIX_ENV_VAR)
    prefix = get_resource_prefix()
    containers = get_running_containers()

    candidates = _container_name_candidates(prefix, service)
    for candidate in candidates:
        if candidate in containers:
            return candidate

    # An explicit run prefix is authoritative.  Do not fall back to a
    # similarly named container from the ordinary project namespace.
    if explicit_prefix is not None:
        return candidates[0]

    # Preserve the historical ordinary-project fallback and its hyphenated
    # Compose form, while keeping the lookup itself exact.
    return candidates[1]


def get_backend_container_name() -> str:
    """Get the exact backend container for the validated resource prefix."""
    return _get_service_container_name("backend")


def get_db_container_name() -> str:
    """Get the exact database container for the validated resource prefix."""
    return _get_service_container_name("db")
