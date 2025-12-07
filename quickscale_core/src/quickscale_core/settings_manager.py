"""Settings Manager for QuickScale

Handles updating Django settings.py files for mutable module configuration.
"""

import re
from pathlib import Path
from typing import Any


class SettingsError(Exception):
    """Error updating settings file"""

    pass


def _bool_to_string(value: bool) -> str:
    """Convert boolean to Python string representation."""
    return "True" if value else "False"


def _str_to_string(value: str) -> str:
    """Convert string to Python string representation with escaping."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _list_to_string(value: list) -> str:
    """Convert list to Python string representation."""
    items = ", ".join(_python_value_to_string(item) for item in value)
    return f"[{items}]"


def _dict_to_string(value: dict) -> str:
    """Convert dict to Python string representation."""
    items = ", ".join(
        f"{_python_value_to_string(k)}: {_python_value_to_string(v)}"
        for k, v in value.items()
    )
    return f"{{{items}}}"


def _set_to_string(value: set) -> str:
    """Convert set to Python string representation."""
    items = ", ".join(_python_value_to_string(item) for item in sorted(value))
    return f"{{{items}}}"


def _python_value_to_string(value: Any) -> str:
    """Convert a Python value to its string representation for settings.py"""
    if value is None:
        return "None"
    if isinstance(value, bool):
        return _bool_to_string(value)
    if isinstance(value, str):
        return _str_to_string(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return _list_to_string(value)
    if isinstance(value, dict):
        return _dict_to_string(value)
    if isinstance(value, set):
        return _set_to_string(value)
    return repr(value)


def update_setting(
    settings_path: Path, setting_name: str, new_value: Any
) -> tuple[bool, str]:
    """Update a single setting in a settings.py file

    Args:
        settings_path: Path to settings.py file
        setting_name: Name of the setting to update (e.g., ACCOUNT_ALLOW_REGISTRATION)
        new_value: New value for the setting

    Returns:
        Tuple of (success, message)

    """
    if not settings_path.exists():
        return False, f"Settings file not found: {settings_path}"

    try:
        content = settings_path.read_text()
    except OSError as e:
        return False, f"Failed to read settings: {e}"

    # Convert value to Python string representation
    value_str = _python_value_to_string(new_value)

    # Pattern to match the setting (handles multi-line for complex values)
    # Matches: SETTING_NAME = value
    pattern = rf"^({setting_name}\s*=\s*).*$"

    # Check if setting exists
    if re.search(pattern, content, re.MULTILINE):
        # Replace existing setting
        new_content = re.sub(
            pattern,
            rf"\g<1>{value_str}",
            content,
            flags=re.MULTILINE,
        )
    else:
        # Append new setting at the end
        new_content = content.rstrip() + f"\n{setting_name} = {value_str}\n"

    try:
        settings_path.write_text(new_content)
    except OSError as e:
        return False, f"Failed to write settings: {e}"

    return True, f"Updated {setting_name} = {value_str}"


def update_multiple_settings(
    settings_path: Path, settings: dict[str, Any]
) -> list[tuple[str, bool, str]]:
    """Update multiple settings in a settings.py file

    Args:
        settings_path: Path to settings.py file
        settings: Dictionary of setting_name -> new_value

    Returns:
        List of tuples (setting_name, success, message)

    """
    results = []
    for setting_name, new_value in settings.items():
        success, message = update_setting(settings_path, setting_name, new_value)
        results.append((setting_name, success, message))
    return results


def get_setting_value(settings_path: Path, setting_name: str) -> tuple[bool, Any]:
    """Get current value of a setting from settings.py

    Args:
        settings_path: Path to settings.py file
        setting_name: Name of the setting

    Returns:
        Tuple of (found, value) - value is None if not found

    Note:
        This uses regex pattern matching and can handle simple values.
        For complex values (multi-line), it may not parse correctly.

    """
    if not settings_path.exists():
        return False, None

    try:
        content = settings_path.read_text()
    except OSError:
        return False, None

    # Pattern to match the setting
    pattern = rf"^{setting_name}\s*=\s*(.+)$"
    match = re.search(pattern, content, re.MULTILINE)

    if not match:
        return False, None

    value_str = match.group(1).strip()

    # Try to parse the value
    try:
        # Use ast.literal_eval for safe evaluation
        import ast

        value = ast.literal_eval(value_str)
        return True, value
    except (ValueError, SyntaxError):
        # Return as string if can't parse
        return True, value_str


def apply_mutable_config_changes(
    project_path: Path, module_name: str, config_changes: dict[str, Any]
) -> list[tuple[str, bool, str]]:
    """Apply mutable configuration changes to project settings

    Args:
        project_path: Path to the project root
        module_name: Name of the module (for error messages)
        config_changes: Dictionary of django_setting -> new_value

    Returns:
        List of tuples (setting_name, success, message)

    """
    # QuickScale uses settings/base.py structure
    settings_path = project_path / project_path.name / "settings" / "base.py"

    if not settings_path.exists():
        # Try alternative path
        settings_path = project_path / project_path.name / "settings.py"

    if not settings_path.exists():
        return [
            (
                "settings",
                False,
                f"Settings file not found for project: {project_path}",
            )
        ]

    return update_multiple_settings(settings_path, config_changes)
