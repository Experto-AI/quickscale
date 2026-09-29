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

# SA5.1: Analytics imperative inventory cleared — all symbols are now
# served by the manifest-driven bridge in quickscale_core.contracts.resolvers.
# The analytics key remains in MANIFEST_INVENTORY with an empty list so that
# callers of get_manifest_inventory("analytics") continue to succeed.
ANALYTICS_MANIFEST: Final[list[tuple[str, str, str]]] = []

# SA217: Auth imperative inventory cleared — the manifest owns its option
# defaults, normalization, validation, and its retired-key refusals
# (`retired_options`), and its CLI configurator reads the manifest.  The auth
# key remains in MANIFEST_INVENTORY with an empty list so that callers of
# get_manifest_inventory("auth") continue to succeed.
AUTH_MANIFEST: Final[list[tuple[str, str, str]]] = []

# SA217: Backups imperative inventory cleared — the manifest owns its option
# defaults, normalization, validation, its retired raw-secret keys
# (`retired_options`), and its CLI configurator reads the manifest.  The
# backups key remains in MANIFEST_INVENTORY with an empty list so that
# callers of get_manifest_inventory("backups") continue to succeed.
BACKUPS_MANIFEST: Final[list[tuple[str, str, str]]] = []

# SA217: Billing imperative inventory cleared — the manifest owns its option
# defaults, normalization, and validation, and its CLI configurator reads the
# manifest.  The billing key remains in MANIFEST_INVENTORY with an empty list
# so that callers of get_manifest_inventory("billing") continue to succeed.
BILLING_MANIFEST: Final[list[tuple[str, str, str]]] = []

# SA217: Blog imperative inventory cleared — the manifest owns its option
# defaults, normalization, and validation, its adapter runs through the
# manifest engine, and its CLI configurator reads the manifest.  The blog
# key remains in MANIFEST_INVENTORY with an empty list so that callers of
# get_manifest_inventory("blog") continue to succeed.
BLOG_MANIFEST: Final[list[tuple[str, str, str]]] = []

# SA217: CRM imperative inventory cleared — the manifest owns its option
# defaults, normalization, validation, and its retired-key refusal
# (`retired_options`), and its CLI configurator reads the manifest.  The CRM
# key remains in MANIFEST_INVENTORY with an empty list so that callers of
# get_manifest_inventory("crm") continue to succeed.
CRM_MANIFEST: Final[list[tuple[str, str, str]]] = []

FORMS_MANIFEST: Final[list[tuple[str, str, str]]] = []

# SA6.2: Listings imperative inventory cleared — all symbols are now
# served by the manifest-driven derivation path in module.yml.
# The listings key remains in MANIFEST_INVENTORY with an empty list so that
# callers of get_manifest_inventory("listings") continue to succeed.
LISTINGS_MANIFEST: Final[list[tuple[str, str, str]]] = []

# SA217: Notifications imperative inventory cleared — the manifest owns its
# option defaults, normalization, validation, and its retired raw-secret keys
# (`retired_options`), its CLI configurator reads the manifest, and its runtime
# backend predicates live in the module adapter.  The notifications key remains
# in MANIFEST_INVENTORY with an empty list so that callers of
# get_manifest_inventory("notifications") continue to succeed.
NOTIFICATIONS_MANIFEST: Final[list[tuple[str, str, str]]] = []

# SA217: Orgs imperative inventory cleared — the manifest owns its option
# defaults, normalization, and validation, and its CLI configurator reads the
# manifest.  The orgs key remains in MANIFEST_INVENTORY with an empty list so
# that callers of get_manifest_inventory("orgs") continue to succeed.
ORGS_MANIFEST: Final[list[tuple[str, str, str]]] = []

# SA217: Social imperative inventory cleared — the manifest owns its option
# defaults, normalization (provider alias expansion and dedupe), and
# validation, and its CLI configurator reads the manifest.  The social key
# remains in MANIFEST_INVENTORY with an empty list so that callers of
# get_manifest_inventory("social") continue to succeed.
SOCIAL_MANIFEST: Final[list[tuple[str, str, str]]] = []

# SA217: Storage imperative inventory cleared — the manifest owns its option
# defaults, normalization, validation, its retired raw-credential keys
# (`retired_options`), and its CLI configurator reads the manifest.  The
# storage key remains in MANIFEST_INVENTORY with an empty list so that callers
# of get_manifest_inventory("storage") continue to succeed.
STORAGE_MANIFEST: Final[list[tuple[str, str, str]]] = []

# ---------------------------------------------------------------------------
# Freeze guardrail baseline
#
# SA5.2 freeze guardrail: grandfathered set of module names that still
# carry imperative inventory entries.  Any module NOT in this set that
# appears in MANIFEST_INVENTORY will fail CI — new modules must go through
# the manifest/derivation path, not add imperative inventory entries.
#
# This set is a **grandfathered freeze** that may only SHRINK when a
# module's imperative entries have been fully migrated to the
# manifest/derivation path (e.g. analytics after SA5.1).  Adding a new
# name here is a freeze-busting event that requires explicit documented
# approval.
#
# Manifest-only / derivation-only modules that ship without imperative
# inventory entries do NOT need to be added to this set.
# ---------------------------------------------------------------------------

#: Grandfathered module names that may still carry imperative inventory
#: entries.  SA5.2 freeze guardrail baseline — this is a grandfathered
#: freeze, not a mutable allowlist (see module docstring for rules).
AUTHORIZED_IMPERATIVE_MODULES: Final[frozenset[str]] = frozenset(
    {
        "analytics",
        "auth",
        "backups",
        "billing",
        "blog",
        "crm",
        "forms",
        "listings",
        "notifications",
        "orgs",
        "social",
        "storage",
    }
)

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
]
