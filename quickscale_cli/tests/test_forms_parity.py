"""Parity/regression tests for the manifest-driven forms path.

These tests encode the *legacy* hardcoded forms defaults and derivation
behaviour as gold expectations and verify that the manifest-driven
replacement (``forms_manifest.py``) produces identical results for every
public entry point.

The legacy forms defaults lived inline in ``module_config.py`` as a
hardcoded dict inside ``get_default_forms_config()``.  They are now sourced
from the forms ``module.yml`` manifest.

Scope
-----
* Default option values
* String field normalization (rate_limit stripping)
* Resolution (defaults + normalized overrides)
* Validation error messages (integer ranges, boolean types, rate-limit format)
* Wiring-relevant derived Django settings projection
"""

from __future__ import annotations

from typing import Any

from quickscale_cli.forms_manifest import (  # type: ignore[import-untyped]
    DEFAULT_FORMS_DATA_RETENTION_DAYS,
    DEFAULT_FORMS_PER_PAGE,
    DEFAULT_FORMS_RATE_LIMIT,
    DEFAULT_FORMS_SPAM_PROTECTION_ENABLED,
    DEFAULT_FORMS_SUBMISSIONS_API_ENABLED,
    default_forms_module_options,
    normalize_forms_module_options,
    resolve_forms_module_options,
    validate_forms_module_options,
)

# ---------------------------------------------------------------------------
# Gold expectations recovered from the legacy hardcoded forms defaults
# ---------------------------------------------------------------------------

_LEGACY_DEFAULTS: dict[str, Any] = {
    "forms_per_page": 25,
    "spam_protection_enabled": True,
    "rate_limit": "5/hour",
    "data_retention_days": 365,
    "submissions_api_enabled": True,
}


# ===========================================================================
# 1. Default values parity
# ===========================================================================


class TestDefaultsParity:
    """The manifest-driven defaults must match the legacy hardcoded dict."""

    def test_default_options_match_legacy_contract(self) -> None:
        """Every default must equal the value the old hardcoded dict returned."""
        defaults = default_forms_module_options()
        assert defaults == _LEGACY_DEFAULTS

    def test_default_options_keys_are_stable(self) -> None:
        """The key set must not drift from the legacy contract."""
        defaults = default_forms_module_options()
        assert set(defaults.keys()) == set(_LEGACY_DEFAULTS.keys())

    def test_default_forms_per_page(self) -> None:
        defaults = default_forms_module_options()
        assert defaults["forms_per_page"] == DEFAULT_FORMS_PER_PAGE

    def test_default_booleans(self) -> None:
        defaults = default_forms_module_options()
        assert defaults["spam_protection_enabled"] is True
        assert defaults["submissions_api_enabled"] is True

    def test_default_rate_limit(self) -> None:
        defaults = default_forms_module_options()
        assert defaults["rate_limit"] == DEFAULT_FORMS_RATE_LIMIT

    def test_default_data_retention_days(self) -> None:
        defaults = default_forms_module_options()
        assert defaults["data_retention_days"] == DEFAULT_FORMS_DATA_RETENTION_DAYS


# ===========================================================================
# 2. Constants parity
# ===========================================================================


class TestConstantsParity:
    """Public constants must remain identical to the legacy hardcoded values."""

    def test_forms_per_page_constant(self) -> None:
        assert DEFAULT_FORMS_PER_PAGE == 25

    def test_spam_protection_constant(self) -> None:
        assert DEFAULT_FORMS_SPAM_PROTECTION_ENABLED is True

    def test_rate_limit_constant(self) -> None:
        assert DEFAULT_FORMS_RATE_LIMIT == "5/hour"

    def test_data_retention_days_constant(self) -> None:
        assert DEFAULT_FORMS_DATA_RETENTION_DAYS == 365

    def test_submissions_api_constant(self) -> None:
        assert DEFAULT_FORMS_SUBMISSIONS_API_ENABLED is True


# ===========================================================================
# 3. Normalization parity
# ===========================================================================


class TestNormalizationParity:
    """Normalization must behave identically to the legacy contract."""

    def test_rate_limit_strip(self) -> None:
        normalized = normalize_forms_module_options({"rate_limit": " 10/minute "})
        assert normalized["rate_limit"] == "10/minute"

    def test_rate_limit_already_clean(self) -> None:
        normalized = normalize_forms_module_options({"rate_limit": "5/hour"})
        assert normalized["rate_limit"] == "5/hour"

    def test_none_options_returns_empty_dict(self) -> None:
        normalized = normalize_forms_module_options(None)
        assert normalized == {}

    def test_empty_options_returns_empty_dict(self) -> None:
        normalized = normalize_forms_module_options({})
        assert normalized == {}


# ===========================================================================
# 4. Resolution parity (defaults + normalized overrides)
# ===========================================================================


class TestResolutionParity:
    """resolve_forms_module_options must merge defaults + overrides."""

    def test_no_overrides_returns_defaults(self) -> None:
        resolved = resolve_forms_module_options(None)
        assert resolved == _LEGACY_DEFAULTS

    def test_empty_overrides_returns_defaults(self) -> None:
        resolved = resolve_forms_module_options({})
        assert resolved == _LEGACY_DEFAULTS

    def test_partial_override_preserves_other_defaults(self) -> None:
        resolved = resolve_forms_module_options({"spam_protection_enabled": False})
        expected = dict(_LEGACY_DEFAULTS)
        expected["spam_protection_enabled"] = False
        assert resolved == expected

    def test_multiple_overrides(self) -> None:
        resolved = resolve_forms_module_options(
            {
                "forms_per_page": 50,
                "rate_limit": "10/minute",
                "data_retention_days": 30,
            }
        )
        assert resolved["forms_per_page"] == 50
        assert resolved["rate_limit"] == "10/minute"
        assert resolved["data_retention_days"] == 30
        # Untouched defaults remain
        assert resolved["spam_protection_enabled"] is True
        assert resolved["submissions_api_enabled"] is True

    def test_rate_limit_override_is_stripped(self) -> None:
        resolved = resolve_forms_module_options({"rate_limit": " 20/hour "})
        assert resolved["rate_limit"] == "20/hour"

    def test_resolved_keys_match_legacy(self) -> None:
        """The resolved dict must contain exactly the same keys as legacy."""
        resolved = resolve_forms_module_options({"forms_per_page": 10})
        assert set(resolved.keys()) == set(_LEGACY_DEFAULTS.keys())

    def test_integer_coercion(self) -> None:
        """Integer fields must be coerced to int even from string input."""
        resolved = resolve_forms_module_options(
            {"forms_per_page": "40", "data_retention_days": "90"}
        )
        assert resolved["forms_per_page"] == 40
        assert isinstance(resolved["forms_per_page"], int)
        assert resolved["data_retention_days"] == 90
        assert isinstance(resolved["data_retention_days"], int)

    def test_boolean_coercion(self) -> None:
        """Boolean fields must be coerced to bool."""
        resolved = resolve_forms_module_options(
            {"spam_protection_enabled": False, "submissions_api_enabled": False}
        )
        assert resolved["spam_protection_enabled"] is False
        assert isinstance(resolved["spam_protection_enabled"], bool)
        assert resolved["submissions_api_enabled"] is False
        assert isinstance(resolved["submissions_api_enabled"], bool)


# ===========================================================================
# 5. Full validation parity
# ===========================================================================


class TestFullValidationParity:
    """validate_forms_module_options must produce legacy-compatible issues."""

    def test_defaults_pass_validation(self) -> None:
        issues = validate_forms_module_options(None)
        assert issues == []

    def test_invalid_forms_per_page_zero(self) -> None:
        issues = validate_forms_module_options({"forms_per_page": 0})
        assert "modules.forms.forms_per_page must be at least 1" in issues

    def test_invalid_forms_per_page_negative(self) -> None:
        issues = validate_forms_module_options({"forms_per_page": -5})
        assert "modules.forms.forms_per_page must be at least 1" in issues

    def test_invalid_data_retention_days_negative(self) -> None:
        issues = validate_forms_module_options({"data_retention_days": -1})
        assert (
            "modules.forms.data_retention_days must be a non-negative integer" in issues
        )

    def test_zero_data_retention_days_is_valid(self) -> None:
        """0 means keep forever, which is a valid value."""
        issues = validate_forms_module_options({"data_retention_days": 0})
        assert issues == []

    def test_invalid_rate_limit_format(self) -> None:
        issues = validate_forms_module_options({"rate_limit": "invalid"})
        assert any("modules.forms.rate_limit" in issue for issue in issues)

    def test_invalid_rate_limit_period(self) -> None:
        issues = validate_forms_module_options({"rate_limit": "5/week"})
        assert any("modules.forms.rate_limit" in issue for issue in issues)

    def test_valid_rate_limit_formats(self) -> None:
        for rate in ("1/second", "10/minute", "5/hour", "100/day"):
            issues = validate_forms_module_options({"rate_limit": rate})
            rate_issues = [i for i in issues if "rate_limit" in i]
            assert rate_issues == [], f"Expected no rate_limit issues for {rate}"

    def test_multiple_issues_collected(self) -> None:
        """Multiple invalid options should produce multiple issues."""
        issues = validate_forms_module_options(
            {
                "forms_per_page": 0,
                "data_retention_days": -1,
                "rate_limit": "bad",
            }
        )
        assert len(issues) >= 3

    def test_valid_overrides_pass_validation(self) -> None:
        issues = validate_forms_module_options(
            {
                "forms_per_page": 50,
                "spam_protection_enabled": False,
                "rate_limit": "10/minute",
                "data_retention_days": 30,
                "submissions_api_enabled": False,
            }
        )
        assert issues == []


# ===========================================================================
# 6. Wiring-relevant derived settings parity
# ===========================================================================


class TestWiringDerivedSettingsParity:
    """The resolved options must project to the correct Django settings.

    These tests verify that the resolved option dict contains all the fields
    that the forms manifest adapter reads, and that
    the values are in the correct shape for direct projection to Django
    settings.
    """

    def test_resolved_options_contain_all_wiring_fields(self) -> None:
        """The resolved dict must have every key the wiring function reads."""
        resolved = resolve_forms_module_options(None)
        wiring_keys = {
            "forms_per_page",
            "spam_protection_enabled",
            "rate_limit",
            "data_retention_days",
            "submissions_api_enabled",
        }
        assert wiring_keys.issubset(set(resolved.keys()))

    def test_default_wiring_settings_projection(self) -> None:
        """Default resolved options should project to the expected Django settings."""
        resolved = resolve_forms_module_options(None)
        expected_settings = {
            "FORMS_PER_PAGE": 25,
            "FORMS_SPAM_PROTECTION": True,
            "FORMS_RATE_LIMIT": "5/hour",
            "FORMS_DATA_RETENTION_DAYS": 365,
            "FORMS_SUBMISSIONS_API": True,
        }
        assert int(resolved["forms_per_page"]) == expected_settings["FORMS_PER_PAGE"]
        assert (
            bool(resolved["spam_protection_enabled"])
            is expected_settings["FORMS_SPAM_PROTECTION"]
        )
        assert (
            str(resolved["rate_limit"]).strip() == expected_settings["FORMS_RATE_LIMIT"]
        )
        assert (
            int(resolved["data_retention_days"])
            == expected_settings["FORMS_DATA_RETENTION_DAYS"]
        )
        assert (
            bool(resolved["submissions_api_enabled"])
            is expected_settings["FORMS_SUBMISSIONS_API"]
        )

    def test_custom_forms_per_page_wiring_projection(self) -> None:
        """Custom forms_per_page should project correctly through to wiring."""
        resolved = resolve_forms_module_options({"forms_per_page": 50})
        assert int(resolved["forms_per_page"]) == 50

    def test_disabled_spam_protection_wiring_projection(self) -> None:
        """When spam protection is disabled, the flag should project as False."""
        resolved = resolve_forms_module_options({"spam_protection_enabled": False})
        assert bool(resolved["spam_protection_enabled"]) is False

    def test_custom_rate_limit_wiring_projection(self) -> None:
        """Custom rate limit should project through to wiring unchanged."""
        resolved = resolve_forms_module_options({"rate_limit": "10/minute"})
        assert str(resolved["rate_limit"]).strip() == "10/minute"

    def test_disabled_submissions_api_wiring_projection(self) -> None:
        """When submissions API is disabled, the flag should project as False."""
        resolved = resolve_forms_module_options({"submissions_api_enabled": False})
        assert bool(resolved["submissions_api_enabled"]) is False

    def test_custom_data_retention_wiring_projection(self) -> None:
        """Custom data retention days should project through to wiring."""
        resolved = resolve_forms_module_options({"data_retention_days": 90})
        assert int(resolved["data_retention_days"]) == 90
