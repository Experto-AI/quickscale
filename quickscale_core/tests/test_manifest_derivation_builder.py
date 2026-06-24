"""Tests for the manifest-to-schema builder (``build_schema_from_manifest``).

Verifies that raw manifest derivation dicts are correctly converted into typed
:class:`ModuleDerivationSchema` instances.
"""

from __future__ import annotations

from quickscale_core.manifest.derivation import (
    NormalizationRule,
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
