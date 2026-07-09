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
    """_billing_post_hook — bool/string coercions (SA17.2)."""

    def test_coerces_bool_enabled(self) -> None:
        """QUICKSCALE_BILLING_ENABLED must be coerced to bool."""
        spec = ModuleWiringSpec(
            settings={"QUICKSCALE_BILLING_ENABLED": 1},
        )
        result = _billing_post_hook(spec, {})
        assert result.settings["QUICKSCALE_BILLING_ENABLED"] is True

    def test_coerces_bool_enabled_from_falsy_int(self) -> None:
        """Falsy int values produce False."""
        spec = ModuleWiringSpec(
            settings={"QUICKSCALE_BILLING_ENABLED": 0},
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
            },
        )
        result = _billing_post_hook(spec, {})
        assert result.settings["QUICKSCALE_BILLING_PUBLISHABLE_KEY_ENV_VAR"] == "123"
        assert result.settings["QUICKSCALE_BILLING_SECRET_KEY_ENV_VAR"] == "456"
        assert result.settings["QUICKSCALE_BILLING_WEBHOOK_SECRET_ENV_VAR"] == "789"
        assert result.settings["QUICKSCALE_BILLING_CURRENCY"] == "999"

    def test_preserves_non_setting_fields(self) -> None:
        """Fields other than settings must pass through unchanged."""
        spec = ModuleWiringSpec(
            apps=("quickscale_modules_billing",),
            middleware=("some.middleware",),
            settings={"QUICKSCALE_BILLING_ENABLED": 0},
        )
        result = _billing_post_hook(spec, {})
        assert result.apps == ("quickscale_modules_billing",)
        assert result.middleware == ("some.middleware",)

    def test_missing_optional_str_key_does_not_raise(self) -> None:
        """Optional string keys that are absent are silently skipped."""
        spec = ModuleWiringSpec(
            settings={"QUICKSCALE_BILLING_ENABLED": True},
        )
        result = _billing_post_hook(spec, {})
        assert result.settings["QUICKSCALE_BILLING_ENABLED"] is True


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
