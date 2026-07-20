"""Tests for manifest-backed module discovery.

These tests verify that the discovery functions correctly enumerate shipped
modules by scanning the repository's ``quickscale_modules/*/module.yml``
files, exclude placeholder directories, and provide the expected fail-closed
rejection path.

Phase 1 (SA109) adds explicit bundled-manifest discovery and resolution-source
observability.
"""

from __future__ import annotations

from importlib import resources as _resources
from pathlib import Path

import pytest

from quickscale_core.contracts.module_discovery import (
    ImproperlyConfigured,
    ModuleResolutionSource,
    PLACEHOLDER_MODULE_NAMES,
    discover_bundled_module_names,
    discover_shipped_module_names,
    discover_shipped_module_paths,
    get_bundled_manifests_path,
    get_modules_base_path,
    get_placeholder_rejection_reason,
    get_resolution_source,
    is_placeholder_module,
    set_modules_base_path,
)


class TestGetModulesBasePath:
    """Tests for get_modules_base_path."""

    def test_default_path_resolves_to_quickscale_modules(self) -> None:
        """The default path should end with 'quickscale_modules'."""
        path = get_modules_base_path()
        assert path.name == "quickscale_modules"
        assert path.is_dir()

    def test_default_path_is_absolute(self) -> None:
        """The default path should be absolute."""
        path = get_modules_base_path()
        assert path.is_absolute()

    def test_override_path(self) -> None:
        """set_modules_base_path should be reflected in get_modules_base_path."""
        import pathlib

        original = get_modules_base_path()
        try:
            test_path = pathlib.Path("/tmp/quickscale-test-modules")
            set_modules_base_path(test_path)
            assert get_modules_base_path() == test_path
        finally:
            set_modules_base_path(original)

    def test_bundled_manifests_exist(self) -> None:
        """The bundled manifest data directory should contain module.yml files
        for every shipped module, making the installed-package fallback viable.
        """
        try:
            ref = _resources.files("quickscale_core") / "data" / "manifests"
        except Exception:
            # ``importlib.resources`` may not support this package layout
            # in all contexts (e.g. namespace packages, editable installs);
            # skip visibly instead of passing silently.
            pytest.skip(
                "importlib.resources bundled path not available in this environment"
            )

        if not ref.is_dir():
            pytest.skip("Bundled manifests directory not found on disk")

        bundled_mods: set[str] = set()
        for entry in sorted(ref.iterdir()):
            if entry.is_dir():
                manifest = entry / "module.yml"
                if manifest.is_file():
                    bundled_mods.add(entry.name)

        for shipped in ("auth", "analytics", "billing", "blog", "crm", "social"):
            assert shipped in bundled_mods, (
                f"Shipped module '{shipped}' missing from bundled manifests"
            )

    def test_get_modules_base_path_raises_when_no_path_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``get_modules_base_path`` raises ``ImproperlyConfigured`` when
        no runtime override is set and the monorepo path does not exist.
        """
        from quickscale_core.contracts import module_discovery as _md

        original_override = _md._modules_base_path
        _md._modules_base_path = None

        try:
            # Make ``Path.is_dir`` return ``False`` so the monorepo
            # path check fails.
            monkeypatch.setattr(Path, "is_dir", lambda _self: False)

            with pytest.raises(
                ImproperlyConfigured, match="Modules base path not found"
            ):
                _md.get_modules_base_path()
        finally:
            _md._modules_base_path = original_override

    def test_discovery_works_through_custom_base_path(self) -> None:
        """``discover_shipped_module_names`` and
        ``discover_shipped_module_paths`` work correctly when the modules
        base path is overridden via ``set_modules_base_path``.
        """
        import tempfile as _tempfile

        original = get_modules_base_path()
        try:
            with _tempfile.TemporaryDirectory() as td:
                tmp = Path(td)

                # Create valid module directories with module.yml files.
                (tmp / "mod_alpha" / "module.yml").parent.mkdir(parents=True)
                (tmp / "mod_alpha" / "module.yml").write_text(
                    "name: mod_alpha\nversion: '1'\n"
                )
                (tmp / "mod_beta" / "module.yml").parent.mkdir(parents=True)
                (tmp / "mod_beta" / "module.yml").write_text(
                    "name: mod_beta\nversion: '1'\n"
                )

                # Create a directory without module.yml — should be excluded.
                (tmp / "not_a_module").mkdir()

                set_modules_base_path(tmp)

                names = discover_shipped_module_names()
                assert "mod_alpha" in names
                assert "mod_beta" in names
                assert "not_a_module" not in names
                assert names == sorted(names)

                paths = discover_shipped_module_paths()
                assert "mod_alpha" in paths
                assert paths["mod_alpha"].is_dir()
                assert "mod_beta" in paths
                assert "not_a_module" not in paths
        finally:
            set_modules_base_path(original)


class TestResolutionSource:
    """Tests for get_resolution_source."""

    def test_override_when_set(self) -> None:
        """When override is set, source should be OVERRIDE."""
        original = get_modules_base_path()
        try:
            set_modules_base_path("/tmp/quickscale-test-source")
            assert get_resolution_source() is ModuleResolutionSource.OVERRIDE
        finally:
            set_modules_base_path(original)

    def test_monorepo_when_no_override(self) -> None:
        """When no override but monorepo exists, source should be MONOREPO."""
        from quickscale_core.contracts import module_discovery as _md

        original_override = _md._modules_base_path
        _md._modules_base_path = None
        try:
            assert get_resolution_source() is ModuleResolutionSource.MONOREPO
        finally:
            _md._modules_base_path = original_override

    def test_raises_when_no_source(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Raises ImproperlyConfigured when no source is available."""
        from quickscale_core.contracts import module_discovery as _md

        original_override = _md._modules_base_path
        _md._modules_base_path = None
        try:
            monkeypatch.setattr(Path, "is_dir", lambda _self: False)

            with pytest.raises(
                ImproperlyConfigured, match="No module resolution source available"
            ):
                get_resolution_source()
        finally:
            _md._modules_base_path = original_override

    def test_bundled_when_monorepo_absent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Returns BUNDLED when monorepo is absent but bundled manifests exist
        and are usable (SA109-CR-002)."""
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

            source = get_resolution_source()
            assert source is ModuleResolutionSource.BUNDLED
        finally:
            _md._modules_base_path = original_override

    def test_raises_when_bundled_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Raises ImproperlyConfigured when bundled manifests directory exists
        but is empty (SA109-CR-002)."""
        import tempfile

        from quickscale_core.contracts import module_discovery as _md

        original_override = _md._modules_base_path
        _md._modules_base_path = None
        try:
            # Make monorepo path look absent so we fall through to bundled.
            monorepo_path = Path(__file__).resolve().parents[2] / "quickscale_modules"
            real_is_dir = Path.is_dir

            # Create an empty manifests directory.
            empty_manifests_root = Path(tempfile.mkdtemp())
            (empty_manifests_root / "data" / "manifests").mkdir(parents=True)

            def _patched_is_dir(self: Path) -> bool:
                if self.resolve() == monorepo_path.resolve():
                    return False
                return real_is_dir(self)

            monkeypatch.setattr(Path, "is_dir", _patched_is_dir)

            # Redirect _resources.files to return a path to the empty dir.
            monkeypatch.setattr(
                _md._resources,
                "files",
                lambda _pkg: empty_manifests_root,
            )

            with pytest.raises(
                ImproperlyConfigured,
                match="No valid module.yml files found",
            ):
                get_resolution_source()
        finally:
            _md._modules_base_path = original_override

    def test_preserves_root_cause_when_files_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Preserves root cause when importlib.resources.files raises
        (SA109-CR-002 — no broad exception swallowing)."""
        from quickscale_core.contracts import module_discovery as _md

        original_override = _md._modules_base_path
        _md._modules_base_path = None
        try:
            # Make monorepo path absent.
            monorepo_path = Path(__file__).resolve().parents[2] / "quickscale_modules"
            real_is_dir = Path.is_dir

            def _patched_is_dir(self: Path) -> bool:
                if self.resolve() == monorepo_path.resolve():
                    return False
                return real_is_dir(self)

            monkeypatch.setattr(Path, "is_dir", _patched_is_dir)

            def _raise_files(_pkg: str) -> None:
                raise RuntimeError("simulated importlib failure")

            monkeypatch.setattr(_md._resources, "files", _raise_files)

            with pytest.raises(ImproperlyConfigured) as exc_info:
                get_resolution_source()
            assert isinstance(exc_info.value.__cause__, RuntimeError), (
                "Root cause must be preserved in ImproperlyConfigured.__cause__"
            )
        finally:
            _md._modules_base_path = original_override


class TestGetBundledManifestsPath:
    """Tests for get_bundled_manifests_path."""

    def test_returns_path(self) -> None:
        """Should return a path ending with 'data/manifests'."""
        path = get_bundled_manifests_path()
        assert isinstance(path, Path)
        assert path.name == "manifests"
        assert path.parent.name == "data"

    def test_path_is_absolute(self) -> None:
        """The returned path should be absolute."""
        path = get_bundled_manifests_path()
        assert path.is_absolute()

    def test_path_exists(self) -> None:
        """The returned path should exist on disk."""
        path = get_bundled_manifests_path()
        assert path.is_dir()

    def test_raises_when_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Raises ImproperlyConfigured when the bundled path does not exist."""
        import quickscale_core.contracts.module_discovery as _md

        # Make is_dir return False for the bundled path.
        real_is_dir = Path.is_dir

        def _selective_is_dir(self: Path) -> bool:
            try:
                ref = _resources.files("quickscale_core") / "data" / "manifests"
                if self.resolve() == ref.resolve():
                    return False
            except Exception:
                pass
            return real_is_dir(self)

        monkeypatch.setattr(Path, "is_dir", _selective_is_dir)

        with pytest.raises(
            ImproperlyConfigured, match="Bundled manifests directory.*not found"
        ):
            _md.get_bundled_manifests_path()


class TestDiscoverBundledModuleNames:
    """Tests for discover_bundled_module_names."""

    def test_returns_sorted_list(self) -> None:
        """Should return a sorted list of module names."""
        names = discover_bundled_module_names()
        assert isinstance(names, list)
        assert names == sorted(names)

    def test_includes_shipped_modules(self) -> None:
        """Known shipped modules should appear in bundled discovery."""
        names = discover_bundled_module_names()
        for shipped in ("auth", "analytics", "billing", "blog", "crm", "social"):
            assert shipped in names, (
                f"Shipped module '{shipped}' missing from bundled manifests"
            )

    def test_excludes_placeholder(self) -> None:
        """'teams' should not appear in bundled discovery."""
        names = discover_bundled_module_names()
        assert "teams" not in names

    def test_matches_shipped_inventory(self) -> None:
        """Bundled discovery should return a subset of shipped discovery
        when running in the monorepo (G4 inventory parity).
        """
        shipped_names = set(discover_shipped_module_names())
        bundled_names = set(discover_bundled_module_names())
        missing = bundled_names - shipped_names
        assert not missing, (
            f"Bundled modules not found in shipped source: {sorted(missing)}"
        )

    def test_raises_when_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Raises ImproperlyConfigured when bundled manifests are empty."""
        import quickscale_core.contracts.module_discovery as _md
        import tempfile

        # Replace the bundled manifests path with an empty temp directory.
        empty_dir = Path(tempfile.mkdtemp())
        monkeypatch.setattr(_md, "get_bundled_manifests_path", lambda: empty_dir)

        with pytest.raises(
            ImproperlyConfigured, match="No valid module.yml files found"
        ):
            _md.discover_bundled_module_names()


class TestDiscoverShippedModuleNames:
    """Tests for discover_shipped_module_names."""

    def test_returns_list(self) -> None:
        """Discovery should return a list."""
        names = discover_shipped_module_names()
        assert isinstance(names, list)

    def test_shipped_modules_included(self) -> None:
        """Known shipped modules should appear in discovery."""
        names = discover_shipped_module_names()
        for shipped in ("auth", "analytics", "billing", "blog", "crm", "social"):
            assert shipped in names, f"Shipped module '{shipped}' not discovered"

    def test_placeholder_excluded(self) -> None:
        """Placeholder directories without module.yml should be excluded."""
        names = discover_shipped_module_names()
        assert "teams" not in names

    def test_sorted_order(self) -> None:
        """Results should be alphabetically sorted."""
        names = discover_shipped_module_names()
        assert names == sorted(names)

    def test_no_readme_files(self) -> None:
        """README.md and other non-directory files should be excluded."""
        names = discover_shipped_module_names()
        assert "README.md" not in names
        assert "adaptive.rules.md" not in names


class TestDiscoverShippedModulePaths:
    """Tests for discover_shipped_module_paths."""

    def test_returns_dict(self) -> None:
        """Discovery should return a dict."""
        paths = discover_shipped_module_paths()
        assert isinstance(paths, dict)

    def test_shipped_modules_included(self) -> None:
        """Known shipped modules should have entries."""
        paths = discover_shipped_module_paths()
        assert "auth" in paths
        assert "social" in paths

    def test_paths_are_absolute(self) -> None:
        """Each module path should be absolute and exist."""
        paths = discover_shipped_module_paths()
        for name, path in paths.items():
            assert path.is_absolute(), f"{name} path is not absolute"
            assert path.is_dir(), f"{name} path does not exist"

    def test_placeholder_excluded(self) -> None:
        """Placeholder directories should be excluded."""
        paths = discover_shipped_module_paths()
        assert "teams" not in paths


class TestIsPlaceholderModule:
    """Tests for is_placeholder_module."""

    def test_teams_is_placeholder(self) -> None:
        """'teams' should be recognised as a placeholder."""
        assert is_placeholder_module("teams")

    def test_shipped_not_placeholder(self) -> None:
        """Shipped module names should not be placeholders."""
        assert not is_placeholder_module("auth")

    def test_unknown_not_placeholder(self) -> None:
        """Unknown names should not be placeholders."""
        assert not is_placeholder_module("nonexistent_module")

    def test_empty_string_not_placeholder(self) -> None:
        """Empty string should not be a placeholder."""
        assert not is_placeholder_module("")


class TestPlaceholderModuleNames:
    """Tests for PLACEHOLDER_MODULE_NAMES constant."""

    def test_teams_in_placeholder(self) -> None:
        """'teams' should be in the placeholder set."""
        assert "teams" in PLACEHOLDER_MODULE_NAMES

    def test_shipped_not_in_placeholder(self) -> None:
        """Shipped modules should not be in the placeholder set."""
        assert "auth" not in PLACEHOLDER_MODULE_NAMES

    def test_placeholder_is_frozenset(self) -> None:
        """PLACEHOLDER_MODULE_NAMES should be a frozenset."""
        assert isinstance(PLACEHOLDER_MODULE_NAMES, frozenset)


class TestGetPlaceholderRejectionReason:
    """Tests for get_placeholder_rejection_reason."""

    def test_returns_reason_for_teams(self) -> None:
        """A known placeholder should return a rejection reason."""
        reason = get_placeholder_rejection_reason("teams")
        assert reason is not None
        assert isinstance(reason, str)
        assert "placeholder" in reason.lower()

    def test_returns_none_for_shipped(self) -> None:
        """Shipped modules should return None."""
        assert get_placeholder_rejection_reason("auth") is None

    def test_returns_none_for_unknown(self) -> None:
        """Unknown modules should return None."""
        assert get_placeholder_rejection_reason("nonexistent") is None

    def test_reason_contains_module_name(self) -> None:
        """The rejection reason should mention the module name."""
        reason = get_placeholder_rejection_reason("teams")
        assert reason is not None
        assert "teams" in reason

    def test_reason_display_name_formatted(self) -> None:
        """The display name in the reason should be title-cased."""
        reason = get_placeholder_rejection_reason("teams")
        assert reason is not None
        assert "Teams" in reason


# ---------------------------------------------------------------------------
# G4 inventory parity — source vs. bundled
# ---------------------------------------------------------------------------


class TestSourceAndBundledInventorySync:
    """G4 guard: source and bundled inventories must remain synchronized.

    When running in the maintainer monorepo, ``discover_shipped_module_names``
    and ``discover_bundled_module_names`` should return the same set of module
    names — the bundled manifests are byte-identical snapshots of the source
    manifests (checked by ``make check-manifest-sync``), and the same
    ``module.yml`` discovery logic applies to both paths.

    The strong superset direction is source ⊇ bundled; in the monorepo,
    they must be equal.
    """

    def test_bundled_is_subset_of_shipped(self) -> None:
        """Every bundled module must also exist in the shipped source (G4)."""
        shipped_names = set(discover_shipped_module_names())
        bundled_names = set(discover_bundled_module_names())
        extra_in_bundled = bundled_names - shipped_names
        assert not extra_in_bundled, (
            f"Bundled manifests contain modules not found in source: "
            f"{sorted(extra_in_bundled)}. "
            "Run `make manifest-sync` to snapshot new source modules, or "
            "remove orphan bundled entries."
        )

    def test_shipped_is_subset_of_bundled(self) -> None:
        """Every shipped module must also have a bundled snapshot (G4)."""
        shipped_names = set(discover_shipped_module_names())
        bundled_names = set(discover_bundled_module_names())
        missing_in_bundled = shipped_names - bundled_names
        assert not missing_in_bundled, (
            f"Shipped modules missing bundled snapshot: "
            f"{sorted(missing_in_bundled)}. "
            "Run `make manifest-sync` to create missing bundled snapshots."
        )

    def test_inventory_exact_match(self) -> None:
        """Source and bundled inventories must be identical in the monorepo."""
        shipped_names = discover_shipped_module_names()
        bundled_names = discover_bundled_module_names()
        assert shipped_names == bundled_names, (
            "Source and bundled module inventories differ:\n"
            f"  Only in source: {sorted(set(shipped_names) - set(bundled_names))}\n"
            f"  Only in bundled: {sorted(set(bundled_names) - set(shipped_names))}"
        )
