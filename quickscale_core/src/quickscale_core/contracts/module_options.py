"""Shared module options normalization, validation, and contract surface.

This module is the central location for module options normalization helpers
and the related constants/validators required by the schema layer. Owning
these symbols in ``quickscale_core`` keeps the schema files free of any
``quickscale_cli`` dependency and prepares the ground for relocating the
schema files themselves in Phase 1.

Each module name keeps the original normalization semantics that previously
lived in the per-module CLI contract files. Constants and validators used by
``config_schema.py`` are also re-exported here.

The module also owns the DR env-var portability classification. The legacy
implementation lived inline in ``quickscale_cli.commands.dr_commands``; the
helper now lives here so any future caller (CLI, generator, schema layer)
can classify an environment variable name without depending on the CLI.
"""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any, Final


# ---------------------------------------------------------------------------
# Constants: analytics
# ---------------------------------------------------------------------------

ANALYTICS_PROVIDER_POSTHOG: Final[str] = "posthog"
ANALYTICS_PROVIDERS: Final[tuple[str, ...]] = (ANALYTICS_PROVIDER_POSTHOG,)


# ---------------------------------------------------------------------------
# Constants: backups
# ---------------------------------------------------------------------------

BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION: Final[str] = "remote_access_key_id_env_var"
BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION: Final[str] = (
    "remote_secret_access_key_env_var"  # noqa: S105 - environment-variable name constant, not a credential
)


# ---------------------------------------------------------------------------
# Constants: billing
# ---------------------------------------------------------------------------

BILLING_ENV_VAR_OPTION_NAMES: Final[tuple[str, ...]] = (
    "publishable_key_env_var",
    "secret_key_env_var",
    "webhook_secret_env_var",
)


# ---------------------------------------------------------------------------
# Constants: notifications
# ---------------------------------------------------------------------------

DEFAULT_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR: Final[str] = "RESEND_API_KEY"
DEFAULT_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR: Final[str] = (
    "QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET"  # noqa: S105 - environment-variable name constant, not a credential
)

NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION: Final[str] = "resend_api_key_env_var"
NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION: Final[str] = "webhook_secret_env_var"  # noqa: S105 - environment-variable name constant, not a credential


# ---------------------------------------------------------------------------
# Constants: analytics (additional)
# ---------------------------------------------------------------------------

ANALYTICS_POSTHOG_DEFAULT_HOST: Final[str] = "https://us.i.posthog.com"
ANALYTICS_POSTHOG_EU_HOST: Final[str] = "https://eu.i.posthog.com"

ANALYTICS_EVENT_PAGEVIEW: Final[str] = "$pageview"
ANALYTICS_EVENT_FORM_SUBMIT: Final[str] = "form_submit"
ANALYTICS_EVENT_SOCIAL_LINK_CLICK: Final[str] = "social_link_click"


# ---------------------------------------------------------------------------
# Constants: notifications (additional)
# ---------------------------------------------------------------------------

DEFAULT_NOTIFICATIONS_DEFAULT_TAGS: Final[tuple[str, ...]] = (
    "quickscale",
    "transactional",
)
DEFAULT_NOTIFICATIONS_ALLOWED_TAGS: Final[tuple[str, ...]] = (
    "quickscale",
    "transactional",
    "notifications",
    "auth",
    "forms",
    "ops",
    "testing",
)

NOTIFICATIONS_LIVE_EMAIL_BACKEND: Final[str] = "anymail.backends.resend.EmailBackend"
NOTIFICATIONS_CONSOLE_EMAIL_BACKEND: Final[str] = (
    "django.core.mail.backends.console.EmailBackend"
)


# ---------------------------------------------------------------------------
# Constants: storage
# ---------------------------------------------------------------------------

STORAGE_BACKEND_LOCAL: Final[str] = "local"
STORAGE_BACKEND_S3: Final[str] = "s3"
STORAGE_BACKEND_R2: Final[str] = "r2"
STORAGE_BACKENDS: Final[tuple[str, ...]] = (
    STORAGE_BACKEND_LOCAL,
    STORAGE_BACKEND_S3,
    STORAGE_BACKEND_R2,
)

DEFAULT_STORAGE_BACKEND: Final[str] = "local"
DEFAULT_STORAGE_MEDIA_URL: Final[str] = "/media/"
DEFAULT_STORAGE_PUBLIC_BASE_URL: Final[str] = ""
DEFAULT_STORAGE_PRIVATE_MEDIA_ENABLED: Final[bool] = False

DEFAULT_STORAGE_ACCESS_KEY_ID_ENV_VAR: Final[str] = "AWS_ACCESS_KEY_ID"
DEFAULT_STORAGE_SECRET_ACCESS_KEY_ENV_VAR: Final[str] = "AWS_SECRET_ACCESS_KEY"  # noqa: S105 - environment-variable name constant, not a credential

STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION: Final[str] = "access_key_id_env_var"
STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION: Final[str] = "secret_access_key_env_var"  # noqa: S105 - environment-variable name constant, not a credential

_LEGACY_STORAGE_SECRET_OPTIONS: Final[dict[str, str]] = {
    "access_key_id": DEFAULT_STORAGE_ACCESS_KEY_ID_ENV_VAR,
    "secret_access_key": DEFAULT_STORAGE_SECRET_ACCESS_KEY_ENV_VAR,
}

STORAGE_MODULE_OPTION_KEYS: Final[frozenset[str]] = frozenset(
    {
        "backend",
        "media_url",
        "public_base_url",
        "bucket_name",
        "endpoint_url",
        "region_name",
        STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION,
        STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
        "default_acl",
        "querystring_auth",
        "private_media_enabled",
    }
)


# ---------------------------------------------------------------------------
# Constants: social
# ---------------------------------------------------------------------------

SOCIAL_LINK_TREE_PATH: Final[str] = "/social"
SOCIAL_EMBEDS_PATH: Final[str] = "/social/embeds"
SOCIAL_INTEGRATION_BASE_PATH: Final[str] = "/_quickscale/social/"
SOCIAL_INTEGRATION_EMBEDS_PATH: Final[str] = "/_quickscale/social/embeds/"
SOCIAL_LAYOUT_VARIANTS: Final[tuple[str, ...]] = ("list", "cards", "grid")


# ---------------------------------------------------------------------------
# Constants: DR env-var portability classification
# ---------------------------------------------------------------------------
#
# These lists are the central source of truth for the disaster-recovery
# env-var sync planner. The legacy implementation lived inline in
# ``quickscale_cli.commands.dr_commands``; the names below are exported
# here verbatim so the CLI keeps a thin import surface while future
# callers (schema, generator, future automation) can share the same
# classification.

#: Exact-match names that must never be copied during env-var sync because
#: they describe the local shell or runtime, not project state.
IGNORED_ENV_EXACT: Final[frozenset[str]] = frozenset(
    {
        "HOME",
        "HOSTNAME",
        "LANG",
        "OLDPWD",
        "PATH",
        "PWD",
        "PYTHONUNBUFFERED",
        "SHELL",
        "SHLVL",
        "TERM",
        "TZ",
        "USER",
        "_",
    }
)

#: Prefix patterns that mark a variable as shell/runtime noise. The match
#: is case-insensitive on the original name; classification normalises the
#: name before matching (see :func:`get_env_var_portability`).
IGNORED_ENV_PREFIXES: Final[tuple[str, ...]] = (
    "GPG_",
    "LC_",
    "NODE_",
    "NPM_",
    "PIP_",
    "PNPM_",
    "POETRY_",
    "PYTHON",
    "VIRTUAL_ENV",
)

#: Exact-match names that are safe to copy verbatim between source and
#: target environments.
PORTABLE_ENV_EXACT: Final[frozenset[str]] = frozenset({"DEBUG"})

#: Prefix patterns that mark a variable as portable. A name is portable
#: when it starts with one of these prefixes after case normalisation.
PORTABLE_ENV_PREFIXES: Final[tuple[str, ...]] = (
    "ACCOUNT_",
    "ANALYTICS_",
    "BLOG_",
    "DJANGO_",
    "FORMS_",
    "LISTINGS_",
    "NOTIFICATIONS_",
    "QUICKSCALE_",
    "SOCIAL_",
    "SOCIALACCOUNT_",
)

#: Exact-match names that must be set manually on the target environment
#: because they describe the target or its providers directly.
NON_PORTABLE_ENV_EXACT: Final[frozenset[str]] = frozenset(
    {
        "ALLOWED_HOSTS",
        "CSRF_TRUSTED_ORIGINS",
        "DATABASE_URL",
        "DJANGO_SETTINGS_MODULE",
        "MEDIA_ROOT",
        "MEDIA_URL",
        "PORT",
        "SECRET_KEY",
        "STATIC_URL",
    }
)

#: Prefix patterns that mark a variable as target/provider-owned.
NON_PORTABLE_ENV_PREFIXES: Final[tuple[str, ...]] = (
    "AWS_",
    "CELERY_BROKER_",
    "CLOUDFLARE_",
    "DATABASE_",
    "DJANGO_SUPERUSER_",
    "EMAIL_",
    "PG",
    "POSTGRES",
    "R2_",
    "RAILWAY_",
    "REDIS_",
    "RESEND_",
    "SENTRY_",
    "SMTP_",
    "STRIPE_",
)

#: Substring tokens that mark a variable as sensitive or
#: environment-specific. The match is performed against the normalised
#: name, so casing is irrelevant.
NON_PORTABLE_ENV_CONTAINS: Final[tuple[str, ...]] = (
    "BACKUPS_REMOTE",
    "BUCKET",
    "COOKIE",
    "CSRF",
    "DOMAIN",
    "ENDPOINT",
    "HOST",
    "KEY",
    "ORIGIN",
    "PASSWORD",
    "PRIVATE",
    "PUBLIC_BASE_URL",
    "REGION",
    "SECRET",
    "STORAGE_",
    "TOKEN",
    "URL",
)


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_NOTIFICATIONS_ENV_VAR_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[A-Z][A-Z0-9_]*$"
)
_BACKUPS_ENV_VAR_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Z][A-Z0-9_]*$")
_LIKELY_AWS_ACCESS_KEY_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(?:AKIA|ASIA)[A-Z0-9]{16}$"
)


# ---------------------------------------------------------------------------
# Normalize functions
# ---------------------------------------------------------------------------


def normalize_notifications_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return notifications options with legacy raw-secret keys raising.

    When *options* is empty (``None`` or ``{}``), returns the full manifest
    defaults so that implied modules without an explicit ``default_config``
    materialise the same options as an explicit default configuration.

    Raises:
        ConfigValidationError: if a legacy raw-secret key is present, naming the
            dead key and its env-var replacement.
    """
    from quickscale_core.schema.config_schema import ConfigValidationError

    normalized = dict(options or {})

    for legacy_key in ("resend_api_key", "webhook_secret"):
        if legacy_key in normalized:
            env_var_option = {
                "resend_api_key": (NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION),
                "webhook_secret": (NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION),
            }[legacy_key]
            raise ConfigValidationError(
                f"Legacy config key '{legacy_key}' is no longer supported. "
                f"Use '{env_var_option}' to reference an environment variable instead."
            )

    if not normalized:
        # No explicit options provided — return full manifest defaults.
        # Lazy import avoids circular dependency (resolvers imports from this
        # module for the normalize_*_module_options helpers).
        from quickscale_core.contracts.resolvers import default_notifications_module_options  # fmt: skip

        return default_notifications_module_options()

    if normalized.get("reply_to_email") is None:
        normalized["reply_to_email"] = ""

    return normalized


def normalize_storage_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return storage options with legacy raw-secret keys removed.

    Legacy raw credential values are converted into conventional environment-variable
    references so downstream persistence layers never re-store the secret values.
    """
    normalized = dict(options or {})

    legacy_access_key_id = str(normalized.pop("access_key_id", "")).strip()
    legacy_secret_access_key = str(normalized.pop("secret_access_key", "")).strip()

    access_key_env_var = str(
        normalized.get(STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION, "")
    ).strip()
    secret_access_key_env_var = str(
        normalized.get(STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION, "")
    ).strip()

    if legacy_access_key_id and not access_key_env_var:
        normalized[STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION] = (
            DEFAULT_STORAGE_ACCESS_KEY_ID_ENV_VAR
        )
    if legacy_secret_access_key and not secret_access_key_env_var:
        normalized[STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION] = (
            DEFAULT_STORAGE_SECRET_ACCESS_KEY_ENV_VAR
        )

    if "backend" in normalized:
        normalized["backend"] = str(normalized["backend"]).strip().lower()

    for strip_key in (
        "public_base_url",
        "bucket_name",
        "endpoint_url",
        "region_name",
        "default_acl",
        STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION,
        STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
    ):
        if strip_key in normalized:
            normalized[strip_key] = str(normalized[strip_key]).strip()

    return normalized


def normalize_social_module_options(
    options: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return a normalized social module options mapping.

    The original CLI implementation in ``quickscale_cli.social_contract``
    also normalized the ``provider_allowlist`` and ``layout_variant`` keys.
    The full provider catalog and alias map are duplicated here so the
    central contract surface remains self-contained and free of any
    cross-module dependencies.
    """
    normalized = dict(options or {})

    if "provider_allowlist" in normalized:
        normalized["provider_allowlist"] = _normalize_social_provider_allowlist(
            normalized["provider_allowlist"]
        )

    if "layout_variant" in normalized:
        normalized["layout_variant"] = str(normalized["layout_variant"]).strip().lower()

    return normalized


# ---------------------------------------------------------------------------
# Social provider normalization helpers
# ---------------------------------------------------------------------------

_SOCIAL_PROVIDER_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"[^a-z0-9-]+")
_SOCIAL_MULTI_DASH_PATTERN: Final[re.Pattern[str]] = re.compile(r"-{2,}")


def _normalize_social_provider_token(value: Any) -> str:
    candidate = str(value).strip().lower().replace("&", "and")
    candidate = re.sub(r"[\s_/]+", "-", candidate)
    candidate = _SOCIAL_PROVIDER_TOKEN_PATTERN.sub("", candidate)
    return _SOCIAL_MULTI_DASH_PATTERN.sub("-", candidate).strip("-")


def _normalize_social_provider(value: Any) -> str | None:
    """Return the canonical provider name for a raw alias/token."""
    token = _normalize_social_provider_token(value)
    if not token:
        return None
    return _SOCIAL_PROVIDER_ALIASES.get(token)


def _coerce_social_allowlist_values(values: Any) -> list[Any]:
    if values is None:
        return []
    if isinstance(values, str):
        return [part for part in values.split(",")]
    if isinstance(values, list):
        return list(values)
    if isinstance(values, tuple):
        return list(values)
    return [values]


def _normalize_social_provider_allowlist(values: Any) -> list[str]:
    """Normalize a social provider allowlist while preserving first-seen order."""
    normalized: list[str] = []
    seen: set[str] = set()

    for value in _coerce_social_allowlist_values(values):
        canonical = _normalize_social_provider(value)
        candidate = canonical or _normalize_social_provider_token(value)
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)

    return normalized


# Social provider catalog (mirrors quickscale_cli.social_contract.SOCIAL_PROVIDER_CATALOG)
_SOCIAL_PROVIDER_ALIASES: Final[dict[str, str]] = {
    "facebook": "facebook",
    "fb": "facebook",
    "instagram": "instagram",
    "ig": "instagram",
    "linkedin": "linkedin",
    "linked-in": "linkedin",
    "tiktok": "tiktok",
    "tik-tok": "tiktok",
    "x": "x",
    "twitter": "x",
    "x-twitter": "x",
    "x-twitter-com": "x",
    "youtube": "youtube",
    "you-tube": "youtube",
}


# ---------------------------------------------------------------------------
# Validate functions
# ---------------------------------------------------------------------------


def validate_notifications_env_var_reference(
    option_name: str, value: Any
) -> str | None:
    """Validate a notifications env-var reference field."""
    candidate = str(value).strip()
    if not candidate:
        return None

    qualified_option = f"modules.notifications.{option_name}"
    if not _NOTIFICATIONS_ENV_VAR_NAME_PATTERN.fullmatch(candidate):
        return (
            f"{qualified_option} must be an environment variable name matching "
            "^[A-Z][A-Z0-9_]*$"
        )
    return None


def validate_notifications_module_options(
    options: Mapping[str, Any] | None,
) -> list[str]:
    """Return validation issues for notifications module options.

    The original CLI implementation performs extensive per-key validation; the
    schema layer handles its own per-key validation in
    ``config_schema._validate_*`` helpers. We expose a no-op stub here so
    consumers of the central contract surface see a stable symbol.
    """
    return []


def validate_storage_env_var_reference(option_name: str, value: Any) -> str | None:
    """Validate a storage env-var reference field.

    Returns an actionable error string when the value is not a safe environment
    variable name or appears to be a literal credential value.
    """
    candidate = str(value).strip()
    if not candidate:
        return None

    qualified_option = f"modules.storage.{option_name}"
    if not _BACKUPS_ENV_VAR_NAME_PATTERN.fullmatch(candidate):
        return (
            f"{qualified_option} must be an environment variable name matching "
            "^[A-Z][A-Z0-9_]*$"
        )

    if option_name == STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION:
        if _LIKELY_AWS_ACCESS_KEY_ID_PATTERN.fullmatch(candidate):
            return (
                f"{qualified_option} must reference an environment variable name, "
                "not a literal AWS access key id"
            )

    return None


def validate_social_module_options(options: dict[str, Any] | None) -> list[str]:
    """Return validation issues for the social module contract.

    The CLI implementation performs extensive per-key validation including
    allowlist checks; the schema layer handles per-key validation inline.
    This stub preserves the public surface for consumers.
    """
    return []


# ---------------------------------------------------------------------------
# DR env-var portability
# ---------------------------------------------------------------------------
#
# The classification below was lifted from
# ``quickscale_cli.commands.dr_commands`` and is now the single source of
# truth. The CLI keeps a thin wrapper that delegates to
# :func:`get_env_var_portability` so the existing call site and the
# existing reason strings stay byte-for-byte identical.


#: The category returned for an environment variable that is safe to copy
#: verbatim between source and target environments.
ENV_VAR_PORTABILITY_PORTABLE: Final[str] = "portable"
#: The category returned for an environment variable that must be set
#: manually on the target environment (provider-owned, target-owned, or
#: outside the conservative portable allowlist).
ENV_VAR_PORTABILITY_MANUAL: Final[str] = "manual"
#: The category returned for an environment variable that is shell or
#: runtime noise and must never be copied.
ENV_VAR_PORTABILITY_IGNORED: Final[str] = "ignored"


def _is_manual_only_restore_gate(normalized_name: str) -> bool:
    """Return whether a normalised env-var name is a destructive restore gate.

    The backups module exposes a small set of ``QUICKSCALE_BACKUPS_*_ALLOW_*``
    variables that gate destructive operations. The DR sync planner must
    always require the operator to set these manually on the target, even
    if the name otherwise looks portable, so a destructive flag cannot
    silently ride along with a routine env-var promotion.
    """
    return normalized_name == "QUICKSCALE_BACKUPS_ALLOW_RESTORE" or (
        normalized_name.startswith("QUICKSCALE_")
        and "ALLOW" in normalized_name
        and "RESTORE" in normalized_name
    )


def get_env_var_portability(name: str) -> tuple[str, str]:
    """Classify an environment variable name for DR env-var sync.

    The function returns a ``(category, reason)`` tuple where ``category``
    is one of :data:`ENV_VAR_PORTABILITY_PORTABLE`,
    :data:`ENV_VAR_PORTABILITY_MANUAL`, or
    :data:`ENV_VAR_PORTABILITY_IGNORED`. The ``reason`` is a short
    human-readable string intended to be surfaced in DR plan output.

    The classification is identical to the legacy inline implementation
    in ``quickscale_cli.commands.dr_commands`` so existing behaviour,
    including the exact reason strings, is preserved.
    """
    normalized = name.strip().upper()
    if not normalized:
        return ENV_VAR_PORTABILITY_IGNORED, "blank name"
    if normalized in IGNORED_ENV_EXACT:
        return ENV_VAR_PORTABILITY_IGNORED, "shell/runtime noise"
    if any(normalized.startswith(prefix) for prefix in IGNORED_ENV_PREFIXES):
        return ENV_VAR_PORTABILITY_IGNORED, "shell/runtime noise"
    if _is_manual_only_restore_gate(normalized):
        return (
            ENV_VAR_PORTABILITY_MANUAL,
            "destructive restore gate must be set manually",
        )
    if normalized in NON_PORTABLE_ENV_EXACT:
        return ENV_VAR_PORTABILITY_MANUAL, "provider-owned or target-owned variable"
    if any(normalized.startswith(prefix) for prefix in NON_PORTABLE_ENV_PREFIXES):
        return ENV_VAR_PORTABILITY_MANUAL, "provider-owned or target-owned variable"
    if any(token in normalized for token in NON_PORTABLE_ENV_CONTAINS):
        return (
            ENV_VAR_PORTABILITY_MANUAL,
            "sensitive or environment-specific variable",
        )
    if normalized in PORTABLE_ENV_EXACT:
        return ENV_VAR_PORTABILITY_PORTABLE, "portable variable"
    if any(normalized.startswith(prefix) for prefix in PORTABLE_ENV_PREFIXES):
        return ENV_VAR_PORTABILITY_PORTABLE, "portable variable"
    return (
        ENV_VAR_PORTABILITY_MANUAL,
        "outside the conservative portable allowlist",
    )


# ---------------------------------------------------------------------------
# Sanitize dispatcher
# ---------------------------------------------------------------------------


def sanitize_module_options(
    module_name: str,
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return module options safe for config/state persistence.

    This is the canonical module-name dispatcher previously located in
    ``quickscale_cli.backups_contract``. It routes to the per-module
    ``normalize_*_module_options`` helper above while one exists, otherwise to
    the manifest's declared normalization rules, and first refuses any key the
    module's manifest declares retired.
    """
    _raise_for_retired_module_options(module_name, options)

    if module_name == "notifications":
        return normalize_notifications_module_options(options)
    if module_name == "social":
        return normalize_social_module_options(dict(options or {}))
    if module_name == "storage":
        return normalize_storage_module_options(options)
    return _normalize_manifest_owned_options(module_name, options)


def _normalize_manifest_owned_options(
    module_name: str,
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Canonicalize a manifest-owned module's supplied option values.

    A module whose per-module option code is gone has no normalizer branch
    above; its manifest's declared normalization rules are the
    canonicalization, applied to the keys the caller supplied (defaults are
    not materialized here).  Undeclared keys pass through unchanged so the
    layer that refuses them can name them; an unknown module or an unreadable
    manifest keeps the supplied values.
    """
    supplied = dict(options or {})
    if not supplied:
        return supplied

    from quickscale_core.contracts.module_discovery import ImproperlyConfigured
    from quickscale_core.contracts.resolvers import (
        load_module_manifest_with_fallback,
    )
    from quickscale_core.manifest.loader import ManifestError
    from quickscale_core.manifest.resolver import normalize_module_option_values

    try:
        manifest = load_module_manifest_with_fallback(module_name)
    except ManifestError, ImproperlyConfigured, OSError:
        return supplied

    canonical = normalize_module_option_values(manifest, supplied)
    return {key: canonical.get(key, value) for key, value in supplied.items()}


def _raise_for_retired_module_options(
    module_name: str,
    options: Mapping[str, Any] | None,
) -> None:
    """Refuse every retired option key the module's manifest declares.

    The message is authored once in the module's ``module.yml``
    (``retired_options``); this dispatcher applies it wherever options are
    canonicalized for config or state persistence.  An undeclared module has
    no retirement declaration and passes through, keeping the layers that own
    unknown modules in charge; a shipped module whose manifest cannot be read
    fails closed rather than silently skipping its declaration.

    Raises:
        ConfigValidationError: naming the retired key and its removal.
        ManifestError: when a shipped module's manifest cannot be read.
    """
    if not options:
        return

    from quickscale_core.contracts.module_catalog import MODULE_CATALOG
    from quickscale_core.contracts.module_discovery import ImproperlyConfigured
    from quickscale_core.contracts.resolvers import (
        load_module_manifest_with_fallback,
    )
    from quickscale_core.manifest.loader import ManifestError
    from quickscale_core.schema.config_schema import ConfigValidationError

    try:
        manifest = load_module_manifest_with_fallback(module_name)
    except ManifestError, ImproperlyConfigured, OSError:
        # The static catalog names the shipped release inventory without
        # touching the filesystem, so this decision holds when a module's
        # directory or manifest is missing and in bundled-only installs.
        shipped_names = {entry.name for entry in MODULE_CATALOG}
        if module_name not in shipped_names:
            return
        raise

    for retired_name, message in sorted(manifest.retired_options.items()):
        if retired_name in options:
            raise ConfigValidationError(message)


__all__ = [
    # Analytics constants
    "ANALYTICS_EVENT_FORM_SUBMIT",
    "ANALYTICS_EVENT_PAGEVIEW",
    "ANALYTICS_EVENT_SOCIAL_LINK_CLICK",
    "ANALYTICS_POSTHOG_DEFAULT_HOST",
    "ANALYTICS_POSTHOG_EU_HOST",
    "ANALYTICS_PROVIDER_POSTHOG",
    "ANALYTICS_PROVIDERS",
    # Backups constants
    "BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION",
    "BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION",
    # Billing constants
    "BILLING_ENV_VAR_OPTION_NAMES",
    # DR env-var portability constants
    "ENV_VAR_PORTABILITY_IGNORED",
    "ENV_VAR_PORTABILITY_MANUAL",
    "ENV_VAR_PORTABILITY_PORTABLE",
    "IGNORED_ENV_EXACT",
    "IGNORED_ENV_PREFIXES",
    "NON_PORTABLE_ENV_CONTAINS",
    "NON_PORTABLE_ENV_EXACT",
    "NON_PORTABLE_ENV_PREFIXES",
    "PORTABLE_ENV_EXACT",
    "PORTABLE_ENV_PREFIXES",
    # DR env-var portability function
    "get_env_var_portability",
    # Notifications constants
    "DEFAULT_NOTIFICATIONS_ALLOWED_TAGS",
    "DEFAULT_NOTIFICATIONS_DEFAULT_TAGS",
    "DEFAULT_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR",
    "DEFAULT_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR",
    "NOTIFICATIONS_CONSOLE_EMAIL_BACKEND",
    "NOTIFICATIONS_LIVE_EMAIL_BACKEND",
    "NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION",
    "NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION",
    # Normalize functions
    "normalize_notifications_module_options",
    "normalize_social_module_options",
    # Validate functions
    "validate_notifications_env_var_reference",
    "validate_notifications_module_options",
    "validate_social_module_options",
    # Storage constants
    "DEFAULT_STORAGE_ACCESS_KEY_ID_ENV_VAR",
    "DEFAULT_STORAGE_BACKEND",
    "DEFAULT_STORAGE_MEDIA_URL",
    "DEFAULT_STORAGE_PRIVATE_MEDIA_ENABLED",
    "DEFAULT_STORAGE_PUBLIC_BASE_URL",
    "DEFAULT_STORAGE_SECRET_ACCESS_KEY_ENV_VAR",
    "STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION",
    "STORAGE_BACKEND_LOCAL",
    "STORAGE_BACKEND_R2",
    "STORAGE_BACKEND_S3",
    "STORAGE_BACKENDS",
    "STORAGE_MODULE_OPTION_KEYS",
    "STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION",
    # Social path constants
    "SOCIAL_EMBEDS_PATH",
    "SOCIAL_INTEGRATION_BASE_PATH",
    "SOCIAL_INTEGRATION_EMBEDS_PATH",
    "SOCIAL_LAYOUT_VARIANTS",
    "SOCIAL_LINK_TREE_PATH",
    # Sanitize dispatcher
    "sanitize_module_options",
    # Storage normalize/validate
    "normalize_storage_module_options",
    "validate_storage_env_var_reference",
]
