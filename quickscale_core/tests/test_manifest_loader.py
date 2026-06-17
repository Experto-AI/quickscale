from pathlib import Path
from unittest.mock import patch

import pytest

from quickscale_core.manifest.loader import (
    ManifestError,
    load_manifest,
    load_manifest_from_path,
    get_manifest_for_module,
)


class TestLoadManifest:
    """Tests for load_manifest function"""

    def test_load_basic_manifest(self) -> None:
        """Test loading a basic manifest"""
        yaml_content = """
name: auth
version: "0.71.0"
description: Authentication module

config:
  mutable:
    registration_enabled:
      type: boolean
      default: true
      django_setting: ACCOUNT_ALLOW_REGISTRATION
      description: Allow new user signups

  immutable:
    authentication_method:
      type: string
      default: email_username
      description: How users authenticate
"""
        manifest = load_manifest(yaml_content, "auth")

        assert manifest.name == "auth"
        assert manifest.version == "0.71.0"
        assert len(manifest.mutable_options) == 1
        assert len(manifest.immutable_options) == 1

        mutable = manifest.mutable_options["registration_enabled"]
        assert mutable.name == "registration_enabled"
        assert mutable.option_type == "boolean"
        assert mutable.default is True
        assert mutable.django_setting == "ACCOUNT_ALLOW_REGISTRATION"
        assert mutable.is_mutable is True

        immutable = manifest.immutable_options["authentication_method"]
        assert immutable.name == "authentication_method"
        assert immutable.option_type == "string"
        assert immutable.default == "email_username"
        assert immutable.is_mutable is False

    def test_load_manifest_no_options(self) -> None:
        """Test loading manifest with no options"""
        yaml_content = """
name: minimal
version: "1.0.0"
description: Minimal module
"""
        manifest = load_manifest(yaml_content, "minimal")

        assert manifest.name == "minimal"
        assert manifest.mutable_options == {}
        assert manifest.immutable_options == {}

    def test_load_manifest_mutable_without_django_setting(self) -> None:
        """Test that mutable options without django_setting raise error"""
        yaml_content = """
name: invalid
version: "1.0.0"

config:
  mutable:
    some_option:
      type: boolean
      default: true
      # Missing django_setting - should error
"""
        with pytest.raises(ManifestError) as exc_info:
            load_manifest(yaml_content, "invalid")

        assert "django_setting" in str(exc_info.value).lower()

    def test_load_manifest_invalid_yaml(self) -> None:
        """Test loading invalid YAML raises error"""
        yaml_content = """
name: test
version: [invalid yaml
"""
        with pytest.raises(ManifestError):
            load_manifest(yaml_content, "test")

    def test_load_manifest_missing_name(self) -> None:
        """Test loading manifest without name raises error"""
        yaml_content = """
version: "1.0.0"
description: Module without name
"""
        with pytest.raises(ManifestError) as exc_info:
            load_manifest(yaml_content, "fallback_name")
        assert "name" in str(exc_info.value).lower()

    def test_load_manifest_non_dict_yaml_raises(self) -> None:
        """YAML that is not a mapping raises ManifestError."""
        with pytest.raises(ManifestError, match="YAML mapping"):
            load_manifest("just a string", "testmod")

    def test_load_manifest_yaml_list_raises(self) -> None:
        """YAML list payloads should also fail manifest parsing."""
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
        """config.mutable must be a mapping."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\nconfig:\n  mutable: not_a_mapping\n"
        )
        with pytest.raises(ManifestError, match="mutable"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_immutable_section_not_dict_raises(self) -> None:
        """config.immutable must be a mapping."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\nconfig:\n  immutable:\n    - item\n"
        )
        with pytest.raises(ManifestError, match="immutable"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_option_data_not_dict_raises(self) -> None:
        """Each option payload must be a mapping when present."""
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
        assert "YAML mapping" in str(exc_info.value)

    def test_load_manifest_dependencies_not_list_raises(self) -> None:
        """dependencies field that is not a list raises ManifestError."""
        yaml_content = "name: mymod\nversion: '1.0.0'\ndependencies: not_a_list\n"
        with pytest.raises(ManifestError, match="dependencies"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_required_modules_not_list_raises(self) -> None:
        """required_modules field that is not a list raises ManifestError."""
        yaml_content = "name: mymod\nversion: '1.0.0'\nrequired_modules: not_a_list\n"
        with pytest.raises(ManifestError, match="required_modules"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_required_modules_round_trip(self) -> None:
        """required_modules should be preserved on the loaded manifest."""
        yaml_content = "name: mymod\nversion: '1.0.0'\nrequired_modules:\n  - orgs\n"

        manifest = load_manifest(yaml_content, "mymod")

        assert manifest.required_modules == ["orgs"]

    def test_load_manifest_django_apps_not_list_raises(self) -> None:
        """django_apps field that is not a list raises ManifestError."""
        yaml_content = "name: mymod\nversion: '1.0.0'\ndjango_apps: not_a_list\n"
        with pytest.raises(ManifestError, match="django_apps"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_option_none_value_allowed(self) -> None:
        """A config option with null/None value is accepted."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\nconfig:\n  immutable:\n    my_option:\n"
        )
        manifest = load_manifest(yaml_content, "mymod")
        assert "my_option" in manifest.immutable_options


class TestLoadManifestFromPath:
    """Tests for load_manifest_from_path function"""

    def test_load_from_file(self, tmp_path: Path) -> None:
        """Test loading manifest from file path"""
        yaml_content = """
name: test
version: "1.0.0"
config:
  mutable:
    enabled:
      type: boolean
      default: true
      django_setting: TEST_ENABLED
"""
        manifest_path = tmp_path / "module.yml"
        manifest_path.write_text(yaml_content)

        manifest = load_manifest_from_path(manifest_path)
        assert manifest.name == "test"
        assert manifest.version == "1.0.0"
        assert len(manifest.mutable_options) == 1

    def test_load_from_nonexistent_file(self, tmp_path: Path) -> None:
        """Test loading from non-existent file raises error"""
        fake_path = tmp_path / "nonexistent.yml"

        with pytest.raises(ManifestError) as exc_info:
            load_manifest_from_path(fake_path)

        assert "not found" in str(exc_info.value).lower()

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
        """Module name in errors is taken from the parent directory name."""
        module_dir = tmp_path / "my_module"
        module_dir.mkdir()
        manifest_path = module_dir / "module.yml"
        manifest_path.write_text("just a string")

        with pytest.raises(ManifestError) as exc_info:
            load_manifest_from_path(manifest_path)
        assert "my_module" in str(exc_info.value)


class TestGetManifestForModule:
    """Tests for get_manifest_for_module function"""

    def test_get_manifest_from_modules_dir(self, tmp_path: Path) -> None:
        """Test getting manifest from modules/<name>/module.yml"""
        # Create project structure
        project_path = tmp_path / "myproject"
        project_path.mkdir()
        modules_dir = project_path / "modules" / "auth"
        modules_dir.mkdir(parents=True)

        yaml_content = """
name: auth
version: "0.71.0"
config:
  mutable:
    test_option:
      type: string
      default: "test"
      django_setting: TEST_SETTING
"""
        manifest_path = modules_dir / "module.yml"
        manifest_path.write_text(yaml_content)

        manifest = get_manifest_for_module(project_path, "auth")
        assert manifest is not None
        assert manifest.name == "auth"

    def test_get_manifest_not_found(self, tmp_path: Path) -> None:
        """Test getting manifest for module without manifest file"""
        project_path = tmp_path / "myproject"
        project_path.mkdir()

        manifest = get_manifest_for_module(project_path, "nonexistent")
        assert manifest is None

    def test_get_manifest_not_found_strict_raises(self, tmp_path: Path) -> None:
        """Strict mode should fail when module.yml is missing."""
        project_path = tmp_path / "myproject"
        project_path.mkdir()

        with pytest.raises(ManifestError, match="Manifest file not found"):
            get_manifest_for_module(project_path, "nonexistent", strict=True)

    def test_get_manifest_invalid_strict_raises(self, tmp_path: Path) -> None:
        """Strict mode should surface invalid embedded manifests."""
        project_path = tmp_path / "myproject"
        module_dir = project_path / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text("- invalid\n- list\n")

        with pytest.raises(ManifestError, match="auth"):
            get_manifest_for_module(project_path, "auth", strict=True)

    def test_get_manifest_from_nested_src(self, tmp_path: Path) -> None:
        """Test getting manifest from src/module/module.yml pattern"""
        # Create project structure with src layout
        project_path = tmp_path / "myproject"
        project_path.mkdir()
        src_dir = project_path / "modules" / "auth" / "src" / "quickscale_modules_auth"
        src_dir.mkdir(parents=True)

        yaml_content = """
name: auth
version: "0.71.0"
"""
        # Manifest in module root
        manifest_path = project_path / "modules" / "auth" / "module.yml"
        manifest_path.write_text(yaml_content)

        manifest = get_manifest_for_module(project_path, "auth")
        assert manifest is not None
        assert manifest.name == "auth"

    def test_get_manifest_returns_none_on_manifest_error(self, tmp_path: Path) -> None:
        """If the manifest file exists but is invalid, None is returned silently."""
        project_path = tmp_path / "project"
        module_dir = project_path / "modules" / "broken"
        module_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text("- invalid\n- list\n")

        result = get_manifest_for_module(project_path, "broken")
        assert result is None


# ---------------------------------------------------------------------------
# Managed files parsing
# ---------------------------------------------------------------------------


class TestLoadManifestManagedFiles:
    """Tests for the managed_files section in load_manifest."""

    def test_no_managed_files_section(self) -> None:
        """Manifests without managed_files produce an empty dict."""
        yaml_content = "name: mymod\nversion: '1.0.0'\n"
        manifest = load_manifest(yaml_content, "mymod")
        assert manifest.managed_files == {}

    def test_empty_managed_files_section(self) -> None:
        """An empty managed_files section is accepted."""
        yaml_content = "name: mymod\nversion: '1.0.0'\nmanaged_files: {}\n"
        manifest = load_manifest(yaml_content, "mymod")
        assert manifest.managed_files == {}

    def test_valid_managed_files(self) -> None:
        """Valid managed_files entries are parsed correctly."""
        yaml_content = """
name: social
version: "0.79.0"
managed_files:
  social_link_tree:
    renderer: social/link_tree.html
    output_path: quickscale_managed/social/link_tree.html
  social_embeds:
    renderer: social/embeds.html
    output_path: quickscale_managed/social/embeds.html
"""
        manifest = load_manifest(yaml_content, "social")
        assert len(manifest.managed_files) == 2
        assert "social_link_tree" in manifest.managed_files
        decl = manifest.managed_files["social_link_tree"]
        assert decl.key == "social_link_tree"
        assert decl.renderer == "social/link_tree.html"
        assert decl.output_path == "quickscale_managed/social/link_tree.html"

    def test_managed_files_not_mapping_raises(self) -> None:
        """managed_files that is not a mapping raises ManifestError."""
        yaml_content = "name: mymod\nversion: '1.0.0'\nmanaged_files: not_a_mapping\n"
        with pytest.raises(ManifestError, match="managed_files"):
            load_manifest(yaml_content, "mymod")

    def test_managed_files_entry_not_mapping_raises(self) -> None:
        """A managed_files entry that is not a mapping raises ManifestError."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\nmanaged_files:\n  my_file: not_a_mapping\n"
        )
        with pytest.raises(ManifestError, match="managed_files.my_file"):
            load_manifest(yaml_content, "mymod")

    def test_managed_files_missing_renderer_raises(self) -> None:
        """A managed_files entry without renderer raises ManifestError."""
        yaml_content = """
name: mymod
version: '1.0.0'
managed_files:
  my_file:
    output_path: quickscale_managed/f.html
"""
        with pytest.raises(ManifestError, match="renderer"):
            load_manifest(yaml_content, "mymod")

    def test_managed_files_empty_renderer_raises(self) -> None:
        """A managed_files entry with empty renderer raises ManifestError."""
        yaml_content = """
name: mymod
version: '1.0.0'
managed_files:
  my_file:
    renderer: ""
    output_path: quickscale_managed/f.html
"""
        with pytest.raises(ManifestError, match="renderer"):
            load_manifest(yaml_content, "mymod")

    def test_managed_files_missing_output_path_raises(self) -> None:
        """A managed_files entry without output_path raises ManifestError."""
        yaml_content = """
name: mymod
version: '1.0.0'
managed_files:
  my_file:
    renderer: some_renderer
"""
        with pytest.raises(ManifestError, match="output_path"):
            load_manifest(yaml_content, "mymod")

    def test_managed_files_path_outside_managed_root_raises(self) -> None:
        """A managed_files entry with path outside quickscale_managed/ raises."""
        yaml_content = """
name: mymod
version: '1.0.0'
managed_files:
  my_file:
    renderer: some_renderer
    output_path: templates/escaped.html
"""
        with pytest.raises(ManifestError, match="quickscale_managed/"):
            load_manifest(yaml_content, "mymod")

    def test_managed_files_path_traversal_raises(self) -> None:
        """Path traversal attempts outside quickscale_managed/ are rejected."""
        yaml_content = """
name: mymod
version: '1.0.0'
managed_files:
  my_file:
    renderer: some_renderer
    output_path: quickscale_managed/../etc/passwd
"""
        with pytest.raises(ManifestError, match="quickscale_managed/"):
            load_manifest(yaml_content, "mymod")

    def test_managed_files_entry_with_none_value_accepted(self) -> None:
        """A managed_files entry with null value is treated as empty mapping.

        This matches the config option behavior where null values are
        accepted as empty mappings.
        """
        yaml_content = """
name: mymod
version: '1.0.0'
managed_files:
  my_file:
"""
        # Should raise because renderer is required
        with pytest.raises(ManifestError, match="renderer"):
            load_manifest(yaml_content, "mymod")
