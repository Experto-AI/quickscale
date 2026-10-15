"""Focused tests for the CRM manifest adapter.

The generic manifest boundary owns CRM's option defaults, normalization,
checks, and projections; these tests pin the adapter's remaining contract —
the off-switch transformation, canonical settings, and the sentinel.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from quickscale_core.manifest import ManifestError, ResolvedOptions
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


class TestCrmManifestAdapterSettings:
    """The manifest owns every canonical CRM setting."""

    def test_defaults_are_canonical(self) -> None:
        spec = _crm_manifest_adapter({})

        assert spec.settings["QUICKSCALE_CRM_DEALS_PER_PAGE"] == 25
        assert spec.settings["QUICKSCALE_CRM_CONTACTS_PER_PAGE"] == 50
        assert spec.settings["QUICKSCALE_CRM_API_ENABLED"] is True

    def test_overrides_are_canonical(self) -> None:
        spec = _crm_manifest_adapter(
            {"deals_per_page": 10, "contacts_per_page": 20, "api_enabled": False}
        )

        assert spec.settings["QUICKSCALE_CRM_DEALS_PER_PAGE"] == 10
        assert spec.settings["QUICKSCALE_CRM_CONTACTS_PER_PAGE"] == 20
        assert spec.settings["QUICKSCALE_CRM_API_ENABLED"] is False

    @pytest.mark.parametrize(
        ("option_name", "value"),
        [
            ("deals_per_page", "25"),
            ("contacts_per_page", True),
            ("api_enabled", 1),
            ("tags_per_page", 0),
        ],
    )
    def test_wrong_shaped_values_are_refused(
        self, option_name: str, value: object
    ) -> None:
        """A raw value of the wrong shape (or range) is refused, never coerced."""
        with pytest.raises(ManifestError, match="modules.crm."):
            _crm_manifest_adapter({option_name: value})


class TestCrmPostHook:
    """_crm_post_hook — the off-switch transformation."""

    def test_enabled_returns_the_assembled_spec(self) -> None:
        spec = ModuleWiringSpec(apps=("quickscale_modules_crm",))
        assert _crm_post_hook(spec, ResolvedOptions({"enabled": True})) is spec

    def test_disabled_module_drops_url_mounts_and_keeps_apps(self) -> None:
        """Rule 1 (D3): off keeps the app and settings but mounts no URLs."""
        spec = ModuleWiringSpec(
            apps=("rest_framework", "django_filters", "quickscale_modules_crm"),
            settings={
                "QUICKSCALE_CRM_DEALS_PER_PAGE": 25,
                "QUICKSCALE_CRM_API_ENABLED": True,
            },
            pre_home_url_includes=(),
            url_includes=(("crm/", "quickscale_modules_crm.urls"),),
        )
        result = _crm_post_hook(spec, ResolvedOptions({"enabled": False}))
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
