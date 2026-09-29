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

from quickscale_core.contracts.imperative_inventory import (
    ADAPTER_ONLY,
    ADAPTER_ONLY_SYMBOLS,
    AUTHORIZED_IMPERATIVE_MODULES,
    DECLARATIVE_TARGET,
    DECLARATIVE_TARGET_SYMBOLS,
    MANIFEST_INVENTORY,
    MANIFEST_RESOLVER,
    MANIFEST_RESOLVER_SYMBOLS,
    SHARED_HELPER,
    SHARED_HELPER_SYMBOLS,
    count_inventory_category,
    get_manifest_inventory,
)
from quickscale_core.contracts.module_catalog import (
    MODULE_CATALOG,
    ModuleCatalogEntry,
    find_not_ready_modules,
    get_discovered_module_entries,
    get_discovered_module_names,
    get_module_entry,
    get_module_readiness_reason,
)
from quickscale_core.contracts.module_discovery import (
    AUTHORITATIVE_MODULE_COUNT,
    ModulePresenceRecord,
    ModulePresenceState,
    authoritative_module_names,
    discover_module_presence,
    discover_shipped_module_names,
    discover_shipped_module_paths,
    validate_active_module_subset,
)
from quickscale_core.contracts.module_options import (
    ANALYTICS_PROVIDER_POSTHOG,
    ANALYTICS_PROVIDERS,
    BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION,
    BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
    BILLING_ENV_VAR_OPTION_NAMES,
    ENV_VAR_PORTABILITY_IGNORED,
    ENV_VAR_PORTABILITY_MANUAL,
    ENV_VAR_PORTABILITY_PORTABLE,
    IGNORED_ENV_EXACT,
    IGNORED_ENV_PREFIXES,
    NON_PORTABLE_ENV_CONTAINS,
    NON_PORTABLE_ENV_EXACT,
    NON_PORTABLE_ENV_PREFIXES,
    NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION,
    NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION,
    PORTABLE_ENV_EXACT,
    STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION,
    STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
    PORTABLE_ENV_PREFIXES,
    get_env_var_portability,
    sanitize_module_options,
)

__all__ = [
    # Module catalog
    "MODULE_CATALOG",
    "ModuleCatalogEntry",
    "find_not_ready_modules",
    "get_discovered_module_entries",
    "get_discovered_module_names",
    "get_module_entry",
    "get_module_readiness_reason",
    # Module discovery
    "AUTHORITATIVE_MODULE_COUNT",
    "ModulePresenceRecord",
    "ModulePresenceState",
    "authoritative_module_names",
    "discover_module_presence",
    "discover_shipped_module_names",
    "discover_shipped_module_paths",
    "validate_active_module_subset",
    # Imperative-logic inventory
    "ADAPTER_ONLY",
    "ADAPTER_ONLY_SYMBOLS",
    "AUTHORIZED_IMPERATIVE_MODULES",
    "DECLARATIVE_TARGET",
    "DECLARATIVE_TARGET_SYMBOLS",
    "MANIFEST_INVENTORY",
    "MANIFEST_RESOLVER",
    "MANIFEST_RESOLVER_SYMBOLS",
    "SHARED_HELPER",
    "SHARED_HELPER_SYMBOLS",
    "count_inventory_category",
    "get_manifest_inventory",
    # Analytics constants
    "ANALYTICS_PROVIDERS",
    "ANALYTICS_PROVIDER_POSTHOG",
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
    # Storage option-name constants
    "STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION",
    "STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION",
    # Sanitize dispatcher
    "sanitize_module_options",
]
