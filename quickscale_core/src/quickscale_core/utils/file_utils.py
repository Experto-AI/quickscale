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
    Validate that project name is a valid project name (hyphens allowed)

    Returns tuple of (is_valid, error_message)
    """
    if not name:
        return False, "Project name cannot be empty"

    # Convert hyphens to underscores for Python identifier check
    package_name = name.replace("-", "_")

    if not package_name.isidentifier():
        return False, f"'{name}' cannot be converted to a valid Python identifier"

    if keyword.iskeyword(package_name):
        return False, f"'{package_name}' is a Python keyword and cannot be used"

    if package_name.lower() in RESERVED_NAMES:
        return False, f"'{name}' results in reserved name '{package_name}'"

    if name.startswith("_") or name.startswith("-"):
        return False, "Project name cannot start with underscore or hyphen"

    # Check for common problematic patterns
    # Allow hyphens in the regex
    if not re.match(r"^[a-z][a-z0-9_-]*$", name):
        return (
            False,
            "Project name must start with lowercase letter and contain only "
            "lowercase letters, numbers, underscores, and hyphens",
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
