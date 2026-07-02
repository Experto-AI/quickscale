"""Tests for the manifest-to-schema builder (``build_schema_from_manifest``).

Verifies that raw manifest derivation dicts are correctly converted into typed
:class:`ModuleDerivationSchema` instances.
"""

from __future__ import annotations

from quickscale_core.manifest.derivation import (
    ModuleDerivationSchema,
    NormalizationRule,
    OptionDerivation,
    ValidationRule,
    DerivedSetting,
    WiringProjection,
    LegacyKeyAlias,
    build_schema_from_manifest,
)


class TestBuildSchemaFromManifest:
    """Test the build_schema_from_manifest conversion function."""

    def test_empty_derivation_produces_empty_schema(self) -> None:
        """All-empty inputs produce a schema with no rules."""
        schema = build_schema_from_manifest("testmod")
        assert schema.module_name == "testmod"
        assert schema.option_derivations == {}
        assert schema.module_wiring_projections == []
        assert schema.shared_normalization_rules == []
        assert schema.shared_validation_rules == []

    def test_wiring_projections_converted(self) -> None:
        """Module-level wiring projections are parsed into typed instances."""
        schema = build_schema_from_manifest(
            "testmod",
            wiring_projections=[
                {
                    "wiring_field": "apps",
                    "derivation_type": "static",
                    "expression": {"value": ["my_app"]},
                    "description": "My app label",
                },
            ],
        )
        assert len(schema.module_wiring_projections) == 1
        wp = schema.module_wiring_projections[0]
        assert isinstance(wp, WiringProjection)
        assert wp.wiring_field == "apps"
        assert wp.derivation_type == "static"
        assert wp.expression == {"value": ["my_app"]}
        assert wp.description == "My app label"

    def test_option_derivations_converted(self) -> None:
        """Per-option derivations are parsed with nested rules."""
        schema = build_schema_from_manifest(
            "testmod",
            option_derivations={
                "enabled": {
                    "derived_settings": [
                        {
                            "setting_key": "MY_ENABLED",
                            "source_options": ["enabled"],
                            "derivation_type": "direct",
                            "expression": {"option": "enabled"},
                        },
                    ],
                },
                "name": {
                    "normalization_rules": [
                        {
                            "source_key": "name",
                            "target_key": "name",
                            "rule_type": "strip",
                        },
                    ],
                    "validation_rules": [
                        {
                            "option_key": "name",
                            "rule_type": "required",
                            "description": "Name is required",
                        },
                    ],
                },
            },
        )
        assert "enabled" in schema.option_derivations
        assert "name" in schema.option_derivations

        enabled_derivation = schema.option_derivations["enabled"]
        assert len(enabled_derivation.derived_settings) == 1
        ds = enabled_derivation.derived_settings[0]
        assert isinstance(ds, DerivedSetting)
        assert ds.setting_key == "MY_ENABLED"
        assert ds.derivation_type == "direct"

        name_derivation = schema.option_derivations["name"]
        assert len(name_derivation.normalization_rules) == 1
        nr = name_derivation.normalization_rules[0]
        assert isinstance(nr, NormalizationRule)
        assert nr.rule_type == "strip"

        assert len(name_derivation.validation_rules) == 1
        vr = name_derivation.validation_rules[0]
        assert isinstance(vr, ValidationRule)
        assert vr.rule_type == "required"
        assert vr.description == "Name is required"

    def test_shared_normalization_and_validation_rules(self) -> None:
        """Shared rules at the derivation level are parsed."""
        schema = build_schema_from_manifest(
            "testmod",
            derivation_rules=[
                {
                    "source_key": "email",
                    "target_key": "email",
                    "rule_type": "strip",
                },
            ],
            validation_rules=[
                {
                    "option_key": "email",
                    "rule_type": "required",
                },
            ],
        )
        assert len(schema.shared_normalization_rules) == 1
        assert len(schema.shared_validation_rules) == 1

        nr = schema.shared_normalization_rules[0]
        assert isinstance(nr, NormalizationRule)
        assert nr.rule_type == "strip"

        vr = schema.shared_validation_rules[0]
        assert isinstance(vr, ValidationRule)
        assert vr.option_key == "email"

    def test_legacy_aliases_in_option_derivation(self) -> None:
        """Legacy aliases nested within option derivations are parsed."""
        schema = build_schema_from_manifest(
            "testmod",
            option_derivations={
                "registration_enabled": {
                    "legacy_aliases": [
                        {
                            "legacy_key": "allow_registration",
                            "current_key": "registration_enabled",
                            "transform": "negate_boolean",
                        },
                    ],
                },
            },
        )
        aliases = schema.option_derivations["registration_enabled"].legacy_aliases
        assert len(aliases) == 1
        alias = aliases[0]
        assert isinstance(alias, LegacyKeyAlias)
        assert alias.legacy_key == "allow_registration"
        assert alias.current_key == "registration_enabled"
        assert alias.transform == "negate_boolean"

    def test_combined_module_and_option_derivations(self) -> None:
        """Both module-level wiring and per-option derivations coexist."""
        schema = build_schema_from_manifest(
            "testmod",
            wiring_projections=[
                {
                    "wiring_field": "apps",
                    "derivation_type": "static",
                    "expression": {"value": ["my_app"]},
                },
            ],
            option_derivations={
                "enabled": {
                    "derived_settings": [
                        {
                            "setting_key": "MY_ENABLED",
                            "derivation_type": "direct",
                            "expression": {"option": "enabled"},
                        },
                    ],
                },
            },
        )
        assert len(schema.module_wiring_projections) == 1
        assert "enabled" in schema.option_derivations
        assert schema.module_wiring_projections[0].wiring_field == "apps"
        assert (
            schema.option_derivations["enabled"].derived_settings[0].setting_key
            == "MY_ENABLED"
        )

    def test_wiring_projection_default_handling(self) -> None:
        """Missing optional fields in wiring projections get sensible defaults."""
        schema = build_schema_from_manifest(
            "testmod",
            wiring_projections=[
                {
                    "wiring_field": "apps",
                    # derivation_type, expression, etc. absent
                },
            ],
        )
        assert len(schema.module_wiring_projections) == 1
        wp = schema.module_wiring_projections[0]
        assert wp.derivation_type == "static"
        assert wp.expression == {}
        assert wp.default == []
        assert wp.description == ""

    def test_derived_setting_with_defaults(self) -> None:
        """Derived settings carry their default values through."""
        schema = build_schema_from_manifest(
            "testmod",
            option_derivations={
                "limit": {
                    "derived_settings": [
                        {
                            "setting_key": "MY_LIMIT",
                            "derivation_type": "direct",
                            "expression": {"option": "limit"},
                            "default": 10,
                        },
                    ],
                },
            },
        )
        ds = schema.option_derivations["limit"].derived_settings[0]
        assert ds.default == 10


# ---------------------------------------------------------------------------
# YAML → ModuleDerivationSchema round-trip (SA6.1)
# ---------------------------------------------------------------------------


class TestYamlToModuleDerivationSchema:
    """Full round-trip test: YAML ``module.yml`` → ``ModuleDerivationSchema``.

    Proves that a ``module.yml`` with a ``derivation:`` section containing
    all six field categories (normalization_rules, validation_rules,
    legacy_aliases, derived_settings, wiring_projections, and
    option_derivations) round-trips through ``yaml.safe_load`` into a
    typed ``ModuleDerivationSchema`` equal to a hand-built equivalent.
    """

    def test_full_derivation_section_round_trip(self) -> None:
        """All six derivation field categories round-trip correctly."""
        yaml_content = """
name: sample-module
version: "1.0.0"

derivation:
  # Module-level lists (shared across all options)
  normalization_rules:
    - source_key: email
      target_key: email
      rule_type: strip
      description: Strip whitespace from email

  validation_rules:
    - option_key: email
      rule_type: required
      description: Email is required

  legacy_aliases:
    - legacy_key: old_email_key
      current_key: email_key
      transform: identity
      description: Renamed in v1.1.0

  derived_settings:
    - setting_key: MY_APP_ENABLED
      source_options:
        - enabled
      derivation_type: direct
      expression:
        option: enabled
      description: Whether the app is enabled

  # Module-level wiring projections
  wiring_projections:
    - wiring_field: apps
      derivation_type: static
      expression:
        value:
          - my_app
      description: My app Django label

  # Per-option derivation metadata
  option_derivations:
    enabled:
      derived_settings:
        - setting_key: MY_APP_ENABLED
          source_options: [enabled]
          derivation_type: direct
          expression:
            option: enabled
          description: Whether the app is enabled

    provider:
      normalization_rules:
        - source_key: provider
          target_key: provider
          rule_type: lowercase
          description: Normalise provider to lowercase
      validation_rules:
        - option_key: provider
          rule_type: choices
          allowed_values:
            - posthog
            - segment
          description: Provider must be a known backend
      derived_settings:
        - setting_key: MY_APP_PROVIDER
          source_options: [provider]
          derivation_type: direct
          expression:
            option: provider
          description: The analytics provider name
"""
        # Step 1: Load YAML through the manifest loader
        from quickscale_core.manifest.loader import load_manifest

        manifest = load_manifest(yaml_content, "sample-module")

        # Step 2: Build a ModuleDerivationSchema from the manifest's
        # derivation fields (raw dicts/lists).
        schema_from_yaml = build_schema_from_manifest(
            manifest_name="sample-module",
            derivation_rules=manifest.derivation_rules,
            validation_rules=manifest.validation_rules,
            legacy_aliases=manifest.legacy_aliases,
            derived_settings=manifest.derived_settings,
            wiring_projections=manifest.wiring_projections,
            option_derivations=manifest.option_derivations,
        )

        # Step 3: Build the equivalent schema by hand using directly constructed
        # dataclasses (not via build_schema_from_manifest) to prove the round-trip
        # is independently correct — no shared-helper bias.
        hand_built = ModuleDerivationSchema(
            module_name="sample-module",
            version="1",
            description="",
            shared_normalization_rules=[
                NormalizationRule(
                    source_key="email",
                    target_key="email",
                    rule_type="strip",
                    description="Strip whitespace from email",
                ),
            ],
            shared_validation_rules=[
                ValidationRule(
                    option_key="email",
                    rule_type="required",
                    description="Email is required",
                ),
            ],
            shared_legacy_aliases=[
                LegacyKeyAlias(
                    legacy_key="old_email_key",
                    current_key="email_key",
                    transform="identity",
                    description="Renamed in v1.1.0",
                ),
            ],
            shared_derived_settings=[
                DerivedSetting(
                    setting_key="MY_APP_ENABLED",
                    source_options=["enabled"],
                    derivation_type="direct",
                    expression={"option": "enabled"},
                    description="Whether the app is enabled",
                ),
            ],
            module_wiring_projections=[
                WiringProjection(
                    wiring_field="apps",
                    derivation_type="static",
                    expression={"value": ["my_app"]},
                    description="My app Django label",
                ),
            ],
            option_derivations={
                "enabled": OptionDerivation(
                    option_key="enabled",
                    derived_settings=[
                        DerivedSetting(
                            setting_key="MY_APP_ENABLED",
                            source_options=["enabled"],
                            derivation_type="direct",
                            expression={"option": "enabled"},
                            description="Whether the app is enabled",
                        ),
                    ],
                ),
                "provider": OptionDerivation(
                    option_key="provider",
                    normalization_rules=[
                        NormalizationRule(
                            source_key="provider",
                            target_key="provider",
                            rule_type="lowercase",
                            description="Normalise provider to lowercase",
                        ),
                    ],
                    validation_rules=[
                        ValidationRule(
                            option_key="provider",
                            rule_type="choices",
                            allowed_values=["posthog", "segment"],
                            description="Provider must be a known backend",
                        ),
                    ],
                    derived_settings=[
                        DerivedSetting(
                            setting_key="MY_APP_PROVIDER",
                            source_options=["provider"],
                            derivation_type="direct",
                            expression={"option": "provider"},
                            description="The analytics provider name",
                        ),
                    ],
                ),
            },
        )

        # Step 4 — Assert equality: frozen dataclass equality covers all
        # nested fields recursively.
        assert schema_from_yaml == hand_built, (
            f"Round-tripped schema differs from hand-built.\n"
            f"From YAML: {schema_from_yaml}\n"
            f"Hand-built: {hand_built}"
        )

        # Also verify key structural properties explicitly so test failure
        # messages are more helpful.
        assert schema_from_yaml.module_name == "sample-module"
        assert len(schema_from_yaml.shared_normalization_rules) == 1
        assert len(schema_from_yaml.shared_validation_rules) == 1
        assert len(schema_from_yaml.shared_legacy_aliases) == 1
        assert len(schema_from_yaml.shared_derived_settings) == 1
        assert (
            schema_from_yaml.shared_derived_settings[0].setting_key == "MY_APP_ENABLED"
        )
        assert len(schema_from_yaml.module_wiring_projections) == 1
        assert len(schema_from_yaml.option_derivations) == 2

    def test_yaml_derivation_section_converts_typed_nested_rules(self) -> None:
        """Nested rules inside option_derivations are typed correctly.

        Verifies that a ``module.yml`` with per-option normalisation,
        validation, and derivation metadata produces the same typed
        ``OptionDerivation`` instances as a hand-built equivalent.
        """
        yaml_content = """
name: sample-module
version: "1.0.0"

derivation:
  option_derivations:
    mode:
      normalization_rules:
        - source_key: mode
          target_key: mode
          rule_type: choice_map
          mapping:
            basic: simple
            advanced: full
          description: Map legacy mode names to canonical values
      validation_rules:
        - option_key: mode
          rule_type: choices
          allowed_values:
            - simple
            - full
          description: Mode must be simple or full
      legacy_aliases:
        - legacy_key: old_mode
          current_key: mode
          transform: rename_value
          transform_params:
            basic: simple
            advanced: full
          description: Renamed and value-mapped in v2.0
      derived_settings:
        - setting_key: APP_MODE
          source_options: [mode]
          derivation_type: direct
          expression:
            option: mode
          description: The application mode setting
      wiring_projections:
        - wiring_field: url_includes
          derivation_type: conditional
          expression:
            branches:
              simple: []
              full:
                - ["api/", "module.urls"]
          description: Wire API URLs only in full mode
"""
        from quickscale_core.manifest.loader import load_manifest

        manifest = load_manifest(yaml_content, "sample-module")

        schema_from_yaml = build_schema_from_manifest(
            manifest_name="sample-module",
            option_derivations=manifest.option_derivations,
        )

        hand_built = build_schema_from_manifest(
            manifest_name="sample-module",
            option_derivations={
                "mode": {
                    "normalization_rules": [
                        {
                            "source_key": "mode",
                            "target_key": "mode",
                            "rule_type": "choice_map",
                            "mapping": {"basic": "simple", "advanced": "full"},
                            "description": "Map legacy mode names to canonical values",
                        },
                    ],
                    "validation_rules": [
                        {
                            "option_key": "mode",
                            "rule_type": "choices",
                            "allowed_values": ["simple", "full"],
                            "description": "Mode must be simple or full",
                        },
                    ],
                    "legacy_aliases": [
                        {
                            "legacy_key": "old_mode",
                            "current_key": "mode",
                            "transform": "rename_value",
                            "transform_params": {"basic": "simple", "advanced": "full"},
                            "description": "Renamed and value-mapped in v2.0",
                        },
                    ],
                    "derived_settings": [
                        {
                            "setting_key": "APP_MODE",
                            "source_options": ["mode"],
                            "derivation_type": "direct",
                            "expression": {"option": "mode"},
                            "description": "The application mode setting",
                        },
                    ],
                    "wiring_projections": [
                        {
                            "wiring_field": "url_includes",
                            "derivation_type": "conditional",
                            "expression": {
                                "branches": {
                                    "simple": [],
                                    "full": [["api/", "module.urls"]],
                                },
                            },
                            "description": "Wire API URLs only in full mode",
                        },
                    ],
                },
            },
        )

        assert schema_from_yaml == hand_built
        mode_opt = schema_from_yaml.option_derivations["mode"]
        assert len(mode_opt.normalization_rules) == 1
        assert len(mode_opt.validation_rules) == 1
        assert len(mode_opt.legacy_aliases) == 1
        assert len(mode_opt.derived_settings) == 1
        assert len(mode_opt.wiring_projections) == 1
