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
        matches the canonical notifications module.yml config defaults.

        This prevents silent drift between the inlined defaults in the
        orgs implies block and the authoritative notifications defaults.
        """
        repo_root = Path(__file__).resolve().parent.parent.parent
        orgs_manifest = load_manifest_from_path(
            repo_root / "quickscale_modules" / "orgs" / "module.yml"
        )
        notifications_manifest = load_manifest_from_path(
            repo_root / "quickscale_modules" / "notifications" / "module.yml"
        )

        # Find the implies entry for notifications
        notifications_implies = [
            e for e in orgs_manifest.implies if e.name == "notifications"
        ]
        assert len(notifications_implies) == 1
        implied_config = notifications_implies[0].default_config

        # Compare against canonical notifications defaults
        canonical_defaults = notifications_manifest.get_defaults()
        assert implied_config == canonical_defaults, (
            f"orgs implies notifications default_config has drifted from "
            f"notifications/module.yml canonical defaults.\n"
            f"Implied: {implied_config}\n"
            f"Canonical: {canonical_defaults}"
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
