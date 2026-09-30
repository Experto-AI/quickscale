from pathlib import Path
from unittest.mock import patch

import pytest

from quickscale_core.manifest.loader import (
    ManifestError,
    load_manifest,
    load_manifest_from_path,
    get_manifest_for_module,
    load_project_contract_vintage,
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
      validation: {}

  immutable:
    authentication_method:
      type: string
      default: email_username
      description: How users authenticate
      validation: {}
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
      description: An option missing its django_setting
      validation: {}
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

    def test_load_manifest_option_null_payload_raises(self) -> None:
        """A config option with a null payload cannot declare its required fields."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\nconfig:\n  immutable:\n    my_option:\n"
        )
        with pytest.raises(ManifestError, match="'type'"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_option_missing_type_raises(self) -> None:
        """An option without a declared type fails the load."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n    my_option:\n"
            "      description: A description\n"
            "      validation: {}\n"
        )
        with pytest.raises(ManifestError, match="non-empty 'type'"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_option_unknown_type_raises(self) -> None:
        """An option with an unsupported type fails the load."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n    my_option:\n"
            "      type: decimal\n"
            "      description: A description\n"
            "      validation: {}\n"
        )
        with pytest.raises(ManifestError, match="unsupported type"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_option_missing_description_raises(self) -> None:
        """An option without a description fails the load."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n    my_option:\n"
            "      type: string\n"
            "      validation: {}\n"
        )
        with pytest.raises(ManifestError, match="non-empty 'description'"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_option_missing_validation_raises(self) -> None:
        """An option without a validation mapping fails the load."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n    my_option:\n"
            "      type: string\n"
            "      default: ''\n"
            "      description: A description\n"
        )
        with pytest.raises(ManifestError, match="'validation' mapping"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_option_missing_default_raises(self) -> None:
        """An option without a default fails the load."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n    my_option:\n"
            "      type: string\n"
            "      description: A description\n"
            "      validation: {}\n"
        )
        with pytest.raises(ManifestError, match="must declare a 'default'"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_option_null_default_raises(self) -> None:
        """A null default fails the load."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n    my_option:\n"
            "      type: string\n"
            "      default:\n"
            "      description: A description\n"
            "      validation: {}\n"
        )
        with pytest.raises(ManifestError, match="'default' must not be null"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_option_default_type_mismatch_raises(self) -> None:
        """A default that does not match the declared type fails the load."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n    my_option:\n"
            "      type: integer\n"
            "      default: not-a-number\n"
            "      description: A description\n"
            "      validation: {}\n"
        )
        with pytest.raises(ManifestError, match="must match its declared type"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_option_unknown_validation_key_raises(self) -> None:
        """A validation block with an unrecognised key fails the load."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n    my_option:\n"
            "      type: string\n"
            "      default: ''\n"
            "      description: A description\n"
            "      validation:\n        required: true\n"
        )
        with pytest.raises(ManifestError, match="unknown key 'required'"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_option_invalid_bound_raises(self) -> None:
        """A non-numeric min bound fails the load."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n    my_option:\n"
            "      type: integer\n"
            "      default: 1\n"
            "      description: A description\n"
            "      validation:\n        min: low\n"
        )
        with pytest.raises(ManifestError, match="validation.min must be a number"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_option_invalid_pattern_raises(self) -> None:
        """An uncompilable pattern fails the load."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n    my_option:\n"
            "      type: string\n"
            "      default: ''\n"
            "      description: A description\n"
            "      validation:\n        pattern: '[unclosed'\n"
        )
        with pytest.raises(ManifestError, match="not a valid"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_option_required_when_accepts_multiple_entries(self) -> None:
        """required_when entries all hold, and {not_empty: true} is a value."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n"
            "    first:\n"
            "      type: boolean\n"
            "      default: true\n"
            "      description: A description\n"
            "      validation: {}\n"
            "    second:\n"
            "      type: string\n"
            "      default: ''\n"
            "      description: A description\n"
            "      validation: {}\n"
            "    my_option:\n"
            "      type: string\n"
            "      default: ''\n"
            "      description: A description\n"
            "      validation:\n        required_when:\n"
            "          first: true\n          second: {not_empty: true}\n"
        )
        manifest = load_manifest(yaml_content, "mymod")
        assert manifest.get_option("my_option") is not None

    def test_load_manifest_option_required_when_rejects_other_mappings(self) -> None:
        """A condition value may only be a literal, a list, or {not_empty: true}."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n"
            "    other:\n"
            "      type: string\n"
            "      default: ''\n"
            "      description: A description\n"
            "      validation: {}\n"
            "    my_option:\n"
            "      type: string\n"
            "      default: ''\n"
            "      description: A description\n"
            "      validation:\n        required_when:\n"
            "          other: {nested: true}\n"
        )
        with pytest.raises(ManifestError, match="must be a literal"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_condition_list_of_literals_is_accepted(self) -> None:
        """A list entry is accepted when every element is a literal."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n"
            "    mode:\n"
            "      type: string\n"
            "      default: local\n"
            "      description: A description\n"
            "      validation: {}\n"
            "    my_option:\n"
            "      type: string\n"
            "      default: ''\n"
            "      description: A description\n"
            "      validation:\n        required_when:\n"
            "          mode: [local, remote]\n"
        )
        manifest = load_manifest(yaml_content, "mymod")
        assert manifest.get_option("my_option") is not None

    def test_load_manifest_condition_list_elements_must_be_literals(self) -> None:
        """A nested condition or container is not a literal list element."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n"
            "    mode:\n"
            "      type: string\n"
            "      default: local\n"
            "      description: A description\n"
            "      validation: {}\n"
            "    my_option:\n"
            "      type: string\n"
            "      default: ''\n"
            "      description: A description\n"
            "      validation:\n        required_when:\n"
            "          mode: [{not_empty: true}]\n"
        )
        with pytest.raises(ManifestError, match="list of literals"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_condition_nonliteral_scalar_is_rejected(self) -> None:
        """A YAML set is not a condition literal."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n"
            "    mode:\n"
            "      type: string\n"
            "      default: local\n"
            "      description: A description\n"
            "      validation: {}\n"
            "    my_option:\n"
            "      type: string\n"
            "      default: ''\n"
            "      description: A description\n"
            "      validation:\n        required_when:\n"
            "          mode: !!set {local: null}\n"
        )
        with pytest.raises(ManifestError, match="must be a literal"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_option_not_empty_must_be_true(self) -> None:
        """validation.not_empty only takes the literal true."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n    my_option:\n"
            "      type: string\n"
            "      default: ''\n"
            "      description: A description\n"
            "      validation:\n        not_empty: false\n"
        )
        with pytest.raises(ManifestError, match="not_empty must be true"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_option_subset_of_references_an_option(self) -> None:
        """subset_of must name a declared option."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n    my_option:\n"
            "      type: list\n"
            "      default: []\n"
            "      description: A description\n"
            "      validation:\n        subset_of: missing_option\n"
        )
        with pytest.raises(ManifestError, match="unknown option 'missing_option'"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_option_excludes_requires_values(self) -> None:
        """excludes and intersects require a non-empty values list."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n"
            "    other:\n"
            "      type: string\n"
            "      default: ''\n"
            "      description: A description\n"
            "      validation: {}\n"
            "    my_option:\n"
            "      type: string\n"
            "      default: ''\n"
            "      description: A description\n"
            "      validation:\n        excludes:\n"
            "          values: []\n"
        )
        with pytest.raises(ManifestError, match="values must be a non-empty list"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_option_excludes_null_when_rejected(self) -> None:
        """An explicitly null condition is malformed, not absent."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n"
            "    other:\n"
            "      type: string\n"
            "      default: ''\n"
            "      description: A description\n"
            "      validation: {}\n"
            "    my_option:\n"
            "      type: string\n"
            "      default: ''\n"
            "      description: A description\n"
            "      validation:\n        excludes:\n"
            "          values: [noreply@example.com]\n"
            "          when: null\n"
        )
        with pytest.raises(ManifestError, match="when must be a condition mapping"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_option_excludes_when_must_be_a_mapping(self) -> None:
        """A condition block is a mapping, never a literal."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n"
            "    other:\n"
            "      type: string\n"
            "      default: ''\n"
            "      description: A description\n"
            "      validation: {}\n"
            "    my_option:\n"
            "      type: string\n"
            "      default: ''\n"
            "      description: A description\n"
            "      validation:\n        excludes:\n"
            "          values: [noreply@example.com]\n"
            "          when: true\n"
        )
        with pytest.raises(ManifestError, match="when must be a condition mapping"):
            load_manifest(yaml_content, "mymod")

    def test_load_manifest_option_reference_must_exist(self) -> None:
        """required_when and any_of may only reference declared options."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n    my_option:\n"
            "      type: string\n"
            "      default: ''\n"
            "      description: A description\n"
            "      validation:\n        required_when:\n"
            "          missing_option: true\n"
        )
        with pytest.raises(ManifestError, match="unknown option 'missing_option'"):
            load_manifest(yaml_content, "mymod")


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
      description: Whether the test switch is on
      validation: {}
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
      description: A test setting
      validation: {}
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

    @pytest.mark.parametrize("strict", [False, True])
    def test_get_manifest_raises_on_manifest_error(
        self, tmp_path: Path, strict: bool
    ) -> None:
        """A present but malformed manifest is never treated as absence."""
        project_path = tmp_path / "project"
        module_dir = project_path / "modules" / "broken"
        module_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text("- invalid\n- list\n")

        with pytest.raises(ManifestError, match="broken"):
            get_manifest_for_module(project_path, "broken", strict=strict)

    @pytest.mark.parametrize("strict", [False, True])
    def test_get_manifest_incomplete_module_raises(
        self, tmp_path: Path, strict: bool
    ) -> None:
        """A module directory without module.yml is an incomplete install."""
        project_path = tmp_path / "project"
        (project_path / "modules" / "incomplete").mkdir(parents=True)

        with pytest.raises(ManifestError, match="module.yml"):
            get_manifest_for_module(project_path, "incomplete", strict=strict)


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

        This matches managed-file entry handling only: every config option
        must declare its own ``type``, ``description``, ``validation``, and
        ``default``, so a null config-option payload is rejected.
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
# Retired implies key and required_modules parsing
# ---------------------------------------------------------------------------


class TestLoadManifestRetiredImplies:
    """The retired ``implies`` key is refused, whatever its payload."""

    @pytest.mark.parametrize(
        "payload",
        [
            "implies:\n  - name: orgs\n",
            "implies: []\n",
            "implies: not_a_list\n",
            "implies:\n  - not_a_mapping\n",
        ],
    )
    def test_implies_key_is_refused(self, payload: str) -> None:
        """Any implies key fails the load, naming the retired key."""
        yaml_content = f"name: mymod\nversion: '1.0.0'\n{payload}"
        with pytest.raises(ManifestError, match="'implies' is retired"):
            load_manifest(yaml_content, "mymod")

    def test_implies_refusal_names_required_modules_and_rule(self) -> None:
        """The refusal names the replacement key and the governing rule."""
        yaml_content = "name: mymod\nversion: '1.0.0'\nimplies:\n  - name: orgs\n"
        with pytest.raises(ManifestError) as exc_info:
            load_manifest(yaml_content, "mymod")
        message = str(exc_info.value)
        assert "required_modules" in message
        assert "rule 39" in message


class TestLoadManifestRequiredModules:
    """Bare-name required_modules parsing (Module Conventions rule 39)."""

    def test_bare_names_are_preserved(self) -> None:
        """Bare module names load in declaration order."""
        yaml_content = (
            "name: orgs\nversion: '1.0.0'\n"
            "required_modules:\n  - auth\n  - notifications\n"
        )
        manifest = load_manifest(yaml_content, "orgs")
        assert manifest.required_modules == ["auth", "notifications"]

    def test_version_specifier_is_refused(self) -> None:
        """A version floor is retired and refused by name."""
        yaml_content = (
            "name: billing\nversion: '1.0.0'\nrequired_modules:\n  - orgs>=0.86.0\n"
        )
        with pytest.raises(ManifestError, match="version specifiers are retired"):
            load_manifest(yaml_content, "billing")

    def test_empty_entry_is_refused(self) -> None:
        """An empty entry is refused."""
        yaml_content = "name: billing\nversion: '1.0.0'\nrequired_modules:\n  - ''\n"
        with pytest.raises(ManifestError, match="must not be empty"):
            load_manifest(yaml_content, "billing")

    def test_non_string_entry_is_refused(self) -> None:
        """A non-string entry is refused."""
        yaml_content = "name: billing\nversion: '1.0.0'\nrequired_modules:\n  - 5\n"
        with pytest.raises(ManifestError, match="Expected a bare module name"):
            load_manifest(yaml_content, "billing")

    def test_orgs_requires_auth_and_notifications(self) -> None:
        """The shipped orgs manifest requires auth and notifications."""
        repo_root = Path(__file__).resolve().parent.parent.parent
        orgs_manifest = load_manifest_from_path(
            repo_root / "quickscale_modules" / "orgs" / "module.yml"
        )
        assert orgs_manifest.required_modules == ["auth", "notifications"]


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

    def test_derivation_normalization_rules_is_refused(self) -> None:
        """A top-level normalization rule nothing executes fails the load."""
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
        with pytest.raises(
            ManifestError, match="derivation.normalization_rules is no longer"
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_validation_rules_is_refused(self) -> None:
        """A top-level validation rule nothing executes fails the load."""
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
        with pytest.raises(
            ManifestError, match="derivation.validation_rules is no longer"
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_normalization_rule_shapes_are_validated(self) -> None:
        """A malformed slug/list rule parameter fails the load, never silently."""
        bad_max_length = """
name: mymod
version: '1.0.0'
config:
  mutable:
    tags:
      type: list
      default: []
      django_setting: TAGS
      description: Tags
      validation: {}
derivation:
  option_derivations:
    tags:
      normalization_rules:
        - rule_type: slug
          max_length: five
"""
        with pytest.raises(ManifestError, match="max_length.*positive integer"):
            load_manifest(bad_max_length, "mymod")

        bad_item_rules = """
name: mymod
version: '1.0.0'
config:
  mutable:
    tags:
      type: list
      default: []
      django_setting: TAGS
      description: Tags
      validation: {}
derivation:
  option_derivations:
    tags:
      normalization_rules:
        - rule_type: list
          item_rules: not-a-list
"""
        with pytest.raises(ManifestError, match="item_rules.*must be a list"):
            load_manifest(bad_item_rules, "mymod")

        bad_replace = """
name: mymod
version: '1.0.0'
config:
  mutable:
    slug:
      type: string
      default: ''
      django_setting: SLUG
      description: Slug
      validation: {}
derivation:
  option_derivations:
    slug:
      normalization_rules:
        - rule_type: slug
          replace: [not, a, mapping]
"""
        with pytest.raises(ManifestError, match="replace.*mapping of strings"):
            load_manifest(bad_replace, "mymod")

    def test_derivation_normalization_rule_unknown_kind_rejected(self) -> None:
        """A rule kind outside rule 12's complete vocabulary fails the load."""
        yaml_content = """
name: mymod
version: '1.0.0'
config:
  mutable:
    name:
      type: string
      default: ''
      django_setting: NAME
      description: Name
      validation: {}
derivation:
  option_derivations:
    name:
      normalization_rules:
        - rule_type: slgu
"""
        with pytest.raises(ManifestError, match="rule_type.*must be one of"):
            load_manifest(yaml_content, "mymod")

    def test_derivation_normalization_rule_null_parameters_rejected(self) -> None:
        """An explicitly null rule parameter the builder cannot consume fails."""
        yaml_content = """
name: mymod
version: '1.0.0'
config:
  mutable:
    name:
      type: string
      default: ''
      django_setting: NAME
      description: Name
      validation: {}
derivation:
  option_derivations:
    name:
      normalization_rules:
        - rule_type: slug
          replace: null
"""
        with pytest.raises(ManifestError, match="replace.*mapping of strings"):
            load_manifest(yaml_content, "mymod")

        nested_null = yaml_content.replace(
            "        - rule_type: slug\n          replace: null\n",
            "        - rule_type: list\n          item_rules: null\n",
        )
        with pytest.raises(ManifestError, match="item_rules.*must be a list"):
            load_manifest(nested_null, "mymod")

    def test_derivation_normalization_rule_unknown_parameter_rejected(self) -> None:
        """A misspelled rule parameter fails the load instead of being ignored."""
        yaml_content = """
name: mymod
version: '1.0.0'
config:
  mutable:
    tags:
      type: list
      default: []
      django_setting: TAGS
      description: Tags
      validation: {}
derivation:
  option_derivations:
    tags:
      normalization_rules:
        - rule_type: list
          item_rules:
            - rule_type: slug
              max_lenght: 50
"""
        with pytest.raises(
            ManifestError, match="max_lenght.*not a supported parameter"
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_legacy_aliases_is_refused(self) -> None:
        """A top-level alias nothing executes fails the load."""
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
        with pytest.raises(
            ManifestError, match="derivation.legacy_aliases is no longer"
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_derived_settings(self) -> None:
        """Derived settings in the derivation section are parsed."""
        yaml_content = """
name: mymod
version: '1.0.0'
config:
  immutable:
    enabled:
      type: boolean
      default: true
      description: A description
      validation: {}
derivation:
  derived_settings:
    - setting_key: MY_APP_ENABLED
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
            "derivation:\n  wiring_projections: not_a_list\n"
        )
        with pytest.raises(ManifestError, match="wiring_projections"):
            load_manifest(yaml_content, "mymod")

    def test_derivation_not_mapping_raises(self) -> None:
        """derivation that is not a mapping raises ManifestError."""
        yaml_content = "name: mymod\nversion: '1.0.0'\nderivation: not_a_mapping\n"
        with pytest.raises(ManifestError, match="derivation"):
            load_manifest(yaml_content, "mymod")

    def test_derivation_coexists_with_required_modules(self) -> None:
        """derivation and required_modules parse independently."""
        yaml_content = """
name: billing
version: '1.0.0'
config:
  immutable:
    provider:
      type: string
      default: ''
      description: A description
      validation: {}
required_modules:
  - orgs
derivation:
  option_derivations:
    provider:
      normalization_rules:
        - source_key: provider
          target_key: provider
          rule_type: lowercase
"""
        manifest = load_manifest(yaml_content, "billing")
        assert manifest.required_modules == ["orgs"]
        assert (
            manifest.option_derivations["provider"]["normalization_rules"][0][
                "rule_type"
            ]
            == "lowercase"
        )

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
config:
  immutable:
    enabled:
      type: boolean
      default: true
      description: A description
      validation: {}
    provider:
      type: string
      default: ''
      description: A description
      validation: {}
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
          derivation_type: direct
          expression:
            option: enabled
    provider:
      derived_settings:
        - setting_key: QUICKSCALE_ANALYTICS_PROVIDER
          derivation_type: direct
          expression:
            option: provider
      normalization_rules:
        - source_key: provider
          target_key: provider
          rule_type: lowercase
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
        assert len(manifest.wiring_projections) == 1

    def test_derivation_option_validation_rules_is_refused(self) -> None:
        """A per-option derivation check nothing executes fails the load."""
        yaml_content = """
name: mymod
version: '1.0.0'
derivation:
  option_derivations:
    mode:
      validation_rules:
        - option_key: mode
          rule_type: choices
          allowed_values: [simple]
"""
        with pytest.raises(
            ManifestError,
            match=r"option_derivations\.mode\.validation_rules is no longer",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_option_legacy_aliases_is_refused(self) -> None:
        """Rule 6: a renamed option is refused by name, never aliased."""
        yaml_content = """
name: mymod
version: '1.0.0'
derivation:
  option_derivations:
    mode:
      legacy_aliases:
        - legacy_key: old_mode
          current_key: mode
          transform: identity
"""
        with pytest.raises(
            ManifestError,
            match=r"option_derivations\.mode\.legacy_aliases is no longer",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_option_alias_null_is_refused(self) -> None:
        """An explicitly present alias key is refused even when null."""
        yaml_content = """
name: mymod
version: '1.0.0'
derivation:
  option_derivations:
    mode:
      legacy_aliases: null
"""
        with pytest.raises(
            ManifestError,
            match=r"option_derivations\.mode\.legacy_aliases is no longer",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_option_subsection_must_be_a_list(self) -> None:
        """A null wireable sub-section is refused, not crashed on later."""
        yaml_content = """
name: mymod
version: '1.0.0'
derivation:
  option_derivations:
    mode:
      derived_settings: null
"""
        with pytest.raises(
            ManifestError,
            match=r"option_derivations\.mode\.derived_settings must be a list",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_settings_entry_must_be_a_mapping(self) -> None:
        """A null entry in a wired list section fails the load."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "derivation:\n  derived_settings:\n    - null\n"
        )
        with pytest.raises(
            ManifestError,
            match=r"derivation\.derived_settings\[0\] must be a mapping",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_option_settings_entry_must_be_a_mapping(self) -> None:
        """A malformed per-option wiring entry fails the load."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "derivation:\n  option_derivations:\n    mode:\n"
            "      wiring_projections: [null]\n"
        )
        with pytest.raises(
            ManifestError,
            match=r"option_derivations\.mode\.wiring_projections\[0\] must be a mapping",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_settings_expression_must_be_a_mapping(self) -> None:
        """A null expression would crash the builder, so it fails the load."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "derivation:\n  derived_settings:\n    - setting_key: X\n"
            "      derivation_type: direct\n      expression: null\n"
        )
        with pytest.raises(
            ManifestError,
            match=r"derivation\.derived_settings\[0\]\.expression must be a mapping",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_wiring_default_must_be_a_list(self) -> None:
        """A null wiring default would crash the builder, so it fails the load."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "derivation:\n  wiring_projections:\n    - wiring_field: apps\n"
            "      derivation_type: static\n      expression:\n        value: [x]\n"
            "      default: null\n"
        )
        with pytest.raises(
            ManifestError,
            match=r"derivation\.wiring_projections\[0\]\.default must be a list",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_option_unknown_key_is_refused(self) -> None:
        """A misspelled per-option key cannot load and be silently ignored."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "derivation:\n  option_derivations:\n    tags:\n"
            "      normalisation_rules:\n        - rule_type: list\n"
        )
        with pytest.raises(
            ManifestError,
            match=r"option_derivations\.tags declares unknown key 'normalisation_rules'",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_option_non_string_key_is_refused(self) -> None:
        """A non-string key is refused, never sorted against strings."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "derivation:\n  option_derivations:\n    tags:\n"
            "      1: []\n"
        )
        with pytest.raises(ManifestError, match="declares unknown key '1'"):
            load_manifest(yaml_content, "mymod")

    def test_derivation_conditional_branches_must_be_a_mapping(self) -> None:
        """A null branches mapping would crash resolution, so it fails the load."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n"
            "    mode:\n"
            "      type: string\n"
            "      default: go\n"
            "      description: A description\n"
            "      validation: {}\n"
            "derivation:\n  derived_settings:\n"
            "    - setting_key: X\n"
            "      source_options: [mode]\n"
            "      derivation_type: conditional\n"
            "      expression:\n        branches: null\n"
        )
        with pytest.raises(
            ManifestError,
            match=r"derived_settings\[0\]\.expression\.branches must be a mapping",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_conditional_cannot_select_a_list_option(self) -> None:
        """A list selector cannot crash branch membership, so it fails the load."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n"
            "    tags:\n"
            "      type: list\n"
            "      default: []\n"
            "      description: A description\n"
            "      validation: {}\n"
            "derivation:\n  wiring_projections:\n"
            "    - wiring_field: apps\n"
            "      source_options: [tags]\n"
            "      derivation_type: conditional\n"
            "      expression:\n        branches: {a: [x]}\n"
        )
        with pytest.raises(
            ManifestError,
            match=r"wiring_projections\[0\]\.source_options cannot select list option 'tags'",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_unknown_top_level_key_is_refused(self) -> None:
        """A dropped top-level declaration cannot load silently."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\nderivation:\n  validations_rules: []\n"
        )
        with pytest.raises(
            ManifestError,
            match="derivation declares unknown key 'validations_rules'",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_option_undeclared_name_is_refused(self) -> None:
        """A misspelled option name cannot load and never normalize."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "derivation:\n  option_derivations:\n    tagz:\n"
            "      normalization_rules:\n        - source_key: tagz\n"
            "          target_key: tagz\n          rule_type: lowercase\n"
        )
        with pytest.raises(
            ManifestError,
            match="option_derivations.tagz names an undeclared option",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_unknown_wiring_field_is_refused(self) -> None:
        """A misspelled projection field cannot contribute nothing silently."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "derivation:\n  wiring_projections:\n"
            "    - wiring_field: appz\n      derivation_type: static\n"
            "      expression:\n        value: [x]\n"
        )
        with pytest.raises(
            ManifestError,
            match=r"wiring_projections\[0\]\.wiring_field must be one of",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_unknown_derivation_type_is_refused(self) -> None:
        """A misspelled derivation type cannot skip resolution silently."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "derivation:\n  wiring_projections:\n"
            "    - wiring_field: apps\n      derivation_type: statci\n"
            "      expression:\n        value: [x]\n"
        )
        with pytest.raises(
            ManifestError,
            match=r"wiring_projections\[0\]\.derivation_type must be one of",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_wiring_field_must_be_a_string(self) -> None:
        """An unhashable field is refused, never a bare TypeError."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "derivation:\n  wiring_projections:\n"
            "    - wiring_field: [apps]\n      derivation_type: static\n"
            "      expression:\n        value: [x]\n"
        )
        with pytest.raises(
            ManifestError,
            match=r"wiring_projections\[0\]\.wiring_field must be one of",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_computed_template_conversion_is_restricted(self) -> None:
        """An unsupported conversion cannot load and then render nothing."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n"
            "    mode:\n      type: string\n      default: basic\n"
            "      description: A description\n      validation: {}\n"
            "derivation:\n  wiring_projections:\n"
            "    - wiring_field: apps\n      derivation_type: computed\n"
            '      expression:\n        values: ["{mode!z}"]\n'
        )
        with pytest.raises(
            ManifestError,
            match="conversion '!z' is not supported",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_selector_null_rule_list_is_refused(self) -> None:
        """A malformed selector rule list is refused, never a TypeError."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n"
            "    mode:\n      type: string\n      default: go\n"
            "      description: A description\n      validation: {}\n"
            "derivation:\n  option_derivations:\n    mode:\n"
            "      normalization_rules: null\n"
            "  wiring_projections:\n"
            "    - wiring_field: apps\n      source_options: [mode]\n"
            "      derivation_type: conditional\n"
            "      expression:\n        branches: {x: [y]}\n"
        )
        with pytest.raises(
            ManifestError,
            match=r"option_derivations\.mode\.normalization_rules' must be a list",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_direct_option_must_be_declared(self) -> None:
        """A direct projection cannot reference an undeclared option."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "derivation:\n  derived_settings:\n"
            "    - setting_key: X\n      derivation_type: direct\n"
            "      expression:\n        option: ghost\n"
        )
        with pytest.raises(
            ManifestError,
            match="expression.option references unknown option 'ghost'",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_static_contribution_must_be_a_list(self) -> None:
        """A scalar static contribution cannot be silently discarded."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "derivation:\n  wiring_projections:\n"
            "    - wiring_field: apps\n      derivation_type: static\n"
            "      expression:\n        value: my_app\n"
        )
        with pytest.raises(
            ManifestError,
            match=r"expression\.value must be a list of contributions for 'apps'",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_url_branch_items_must_be_pairs(self) -> None:
        """A URL branch item that is not a pair cannot be silently dropped."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n"
            "    mode:\n      type: string\n      default: go\n"
            "      description: A description\n      validation: {}\n"
            "derivation:\n  wiring_projections:\n"
            "    - wiring_field: url_includes\n      derivation_type: conditional\n"
            "      source_options: [mode]\n"
            "      expression:\n        branches:\n          go: [not-a-pair]\n"
        )
        with pytest.raises(
            ManifestError,
            match=r"branches\.go\[0\] must be a \[route, include\] pair",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_template_format_spec_must_format_a_string(self) -> None:
        """A numeric format spec cannot silently degrade a string template."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n"
            "    mode:\n      type: string\n      default: go\n"
            "      description: A description\n      validation: {}\n"
            "derivation:\n  derived_settings:\n"
            "    - setting_key: X\n      derivation_type: computed\n"
            '      expression:\n        template: "{mode:+d}"\n'
        )
        with pytest.raises(
            ManifestError,
            match=r"format spec '\+d' cannot format a string",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_rule_keys_must_match_the_owning_option(self) -> None:
        """A rule naming another key is not executed, so it is refused."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n"
            "    mode:\n      type: string\n      default: go\n"
            "      description: A description\n      validation: {}\n"
            "derivation:\n  option_derivations:\n    mode:\n"
            "      normalization_rules:\n"
            "        - source_key: ghost\n          target_key: new_mode\n"
            "          rule_type: lowercase\n"
        )
        with pytest.raises(
            ManifestError,
            match=r"normalization_rules\[0\] must declare source_key and target_key as 'mode'",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_excludes_unknown_key_is_refused(self) -> None:
        """A misspelled gate key cannot enforce a conditional rule always."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n"
            "    enabled:\n      type: boolean\n      default: true\n"
            "      description: A description\n      validation: {}\n"
            "    sender:\n      type: string\n      default: ''\n"
            "      description: A description\n"
            "      validation:\n"
            "        excludes:\n          values: [blocked]\n"
            "          wen: {enabled: true}\n"
        )
        with pytest.raises(
            ManifestError,
            match=r"validation\.excludes declares unknown key 'wen'",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_not_empty_marker_must_be_boolean_true(self) -> None:
        """`{not_empty: 1}` cannot pass and then never match at runtime."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n"
            "    context:\n      type: string\n      default: ''\n"
            "      description: A description\n      validation: {}\n"
            "    token:\n      type: string\n      default: ''\n"
            "      description: A description\n"
            "      validation:\n        required_when:\n"
            "          context: {not_empty: 1}\n"
        )
        with pytest.raises(
            ManifestError,
            match="must be a literal, a non-empty list, or {not_empty: true}",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_direct_requires_an_expression(self) -> None:
        """A direct projection with no option cannot project None silently."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n"
            "    mode:\n      type: string\n      default: go\n"
            "      description: A description\n      validation: {}\n"
            "derivation:\n  derived_settings:\n"
            "    - setting_key: X\n"
            "      derivation_type: direct\n"
        )
        with pytest.raises(
            ManifestError,
            match=r"derived_settings\[0\]\.expression must be a mapping",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_setting_key_must_be_declared(self) -> None:
        """A derived setting cannot enter the settings map as an empty key."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n"
            "    mode:\n      type: string\n      default: go\n"
            "      description: A description\n      validation: {}\n"
            "derivation:\n  derived_settings:\n"
            "    - derivation_type: direct\n"
            "      expression:\n        option: mode\n"
        )
        with pytest.raises(
            ManifestError,
            match=r"derived_settings\[0\]\.setting_key must be a non-empty string",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_static_contribution_item_must_be_a_string(self) -> None:
        """An item the resolver drops or stringifies cannot load."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "derivation:\n  wiring_projections:\n"
            "    - wiring_field: apps\n      derivation_type: static\n"
            "      expression:\n        value: [null]\n"
        )
        with pytest.raises(
            ManifestError,
            match=r"expression\.value\[0\] must be an app or middleware label",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_nested_rule_keys_must_match_the_owning_option(self) -> None:
        """A nested item rule naming another key is not executed, so it is refused."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n"
            "    tags:\n      type: list\n      default: []\n"
            "      description: A description\n      validation: {}\n"
            "derivation:\n  option_derivations:\n    tags:\n"
            "      normalization_rules:\n"
            "        - source_key: tags\n          target_key: tags\n"
            "          rule_type: list\n"
            "          item_rules:\n"
            "            - source_key: ghost\n              rule_type: lowercase\n"
        )
        with pytest.raises(
            ManifestError,
            match=r"item_rules\[0\] must declare source_key as 'tags'",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_nested_rule_declared_null_key_is_refused(self) -> None:
        """A declared nested key is checked even when its value is null."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n"
            "    tags:\n      type: list\n      default: []\n"
            "      description: A description\n      validation: {}\n"
            "derivation:\n  option_derivations:\n    tags:\n"
            "      normalization_rules:\n"
            "        - source_key: tags\n          target_key: tags\n"
            "          rule_type: list\n"
            "          item_rules:\n"
            "            - source_key: null\n              rule_type: lowercase\n"
        )
        with pytest.raises(
            ManifestError,
            match=r"item_rules\[0\] must declare source_key as 'tags'",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_static_requires_a_value(self) -> None:
        """A static projection with no value cannot load inert."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "derivation:\n  wiring_projections:\n"
            "    - wiring_field: apps\n      derivation_type: static\n"
            "      expression: {}\n"
        )
        with pytest.raises(
            ManifestError,
            match=r"expression\.value is required for a static projection",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_computed_requires_a_template(self) -> None:
        """A computed derived setting with no template cannot project None."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n"
            "    mode:\n      type: string\n      default: go\n"
            "      description: A description\n      validation: {}\n"
            "derivation:\n  derived_settings:\n"
            "    - setting_key: X\n      derivation_type: computed\n"
            "      expression: {}\n"
        )
        with pytest.raises(
            ManifestError,
            match=r"expression\.template is required for a computed projection",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_conditional_requires_a_selector(self) -> None:
        """A conditional projection with no selector cannot load inert."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "derivation:\n  wiring_projections:\n"
            "    - wiring_field: apps\n      derivation_type: conditional\n"
            "      expression:\n        branches: {x: [y]}\n"
        )
        with pytest.raises(
            ManifestError,
            match="source_options must list the selector option",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_contribution_items_must_be_strings(self) -> None:
        """A mapping item cannot be stringified into an app label."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "derivation:\n  wiring_projections:\n"
            "    - wiring_field: apps\n      derivation_type: static\n"
            "      expression:\n        value: [{plugin: on}]\n"
        )
        with pytest.raises(
            ManifestError,
            match=r"expression\.value\[0\] must be an app or middleware label",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_url_pair_must_be_exactly_two_strings(self) -> None:
        """A malformed pair cannot be silently truncated."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "derivation:\n  wiring_projections:\n"
            "    - wiring_field: url_includes\n      derivation_type: static\n"
            "      expression:\n        value: [[a, b, c]]\n"
        )
        with pytest.raises(
            ManifestError,
            match=r"expression\.value\[0\] must be a \[route, include\] pair of strings",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_direct_url_default_must_be_pairs(self) -> None:
        """A known default that cannot be a URL pair fails the load."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n"
            "    routes:\n      type: list\n      default: [users/]\n"
            "      description: A description\n      validation: {}\n"
            "derivation:\n  wiring_projections:\n"
            "    - wiring_field: url_includes\n      derivation_type: direct\n"
            "      expression:\n        option: routes\n"
        )
        with pytest.raises(
            ManifestError,
            match=r"expression\.option default\[0\] must be a \[route, include\] pair of strings",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_computed_values_items_must_be_strings(self) -> None:
        """A null computed value cannot become the app label 'None'."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "derivation:\n  wiring_projections:\n"
            "    - wiring_field: apps\n      derivation_type: computed\n"
            "      expression:\n        values: [null]\n"
        )
        with pytest.raises(
            ManifestError,
            match=r"expression\.values\[0\] must be a string",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_computed_template_must_not_be_empty(self) -> None:
        """An empty template cannot silently project the default."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n"
            "    mode:\n      type: string\n      default: go\n"
            "      description: A description\n      validation: {}\n"
            "derivation:\n  derived_settings:\n"
            "    - setting_key: X\n      derivation_type: computed\n"
            '      expression:\n        template: ""\n'
        )
        with pytest.raises(
            ManifestError,
            match="must be a non-empty template",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_expression_unknown_key_is_refused(self) -> None:
        """An unconsumed expression key cannot be ignored."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "derivation:\n  wiring_projections:\n"
            "    - wiring_field: apps\n      derivation_type: conditional\n"
            "      source_options: [mode]\n"
            "      expression:\n"
            "        branches: {x: [y]}\n        default: [fallback_app]\n"
        )
        with pytest.raises(
            ManifestError,
            match=r"expression declares unknown key 'default'",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_computed_values_must_not_be_empty(self) -> None:
        """A computed projection with no template cannot load inert."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "derivation:\n  wiring_projections:\n"
            "    - wiring_field: apps\n      derivation_type: computed\n"
            "      expression:\n        values: []\n"
        )
        with pytest.raises(
            ManifestError,
            match=r"expression\.values must be a non-empty list",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_source_options_are_conditional_only(self) -> None:
        """Source metadata a projection does not execute cannot load."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n"
            "    mode:\n      type: string\n      default: go\n"
            "      description: A description\n      validation: {}\n"
            "derivation:\n  derived_settings:\n"
            "    - setting_key: X\n      source_options: [mode]\n"
            "      derivation_type: direct\n"
            "      expression:\n        option: mode\n"
        )
        with pytest.raises(
            ManifestError,
            match="source_options is only valid for a conditional projection",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_computed_template_placeholder_is_restricted(self) -> None:
        """Attribute access in a template would crash, so it fails the load."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n"
            "    tags:\n      type: string\n      default: ''\n"
            "      description: A description\n      validation: {}\n"
            "derivation:\n  derived_settings:\n"
            "    - setting_key: X\n      derivation_type: computed\n"
            '      expression:\n        template: "{tags.not_a_property}"\n'
        )
        with pytest.raises(
            ManifestError,
            match="placeholder 'tags.not_a_property' must be a plain option name",
        ):
            load_manifest(yaml_content, "mymod")

    def test_derivation_selector_with_list_normalization_is_refused(self) -> None:
        """A selector whose rule can yield a list cannot key a branch."""
        yaml_content = (
            "name: mymod\nversion: '1.0.0'\n"
            "config:\n  immutable:\n"
            "    mode:\n      type: string\n      default: go\n"
            "      description: A description\n      validation: {}\n"
            "derivation:\n  option_derivations:\n    mode:\n"
            "      normalization_rules:\n"
            "        - source_key: mode\n          target_key: mode\n"
            "          rule_type: choice_map\n          mapping:\n"
            "            go: [oops]\n"
            "  wiring_projections:\n"
            "    - wiring_field: apps\n      source_options: [mode]\n"
            "      derivation_type: conditional\n"
            "      expression:\n        branches: {x: [y]}\n"
        )
        with pytest.raises(
            ManifestError,
            match="cannot select 'mode'",
        ):
            load_manifest(yaml_content, "mymod")

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

    def test_contract_vintage_with_id(self) -> None:
        """An optional step id is parsed for exact adoption tracking."""
        yaml_content = """
name: mymod
version: '1.0.0'
contract_vintage:
  id: sa999-step
  minimum: "0.89.0"
  manual_adoption_steps:
    - "Step one"
"""
        manifest = load_manifest(yaml_content, "mymod")
        assert manifest.contract_vintage is not None
        assert manifest.contract_vintage.id == "sa999-step"

    def test_contract_vintage_empty_id_raises(self) -> None:
        """An empty step id fails closed instead of tracking nothing."""
        yaml_content = """
name: mymod
version: '1.0.0'
contract_vintage:
  id: ""
  minimum: "0.89.0"
"""
        with pytest.raises(ManifestError, match="contract_vintage.id"):
            load_manifest(yaml_content, "mymod")

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


class TestLoadManifestRetiredOptions:
    """Tests for the optional retired_options section in load_manifest (SA217)."""

    def test_no_retired_options_section(self) -> None:
        """Manifests without a retired_options section produce an empty mapping."""
        yaml_content = "name: mymod\nversion: '1.0.0'\n"
        manifest = load_manifest(yaml_content, "mymod")
        assert manifest.retired_options == {}

    def test_retired_options_are_parsed_with_their_messages(self) -> None:
        """Each retired key maps to the removal message that must refuse it."""
        yaml_content = """
name: mymod
version: '1.0.0'
retired_options:
  default_pipeline_stages: >-
    Legacy config key 'default_pipeline_stages' is no longer supported.
"""
        manifest = load_manifest(yaml_content, "mymod")
        assert manifest.retired_options == {
            "default_pipeline_stages": (
                "Legacy config key 'default_pipeline_stages' is no longer supported."
            )
        }

    def test_retired_options_must_be_a_mapping(self) -> None:
        yaml_content = """
name: mymod
version: '1.0.0'
retired_options:
  - default_pipeline_stages
"""
        with pytest.raises(ManifestError, match="must be a mapping"):
            load_manifest(yaml_content, "mymod")

    def test_retired_option_message_must_be_non_empty(self) -> None:
        yaml_content = """
name: mymod
version: '1.0.0'
retired_options:
  default_pipeline_stages: ""
"""
        with pytest.raises(ManifestError, match="non-empty removal message"):
            load_manifest(yaml_content, "mymod")

    def test_retired_option_cannot_also_be_declared(self) -> None:
        """A key is either live or retired, never both."""
        yaml_content = """
name: mymod
version: '1.0.0'
config:
  mutable:
    deals_per_page:
      type: integer
      default: 25
      django_setting: DEALS_PER_PAGE
      description: Deals per page
      validation: {}
  immutable: {}
retired_options:
  deals_per_page: Legacy key
"""
        with pytest.raises(ManifestError, match="also a declared option"):
            load_manifest(yaml_content, "mymod")


class TestLoadProjectContractVintage:
    """Tests for the packaged generated-project contract declaration (SA207)."""

    def test_packaged_declaration_loads(self) -> None:
        """The shipped declaration parses with its template contract steps."""
        declaration = load_project_contract_vintage()
        step_ids = [step.id for step in declaration.steps]

        assert step_ids[:4] == [
            "sa192-shared-design",
            "sa200-proxy-trust",
            "sa201-throttling",
            "sa206-runtime-settings-facade",
        ]
        assert all(step.minimum == "0.89.0" for step in declaration.steps)
        assert all(step.title for step in declaration.steps)
        assert all(step.manual_adoption_steps for step in declaration.steps)

    def test_missing_declaration_raises(self, tmp_path: Path) -> None:
        """A missing declaration file fails hard."""
        with pytest.raises(ManifestError, match="Unable to read"):
            load_project_contract_vintage(tmp_path / "missing.yml")

    @pytest.mark.parametrize(
        ("body", "match"),
        [
            ("steps: []\n", "non-empty list"),
            ("steps: not_a_list\n", "non-empty list"),
            ("steps:\n  - id: sa1\n    minimum: '0.89.0'\n", "title"),
            (
                "steps:\n  - id: sa1\n    minimum: '0.89.0'\n    title: t\n",
                "adoption_steps",
            ),
            (
                "steps:\n  - id: sa1\n    minimum: '0.89.0'\n"
                "    title: t\n    adoption_steps: []\n",
                "adoption_steps",
            ),
            (
                "steps:\n  - id: ''\n    minimum: '0.89.0'\n"
                "    title: t\n    adoption_steps: [s]\n",
                "id",
            ),
            (
                "steps:\n  - id: sa1\n    minimum: abc\n"
                "    title: t\n    adoption_steps: [s]\n",
                "dotted-numeric",
            ),
            (
                "steps:\n  - id: sa1\n    minimum: '0.89.0'\n"
                "    title: t\n    adoption_steps: [s]\n"
                "  - id: sa1\n    minimum: '0.89.0'\n"
                "    title: t\n    adoption_steps: [s]\n",
                "duplicates",
            ),
            (
                "steps:\n  - id: sa1\n    minimum: '0.89.0'\n"
                "    title: t\n    adoption_steps: [1]\n",
                "must be a non-empty string",
            ),
        ],
    )
    def test_malformed_declaration_fails_closed(
        self, tmp_path: Path, body: str, match: str
    ) -> None:
        declaration_path = tmp_path / "project_contract.yml"
        declaration_path.write_text(body, encoding="utf-8")

        with pytest.raises(ManifestError, match=match):
            load_project_contract_vintage(declaration_path)
