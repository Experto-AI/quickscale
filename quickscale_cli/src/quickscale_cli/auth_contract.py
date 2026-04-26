"""Shared auth-module configuration helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

AUTH_REGISTRATION_ENABLED_OPTION = "registration_enabled"
AUTH_EMAIL_VERIFICATION_OPTION = "email_verification"
AUTH_AUTHENTICATION_METHOD_OPTION = "authentication_method"
AUTH_SESSION_COOKIE_AGE_OPTION = "session_cookie_age"

AUTH_EMAIL_VERIFICATION_VALUES = ("none", "optional", "mandatory")
AUTH_AUTHENTICATION_METHOD_VALUES = ("email", "username", "both")
CANONICAL_AUTH_MODULE_OPTION_KEYS = frozenset(
    {
        AUTH_REGISTRATION_ENABLED_OPTION,
        AUTH_EMAIL_VERIFICATION_OPTION,
        AUTH_AUTHENTICATION_METHOD_OPTION,
        AUTH_SESSION_COOKIE_AGE_OPTION,
    }
)

LEGACY_AUTH_ALLOW_REGISTRATION_OPTION = "allow_registration"
LEGACY_AUTH_SOCIAL_PROVIDERS_OPTION = "social_providers"


def default_auth_module_options() -> dict[str, Any]:
    """Return the default planner/apply contract for auth."""
    return {
        AUTH_REGISTRATION_ENABLED_OPTION: True,
        AUTH_EMAIL_VERIFICATION_OPTION: "none",
        AUTH_AUTHENTICATION_METHOD_OPTION: "email",
        AUTH_SESSION_COOKIE_AGE_OPTION: 1209600,
    }


def format_auth_desired_config_contract() -> str:
    """Return concise remediation text for canonical auth desired config."""
    return "\n".join(
        [
            "Canonical auth keys/value shapes:",
            "modules.auth.registration_enabled: true|false",
            "modules.auth.email_verification: none|optional|mandatory",
            "modules.auth.authentication_method: email|username|both",
            "modules.auth.session_cookie_age: <positive integer seconds>  # optional",
            (
                "Remove legacy keys like modules.auth.allow_registration and "
                "modules.auth.social_providers."
            ),
        ]
    )


def normalize_auth_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return auth options with legacy keys normalized or removed."""
    normalized = dict(options or {})

    if (
        AUTH_REGISTRATION_ENABLED_OPTION not in normalized
        and LEGACY_AUTH_ALLOW_REGISTRATION_OPTION in normalized
    ):
        normalized[AUTH_REGISTRATION_ENABLED_OPTION] = normalized[
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
    "AUTH_AUTHENTICATION_METHOD_OPTION",
    "AUTH_AUTHENTICATION_METHOD_VALUES",
    "AUTH_EMAIL_VERIFICATION_OPTION",
    "AUTH_EMAIL_VERIFICATION_VALUES",
    "AUTH_REGISTRATION_ENABLED_OPTION",
    "AUTH_SESSION_COOKIE_AGE_OPTION",
    "CANONICAL_AUTH_MODULE_OPTION_KEYS",
    "LEGACY_AUTH_ALLOW_REGISTRATION_OPTION",
    "LEGACY_AUTH_SOCIAL_PROVIDERS_OPTION",
    "default_auth_module_options",
    "format_auth_desired_config_contract",
    "normalize_auth_module_options",
    "resolve_auth_module_options",
]
