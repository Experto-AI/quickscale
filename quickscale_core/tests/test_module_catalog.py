"""Tests for the shared module catalog owned by quickscale_core."""

import pytest

from quickscale_core.contracts.module_catalog import (
    MODULE_CATALOG,
    find_not_ready_modules,
    get_discovered_module_entries,
    get_discovered_module_names,
    get_module_entry,
    get_module_readiness_reason,
)
from quickscale_core.contracts.module_discovery import (
    PLACEHOLDER_MODULE_NAMES,
    discover_shipped_module_names,
    get_placeholder_rejection_reason,
    is_placeholder_module,
)


class TestGetModuleEntry:
    def test_returns_entry_for_known_module(self) -> None:
        """Known module should return its metadata."""
        entry = get_module_entry("auth")
        assert entry is not None
        assert entry.name == "auth"
        assert entry.ready is True

    def test_returns_none_for_unknown_module(self) -> None:
        """Unknown module name should return None."""
        assert get_module_entry("nonexistent_module") is None


class TestFindNotReadyModules:
    def test_returns_sorted_not_ready(self) -> None:
        """Only known non-ready modules should be returned, sorted."""
        result = find_not_ready_modules(["auth", "teams", "unknown"])
        assert result == ["teams"]

    def test_returns_empty_when_all_ready(self) -> None:
        """All-ready module list should return empty."""
        result = find_not_ready_modules(["auth", "crm"])
        assert result == []

    def test_returns_empty_for_unknown_only(self) -> None:
        """Unknown modules should not be treated as 'not ready'."""
        result = find_not_ready_modules(["madeup"])
        assert result == []

    def test_returns_empty_for_empty_input(self) -> None:
        """Empty input should return empty list."""
        assert find_not_ready_modules([]) == []

    def test_deduplicates_repeated_names(self) -> None:
        """Duplicate module names should appear only once in the result."""
        result = find_not_ready_modules(["teams", "teams", "auth"])
        assert result == ["teams"]


class TestGetModuleReadinessReason:
    def test_returns_none_for_public_ready_module(self) -> None:
        """Ready modules should return None."""
        assert get_module_readiness_reason("auth") is None

    def test_raises_for_unknown_module(self) -> None:
        """Unknown modules should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown module name"):
            get_module_readiness_reason("nonexistent")

    def test_returns_reason_for_non_ready_module(self) -> None:
        """Non-ready modules should return an actionable readiness message."""
        reason = get_module_readiness_reason("teams")
        assert reason is not None
        assert "teams" in reason
        assert "placeholder inventory only" in reason


# ---------------------------------------------------------------------------
# Manifest-backed discovery
# ---------------------------------------------------------------------------


class TestDiscoverShippedModuleNames:
    """Tests for manifest-backed module name discovery."""

    def test_discovery_returns_expected_modules(self) -> None:
        """Discovery should return all shipped module names."""
        names = discover_shipped_module_names()
        assert "auth" in names
        assert "analytics" in names
        assert "billing" in names
        assert "crm" in names
        assert "teams" not in names

    def test_discovery_returns_sorted(self) -> None:
        """Discovery should return names in alphabetical order."""
        names = discover_shipped_module_names()
        assert names == sorted(names)

    def test_discovery_via_module_catalog(self) -> None:
        """get_discovered_module_names delegates to discovery."""
        names = get_discovered_module_names()
        assert "auth" in names
        assert "teams" not in names

    def test_discovery_entries_are_all_ready(self) -> None:
        """Discovered module entries should all be marked ready=True."""
        entries = get_discovered_module_entries()
        for entry in entries:
            assert entry.ready, f"Discovered module {entry.name} is not ready"
        assert "teams" not in [e.name for e in entries]

    def test_discovery_entries_are_sorted(self) -> None:
        """Discovered entries should be in alphabetical order."""
        entries = get_discovered_module_entries()
        names = [e.name for e in entries]
        assert names == sorted(names)

    def test_discovery_entries_have_descriptions(self) -> None:
        """Discovered entries should carry descriptions from the static catalog."""
        entries = get_discovered_module_entries()
        entry_map = {e.name: e for e in entries}
        auth_entry = entry_map.get("auth")
        assert auth_entry is not None
        assert auth_entry.description  # non-empty


# ---------------------------------------------------------------------------
# Placeholder module rejection
# ---------------------------------------------------------------------------


class TestPlaceholderModuleRejection:
    """Tests for the fail-closed placeholder module rejection path."""

    def test_teams_is_placeholder(self) -> None:
        """Teams should be a known placeholder."""
        assert is_placeholder_module("teams")

    def test_shipped_module_not_placeholder(self) -> None:
        """Shipped modules should not be placeholders."""
        assert not is_placeholder_module("auth")

    def test_unknown_not_placeholder(self) -> None:
        """Unknown modules should not be placeholders."""
        assert not is_placeholder_module("nonexistent")

    def test_placeholder_in_set(self) -> None:
        """PLACEHOLDER_MODULE_NAMES should contain teams."""
        assert "teams" in PLACEHOLDER_MODULE_NAMES

    def test_placeholder_rejection_reason(self) -> None:
        """get_placeholder_rejection_reason should return a reason for teams."""
        reason = get_placeholder_rejection_reason("teams")
        assert reason is not None
        assert "placeholder inventory only" in reason

    def test_placeholder_rejection_none_for_shipped(self) -> None:
        """get_placeholder_rejection_reason should return None for shipped modules."""
        assert get_placeholder_rejection_reason("auth") is None

    def test_find_not_ready_includes_placeholder(self) -> None:
        """find_not_ready_modules should include placeholder module names."""
        result = find_not_ready_modules(["teams", "auth"])
        assert "teams" in result

    def test_readiness_reason_via_placeholder(self) -> None:
        """get_module_readiness_reason should route to placeholder check."""
        reason = get_module_readiness_reason("teams")
        assert reason is not None
        assert "placeholder inventory only" in reason


# ---------------------------------------------------------------------------
# Canonical inventory guard — D2
# ---------------------------------------------------------------------------


class TestDiscoveredCatalogIsCanonicalInventory:
    """Guard that ``get_discovered_module_entries`` is the sole inventory path.

    ``MODULE_CATALOG`` is frozen to description-only metadata after D2.
    Any caller that needs the list of shipped modules must use
    :func:`get_discovered_module_entries` or
    :func:`get_discovered_module_names` instead of iterating the static
    ``MODULE_CATALOG`` tuple.
    """

    def test_discovered_entries_cover_all_ready_static_entries(self) -> None:
        """Every ready module in the static catalog must appear in discovered entries.

        This prevents divergence: if you add a ``module.yml`` for a new module,
        it must also appear in the static catalog's ready set (for description
        metadata), and vice versa.
        """
        discovered = {e.name for e in get_discovered_module_entries()}
        static_ready = {e.name for e in MODULE_CATALOG if e.ready}
        missing = static_ready - discovered
        assert not missing, (
            "Ready static catalog modules missing from discovered inventory: "
            f"{sorted(missing)}. "
            "Either the module.yml is missing or the static catalog entry "
            "is stale."
        )

    def test_discovered_names_are_sorted(self) -> None:
        """get_discovered_module_names must return sorted names."""
        names = get_discovered_module_names()
        assert names == sorted(names)

    def test_discovered_entries_are_sorted(self) -> None:
        """get_discovered_module_entries must return sorted entries."""
        entries = get_discovered_module_entries()
        names = [e.name for e in entries]
        assert names == sorted(names)
