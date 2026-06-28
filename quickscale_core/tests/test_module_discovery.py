"""Tests for manifest-backed module discovery.

These tests verify that the discovery functions correctly enumerate shipped
modules by scanning the repository's ``quickscale_modules/*/module.yml``
files, exclude placeholder directories, and provide the expected fail-closed
rejection path.
"""

from __future__ import annotations

from importlib import resources as _resources
from pathlib import Path

import pytest

from django.core.exceptions import ImproperlyConfigured

from quickscale_core.contracts.module_discovery import (
    PLACEHOLDER_MODULE_NAMES,
    discover_shipped_module_names,
    discover_shipped_module_paths,
    get_modules_base_path,
    get_placeholder_rejection_reason,
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

    def test_bundled_manifests_path_not_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``get_modules_base_path`` does **not** fall through to the bundled
        manifests path — the bundled context is not a supported fallback
        (AF7 decision).  Raises ``ImproperlyConfigured`` even when the
        bundled manifests directory exists.
        """
        from quickscale_core.contracts import module_discovery as _md

        original_override = _md._modules_base_path
        _md._modules_base_path = None

        try:
            # Calculate the monorepo path that ``get_modules_base_path``
            # checks first so we can make it appear non-existent.
            monorepo_path = (
                Path(_md.__file__).resolve().parents[4] / "quickscale_modules"
            )

            # Monkeypatch ``Path.is_dir`` to return ``False`` only for the
            # monorepo path, proving the function raises rather than falling
            # through to any bundled path.
            _real_is_dir = Path.is_dir

            def _selective_is_dir(self: Path) -> bool:
                if str(self.resolve()) == str(monorepo_path.resolve()):
                    return False
                return _real_is_dir(self)

            monkeypatch.setattr(Path, "is_dir", _selective_is_dir)

            with pytest.raises(
                ImproperlyConfigured, match="Modules base path not found"
            ):
                _md.get_modules_base_path()
        finally:
            _md._modules_base_path = original_override

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
