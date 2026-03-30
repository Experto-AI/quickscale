"""Shared backups-module configuration helpers.

This module centralizes the non-secret configuration contract used by the
planner, apply flow, and state persistence for the backups module.
"""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

from quickscale_cli.notifications_contract import normalize_notifications_module_options

DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR = "QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID"
DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR = (
    "QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY"
)

BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION = "remote_access_key_id_env_var"
BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION = "remote_secret_access_key_env_var"

_LEGACY_BACKUPS_SECRET_OPTIONS = {
    "remote_access_key_id": DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR,
    "remote_secret_access_key": DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR,
}

_BACKUPS_ENV_VAR_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
_LIKELY_AWS_ACCESS_KEY_ID_PATTERN = re.compile(r"^(?:AKIA|ASIA)[A-Z0-9]{16}$")


def normalize_backups_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return backups options with legacy raw-secret keys removed.

    Legacy raw credential values are converted into conventional environment-variable
    references so downstream persistence layers never re-store the secret values.
    """
    normalized = dict(options or {})

    legacy_access_key_id = str(normalized.pop("remote_access_key_id", "")).strip()
    legacy_secret_access_key = str(
        normalized.pop("remote_secret_access_key", "")
    ).strip()

    access_key_env_var = str(
        normalized.get(BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION, "")
    ).strip()
    secret_access_key_env_var = str(
        normalized.get(BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION, "")
    ).strip()

    if legacy_access_key_id and not access_key_env_var:
        normalized[BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION] = (
            DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR
        )
    if legacy_secret_access_key and not secret_access_key_env_var:
        normalized[BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION] = (
            DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR
        )

    return normalized


def has_legacy_backups_secret_values(options: Mapping[str, Any] | None) -> bool:
    """Return whether backups options still include legacy raw-secret keys."""
    if not options:
        return False

    for option_name in _LEGACY_BACKUPS_SECRET_OPTIONS:
        if str(options.get(option_name, "")).strip():
            return True
    return False


def validate_backups_env_var_reference(option_name: str, value: Any) -> str | None:
    """Validate a backups env-var reference field.

    Returns an actionable error string when the value is not a safe environment
    variable name or appears to be a literal credential value.
    """
    candidate = str(value).strip()
    if not candidate:
        return None

    qualified_option = f"modules.backups.{option_name}"
    if not _BACKUPS_ENV_VAR_NAME_PATTERN.fullmatch(candidate):
        return (
            f"{qualified_option} must be an environment variable name matching "
            "^[A-Z][A-Z0-9_]*$"
        )

    if option_name == BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION:
        if _LIKELY_AWS_ACCESS_KEY_ID_PATTERN.fullmatch(candidate):
            return (
                f"{qualified_option} must reference an environment variable name, "
                "not a literal AWS access key id"
            )

    return None


def sanitize_module_options(
    module_name: str,
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return module options safe for config/state persistence."""
    if module_name == "backups":
        return normalize_backups_module_options(options)
    if module_name == "notifications":
        return normalize_notifications_module_options(options)
    return dict(options or {})


__all__ = [
    "BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION",
    "BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION",
    "DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR",
    "DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR",
    "has_legacy_backups_secret_values",
    "normalize_backups_module_options",
    "sanitize_module_options",
    "validate_backups_env_var_reference",
]
