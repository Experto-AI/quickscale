"""Focused tests for the billing manifest adapter.

Covers the declared throttle scopes, the off-switch transformation, the
manifest-owned secret references, and the sentinel contract.  The generic
manifest boundary owns every option default, normalization rule, check,
projection, and declared throttle scope; the adapter contributes no rate map.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from quickscale_core.manifest import ManifestError, ResolvedOptions
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


class TestBillingManifestAdapterSettings:
    """The manifest owns every canonical billing setting."""

    def test_defaults_include_declared_throttle_scopes(self) -> None:
        spec = _billing_manifest_adapter({})

        assert spec.settings["QUICKSCALE_BILLING_ENABLED"] is True
        assert spec.settings["QUICKSCALE_BILLING_TRANSACTIONS_PER_PAGE"] == 25
        assert spec.settings["QUICKSCALE_BILLING_PLANS_PER_PAGE"] == 25
        assert "REST_FRAMEWORK" not in spec.settings
        assert dict(spec.throttle_scopes) == {
            "quickscale_billing_checkout": "30/hour",
            "quickscale_billing_portal": "30/hour",
        }

    @pytest.mark.parametrize(
        ("option_name", "value"),
        [
            ("transactions_per_page", "10"),
            ("plans_per_page", 0),
            ("enabled", 1),
            ("currency", 999),
            ("api_rate_limit", "no-rate"),
        ],
    )
    def test_wrong_shaped_values_are_refused(
        self, option_name: str, value: object
    ) -> None:
        """A raw value of the wrong shape is refused, never coerced."""
        with pytest.raises(ManifestError, match="modules.billing."):
            _billing_manifest_adapter({option_name: value})

    def test_canonical_rate_reaches_both_scopes(self) -> None:
        spec = _billing_manifest_adapter({"api_rate_limit": " 10/minute "})

        assert spec.settings["QUICKSCALE_BILLING_API_RATE_LIMIT"] == "10/minute"
        assert dict(spec.throttle_scopes) == {
            "quickscale_billing_checkout": "10/minute",
            "quickscale_billing_portal": "10/minute",
        }


class TestBillingPostHook:
    """_billing_post_hook — off-switch behaviour and declared scope preservation."""

    def test_enabled_returns_the_assembled_spec_with_scopes(self) -> None:
        spec = ModuleWiringSpec(
            apps=("quickscale_modules_billing",),
            middleware=("some.middleware",),
            settings={"QUICKSCALE_BILLING_API_RATE_LIMIT": "30/hour"},
            throttle_scopes={
                "quickscale_billing_checkout": "30/hour",
                "quickscale_billing_portal": "30/hour",
            },
        )
        result = _billing_post_hook(spec, ResolvedOptions({"enabled": True}))

        assert result is spec
        assert result.apps == ("quickscale_modules_billing",)
        assert result.middleware == ("some.middleware",)
        assert dict(result.throttle_scopes) == {
            "quickscale_billing_checkout": "30/hour",
            "quickscale_billing_portal": "30/hour",
        }

    def test_disabled_module_keeps_only_the_webhook_mount(self) -> None:
        """Rule 1 (D3)/rule 26: off unmounts pages and APIs but keeps webhooks."""
        scopes = {
            "quickscale_billing_checkout": "30/hour",
            "quickscale_billing_portal": "30/hour",
        }
        spec = ModuleWiringSpec(
            apps=("rest_framework", "quickscale_modules_billing"),
            settings={"QUICKSCALE_BILLING_API_RATE_LIMIT": "30/hour"},
            pre_home_url_includes=(),
            url_includes=(("billing/", "quickscale_modules_billing.urls"),),
            throttle_scopes=scopes,
        )
        result = _billing_post_hook(spec, ResolvedOptions({"enabled": False}))

        assert result.url_includes == (
            ("billing/", "quickscale_modules_billing.webhook_urls"),
        )
        assert result.pre_home_url_includes == ()
        assert dict(result.throttle_scopes) == scopes


class TestBillingSecretProjection:
    """Rule 35: the generic boundary projects each Stripe secret reference."""

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
        spec = _billing_manifest_adapter(
            {
                "publishable_key_env_var": "   ",
                "secret_key_env_var": "",
                "webhook_secret_env_var": "OPS_WEBHOOK_SECRET",
            }
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
