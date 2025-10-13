"""File utilities for project generation"""

import keyword
import re
from pathlib import Path

# Reserved Django/Python project names that should not be used
RESERVED_NAMES = {
    # Python standard library
    "test",
    "tests",
    # Django core
    "django",
    "site",
    # Common package names that would conflict
    "utils",
    "common",
    "core",
}


def validate_project_name(name: str) -> tuple[bool, str]:
    """
    Validate that project name is a valid Python identifier

    Returns tuple of (is_valid, error_message)
    """
    if not name:
        return False, "Project name cannot be empty"

    if not name.isidentifier():
        return False, f"'{name}' is not a valid Python identifier"

    if keyword.iskeyword(name):
        return False, f"'{name}' is a Python keyword and cannot be used"

    if name.lower() in RESERVED_NAMES:
        return False, f"'{name}' is a reserved name and cannot be used"

    if name.startswith("_"):
        return False, "Project name cannot start with underscore"

    # Check for common problematic patterns
    if not re.match(r"^[a-z][a-z0-9_]*$", name):
        return (
            False,
            "Project name must start with lowercase letter and contain only "
            "lowercase letters, numbers, and underscores",
        )

    return True, ""


def ensure_directory(path: Path) -> None:
    """Create directory if it doesn't exist"""
    path.mkdir(parents=True, exist_ok=True)


def write_file(path: Path, content: str, executable: bool = False) -> None:
    """Write content to file with optional executable permission"""
    # Ensure parent directory exists
    ensure_directory(path.parent)

    # Write file
    path.write_text(content)

    # Set executable permission if requested
    if executable:
        current_mode = path.stat().st_mode
        path.chmod(current_mode | 0o111)  # Add execute permission for all
