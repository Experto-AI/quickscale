"""Shared contract surface owned by ``quickscale_core``.

This subpackage is the canonical home for the module catalog and module
options normalization/validation helpers that the schema layer needs to
import. Owning these symbols in ``quickscale_core`` keeps the schema
files (and the future ``quickscale_core/schema/`` package) free of any
dependency on the CLI package.

Phase 0 of the QuickScale Phase 3 architecture improvements relocates the
``sanitize_module_options`` dispatcher, all ``normalize_*_module_options``
helpers, and the module catalog here. The CLI keeps backward-compatible
shims at its original import locations.
"""

from quickscale_core.contracts.module_catalog import (
    MODULE_CATALOG,
    ModuleCatalogEntry,
    find_not_ready_modules,
    get_module_entries,
    get_module_entry,
    get_module_names,
    get_module_readiness_reason,
)
from quickscale_core.contracts.module_options import (
    ANALYTICS_PROVIDERS,
    ANALYTICS_PROVIDER_POSTHOG,
    AUTH_AUTHENTICATION_METHOD_OPTION,
    AUTH_AUTHENTICATION_METHOD_VALUES,
    AUTH_EMAIL_VERIFICATION_OPTION,
    AUTH_EMAIL_VERIFICATION_VALUES,
    AUTH_REGISTRATION_ENABLED_OPTION,
    AUTH_SESSION_COOKIE_AGE_OPTION,
    BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION,
    BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
    BILLING_ENV_VAR_OPTION_NAMES,
    BILLING_MODULE_OPTION_KEYS,
    BILLING_SUPPORTED_CURRENCIES,
    CANONICAL_AUTH_MODULE_OPTION_KEYS,
    DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR,
    DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR,
    DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR,
    DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR,
    DEFAULT_BILLING_CURRENCY,
    DEFAULT_BILLING_PUBLISHABLE_KEY_ENV_VAR,
    DEFAULT_BILLING_SECRET_KEY_ENV_VAR,
    DEFAULT_BILLING_WEBHOOK_SECRET_ENV_VAR,
    DEFAULT_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR,
    DEFAULT_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR,
    ENV_VAR_PORTABILITY_IGNORED,
    ENV_VAR_PORTABILITY_MANUAL,
    ENV_VAR_PORTABILITY_PORTABLE,
    IGNORED_ENV_EXACT,
    IGNORED_ENV_PREFIXES,
    LEGACY_AUTH_ALLOW_REGISTRATION_OPTION,
    LEGACY_AUTH_SOCIAL_PROVIDERS_OPTION,
    NON_PORTABLE_ENV_CONTAINS,
    NON_PORTABLE_ENV_EXACT,
    NON_PORTABLE_ENV_PREFIXES,
    NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION,
    NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION,
    PORTABLE_ENV_EXACT,
    PORTABLE_ENV_PREFIXES,
    format_auth_desired_config_contract,
    get_env_var_portability,
    has_legacy_backups_secret_values,
    normalize_analytics_module_options,
    normalize_auth_module_options,
    normalize_backups_module_options,
    normalize_billing_module_options,
    normalize_crm_module_options,
    normalize_notifications_module_options,
    normalize_social_module_options,
    sanitize_module_options,
    validate_analytics_env_var_reference,
    validate_analytics_module_options,
    validate_auth_module_options,
    validate_backups_env_var_reference,
    validate_billing_currency,
    validate_billing_env_var_reference,
    validate_billing_module_options,
    validate_notifications_env_var_reference,
    validate_notifications_module_options,
    validate_social_module_options,
)

__all__ = [
    # Module catalog
    "MODULE_CATALOG",
    "ModuleCatalogEntry",
    "find_not_ready_modules",
    "get_module_entries",
    "get_module_entry",
    "get_module_names",
    "get_module_readiness_reason",
    # Analytics constants
    "ANALYTICS_PROVIDERS",
    "ANALYTICS_PROVIDER_POSTHOG",
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
    "DEFAULT_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR",
    "DEFAULT_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR",
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
    # Helpers
    "format_auth_desired_config_contract",
    "has_legacy_backups_secret_values",
    # Sanitize dispatcher
    "sanitize_module_options",
]
