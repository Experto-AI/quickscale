"""Parity/regression tests for the manifest-driven analytics path.

These tests encode the *legacy* ``analytics_contract.py`` behaviour as gold
expectations and verify that the manifest-driven replacement
(``analytics_manifest.py``) produces identical results for every public
entry point.

The legacy contract file was deleted when the analytics module was migrated
to the manifest-driven path (Phase 4, Finding 1).  The gold values below
were recovered from the last committed version of ``analytics_contract.py``
and from the analytics ``module.yml`` manifest that now owns the defaults.

Scope
-----
* Default option values
* Provider normalisation (strip + lowercase)
* Env-var reference normalisation and validation
* PostHog host URL canonicalisation (scheme prepend, trailing slash removal)
* Resolution (defaults + normalised overrides)
* Validation error messages (provider choices, env-var pattern, host URL, booleans)
* Production-targeting predicate
* Wiring-relevant derived Django settings projection
"""

from __future__ import annotations

from typing import Any

import pytest

from quickscale_cli.analytics_manifest import (  # type: ignore[import-untyped]
    ANALYTICS_EVENT_FORM_SUBMIT,
    ANALYTICS_EVENT_PAGEVIEW,
    ANALYTICS_EVENT_SOCIAL_LINK_CLICK,
    ANALYTICS_POSTHOG_DEFAULT_HOST,
    ANALYTICS_POSTHOG_EU_HOST,
    ANALYTICS_PROVIDER_POSTHOG,
    ANALYTICS_PROVIDERS,
    DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR,
    DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR,
    analytics_production_targeted,
    default_analytics_module_options,
    normalize_analytics_module_options,
    resolve_analytics_module_options,
    validate_analytics_env_var_reference,
    validate_analytics_module_options,
)

# ---------------------------------------------------------------------------
# Gold expectations recovered from the legacy analytics_contract.py
# ---------------------------------------------------------------------------

_LEGACY_DEFAULTS: dict[str, Any] = {
    "enabled": True,
    "provider": "posthog",
    "posthog_api_key_env_var": "POSTHOG_API_KEY",
    "posthog_host_env_var": "POSTHOG_HOST",
    "posthog_host": "https://us.i.posthog.com",
    "exclude_debug": True,
    "exclude_staff": False,
    "anonymous_by_default": True,
}


# ===========================================================================
# 1. Default values parity
# ===========================================================================


class TestDefaultsParity:
    """The manifest-driven defaults must match the legacy hardcoded dict."""

    def test_default_options_match_legacy_contract(self) -> None:
        """Every default must equal the value the old contract file returned."""
        defaults = default_analytics_module_options()
        assert defaults == _LEGACY_DEFAULTS

    def test_default_options_keys_are_stable(self) -> None:
        """The key set must not drift from the legacy contract."""
        defaults = default_analytics_module_options()
        assert set(defaults.keys()) == set(_LEGACY_DEFAULTS.keys())

    def test_default_provider_is_posthog(self) -> None:
        defaults = default_analytics_module_options()
        assert defaults["provider"] == ANALYTICS_PROVIDER_POSTHOG

    def test_default_booleans(self) -> None:
        defaults = default_analytics_module_options()
        assert defaults["enabled"] is True
        assert defaults["exclude_debug"] is True
        assert defaults["exclude_staff"] is False
        assert defaults["anonymous_by_default"] is True

    def test_default_host_is_us_region(self) -> None:
        defaults = default_analytics_module_options()
        assert defaults["posthog_host"] == ANALYTICS_POSTHOG_DEFAULT_HOST


# ===========================================================================
# 2. Constants parity
# ===========================================================================


class TestConstantsParity:
    """Public constants must remain identical to the legacy contract values."""

    def test_provider_constants(self) -> None:
        assert ANALYTICS_PROVIDER_POSTHOG == "posthog"
        assert ANALYTICS_PROVIDERS == ("posthog",)

    def test_env_var_defaults(self) -> None:
        assert DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR == "POSTHOG_API_KEY"
        assert DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR == "POSTHOG_HOST"

    def test_host_constants(self) -> None:
        assert ANALYTICS_POSTHOG_DEFAULT_HOST == "https://us.i.posthog.com"
        assert ANALYTICS_POSTHOG_EU_HOST == "https://eu.i.posthog.com"

    def test_event_name_constants(self) -> None:
        assert ANALYTICS_EVENT_PAGEVIEW == "$pageview"
        assert ANALYTICS_EVENT_FORM_SUBMIT == "form_submit"
        assert ANALYTICS_EVENT_SOCIAL_LINK_CLICK == "social_link_click"


# ===========================================================================
# 3. Normalisation parity
# ===========================================================================


class TestNormalizationParity:
    """Normalisation must behave identically to the legacy contract."""

    def test_provider_strip_and_lowercase(self) -> None:
        normalized = normalize_analytics_module_options({"provider": " PostHog "})
        assert normalized["provider"] == "posthog"

    def test_provider_already_lower(self) -> None:
        normalized = normalize_analytics_module_options({"provider": "posthog"})
        assert normalized["provider"] == "posthog"

    def test_env_var_strip(self) -> None:
        normalized = normalize_analytics_module_options(
            {
                "posthog_api_key_env_var": " MY_KEY ",
                "posthog_host_env_var": " MY_HOST ",
            }
        )
        assert normalized["posthog_api_key_env_var"] == "MY_KEY"
        assert normalized["posthog_host_env_var"] == "MY_HOST"

    def test_none_options_returns_empty_dict(self) -> None:
        normalized = normalize_analytics_module_options(None)
        assert normalized == {}

    def test_empty_options_returns_empty_dict(self) -> None:
        normalized = normalize_analytics_module_options({})
        assert normalized == {}


# ===========================================================================
# 4. Host canonicalisation parity (legacy _normalize_posthog_host)
# ===========================================================================


class TestHostCanonicalizationParity:
    """PostHog host URL canonicalisation must match legacy behaviour exactly."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            # Already canonical
            ("https://us.i.posthog.com", "https://us.i.posthog.com"),
            ("https://eu.i.posthog.com", "https://eu.i.posthog.com"),
            # Missing scheme — must prepend https://
            ("eu.i.posthog.com", "https://eu.i.posthog.com"),
            ("us.i.posthog.com", "https://us.i.posthog.com"),
            # Trailing slash — must strip
            ("https://us.i.posthog.com/", "https://us.i.posthog.com"),
            ("https://eu.i.posthog.com///", "https://eu.i.posthog.com"),
            # Missing scheme + trailing slash
            ("eu.i.posthog.com/", "https://eu.i.posthog.com"),
            # Whitespace stripping
            ("  https://us.i.posthog.com  ", "https://us.i.posthog.com"),
            # Leading slashes stripped before scheme prepend
            ("//eu.i.posthog.com", "https://eu.i.posthog.com"),
            # HTTP scheme preserved (not upgraded to HTTPS)
            ("http://localhost:8000", "http://localhost:8000"),
            # Empty string
            ("", ""),
            ("  ", ""),
        ],
    )
    def test_host_canonicalization(self, raw: str, expected: str) -> None:
        """The resolve path must canonicalize the host identically to legacy."""
        resolved = resolve_analytics_module_options({"posthog_host": raw})
        assert resolved["posthog_host"] == expected

    def test_host_canonicalization_via_normalize(self) -> None:
        """Normalize alone should also canonicalize the host."""
        normalized = normalize_analytics_module_options(
            {"posthog_host": "eu.i.posthog.com/"}
        )
        assert normalized["posthog_host"] == "https://eu.i.posthog.com"


# ===========================================================================
# 5. Resolution parity (defaults + normalised overrides)
# ===========================================================================


class TestResolutionParity:
    """resolve_analytics_module_options must merge defaults + overrides."""

    def test_no_overrides_returns_defaults(self) -> None:
        resolved = resolve_analytics_module_options(None)
        assert resolved == _LEGACY_DEFAULTS

    def test_empty_overrides_returns_defaults(self) -> None:
        resolved = resolve_analytics_module_options({})
        assert resolved == _LEGACY_DEFAULTS

    def test_partial_override_preserves_other_defaults(self) -> None:
        resolved = resolve_analytics_module_options({"exclude_staff": True})
        expected = dict(_LEGACY_DEFAULTS)
        expected["exclude_staff"] = True
        assert resolved == expected

    def test_multiple_overrides(self) -> None:
        resolved = resolve_analytics_module_options(
            {
                "posthog_host": "eu.i.posthog.com",
                "exclude_staff": True,
                "anonymous_by_default": False,
            }
        )
        assert resolved["posthog_host"] == "https://eu.i.posthog.com"
        assert resolved["exclude_staff"] is True
        assert resolved["anonymous_by_default"] is False
        # Untouched defaults remain
        assert resolved["enabled"] is True
        assert resolved["provider"] == "posthog"
        assert resolved["exclude_debug"] is True

    def test_provider_override_is_normalized(self) -> None:
        resolved = resolve_analytics_module_options({"provider": " POSTHOG "})
        assert resolved["provider"] == "posthog"

    def test_env_var_overrides_are_stripped(self) -> None:
        resolved = resolve_analytics_module_options(
            {
                "posthog_api_key_env_var": " CUSTOM_KEY ",
                "posthog_host_env_var": " CUSTOM_HOST ",
            }
        )
        assert resolved["posthog_api_key_env_var"] == "CUSTOM_KEY"
        assert resolved["posthog_host_env_var"] == "CUSTOM_HOST"

    def test_resolved_keys_match_legacy(self) -> None:
        """The resolved dict must contain exactly the same keys as legacy."""
        resolved = resolve_analytics_module_options({"exclude_staff": True})
        assert set(resolved.keys()) == set(_LEGACY_DEFAULTS.keys())


# ===========================================================================
# 6. Env-var validation parity
# ===========================================================================


class TestEnvVarValidationParity:
    """Env-var reference validation must match legacy pattern checks."""

    def test_valid_env_var_returns_none(self) -> None:
        assert (
            validate_analytics_env_var_reference(
                "posthog_api_key_env_var", "POSTHOG_API_KEY"
            )
            is None
        )

    def test_valid_env_var_with_underscores(self) -> None:
        assert (
            validate_analytics_env_var_reference(
                "posthog_host_env_var", "MY_CUSTOM_HOST_VAR"
            )
            is None
        )

    def test_lowercase_rejected(self) -> None:
        result = validate_analytics_env_var_reference(
            "posthog_api_key_env_var", "posthog_api_key"
        )
        assert result is not None
        assert "modules.analytics.posthog_api_key_env_var" in result
        assert "^[A-Z][A-Z0-9_]*$" in result

    def test_hyphen_rejected(self) -> None:
        result = validate_analytics_env_var_reference(
            "posthog_api_key_env_var", "ops-posthog-api-key"
        )
        assert result is not None
        assert "modules.analytics.posthog_api_key_env_var" in result

    def test_leading_digit_rejected(self) -> None:
        result = validate_analytics_env_var_reference(
            "posthog_api_key_env_var", "1INVALID"
        )
        assert result is not None

    def test_empty_string_returns_none(self) -> None:
        """Empty env-var references are treated as absent (no error)."""
        assert (
            validate_analytics_env_var_reference("posthog_api_key_env_var", "") is None
        )

    def test_whitespace_only_returns_none(self) -> None:
        assert (
            validate_analytics_env_var_reference("posthog_api_key_env_var", "   ")
            is None
        )


# ===========================================================================
# 7. Full validation parity
# ===========================================================================


class TestFullValidationParity:
    """validate_analytics_module_options must produce legacy-compatible issues."""

    def test_defaults_pass_validation(self) -> None:
        issues = validate_analytics_module_options(None)
        assert issues == []

    def test_invalid_provider(self) -> None:
        issues = validate_analytics_module_options({"provider": "segment"})
        assert "modules.analytics.provider must be one of: posthog" in issues

    def test_invalid_env_var_name(self) -> None:
        issues = validate_analytics_module_options(
            {"posthog_api_key_env_var": "ops-posthog-api-key"}
        )
        expected = (
            "modules.analytics.posthog_api_key_env_var must be an environment "
            "variable name matching ^[A-Z][A-Z0-9_]*$"
        )
        assert expected in issues

    def test_invalid_host_url(self) -> None:
        """A host that fails URL validation even after canonicalization."""
        # After canonicalization "not-a-url" becomes "https://not-a-url" which
        # has scheme+netloc and passes validation.  Use a value that the
        # canonicalizer produces but that urlsplit rejects as non-absolute.
        issues = validate_analytics_module_options(
            {"posthog_host": "https:///missing-host"}
        )
        assert (
            "modules.analytics.posthog_host must be an absolute http(s) URL" in issues
        )

    def test_non_boolean_enabled(self) -> None:
        issues = validate_analytics_module_options({"enabled": "yes"})
        assert "modules.analytics.enabled must be a boolean" in issues

    def test_non_boolean_exclude_debug(self) -> None:
        issues = validate_analytics_module_options({"exclude_debug": 1})
        assert "modules.analytics.exclude_debug must be a boolean" in issues

    def test_non_boolean_exclude_staff(self) -> None:
        issues = validate_analytics_module_options({"exclude_staff": "true"})
        assert "modules.analytics.exclude_staff must be a boolean" in issues

    def test_non_boolean_anonymous_by_default(self) -> None:
        issues = validate_analytics_module_options({"anonymous_by_default": 0})
        assert "modules.analytics.anonymous_by_default must be a boolean" in issues

    def test_multiple_issues_collected(self) -> None:
        """Multiple invalid options should produce multiple issues."""
        issues = validate_analytics_module_options(
            {
                "provider": "segment",
                "enabled": "yes",
                "posthog_api_key_env_var": "bad-name",
            }
        )
        assert len(issues) >= 3

    def test_valid_overrides_pass_validation(self) -> None:
        issues = validate_analytics_module_options(
            {
                "provider": "posthog",
                "posthog_host": "eu.i.posthog.com",
                "exclude_staff": True,
                "anonymous_by_default": False,
            }
        )
        assert issues == []


# ===========================================================================
# 8. Production-targeting parity
# ===========================================================================


class TestProductionTargetedParity:
    """analytics_production_targeted must match legacy predicate behaviour."""

    def test_defaults_are_production_targeted(self) -> None:
        """Default config has enabled=True and a valid env-var reference."""
        assert analytics_production_targeted(None) is True

    def test_disabled_is_not_production_targeted(self) -> None:
        assert analytics_production_targeted({"enabled": False}) is False

    def test_invalid_env_var_is_not_production_targeted(self) -> None:
        assert (
            analytics_production_targeted(
                {"posthog_api_key_env_var": "ops-posthog-api-key"}
            )
            is False
        )

    def test_valid_custom_env_var_is_production_targeted(self) -> None:
        assert (
            analytics_production_targeted(
                {"posthog_api_key_env_var": "OPS_POSTHOG_API_KEY"}
            )
            is True
        )

    def test_empty_env_var_is_production_targeted(self) -> None:
        """Empty env-var reference is treated as absent (not an error) by legacy.

        The legacy contract treated empty env-var references as non-errors in
        ``validate_analytics_env_var_reference`` (returns None), so
        ``analytics_production_targeted`` considers the config valid.
        This parity test preserves that behaviour.
        """
        assert analytics_production_targeted({"posthog_api_key_env_var": ""}) is True


# ===========================================================================
# 9. Wiring-relevant derived settings parity
# ===========================================================================


class TestWiringDerivedSettingsParity:
    """The resolved options must project to the correct Django settings.

    These tests verify that the resolved option dict contains all the fields
    that the analytics manifest adapter reads, and that
    the values are in the correct shape for direct projection to Django
    settings.
    """

    def test_resolved_options_contain_all_wiring_fields(self) -> None:
        """The resolved dict must have every key the wiring function reads."""
        resolved = resolve_analytics_module_options(None)
        wiring_keys = {
            "enabled",
            "provider",
            "posthog_api_key_env_var",
            "posthog_host_env_var",
            "posthog_host",
            "exclude_debug",
            "exclude_staff",
            "anonymous_by_default",
        }
        assert wiring_keys.issubset(set(resolved.keys()))

    def test_default_wiring_settings_projection(self) -> None:
        """Default resolved options should project to the expected Django settings."""
        resolved = resolve_analytics_module_options(None)
        expected_settings = {
            "QUICKSCALE_ANALYTICS_ENABLED": True,
            "QUICKSCALE_ANALYTICS_PROVIDER": "posthog",
            "QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR": "POSTHOG_API_KEY",
            "QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR": "POSTHOG_HOST",
            "QUICKSCALE_ANALYTICS_POSTHOG_HOST": "https://us.i.posthog.com",
            "QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG": True,
            "QUICKSCALE_ANALYTICS_EXCLUDE_STAFF": False,
            "QUICKSCALE_ANALYTICS_ANONYMOUS_BY_DEFAULT": True,
        }
        # Verify each setting can be derived from the resolved options
        assert (
            bool(resolved["enabled"])
            is expected_settings["QUICKSCALE_ANALYTICS_ENABLED"]
        )
        assert (
            str(resolved["provider"]).strip()
            == expected_settings["QUICKSCALE_ANALYTICS_PROVIDER"]
        )
        assert (
            str(resolved["posthog_api_key_env_var"]).strip()
            == expected_settings["QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR"]
        )
        assert (
            str(resolved["posthog_host_env_var"]).strip()
            == expected_settings["QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR"]
        )
        assert (
            str(resolved["posthog_host"]).strip()
            == expected_settings["QUICKSCALE_ANALYTICS_POSTHOG_HOST"]
        )
        assert (
            bool(resolved["exclude_debug"])
            is expected_settings["QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG"]
        )
        assert (
            bool(resolved["exclude_staff"])
            is expected_settings["QUICKSCALE_ANALYTICS_EXCLUDE_STAFF"]
        )
        assert (
            bool(resolved["anonymous_by_default"])
            is expected_settings["QUICKSCALE_ANALYTICS_ANONYMOUS_BY_DEFAULT"]
        )

    def test_eu_host_wiring_projection(self) -> None:
        """EU host override should project correctly through to wiring."""
        resolved = resolve_analytics_module_options(
            {"posthog_host": "eu.i.posthog.com"}
        )
        assert str(resolved["posthog_host"]).strip() == "https://eu.i.posthog.com"

    def test_disabled_wiring_projection(self) -> None:
        """When disabled, the enabled flag should project as False."""
        resolved = resolve_analytics_module_options({"enabled": False})
        assert bool(resolved["enabled"]) is False

    def test_custom_env_vars_wiring_projection(self) -> None:
        """Custom env-var names should project through to wiring unchanged."""
        resolved = resolve_analytics_module_options(
            {
                "posthog_api_key_env_var": "CUSTOM_PH_KEY",
                "posthog_host_env_var": "CUSTOM_PH_HOST",
            }
        )
        assert str(resolved["posthog_api_key_env_var"]).strip() == "CUSTOM_PH_KEY"
        assert str(resolved["posthog_host_env_var"]).strip() == "CUSTOM_PH_HOST"
