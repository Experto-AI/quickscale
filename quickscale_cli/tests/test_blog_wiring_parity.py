"""Wiring-parity tests for the manifest-driven blog path (C4).

Compares the legacy ``_blog_wiring`` builder output against the manifest-driven
``build_manifest_wiring_spec("blog", ...)`` for every option case, asserting
full :class:`~quickscale_core.module_wiring.ModuleWiringSpec` dataclass equality.

Key invariants verified:
- apps tuple: ("markdownx", "quickscale_modules_blog")
- url_includes: [("blog/", ...), ("markdownx/", ...)]
- MARKDOWNX_MARKDOWN_EXTENSIONS list (static)
- MARKDOWNX_MEDIA_PATH (static)
- BLOG_POSTS_PER_PAGE int
- BLOG_ENABLE_RSS bool
- BLOG_API_RATE_LIMIT str (with fallback to default)

Scope
-----
* Default options (empty dict)
* posts_per_page override
* enable_rss override
* api_rate_limit override
* Combined override case
"""

from __future__ import annotations

import pytest

from wiring_parity import assert_wiring_parity


class TestBlogWiringParityDefaults:
    """Default options must produce equal specs from both paths."""

    def test_empty_options(self) -> None:
        assert_wiring_parity("blog", [{}])

    def test_default_apps_order(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("blog", {})
        assert spec.apps == ("markdownx", "quickscale_modules_blog")

    def test_default_url_includes(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("blog", {})
        assert spec.url_includes == (
            ("blog/", "quickscale_modules_blog.urls"),
            ("markdownx/", "markdownx.urls"),
        )

    def test_markdownx_extensions_present(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("blog", {})
        assert spec.settings["MARKDOWNX_MARKDOWN_EXTENSIONS"] == [
            "markdown.extensions.fenced_code",
            "markdown.extensions.tables",
            "markdown.extensions.toc",
        ]

    def test_markdownx_media_path(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("blog", {})
        assert spec.settings["MARKDOWNX_MEDIA_PATH"] == "blog/markdownx/"

    def test_default_api_rate_limit(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("blog", {})
        assert spec.settings["BLOG_API_RATE_LIMIT"] == "5/hour"


class TestBlogWiringParityOverrides:
    """Overridden options must produce equal specs from both paths."""

    @pytest.mark.parametrize("per_page", [1, 5, 10, 20, 50])
    def test_posts_per_page(self, per_page: int) -> None:
        assert_wiring_parity("blog", [{"posts_per_page": per_page}])

    def test_enable_rss_false(self) -> None:
        assert_wiring_parity("blog", [{"enable_rss": False}])

    def test_enable_rss_true_explicit(self) -> None:
        assert_wiring_parity("blog", [{"enable_rss": True}])

    def test_api_rate_limit_custom(self) -> None:
        assert_wiring_parity("blog", [{"api_rate_limit": "10/minute"}])

    def test_api_rate_limit_per_day(self) -> None:
        assert_wiring_parity("blog", [{"api_rate_limit": "100/day"}])

    def test_combined_overrides(self) -> None:
        assert_wiring_parity(
            "blog",
            [
                {
                    "posts_per_page": 20,
                    "enable_rss": False,
                    "api_rate_limit": "10/minute",
                }
            ],
        )

    def test_multiple_cases_batch(self) -> None:
        assert_wiring_parity(
            "blog",
            [
                {},
                {"posts_per_page": 20},
                {"enable_rss": False},
                {"api_rate_limit": "2/hour"},
                {"posts_per_page": 5, "enable_rss": True, "api_rate_limit": "3/day"},
            ],
        )
