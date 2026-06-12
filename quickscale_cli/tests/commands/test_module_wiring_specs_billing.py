"""Focused billing wiring regression tests."""

from quickscale_cli.billing_manifest import (
    DEFAULT_BILLING_CURRENCY,
    DEFAULT_BILLING_PUBLISHABLE_KEY_ENV_VAR,
    DEFAULT_BILLING_SECRET_KEY_ENV_VAR,
    DEFAULT_BILLING_WEBHOOK_SECRET_ENV_VAR,
)
from quickscale_cli.commands.module_wiring_specs import _billing_wiring


class TestBillingWiring:
    """Focused regression coverage for the billing wiring builder."""

    def test_billing_wiring_uses_default_settings_apps_and_urls(self):
        """Billing wiring should emit the default app, settings, and URL include."""
        spec = _billing_wiring({})

        assert spec.apps == ("rest_framework", "quickscale_modules_billing")
        assert spec.settings == {
            "QUICKSCALE_BILLING_ENABLED": True,
            "QUICKSCALE_BILLING_PUBLISHABLE_KEY_ENV_VAR": (
                DEFAULT_BILLING_PUBLISHABLE_KEY_ENV_VAR
            ),
            "QUICKSCALE_BILLING_SECRET_KEY_ENV_VAR": (
                DEFAULT_BILLING_SECRET_KEY_ENV_VAR
            ),
            "QUICKSCALE_BILLING_WEBHOOK_SECRET_ENV_VAR": (
                DEFAULT_BILLING_WEBHOOK_SECRET_ENV_VAR
            ),
            "QUICKSCALE_BILLING_CURRENCY": DEFAULT_BILLING_CURRENCY,
        }
        assert spec.url_includes == (("", "quickscale_modules_billing.urls"),)

    def test_billing_wiring_normalizes_custom_env_vars_and_currency(self):
        """Billing wiring should trim env vars and lowercase the configured currency."""
        spec = _billing_wiring(
            {
                "enabled": False,
                "publishable_key_env_var": " OPS_STRIPE_PUBLISHABLE_KEY ",
                "secret_key_env_var": " OPS_STRIPE_SECRET_KEY ",
                "webhook_secret_env_var": " OPS_BILLING_WEBHOOK_SECRET ",
                "billing_currency": " EUR ",
            }
        )

        assert spec.apps == ("rest_framework", "quickscale_modules_billing")
        assert spec.settings["QUICKSCALE_BILLING_ENABLED"] is False
        assert (
            spec.settings["QUICKSCALE_BILLING_PUBLISHABLE_KEY_ENV_VAR"]
            == "OPS_STRIPE_PUBLISHABLE_KEY"
        )
        assert (
            spec.settings["QUICKSCALE_BILLING_SECRET_KEY_ENV_VAR"]
            == "OPS_STRIPE_SECRET_KEY"
        )
        assert (
            spec.settings["QUICKSCALE_BILLING_WEBHOOK_SECRET_ENV_VAR"]
            == "OPS_BILLING_WEBHOOK_SECRET"
        )
        assert spec.settings["QUICKSCALE_BILLING_CURRENCY"] == "eur"
        assert spec.url_includes == (("", "quickscale_modules_billing.urls"),)
