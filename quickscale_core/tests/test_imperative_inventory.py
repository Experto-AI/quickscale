"""Tests for the imperative-logic inventory / ownership matrix.

Validates that the symbol inventories for each module manifest file are
internally consistent and meet basic structural expectations.
"""

from quickscale_core.contracts.imperative_inventory import (
    ADAPTER_ONLY,
    ADAPTER_ONLY_SYMBOLS,
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

    def test_inventory_has_all_shipped_modules(self) -> None:
        """Every shipped module should have an inventory entry."""
        shipped = discover_shipped_module_names()
        for name in shipped:
            assert name in MANIFEST_INVENTORY, (
                f"Shipped module '{name}' missing from MANIFEST_INVENTORY"
            )

    def test_inventory_only_has_shipped_modules(self) -> None:
        """Inventory should not contain entries for placeholder modules."""
        assert "teams" not in MANIFEST_INVENTORY

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


class TestManifestInventoryHelpers:
    """Tests for helper functions in imperative_inventory."""

    def test_get_manifest_inventory_known(self) -> None:
        """get_manifest_inventory returns entries for known modules."""
        entries = get_manifest_inventory("analytics")
        assert len(entries) > 0

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
