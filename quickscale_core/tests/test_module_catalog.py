"""Tests for the shared module catalog owned by quickscale_core."""

from quickscale_core.contracts.module_catalog import (
    MODULE_CATALOG,
    find_not_ready_modules,
    get_module_entries,
    get_module_entry,
    get_module_names,
    get_module_readiness_reason,
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


class TestGetModuleEntries:
    def test_filters_non_ready_by_default(self) -> None:
        """Default entries should exclude non-ready modules."""
        entries = get_module_entries()
        names = [e.name for e in entries]
        assert "auth" in names
        assert "teams" not in names

    def test_includes_experimental_when_requested(self) -> None:
        """include_experimental=True should surface non-ready entries."""
        entries = get_module_entries(include_experimental=True)
        names = [e.name for e in entries]
        assert "teams" in names


class TestGetModuleNames:
    def test_returns_all_when_including_experimental(self) -> None:
        """All module names should be returned with include_experimental=True."""
        names = get_module_names(include_experimental=True)
        assert "teams" in names
        assert len(names) == len(MODULE_CATALOG)

    def test_includes_experimental_by_default(self) -> None:
        """Default get_module_names includes experimental modules (param default is True)."""
        names = get_module_names()
        assert "teams" in names

    def test_excludes_teams_when_explicitly_false(self) -> None:
        """Explicit include_experimental=False filters non-ready modules."""
        names = get_module_names(include_experimental=False)
        assert "teams" not in names


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

    def test_returns_none_for_unknown_module(self) -> None:
        """Unknown modules should return None."""
        assert get_module_readiness_reason("nonexistent") is None

    def test_returns_reason_for_non_ready_module(self) -> None:
        """Non-ready modules should return an actionable readiness message."""
        reason = get_module_readiness_reason("teams")
        assert reason is not None
        assert "teams" in reason
        assert "placeholder inventory only" in reason
