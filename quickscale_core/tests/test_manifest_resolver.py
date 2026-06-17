"""Tests for the manifest-driven module configuration resolver.

These tests exercise the runtime engine that executes derivation rules:
computing defaults, normalizing overrides, validating resolved values,
and projecting derived Django settings.

The resolver is additive to the existing manifest loader and does not
replace or migrate the legacy contract-file path.
"""

from __future__ import annotations

import pytest

from quickscale_core.manifest import (
    ConfigOption,
    DerivedSetting,
    LegacyKeyAlias,
    ModuleDerivationSchema,
    ModuleManifest,
    NormalizationRule,
    OptionDerivation,
    ResolverResult,
    ValidationRule,
    resolve_module_config,
)
from quickscale_core.manifest.resolver import (
    ResolverResult as ResolverResultDirect,
    resolve_module_config as resolve_module_config_direct,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manifest(
    name: str = "test_module",
    mutable_options: dict[str, ConfigOption] | None = None,
    immutable_options: dict[str, ConfigOption] | None = None,
) -> ModuleManifest:
    """Build a minimal ModuleManifest for testing."""
    return ModuleManifest(
        name=name,
        version="1.0.0",
        mutable_options=mutable_options or {},
        immutable_options=immutable_options or {},
    )


def _make_schema(
    module_name: str = "test_module",
    option_derivations: dict[str, OptionDerivation] | None = None,
    shared_normalization_rules: list[NormalizationRule] | None = None,
    shared_validation_rules: list[ValidationRule] | None = None,
) -> ModuleDerivationSchema:
    """Build a minimal ModuleDerivationSchema for testing."""
    return ModuleDerivationSchema(
        module_name=module_name,
        version="1",
        option_derivations=option_derivations or {},
        shared_normalization_rules=shared_normalization_rules or [],
        shared_validation_rules=shared_validation_rules or [],
    )


# ---------------------------------------------------------------------------
# ResolverResult dataclass
# ---------------------------------------------------------------------------


class TestResolverResult:
    """Tests for the ResolverResult dataclass."""

    def test_frozen_result(self) -> None:
        """ResolverResult instances are immutable."""
        result = ResolverResult(
            module_name="test",
            defaults={},
            resolved={},
        )
        with pytest.raises(AttributeError):
            result.module_name = "other"  # type: ignore[misc]

    def test_default_fields(self) -> None:
        """ResolverResult defaults validation_issues, derived_settings, and
        legacy_migrations to empty collections."""
        result = ResolverResult(
            module_name="test",
            defaults={"key": "value"},
            resolved={"key": "value"},
        )
        assert result.validation_issues == []
        assert result.derived_settings == {}
        assert result.legacy_migrations == {}


# ---------------------------------------------------------------------------
# Basic resolution: defaults only
# ---------------------------------------------------------------------------


class TestResolveDefaultsOnly:
    """Tests for resolving with no overrides."""

    def test_empty_manifest_empty_schema(self) -> None:
        """Resolving an empty manifest with an empty schema produces empty
        results."""
        manifest = _make_manifest()
        schema = _make_schema()

        result = resolve_module_config(manifest, schema)

        assert result.module_name == "test_module"
        assert result.defaults == {}
        assert result.resolved == {}
        assert result.validation_issues == []
        assert result.derived_settings == {}
        assert result.legacy_migrations == {}

    def test_defaults_from_manifest(self) -> None:
        """Defaults are extracted from the manifest's config options."""
        manifest = _make_manifest(
            mutable_options={
                "enabled": ConfigOption(
                    name="enabled",
                    option_type="boolean",
                    default=True,
                    django_setting="TEST_ENABLED",
                    mutability="mutable",
                ),
                "provider": ConfigOption(
                    name="provider",
                    option_type="string",
                    default="posthog",
                    django_setting="TEST_PROVIDER",
                    mutability="mutable",
                ),
            },
            immutable_options={
                "auth_method": ConfigOption(
                    name="auth_method",
                    option_type="string",
                    default="email",
                    mutability="immutable",
                ),
            },
        )
        schema = _make_schema()

        result = resolve_module_config(manifest, schema)

        assert result.defaults == {
            "enabled": True,
            "provider": "posthog",
            "auth_method": "email",
        }
        assert result.resolved == result.defaults

    def test_none_default_preserved(self) -> None:
        """A ConfigOption with default=None is preserved in the result."""
        manifest = _make_manifest(
            immutable_options={
                "optional_key": ConfigOption(
                    name="optional_key",
                    option_type="string",
                    default=None,
                    mutability="immutable",
                ),
            },
        )
        schema = _make_schema()

        result = resolve_module_config(manifest, schema)

        assert result.defaults["optional_key"] is None
        assert result.resolved["optional_key"] is None


# ---------------------------------------------------------------------------
# Overrides merging
# ---------------------------------------------------------------------------


class TestResolveWithOverrides:
    """Tests for merging overrides on top of defaults."""

    def test_overrides_replace_defaults(self) -> None:
        """User-supplied overrides replace the corresponding defaults."""
        manifest = _make_manifest(
            mutable_options={
                "enabled": ConfigOption(
                    name="enabled",
                    option_type="boolean",
                    default=True,
                    django_setting="TEST_ENABLED",
                    mutability="mutable",
                ),
                "provider": ConfigOption(
                    name="provider",
                    option_type="string",
                    default="posthog",
                    django_setting="TEST_PROVIDER",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema()

        result = resolve_module_config(manifest, schema, overrides={"enabled": False})

        assert result.resolved["enabled"] is False
        assert result.resolved["provider"] == "posthog"

    def test_overrides_none_treated_as_empty(self) -> None:
        """Passing overrides=None is equivalent to no overrides."""
        manifest = _make_manifest(
            mutable_options={
                "enabled": ConfigOption(
                    name="enabled",
                    option_type="boolean",
                    default=True,
                    django_setting="TEST_ENABLED",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema()

        result = resolve_module_config(manifest, schema, overrides=None)

        assert result.resolved == {"enabled": True}

    def test_overrides_do_not_mutate_input(self) -> None:
        """The resolver does not mutate the caller's overrides dict."""
        manifest = _make_manifest(
            mutable_options={
                "key": ConfigOption(
                    name="key",
                    option_type="string",
                    default="default",
                    django_setting="TEST_KEY",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema()
        overrides = {"key": "override"}

        resolve_module_config(manifest, schema, overrides=overrides)

        assert overrides == {"key": "override"}


# ---------------------------------------------------------------------------
# Normalization rules
# ---------------------------------------------------------------------------


class TestNormalization:
    """Tests for normalization rule execution."""

    def test_strip_normalization(self) -> None:
        """Strip rule removes leading/trailing whitespace from strings."""
        manifest = _make_manifest(
            mutable_options={
                "name": ConfigOption(
                    name="name",
                    option_type="string",
                    default="  hello  ",
                    django_setting="TEST_NAME",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "name": OptionDerivation(
                    option_key="name",
                    normalization_rules=[
                        NormalizationRule(
                            source_key="name",
                            target_key="name",
                            rule_type="strip",
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(manifest, schema)

        assert result.resolved["name"] == "hello"

    def test_lowercase_normalization(self) -> None:
        """Lowercase rule folds string values to lowercase."""
        manifest = _make_manifest(
            mutable_options={
                "provider": ConfigOption(
                    name="provider",
                    option_type="string",
                    default="PostHog",
                    django_setting="TEST_PROVIDER",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "provider": OptionDerivation(
                    option_key="provider",
                    normalization_rules=[
                        NormalizationRule(
                            source_key="provider",
                            target_key="provider",
                            rule_type="lowercase",
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(manifest, schema)

        assert result.resolved["provider"] == "posthog"

    def test_choice_map_normalization(self) -> None:
        """Choice-map rule maps raw values to canonical forms."""
        manifest = _make_manifest(
            mutable_options={
                "mode": ConfigOption(
                    name="mode",
                    option_type="string",
                    default="basic",
                    django_setting="TEST_MODE",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "mode": OptionDerivation(
                    option_key="mode",
                    normalization_rules=[
                        NormalizationRule(
                            source_key="mode",
                            target_key="mode",
                            rule_type="choice_map",
                            mapping={
                                "basic": "page_view",
                                "full": "page_view_with_events",
                                "off": "disabled",
                            },
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(manifest, schema)

        assert result.resolved["mode"] == "page_view"

    def test_choice_map_unmapped_value_passes_through(self) -> None:
        """Choice-map rule leaves unmapped values unchanged."""
        manifest = _make_manifest(
            mutable_options={
                "mode": ConfigOption(
                    name="mode",
                    option_type="string",
                    default="unknown_mode",
                    django_setting="TEST_MODE",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "mode": OptionDerivation(
                    option_key="mode",
                    normalization_rules=[
                        NormalizationRule(
                            source_key="mode",
                            target_key="mode",
                            rule_type="choice_map",
                            mapping={"basic": "page_view"},
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(manifest, schema)

        assert result.resolved["mode"] == "unknown_mode"

    def test_coerce_int_normalization(self) -> None:
        """Coerce-int rule converts string values to integers."""
        manifest = _make_manifest(
            mutable_options={
                "count": ConfigOption(
                    name="count",
                    option_type="integer",
                    default="42",
                    django_setting="TEST_COUNT",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "count": OptionDerivation(
                    option_key="count",
                    normalization_rules=[
                        NormalizationRule(
                            source_key="count",
                            target_key="count",
                            rule_type="coerce_int",
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(manifest, schema)

        assert result.resolved["count"] == 42

    def test_coerce_bool_normalization(self) -> None:
        """Coerce-bool rule converts string values to booleans."""
        manifest = _make_manifest(
            mutable_options={
                "flag": ConfigOption(
                    name="flag",
                    option_type="boolean",
                    default="true",
                    django_setting="TEST_FLAG",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "flag": OptionDerivation(
                    option_key="flag",
                    normalization_rules=[
                        NormalizationRule(
                            source_key="flag",
                            target_key="flag",
                            rule_type="coerce_bool",
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(manifest, schema)

        assert result.resolved["flag"] is True

    def test_identity_normalization(self) -> None:
        """Identity rule passes values through unchanged."""
        manifest = _make_manifest(
            mutable_options={
                "key": ConfigOption(
                    name="key",
                    option_type="string",
                    default="unchanged",
                    django_setting="TEST_KEY",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "key": OptionDerivation(
                    option_key="key",
                    normalization_rules=[
                        NormalizationRule(
                            source_key="key",
                            target_key="key",
                            rule_type="identity",
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(manifest, schema)

        assert result.resolved["key"] == "unchanged"

    def test_shared_strip_rule(self) -> None:
        """Shared normalization rules apply to all options."""
        manifest = _make_manifest(
            mutable_options={
                "name": ConfigOption(
                    name="name",
                    option_type="string",
                    default="  spaced  ",
                    django_setting="TEST_NAME",
                    mutability="mutable",
                ),
                "host": ConfigOption(
                    name="host",
                    option_type="string",
                    default="  example.com  ",
                    django_setting="TEST_HOST",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            shared_normalization_rules=[
                NormalizationRule(
                    source_key="*",
                    target_key="*",
                    rule_type="strip",
                    description="Strip whitespace from all string values",
                ),
            ],
        )

        result = resolve_module_config(manifest, schema)

        assert result.resolved["name"] == "spaced"
        assert result.resolved["host"] == "example.com"

    def test_multiple_normalization_rules_chain(self) -> None:
        """Multiple per-option normalization rules are applied in order."""
        manifest = _make_manifest(
            mutable_options={
                "provider": ConfigOption(
                    name="provider",
                    option_type="string",
                    default="  PostHog  ",
                    django_setting="TEST_PROVIDER",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "provider": OptionDerivation(
                    option_key="provider",
                    normalization_rules=[
                        NormalizationRule(
                            source_key="provider",
                            target_key="provider",
                            rule_type="strip",
                        ),
                        NormalizationRule(
                            source_key="provider",
                            target_key="provider",
                            rule_type="lowercase",
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(manifest, schema)

        assert result.resolved["provider"] == "posthog"


# ---------------------------------------------------------------------------
# Validation rules
# ---------------------------------------------------------------------------


class TestValidation:
    """Tests for validation rule execution."""

    def test_required_validation_passes(self) -> None:
        """Required validation passes when value is present."""
        manifest = _make_manifest(
            mutable_options={
                "api_key": ConfigOption(
                    name="api_key",
                    option_type="string",
                    default="phc_abc123",
                    django_setting="TEST_API_KEY",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "api_key": OptionDerivation(
                    option_key="api_key",
                    validation_rules=[
                        ValidationRule(
                            option_key="api_key",
                            rule_type="required",
                            description="API key is required",
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(manifest, schema)

        assert result.validation_issues == []

    def test_required_validation_fails_on_none(self) -> None:
        """Required validation fails when value is None."""
        manifest = _make_manifest(
            mutable_options={
                "api_key": ConfigOption(
                    name="api_key",
                    option_type="string",
                    default=None,
                    django_setting="TEST_API_KEY",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "api_key": OptionDerivation(
                    option_key="api_key",
                    validation_rules=[
                        ValidationRule(
                            option_key="api_key",
                            rule_type="required",
                            description="API key is required",
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(manifest, schema)

        assert len(result.validation_issues) == 1
        assert "API key is required" in result.validation_issues[0]

    def test_required_validation_fails_on_empty_string(self) -> None:
        """Required validation fails when value is an empty string."""
        manifest = _make_manifest(
            mutable_options={
                "api_key": ConfigOption(
                    name="api_key",
                    option_type="string",
                    default="",
                    django_setting="TEST_API_KEY",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "api_key": OptionDerivation(
                    option_key="api_key",
                    validation_rules=[
                        ValidationRule(
                            option_key="api_key",
                            rule_type="required",
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(manifest, schema)

        assert len(result.validation_issues) == 1

    def test_choices_validation_passes(self) -> None:
        """Choices validation passes when value is in allowed set."""
        manifest = _make_manifest(
            mutable_options={
                "provider": ConfigOption(
                    name="provider",
                    option_type="string",
                    default="posthog",
                    django_setting="TEST_PROVIDER",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "provider": OptionDerivation(
                    option_key="provider",
                    validation_rules=[
                        ValidationRule(
                            option_key="provider",
                            rule_type="choices",
                            allowed_values=["posthog", "segment", "none"],
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(manifest, schema)

        assert result.validation_issues == []

    def test_choices_validation_fails(self) -> None:
        """Choices validation fails when value is not in allowed set."""
        manifest = _make_manifest(
            mutable_options={
                "provider": ConfigOption(
                    name="provider",
                    option_type="string",
                    default="unknown",
                    django_setting="TEST_PROVIDER",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "provider": OptionDerivation(
                    option_key="provider",
                    validation_rules=[
                        ValidationRule(
                            option_key="provider",
                            rule_type="choices",
                            allowed_values=["posthog", "segment"],
                            description="Provider must be a known backend",
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(manifest, schema)

        assert len(result.validation_issues) == 1
        assert "known backend" in result.validation_issues[0]

    def test_range_validation_passes(self) -> None:
        """Range validation passes when value is within bounds."""
        manifest = _make_manifest(
            mutable_options={
                "interval": ConfigOption(
                    name="interval",
                    option_type="integer",
                    default=60,
                    django_setting="TEST_INTERVAL",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "interval": OptionDerivation(
                    option_key="interval",
                    validation_rules=[
                        ValidationRule(
                            option_key="interval",
                            rule_type="range",
                            min_value=1,
                            max_value=3600,
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(manifest, schema)

        assert result.validation_issues == []

    def test_range_validation_fails_below_min(self) -> None:
        """Range validation fails when value is below minimum."""
        manifest = _make_manifest(
            mutable_options={
                "interval": ConfigOption(
                    name="interval",
                    option_type="integer",
                    default=0,
                    django_setting="TEST_INTERVAL",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "interval": OptionDerivation(
                    option_key="interval",
                    validation_rules=[
                        ValidationRule(
                            option_key="interval",
                            rule_type="range",
                            min_value=1,
                            max_value=3600,
                            description="Interval must be between 1 and 3600",
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(manifest, schema)

        assert len(result.validation_issues) == 1
        assert "between 1 and 3600" in result.validation_issues[0]

    def test_range_validation_fails_above_max(self) -> None:
        """Range validation fails when value exceeds maximum."""
        manifest = _make_manifest(
            mutable_options={
                "interval": ConfigOption(
                    name="interval",
                    option_type="integer",
                    default=9999,
                    django_setting="TEST_INTERVAL",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "interval": OptionDerivation(
                    option_key="interval",
                    validation_rules=[
                        ValidationRule(
                            option_key="interval",
                            rule_type="range",
                            min_value=1,
                            max_value=3600,
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(manifest, schema)

        assert len(result.validation_issues) == 1

    def test_pattern_validation_passes(self) -> None:
        """Pattern validation passes when value matches regex."""
        manifest = _make_manifest(
            mutable_options={
                "api_key": ConfigOption(
                    name="api_key",
                    option_type="string",
                    default="phc_abc123",
                    django_setting="TEST_API_KEY",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "api_key": OptionDerivation(
                    option_key="api_key",
                    validation_rules=[
                        ValidationRule(
                            option_key="api_key",
                            rule_type="pattern",
                            pattern=r"^phc_[a-zA-Z0-9]+$",
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(manifest, schema)

        assert result.validation_issues == []

    def test_pattern_validation_fails(self) -> None:
        """Pattern validation fails when value does not match regex."""
        manifest = _make_manifest(
            mutable_options={
                "api_key": ConfigOption(
                    name="api_key",
                    option_type="string",
                    default="invalid_key",
                    django_setting="TEST_API_KEY",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "api_key": OptionDerivation(
                    option_key="api_key",
                    validation_rules=[
                        ValidationRule(
                            option_key="api_key",
                            rule_type="pattern",
                            pattern=r"^phc_[a-zA-Z0-9]+$",
                            description="API key must start with phc_",
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(manifest, schema)

        assert len(result.validation_issues) == 1
        assert "phc_" in result.validation_issues[0]

    def test_shared_validation_rule(self) -> None:
        """Shared validation rules apply to all options."""
        manifest = _make_manifest(
            mutable_options={
                "key1": ConfigOption(
                    name="key1",
                    option_type="string",
                    default="value1",
                    django_setting="TEST_KEY1",
                    mutability="mutable",
                ),
                "key2": ConfigOption(
                    name="key2",
                    option_type="string",
                    default=None,
                    django_setting="TEST_KEY2",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            shared_validation_rules=[
                ValidationRule(
                    option_key="*",
                    rule_type="required",
                    description="All values are required",
                ),
            ],
        )

        result = resolve_module_config(manifest, schema)

        # key1 passes, key2 fails
        assert len(result.validation_issues) == 1
        assert "All values are required" in result.validation_issues[0]

    def test_multiple_validation_issues_collected(self) -> None:
        """Multiple validation failures are all reported."""
        manifest = _make_manifest(
            mutable_options={
                "provider": ConfigOption(
                    name="provider",
                    option_type="string",
                    default="invalid",
                    django_setting="TEST_PROVIDER",
                    mutability="mutable",
                ),
                "api_key": ConfigOption(
                    name="api_key",
                    option_type="string",
                    default=None,
                    django_setting="TEST_API_KEY",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "provider": OptionDerivation(
                    option_key="provider",
                    validation_rules=[
                        ValidationRule(
                            option_key="provider",
                            rule_type="choices",
                            allowed_values=["posthog", "segment"],
                            description="Invalid provider",
                        ),
                    ],
                ),
                "api_key": OptionDerivation(
                    option_key="api_key",
                    validation_rules=[
                        ValidationRule(
                            option_key="api_key",
                            rule_type="required",
                            description="API key is required",
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(manifest, schema)

        assert len(result.validation_issues) == 2
        descriptions = " ".join(result.validation_issues)
        assert "Invalid provider" in descriptions
        assert "API key is required" in descriptions


# ---------------------------------------------------------------------------
# Legacy alias migration
# ---------------------------------------------------------------------------


class TestLegacyAliasMigration:
    """Tests for legacy key alias migration."""

    def test_identity_alias_migrates_key(self) -> None:
        """Identity transform migrates a legacy key to its current name."""
        manifest = _make_manifest(
            mutable_options={
                "api_key": ConfigOption(
                    name="api_key",
                    option_type="string",
                    default="default_key",
                    django_setting="TEST_API_KEY",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "api_key": OptionDerivation(
                    option_key="api_key",
                    legacy_aliases=[
                        LegacyKeyAlias(
                            legacy_key="posthog_api_key",
                            current_key="api_key",
                            transform="identity",
                            description="Renamed in v0.80.0",
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(
            manifest, schema, overrides={"posthog_api_key": "migrated_value"}
        )

        assert result.resolved["api_key"] == "migrated_value"
        assert "posthog_api_key" not in result.resolved
        assert result.legacy_migrations == {"posthog_api_key": "migrated_value"}

    def test_rename_value_alias(self) -> None:
        """Rename-value transform migrates and remaps a legacy key."""
        manifest = _make_manifest(
            mutable_options={
                "tracking_mode": ConfigOption(
                    name="tracking_mode",
                    option_type="string",
                    default="page_view",
                    django_setting="TEST_MODE",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "tracking_mode": OptionDerivation(
                    option_key="tracking_mode",
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
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(
            manifest, schema, overrides={"tracking_level": "basic"}
        )

        assert result.resolved["tracking_mode"] == "page_view"
        assert result.legacy_migrations["tracking_level"] == "page_view"

    def test_split_comma_list_alias(self) -> None:
        """Split-comma-list transform converts a string to a list."""
        manifest = _make_manifest(
            mutable_options={
                "providers": ConfigOption(
                    name="providers",
                    option_type="list",
                    default=[],
                    django_setting="TEST_PROVIDERS",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "providers": OptionDerivation(
                    option_key="providers",
                    legacy_aliases=[
                        LegacyKeyAlias(
                            legacy_key="provider_list",
                            current_key="providers",
                            transform="split_comma_list",
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(
            manifest, schema, overrides={"provider_list": "a, b, c"}
        )

        assert result.resolved["providers"] == ["a", "b", "c"]

    def test_negate_boolean_alias(self) -> None:
        """Negate-boolean transform inverts a boolean legacy value."""
        manifest = _make_manifest(
            mutable_options={
                "anonymous": ConfigOption(
                    name="anonymous",
                    option_type="boolean",
                    default=True,
                    django_setting="TEST_ANONYMOUS",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "anonymous": OptionDerivation(
                    option_key="anonymous",
                    legacy_aliases=[
                        LegacyKeyAlias(
                            legacy_key="identify_users",
                            current_key="anonymous",
                            transform="negate_boolean",
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(
            manifest, schema, overrides={"identify_users": True}
        )

        assert result.resolved["anonymous"] is False

    def test_explicit_current_key_wins_over_legacy(self) -> None:
        """When both legacy and current keys are provided, current wins."""
        manifest = _make_manifest(
            mutable_options={
                "api_key": ConfigOption(
                    name="api_key",
                    option_type="string",
                    default="default",
                    django_setting="TEST_API_KEY",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "api_key": OptionDerivation(
                    option_key="api_key",
                    legacy_aliases=[
                        LegacyKeyAlias(
                            legacy_key="old_key",
                            current_key="api_key",
                            transform="identity",
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(
            manifest,
            schema,
            overrides={"old_key": "legacy_value", "api_key": "explicit_value"},
        )

        assert result.resolved["api_key"] == "explicit_value"

    def test_legacy_key_not_in_overrides_is_skipped(self) -> None:
        """Legacy aliases that are not present in overrides are ignored."""
        manifest = _make_manifest(
            mutable_options={
                "api_key": ConfigOption(
                    name="api_key",
                    option_type="string",
                    default="default",
                    django_setting="TEST_API_KEY",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "api_key": OptionDerivation(
                    option_key="api_key",
                    legacy_aliases=[
                        LegacyKeyAlias(
                            legacy_key="old_key",
                            current_key="api_key",
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(manifest, schema, overrides={})

        assert result.legacy_migrations == {}
        assert result.resolved["api_key"] == "default"


# ---------------------------------------------------------------------------
# Derived settings projection
# ---------------------------------------------------------------------------


class TestDerivedSettingsProjection:
    """Tests for derived Django settings projection."""

    def test_direct_derivation(self) -> None:
        """Direct derivation passes the option value through."""
        manifest = _make_manifest(
            mutable_options={
                "api_key": ConfigOption(
                    name="api_key",
                    option_type="string",
                    default="phc_abc123",
                    django_setting="TEST_API_KEY",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "api_key": OptionDerivation(
                    option_key="api_key",
                    derived_settings=[
                        DerivedSetting(
                            setting_key="POSTHOG_PROJECT_KEY",
                            source_options=["api_key"],
                            derivation_type="direct",
                            expression={"option": "api_key"},
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(manifest, schema)

        assert result.derived_settings["POSTHOG_PROJECT_KEY"] == "phc_abc123"

    def test_static_derivation(self) -> None:
        """Static derivation returns a constant value."""
        manifest = _make_manifest()
        schema = _make_schema(
            option_derivations={
                "version": OptionDerivation(
                    option_key="version",
                    derived_settings=[
                        DerivedSetting(
                            setting_key="MODULE_VERSION",
                            derivation_type="static",
                            expression={"value": "1.0.0"},
                            default="1.0.0",
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(manifest, schema)

        assert result.derived_settings["MODULE_VERSION"] == "1.0.0"

    def test_conditional_derivation(self) -> None:
        """Conditional derivation selects a value based on a source option."""
        manifest = _make_manifest(
            mutable_options={
                "mode": ConfigOption(
                    name="mode",
                    option_type="string",
                    default="full",
                    django_setting="TEST_MODE",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "mode": OptionDerivation(
                    option_key="mode",
                    derived_settings=[
                        DerivedSetting(
                            setting_key="DEBUG_LOGGING",
                            source_options=["mode"],
                            derivation_type="conditional",
                            expression={
                                "branches": {
                                    "basic": False,
                                    "full": True,
                                    "off": False,
                                },
                            },
                            default=False,
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(manifest, schema)

        assert result.derived_settings["DEBUG_LOGGING"] is True

    def test_conditional_derivation_uses_default_for_unknown(self) -> None:
        """Conditional derivation falls back to default for unknown values."""
        manifest = _make_manifest(
            mutable_options={
                "mode": ConfigOption(
                    name="mode",
                    option_type="string",
                    default="unknown",
                    django_setting="TEST_MODE",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "mode": OptionDerivation(
                    option_key="mode",
                    derived_settings=[
                        DerivedSetting(
                            setting_key="DEBUG_LOGGING",
                            source_options=["mode"],
                            derivation_type="conditional",
                            expression={
                                "branches": {"full": True},
                            },
                            default=False,
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(manifest, schema)

        assert result.derived_settings["DEBUG_LOGGING"] is False

    def test_direct_derivation_uses_default_when_source_absent(self) -> None:
        """Direct derivation returns default when source option is None."""
        manifest = _make_manifest(
            mutable_options={
                "api_key": ConfigOption(
                    name="api_key",
                    option_type="string",
                    default=None,
                    django_setting="TEST_API_KEY",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "api_key": OptionDerivation(
                    option_key="api_key",
                    derived_settings=[
                        DerivedSetting(
                            setting_key="POSTHOG_KEY",
                            source_options=["api_key"],
                            derivation_type="direct",
                            expression={"option": "api_key"},
                            default="fallback",
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(manifest, schema)

        assert result.derived_settings["POSTHOG_KEY"] == "fallback"

    def test_computed_derivation_with_template(self) -> None:
        """Computed derivation formats a template from resolved values."""
        manifest = _make_manifest(
            mutable_options={
                "host": ConfigOption(
                    name="host",
                    option_type="string",
                    default="example.com",
                    django_setting="TEST_HOST",
                    mutability="mutable",
                ),
                "port": ConfigOption(
                    name="port",
                    option_type="integer",
                    default=8080,
                    django_setting="TEST_PORT",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "host": OptionDerivation(
                    option_key="host",
                    derived_settings=[
                        DerivedSetting(
                            setting_key="BASE_URL",
                            source_options=["host", "port"],
                            derivation_type="computed",
                            expression={
                                "template": "https://{host}:{port}",
                            },
                            default="",
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(manifest, schema)

        assert result.derived_settings["BASE_URL"] == "https://example.com:8080"

    def test_multiple_derived_settings_collected(self) -> None:
        """All derived settings across all options are collected."""
        manifest = _make_manifest(
            mutable_options={
                "key": ConfigOption(
                    name="key",
                    option_type="string",
                    default="val",
                    django_setting="TEST_KEY",
                    mutability="mutable",
                ),
                "mode": ConfigOption(
                    name="mode",
                    option_type="string",
                    default="on",
                    django_setting="TEST_MODE",
                    mutability="mutable",
                ),
            },
        )
        schema = _make_schema(
            option_derivations={
                "key": OptionDerivation(
                    option_key="key",
                    derived_settings=[
                        DerivedSetting(
                            setting_key="SETTING_A",
                            source_options=["key"],
                            derivation_type="direct",
                            expression={"option": "key"},
                        ),
                    ],
                ),
                "mode": OptionDerivation(
                    option_key="mode",
                    derived_settings=[
                        DerivedSetting(
                            setting_key="SETTING_B",
                            source_options=["mode"],
                            derivation_type="direct",
                            expression={"option": "mode"},
                        ),
                    ],
                ),
            },
        )

        result = resolve_module_config(manifest, schema)

        assert result.derived_settings == {
            "SETTING_A": "val",
            "SETTING_B": "on",
        }


# ---------------------------------------------------------------------------
# End-to-end analytics-shaped test
# ---------------------------------------------------------------------------


class TestAnalyticsShapedResolution:
    """End-to-end test using analytics-shaped derivation rules.

    Proves that the resolver can compute defaults, normalize, validate,
    and project settings for a configuration shape similar to what the
    analytics module will use as its first pilot.
    """

    def _build_analytics_manifest(self) -> ModuleManifest:
        return ModuleManifest(
            name="analytics",
            version="0.80.0",
            mutable_options={
                "enabled": ConfigOption(
                    name="enabled",
                    option_type="boolean",
                    default=True,
                    django_setting="QUICKSCALE_ANALYTICS_ENABLED",
                    mutability="mutable",
                ),
                "provider": ConfigOption(
                    name="provider",
                    option_type="string",
                    default="posthog",
                    django_setting="QUICKSCALE_ANALYTICS_PROVIDER",
                    mutability="mutable",
                ),
                "posthog_host": ConfigOption(
                    name="posthog_host",
                    option_type="string",
                    default="https://us.i.posthog.com",
                    django_setting="QUICKSCALE_ANALYTICS_POSTHOG_HOST",
                    mutability="mutable",
                ),
            },
            immutable_options={},
        )

    def _build_analytics_schema(self) -> ModuleDerivationSchema:
        return ModuleDerivationSchema(
            module_name="analytics",
            version="1",
            option_derivations={
                "provider": OptionDerivation(
                    option_key="provider",
                    normalization_rules=[
                        NormalizationRule(
                            source_key="provider",
                            target_key="provider",
                            rule_type="strip",
                        ),
                        NormalizationRule(
                            source_key="provider",
                            target_key="provider",
                            rule_type="lowercase",
                        ),
                    ],
                    validation_rules=[
                        ValidationRule(
                            option_key="provider",
                            rule_type="choices",
                            allowed_values=["posthog", "segment", "none"],
                            description="Provider must be a known analytics backend",
                        ),
                    ],
                    derived_settings=[
                        DerivedSetting(
                            setting_key="ANALYTICS_PROVIDER",
                            source_options=["provider"],
                            derivation_type="direct",
                            expression={"option": "provider"},
                        ),
                    ],
                ),
                "posthog_host": OptionDerivation(
                    option_key="posthog_host",
                    normalization_rules=[
                        NormalizationRule(
                            source_key="posthog_host",
                            target_key="posthog_host",
                            rule_type="strip",
                        ),
                    ],
                    derived_settings=[
                        DerivedSetting(
                            setting_key="POSTHOG_HOST",
                            source_options=["posthog_host"],
                            derivation_type="direct",
                            expression={"option": "posthog_host"},
                        ),
                    ],
                ),
                "enabled": OptionDerivation(
                    option_key="enabled",
                    derived_settings=[
                        DerivedSetting(
                            setting_key="ANALYTICS_ENABLED",
                            source_options=["enabled"],
                            derivation_type="direct",
                            expression={"option": "enabled"},
                        ),
                    ],
                ),
            },
            shared_normalization_rules=[],
            shared_validation_rules=[],
            description="Analytics module derivation schema",
        )

    def test_defaults_resolve_cleanly(self) -> None:
        """Default analytics config resolves with no validation issues."""
        manifest = self._build_analytics_manifest()
        schema = self._build_analytics_schema()

        result = resolve_module_config(manifest, schema)

        assert result.module_name == "analytics"
        assert result.resolved["enabled"] is True
        assert result.resolved["provider"] == "posthog"
        assert result.resolved["posthog_host"] == "https://us.i.posthog.com"
        assert result.validation_issues == []
        assert result.derived_settings["ANALYTICS_PROVIDER"] == "posthog"
        assert result.derived_settings["ANALYTICS_ENABLED"] is True
        assert result.derived_settings["POSTHOG_HOST"] == "https://us.i.posthog.com"

    def test_override_with_normalization_and_validation(self) -> None:
        """Overrides are normalized and validated through the derivation rules."""
        manifest = self._build_analytics_manifest()
        schema = self._build_analytics_schema()

        result = resolve_module_config(
            manifest,
            schema,
            overrides={"provider": "  PostHog  "},
        )

        # Normalization: strip + lowercase
        assert result.resolved["provider"] == "posthog"
        assert result.validation_issues == []
        assert result.derived_settings["ANALYTICS_PROVIDER"] == "posthog"

    def test_invalid_provider_produces_validation_issue(self) -> None:
        """An invalid provider value produces a validation issue."""
        manifest = self._build_analytics_manifest()
        schema = self._build_analytics_schema()

        result = resolve_module_config(
            manifest,
            schema,
            overrides={"provider": "unknown_backend"},
        )

        assert len(result.validation_issues) == 1
        assert "known analytics backend" in result.validation_issues[0]


# ---------------------------------------------------------------------------
# Managed files threading
# ---------------------------------------------------------------------------


class TestResolverManagedFiles:
    """Tests for managed_files threading through ResolverResult."""

    def test_default_empty_managed_files(self) -> None:
        """ResolverResult defaults managed_files to empty tuple."""
        result = ResolverResult(
            module_name="test",
            defaults={},
            resolved={},
        )
        assert result.managed_files == ()

    def test_resolve_threads_managed_files_from_manifest(self) -> None:
        """resolve_module_config threads managed_files from manifest."""
        from quickscale_core.manifest.schema import ManagedFileDeclaration

        decl = ManagedFileDeclaration(
            key="social_link_tree",
            renderer="social/link_tree.html",
            output_path="quickscale_managed/social/link_tree.html",
        )
        manifest = ModuleManifest(
            name="social",
            version="0.79.0",
            managed_files={"social_link_tree": decl},
        )
        schema = ModuleDerivationSchema(module_name="social", version="1")

        result = resolve_module_config(manifest, schema)

        assert len(result.managed_files) == 1
        assert result.managed_files[0] is decl
        assert result.managed_files[0].key == "social_link_tree"
        assert result.managed_files[0].renderer == "social/link_tree.html"
        assert (
            result.managed_files[0].output_path
            == "quickscale_managed/social/link_tree.html"
        )

    def test_resolve_empty_manifest_produces_empty_managed_files(self) -> None:
        """A manifest with no managed_files produces empty tuple in result."""
        manifest = ModuleManifest(name="m", version="1.0.0")
        schema = ModuleDerivationSchema(module_name="m", version="1")

        result = resolve_module_config(manifest, schema)

        assert result.managed_files == ()

    def test_resolve_multiple_managed_files(self) -> None:
        """Multiple managed_files declarations are all threaded through."""
        from quickscale_core.manifest.schema import ManagedFileDeclaration

        decl1 = ManagedFileDeclaration(
            key="file_a",
            renderer="renderer_a",
            output_path="quickscale_managed/a.html",
        )
        decl2 = ManagedFileDeclaration(
            key="file_b",
            renderer="renderer_b",
            output_path="quickscale_managed/b.html",
        )
        manifest = ModuleManifest(
            name="m",
            version="1.0.0",
            managed_files={"file_a": decl1, "file_b": decl2},
        )
        schema = ModuleDerivationSchema(module_name="m", version="1")

        result = resolve_module_config(manifest, schema)

        assert len(result.managed_files) == 2
        keys = {d.key for d in result.managed_files}
        assert keys == {"file_a", "file_b"}


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


class TestPublicExports:
    """Verify that resolver types are importable from the public API."""

    def test_resolver_result_importable(self) -> None:
        """ResolverResult is exported from quickscale_core.manifest."""
        assert ResolverResult is ResolverResultDirect

    def test_resolve_module_config_importable(self) -> None:
        """resolve_module_config is exported from quickscale_core.manifest."""
        assert resolve_module_config is resolve_module_config_direct
