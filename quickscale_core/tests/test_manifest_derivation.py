"""Tests for module manifest derivation schema.

These tests prove **representation** only: that the derivation dataclasses
can hold analytics-shaped normalisation, validation, legacy-alias, and
setting-projection rules.  They do **not** exercise runtime derivation
execution, YAML loading, or loader wiring — those are deferred to later
roadmap phases.
"""

from __future__ import annotations

import pytest

from quickscale_core.manifest import (
    DerivedSetting,
    LegacyKeyAlias,
    ModuleDerivationSchema,
    NormalizationRule,
    OptionDerivation,
    ValidationRule,
)
from quickscale_core.manifest.derivation import (
    DerivedSetting as DerivedSettingDirect,
    LegacyKeyAlias as LegacyKeyAliasDirect,
    ModuleDerivationSchema as ModuleDerivationSchemaDirect,
    NormalizationRule as NormalizationRuleDirect,
    OptionDerivation as OptionDerivationDirect,
    ValidationRule as ValidationRuleDirect,
)


class TestNormalizationRule:
    """Tests for NormalizationRule dataclass."""

    def test_default_construction(self) -> None:
        """NormalizationRule can be created with required fields only."""
        rule = NormalizationRule(
            source_key="analytics_provider",
            target_key="analytics_provider",
            rule_type="identity",
        )
        assert rule.source_key == "analytics_provider"
        assert rule.target_key == "analytics_provider"
        assert rule.rule_type == "identity"
        assert rule.mapping == {}
        assert rule.description == ""

    def test_choice_map_rule(self) -> None:
        """NormalizationRule can represent a choice-map transformation."""
        rule = NormalizationRule(
            source_key="tracking_mode",
            target_key="tracking_mode",
            rule_type="choice_map",
            mapping={
                "page": "page_view",
                "full": "page_view_with_events",
                "off": "disabled",
            },
            description="Normalize legacy tracking mode values",
        )
        assert rule.rule_type == "choice_map"
        assert rule.mapping["page"] == "page_view"
        assert rule.mapping["off"] == "disabled"
        assert "legacy" in rule.description

    def test_is_frozen(self) -> None:
        """NormalizationRule instances are immutable."""
        rule = NormalizationRule(
            source_key="key",
            target_key="key",
            rule_type="identity",
        )
        with pytest.raises(AttributeError):
            rule.source_key = "other"  # type: ignore[misc]


class TestValidationRule:
    """Tests for ValidationRule dataclass."""

    def test_choices_validation(self) -> None:
        """ValidationRule can represent a choices constraint."""
        rule = ValidationRule(
            option_key="analytics_provider",
            rule_type="choices",
            allowed_values=["posthog", "segment", "none"],
            description="Provider must be a known analytics backend",
        )
        assert rule.rule_type == "choices"
        assert "posthog" in rule.allowed_values
        assert rule.min_value is None
        assert rule.max_value is None
        assert rule.pattern is None

    def test_range_validation(self) -> None:
        """ValidationRule can represent a numeric range constraint."""
        rule = ValidationRule(
            option_key="flush_interval_seconds",
            rule_type="range",
            min_value=1,
            max_value=3600,
            description="Flush interval must be between 1 and 3600 seconds",
        )
        assert rule.rule_type == "range"
        assert rule.min_value == 1
        assert rule.max_value == 3600
        assert rule.allowed_values == []

    def test_pattern_validation(self) -> None:
        """ValidationRule can represent a regex pattern constraint."""
        rule = ValidationRule(
            option_key="api_key",
            rule_type="pattern",
            pattern=r"^phc_[a-zA-Z0-9]+$",
            description="PostHog API key must start with phc_",
        )
        assert rule.rule_type == "pattern"
        assert rule.pattern == r"^phc_[a-zA-Z0-9]+$"

    def test_is_frozen(self) -> None:
        """ValidationRule instances are immutable."""
        rule = ValidationRule(option_key="k", rule_type="required")
        with pytest.raises(AttributeError):
            rule.option_key = "other"  # type: ignore[misc]


class TestLegacyKeyAlias:
    """Tests for LegacyKeyAlias dataclass."""

    def test_identity_alias(self) -> None:
        """LegacyKeyAlias can represent a simple key rename."""
        alias = LegacyKeyAlias(
            legacy_key="enable_analytics",
            current_key="analytics_enabled",
            description="Renamed in v0.80.0",
        )
        assert alias.legacy_key == "enable_analytics"
        assert alias.current_key == "analytics_enabled"
        assert alias.transform == "identity"
        assert alias.transform_params == {}

    def test_rename_value_alias(self) -> None:
        """LegacyKeyAlias can carry a value transformation."""
        alias = LegacyKeyAlias(
            legacy_key="tracking_level",
            current_key="tracking_mode",
            transform="rename_value",
            transform_params={
                "basic": "page_view",
                "advanced": "page_view_with_events",
            },
            description="tracking_level renamed and values remapped",
        )
        assert alias.transform == "rename_value"
        assert alias.transform_params["basic"] == "page_view"

    def test_is_frozen(self) -> None:
        """LegacyKeyAlias instances are immutable."""
        alias = LegacyKeyAlias(legacy_key="old", current_key="new")
        with pytest.raises(AttributeError):
            alias.legacy_key = "other"  # type: ignore[misc]


class TestDerivedSetting:
    """Tests for DerivedSetting dataclass."""

    def test_direct_derivation(self) -> None:
        """DerivedSetting can represent a direct pass-through setting."""
        setting = DerivedSetting(
            setting_key="POSTHOG_PROJECT_KEY",
            source_options=["api_key"],
            derivation_type="direct",
            expression={"option": "api_key"},
            description="PostHog project key for frontend snippet",
        )
        assert setting.setting_key == "POSTHOG_PROJECT_KEY"
        assert setting.source_options == ["api_key"]
        assert setting.derivation_type == "direct"
        assert setting.default is None

    def test_conditional_derivation(self) -> None:
        """DerivedSetting can represent a conditional setting."""
        setting = DerivedSetting(
            setting_key="ANALYTICS_DEBUG",
            source_options=["tracking_mode"],
            derivation_type="conditional",
            expression={
                "branches": {
                    "page_view": False,
                    "page_view_with_events": True,
                    "disabled": False,
                },
            },
            default=False,
            description="Enable analytics debug logging for full tracking",
        )
        assert setting.derivation_type == "conditional"
        assert setting.default is False
        assert "branches" in setting.expression

    def test_static_derivation(self) -> None:
        """DerivedSetting can represent a static constant setting."""
        setting = DerivedSetting(
            setting_key="ANALYTICS_MODULE_VERSION",
            derivation_type="static",
            expression={"value": "0.80.0"},
            default="0.80.0",
            description="Analytics module version constant",
        )
        assert setting.derivation_type == "static"
        assert setting.source_options == []
        assert setting.default == "0.80.0"

    def test_computed_derivation(self) -> None:
        """DerivedSetting can represent a computed setting from multiple sources."""
        setting = DerivedSetting(
            setting_key="ANALYTICS_ENABLED",
            source_options=["analytics_enabled", "tracking_mode"],
            derivation_type="computed",
            expression={
                "template": "{analytics_enabled} and {tracking_mode} != 'disabled'",
            },
            default=False,
            description="Analytics is enabled when flag is on and mode is not disabled",
        )
        assert setting.derivation_type == "computed"
        assert len(setting.source_options) == 2

    def test_is_frozen(self) -> None:
        """DerivedSetting instances are immutable."""
        setting = DerivedSetting(setting_key="X")
        with pytest.raises(AttributeError):
            setting.setting_key = "Y"  # type: ignore[misc]


class TestOptionDerivation:
    """Tests for OptionDerivation dataclass."""

    def test_empty_option_derivation(self) -> None:
        """OptionDerivation can be created with just an option key."""
        od = OptionDerivation(option_key="analytics_enabled")
        assert od.option_key == "analytics_enabled"
        assert od.normalization_rules == []
        assert od.validation_rules == []
        assert od.legacy_aliases == []
        assert od.derived_settings == []

    def test_full_option_derivation(self) -> None:
        """OptionDerivation can bundle all rule types for one option."""
        norm = NormalizationRule(
            source_key="tracking_mode",
            target_key="tracking_mode",
            rule_type="choice_map",
            mapping={"basic": "page_view"},
        )
        val = ValidationRule(
            option_key="tracking_mode",
            rule_type="choices",
            allowed_values=["page_view", "page_view_with_events", "disabled"],
        )
        alias = LegacyKeyAlias(
            legacy_key="tracking_level",
            current_key="tracking_mode",
            transform="rename_value",
            transform_params={"basic": "page_view"},
        )
        derived = DerivedSetting(
            setting_key="POSTHOG_DEBUG",
            source_options=["tracking_mode"],
            derivation_type="conditional",
            expression={"branches": {"page_view_with_events": True}},
            default=False,
        )

        od = OptionDerivation(
            option_key="tracking_mode",
            normalization_rules=[norm],
            validation_rules=[val],
            legacy_aliases=[alias],
            derived_settings=[derived],
        )

        assert len(od.normalization_rules) == 1
        assert len(od.validation_rules) == 1
        assert len(od.legacy_aliases) == 1
        assert len(od.derived_settings) == 1
        assert od.normalization_rules[0].rule_type == "choice_map"
        assert od.derived_settings[0].setting_key == "POSTHOG_DEBUG"

    def test_is_frozen(self) -> None:
        """OptionDerivation instances are immutable."""
        od = OptionDerivation(option_key="x")
        with pytest.raises(AttributeError):
            od.option_key = "y"  # type: ignore[misc]


class TestModuleDerivationSchema:
    """Tests for ModuleDerivationSchema dataclass."""

    def test_empty_schema(self) -> None:
        """ModuleDerivationSchema can be created with required fields only."""
        schema = ModuleDerivationSchema(
            module_name="analytics",
            version="1",
        )
        assert schema.module_name == "analytics"
        assert schema.version == "1"
        assert schema.option_derivations == {}
        assert schema.shared_normalization_rules == []
        assert schema.shared_validation_rules == []
        assert schema.description == ""

    def test_get_option_derivation_found(self) -> None:
        """get_option_derivation returns the matching derivation."""
        od = OptionDerivation(option_key="api_key")
        schema = ModuleDerivationSchema(
            module_name="analytics",
            version="1",
            option_derivations={"api_key": od},
        )
        result = schema.get_option_derivation("api_key")
        assert result is od

    def test_get_option_derivation_not_found(self) -> None:
        """get_option_derivation returns None for unknown keys."""
        schema = ModuleDerivationSchema(
            module_name="analytics",
            version="1",
        )
        assert schema.get_option_derivation("nonexistent") is None

    def test_get_all_derived_settings(self) -> None:
        """get_all_derived_settings collects settings across all options."""
        s1 = DerivedSetting(setting_key="POSTHOG_KEY", source_options=["api_key"])
        s2 = DerivedSetting(
            setting_key="POSTHOG_DEBUG", source_options=["tracking_mode"]
        )
        schema = ModuleDerivationSchema(
            module_name="analytics",
            version="1",
            option_derivations={
                "api_key": OptionDerivation(
                    option_key="api_key", derived_settings=[s1]
                ),
                "tracking_mode": OptionDerivation(
                    option_key="tracking_mode", derived_settings=[s2]
                ),
            },
        )
        all_settings = schema.get_all_derived_settings()
        assert len(all_settings) == 2
        setting_keys = {s.setting_key for s in all_settings}
        assert setting_keys == {"POSTHOG_KEY", "POSTHOG_DEBUG"}

    def test_get_all_derived_settings_empty(self) -> None:
        """get_all_derived_settings returns empty list when no derivations."""
        schema = ModuleDerivationSchema(
            module_name="analytics",
            version="1",
        )
        assert schema.get_all_derived_settings() == []

    def test_get_all_legacy_aliases(self) -> None:
        """get_all_legacy_aliases collects aliases across all options."""
        a1 = LegacyKeyAlias(legacy_key="old_key", current_key="api_key")
        a2 = LegacyKeyAlias(legacy_key="old_mode", current_key="tracking_mode")
        schema = ModuleDerivationSchema(
            module_name="analytics",
            version="1",
            option_derivations={
                "api_key": OptionDerivation(option_key="api_key", legacy_aliases=[a1]),
                "tracking_mode": OptionDerivation(
                    option_key="tracking_mode", legacy_aliases=[a2]
                ),
            },
        )
        all_aliases = schema.get_all_legacy_aliases()
        assert len(all_aliases) == 2
        legacy_keys = {a.legacy_key for a in all_aliases}
        assert legacy_keys == {"old_key", "old_mode"}

    def test_get_all_legacy_aliases_empty(self) -> None:
        """get_all_legacy_aliases returns empty list when no aliases."""
        schema = ModuleDerivationSchema(
            module_name="analytics",
            version="1",
        )
        assert schema.get_all_legacy_aliases() == []

    def test_shared_rules(self) -> None:
        """ModuleDerivationSchema can carry shared module-wide rules."""
        shared_norm = NormalizationRule(
            source_key="*",
            target_key="*",
            rule_type="strip",
            description="Strip whitespace from all string values",
        )
        shared_val = ValidationRule(
            option_key="*",
            rule_type="type",
            description="All values must be YAML-safe scalar types",
        )
        schema = ModuleDerivationSchema(
            module_name="analytics",
            version="1",
            shared_normalization_rules=[shared_norm],
            shared_validation_rules=[shared_val],
            description="Analytics module derivation schema",
        )
        assert len(schema.shared_normalization_rules) == 1
        assert len(schema.shared_validation_rules) == 1
        assert schema.description == "Analytics module derivation schema"

    def test_is_frozen(self) -> None:
        """ModuleDerivationSchema instances are immutable."""
        schema = ModuleDerivationSchema(module_name="analytics", version="1")
        with pytest.raises(AttributeError):
            schema.module_name = "other"  # type: ignore[misc]


class TestAnalyticsShapedRepresentation:
    """End-to-end representation test using analytics-shaped rules.

    Proves that the derivation schema can represent the kind of
    normalisation, validation, legacy-alias, and setting-projection
    rules that the analytics module will need when it becomes the
    first pilot for the manifest-driven path.
    """

    def test_analytics_derivation_schema_representation(self) -> None:
        """A full analytics-shaped derivation schema can be represented."""
        # api_key option: direct pass-through to POSTHOG_PROJECT_KEY
        api_key_derivation = OptionDerivation(
            option_key="api_key",
            normalization_rules=[
                NormalizationRule(
                    source_key="api_key",
                    target_key="api_key",
                    rule_type="strip",
                    description="Strip whitespace from API key",
                ),
            ],
            validation_rules=[
                ValidationRule(
                    option_key="api_key",
                    rule_type="required",
                    description="PostHog API key is required when analytics is enabled",
                ),
                ValidationRule(
                    option_key="api_key",
                    rule_type="pattern",
                    pattern=r"^phc_[a-zA-Z0-9]+$",
                    description="PostHog API key must start with phc_",
                ),
            ],
            legacy_aliases=[
                LegacyKeyAlias(
                    legacy_key="posthog_api_key",
                    current_key="api_key",
                    description="Renamed from posthog_api_key in v0.80.0",
                ),
            ],
            derived_settings=[
                DerivedSetting(
                    setting_key="POSTHOG_PROJECT_KEY",
                    source_options=["api_key"],
                    derivation_type="direct",
                    expression={"option": "api_key"},
                    description="PostHog project key for frontend snippet",
                ),
            ],
        )

        # tracking_mode option: choice-map normalization + conditional setting
        tracking_mode_derivation = OptionDerivation(
            option_key="tracking_mode",
            normalization_rules=[
                NormalizationRule(
                    source_key="tracking_mode",
                    target_key="tracking_mode",
                    rule_type="choice_map",
                    mapping={
                        "basic": "page_view",
                        "full": "page_view_with_events",
                        "off": "disabled",
                    },
                    description="Normalize legacy tracking mode values",
                ),
            ],
            validation_rules=[
                ValidationRule(
                    option_key="tracking_mode",
                    rule_type="choices",
                    allowed_values=[
                        "page_view",
                        "page_view_with_events",
                        "disabled",
                    ],
                    description="Tracking mode must be a known value",
                ),
            ],
            legacy_aliases=[
                LegacyKeyAlias(
                    legacy_key="tracking_level",
                    current_key="tracking_mode",
                    transform="rename_value",
                    transform_params={
                        "basic": "page_view",
                        "advanced": "page_view_with_events",
                        "none": "disabled",
                    },
                    description="tracking_level renamed to tracking_mode",
                ),
            ],
            derived_settings=[
                DerivedSetting(
                    setting_key="POSTHOG_CAPTURE_MODE",
                    source_options=["tracking_mode"],
                    derivation_type="direct",
                    expression={"option": "tracking_mode"},
                    description="PostHog capture mode",
                ),
                DerivedSetting(
                    setting_key="ANALYTICS_DEBUG",
                    source_options=["tracking_mode"],
                    derivation_type="conditional",
                    expression={
                        "branches": {
                            "page_view": False,
                            "page_view_with_events": True,
                            "disabled": False,
                        },
                    },
                    default=False,
                    description="Debug logging for full tracking mode",
                ),
            ],
        )

        schema = ModuleDerivationSchema(
            module_name="analytics",
            version="1",
            option_derivations={
                "api_key": api_key_derivation,
                "tracking_mode": tracking_mode_derivation,
            },
            shared_normalization_rules=[
                NormalizationRule(
                    source_key="*",
                    target_key="*",
                    rule_type="strip",
                    description="Strip whitespace from all string option values",
                ),
            ],
            shared_validation_rules=[],
            description=(
                "Derivation schema for the analytics module. "
                "Describes how module.yml options normalise, validate, "
                "and project into Django settings."
            ),
        )

        # Verify structure
        assert schema.module_name == "analytics"
        assert schema.version == "1"
        assert len(schema.option_derivations) == 2
        assert len(schema.shared_normalization_rules) == 1

        # Verify helper methods
        assert schema.get_option_derivation("api_key") is api_key_derivation
        assert schema.get_option_derivation("nonexistent") is None

        all_settings = schema.get_all_derived_settings()
        assert len(all_settings) == 3  # 1 from api_key + 2 from tracking_mode
        setting_keys = {s.setting_key for s in all_settings}
        assert setting_keys == {
            "POSTHOG_PROJECT_KEY",
            "POSTHOG_CAPTURE_MODE",
            "ANALYTICS_DEBUG",
        }

        all_aliases = schema.get_all_legacy_aliases()
        assert len(all_aliases) == 2
        legacy_keys = {a.legacy_key for a in all_aliases}
        assert legacy_keys == {"posthog_api_key", "tracking_level"}


class TestPublicExports:
    """Verify that derivation types are importable from the public API."""

    def test_types_importable_from_package(self) -> None:
        """All six derivation types are exported from quickscale_core.manifest."""
        # These imports are at module top; this test just confirms they
        # are the same objects as the direct derivation-module imports.
        assert NormalizationRule is NormalizationRuleDirect
        assert ValidationRule is ValidationRuleDirect
        assert LegacyKeyAlias is LegacyKeyAliasDirect
        assert DerivedSetting is DerivedSettingDirect
        assert OptionDerivation is OptionDerivationDirect
        assert ModuleDerivationSchema is ModuleDerivationSchemaDirect
