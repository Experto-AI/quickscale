"""Imperative-logic inventory and ownership matrix for CLI contract files.

This module catalogs every public symbol exported by the per-module
``*_manifest.py`` files in ``quickscale_cli`` and classifies them by
ownership category.  Later phases (Track 2 Phase 3+) use this inventory
to decide which symbols can be deleted when the corresponding manifest
adapter is migrated to the declarative path.

Every per-module inventory is empty since SA217 cleared the last entry, so
the module keys come from core's declared release inventory instead of a
hand-written list (Module Conventions rule 37).  The categories below remain
the classification vocabulary.

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

from quickscale_core.contracts.module_catalog import MODULE_CATALOG

# ---------------------------------------------------------------------------
# Ownership categories (string literals for readability)
# ---------------------------------------------------------------------------

DECLARATIVE_TARGET: Final[str] = "declarative_target"
SHARED_HELPER: Final[str] = "shared_helper"
MANIFEST_RESOLVER: Final[str] = "manifest_resolver"
ADAPTER_ONLY: Final[str] = "adapter_only"

# ---------------------------------------------------------------------------
# Declared inventory
#
# The per-module keys come from core's declared release inventory (Module
# Conventions rule 37's allowed exception), which the catalog consistency test
# keeps equal to manifest discovery.  Reading it never touches the filesystem,
# so importing this module cannot run discovery (decisions.md: no import-time
# filesystem discovery).  The SA5.2 freeze guardrail stays as the companion
# test that rejects an inventory key which is not a shipped module; a future
# module carries its options through the manifest/derivation path, not through
# a new literal entry here.
# ---------------------------------------------------------------------------

#: Mapping from module name to its symbol inventory list.
#: Each value is a list of ``(symbol_name, category, phase)`` tuples.
MANIFEST_INVENTORY: Final[dict[str, list[tuple[str, str, str]]]] = {
    entry.name: [] for entry in MODULE_CATALOG
}

#: Grandfathered module names that may still carry imperative inventory
#: entries.  SA5.2 freeze guardrail baseline: every declared module is
#: authorized in the cleared state, and the companion test keeps the set a
#: superset of the inventory keys.
AUTHORIZED_IMPERATIVE_MODULES: Final[frozenset[str]] = frozenset(MANIFEST_INVENTORY)

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
