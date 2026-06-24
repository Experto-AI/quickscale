"""Parity/regression tests for the manifest-driven billing path.

These tests encode the *legacy* ``billing_contract.py`` behaviour as gold
expectations and verify that the manifest-driven replacement
(``billing_manifest.py``) produces identical results for every public
entry point.

The legacy contract file was deleted when the billing module was migrated
to the manifest-driven path (Phase 4, billing migration).  The gold values
below were recovered from the last committed version of ``billing_contract.py``
and from the billing ``module.yml`` manifest that now owns the defaults.

Scope
-----
* Default option values
* Env-var reference normalisation (strip)
* Currency normalisation (strip + lowercase)
* Resolution (defaults + normalised overrides, idempotency)
* Env-var validation messages (pattern check)
* Currency validation messages (unsupported code, blank)
* Full module options validation
* Production-targeting predicate truth table
* BILLING_SUPPORTED_CURRENCIES set completeness
"""

from __future__ import annotations

from typing import Any

import pytest

from quickscale_core.contracts.module_options import (
    BILLING_ENV_VAR_OPTION_NAMES,
    BILLING_MODULE_OPTION_KEYS,
    BILLING_SUPPORTED_CURRENCIES,
    DEFAULT_BILLING_CURRENCY,
    DEFAULT_BILLING_PUBLISHABLE_KEY_ENV_VAR,
    DEFAULT_BILLING_SECRET_KEY_ENV_VAR,
    DEFAULT_BILLING_WEBHOOK_SECRET_ENV_VAR,
    normalize_billing_module_options,
    validate_billing_currency,
    validate_billing_env_var_reference,
)
from quickscale_core.contracts.resolvers import (
    billing_production_targeted,
    default_billing_module_options,
    resolve_billing_module_options,
    validate_billing_module_options,
)

# ---------------------------------------------------------------------------
# Gold expectations recovered from the legacy billing_contract.py
# billing has NO immutable options, so default_billing_module_options()
# == get_defaults() == {k: opt.default for all mutable options}.
# ---------------------------------------------------------------------------

_LEGACY_DEFAULTS: dict[str, Any] = {
    "enabled": True,
    "publishable_key_env_var": "STRIPE_PUBLISHABLE_KEY",
    "secret_key_env_var": "STRIPE_SECRET_KEY",
    "webhook_secret_env_var": "QUICKSCALE_BILLING_WEBHOOK_SECRET",
    "billing_currency": "usd",
}

_LEGACY_SUPPORTED_CURRENCIES = (
    "aud",
    "brl",
    "cad",
    "chf",
    "czk",
    "dkk",
    "eur",
    "gbp",
    "hkd",
    "huf",
    "inr",
    "jpy",
    "mxn",
    "myr",
    "nok",
    "nzd",
    "php",
    "pln",
    "ron",
    "sek",
    "sgd",
    "thb",
    "try",
    "usd",
    "zar",
)


# ===========================================================================
# 1. Default values parity
# ===========================================================================


class TestDefaultsParity:
    """The manifest-driven defaults must match the legacy hardcoded dict."""

    def test_default_options_match_legacy_contract(self) -> None:
        """Every default must equal the value the old contract file returned."""
        defaults = default_billing_module_options()
        assert defaults == _LEGACY_DEFAULTS

    def test_default_options_keys_are_stable(self) -> None:
        """The key set must not drift from the legacy contract."""
        defaults = default_billing_module_options()
        assert set(defaults.keys()) == set(_LEGACY_DEFAULTS.keys())

    def test_default_enabled_is_true(self) -> None:
        defaults = default_billing_module_options()
        assert defaults["enabled"] is True

    def test_default_currency_is_usd(self) -> None:
        defaults = default_billing_module_options()
        assert defaults["billing_currency"] == DEFAULT_BILLING_CURRENCY
        assert defaults["billing_currency"] == "usd"

    def test_default_publishable_key_env_var(self) -> None:
        defaults = default_billing_module_options()
        assert (
            defaults["publishable_key_env_var"]
            == DEFAULT_BILLING_PUBLISHABLE_KEY_ENV_VAR
        )
        assert defaults["publishable_key_env_var"] == "STRIPE_PUBLISHABLE_KEY"

    def test_default_secret_key_env_var(self) -> None:
        defaults = default_billing_module_options()
        assert defaults["secret_key_env_var"] == DEFAULT_BILLING_SECRET_KEY_ENV_VAR
        assert defaults["secret_key_env_var"] == "STRIPE_SECRET_KEY"

    def test_default_webhook_secret_env_var(self) -> None:
        defaults = default_billing_module_options()
        assert (
            defaults["webhook_secret_env_var"] == DEFAULT_BILLING_WEBHOOK_SECRET_ENV_VAR
        )
        assert defaults["webhook_secret_env_var"] == "QUICKSCALE_BILLING_WEBHOOK_SECRET"


# ===========================================================================
# 2. Constants parity
# ===========================================================================


class TestConstantsParity:
    """Public constants must remain identical to the legacy contract values."""

    def test_default_publishable_key_constant(self) -> None:
        assert DEFAULT_BILLING_PUBLISHABLE_KEY_ENV_VAR == "STRIPE_PUBLISHABLE_KEY"

    def test_default_secret_key_constant(self) -> None:
        assert DEFAULT_BILLING_SECRET_KEY_ENV_VAR == "STRIPE_SECRET_KEY"

    def test_default_webhook_secret_constant(self) -> None:
        assert (
            DEFAULT_BILLING_WEBHOOK_SECRET_ENV_VAR
            == "QUICKSCALE_BILLING_WEBHOOK_SECRET"
        )

    def test_default_currency_constant(self) -> None:
        assert DEFAULT_BILLING_CURRENCY == "usd"

    def test_env_var_option_names_tuple(self) -> None:
        assert BILLING_ENV_VAR_OPTION_NAMES == (
            "publishable_key_env_var",
            "secret_key_env_var",
            "webhook_secret_env_var",
        )

    def test_module_option_keys_frozenset(self) -> None:
        assert BILLING_MODULE_OPTION_KEYS == frozenset(
            {
                "enabled",
                "publishable_key_env_var",
                "secret_key_env_var",
                "webhook_secret_env_var",
                "billing_currency",
            }
        )


# ===========================================================================
# 3. BILLING_SUPPORTED_CURRENCIES parity
# ===========================================================================


class TestSupportedCurrenciesParity:
    """BILLING_SUPPORTED_CURRENCIES must be byte-identical to the legacy tuple."""

    def test_supported_currencies_match_legacy(self) -> None:
        assert BILLING_SUPPORTED_CURRENCIES == _LEGACY_SUPPORTED_CURRENCIES

    def test_supported_currencies_count(self) -> None:
        assert len(BILLING_SUPPORTED_CURRENCIES) == 25

    def test_usd_in_supported_currencies(self) -> None:
        assert "usd" in BILLING_SUPPORTED_CURRENCIES

    def test_eur_in_supported_currencies(self) -> None:
        assert "eur" in BILLING_SUPPORTED_CURRENCIES

    def test_gbp_in_supported_currencies(self) -> None:
        assert "gbp" in BILLING_SUPPORTED_CURRENCIES

    def test_no_uppercase_currencies(self) -> None:
        """All currency codes should be lowercase."""
        for code in BILLING_SUPPORTED_CURRENCIES:
            assert code == code.lower(), f"Expected lowercase: {code!r}"


# ===========================================================================
# 4. Normalisation parity
# ===========================================================================


class TestNormalizationParity:
    """Normalisation must behave identically to the legacy contract."""

    def test_env_var_strip(self) -> None:
        normalized = normalize_billing_module_options(
            {
                "publishable_key_env_var": "  OPS_STRIPE_PUBLISHABLE_KEY  ",
                "secret_key_env_var": " OPS_STRIPE_SECRET_KEY ",
                "webhook_secret_env_var": "  OPS_BILLING_WEBHOOK_SECRET ",
            }
        )
        assert normalized["publishable_key_env_var"] == "OPS_STRIPE_PUBLISHABLE_KEY"
        assert normalized["secret_key_env_var"] == "OPS_STRIPE_SECRET_KEY"
        assert normalized["webhook_secret_env_var"] == "OPS_BILLING_WEBHOOK_SECRET"

    def test_currency_strip_and_lowercase(self) -> None:
        normalized = normalize_billing_module_options({"billing_currency": " EUR "})
        assert normalized["billing_currency"] == "eur"

    def test_currency_already_lower(self) -> None:
        normalized = normalize_billing_module_options({"billing_currency": "usd"})
        assert normalized["billing_currency"] == "usd"

    def test_none_options_returns_empty_dict(self) -> None:
        normalized = normalize_billing_module_options(None)
        assert normalized == {}

    def test_empty_options_returns_empty_dict(self) -> None:
        normalized = normalize_billing_module_options({})
        assert normalized == {}

    def test_untouched_keys_pass_through(self) -> None:
        normalized = normalize_billing_module_options({"enabled": False})
        assert normalized["enabled"] is False
        assert "billing_currency" not in normalized


# ===========================================================================
# 5. Resolution parity (defaults + normalised overrides)
# ===========================================================================


class TestResolutionParity:
    """resolve_billing_module_options must merge defaults + overrides."""

    def test_no_overrides_returns_defaults(self) -> None:
        resolved = resolve_billing_module_options(None)
        assert resolved == _LEGACY_DEFAULTS

    def test_empty_overrides_returns_defaults(self) -> None:
        resolved = resolve_billing_module_options({})
        assert resolved == _LEGACY_DEFAULTS

    def test_partial_override_preserves_other_defaults(self) -> None:
        resolved = resolve_billing_module_options({"enabled": False})
        expected = dict(_LEGACY_DEFAULTS)
        expected["enabled"] = False
        assert resolved == expected

    def test_env_var_overrides_are_stripped(self) -> None:
        resolved = resolve_billing_module_options(
            {
                "publishable_key_env_var": "  OPS_STRIPE_PUBLISHABLE_KEY  ",
                "secret_key_env_var": " OPS_STRIPE_SECRET_KEY ",
                "webhook_secret_env_var": "  OPS_BILLING_WEBHOOK_SECRET ",
                "billing_currency": " EUR ",
            }
        )
        assert resolved == {
            "enabled": True,
            "publishable_key_env_var": "OPS_STRIPE_PUBLISHABLE_KEY",
            "secret_key_env_var": "OPS_STRIPE_SECRET_KEY",
            "webhook_secret_env_var": "OPS_BILLING_WEBHOOK_SECRET",
            "billing_currency": "eur",
        }

    def test_resolution_is_idempotent(self) -> None:
        """Resolved options are stable when resolved again."""
        resolved = resolve_billing_module_options(
            {
                "publishable_key_env_var": "  OPS_STRIPE_PUBLISHABLE_KEY  ",
                "billing_currency": " EUR ",
            }
        )
        assert resolve_billing_module_options(resolved) == resolved

    def test_resolved_keys_match_legacy(self) -> None:
        """The resolved dict must contain exactly the same keys as legacy."""
        resolved = resolve_billing_module_options({"enabled": False})
        assert set(resolved.keys()) == set(_LEGACY_DEFAULTS.keys())


# ===========================================================================
# 6. Env-var validation parity
# ===========================================================================


class TestEnvVarValidationParity:
    """Env-var reference validation must match legacy pattern checks."""

    def test_valid_env_var_returns_none(self) -> None:
        assert (
            validate_billing_env_var_reference(
                "publishable_key_env_var", "STRIPE_PUBLISHABLE_KEY"
            )
            is None
        )

    def test_valid_env_var_with_underscores(self) -> None:
        assert (
            validate_billing_env_var_reference(
                "secret_key_env_var", "MY_CUSTOM_SECRET_KEY"
            )
            is None
        )

    def test_lowercase_rejected(self) -> None:
        result = validate_billing_env_var_reference(
            "publishable_key_env_var", "stripe_publishable_key"
        )
        assert result is not None
        assert "modules.billing.publishable_key_env_var" in result
        assert "^[A-Z][A-Z0-9_]*$" in result

    def test_hyphen_rejected(self) -> None:
        result = validate_billing_env_var_reference(
            "publishable_key_env_var", "stripe-publishable-key"
        )
        assert result is not None
        assert "modules.billing.publishable_key_env_var" in result

    def test_leading_digit_rejected(self) -> None:
        result = validate_billing_env_var_reference(
            "publishable_key_env_var", "1INVALID"
        )
        assert result is not None

    def test_empty_string_returns_none(self) -> None:
        """Empty env-var references are treated as absent (no error)."""
        assert validate_billing_env_var_reference("publishable_key_env_var", "") is None

    def test_whitespace_only_returns_none(self) -> None:
        assert (
            validate_billing_env_var_reference("publishable_key_env_var", "   ") is None
        )

    def test_error_message_contains_qualified_option_name(self) -> None:
        result = validate_billing_env_var_reference(
            "webhook_secret_env_var", "bad-name"
        )
        assert result is not None
        assert "modules.billing.webhook_secret_env_var" in result


# ===========================================================================
# 7. Currency validation parity
# ===========================================================================


class TestCurrencyValidationParity:
    """validate_billing_currency must match legacy validation exactly."""

    def test_valid_usd_returns_none(self) -> None:
        assert validate_billing_currency("usd") is None

    def test_valid_eur_returns_none(self) -> None:
        assert validate_billing_currency("eur") is None

    def test_valid_gbp_returns_none(self) -> None:
        assert validate_billing_currency("gbp") is None

    def test_uppercase_usd_returns_none(self) -> None:
        """Legacy contract strips and lowercases before checking."""
        assert validate_billing_currency("USD") is None

    def test_whitespace_usd_returns_none(self) -> None:
        assert validate_billing_currency("  usd  ") is None

    def test_unsupported_code_returns_error(self) -> None:
        result = validate_billing_currency("credits")
        assert result is not None
        assert "modules.billing.billing_currency" in result
        assert "supported QuickScale billing currency codes" in result

    def test_blank_returns_error(self) -> None:
        result = validate_billing_currency("")
        assert result is not None
        assert "modules.billing.billing_currency" in result
        assert "cannot be blank" in result

    def test_whitespace_only_returns_blank_error(self) -> None:
        result = validate_billing_currency("   ")
        assert result is not None
        assert "cannot be blank" in result

    def test_error_message_lists_currencies(self) -> None:
        result = validate_billing_currency("credits")
        assert result is not None
        assert "usd" in result
        assert "eur" in result


# ===========================================================================
# 8. Full module options validation parity
# ===========================================================================


class TestFullValidationParity:
    """validate_billing_module_options must produce legacy-compatible issues."""

    def test_defaults_pass_validation(self) -> None:
        issues = validate_billing_module_options(None)
        assert issues == []

    def test_valid_overrides_pass_validation(self) -> None:
        issues = validate_billing_module_options(
            {
                "enabled": True,
                "publishable_key_env_var": "OPS_STRIPE_PUBLISHABLE_KEY",
                "secret_key_env_var": "OPS_STRIPE_SECRET_KEY",
                "webhook_secret_env_var": "OPS_BILLING_WEBHOOK_SECRET",
                "billing_currency": "eur",
            }
        )
        assert issues == []

    def test_invalid_env_var_name(self) -> None:
        issues = validate_billing_module_options(
            {"publishable_key_env_var": "stripe-publishable-key"}
        )
        expected = (
            "modules.billing.publishable_key_env_var must be an environment variable "
            "name matching ^[A-Z][A-Z0-9_]*$"
        )
        assert expected in issues

    def test_invalid_currency(self) -> None:
        issues = validate_billing_module_options({"billing_currency": "credits"})
        assert len(issues) == 1
        assert "modules.billing.billing_currency" in issues[0]
        assert "supported QuickScale billing currency codes" in issues[0]

    def test_multiple_issues_collected(self) -> None:
        """Multiple invalid options should produce multiple issues."""
        issues = validate_billing_module_options(
            {
                "publishable_key_env_var": "stripe-publishable-key",
                "billing_currency": "credits",
            }
        )
        assert len(issues) >= 2


# ===========================================================================
# 9. Production-targeting parity (truth table)
# ===========================================================================


class TestProductionTargetedParity:
    """billing_production_targeted must match legacy predicate behaviour."""

    def test_defaults_are_production_targeted(self) -> None:
        """Default config has enabled=True and valid env-var references."""
        assert billing_production_targeted(None) is True

    def test_empty_overrides_are_production_targeted(self) -> None:
        assert billing_production_targeted({}) is True

    def test_defaults_dict_is_production_targeted(self) -> None:
        assert billing_production_targeted(default_billing_module_options()) is True

    def test_disabled_is_not_production_targeted(self) -> None:
        assert billing_production_targeted({"enabled": False}) is False

    def test_invalid_env_var_is_not_production_targeted(self) -> None:
        assert (
            billing_production_targeted(
                {"publishable_key_env_var": "stripe-publishable-key"}
            )
            is False
        )

    def test_invalid_currency_is_not_production_targeted(self) -> None:
        assert billing_production_targeted({"billing_currency": "credits"}) is False

    def test_blank_currency_is_not_production_targeted(self) -> None:
        assert billing_production_targeted({"billing_currency": ""}) is False

    def test_valid_custom_env_vars_are_production_targeted(self) -> None:
        assert (
            billing_production_targeted(
                {
                    "publishable_key_env_var": "OPS_STRIPE_PUBLISHABLE_KEY",
                    "secret_key_env_var": "OPS_STRIPE_SECRET_KEY",
                    "webhook_secret_env_var": "OPS_BILLING_WEBHOOK_SECRET",
                }
            )
            is True
        )

    def test_valid_eur_currency_is_production_targeted(self) -> None:
        assert billing_production_targeted({"billing_currency": "eur"}) is True

    @pytest.mark.parametrize("currency", list(_LEGACY_SUPPORTED_CURRENCIES))
    def test_every_supported_currency_is_production_targeted(
        self, currency: str
    ) -> None:
        """Every supported currency must allow production targeting."""
        assert billing_production_targeted({"billing_currency": currency}) is True
