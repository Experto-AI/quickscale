"""Wiring-parity tests for the manifest-driven forms path (C7).

Compares the legacy ``_forms_wiring`` builder output against the manifest-driven
``build_manifest_wiring_spec("forms", ...)`` for every option case, asserting
full :class:`~quickscale_core.module_wiring.ModuleWiringSpec` dataclass equality.

Key invariants verified:
- apps tuple: ("rest_framework", "django_filters", "quickscale_modules_forms")
- url_includes: [("", "quickscale_modules_forms.urls")]
- FORMS_PER_PAGE int
- FORMS_SPAM_PROTECTION bool
- FORMS_RATE_LIMIT str
- FORMS_DATA_RETENTION_DAYS int
- FORMS_SUBMISSIONS_API bool

Scope
-----
* Default options (empty dict)
* forms_per_page override
* spam_protection_enabled override
* rate_limit override
* data_retention_days override
* submissions_api_enabled override
* Combined override case
"""

from __future__ import annotations

import pytest

from wiring_parity import assert_wiring_parity


class TestFormsWiringParityDefaults:
    """Default options must produce equal specs from both paths."""

    def test_empty_options(self) -> None:
        assert_wiring_parity("forms", [{}])

    def test_default_apps_order(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("forms", {})
        assert spec.apps == (
            "rest_framework",
            "django_filters",
            "quickscale_modules_forms",
        )

    def test_default_url_includes(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("forms", {})
        assert spec.url_includes == (("", "quickscale_modules_forms.urls"),)

    def test_default_forms_per_page(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("forms", {})
        assert spec.settings["FORMS_PER_PAGE"] == 25

    def test_default_spam_protection_true(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("forms", {})
        assert spec.settings["FORMS_SPAM_PROTECTION"] is True

    def test_default_rate_limit(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("forms", {})
        assert spec.settings["FORMS_RATE_LIMIT"] == "5/hour"

    def test_default_data_retention_days(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("forms", {})
        assert spec.settings["FORMS_DATA_RETENTION_DAYS"] == 365

    def test_default_submissions_api_true(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("forms", {})
        assert spec.settings["FORMS_SUBMISSIONS_API"] is True


class TestFormsWiringParityOverrides:
    """Overridden options must produce equal specs from both paths."""

    @pytest.mark.parametrize("per_page", [1, 10, 25, 50, 100])
    def test_forms_per_page(self, per_page: int) -> None:
        assert_wiring_parity("forms", [{"forms_per_page": per_page}])

    def test_spam_protection_disabled(self) -> None:
        assert_wiring_parity("forms", [{"spam_protection_enabled": False}])

    def test_spam_protection_enabled_explicit(self) -> None:
        assert_wiring_parity("forms", [{"spam_protection_enabled": True}])

    @pytest.mark.parametrize(
        "rate_limit",
        ["1/second", "5/minute", "10/hour", "100/day"],
    )
    def test_rate_limit_variants(self, rate_limit: str) -> None:
        assert_wiring_parity("forms", [{"rate_limit": rate_limit}])

    @pytest.mark.parametrize("days", [0, 30, 90, 365, 730])
    def test_data_retention_days(self, days: int) -> None:
        assert_wiring_parity("forms", [{"data_retention_days": days}])

    def test_submissions_api_disabled(self) -> None:
        assert_wiring_parity("forms", [{"submissions_api_enabled": False}])

    def test_submissions_api_enabled_explicit(self) -> None:
        assert_wiring_parity("forms", [{"submissions_api_enabled": True}])

    def test_combined_overrides(self) -> None:
        assert_wiring_parity(
            "forms",
            [
                {
                    "forms_per_page": 50,
                    "spam_protection_enabled": False,
                    "rate_limit": "10/minute",
                    "data_retention_days": 90,
                    "submissions_api_enabled": False,
                }
            ],
        )

    def test_multiple_cases_batch(self) -> None:
        assert_wiring_parity(
            "forms",
            [
                {},
                {"forms_per_page": 50},
                {"spam_protection_enabled": False},
                {"rate_limit": "10/minute"},
                {"data_retention_days": 90},
                {"submissions_api_enabled": False},
                {
                    "forms_per_page": 10,
                    "spam_protection_enabled": True,
                    "rate_limit": "1/second",
                    "data_retention_days": 730,
                    "submissions_api_enabled": True,
                },
            ],
        )
