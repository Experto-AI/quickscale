"""Additional tests for settings_manager covering uncovered branches."""

from pathlib import Path

import pytest

from quickscale_core.settings_manager import (
    _python_value_to_string,
    _resolve_package_name,
    apply_mutable_config_changes,
    SettingsError,
)


class TestResolvePackageName:
    """Tests for _resolve_package_name covering the state.yml path and error cases."""

    def test_resolve_package_name_from_quickscale_yml(self, tmp_path: Path) -> None:
        """Resolves package name from quickscale.yml successfully."""
        project_path = tmp_path / "myproject"
        project_path.mkdir()
        (project_path / "quickscale.yml").write_text("project:\n  package: mypackage\n")
        assert _resolve_package_name(project_path) == "mypackage"

    def test_resolve_package_name_from_state_yml(self, tmp_path: Path) -> None:
        """Falls back to .quickscale/state.yml when quickscale.yml is missing."""
        project_path = tmp_path / "myproject"
        project_path.mkdir()
        state_dir = project_path / ".quickscale"
        state_dir.mkdir()
        (state_dir / "state.yml").write_text("project:\n  package: state_package\n")
        assert _resolve_package_name(project_path) == "state_package"

    def test_resolve_package_name_state_yml_takes_effect_when_yml_missing_package(
        self, tmp_path: Path
    ) -> None:
        """Falls back to state.yml when quickscale.yml exists but has no package key."""
        project_path = tmp_path / "myproject"
        project_path.mkdir()
        # quickscale.yml exists but no package field
        (project_path / "quickscale.yml").write_text("project:\n  slug: myproject\n")
        state_dir = project_path / ".quickscale"
        state_dir.mkdir()
        (state_dir / "state.yml").write_text("project:\n  package: fallback_pkg\n")
        assert _resolve_package_name(project_path) == "fallback_pkg"

    def test_resolve_package_name_raises_when_no_config(self, tmp_path: Path) -> None:
        """SettingsError is raised when neither config file provides a package."""
        project_path = tmp_path / "empty_project"
        project_path.mkdir()
        with pytest.raises(SettingsError, match="Unable to resolve project package"):
            _resolve_package_name(project_path)

    def test_resolve_package_name_raises_when_both_missing_package(
        self, tmp_path: Path
    ) -> None:
        """SettingsError raised when both files exist but neither has package."""
        project_path = tmp_path / "myproject"
        project_path.mkdir()
        (project_path / "quickscale.yml").write_text("project:\n  slug: myproject\n")
        state_dir = project_path / ".quickscale"
        state_dir.mkdir()
        (state_dir / "state.yml").write_text("project:\n  slug: myproject\n")
        with pytest.raises(SettingsError):
            _resolve_package_name(project_path)

    def test_resolve_package_name_quickscale_yml_invalid_yaml_falls_back(
        self, tmp_path: Path
    ) -> None:
        """Invalid YAML in quickscale.yml causes fallback to state.yml."""
        project_path = tmp_path / "myproject"
        project_path.mkdir()
        # Invalid YAML - will raise exception in the try block
        (project_path / "quickscale.yml").write_text(
            "project:\n  package: [invalid yaml\n"
        )
        state_dir = project_path / ".quickscale"
        state_dir.mkdir()
        (state_dir / "state.yml").write_text("project:\n  package: recovered_package\n")
        assert _resolve_package_name(project_path) == "recovered_package"

    def test_resolve_package_name_state_yml_invalid_yaml_raises(
        self, tmp_path: Path
    ) -> None:
        """Invalid YAML in state.yml (and no quickscale.yml) raises SettingsError."""
        project_path = tmp_path / "myproject"
        project_path.mkdir()
        state_dir = project_path / ".quickscale"
        state_dir.mkdir()
        (state_dir / "state.yml").write_text("project:\n  package: [invalid yaml\n")
        with pytest.raises(SettingsError):
            _resolve_package_name(project_path)


class TestPythonValueToStringEdgeCases:
    """Tests for _python_value_to_string covering the repr() fallback."""

    def test_repr_fallback_for_custom_object(self) -> None:
        """Custom objects that are not standard types fall back to repr()."""

        class CustomObj:
            def __repr__(self) -> str:
                return "CustomObj()"

        result = _python_value_to_string(CustomObj())
        assert result == "CustomObj()"

    def test_repr_fallback_for_bytes(self) -> None:
        """Bytes objects use repr() fallback."""
        result = _python_value_to_string(b"hello")
        assert result == repr(b"hello")

    def test_repr_fallback_for_tuple(self) -> None:
        """Tuples (not a special-cased type) use repr() fallback."""
        result = _python_value_to_string((1, 2, 3))
        assert result == repr((1, 2, 3))


class TestApplyMutableConfigChangesLegacyPaths:
    """Tests for apply_mutable_config_changes legacy settings file paths."""

    def test_apply_changes_uses_legacy_settings_py_when_base_missing(
        self, tmp_path: Path
    ) -> None:
        """Falls back to package/settings.py when package/settings/base.py not found."""
        project_path = tmp_path / "myproject"
        project_path.mkdir()
        (project_path / "quickscale.yml").write_text("project:\n  package: mypackage\n")
        # Create legacy single-file settings layout
        pkg_dir = project_path / "mypackage"
        pkg_dir.mkdir()
        settings_file = pkg_dir / "settings.py"
        settings_file.write_text("DEBUG = True\n")

        results = apply_mutable_config_changes(project_path, "mymod", {"DEBUG": False})

        assert len(results) == 1
        name, success, _msg = results[0]
        assert success is True
        assert "DEBUG = False" in settings_file.read_text()

    def test_apply_changes_returns_failure_when_no_settings_file(
        self, tmp_path: Path
    ) -> None:
        """Returns failure result when neither settings/base.py nor settings.py exist."""
        project_path = tmp_path / "myproject"
        project_path.mkdir()
        (project_path / "quickscale.yml").write_text("project:\n  package: mypackage\n")
        # Create package dir but NO settings file
        (project_path / "mypackage").mkdir()

        results = apply_mutable_config_changes(
            project_path, "mymod", {"SOME_SETTING": "value"}
        )

        assert len(results) == 1
        _name, success, msg = results[0]
        assert success is False
        assert "not found" in msg.lower() or "settings" in msg.lower()

    def test_apply_changes_returns_failure_when_package_unresolvable(
        self, tmp_path: Path
    ) -> None:
        """Returns failure result when project identity cannot be resolved."""
        project_path = tmp_path / "empty"
        project_path.mkdir()
        # No quickscale.yml or state.yml

        results = apply_mutable_config_changes(
            project_path, "mymod", {"SOME_SETTING": "value"}
        )

        assert len(results) == 1
        _name, success, msg = results[0]
        assert success is False
        assert "Unable to resolve" in msg
