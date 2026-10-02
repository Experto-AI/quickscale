"""Focused tests for the billing manifest adapter.

Covers the post-resolution coercion hook and the sentinel contract.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from quickscale_core.module_wiring import ModuleWiringSpec

from quickscale_modules_billing.adapter import (
    _billing_manifest_adapter,
    _billing_post_hook,
    get_manifest_adapter,
)


class TestGetManifestAdapter:
    """get_manifest_adapter sentinel contract."""

    def test_returns_callable(self) -> None:
        """get_manifest_adapter must return a callable."""
        adapter = get_manifest_adapter()
        assert callable(adapter)


class TestBillingPostHook:
    """_billing_post_hook — bool/string coercions."""

    def test_coerces_bool_enabled(self) -> None:
        """QUICKSCALE_BILLING_ENABLED must be coerced to bool."""
        spec = ModuleWiringSpec(
            settings={
                "QUICKSCALE_BILLING_ENABLED": 1,
                "QUICKSCALE_BILLING_API_RATE_LIMIT": "30/hour",
            },
        )
        result = _billing_post_hook(spec, {})
        assert result.settings["QUICKSCALE_BILLING_ENABLED"] is True

    def test_coerces_bool_enabled_from_falsy_int(self) -> None:
        """Falsy int values produce False."""
        spec = ModuleWiringSpec(
            settings={
                "QUICKSCALE_BILLING_ENABLED": 0,
                "QUICKSCALE_BILLING_API_RATE_LIMIT": "30/hour",
            },
        )
        result = _billing_post_hook(spec, {})
        assert result.settings["QUICKSCALE_BILLING_ENABLED"] is False

    def test_coerces_str_keys(self) -> None:
        """String env-var name settings must be coerced to str."""
        spec = ModuleWiringSpec(
            settings={
                "QUICKSCALE_BILLING_ENABLED": True,
                "QUICKSCALE_BILLING_PUBLISHABLE_KEY_ENV_VAR": 123,
                "QUICKSCALE_BILLING_SECRET_KEY_ENV_VAR": 456,
                "QUICKSCALE_BILLING_WEBHOOK_SECRET_ENV_VAR": 789,
                "QUICKSCALE_BILLING_CURRENCY": 999,
                "QUICKSCALE_BILLING_API_RATE_LIMIT": 3030,
            },
        )
        result = _billing_post_hook(spec, {})
        assert result.settings["QUICKSCALE_BILLING_PUBLISHABLE_KEY_ENV_VAR"] == "123"
        assert result.settings["QUICKSCALE_BILLING_SECRET_KEY_ENV_VAR"] == "456"
        assert result.settings["QUICKSCALE_BILLING_WEBHOOK_SECRET_ENV_VAR"] == "789"
        assert result.settings["QUICKSCALE_BILLING_CURRENCY"] == "999"
        assert result.settings["QUICKSCALE_BILLING_API_RATE_LIMIT"] == "3030"

    def test_preserves_non_setting_fields(self) -> None:
        """Fields other than settings must pass through unchanged."""
        spec = ModuleWiringSpec(
            apps=("quickscale_modules_billing",),
            middleware=("some.middleware",),
            settings={
                "QUICKSCALE_BILLING_ENABLED": 0,
                "QUICKSCALE_BILLING_API_RATE_LIMIT": "30/hour",
            },
        )
        result = _billing_post_hook(spec, {})
        assert result.apps == ("quickscale_modules_billing",)
        assert result.middleware == ("some.middleware",)

    def test_missing_optional_str_key_does_not_raise(self) -> None:
        """Optional string keys that are absent are silently skipped."""
        spec = ModuleWiringSpec(
            settings={
                "QUICKSCALE_BILLING_ENABLED": True,
                "QUICKSCALE_BILLING_API_RATE_LIMIT": "30/hour",
            },
        )
        result = _billing_post_hook(spec, {})
        assert result.settings["QUICKSCALE_BILLING_ENABLED"] is True


class TestBillingSecretProjection:
    """Rule 35: the adapter projects each Stripe secret through `__QS_ENV__`."""

    def test_projects_default_env_var_names(self) -> None:
        """Manifest defaults project the three Stripe secrets."""
        spec = _billing_manifest_adapter({})

        assert spec.settings["QUICKSCALE_BILLING_PUBLISHABLE_KEY"] == (
            "__QS_ENV__:STRIPE_PUBLISHABLE_KEY"
        )
        assert spec.settings["QUICKSCALE_BILLING_SECRET_KEY"] == (
            "__QS_ENV__:STRIPE_SECRET_KEY"
        )
        assert spec.settings["QUICKSCALE_BILLING_WEBHOOK_SECRET"] == (
            "__QS_ENV__:QUICKSCALE_BILLING_WEBHOOK_SECRET"
        )

    def test_projects_configured_env_var_names(self) -> None:
        """A configured `_ENV_VAR` option name is the projected reference."""
        spec = _billing_manifest_adapter(
            {
                "publishable_key_env_var": "OPS_PUBLISHABLE_KEY",
                "secret_key_env_var": "OPS_SECRET_KEY",
                "webhook_secret_env_var": "OPS_WEBHOOK_SECRET",
            }
        )

        assert spec.settings["QUICKSCALE_BILLING_PUBLISHABLE_KEY"] == (
            "__QS_ENV__:OPS_PUBLISHABLE_KEY"
        )
        assert spec.settings["QUICKSCALE_BILLING_SECRET_KEY"] == (
            "__QS_ENV__:OPS_SECRET_KEY"
        )
        assert spec.settings["QUICKSCALE_BILLING_WEBHOOK_SECRET"] == (
            "__QS_ENV__:OPS_WEBHOOK_SECRET"
        )

    def test_blank_env_var_name_projects_empty_value(self) -> None:
        """A blank option name projects an empty value, never a dangling reference."""
        spec = _billing_post_hook(
            ModuleWiringSpec(
                settings={
                    "QUICKSCALE_BILLING_ENABLED": True,
                    "QUICKSCALE_BILLING_PUBLISHABLE_KEY_ENV_VAR": "   ",
                    "QUICKSCALE_BILLING_SECRET_KEY_ENV_VAR": "",
                    "QUICKSCALE_BILLING_WEBHOOK_SECRET_ENV_VAR": "OPS_WEBHOOK_SECRET",
                    "QUICKSCALE_BILLING_CURRENCY": "usd",
                    "QUICKSCALE_BILLING_API_RATE_LIMIT": "30/hour",
                },
            ),
            {},
        )

        assert spec.settings["QUICKSCALE_BILLING_PUBLISHABLE_KEY"] == ""
        assert spec.settings["QUICKSCALE_BILLING_SECRET_KEY"] == ""
        assert spec.settings["QUICKSCALE_BILLING_WEBHOOK_SECRET"] == (
            "__QS_ENV__:OPS_WEBHOOK_SECRET"
        )


class TestBillingManifestAdapter:
    """_billing_manifest_adapter delegation."""

    @patch("quickscale_modules_billing.adapter.build_generic_manifest_spec")
    def test_delegates_to_build_generic_manifest_spec(
        self,
        mock_build: MagicMock,
    ) -> None:
        """The adapter must call build_generic_manifest_spec with billing module name."""
        mock_build.return_value = ModuleWiringSpec()

        result = _billing_manifest_adapter({"enabled": True})

        mock_build.assert_called_once_with(
            "billing",
            {"enabled": True},
            post_hook=_billing_post_hook,
        )
        assert isinstance(result, ModuleWiringSpec)

    @patch("quickscale_modules_billing.adapter.build_generic_manifest_spec")
    def test_passes_options_unchanged(self, mock_build: MagicMock) -> None:
        """Adapter must forward the options dict literally."""
        mock_build.return_value = ModuleWiringSpec()

        _billing_manifest_adapter({"enabled": False, "currency": "eur"})

        mock_build.assert_called_once_with(
            "billing",
            {"enabled": False, "currency": "eur"},
            post_hook=_billing_post_hook,
        )
