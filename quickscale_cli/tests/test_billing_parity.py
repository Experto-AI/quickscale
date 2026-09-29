"""Contract tests for the billing module's manifest-owned configuration.

The billing option defaults, normalization, and validation are declared in
``quickscale_modules/billing/module.yml`` and enforced through the shared
manifest engine; its CLI configurator is the one generic manifest-driven
configurator.  These tests pin that contract and the operator-facing
behaviour it produces.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from quickscale_cli.commands.module_config import MODULE_CONFIGURATOR_REGISTRY
from quickscale_core.contracts.module_options import BILLING_ENV_VAR_OPTION_NAMES
from quickscale_core.contracts.resolvers import (
    load_module_manifest_with_fallback,
    resolve_manifest_module_options,
)
from quickscale_core.manifest.option_validation import (
    collect_option_validation_issues,
    validate_module_options,
)

_EXPECTED_DEFAULTS: dict[str, object] = {
    "enabled": True,
    "publishable_key_env_var": "STRIPE_PUBLISHABLE_KEY",
    "secret_key_env_var": "STRIPE_SECRET_KEY",
    "webhook_secret_env_var": "QUICKSCALE_BILLING_WEBHOOK_SECRET",
    "billing_currency": "usd",
}

_SUPPORTED_CURRENCIES = (
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


def _manifest():
    return load_module_manifest_with_fallback("billing")


# ===========================================================================
# 1. Supported currencies live in the manifest
# ===========================================================================


class TestSupportedCurrenciesDeclaration:
    """The manifest's currency choices are the module's supported set."""

    def test_manifest_choices_match_the_supported_set(self) -> None:
        option = _manifest().get_option("billing_currency")
        assert option is not None
        assert option.validation.get("choices") == list(_SUPPORTED_CURRENCIES)

    def test_supported_set_has_25_lowercase_codes(self) -> None:
        option = _manifest().get_option("billing_currency")
        assert option is not None
        choices = option.validation.get("choices") or []
        assert len(choices) == 25
        for code in choices:
            assert code == code.lower(), f"Expected lowercase: {code!r}"
        assert "usd" in choices
        assert "eur" in choices
        assert "gbp" in choices


# ===========================================================================
# 2. Validation engine behaviour
# ===========================================================================


class TestBillingValidation:
    """The shared engine enforces the manifest's declared constraints."""

    def test_defaults_pass_validation(self) -> None:
        assert validate_module_options(_manifest(), None) == []

    def test_valid_overrides_pass_validation(self) -> None:
        assert (
            validate_module_options(
                _manifest(),
                {
                    "enabled": True,
                    "publishable_key_env_var": "OPS_STRIPE_PUBLISHABLE_KEY",
                    "secret_key_env_var": "OPS_STRIPE_SECRET_KEY",
                    "webhook_secret_env_var": "OPS_BILLING_WEBHOOK_SECRET",
                    "billing_currency": "eur",
                },
            )
            == []
        )

    @pytest.mark.parametrize("bad_value", ["stripe-publishable-key", "1INVALID"])
    def test_invalid_env_var_names_are_refused(self, bad_value: str) -> None:
        for option_name in BILLING_ENV_VAR_OPTION_NAMES:
            issues = collect_option_validation_issues(
                _manifest(), {option_name: bad_value}
            )
            assert any(
                issue.option_name == option_name
                and "must match pattern" in issue.message
                for issue in issues
            )

    def test_blank_env_var_names_are_accepted(self) -> None:
        for option_name in BILLING_ENV_VAR_OPTION_NAMES:
            assert validate_module_options(_manifest(), {option_name: ""}) == []

    def test_uppercase_currency_is_canonicalized_before_the_check(self) -> None:
        assert validate_module_options(_manifest(), {"billing_currency": "USD"}) == []

    @pytest.mark.parametrize("bad_value", ["credits", "", "   "])
    def test_unsupported_or_blank_currency_is_refused(self, bad_value: str) -> None:
        issues = collect_option_validation_issues(
            _manifest(), {"billing_currency": bad_value}
        )
        assert any(
            issue.option_name == "billing_currency"
            and "must be one of" in issue.message
            for issue in issues
        )

    def test_non_boolean_enabled_is_refused(self) -> None:
        issues = collect_option_validation_issues(
            _manifest(), {"enabled": "yes"}, supplied={"enabled": "yes"}
        )
        assert any(
            issue.option_name == "enabled" and "boolean" in issue.message
            for issue in issues
        )

    def test_multiple_issues_are_collected(self) -> None:
        issues = collect_option_validation_issues(
            _manifest(),
            {
                "publishable_key_env_var": "stripe-publishable-key",
                "billing_currency": "credits",
            },
        )
        assert len(issues) >= 2


# ===========================================================================
# 3. Generic resolver behaviour
# ===========================================================================


class TestBillingResolution:
    """The generic manifest resolver returns the manifest's canonical values."""

    def test_defaults_match_the_manifest(self) -> None:
        assert resolve_manifest_module_options("billing") == _EXPECTED_DEFAULTS

    def test_partial_override_preserves_other_defaults(self) -> None:
        resolved = resolve_manifest_module_options("billing", {"enabled": False})
        expected = dict(_EXPECTED_DEFAULTS)
        expected["enabled"] = False
        assert resolved == expected

    def test_env_var_overrides_are_stripped_and_currency_lowercased(self) -> None:
        resolved = resolve_manifest_module_options(
            "billing",
            {
                "publishable_key_env_var": "  OPS_STRIPE_PUBLISHABLE_KEY  ",
                "secret_key_env_var": " OPS_STRIPE_SECRET_KEY ",
                "webhook_secret_env_var": "  OPS_BILLING_WEBHOOK_SECRET ",
                "billing_currency": " EUR ",
            },
        )
        assert resolved == {
            "enabled": True,
            "publishable_key_env_var": "OPS_STRIPE_PUBLISHABLE_KEY",
            "secret_key_env_var": "OPS_STRIPE_SECRET_KEY",
            "webhook_secret_env_var": "OPS_BILLING_WEBHOOK_SECRET",
            "billing_currency": "eur",
        }

    def test_resolution_is_idempotent(self) -> None:
        resolved = resolve_manifest_module_options(
            "billing",
            {
                "publishable_key_env_var": "  OPS_STRIPE_PUBLISHABLE_KEY  ",
                "billing_currency": " EUR ",
            },
        )
        assert resolve_manifest_module_options("billing", resolved) == resolved


# ===========================================================================
# 4. CLI configurator behaviour
# ===========================================================================


class TestBillingConfigurator:
    """The CLI configurator's prompts and defaults come from the manifest."""

    def test_defaults_factory_reads_the_manifest(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["billing"]
        assert entry.get_defaults() == _EXPECTED_DEFAULTS

    def test_non_interactive_configuration_uses_manifest_defaults(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["billing"]
        assert entry.configure(non_interactive=True) == _EXPECTED_DEFAULTS

    def test_existing_declared_values_are_kept(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["billing"]
        config = entry.configure(
            non_interactive=True,
            existing_config={"enabled": False, "billing_currency": "eur"},
        )
        assert config["enabled"] is False
        assert config["billing_currency"] == "eur"
        assert config["secret_key_env_var"] == "STRIPE_SECRET_KEY"

    def test_undeclared_existing_keys_are_dropped(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["billing"]
        config = entry.configure(
            non_interactive=True,
            existing_config={"stripe_secret_key": "sk_live_value"},
        )
        assert "stripe_secret_key" not in config
        assert config == _EXPECTED_DEFAULTS

    def test_existing_values_are_returned_in_canonical_form(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["billing"]
        config = entry.configure(
            non_interactive=True,
            existing_config={
                "publishable_key_env_var": "  OPS_STRIPE_PUBLISHABLE_KEY  ",
                "billing_currency": " GBP ",
            },
        )
        assert config["publishable_key_env_var"] == "OPS_STRIPE_PUBLISHABLE_KEY"
        assert config["billing_currency"] == "gbp"

    @patch("quickscale_cli.commands.module_config.click.prompt")
    @patch("quickscale_cli.commands.module_config.click.confirm")
    def test_interactive_values_are_returned_in_canonical_form(
        self, mock_confirm, mock_prompt
    ) -> None:
        """Padded interactive answers are stored in their canonical forms."""
        mock_confirm.side_effect = [True]
        mock_prompt.side_effect = ["  OPS_KEY  ", "OPS_SECRET", "OPS_HOOK", " EUR "]

        entry = MODULE_CONFIGURATOR_REGISTRY["billing"]
        config = entry.configure(non_interactive=False)

        assert config["publishable_key_env_var"] == "OPS_KEY"
        assert config["secret_key_env_var"] == "OPS_SECRET"
        assert config["webhook_secret_env_var"] == "OPS_HOOK"
        assert config["billing_currency"] == "eur"
