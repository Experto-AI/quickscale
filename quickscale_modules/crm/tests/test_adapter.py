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
    """_crm_post_hook — int/bool coercions."""

    def test_coerces_deals_per_page_to_int(self) -> None:
        """QUICKSCALE_CRM_DEALS_PER_PAGE must be coerced to int."""
        spec = ModuleWiringSpec(
            settings={
                "QUICKSCALE_CRM_DEALS_PER_PAGE": "25",
                "QUICKSCALE_CRM_CONTACTS_PER_PAGE": "50",
                "QUICKSCALE_CRM_API_ENABLED": 1,
            },
        )
        result = _crm_post_hook(spec, {"enabled": True})
        assert result.settings["QUICKSCALE_CRM_DEALS_PER_PAGE"] == 25
        assert isinstance(result.settings["QUICKSCALE_CRM_DEALS_PER_PAGE"], int)

    def test_coerces_contacts_per_page_to_int(self) -> None:
        """QUICKSCALE_CRM_CONTACTS_PER_PAGE must be coerced to int."""
        spec = ModuleWiringSpec(
            settings={
                "QUICKSCALE_CRM_DEALS_PER_PAGE": "10",
                "QUICKSCALE_CRM_CONTACTS_PER_PAGE": "20",
                "QUICKSCALE_CRM_API_ENABLED": 0,
            },
        )
        result = _crm_post_hook(spec, {"enabled": True})
        assert result.settings["QUICKSCALE_CRM_CONTACTS_PER_PAGE"] == 20
        assert isinstance(result.settings["QUICKSCALE_CRM_CONTACTS_PER_PAGE"], int)

    def test_coerces_enable_api_to_bool(self) -> None:
        """QUICKSCALE_CRM_API_ENABLED must be coerced to bool."""
        spec = ModuleWiringSpec(
            settings={
                "QUICKSCALE_CRM_DEALS_PER_PAGE": "10",
                "QUICKSCALE_CRM_CONTACTS_PER_PAGE": "10",
                "QUICKSCALE_CRM_API_ENABLED": 1,
            },
        )
        result = _crm_post_hook(spec, {"enabled": True})
        assert result.settings["QUICKSCALE_CRM_API_ENABLED"] is True

    def test_coerces_enable_api_to_false(self) -> None:
        """Falsy values produce False for the API flag."""
        spec = ModuleWiringSpec(
            settings={
                "QUICKSCALE_CRM_DEALS_PER_PAGE": "5",
                "QUICKSCALE_CRM_CONTACTS_PER_PAGE": "5",
                "QUICKSCALE_CRM_API_ENABLED": 0,
            },
        )
        result = _crm_post_hook(spec, {"enabled": True})
        assert result.settings["QUICKSCALE_CRM_API_ENABLED"] is False

    def test_preserves_non_setting_fields(self) -> None:
        """Fields other than settings must pass through unchanged."""
        spec = ModuleWiringSpec(
            apps=("quickscale_modules_crm",),
            middleware=(),
            settings={
                "QUICKSCALE_CRM_DEALS_PER_PAGE": "10",
                "QUICKSCALE_CRM_CONTACTS_PER_PAGE": "20",
                "QUICKSCALE_CRM_API_ENABLED": True,
            },
        )
        result = _crm_post_hook(spec, {"enabled": True})
        assert result.apps == ("quickscale_modules_crm",)
        assert result.middleware == ()

    def test_disabled_module_drops_url_mounts_and_keeps_apps(self) -> None:
        """Rule 1 (D3): off keeps the app and settings but mounts no URLs."""
        spec = ModuleWiringSpec(
            apps=("rest_framework", "django_filters", "quickscale_modules_crm"),
            settings={
                "QUICKSCALE_CRM_DEALS_PER_PAGE": 25,
                "QUICKSCALE_CRM_CONTACTS_PER_PAGE": 50,
                "QUICKSCALE_CRM_API_ENABLED": True,
            },
            pre_home_url_includes=(),
            url_includes=(("crm/", "quickscale_modules_crm.urls"),),
        )
        result = _crm_post_hook(spec, {"enabled": False})
        assert result.url_includes == ()
        assert result.pre_home_url_includes == ()
        assert result.apps == (
            "rest_framework",
            "django_filters",
            "quickscale_modules_crm",
        )
        assert result.settings["QUICKSCALE_CRM_API_ENABLED"] is True


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
