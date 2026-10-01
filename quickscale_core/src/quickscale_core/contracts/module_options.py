"""Shared module options normalization and contract surface.

Owns the module-name dispatcher ``sanitize_module_options`` — which refuses a
manifest's retired keys and applies the manifest's declared normalization — and
the DR env-var portability classification.  Per-module option defaults,
normalization, and validation live in each module's ``module.yml``; SA217
removed the last per-module option normalizers and validators from this surface.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final


# ---------------------------------------------------------------------------
# Constants: analytics
# ---------------------------------------------------------------------------

ANALYTICS_PROVIDER_POSTHOG: Final[str] = "posthog"
ANALYTICS_PROVIDERS: Final[tuple[str, ...]] = (ANALYTICS_PROVIDER_POSTHOG,)

ANALYTICS_POSTHOG_DEFAULT_HOST: Final[str] = "https://us.i.posthog.com"
ANALYTICS_POSTHOG_EU_HOST: Final[str] = "https://eu.i.posthog.com"

ANALYTICS_EVENT_PAGEVIEW: Final[str] = "$pageview"


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
# Constants: notifications (option names)
# ---------------------------------------------------------------------------

NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION: Final[str] = "resend_api_key_env_var"
NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION: Final[str] = "webhook_secret_env_var"  # noqa: S105 - environment-variable name constant, not a credential


# ---------------------------------------------------------------------------
# Constants: storage (option names)
# ---------------------------------------------------------------------------

STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION: Final[str] = "access_key_id_env_var"
STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION: Final[str] = "secret_access_key_env_var"  # noqa: S105 - environment-variable name constant, not a credential


# ---------------------------------------------------------------------------
# Constants: social (paths)
# ---------------------------------------------------------------------------

SOCIAL_LINK_TREE_PATH: Final[str] = "/social"
SOCIAL_EMBEDS_PATH: Final[str] = "/social/embeds"
SOCIAL_INTEGRATION_BASE_PATH: Final[str] = "/_quickscale/social/"
SOCIAL_INTEGRATION_EMBEDS_PATH: Final[str] = "/_quickscale/social/embeds/"


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
    ``quickscale_cli.backups_contract``.  It first refuses any key the module's
    manifest declares retired, then applies the manifest's declared
    normalization rules to the keys the caller supplied.
    """
    _raise_for_retired_module_options(module_name, options)
    return _normalize_manifest_owned_options(module_name, options)


def _normalize_manifest_owned_options(
    module_name: str,
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Canonicalize a manifest-owned module's supplied option values.

    A module whose per-module option code is gone has no normalizer branch;
    its manifest's declared normalization rules are the canonicalization,
    applied to the keys the caller supplied (defaults are not materialized
    here).  Undeclared keys pass through unchanged so the layer that refuses
    them can name them; an unknown module or an unreadable manifest keeps the
    supplied values.
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
    "ANALYTICS_EVENT_PAGEVIEW",
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
    # Notifications option-name constants
    "NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION",
    "NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION",
    # Social path constants
    "SOCIAL_EMBEDS_PATH",
    "SOCIAL_INTEGRATION_BASE_PATH",
    "SOCIAL_INTEGRATION_EMBEDS_PATH",
    "SOCIAL_LINK_TREE_PATH",
    # Storage option-name constants
    "STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION",
    "STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION",
    # Sanitize dispatcher
    "sanitize_module_options",
]
