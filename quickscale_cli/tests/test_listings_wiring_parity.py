"""Wiring-parity tests for the manifest-driven listings path (C3).

Compares the legacy ``_listings_wiring`` builder output against the manifest-driven
``build_manifest_wiring_spec("listings", ...)`` for every option case, asserting
full :class:`~quickscale_core.module_wiring.ModuleWiringSpec` dataclass equality.

Key invariants verified:
- apps tuple: ("django_filters", "markdownx", "quickscale_modules_listings")
- url_includes: [("listings/", ...), ("markdownx/", ...)]
- MARKDOWNX_MARKDOWN_EXTENSIONS list (static)
- LISTINGS_PER_PAGE int

Scope
-----
* Default options (empty dict)
* Custom listings_per_page
* Batch of cases
"""

from __future__ import annotations

import pytest

from wiring_parity import assert_wiring_parity


class TestListingsWiringParityDefaults:
    """Default options must produce equal specs from both paths."""

    def test_empty_options(self) -> None:
        assert_wiring_parity("listings", [{}])

    def test_default_apps_order(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("listings", {})
        assert spec.apps == (
            "django_filters",
            "markdownx",
            "quickscale_modules_listings",
        )

    def test_default_url_includes(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("listings", {})
        assert spec.url_includes == (
            ("listings/", "quickscale_modules_listings.urls"),
            ("markdownx/", "markdownx.urls"),
        )

    def test_markdownx_extensions_present(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("listings", {})
        assert "MARKDOWNX_MARKDOWN_EXTENSIONS" in spec.settings
        assert spec.settings["MARKDOWNX_MARKDOWN_EXTENSIONS"] == [
            "markdown.extensions.fenced_code",
            "markdown.extensions.tables",
            "markdown.extensions.toc",
        ]


class TestListingsWiringParityOverrides:
    """Overridden options must produce equal specs from both paths."""

    @pytest.mark.parametrize("per_page", [1, 5, 12, 20, 50, 100])
    def test_listings_per_page(self, per_page: int) -> None:
        assert_wiring_parity("listings", [{"listings_per_page": per_page}])

    def test_combined_cases_batch(self) -> None:
        assert_wiring_parity(
            "listings",
            [
                {},
                {"listings_per_page": 1},
                {"listings_per_page": 24},
                {"listings_per_page": 50},
            ],
        )
