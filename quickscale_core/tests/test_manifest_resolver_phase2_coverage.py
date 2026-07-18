"""Focused edge-branch coverage for the manifest resolver.

The cases here target fallback and coercion behavior that is easy to miss in
the broader resolver tests.  They assert returned values and issue text rather
than implementation-specific coverage mechanics.
"""

from __future__ import annotations

import pytest

from quickscale_core.manifest import (
    DerivedSetting,
    LegacyKeyAlias,
    NormalizationRule,
    ValidationRule,
)
from quickscale_core.manifest.resolver import (
    _apply_legacy_transform,
    _apply_normalization_rule,
    _check_validation_rule,
    _coerce_contribution,
    _project_derived_setting,
)


@pytest.mark.parametrize(
    ("value", "rule_type", "expected"),
    [
        ("not-an-integer", "coerce_int", "not-an-integer"),
        (None, "coerce_int", None),
        (42, "strip", 42),
        (42, "lowercase", 42),
        ("false", "coerce_bool", False),
        (True, "coerce_bool", True),
        (0, "coerce_bool", False),
        (2.5, "coerce_bool", True),
        (object(), "coerce_bool", object),
        ("unchanged", "future_rule", "unchanged"),
    ],
)
def test_normalization_coercion_and_fallbacks(
    value: object, rule_type: str, expected: object
) -> None:
    """Invalid coercions and unsupported rules preserve safe fallback values."""
    rule = NormalizationRule(
        source_key="option",
        target_key="option",
        rule_type=rule_type,
    )

    result = _apply_normalization_rule(value, rule)

    if expected is object:
        assert result is value
    else:
        assert result == expected


@pytest.mark.parametrize(
    ("value", "rule"),
    [
        (
            "not-a-number",
            ValidationRule(option_key="option", rule_type="range"),
        ),
        (
            "abc",
            ValidationRule(
                option_key="option", rule_type="pattern", pattern=r"^[a-z]+$"
            ),
        ),
        (
            "three",
            ValidationRule(option_key="option", rule_type="min_length", min_value=3),
        ),
        (
            "ok",
            ValidationRule(option_key="option", rule_type="max_length", max_value=2),
        ),
        (
            object(),
            ValidationRule(option_key="option", rule_type="min_length", min_value=1),
        ),
        (
            object(),
            ValidationRule(option_key="option", rule_type="max_length", max_value=1),
        ),
        (object(), ValidationRule(option_key="option", rule_type="type")),
    ],
)
def test_validation_edge_rules(value: object, rule: ValidationRule) -> None:
    """Validation handles non-numeric input and passing reserved rules safely."""
    issue = _check_validation_rule(value, rule, "option")

    if rule.rule_type == "range":
        assert issue == "option must be a numeric value"
    else:
        assert issue is None


def test_legacy_transform_mapping_and_fallbacks() -> None:
    """Rename mappings apply while non-boolean and unknown transforms pass through."""
    rename = LegacyKeyAlias(
        legacy_key="old_mode",
        current_key="mode",
        transform="rename_value",
        transform_params={"basic": "page_view"},
    )
    negate = LegacyKeyAlias(
        legacy_key="identify_users",
        current_key="anonymous",
        transform="negate_boolean",
    )
    unknown = LegacyKeyAlias(
        legacy_key="old",
        current_key="new",
        transform="future_transform",
    )
    split = LegacyKeyAlias(
        legacy_key="providers",
        current_key="provider_list",
        transform="split_comma_list",
    )

    assert _apply_legacy_transform("basic", rename) == "page_view"
    assert _apply_legacy_transform("yes", negate) == "yes"
    assert _apply_legacy_transform("value", unknown) == "value"
    assert _apply_legacy_transform(["already", "a", "list"], split) == [
        "already",
        "a",
        "list",
    ]


@pytest.mark.parametrize(
    "setting",
    [
        DerivedSetting(
            setting_key="BROKEN_TEMPLATE",
            derivation_type="computed",
            expression={"template": "{missing}"},
            default="fallback",
        ),
        DerivedSetting(
            setting_key="UNKNOWN_DERIVATION",
            derivation_type="future_derivation",
            default="fallback",
        ),
        DerivedSetting(
            setting_key="ABSENT_SOURCE",
            derivation_type="direct",
            expression={"option": "missing"},
            default="fallback",
        ),
        DerivedSetting(
            setting_key="EMPTY_TEMPLATE",
            derivation_type="computed",
            expression={"template": ""},
            default="fallback",
        ),
    ],
)
def test_derived_setting_fallbacks(setting: DerivedSetting) -> None:
    """Template failures and unknown derivations return declared defaults."""
    assert _project_derived_setting(setting, {}) == "fallback"


@pytest.mark.parametrize(
    ("raw", "wiring_field"),
    [
        (None, "apps"),
        ("not-a-list", "apps"),
        ({"app": "value"}, "middleware"),
        (42, "url_includes"),
    ],
)
def test_contribution_coercion_rejects_non_sequences(
    raw: object, wiring_field: str
) -> None:
    """Only list and tuple contributions are accepted for wiring fields."""
    assert _coerce_contribution(raw, wiring_field) == []
