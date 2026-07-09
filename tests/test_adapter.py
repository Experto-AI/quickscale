"""Focused tests for the CRM manifest adapter.

Covers the post-resolution coercion hook and the sentinel contract.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from quickscale_core.module_wiring import ModuleWiringSpec

from quickscale_modules_crm.adapter import (
    _crm_manifest_adapter,
    _crm_post_hook,
    get_manifest_adapter,
)


class TestGetManifestAdapter:
    """get_manifest_adapter sentinel contract."""

    def test_returns_callable(self) -> None:
        """get_manifest_adapter must return a callable."""
        adapter = get_manifest_adapter()
        assert callable(adapter)


class TestCrmPostHook:
    """_crm_post_hook — int/bool coercions (SA17.3)."""

    def test_coerces_deals_per_page_to_int(self) -> None:
        """CRM_DEALS_PER_PAGE must be coerced to int."""
        spec = ModuleWiringSpec(
            settings={
                "CRM_DEALS_PER_PAGE": "25",
                "CRM_CONTACTS_PER_PAGE": "50",
                "CRM_ENABLE_API": 1,
            },
        )
        result = _crm_post_hook(spec, {})
        assert result.settings["CRM_DEALS_PER_PAGE"] == 25
        assert isinstance(result.settings["CRM_DEALS_PER_PAGE"], int)

    def test_coerces_contacts_per_page_to_int(self) -> None:
        """CRM_CONTACTS_PER_PAGE must be coerced to int."""
        spec = ModuleWiringSpec(
            settings={
                "CRM_DEALS_PER_PAGE": "10",
                "CRM_CONTACTS_PER_PAGE": "20",
                "CRM_ENABLE_API": 0,
            },
        )
        result = _crm_post_hook(spec, {})
        assert result.settings["CRM_CONTACTS_PER_PAGE"] == 20
        assert isinstance(result.settings["CRM_CONTACTS_PER_PAGE"], int)

    def test_coerces_enable_api_to_bool(self) -> None:
        """CRM_ENABLE_API must be coerced to bool."""
        spec = ModuleWiringSpec(
            settings={
                "CRM_DEALS_PER_PAGE": "10",
                "CRM_CONTACTS_PER_PAGE": "10",
                "CRM_ENABLE_API": 1,
            },
        )
        result = _crm_post_hook(spec, {})
        assert result.settings["CRM_ENABLE_API"] is True

    def test_coerces_enable_api_to_false(self) -> None:
        """Falsy values produce False for the API flag."""
        spec = ModuleWiringSpec(
            settings={
                "CRM_DEALS_PER_PAGE": "5",
                "CRM_CONTACTS_PER_PAGE": "5",
                "CRM_ENABLE_API": 0,
            },
        )
        result = _crm_post_hook(spec, {})
        assert result.settings["CRM_ENABLE_API"] is False

    def test_preserves_non_setting_fields(self) -> None:
        """Fields other than settings must pass through unchanged."""
        spec = ModuleWiringSpec(
            apps=("quickscale_modules_crm",),
            middleware=(),
            settings={
                "CRM_DEALS_PER_PAGE": "10",
                "CRM_CONTACTS_PER_PAGE": "20",
                "CRM_ENABLE_API": True,
            },
        )
        result = _crm_post_hook(spec, {})
        assert result.apps == ("quickscale_modules_crm",)
        assert result.middleware == ()


class TestCrmManifestAdapter:
    """_crm_manifest_adapter delegation."""

    @patch("quickscale_modules_crm.adapter.build_generic_manifest_spec")
    def test_delegates_to_build_generic_manifest_spec(
        self,
        mock_build: MagicMock,
    ) -> None:
        """The adapter must call build_generic_manifest_spec with crm module name."""
        mock_build.return_value = ModuleWiringSpec()

        result = _crm_manifest_adapter({"enabled": True})

        mock_build.assert_called_once_with(
            "crm",
            {"enabled": True},
            post_hook=_crm_post_hook,
        )
        assert isinstance(result, ModuleWiringSpec)

    @patch("quickscale_modules_crm.adapter.build_generic_manifest_spec")
    def test_passes_options_unchanged(self, mock_build: MagicMock) -> None:
        """Adapter must forward the options dict literally."""
        mock_build.return_value = ModuleWiringSpec()

        _crm_manifest_adapter({"deals_per_page": 50})

        mock_build.assert_called_once_with(
            "crm",
            {"deals_per_page": 50},
            post_hook=_crm_post_hook,
        )
