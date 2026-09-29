"""Tests for the shared module catalog owned by quickscale_core."""

from pathlib import Path

import pytest

from quickscale_core.contracts.module_catalog import (
    MODULE_CATALOG,
    ModuleCatalogEntry,
    find_not_ready_modules,
    get_discovered_module_entries,
    get_discovered_module_names,
    get_module_entry,
    get_module_readiness_reason,
)
from quickscale_core.contracts.module_discovery import discover_shipped_module_names


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

    def test_returns_manifest_description_for_declared_module(self) -> None:
        """A declared module's description comes from its module.yml (rule 37)."""
        from quickscale_core.contracts.module_discovery import (
            discover_shipped_module_paths,
        )
        from quickscale_core.manifest.loader import load_manifest_from_path

        entry = get_module_entry("orgs")
        assert entry is not None
        manifest = load_manifest_from_path(
            discover_shipped_module_paths()["orgs"] / "module.yml"
        )
        assert entry.description == manifest.description


class TestFindNotReadyModules:
    def test_returns_sorted_not_ready(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Only known non-ready modules should be returned, sorted."""
        from quickscale_core.contracts import module_catalog as _mc

        original = _mc.get_module_entry

        def fake(name: str) -> ModuleCatalogEntry | None:
            if name == "hidden":
                return ModuleCatalogEntry(name="hidden", description="", ready=False)
            return original(name)

        monkeypatch.setattr(_mc, "get_module_entry", fake)
        result = find_not_ready_modules(["auth", "hidden", "unknown"])
        assert result == ["hidden"]

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

    def test_deduplicates_repeated_names(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Duplicate module names should appear only once in the result."""
        from quickscale_core.contracts import module_catalog as _mc

        original = _mc.get_module_entry

        def fake(name: str) -> ModuleCatalogEntry | None:
            if name == "hidden":
                return ModuleCatalogEntry(name="hidden", description="", ready=False)
            return original(name)

        monkeypatch.setattr(_mc, "get_module_entry", fake)
        result = find_not_ready_modules(["hidden", "hidden", "auth"])
        assert result == ["hidden"]


class TestGetModuleReadinessReason:
    def test_returns_none_for_public_ready_module(self) -> None:
        """Ready modules should return None."""
        assert get_module_readiness_reason("auth") is None

    def test_raises_for_unknown_module(self) -> None:
        """Unknown modules should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown module name"):
            get_module_readiness_reason("nonexistent")

    def test_returns_reason_for_non_ready_module(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-ready modules should return an actionable readiness message."""
        from quickscale_core.contracts import module_catalog as _mc

        original = _mc.get_module_entry

        def fake(name: str) -> ModuleCatalogEntry | None:
            if name == "hidden":
                return ModuleCatalogEntry(name="hidden", description="", ready=False)
            return original(name)

        monkeypatch.setattr(_mc, "get_module_entry", fake)
        reason = get_module_readiness_reason("hidden")
        assert reason is not None
        assert "hidden" in reason
        assert "not a public-ready" in reason


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
        """Discovered entries carry the module.yml description of each module."""
        from quickscale_core.contracts.module_discovery import (
            discover_shipped_module_paths,
        )
        from quickscale_core.manifest.loader import load_manifest_from_path

        entries = get_discovered_module_entries()
        entry_map = {e.name: e for e in entries}
        assert entry_map["auth"].description  # non-empty
        for name, module_path in discover_shipped_module_paths().items():
            manifest = load_manifest_from_path(module_path / "module.yml")
            assert entry_map[name].description == manifest.description


# ---------------------------------------------------------------------------
# Canonical inventory guard — D2
# ---------------------------------------------------------------------------


class TestDiscoveredCatalogIsCanonicalInventory:
    """Guard that ``get_discovered_module_entries`` is the sole inventory path.

    ``MODULE_CATALOG`` declares the shipped-contract inventory and readiness
    only; a module's description lives in its ``module.yml``.  Any caller that
    needs the list of shipped modules must use
    :func:`get_discovered_module_entries` or
    :func:`get_discovered_module_names` instead of iterating the static
    ``MODULE_CATALOG`` tuple.
    """

    def test_discovered_entries_cover_all_ready_static_entries(self) -> None:
        """Every ready module in the static catalog must appear in discovered entries.

        This prevents divergence: if you add a ``module.yml`` for a new module,
        it must also appear in the static catalog's ready set (the shipped
        contract), and vice versa.
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

    def test_declared_inventory_matches_discovery(self) -> None:
        """The declared release inventory equals the discovered shipped set."""
        declared = {entry.name for entry in MODULE_CATALOG}
        discovered = set(get_discovered_module_names())
        assert declared == discovered

    def test_discovered_names_are_sorted(self) -> None:
        """get_discovered_module_names must return sorted names."""
        names = get_discovered_module_names()
        assert names == sorted(names)

    def test_discovered_entries_are_sorted(self) -> None:
        """get_discovered_module_entries must return sorted entries."""
        entries = get_discovered_module_entries()
        names = [e.name for e in entries]
        assert names == sorted(names)


# ---------------------------------------------------------------------------
# SA109 Phase 2 — authoritative source-or-bundled discovery, fail-hard
# ---------------------------------------------------------------------------


class TestGetDiscoveredModuleNamesSourceOrBundled:
    """``get_discovered_module_names`` resolves source inventory first and
    falls back to authoritative bundled inventory.  Neither available → fail-hard.
    """

    def test_source_used_when_available(self) -> None:
        """When the monorepo is available, discovery returns source inventory."""
        names = get_discovered_module_names()
        assert "analytics" in names
        assert "teams" not in names
        assert names == sorted(names)

    def test_bundled_fallback_when_source_unavailable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the monorepo is not available, falls back to bundled manifests."""
        from quickscale_core.contracts import module_discovery as _md

        original_override = _md._modules_base_path
        _md._modules_base_path = None
        try:
            monorepo_path = Path(__file__).resolve().parents[2] / "quickscale_modules"
            real_is_dir = Path.is_dir

            def _no_monorepo(self: Path) -> bool:
                if self.resolve() == monorepo_path.resolve():
                    return False
                return real_is_dir(self)

            monkeypatch.setattr(Path, "is_dir", _no_monorepo)

            names = get_discovered_module_names()
            assert "analytics" in names
            assert "teams" not in names
            assert names == sorted(names)
        finally:
            _md._modules_base_path = original_override

    def test_fails_hard_when_no_inventory(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Raises ImproperlyConfigured when neither source nor bundled exists."""
        from quickscale_core.contracts import module_discovery as _md
        from quickscale_core.contracts.module_discovery import ImproperlyConfigured

        original_override = _md._modules_base_path
        _md._modules_base_path = None
        try:
            # Make ALL is_dir calls return False — monorepo AND bundled vanish.
            monkeypatch.setattr(Path, "is_dir", lambda _self: False)

            with pytest.raises(
                ImproperlyConfigured,
                match="No valid module.yml files found|Bundled manifests directory.*not found",
            ):
                get_discovered_module_names()
        finally:
            _md._modules_base_path = original_override


class TestGetDiscoveredModuleEntriesBundledAware:
    """``get_discovered_module_entries`` must use the same bundled-aware
    discovery path as ``get_discovered_module_names`` (SA109-CR-001).
    """

    def test_entries_use_source_when_available(self) -> None:
        """Entries return all shipped modules when source is available."""
        entries = get_discovered_module_entries()
        names = [e.name for e in entries]
        assert "auth" in names
        assert "analytics" in names
        assert "teams" not in names
        assert names == sorted(names)

    def test_entries_fallback_to_bundled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Entries fall back to bundled manifests when source is unavailable."""
        from quickscale_core.contracts import module_discovery as _md

        original_override = _md._modules_base_path
        _md._modules_base_path = None
        try:
            monorepo_path = Path(__file__).resolve().parents[2] / "quickscale_modules"
            real_is_dir = Path.is_dir

            def _no_monorepo(self: Path) -> bool:
                if self.resolve() == monorepo_path.resolve():
                    return False
                return real_is_dir(self)

            monkeypatch.setattr(Path, "is_dir", _no_monorepo)

            entries = get_discovered_module_entries()
            names = [e.name for e in entries]
            assert "analytics" in names
            assert "teams" not in names
            assert names == sorted(names)
        finally:
            _md._modules_base_path = original_override

    def test_entries_names_match_discovered_names(self) -> None:
        """Entry names must be identical to the canonical discovered names."""
        entries = get_discovered_module_entries()
        entry_names = sorted([e.name for e in entries])
        discovered_names = sorted(get_discovered_module_names())
        assert entry_names == discovered_names, (
            "get_discovered_module_entries returned different names than "
            f"get_discovered_module_names: "
            f"entries={entry_names}, names={discovered_names}"
        )

    def test_entries_fails_hard_when_no_inventory(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Raises ImproperlyConfigured when neither source nor bundled exists."""
        from quickscale_core.contracts import module_discovery as _md
        from quickscale_core.contracts.module_discovery import ImproperlyConfigured

        original_override = _md._modules_base_path
        _md._modules_base_path = None
        try:
            monkeypatch.setattr(Path, "is_dir", lambda _self: False)

            with pytest.raises(
                ImproperlyConfigured,
                match="No valid module.yml files found|Bundled manifests directory.*not found",
            ):
                get_discovered_module_entries()
        finally:
            _md._modules_base_path = original_override
