from pathlib import Path
from unittest.mock import patch

import pytest

from quickscale_core.manifest.loader import (
    ManifestError,
    load_manifest,
    load_manifest_from_path,
    get_manifest_for_module,
)
from quickscale_core.manifest.schema import ImpliesEntry


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
# ModuleVersionMismatchError and assert_manifest_version_matches_core
# ---------------------------------------------------------------------------


class TestModuleVersionMismatch:
    """Tests for ModuleVersionMismatchError and assert_manifest_version_matches_core."""

    def test_mismatch_error_is_runtime_error_not_manifest_error(self) -> None:
        """ModuleVersionMismatchError must be a RuntimeError, not ManifestError."""
        from quickscale_core.manifest.loader import ModuleVersionMismatchError

        with pytest.raises(RuntimeError) as exc_info:
            raise ModuleVersionMismatchError("test error")
        assert not issubclass(ModuleVersionMismatchError, ManifestError)
        assert str(exc_info.value) == "test error"

    def test_pass_when_manifest_matches_core(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """assert_manifest_version_matches_core passes when versions match."""
        from quickscale_core.manifest.loader import (
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "0.87.0",
        )

        # Same version — must not raise.
        assert_manifest_version_matches_core("0.87.0", "auth")

    def test_reject_when_manifest_newer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A manifest newer than the core version must be rejected (strict equality)."""
        from quickscale_core.manifest.loader import (
            ModuleVersionMismatchError,
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "0.86.0",
        )

        with pytest.raises(ModuleVersionMismatchError):
            assert_manifest_version_matches_core("0.87.0", "auth")

    def test_raise_on_mismatch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A manifest older than the core version must raise."""
        from quickscale_core.manifest.loader import (
            ModuleVersionMismatchError,
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "0.87.0",
        )

        with pytest.raises(ModuleVersionMismatchError):
            assert_manifest_version_matches_core("0.86.0", "auth")

    def test_mismatch_message_format(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Error message matches the stable format."""
        from quickscale_core.manifest.loader import (
            ModuleVersionMismatchError,
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "0.87.0",
        )

        with pytest.raises(ModuleVersionMismatchError) as exc_info:
            assert_manifest_version_matches_core("0.86.0", "auth")

        msg = str(exc_info.value)
        assert "Module 'auth' version mismatch:" in msg
        assert "found 0.86.0" in msg
        assert "expected core version 0.87.0" in msg

    def test_empty_version_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty manifest version must be rejected (strict equality)."""
        from quickscale_core.manifest.loader import (
            ModuleVersionMismatchError,
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "0.87.0",
        )

        with pytest.raises(ModuleVersionMismatchError):
            assert_manifest_version_matches_core("", "auth")

    def test_whitespace_version_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Whitespace-only manifest version must be rejected."""
        from quickscale_core.manifest.loader import (
            ModuleVersionMismatchError,
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "0.87.0",
        )

        with pytest.raises(ModuleVersionMismatchError):
            assert_manifest_version_matches_core("  ", "auth")

    def test_unparseable_version_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unparseable manifest version (e.g. 'abc') must be rejected."""
        from quickscale_core.manifest.loader import (
            ModuleVersionMismatchError,
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "0.87.0",
        )

        with pytest.raises(ModuleVersionMismatchError):
            assert_manifest_version_matches_core("abc", "auth")

    def test_single_component_version_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A single-component version like '0' must be rejected."""
        from quickscale_core.manifest.loader import (
            ModuleVersionMismatchError,
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "0.87.0",
        )

        with pytest.raises(ModuleVersionMismatchError):
            assert_manifest_version_matches_core("0", "auth")

    def test_prerelease_version_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Pre-release suffixes like '0.87.0-alpha' must be rejected
        (literal string equality — alpha does not equal the core version)."""
        from quickscale_core.manifest.loader import (
            ModuleVersionMismatchError,
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "0.87.0",
        )

        with pytest.raises(ModuleVersionMismatchError):
            assert_manifest_version_matches_core("0.87.0-alpha", "auth")

    # ------------------------------------------------------------------
    # SA117a: lockstep canonical version parser — private parser tests
    # ------------------------------------------------------------------

    def test_leading_zero_component_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Leading-zero components like '0.87.00' must be rejected (not
        canonical: canonical form would be 0.87.0)."""
        from quickscale_core.manifest.loader import (
            ModuleVersionMismatchError,
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "0.87.0",
        )

        with pytest.raises(ModuleVersionMismatchError):
            assert_manifest_version_matches_core("0.87.00", "auth")

    def test_whitespace_padded_version_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Whitespace-padded manifest version ' 0.87.0 ' must be rejected.
        The lockstep parser does not strip before canonical comparison."""
        from quickscale_core.manifest.loader import (
            ModuleVersionMismatchError,
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "0.87.0",
        )

        with pytest.raises(ModuleVersionMismatchError):
            assert_manifest_version_matches_core(" 0.87.0 ", "auth")

    def test_two_component_version_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A two-component version like '0.87' must be rejected (needs
        exactly 3 dot-separated components)."""
        from quickscale_core.manifest.loader import (
            ModuleVersionMismatchError,
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "0.87.0",
        )

        with pytest.raises(ModuleVersionMismatchError):
            assert_manifest_version_matches_core("0.87", "auth")

    def test_four_component_version_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A four-component version like '0.87.0.1' must be rejected."""
        from quickscale_core.manifest.loader import (
            ModuleVersionMismatchError,
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "0.87.0",
        )

        with pytest.raises(ModuleVersionMismatchError):
            assert_manifest_version_matches_core("0.87.0.1", "auth")

    def test_non_decimal_component_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A component that is not pure decimal like '0.87.0a' must be rejected."""
        from quickscale_core.manifest.loader import (
            ModuleVersionMismatchError,
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "0.87.0",
        )

        with pytest.raises(ModuleVersionMismatchError):
            assert_manifest_version_matches_core("0.87.0a", "auth")

    def test_canonical_manifest_with_different_minor_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A canonical but different version (0.88.0) must be rejected,
        proving triple comparison is semantic, not string-equality-only."""
        from quickscale_core.manifest.loader import (
            ModuleVersionMismatchError,
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "0.87.0",
        )

        with pytest.raises(ModuleVersionMismatchError):
            assert_manifest_version_matches_core("0.88.0", "auth")

    # ------------------------------------------------------------------
    # SA117a-CR-001: ASCII-only-digit invariant, no-strip, complete
    # expected strings including malformed core
    # ------------------------------------------------------------------

    def test_noncanonical_version_complete_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-canonical (leading-zero) version produces the exact
        complete message with raw manifest and core spellings."""
        from quickscale_core.manifest.loader import (
            ModuleVersionMismatchError,
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "0.87.0",
        )

        with pytest.raises(ModuleVersionMismatchError) as exc_info:
            assert_manifest_version_matches_core("0.87.00", "auth")

        assert str(exc_info.value) == (
            "Module 'auth' version mismatch: "
            "found 0.87.00; expected core version 0.87.0."
        )

    def test_mismatch_complete_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Canonical-but-mismatched version produces the exact complete
        message with raw manifest and core spellings."""
        from quickscale_core.manifest.loader import (
            ModuleVersionMismatchError,
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "0.87.0",
        )

        with pytest.raises(ModuleVersionMismatchError) as exc_info:
            assert_manifest_version_matches_core("0.86.0", "auth")

        assert str(exc_info.value) == (
            "Module 'auth' version mismatch: "
            "found 0.86.0; expected core version 0.87.0."
        )

    def test_malformed_core_complete_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the core version itself is non-canonical, the complete
        message preserves the raw core spelling exactly as-is."""
        from quickscale_core.manifest.loader import (
            ModuleVersionMismatchError,
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "0.87.00",
        )

        with pytest.raises(ModuleVersionMismatchError) as exc_info:
            assert_manifest_version_matches_core("0.87.0", "auth")

        assert str(exc_info.value) == (
            "Module 'auth' version mismatch: "
            "found 0.87.0; expected core version 0.87.00."
        )

    def test_signed_positive_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A signed positive version '+1.2.3' must be rejected (ASCII
        digit check before int() would strip '+' sign)."""
        from quickscale_core.manifest.loader import (
            ModuleVersionMismatchError,
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "0.87.0",
        )

        with pytest.raises(ModuleVersionMismatchError):
            assert_manifest_version_matches_core("+1.2.3", "auth")

    def test_signed_negative_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A signed negative version '-1.2.3' must be rejected."""
        from quickscale_core.manifest.loader import (
            ModuleVersionMismatchError,
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "0.87.0",
        )

        with pytest.raises(ModuleVersionMismatchError):
            assert_manifest_version_matches_core("-1.2.3", "auth")

    def test_unicode_digit_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A version containing Unicode digits (Arabic-Indic ١) must be
        rejected by the ASCII-only check before int()."""
        from quickscale_core.manifest.loader import (
            ModuleVersionMismatchError,
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "0.87.0",
        )

        with pytest.raises(ModuleVersionMismatchError):
            assert_manifest_version_matches_core("١.2.3", "auth")

    def test_empty_component_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A version with an empty component '0..1' must be rejected."""
        from quickscale_core.manifest.loader import (
            ModuleVersionMismatchError,
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "0.87.0",
        )

        with pytest.raises(ModuleVersionMismatchError):
            assert_manifest_version_matches_core("0..1", "auth")

    def test_whitespace_component_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A version with whitespace in a component '0.87.0 ' must be
        rejected (trailing space after last component)."""
        from quickscale_core.manifest.loader import (
            ModuleVersionMismatchError,
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "0.87.0",
        )

        with pytest.raises(ModuleVersionMismatchError):
            assert_manifest_version_matches_core("0.87.0 ", "auth")

    def test_whitespace_only_version_uses_repr_in_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A whitespace-only version ('   ') produces repr in the
        error message (the !r format for empty/invalid inputs)."""
        from quickscale_core.manifest.loader import (
            ModuleVersionMismatchError,
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "0.87.0",
        )

        with pytest.raises(ModuleVersionMismatchError) as exc_info:
            assert_manifest_version_matches_core("   ", "auth")

        msg = str(exc_info.value)
        # Whitespace-only uses repr: found '   '
        assert "found " in msg
        assert "expected core version 0.87.0" in msg

    # ------------------------------------------------------------------
    # SA117-CR-001: exact complete-string message assertions for
    # signed/Unicode/empty manifest versions and monkeypatched core.
    # ------------------------------------------------------------------

    def test_signed_positive_complete_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Signed positive version '+1.2.3' produces the exact complete
        message with the raw manifest spelling preserved as-is (no repr)."""
        from quickscale_core.manifest.loader import (
            ModuleVersionMismatchError,
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "0.87.0",
        )

        with pytest.raises(ModuleVersionMismatchError) as exc_info:
            assert_manifest_version_matches_core("+1.2.3", "auth")

        assert str(exc_info.value) == (
            "Module 'auth' version mismatch: "
            "found +1.2.3; expected core version 0.87.0."
        )

    def test_signed_negative_complete_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Signed negative version '-1.2.3' produces the exact complete
        message with the raw manifest spelling preserved as-is."""
        from quickscale_core.manifest.loader import (
            ModuleVersionMismatchError,
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "0.87.0",
        )

        with pytest.raises(ModuleVersionMismatchError) as exc_info:
            assert_manifest_version_matches_core("-1.2.3", "auth")

        assert str(exc_info.value) == (
            "Module 'auth' version mismatch: "
            "found -1.2.3; expected core version 0.87.0."
        )

    def test_unicode_digit_complete_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unicode-digit version '١.2.3' produces the exact complete
        message with the raw Unicode manifest spelling preserved."""
        from quickscale_core.manifest.loader import (
            ModuleVersionMismatchError,
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "0.87.0",
        )

        with pytest.raises(ModuleVersionMismatchError) as exc_info:
            assert_manifest_version_matches_core("١.2.3", "auth")

        assert str(exc_info.value) == (
            "Module 'auth' version mismatch: "
            "found \u0661.2.3; expected core version 0.87.0."
        )

    def test_empty_component_complete_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Version with empty component '0..1' produces the exact complete
        message with the raw manifest spelling preserved."""
        from quickscale_core.manifest.loader import (
            ModuleVersionMismatchError,
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "0.87.0",
        )

        with pytest.raises(ModuleVersionMismatchError) as exc_info:
            assert_manifest_version_matches_core("0..1", "auth")

        assert str(exc_info.value) == (
            "Module 'auth' version mismatch: found 0..1; expected core version 0.87.0."
        )

    def test_signed_positive_core_preserves_raw_spelling(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the core version is monkeypatched to a signed value
        ('+1.2.3'), the complete message preserves the raw core spelling
        as-is — proving the ValueError path does not repr-escape the core
        version."""
        from quickscale_core.manifest.loader import (
            ModuleVersionMismatchError,
            assert_manifest_version_matches_core,
        )

        monkeypatch.setattr(
            "quickscale_core.manifest.loader._core_version",
            "+1.2.3",
        )

        with pytest.raises(ModuleVersionMismatchError) as exc_info:
            assert_manifest_version_matches_core("0.87.0", "auth")

        assert str(exc_info.value) == (
            "Module 'auth' version mismatch: "
            "found 0.87.0; expected core version +1.2.3."
        )


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


# ---------------------------------------------------------------------------
# Implies parsing
# ---------------------------------------------------------------------------


class TestLoadManifestImplies:
    """Tests for the implies section in load_manifest."""

    def test_no_implies_section(self) -> None:
        """Manifests without implies produce an empty list."""
        yaml_content = "name: mymod\nversion: '1.0.0'\n"
        manifest = load_manifest(yaml_content, "mymod")
        assert manifest.implies == []

    def test_empty_implies_section(self) -> None:
        """An empty implies list is accepted."""
        yaml_content = "name: mymod\nversion: '1.0.0'\nimplies: []\n"
        manifest = load_manifest(yaml_content, "mymod")
        assert manifest.implies == []

    def test_single_implied_module(self) -> None:
        """A single implies entry is parsed correctly."""
        yaml_content = """
name: billing
version: "1.0.0"
implies:
  - name: orgs
"""
        manifest = load_manifest(yaml_content, "billing")
        assert len(manifest.implies) == 1
        entry = manifest.implies[0]
        assert isinstance(entry, ImpliesEntry)
        assert entry.name == "orgs"
        assert entry.default_config == {}

    def test_multiple_implied_modules(self) -> None:
        """Multiple implies entries are parsed correctly."""
        yaml_content = """
name: billing
version: "1.0.0"
implies:
  - name: orgs
  - name: notifications
    default_config:
      enabled: true
      sender_name: "QuickScale"
"""
        manifest = load_manifest(yaml_content, "billing")
        assert len(manifest.implies) == 2
        assert manifest.implies[0].name == "orgs"
        assert manifest.implies[1].name == "notifications"
        assert manifest.implies[1].default_config == {
            "enabled": True,
            "sender_name": "QuickScale",
        }

    def test_implies_with_default_config(self) -> None:
        """Implies entry with default_config is parsed correctly."""
        yaml_content = """
name: orgs
version: "1.0.0"
implies:
  - name: notifications
    default_config:
      enabled: true
      sender_name: "QuickScale"
      sender_email: "noreply@example.com"
      resend_api_key_env_var: "RESEND_API_KEY"
      webhook_secret_env_var: "QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET"
      default_tags:
        - quickscale
        - transactional
      allowed_tags:
        - quickscale
        - transactional
        - notifications
        - auth
      webhook_ttl_seconds: 300
"""
        manifest = load_manifest(yaml_content, "orgs")
        assert len(manifest.implies) == 1
        entry = manifest.implies[0]
        assert entry.name == "notifications"
        assert entry.default_config["enabled"] is True
        assert entry.default_config["sender_name"] == "QuickScale"
        assert entry.default_config["default_tags"] == ["quickscale", "transactional"]
        assert entry.default_config["webhook_ttl_seconds"] == 300

    def test_implies_not_list_raises(self) -> None:
        """implies that is not a list raises ManifestError."""
        yaml_content = "name: mymod\nversion: '1.0.0'\nimplies: not_a_list\n"
        with pytest.raises(ManifestError, match="implies"):
            load_manifest(yaml_content, "mymod")

    def test_implies_entry_not_mapping_raises(self) -> None:
        """An implies entry that is not a mapping raises ManifestError."""
        yaml_content = "name: mymod\nversion: '1.0.0'\nimplies:\n  - not_a_mapping\n"
        with pytest.raises(ManifestError, match="implies"):
            load_manifest(yaml_content, "mymod")

    def test_implies_entry_missing_name_raises(self) -> None:
        """An implies entry without name raises ManifestError."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\nimplies:\n  - default_config: {}\n"
        )
        with pytest.raises(ManifestError, match="name"):
            load_manifest(yaml_content, "mymod")

    def test_implies_entry_empty_name_raises(self) -> None:
        """An implies entry with empty name raises ManifestError."""
        yaml_content = "name: mymod\nversion: '1.0.0'\nimplies:\n  - name: ''\n"
        with pytest.raises(ManifestError, match="name"):
            load_manifest(yaml_content, "mymod")

    def test_implies_entry_default_config_not_mapping_raises(self) -> None:
        """An implies entry with non-mapping default_config raises ManifestError."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\nimplies:\n"
            "  - name: orgs\n    default_config: not_a_mapping\n"
        )
        with pytest.raises(ManifestError, match="default_config"):
            load_manifest(yaml_content, "mymod")

    def test_implies_coexists_with_required_modules(self) -> None:
        """implies and required_modules parse independently."""
        yaml_content = """
name: billing
version: "1.0.0"
required_modules:
  - orgs
implies:
  - name: notifications
"""
        manifest = load_manifest(yaml_content, "billing")
        assert manifest.required_modules == ["orgs"]
        assert len(manifest.implies) == 1
        assert manifest.implies[0].name == "notifications"

    def test_implies_does_not_break_backward_compat(self) -> None:
        """A manifest without implies still loads and has empty implies."""
        yaml_content = "name: auth\nversion: '1.0.0'\n"
        manifest = load_manifest(yaml_content, "auth")
        assert manifest.implies == []
        assert manifest.name == "auth"
        assert manifest.version == "1.0.0"

    def test_orgs_implies_notifications_default_config_parity(self) -> None:
        """The orgs module's implied default_config for notifications
        is empty — defaults are sourced from notifications/module.yml only.

        SA7.3 removed the duplicated inline defaults from orgs/module.yml.
        Re-adding them would silently create a second source of truth for
        notifications defaults, so this test asserts the default_config
        block stays empty.
        """
        repo_root = Path(__file__).resolve().parent.parent.parent
        orgs_manifest = load_manifest_from_path(
            repo_root / "quickscale_modules" / "orgs" / "module.yml"
        )

        # Find the implies entry for notifications
        notifications_implies = [
            e for e in orgs_manifest.implies if e.name == "notifications"
        ]
        assert len(notifications_implies) == 1
        implied_config = notifications_implies[0].default_config

        # Must be empty — notifications provides its own canonical defaults
        assert implied_config == {}, (
            f"orgs implies notifications default_config must be empty.\n"
            f"SA7.3 removed the duplicated inline defaults; notifications "
            f"defaults are now sourced exclusively from\n"
            f"notifications/module.yml. Found: {implied_config}"
        )


# ---------------------------------------------------------------------------
# Derivation section parsing (T2.3+)
# ---------------------------------------------------------------------------


class TestLoadManifestDerivation:
    """Tests for the optional derivation section in load_manifest."""

    def test_no_derivation_section(self) -> None:
        """Manifests without a derivation section produce empty lists."""
        yaml_content = "name: mymod\nversion: '1.0.0'\n"
        manifest = load_manifest(yaml_content, "mymod")
        assert manifest.derivation_rules == []
        assert manifest.validation_rules == []
        assert manifest.legacy_aliases == []
        assert manifest.derived_settings == []
        assert manifest.wiring_projections == []

    def test_empty_derivation_section(self) -> None:
        """An empty derivation section produces empty lists."""
        yaml_content = "name: mymod\nversion: '1.0.0'\nderivation: {}\n"
        manifest = load_manifest(yaml_content, "mymod")
        assert manifest.derivation_rules == []
        assert manifest.validation_rules == []
        assert manifest.legacy_aliases == []
        assert manifest.derived_settings == []
        assert manifest.wiring_projections == []

    def test_derivation_normalization_rules(self) -> None:
        """Normalization rules in the derivation section are parsed."""
        yaml_content = """
name: mymod
version: '1.0.0'
derivation:
  normalization_rules:
    - source_key: provider
      target_key: provider
      rule_type: lowercase
    - source_key: mode
      target_key: mode
      rule_type: choice_map
      mapping:
        basic: simple
        full: detailed
"""
        manifest = load_manifest(yaml_content, "mymod")
        assert len(manifest.derivation_rules) == 2
        assert manifest.derivation_rules[0]["source_key"] == "provider"
        assert manifest.derivation_rules[0]["rule_type"] == "lowercase"
        assert manifest.derivation_rules[1]["source_key"] == "mode"
        assert manifest.derivation_rules[1]["rule_type"] == "choice_map"

    def test_derivation_validation_rules(self) -> None:
        """Validation rules in the derivation section are parsed."""
        yaml_content = """
name: mymod
version: '1.0.0'
derivation:
  validation_rules:
    - option_key: provider
      rule_type: choices
      allowed_values:
        - posthog
        - segment
    - option_key: enabled
      rule_type: required
"""
        manifest = load_manifest(yaml_content, "mymod")
        assert len(manifest.validation_rules) == 2
        assert manifest.validation_rules[0]["option_key"] == "provider"
        assert manifest.validation_rules[0]["rule_type"] == "choices"
        assert manifest.validation_rules[1]["option_key"] == "enabled"

    def test_derivation_legacy_aliases(self) -> None:
        """Legacy aliases in the derivation section are parsed."""
        yaml_content = """
name: mymod
version: '1.0.0'
derivation:
  legacy_aliases:
    - legacy_key: old_api_key
      current_key: api_key
      transform: identity
    - legacy_key: old_provider
      current_key: provider
      transform: rename_value
      transform_params:
        basic: posthog
"""
        manifest = load_manifest(yaml_content, "mymod")
        assert len(manifest.legacy_aliases) == 2
        assert manifest.legacy_aliases[0]["legacy_key"] == "old_api_key"
        assert manifest.legacy_aliases[1]["transform"] == "rename_value"

    def test_derivation_derived_settings(self) -> None:
        """Derived settings in the derivation section are parsed."""
        yaml_content = """
name: mymod
version: '1.0.0'
derivation:
  derived_settings:
    - setting_key: MY_APP_ENABLED
      source_options:
        - enabled
      derivation_type: direct
      expression:
        option: enabled
    - setting_key: MY_APP_MODE
      derivation_type: static
      expression:
        value: production
"""
        manifest = load_manifest(yaml_content, "mymod")
        assert len(manifest.derived_settings) == 2
        assert manifest.derived_settings[0]["setting_key"] == "MY_APP_ENABLED"
        assert manifest.derived_settings[1]["setting_key"] == "MY_APP_MODE"

    def test_derivation_wiring_projections(self) -> None:
        """Wiring projections in the derivation section are parsed."""
        yaml_content = """
name: mymod
version: '1.0.0'
derivation:
  wiring_projections:
    - wiring_field: apps
      derivation_type: static
      expression:
        value:
          - my_app
    - wiring_field: url_includes
      derivation_type: static
      expression:
        value:
          - ["", "my_app.urls"]
"""
        manifest = load_manifest(yaml_content, "mymod")
        assert len(manifest.wiring_projections) == 2
        assert manifest.wiring_projections[0]["wiring_field"] == "apps"
        assert manifest.wiring_projections[1]["wiring_field"] == "url_includes"

    def test_derivation_not_list_raises(self) -> None:
        """A derivation sub-section that is not a list raises ManifestError."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "derivation:\n  validation_rules: not_a_list\n"
        )
        with pytest.raises(ManifestError, match="validation_rules"):
            load_manifest(yaml_content, "mymod")

    def test_derivation_not_mapping_raises(self) -> None:
        """derivation that is not a mapping raises ManifestError."""
        yaml_content = "name: mymod\nversion: '1.0.0'\nderivation: not_a_mapping\n"
        with pytest.raises(ManifestError, match="derivation"):
            load_manifest(yaml_content, "mymod")

    def test_derivation_coexists_with_implies(self) -> None:
        """derivation and implies parse independently."""
        yaml_content = """
name: billing
version: '1.0.0'
implies:
  - name: orgs
derivation:
  normalization_rules:
    - source_key: provider
      target_key: provider
      rule_type: lowercase
"""
        manifest = load_manifest(yaml_content, "billing")
        assert len(manifest.implies) == 1
        assert manifest.implies[0].name == "orgs"
        assert len(manifest.derivation_rules) == 1

    def test_derivation_does_not_break_backward_compat(self) -> None:
        """A manifest without derivation loads cleanly with empty derivation fields."""
        yaml_content = "name: auth\nversion: '1.0.0'\n"
        manifest = load_manifest(yaml_content, "auth")
        assert manifest.derivation_rules == []
        assert manifest.validation_rules == []
        assert manifest.legacy_aliases == []
        assert manifest.derived_settings == []
        assert manifest.wiring_projections == []
        assert manifest.option_derivations == {}
        assert manifest.name == "auth"

    def test_option_derivations_parsed(self) -> None:
        """option_derivations are parsed from the derivation section."""
        yaml_content = """
name: analytics
version: '1.0.0'
derivation:
  wiring_projections:
    - wiring_field: apps
      derivation_type: static
      expression:
        value: [quickscale_modules_analytics]
  option_derivations:
    enabled:
      derived_settings:
        - setting_key: QUICKSCALE_ANALYTICS_ENABLED
          source_options: [enabled]
          derivation_type: direct
          expression:
            option: enabled
    provider:
      derived_settings:
        - setting_key: QUICKSCALE_ANALYTICS_PROVIDER
          source_options: [provider]
          derivation_type: direct
          expression:
            option: provider
      normalization_rules:
        - source_key: provider
          target_key: provider
          rule_type: lowercase
      validation_rules:
        - option_key: provider
          rule_type: choices
          allowed_values: [posthog]
"""
        manifest = load_manifest(yaml_content, "analytics")
        assert "enabled" in manifest.option_derivations
        assert "provider" in manifest.option_derivations
        assert len(manifest.option_derivations["enabled"]["derived_settings"]) == 1
        assert (
            manifest.option_derivations["enabled"]["derived_settings"][0]["setting_key"]
            == "QUICKSCALE_ANALYTICS_ENABLED"
        )
        assert len(manifest.option_derivations["provider"]["normalization_rules"]) == 1
        assert len(manifest.option_derivations["provider"]["validation_rules"]) == 1
        assert (
            manifest.option_derivations["provider"]["validation_rules"][0]["rule_type"]
            == "choices"
        )
        assert len(manifest.wiring_projections) == 1

    def test_option_derivations_empty_when_absent(self) -> None:
        """option_derivations defaults to empty dict when the derivation section
        does not contain it."""
        yaml_content = """
name: auth
version: '1.0.0'
derivation:
  wiring_projections:
    - wiring_field: apps
      derivation_type: static
      expression:
        value: [my_app]
"""
        manifest = load_manifest(yaml_content, "auth")
        assert manifest.option_derivations == {}

    def test_option_derivations_not_mapping_raises(self) -> None:
        """option_derivations that is not a mapping raises ManifestError."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "derivation:\n  option_derivations: not_a_mapping\n"
        )
        with pytest.raises(ManifestError, match="option_derivations"):
            load_manifest(yaml_content, "mymod")

    def test_option_derivation_entry_not_mapping_raises(self) -> None:
        """An individual option_derivation entry that is not a mapping raises."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "derivation:\n  option_derivations:\n    enabled: not_a_mapping\n"
        )
        with pytest.raises(ManifestError, match="option_derivations.enabled"):
            load_manifest(yaml_content, "mymod")


# ---------------------------------------------------------------------------
# Contract-vintage section parsing (SA10.2)
# ---------------------------------------------------------------------------


class TestLoadManifestContractVintage:
    """Tests for the optional contract_vintage section in load_manifest."""

    def test_no_contract_vintage_section(self) -> None:
        """Manifests without a contract_vintage section produce None."""
        yaml_content = "name: mymod\nversion: '1.0.0'\n"
        manifest = load_manifest(yaml_content, "mymod")
        assert manifest.contract_vintage is None

    def test_contract_vintage_with_minimum_only(self) -> None:
        """A contract_vintage section with just minimum is parsed."""
        yaml_content = """
name: mymod
version: '1.0.0'
contract_vintage:
  minimum: "0.87.0"
"""
        manifest = load_manifest(yaml_content, "mymod")
        assert manifest.contract_vintage is not None
        assert manifest.contract_vintage.minimum == "0.87.0"
        assert manifest.contract_vintage.manual_adoption_steps == []

    def test_contract_vintage_with_steps(self) -> None:
        """A contract_vintage section with manual_adoption_steps is parsed."""
        yaml_content = """
name: mymod
version: '1.0.0'
contract_vintage:
  minimum: "0.87.0"
  manual_adoption_steps:
    - "Step one: do this"
    - "Step two: do that"
"""
        manifest = load_manifest(yaml_content, "mymod")
        assert manifest.contract_vintage is not None
        assert manifest.contract_vintage.minimum == "0.87.0"
        assert len(manifest.contract_vintage.manual_adoption_steps) == 2
        assert manifest.contract_vintage.manual_adoption_steps[0] == "Step one: do this"
        assert manifest.contract_vintage.manual_adoption_steps[1] == "Step two: do that"

    def test_contract_vintage_not_mapping_raises(self) -> None:
        """contract_vintage that is not a mapping raises ManifestError."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\ncontract_vintage: not_a_mapping\n"
        )
        with pytest.raises(ManifestError, match="contract_vintage"):
            load_manifest(yaml_content, "mymod")

    def test_contract_vintage_missing_minimum_raises(self) -> None:
        """contract_vintage without minimum raises ManifestError."""
        yaml_content = """
name: mymod
version: '1.0.0'
contract_vintage:
  manual_adoption_steps: []
"""
        with pytest.raises(ManifestError, match="minimum"):
            load_manifest(yaml_content, "mymod")

    def test_contract_vintage_empty_minimum_raises(self) -> None:
        """contract_vintage with empty minimum raises ManifestError."""
        yaml_content = """
name: mymod
version: '1.0.0'
contract_vintage:
  minimum: ""
"""
        with pytest.raises(ManifestError, match="minimum"):
            load_manifest(yaml_content, "mymod")

    def test_contract_vintage_steps_not_list_raises(self) -> None:
        """contract_vintage with non-list manual_adoption_steps raises."""
        yaml_content = """
name: mymod
version: '1.0.0'
contract_vintage:
  minimum: "0.87.0"
  manual_adoption_steps: not_a_list
"""
        with pytest.raises(ManifestError, match="manual_adoption_steps"):
            load_manifest(yaml_content, "mymod")

    def test_contract_vintage_step_not_string_raises(self) -> None:
        """A manual_adoption_step that is not a string raises."""
        yaml_content = """
name: mymod
version: '1.0.0'
contract_vintage:
  minimum: "0.87.0"
  manual_adoption_steps:
    - 123
"""
        with pytest.raises(ManifestError, match="manual_adoption_steps"):
            load_manifest(yaml_content, "mymod")

    def test_contract_vintage_does_not_break_backward_compat(self) -> None:
        """A manifest without contract_vintage loads cleanly."""
        yaml_content = "name: auth\nversion: '1.0.0'\n"
        manifest = load_manifest(yaml_content, "auth")
        assert manifest.contract_vintage is None
        assert manifest.name == "auth"
        assert manifest.version == "1.0.0"

    def test_contract_vintage_malformed_minimum_raises(self) -> None:
        """contract_vintage with unparseable minimum raises ManifestError
        (fail closed instead of silently producing (0,))."""
        yaml_content = """
name: mymod
version: '1.0.0'
contract_vintage:
  minimum: "abc"
"""
        with pytest.raises(ManifestError, match="dotted-numeric"):
            load_manifest(yaml_content, "mymod")

    def test_contract_vintage_malformed_minimum_partial_raises(self) -> None:
        """Partially numeric minimum like '1.2.three' raises ManifestError."""
        yaml_content = """
name: mymod
version: '1.0.0'
contract_vintage:
  minimum: "1.2.three"
"""
        with pytest.raises(ManifestError, match="dotted-numeric"):
            load_manifest(yaml_content, "mymod")

    def test_contract_vintage_minimum_with_prerelease(self) -> None:
        """Pre-release suffix on minimum is valid (stripped before parse)."""
        yaml_content = """
name: mymod
version: '1.0.0'
contract_vintage:
  minimum: "0.87.0-alpha"
"""
        manifest = load_manifest(yaml_content, "mymod")
        assert manifest.contract_vintage is not None
        assert manifest.contract_vintage.minimum == "0.87.0-alpha"

    def test_contract_vintage_minimum_single_component(self) -> None:
        """A single-component minimum like '0' is accepted (valid version)."""
        yaml_content = """
name: mymod
version: '1.0.0'
contract_vintage:
  minimum: "0"
"""
        manifest = load_manifest(yaml_content, "mymod")
        assert manifest.contract_vintage is not None
        assert manifest.contract_vintage.minimum == "0"
