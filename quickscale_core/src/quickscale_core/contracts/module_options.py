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

DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR: Final[str] = "POSTHOG_API_KEY"
DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR: Final[str] = "POSTHOG_HOST"


# ---------------------------------------------------------------------------
# Constants: auth
# ---------------------------------------------------------------------------

AUTH_REGISTRATION_ENABLED_OPTION: Final[str] = "registration_enabled"
AUTH_EMAIL_VERIFICATION_OPTION: Final[str] = "email_verification"
AUTH_AUTHENTICATION_METHOD_OPTION: Final[str] = "authentication_method"
AUTH_SESSION_COOKIE_AGE_OPTION: Final[str] = "session_cookie_age"

AUTH_EMAIL_VERIFICATION_VALUES: Final[tuple[str, ...]] = (
    "none",
    "optional",
    "mandatory",
)
AUTH_AUTHENTICATION_METHOD_VALUES: Final[tuple[str, ...]] = (
    "email",
    "username",
    "both",
)
CANONICAL_AUTH_MODULE_OPTION_KEYS: Final[frozenset[str]] = frozenset(
    {
        AUTH_REGISTRATION_ENABLED_OPTION,
        AUTH_EMAIL_VERIFICATION_OPTION,
        AUTH_AUTHENTICATION_METHOD_OPTION,
        AUTH_SESSION_COOKIE_AGE_OPTION,
    }
)

LEGACY_AUTH_ALLOW_REGISTRATION_OPTION: Final[str] = "allow_registration"
LEGACY_AUTH_SOCIAL_PROVIDERS_OPTION: Final[str] = "social_providers"


# ---------------------------------------------------------------------------
# Constants: backups
# ---------------------------------------------------------------------------

DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR: Final[str] = (
    "QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID"
)
DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR: Final[str] = (
    "QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY"
)

BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION: Final[str] = "remote_access_key_id_env_var"
BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION: Final[str] = (
    "remote_secret_access_key_env_var"
)

_LEGACY_BACKUPS_SECRET_OPTIONS: Final[dict[str, str]] = {
    "remote_access_key_id": DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR,
    "remote_secret_access_key": DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR,
}


# ---------------------------------------------------------------------------
# Constants: billing
# ---------------------------------------------------------------------------

DEFAULT_BILLING_PUBLISHABLE_KEY_ENV_VAR: Final[str] = "STRIPE_PUBLISHABLE_KEY"
DEFAULT_BILLING_SECRET_KEY_ENV_VAR: Final[str] = "STRIPE_SECRET_KEY"
DEFAULT_BILLING_WEBHOOK_SECRET_ENV_VAR: Final[str] = "QUICKSCALE_BILLING_WEBHOOK_SECRET"
DEFAULT_BILLING_CURRENCY: Final[str] = "usd"

BILLING_ENV_VAR_OPTION_NAMES: Final[tuple[str, ...]] = (
    "publishable_key_env_var",
    "secret_key_env_var",
    "webhook_secret_env_var",
)
BILLING_MODULE_OPTION_KEYS: Final[frozenset[str]] = frozenset(
    {
        "enabled",
        *BILLING_ENV_VAR_OPTION_NAMES,
        "billing_currency",
    }
)
BILLING_SUPPORTED_CURRENCIES: Final[tuple[str, ...]] = (
    "aud",
    "brl",
    "cad",
    "chf",
    "czk",
    "dkk",
    "eur",
    "gbp",
    "hkd",
    "huf",
    "inr",
    "jpy",
    "mxn",
    "myr",
    "nok",
    "nzd",
    "php",
    "pln",
    "ron",
    "sek",
    "sgd",
    "thb",
    "try",
    "usd",
    "zar",
)


# ---------------------------------------------------------------------------
# Constants: notifications
# ---------------------------------------------------------------------------

DEFAULT_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR: Final[str] = "RESEND_API_KEY"
DEFAULT_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR: Final[str] = (
    "QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET"
)

NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION: Final[str] = "resend_api_key_env_var"
NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION: Final[str] = "webhook_secret_env_var"


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
# Constants: orgs
# ---------------------------------------------------------------------------

ORGS_MODE_SOLO: Final[str] = "solo"
ORGS_MODE_SAAS: Final[str] = "saas"
ORGS_MODES: Final[tuple[str, ...]] = (ORGS_MODE_SOLO, ORGS_MODE_SAAS)

DEFAULT_ORGS_MODE: Final[str] = "solo"

ORGS_MODULE_OPTION_KEYS: Final[frozenset[str]] = frozenset({"mode"})


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
DEFAULT_STORAGE_SECRET_ACCESS_KEY_ENV_VAR: Final[str] = "AWS_SECRET_ACCESS_KEY"

STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION: Final[str] = "access_key_id_env_var"
STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION: Final[str] = "secret_access_key_env_var"

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

_ANALYTICS_ENV_VAR_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[A-Z][A-Z0-9_]*$"
)
_BILLING_ENV_VAR_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Z][A-Z0-9_]*$")
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


def normalize_analytics_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return analytics options with normalized provider and host fields."""
    normalized = dict(options or {})

    if "provider" in normalized:
        provider = str(normalized["provider"]).strip().lower()
        normalized["provider"] = provider

    for option_name in ("posthog_api_key_env_var", "posthog_host_env_var"):
        if option_name in normalized:
            normalized[option_name] = str(normalized[option_name]).strip()

    if "posthog_host" in normalized:
        candidate = str(normalized["posthog_host"]).strip()
        if candidate and not candidate.startswith(("http://", "https://")):
            candidate = "https://" + candidate.lstrip("/")
        normalized["posthog_host"] = candidate.rstrip("/")

    return normalized


def normalize_auth_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return auth options with legacy keys raising instead of silent translation.

    Raises:
        ConfigValidationError: if any legacy key is present, naming the dead key
            and its replacement.
    """
    from quickscale_core.schema.config_schema import ConfigValidationError

    normalized = dict(options or {})

    if LEGACY_AUTH_ALLOW_REGISTRATION_OPTION in normalized:
        raise ConfigValidationError(
            f"Legacy config key '{LEGACY_AUTH_ALLOW_REGISTRATION_OPTION}' is "
            f"no longer supported. Use '{AUTH_REGISTRATION_ENABLED_OPTION}' instead."
        )

    if LEGACY_AUTH_SOCIAL_PROVIDERS_OPTION in normalized:
        raise ConfigValidationError(
            f"Legacy config key '{LEGACY_AUTH_SOCIAL_PROVIDERS_OPTION}' is "
            "no longer supported. Remove it from the auth module options."
        )

    return normalized


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


def normalize_billing_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return billing options with normalized env-var and currency values."""
    normalized = dict(options or {})

    for option_name in BILLING_ENV_VAR_OPTION_NAMES:
        if option_name in normalized:
            normalized[option_name] = str(normalized[option_name]).strip()

    if "billing_currency" in normalized:
        normalized["billing_currency"] = (
            str(normalized["billing_currency"]).strip().lower()
        )

    return normalized


def normalize_crm_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return CRM options with retired legacy keys raising instead of silent drop.

    Raises:
        ConfigValidationError: if a legacy key is present, naming the dead key.
    """
    from quickscale_core.schema.config_schema import ConfigValidationError

    normalized = dict(options or {})

    if "default_pipeline_stages" in normalized:
        raise ConfigValidationError(
            "Legacy config key 'default_pipeline_stages' is no longer supported. "
            "Remove it from the CRM module options."
        )

    return normalized


def normalize_notifications_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return notifications options with legacy raw-secret keys raising.

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


def validate_analytics_env_var_reference(option_name: str, value: Any) -> str | None:
    """Validate an analytics env-var reference field."""
    candidate = str(value).strip()
    if not candidate:
        return None

    qualified_option = f"modules.analytics.{option_name}"
    if not _ANALYTICS_ENV_VAR_NAME_PATTERN.fullmatch(candidate):
        return (
            f"{qualified_option} must be an environment variable name matching "
            "^[A-Z][A-Z0-9_]*$"
        )
    return None


def validate_analytics_module_options(options: Mapping[str, Any] | None) -> list[str]:
    """Return validation issues for analytics module options."""
    issues: list[str] = []

    if options is not None and "provider" in options:
        provider = str(options.get("provider", "")).strip().lower()
        if provider not in ANALYTICS_PROVIDERS:
            issues.append(
                "modules.analytics.provider must be one of: "
                + ", ".join(ANALYTICS_PROVIDERS)
            )

    for option_name in ("posthog_api_key_env_var", "posthog_host_env_var"):
        if options is None or option_name not in options:
            continue
        issue = validate_analytics_env_var_reference(
            option_name,
            options.get(option_name, ""),
        )
        if issue:
            issues.append(issue)

    return issues


def validate_auth_module_options(options: Mapping[str, Any] | None) -> list[str]:
    """Return validation issues for auth module options.

    The original CLI module did not expose a top-level
    ``validate_auth_module_options`` helper; schema-layer callers handle
    per-key validation directly. We provide a no-op stub here to satisfy the
    contract surface requested by Phase 0 — the schema layer still owns the
    full per-key validation in ``config_schema._validate_auth_module_options``.
    """
    return []


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


def validate_billing_currency(value: Any) -> str | None:
    """Validate the configured billing currency code."""
    candidate = str(value).strip().lower()
    if not candidate:
        return "modules.billing.billing_currency cannot be blank"

    if candidate not in BILLING_SUPPORTED_CURRENCIES:
        return (
            "modules.billing.billing_currency must be one of the supported "
            "QuickScale billing currency codes: "
            + ", ".join(BILLING_SUPPORTED_CURRENCIES)
        )
    return None


def validate_billing_env_var_reference(option_name: str, value: Any) -> str | None:
    """Validate a billing env-var reference field."""
    candidate = str(value).strip()
    if not candidate:
        return None

    qualified_option = f"modules.billing.{option_name}"
    if not _BILLING_ENV_VAR_NAME_PATTERN.fullmatch(candidate):
        return (
            f"{qualified_option} must be an environment variable name matching "
            "^[A-Z][A-Z0-9_]*$"
        )
    return None


def validate_billing_module_options(options: Mapping[str, Any] | None) -> list[str]:
    """Return validation issues for billing module options.

    The original CLI implementation resolves defaults and re-validates; the
    schema layer performs the same checks inline via
    ``_validate_billing_module_options``. We expose a no-op stub here so
    consumers of the central contract surface see a stable symbol.
    """
    return []


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
# Helpers
# ---------------------------------------------------------------------------


def has_legacy_backups_secret_values(options: Mapping[str, Any] | None) -> bool:
    """Return whether backups options still include legacy raw-secret keys."""
    if not options:
        return False

    for option_name in _LEGACY_BACKUPS_SECRET_OPTIONS:
        if str(options.get(option_name, "")).strip():
            return True
    return False


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
    ``normalize_*_module_options`` helper above.
    """
    if module_name == "analytics":
        return normalize_analytics_module_options(options)
    if module_name == "auth":
        return normalize_auth_module_options(options)
    if module_name == "backups":
        return normalize_backups_module_options(options)
    if module_name == "billing":
        return normalize_billing_module_options(options)
    if module_name == "crm":
        return normalize_crm_module_options(options)
    if module_name == "notifications":
        return normalize_notifications_module_options(options)
    if module_name == "social":
        return normalize_social_module_options(dict(options or {}))
    if module_name == "storage":
        return normalize_storage_module_options(options)
    return dict(options or {})


__all__ = [
    # Analytics constants
    "ANALYTICS_EVENT_FORM_SUBMIT",
    "ANALYTICS_EVENT_PAGEVIEW",
    "ANALYTICS_EVENT_SOCIAL_LINK_CLICK",
    "ANALYTICS_POSTHOG_DEFAULT_HOST",
    "ANALYTICS_POSTHOG_EU_HOST",
    "ANALYTICS_PROVIDER_POSTHOG",
    "ANALYTICS_PROVIDERS",
    "DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR",
    "DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR",
    # Auth constants
    "AUTH_AUTHENTICATION_METHOD_OPTION",
    "AUTH_AUTHENTICATION_METHOD_VALUES",
    "AUTH_EMAIL_VERIFICATION_OPTION",
    "AUTH_EMAIL_VERIFICATION_VALUES",
    "AUTH_REGISTRATION_ENABLED_OPTION",
    "AUTH_SESSION_COOKIE_AGE_OPTION",
    "CANONICAL_AUTH_MODULE_OPTION_KEYS",
    "LEGACY_AUTH_ALLOW_REGISTRATION_OPTION",
    "LEGACY_AUTH_SOCIAL_PROVIDERS_OPTION",
    # Backups constants
    "BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION",
    "BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION",
    "DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR",
    "DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR",
    # Billing constants
    "BILLING_ENV_VAR_OPTION_NAMES",
    "BILLING_MODULE_OPTION_KEYS",
    "BILLING_SUPPORTED_CURRENCIES",
    "DEFAULT_BILLING_CURRENCY",
    "DEFAULT_BILLING_PUBLISHABLE_KEY_ENV_VAR",
    "DEFAULT_BILLING_SECRET_KEY_ENV_VAR",
    "DEFAULT_BILLING_WEBHOOK_SECRET_ENV_VAR",
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
    "normalize_analytics_module_options",
    "normalize_auth_module_options",
    "normalize_backups_module_options",
    "normalize_billing_module_options",
    "normalize_crm_module_options",
    "normalize_notifications_module_options",
    "normalize_social_module_options",
    # Validate functions
    "validate_analytics_env_var_reference",
    "validate_analytics_module_options",
    "validate_auth_module_options",
    "validate_backups_env_var_reference",
    "validate_billing_currency",
    "validate_billing_env_var_reference",
    "validate_billing_module_options",
    "validate_notifications_env_var_reference",
    "validate_notifications_module_options",
    "validate_social_module_options",
    # Orgs constants
    "DEFAULT_ORGS_MODE",
    "ORGS_MODE_SAAS",
    "ORGS_MODE_SOLO",
    "ORGS_MODES",
    "ORGS_MODULE_OPTION_KEYS",
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
    # Helpers
    "format_auth_desired_config_contract",
    "has_legacy_backups_secret_values",
    # Sanitize dispatcher
    "sanitize_module_options",
    # Storage normalize/validate
    "normalize_storage_module_options",
    "validate_storage_env_var_reference",
]
