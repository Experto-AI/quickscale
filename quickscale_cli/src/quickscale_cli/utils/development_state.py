"""Build-state tracking helpers for development commands."""

import json
from pathlib import Path


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

    except json.JSONDecodeError, KeyError, OSError:
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
