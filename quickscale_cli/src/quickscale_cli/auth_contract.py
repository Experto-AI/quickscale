"""Shared auth-module configuration helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

LEGACY_AUTH_ALLOW_REGISTRATION_OPTION = "allow_registration"
LEGACY_AUTH_SOCIAL_PROVIDERS_OPTION = "social_providers"


def default_auth_module_options() -> dict[str, Any]:
    """Return the default planner/apply contract for auth."""
    return {
        "registration_enabled": True,
        "email_verification": "none",
        "authentication_method": "email",
        "session_cookie_age": 1209600,
    }


def normalize_auth_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return auth options with legacy keys normalized or removed."""
    normalized = dict(options or {})

    if (
        "registration_enabled" not in normalized
        and LEGACY_AUTH_ALLOW_REGISTRATION_OPTION in normalized
    ):
        normalized["registration_enabled"] = normalized[
            LEGACY_AUTH_ALLOW_REGISTRATION_OPTION
        ]

    normalized.pop(LEGACY_AUTH_ALLOW_REGISTRATION_OPTION, None)
    normalized.pop(LEGACY_AUTH_SOCIAL_PROVIDERS_OPTION, None)
    return normalized


def resolve_auth_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Merge auth options with defaults and normalized overrides."""
    resolved = default_auth_module_options()
    resolved.update(normalize_auth_module_options(options))
    return resolved


__all__ = [
    "LEGACY_AUTH_ALLOW_REGISTRATION_OPTION",
    "LEGACY_AUTH_SOCIAL_PROVIDERS_OPTION",
    "default_auth_module_options",
    "normalize_auth_module_options",
    "resolve_auth_module_options",
]
