"""Additional tests for manifest loader error paths not covered by existing tests."""

from pathlib import Path
from unittest.mock import patch

import pytest

from quickscale_core.manifest.loader import (
    ManifestError,
    load_manifest,
    load_manifest_from_path,
    get_manifest_for_module,
)


class TestLoadManifestEdgeCases:
    """Tests for load_manifest covering previously uncovered error branches."""

    def test_load_manifest_non_dict_yaml_raises(self) -> None:
        """YAML that is not a mapping (e.g., a plain string) raises ManifestError."""
        with pytest.raises(ManifestError, match="YAML mapping"):
            load_manifest("just a string", "testmod")

    def test_load_manifest_yaml_list_raises(self) -> None:
        """YAML that is a list raises ManifestError."""
        with pytest.raises(ManifestError, match="YAML mapping"):
            load_manifest("- item1\n- item2", "testmod")

    def test_load_manifest_missing_version_raises(self) -> None:
        """Manifest without a version field raises ManifestError."""
        yaml_content = "name: mymod\ndescription: no version"
        with pytest.raises(ManifestError, match="version"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_empty_version_raises(self) -> None:
        """Manifest with an empty version string raises ManifestError."""
        yaml_content = "name: mymod\nversion: ''"
        with pytest.raises(ManifestError, match="version"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_non_string_version_raises(self) -> None:
        """Manifest with a non-string version raises ManifestError."""
        yaml_content = "name: mymod\nversion: 123"
        with pytest.raises(ManifestError):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_config_not_dict_raises(self) -> None:
        """Top-level config that is not a mapping raises ManifestError."""
        yaml_content = "name: mymod\nversion: '1.0.0'\nconfig: not_a_dict"
        with pytest.raises(ManifestError, match="config"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_mutable_section_not_dict_raises(self) -> None:
        """config.mutable that is a string (not a mapping) raises ManifestError."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\nconfig:\n  mutable: not_a_mapping\n"
        )
        with pytest.raises(ManifestError, match="mutable"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_immutable_section_not_dict_raises(self) -> None:
        """config.immutable that is a list raises ManifestError."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\nconfig:\n  immutable:\n    - item\n"
        )
        with pytest.raises(ManifestError, match="immutable"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_option_data_not_dict_raises(self) -> None:
        """A config option whose value is a plain string raises ManifestError."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n    my_option: not_a_mapping\n"
        )
        with pytest.raises(ManifestError):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_error_includes_module_name(self) -> None:
        """ManifestError message includes the module name when provided."""
        with pytest.raises(ManifestError) as exc_info:
            load_manifest("just a string", "my_module")
        assert "my_module" in str(exc_info.value)

    def test_load_manifest_error_without_module_name(self) -> None:
        """ManifestError without module name formats cleanly."""
        with pytest.raises(ManifestError) as exc_info:
            load_manifest("just a string")
        # Should not crash; message should still describe the error
        assert "YAML mapping" in str(exc_info.value)

    def test_load_manifest_dependencies_not_list_raises(self) -> None:
        """dependencies field that is not a list raises ManifestError."""
        yaml_content = "name: mymod\nversion: '1.0.0'\ndependencies: not_a_list\n"
        with pytest.raises(ManifestError, match="dependencies"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_django_apps_not_list_raises(self) -> None:
        """django_apps field that is not a list raises ManifestError."""
        yaml_content = "name: mymod\nversion: '1.0.0'\ndjango_apps: not_a_list\n"
        with pytest.raises(ManifestError, match="django_apps"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_option_none_value_allowed(self) -> None:
        """A config option with null/None value is accepted (treated as empty dict)."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\nconfig:\n  immutable:\n    my_option:\n"
        )
        manifest = load_manifest(yaml_content, "mymod")
        assert "my_option" in manifest.immutable_options


class TestLoadManifestFromPathEdgeCases:
    """Tests for load_manifest_from_path covering OSError branch."""

    def test_load_from_path_read_error_raises(self, tmp_path: Path) -> None:
        """OSError while reading the file raises ManifestError."""
        manifest_path = tmp_path / "auth" / "module.yml"
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text("name: auth\nversion: '1.0.0'\n")

        with patch("pathlib.Path.read_text", side_effect=OSError("disk error")):
            with pytest.raises(ManifestError, match="Failed to read manifest"):
                load_manifest_from_path(manifest_path)

    def test_load_from_path_uses_parent_name_as_module_name(
        self, tmp_path: Path
    ) -> None:
        """Module name in errors is taken from the manifest's parent directory name."""
        module_dir = tmp_path / "my_module"
        module_dir.mkdir()
        manifest_path = module_dir / "module.yml"
        # Write invalid YAML to trigger an error that includes the module name
        manifest_path.write_text("just a string")

        with pytest.raises(ManifestError) as exc_info:
            load_manifest_from_path(manifest_path)
        assert "my_module" in str(exc_info.value)


class TestGetManifestForModuleEdgeCases:
    """Tests for get_manifest_for_module covering the ManifestError suppression."""

    def test_get_manifest_returns_none_on_manifest_error(self, tmp_path: Path) -> None:
        """If the manifest file exists but is invalid, None is returned silently."""
        project_path = tmp_path / "project"
        module_dir = project_path / "modules" / "broken"
        module_dir.mkdir(parents=True)
        # Write invalid YAML content (not a mapping)
        (module_dir / "module.yml").write_text("- invalid\n- list\n")

        result = get_manifest_for_module(project_path, "broken")
        assert result is None

    def test_get_manifest_returns_none_when_not_found(self, tmp_path: Path) -> None:
        """Returns None when module directory does not contain a manifest file."""
        project_path = tmp_path / "project"
        project_path.mkdir()

        result = get_manifest_for_module(project_path, "nonexistent")
        assert result is None
