"""Wiring-parity tests for the manifest-driven CRM path (C6).

Compares the legacy ``_crm_wiring`` builder output against the manifest-driven
``build_manifest_wiring_spec("crm", ...)`` for every option case, asserting
full :class:`~quickscale_core.module_wiring.ModuleWiringSpec` dataclass equality.

Key invariants verified:
- apps tuple: ("rest_framework", "django_filters", "quickscale_modules_crm")
- url_includes: [("", "quickscale_modules_crm.urls")]
- CRM_DEALS_PER_PAGE int
- CRM_CONTACTS_PER_PAGE int
- CRM_ENABLE_API bool

Scope
-----
* Default options (empty dict)
* deals_per_page override
* contacts_per_page override
* enable_api override
* Combined override case
"""

from __future__ import annotations

import pytest

from wiring_parity import assert_wiring_parity


class TestCrmWiringParityDefaults:
    """Default options must produce equal specs from both paths."""

    def test_empty_options(self) -> None:
        assert_wiring_parity("crm", [{}])

    def test_default_apps_order(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("crm", {})
        assert spec.apps == (
            "rest_framework",
            "django_filters",
            "quickscale_modules_crm",
        )

    def test_default_url_includes(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("crm", {})
        assert spec.url_includes == (("", "quickscale_modules_crm.urls"),)

    def test_default_enable_api_true(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("crm", {})
        assert spec.settings["CRM_ENABLE_API"] is True

    def test_default_deals_per_page(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("crm", {})
        assert spec.settings["CRM_DEALS_PER_PAGE"] == 25

    def test_default_contacts_per_page(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("crm", {})
        assert spec.settings["CRM_CONTACTS_PER_PAGE"] == 50


class TestCrmWiringParityOverrides:
    """Overridden options must produce equal specs from both paths."""

    @pytest.mark.parametrize("per_page", [1, 10, 25, 50, 100])
    def test_deals_per_page(self, per_page: int) -> None:
        assert_wiring_parity("crm", [{"deals_per_page": per_page}])

    @pytest.mark.parametrize("per_page", [1, 10, 50, 100, 200])
    def test_contacts_per_page(self, per_page: int) -> None:
        assert_wiring_parity("crm", [{"contacts_per_page": per_page}])

    def test_enable_api_false(self) -> None:
        assert_wiring_parity("crm", [{"enable_api": False}])

    def test_enable_api_true_explicit(self) -> None:
        assert_wiring_parity("crm", [{"enable_api": True}])

    def test_combined_overrides(self) -> None:
        assert_wiring_parity(
            "crm",
            [
                {
                    "deals_per_page": 50,
                    "contacts_per_page": 100,
                    "enable_api": False,
                }
            ],
        )

    def test_multiple_cases_batch(self) -> None:
        assert_wiring_parity(
            "crm",
            [
                {},
                {"deals_per_page": 10},
                {"contacts_per_page": 100},
                {"enable_api": False},
                {"deals_per_page": 50, "contacts_per_page": 200, "enable_api": True},
            ],
        )
