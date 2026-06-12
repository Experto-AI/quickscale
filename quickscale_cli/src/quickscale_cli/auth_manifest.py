"""Auth module manifest-driven configuration adapter.

Replaces the legacy ``auth_contract.py`` by sourcing defaults from the
auth ``module.yml`` manifest and routing normalization and resolution
through the manifest-driven resolver
(:mod:`quickscale_core.manifest.resolver`).

The public API is a drop-in replacement for the old contract file so that
callers in ``module_config.py`` and ``plan_command.py`` can migrate without
rewriting their logic.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from quickscale_core.manifest.loader import load_manifest_from_path
from quickscale_core.manifest.resolver import resolve_module_config
from quickscale_core.manifest.derivation import (
    ModuleDerivationSchema,
)

# ---------------------------------------------------------------------------
# Constants
#
# These are re-declared as module-level constants so that callers that
# reference them by name continue to work without changes.
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_AUTH_MANIFEST_PATH = _REPO_ROOT / "quickscale_modules" / "auth" / "module.yml"


def _load_auth_manifest() -> Any:
    """Load the auth module manifest from ``module.yml``."""
    return load_manifest_from_path(_AUTH_MANIFEST_PATH)


def _build_auth_derivation_schema() -> ModuleDerivationSchema:
    """Build a minimal derivation schema for the auth module.

    Auth has no special normalization or derived settings that the generic
    resolver needs to express — all auth-specific logic (legacy-key mapping
    and social_providers removal) is applied as adapter-level post-steps
    in the functions below.
    """
    return ModuleDerivationSchema(
        module_name="auth",
        version="1",
        option_derivations={},
    )


# ---------------------------------------------------------------------------
# Public API — drop-in replacement for auth_contract.py
# ---------------------------------------------------------------------------


def default_auth_module_options() -> dict[str, Any]:
    """Return the default planner/apply contract for auth.

    Defaults are sourced from the auth ``module.yml`` manifest via
    :meth:`ModuleManifest.get_defaults`.  This includes both mutable and
    immutable options (registration_enabled, email_verification,
    session_cookie_age, authentication_method).
    """
    manifest = _load_auth_manifest()
    result: dict[str, Any] = manifest.get_defaults()
    return result


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
    """Merge auth options with defaults and normalized overrides.

    Routes through the manifest-driven resolver for defaults extraction,
    then applies the auth-specific legacy-key normalization that the
    generic resolver does not cover.
    """
    manifest = _load_auth_manifest()
    schema = _build_auth_derivation_schema()

    # Normalize first to handle legacy keys before passing to the resolver.
    normalized_overrides = normalize_auth_module_options(options)

    result = resolve_module_config(manifest, schema, overrides=normalized_overrides)
    return dict(result.resolved)


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
