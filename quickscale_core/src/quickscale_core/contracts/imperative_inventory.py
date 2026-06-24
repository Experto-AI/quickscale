"""Imperative-logic inventory and ownership matrix for CLI contract files.

This module catalogs every public symbol exported by the per-module
``*_manifest.py`` files in ``quickscale_cli`` and classifies them by
ownership category.  Later phases (Track 2 Phase 3+) use this inventory
to decide which symbols can be deleted when the corresponding manifest
adapter is migrated to the declarative path.

Ownership categories
--------------------
- ``declarative_target``
    Constant/data definitions that belong in the module's ``module.yml``
    manifest (e.g. default option values, supported-choices lists).  They
    are **declarative targets** because they should eventually live in
    YAML data rather than imperative Python.

- ``shared_helper``
    Symbols that have **already been relocated** to
    ``quickscale_core/contracts/module_options.py`` or an adjacent
    contract surface.  The CLI manifest file keeps a thin re-export or
    backward-compatible shim.

- ``manifest_resolver``
    Runtime helpers that build derivation schemas, load manifests, or
    wire resolvers.  These belong under ``quickscale_core.manifest``.

- ``adapter_only``
    Functions tightly coupled to the CLI adapter pattern (e.g. interactive
    configuration prompts, settings-file generation).  These will be
    deleted along with the adapter file in a later phase — no migration
    needed.

Every entry in the per-module inventories is a tuple of
``(symbol_name, ownership_category, migration_phase)`` where
*migration_phase* is the Track 2 phase that should address it
(``"T2.3"``, ``"T2.4"``, ``"T2.5"``, or ``"deferred"``).
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Ownership categories (string literals for readability)
# ---------------------------------------------------------------------------

DECLARATIVE_TARGET: Final[str] = "declarative_target"
SHARED_HELPER: Final[str] = "shared_helper"
MANIFEST_RESOLVER: Final[str] = "manifest_resolver"
ADAPTER_ONLY: Final[str] = "adapter_only"

# ---------------------------------------------------------------------------
# Per-module inventories
#
# Each module entry is a list of (symbol_name, category, phase) tuples.
# Symbols that are already migrated (shared_helper) reference the
# canonical location in a comment.
# ---------------------------------------------------------------------------

ANALYTICS_MANIFEST: Final[list[tuple[str, str, str]]] = [
    # Declarative targets — should move to module.yml derivation section
    ("ANALYTICS_PROVIDER_POSTHOG", DECLARATIVE_TARGET, "T2.4"),
    ("ANALYTICS_PROVIDERS", DECLARATIVE_TARGET, "T2.4"),
    ("DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR", DECLARATIVE_TARGET, "T2.4"),
    ("DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR", DECLARATIVE_TARGET, "T2.4"),
    ("ANALYTICS_POSTHOG_DEFAULT_HOST", DECLARATIVE_TARGET, "T2.4"),
    # Adapter-only — configuration+resolution surface
    ("default_analytics_module_options", ADAPTER_ONLY, "T2.5"),
    ("resolve_analytics_module_options", ADAPTER_ONLY, "T2.5"),
    ("validate_analytics_module_options", ADAPTER_ONLY, "T2.5"),
]

AUTH_MANIFEST: Final[list[tuple[str, str, str]]] = [
    # Shared helpers — relocated to quickscale_core.contracts.module_options
    ("AUTH_REGISTRATION_ENABLED_OPTION", SHARED_HELPER, "T2.3"),
    ("AUTH_EMAIL_VERIFICATION_OPTION", SHARED_HELPER, "T2.3"),
    ("AUTH_AUTHENTICATION_METHOD_OPTION", SHARED_HELPER, "T2.3"),
    ("AUTH_SESSION_COOKIE_AGE_OPTION", SHARED_HELPER, "T2.3"),
    ("AUTH_EMAIL_VERIFICATION_VALUES", SHARED_HELPER, "T2.3"),
    ("AUTH_AUTHENTICATION_METHOD_VALUES", SHARED_HELPER, "T2.3"),
    ("CANONICAL_AUTH_MODULE_OPTION_KEYS", SHARED_HELPER, "T2.3"),
    ("LEGACY_AUTH_ALLOW_REGISTRATION_OPTION", SHARED_HELPER, "T2.3"),
    ("LEGACY_AUTH_SOCIAL_PROVIDERS_OPTION", SHARED_HELPER, "T2.3"),
    ("normalize_auth_module_options", SHARED_HELPER, "T2.3"),
    ("validate_auth_module_options", SHARED_HELPER, "T2.3"),
    ("format_auth_desired_config_contract", SHARED_HELPER, "T2.3"),
    # Declarative targets
    ("DEFAULT_AUTH_SESSION_COOKIE_AGE", DECLARATIVE_TARGET, "T2.4"),
    # Adapter-only
    ("default_auth_module_options", ADAPTER_ONLY, "T2.5"),
    ("resolve_auth_module_options", ADAPTER_ONLY, "T2.5"),
]

BACKUPS_MANIFEST: Final[list[tuple[str, str, str]]] = [
    # Shared helpers — relocated to quickscale_core.contracts.module_options
    ("DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR", SHARED_HELPER, "T2.3"),
    ("DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR", SHARED_HELPER, "T2.3"),
    ("BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION", SHARED_HELPER, "T2.3"),
    ("BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION", SHARED_HELPER, "T2.3"),
    ("normalize_backups_module_options", SHARED_HELPER, "T2.3"),
    ("validate_backups_env_var_reference", SHARED_HELPER, "T2.3"),
    # Declarative targets
    ("BACKUPS_DEFAULT_RETENTION_DAYS", DECLARATIVE_TARGET, "T2.4"),
    ("BACKUPS_DEFAULT_NAMING_PREFIX", DECLARATIVE_TARGET, "T2.4"),
    ("BACKUPS_TARGET_MODES", DECLARATIVE_TARGET, "T2.4"),
    # Manifest resolver
    ("_build_backups_derivation_schema", MANIFEST_RESOLVER, "T2.4"),
    # Adapter-only
    ("default_backups_module_options", ADAPTER_ONLY, "T2.5"),
]

BILLING_MANIFEST: Final[list[tuple[str, str, str]]] = [
    # Shared helpers — relocated to quickscale_core.contracts.module_options
    ("DEFAULT_BILLING_PUBLISHABLE_KEY_ENV_VAR", SHARED_HELPER, "T2.3"),
    ("DEFAULT_BILLING_SECRET_KEY_ENV_VAR", SHARED_HELPER, "T2.3"),
    ("DEFAULT_BILLING_WEBHOOK_SECRET_ENV_VAR", SHARED_HELPER, "T2.3"),
    ("DEFAULT_BILLING_CURRENCY", SHARED_HELPER, "T2.3"),
    ("BILLING_ENV_VAR_OPTION_NAMES", SHARED_HELPER, "T2.3"),
    ("BILLING_MODULE_OPTION_KEYS", SHARED_HELPER, "T2.3"),
    ("BILLING_SUPPORTED_CURRENCIES", SHARED_HELPER, "T2.3"),
    ("normalize_billing_module_options", SHARED_HELPER, "T2.3"),
    ("validate_billing_env_var_reference", SHARED_HELPER, "T2.3"),
    ("validate_billing_currency", SHARED_HELPER, "T2.3"),
    ("validate_billing_module_options", SHARED_HELPER, "T2.3"),
    # Manifest resolver
    ("_build_billing_derivation_schema", MANIFEST_RESOLVER, "T2.4"),
    # Adapter-only
    ("default_billing_module_options", ADAPTER_ONLY, "T2.5"),
    ("resolve_billing_module_options", ADAPTER_ONLY, "T2.5"),
    ("billing_production_targeted", ADAPTER_ONLY, "T2.5"),
]

BLOG_MANIFEST: Final[list[tuple[str, str, str]]] = [
    # Declarative targets
    ("DEFAULT_BLOG_POSTS_PER_PAGE", DECLARATIVE_TARGET, "T2.4"),
    ("DEFAULT_BLOG_ENABLE_RSS", DECLARATIVE_TARGET, "T2.4"),
    ("DEFAULT_BLOG_API_RATE_LIMIT", DECLARATIVE_TARGET, "T2.4"),
    ("DEFAULT_BLOG_ORG_ROUTING_ENABLED", DECLARATIVE_TARGET, "T2.4"),
    ("BLOG_MODULE_OPTION_KEYS", DECLARATIVE_TARGET, "T2.4"),
    # Manifest resolver
    ("_build_blog_derivation_schema", MANIFEST_RESOLVER, "T2.4"),
    # Adapter-only
    ("default_blog_module_options", ADAPTER_ONLY, "T2.5"),
    ("normalize_blog_module_options", ADAPTER_ONLY, "T2.5"),
    ("resolve_blog_module_options", ADAPTER_ONLY, "T2.5"),
    ("validate_blog_module_options", ADAPTER_ONLY, "T2.5"),
]

CRM_MANIFEST: Final[list[tuple[str, str, str]]] = [
    # Shared helpers — relocated to quickscale_core.contracts.module_options
    ("normalize_crm_module_options", SHARED_HELPER, "T2.3"),
    # Declarative targets
    ("LEGACY_CRM_DEFAULT_PIPELINE_STAGES_OPTION", DECLARATIVE_TARGET, "T2.4"),
    ("DEFAULT_CRM_DEALS_PER_PAGE", DECLARATIVE_TARGET, "T2.4"),
    ("DEFAULT_CRM_CONTACTS_PER_PAGE", DECLARATIVE_TARGET, "T2.4"),
    ("CRM_MODULE_OPTION_KEYS", DECLARATIVE_TARGET, "T2.4"),
    # Manifest resolver
    ("_build_crm_derivation_schema", MANIFEST_RESOLVER, "T2.4"),
    # Adapter-only
    ("default_crm_module_options", ADAPTER_ONLY, "T2.5"),
    ("resolve_crm_module_options", ADAPTER_ONLY, "T2.5"),
    ("validate_crm_module_options", ADAPTER_ONLY, "T2.5"),
]

FORMS_MANIFEST: Final[list[tuple[str, str, str]]] = [
    # Declarative targets
    ("DEFAULT_FORMS_PER_PAGE", DECLARATIVE_TARGET, "T2.4"),
    ("DEFAULT_FORMS_SPAM_PROTECTION_ENABLED", DECLARATIVE_TARGET, "T2.4"),
    ("DEFAULT_FORMS_RATE_LIMIT", DECLARATIVE_TARGET, "T2.4"),
    ("DEFAULT_FORMS_DATA_RETENTION_DAYS", DECLARATIVE_TARGET, "T2.4"),
    ("DEFAULT_FORMS_SUBMISSIONS_API_ENABLED", DECLARATIVE_TARGET, "T2.4"),
    ("FORMS_MODULE_OPTION_KEYS", DECLARATIVE_TARGET, "T2.4"),
    # Manifest resolver
    ("_build_forms_derivation_schema", MANIFEST_RESOLVER, "T2.4"),
    # Adapter-only
    ("default_forms_module_options", ADAPTER_ONLY, "T2.5"),
    ("normalize_forms_module_options", ADAPTER_ONLY, "T2.5"),
    ("resolve_forms_module_options", ADAPTER_ONLY, "T2.5"),
    ("validate_forms_module_options", ADAPTER_ONLY, "T2.5"),
]

LISTINGS_MANIFEST: Final[list[tuple[str, str, str]]] = [
    # Declarative targets
    ("DEFAULT_LISTINGS_PER_PAGE", DECLARATIVE_TARGET, "T2.4"),
    ("LISTINGS_MODULE_OPTION_KEYS", DECLARATIVE_TARGET, "T2.4"),
    # Manifest resolver
    ("_build_listings_derivation_schema", MANIFEST_RESOLVER, "T2.4"),
    # Adapter-only
    ("default_listings_module_options", ADAPTER_ONLY, "T2.5"),
    ("normalize_listings_module_options", ADAPTER_ONLY, "T2.5"),
    ("resolve_listings_module_options", ADAPTER_ONLY, "T2.5"),
    ("validate_listings_module_options", ADAPTER_ONLY, "T2.5"),
]

NOTIFICATIONS_MANIFEST: Final[list[tuple[str, str, str]]] = [
    # Shared helpers — relocated to quickscale_core.contracts.module_options
    ("DEFAULT_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR", SHARED_HELPER, "T2.3"),
    ("DEFAULT_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR", SHARED_HELPER, "T2.3"),
    ("NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION", SHARED_HELPER, "T2.3"),
    ("NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION", SHARED_HELPER, "T2.3"),
    ("normalize_notifications_module_options", SHARED_HELPER, "T2.3"),
    ("validate_notifications_module_options", SHARED_HELPER, "T2.3"),
    ("validate_notifications_env_var_reference", SHARED_HELPER, "T2.3"),
    # Declarative targets
    ("DEFAULT_NOTIFICATIONS_ALLOWED_TAGS", DECLARATIVE_TARGET, "T2.4"),
    ("NOTIFICATIONS_DEFAULT_TAGS", DECLARATIVE_TARGET, "T2.4"),
    ("NOTIFICATIONS_LIVE_EMAIL_BACKEND", DECLARATIVE_TARGET, "T2.4"),
    # Manifest resolver
    ("_build_notifications_derivation_schema", MANIFEST_RESOLVER, "T2.4"),
    # Adapter-only
    ("default_notifications_module_options", ADAPTER_ONLY, "T2.5"),
    ("resolve_notifications_module_options", ADAPTER_ONLY, "T2.5"),
    ("notifications_runtime_email_backend", ADAPTER_ONLY, "T2.5"),
    ("notifications_production_targeted", ADAPTER_ONLY, "T2.5"),
]

ORGS_MANIFEST: Final[list[tuple[str, str, str]]] = [
    # Declarative targets
    ("DEFAULT_ORGS_MODE", DECLARATIVE_TARGET, "T2.4"),
    ("ORGS_MODULE_OPTION_KEYS", DECLARATIVE_TARGET, "T2.4"),
    # Manifest resolver
    ("_build_orgs_derivation_schema", MANIFEST_RESOLVER, "T2.4"),
    # Adapter-only
    ("default_orgs_module_options", ADAPTER_ONLY, "T2.5"),
    ("resolve_orgs_module_options", ADAPTER_ONLY, "T2.5"),
    ("validate_orgs_module_options", ADAPTER_ONLY, "T2.5"),
]

SOCIAL_MANIFEST: Final[list[tuple[str, str, str]]] = [
    # Declarative targets
    ("SOCIAL_LINK_TREE_PATH", DECLARATIVE_TARGET, "T2.4"),
    ("SOCIAL_EMBEDS_PATH", DECLARATIVE_TARGET, "T2.4"),
    ("SOCIAL_INTEGRATION_BASE_PATH", DECLARATIVE_TARGET, "T2.4"),
    ("SOCIAL_INTEGRATION_EMBEDS_PATH", DECLARATIVE_TARGET, "T2.4"),
    ("SOCIAL_LAYOUT_VARIANTS", DECLARATIVE_TARGET, "T2.4"),
    ("SOCIAL_STATUS_ENABLED", DECLARATIVE_TARGET, "T2.4"),
    ("SOCIAL_STATUS_EMPTY", DECLARATIVE_TARGET, "T2.4"),
    ("SOCIAL_STATUS_DISABLED", DECLARATIVE_TARGET, "T2.4"),
    ("SOCIAL_STATUS_ERROR", DECLARATIVE_TARGET, "T2.4"),
    ("SOCIAL_PAYLOAD_STATUSES", DECLARATIVE_TARGET, "T2.4"),
    ("SOCIAL_PAYLOAD_HTTP_STATUS", DECLARATIVE_TARGET, "T2.4"),
    ("DEFAULT_SOCIAL_PROVIDER_ALLOWLIST", DECLARATIVE_TARGET, "T2.4"),
    ("DEFAULT_SOCIAL_EMBED_PROVIDER_ALLOWLIST", DECLARATIVE_TARGET, "T2.4"),
    # Manifest resolver
    ("_build_social_derivation_schema", MANIFEST_RESOLVER, "T2.4"),
    ("load_social_manifest", MANIFEST_RESOLVER, "T2.4"),
    # Shared helpers — relocated to quickscale_core.contracts.module_options
    ("normalize_social_module_options", SHARED_HELPER, "T2.3"),
    ("validate_social_module_options", SHARED_HELPER, "T2.3"),
    # Adapter-only
    ("default_social_module_options", ADAPTER_ONLY, "T2.5"),
    ("resolve_social_module_options", ADAPTER_ONLY, "T2.5"),
    # Social domain logic — tightly coupled, stays in CLI until deletion
    ("SocialProviderMetadata", ADAPTER_ONLY, "T2.5"),
    ("ResolvedSocialTarget", ADAPTER_ONLY, "T2.5"),
    ("get_social_provider_metadata", ADAPTER_ONLY, "T2.5"),
    ("social_provider_supports_embeds", ADAPTER_ONLY, "T2.5"),
    ("social_payload_status_code", ADAPTER_ONLY, "T2.5"),
    ("normalize_social_provider_allowlist", ADAPTER_ONLY, "T2.5"),
    ("normalize_social_provider", ADAPTER_ONLY, "T2.5"),
    ("detect_social_provider", ADAPTER_ONLY, "T2.5"),
    ("resolve_social_target", ADAPTER_ONLY, "T2.5"),
    ("normalize_social_url", ADAPTER_ONLY, "T2.5"),
    # Renderers — tightly coupled to adapter
    ("render_social_managed_init_module", ADAPTER_ONLY, "T2.5"),
    ("render_social_managed_urls_module", ADAPTER_ONLY, "T2.5"),
    ("render_social_managed_views_module", ADAPTER_ONLY, "T2.5"),
]

STORAGE_MANIFEST: Final[list[tuple[str, str, str]]] = [
    # Declarative targets
    ("STORAGE_BACKEND_LOCAL", DECLARATIVE_TARGET, "T2.4"),
    ("STORAGE_BACKEND_S3", DECLARATIVE_TARGET, "T2.4"),
    ("STORAGE_BACKEND_R2", DECLARATIVE_TARGET, "T2.4"),
    ("STORAGE_BACKENDS", DECLARATIVE_TARGET, "T2.4"),
    ("DEFAULT_STORAGE_BACKEND", DECLARATIVE_TARGET, "T2.4"),
    ("DEFAULT_STORAGE_MEDIA_URL", DECLARATIVE_TARGET, "T2.4"),
    ("DEFAULT_STORAGE_PUBLIC_BASE_URL", DECLARATIVE_TARGET, "T2.4"),
    ("DEFAULT_STORAGE_PRIVATE_MEDIA_ENABLED", DECLARATIVE_TARGET, "T2.4"),
    ("STORAGE_MODULE_OPTION_KEYS", DECLARATIVE_TARGET, "T2.4"),
    # Manifest resolver
    ("_build_storage_derivation_schema", MANIFEST_RESOLVER, "T2.4"),
    # Adapter-only
    ("default_storage_module_options", ADAPTER_ONLY, "T2.5"),
    ("resolve_storage_module_options", ADAPTER_ONLY, "T2.5"),
]

# ---------------------------------------------------------------------------
# Combined inventory
# ---------------------------------------------------------------------------

#: Mapping from module name to its symbol inventory list.
#: Each value is a list of ``(symbol_name, category, phase)`` tuples.
MANIFEST_INVENTORY: Final[dict[str, list[tuple[str, str, str]]]] = {
    "analytics": ANALYTICS_MANIFEST,
    "auth": AUTH_MANIFEST,
    "backups": BACKUPS_MANIFEST,
    "billing": BILLING_MANIFEST,
    "blog": BLOG_MANIFEST,
    "crm": CRM_MANIFEST,
    "forms": FORMS_MANIFEST,
    "listings": LISTINGS_MANIFEST,
    "notifications": NOTIFICATIONS_MANIFEST,
    "orgs": ORGS_MANIFEST,
    "social": SOCIAL_MANIFEST,
    "storage": STORAGE_MANIFEST,
}

#: Set of all symbols that are classified as ``declarative_target`` and
#: should move to ``module.yml`` derivation/validation sections.
DECLARATIVE_TARGET_SYMBOLS: Final[frozenset[str]] = frozenset(
    symbol
    for entries in MANIFEST_INVENTORY.values()
    for symbol, category, _ in entries
    if category == DECLARATIVE_TARGET
)

#: Set of all symbols that are already relocated to
#: ``quickscale_core.contracts.module_options``.
SHARED_HELPER_SYMBOLS: Final[frozenset[str]] = frozenset(
    symbol
    for entries in MANIFEST_INVENTORY.values()
    for symbol, category, _ in entries
    if category == SHARED_HELPER
)

#: Set of all symbols classified as manifest-resolver helpers.
MANIFEST_RESOLVER_SYMBOLS: Final[frozenset[str]] = frozenset(
    symbol
    for entries in MANIFEST_INVENTORY.values()
    for symbol, category, _ in entries
    if category == MANIFEST_RESOLVER
)

#: Set of all symbols classified as adapter-only (will be deleted with file).
ADAPTER_ONLY_SYMBOLS: Final[frozenset[str]] = frozenset(
    symbol
    for entries in MANIFEST_INVENTORY.values()
    for symbol, category, _ in entries
    if category == ADAPTER_ONLY
)


def get_manifest_inventory(module_name: str) -> list[tuple[str, str, str]]:
    """Return the symbol inventory for a single module manifest file.

    Args:
        module_name: The module name (e.g. ``"analytics"``, ``"auth"``).

    Returns:
        List of ``(symbol_name, category, phase)`` tuples.  Returns an
        empty list when the module is not in the inventory.
    """
    return list(MANIFEST_INVENTORY.get(module_name, []))


def count_inventory_category(category: str) -> int:
    """Count how many symbols across all modules share a given category.

    Args:
        category: One of ``DECLARATIVE_TARGET``, ``SHARED_HELPER``,
            ``MANIFEST_RESOLVER``, ``ADAPTER_ONLY``.

    Returns:
        The total count.
    """
    return sum(
        1
        for entries in MANIFEST_INVENTORY.values()
        for _, cat, _ in entries
        if cat == category
    )


__all__ = [
    "ADAPTER_ONLY",
    "ADAPTER_ONLY_SYMBOLS",
    "DECLARATIVE_TARGET",
    "DECLARATIVE_TARGET_SYMBOLS",
    "MANIFEST_INVENTORY",
    "MANIFEST_RESOLVER",
    "MANIFEST_RESOLVER_SYMBOLS",
    "SHARED_HELPER",
    "SHARED_HELPER_SYMBOLS",
    "count_inventory_category",
    "get_manifest_inventory",
]
