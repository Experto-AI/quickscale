"""Tests for the imperative-logic inventory / ownership matrix.

Validates that the symbol inventories for each module manifest file are
internally consistent and meet basic structural expectations.
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
from quickscale_core.contracts.module_discovery import discover_shipped_module_names


class TestImperativeInventoryStructure:
    """Tests for the structure and consistency of MANIFEST_INVENTORY."""

    def test_inventory_only_has_shipped_modules(self) -> None:
        """Every module in MANIFEST_INVENTORY must be a shipped module."""
        shipped = set(discover_shipped_module_names())
        for name in MANIFEST_INVENTORY:
            assert name in shipped, (
                f"Module '{name}' in MANIFEST_INVENTORY but not a shipped module. "
                "New modules must go through the manifest/derivation path."
            )

    def test_every_entry_has_valid_category(self) -> None:
        """Every symbol entry should have a recognised ownership category."""
        valid_categories = {
            DECLARATIVE_TARGET,
            SHARED_HELPER,
            MANIFEST_RESOLVER,
            ADAPTER_ONLY,
        }
        for module_name, entries in MANIFEST_INVENTORY.items():
            for symbol, category, phase in entries:
                assert category in valid_categories, (
                    f"{module_name}.{symbol}: unknown category '{category}'"
                )

    def test_every_entry_has_phase(self) -> None:
        """Every symbol entry should have a non-empty migration phase."""
        for module_name, entries in MANIFEST_INVENTORY.items():
            for symbol, category, phase in entries:
                assert phase, f"{module_name}.{symbol}: empty migration phase"

    def test_no_duplicate_symbols_across_modules(self) -> None:
        """No symbol name should appear in two different modules."""
        seen: dict[str, str] = {}
        for module_name, entries in MANIFEST_INVENTORY.items():
            for symbol, category, phase in entries:
                assert symbol not in seen, (
                    f"Symbol '{symbol}' appears in both "
                    f"{seen[symbol]} and {module_name}"
                )
                seen[symbol] = module_name

    def test_category_sets_are_consistent(self) -> None:
        """The frozenset aggregates should match the per-module entries."""
        computed_declarative = frozenset(
            symbol
            for entries in MANIFEST_INVENTORY.values()
            for symbol, cat, _ in entries
            if cat == DECLARATIVE_TARGET
        )
        assert computed_declarative == DECLARATIVE_TARGET_SYMBOLS

        computed_shared = frozenset(
            symbol
            for entries in MANIFEST_INVENTORY.values()
            for symbol, cat, _ in entries
            if cat == SHARED_HELPER
        )
        assert computed_shared == SHARED_HELPER_SYMBOLS

        computed_resolver = frozenset(
            symbol
            for entries in MANIFEST_INVENTORY.values()
            for symbol, cat, _ in entries
            if cat == MANIFEST_RESOLVER
        )
        assert computed_resolver == MANIFEST_RESOLVER_SYMBOLS

        computed_adapter = frozenset(
            symbol
            for entries in MANIFEST_INVENTORY.values()
            for symbol, cat, _ in entries
            if cat == ADAPTER_ONLY
        )
        assert computed_adapter == ADAPTER_ONLY_SYMBOLS

    # ------------------------------------------------------------------
    # SA5.2 freeze guardrail
    # ------------------------------------------------------------------

    def test_no_new_imperative_modules_outside_authorized_set(self) -> None:
        """No module outside AUTHORIZED_IMPERATIVE_MODULES may appear in
        MANIFEST_INVENTORY.

        SA5.2 freeze guardrail: adding a new module's imperative builder
        entries to MANIFEST_INVENTORY fails CI unless the module name is
        first added to AUTHORIZED_IMPERATIVE_MODULES through an explicit
        policy decision (see the constant's docstring for rules).

        New modules must go through the manifest/derivation path instead
        of adding imperative inventory entries.
        """
        inventory_modules = set(MANIFEST_INVENTORY.keys())
        unauthorized = inventory_modules - AUTHORIZED_IMPERATIVE_MODULES
        assert not unauthorized, (
            f"Modules in MANIFEST_INVENTORY outside "
            f"AUTHORIZED_IMPERATIVE_MODULES: {unauthorized}. "
            "New modules must go through the manifest/derivation path, "
            "not add imperative inventory entries."
        )

    def test_authorized_set_contains_all_inventory_modules(self) -> None:
        """AUTHORIZED_IMPERATIVE_MODULES should be a superset of
        MANIFEST_INVENTORY keys.  This is the companion assertion to
        test_no_new_imperative_modules_outside_authorized_set, verifying
        that the authorized set is not accidentally narrowed.
        """
        assert AUTHORIZED_IMPERATIVE_MODULES.issuperset(MANIFEST_INVENTORY.keys()), (
            "AUTHORIZED_IMPERATIVE_MODULES is missing some modules from "
            "MANIFEST_INVENTORY.  Either add the missing module names to "
            "the authorized set, or migrate those modules to the "
            "manifest/derivation path and remove their inventory entries."
        )


class TestManifestInventoryHelpers:
    """Tests for helper functions in imperative_inventory."""

    def test_get_manifest_inventory_known(self) -> None:
        """get_manifest_inventory returns entries for known modules."""
        entries = get_manifest_inventory("analytics")
        # SA5.1: analytics inventory cleared — all symbols served by manifest bridge.
        assert len(entries) == 0

    def test_get_manifest_inventory_listings_migrated(self) -> None:
        """get_manifest_inventory returns empty list for listings after SA6.2.

        SA6.3 freeze guardrail: listings inventory cleared — all symbols
        served by manifest-driven derivation. Re-introducing imperative
        listings builder entries to MANIFEST_INVENTORY will fail this test.
        """
        entries = get_manifest_inventory("listings")
        # SA6.2: listings inventory cleared — all symbols served by manifest derivation.
        assert len(entries) == 0

    def test_get_manifest_inventory_unknown(self) -> None:
        """get_manifest_inventory returns empty list for unknown modules."""
        entries = get_manifest_inventory("nonexistent")
        assert entries == []

    def test_get_manifest_inventory_placeholder(self) -> None:
        """get_manifest_inventory returns empty list for placeholder names."""
        entries = get_manifest_inventory("teams")
        assert entries == []

    def test_count_inventory_category(self) -> None:
        """count_inventory_category returns a positive count for each category."""
        for category in (
            DECLARATIVE_TARGET,
            SHARED_HELPER,
            MANIFEST_RESOLVER,
            ADAPTER_ONLY,
        ):
            count = count_inventory_category(category)
            assert count > 0, f"Category '{category}' has zero entries"

    def test_total_symbols(self) -> None:
        """The sum of category counts should equal the total inventory size."""
        total = sum(len(entries) for entries in MANIFEST_INVENTORY.values())
        categorized = (
            count_inventory_category(DECLARATIVE_TARGET)
            + count_inventory_category(SHARED_HELPER)
            + count_inventory_category(MANIFEST_RESOLVER)
            + count_inventory_category(ADAPTER_ONLY)
        )
        assert total == categorized
