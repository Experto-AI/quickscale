"""Tests for manifest loader"""

import pytest
from pathlib import Path

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
