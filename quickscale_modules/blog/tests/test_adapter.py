"""Focused tests for the blog manifest adapter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from quickscale_core.manifest import ManifestError
from quickscale_core.module_wiring import ModuleWiringSpec

from quickscale_modules_blog.adapter import (
    _blog_manifest_adapter,
    _blog_post_hook,
    get_manifest_adapter,
)


def test_get_manifest_adapter_returns_callable() -> None:
    assert callable(get_manifest_adapter())


def test_missing_blog_setting_raises_key_error() -> None:
    with pytest.raises(KeyError, match="QUICKSCALE_BLOG_POSTS_PER_PAGE"):
        _blog_post_hook(
            ModuleWiringSpec(
                settings={
                    "QUICKSCALE_BLOG_RSS_ENABLED": True,
                    "QUICKSCALE_BLOG_API_RATE_LIMIT": "5/hour",
                }
            ),
            {},
        )


def test_whitespace_only_rate_limit_raises_manifest_error() -> None:
    with pytest.raises(ManifestError, match="QUICKSCALE_BLOG_API_RATE_LIMIT"):
        _blog_post_hook(
            ModuleWiringSpec(
                settings={
                    "QUICKSCALE_BLOG_POSTS_PER_PAGE": 10,
                    "QUICKSCALE_BLOG_RSS_ENABLED": True,
                    "QUICKSCALE_BLOG_API_RATE_LIMIT": "   ",
                }
            ),
            {},
        )


def test_post_hook_coerces_and_adds_static_settings() -> None:
    result = _blog_post_hook(
        ModuleWiringSpec(
            settings={
                "QUICKSCALE_BLOG_POSTS_PER_PAGE": "10",
                "QUICKSCALE_BLOG_RSS_ENABLED": 1,
                "QUICKSCALE_BLOG_API_RATE_LIMIT": " 5/hour ",
            }
        ),
        {"enabled": True},
    )
    assert result.settings["QUICKSCALE_BLOG_POSTS_PER_PAGE"] == 10
    assert result.settings["QUICKSCALE_BLOG_RSS_ENABLED"] is True
    assert result.settings["QUICKSCALE_BLOG_API_RATE_LIMIT"] == "5/hour"
    assert result.settings["REST_FRAMEWORK"] == {
        "DEFAULT_THROTTLE_RATES": {"quickscale_blog_api": "5/hour"}
    }
    assert result.settings["MARKDOWNX_MEDIA_PATH"] == "blog/markdownx/"


def test_disabled_module_drops_url_mounts_and_keeps_apps() -> None:
    """Rule 1 (D3): off keeps the app and settings but mounts no URLs."""
    result = _blog_post_hook(
        ModuleWiringSpec(
            apps=("rest_framework", "markdownx", "quickscale_modules_blog"),
            settings={
                "QUICKSCALE_BLOG_POSTS_PER_PAGE": 10,
                "QUICKSCALE_BLOG_RSS_ENABLED": True,
                "QUICKSCALE_BLOG_API_RATE_LIMIT": "5/hour",
            },
            pre_home_url_includes=(),
            url_includes=(
                ("blog/", "quickscale_modules_blog.urls"),
                ("markdownx/", "quickscale_modules_blog.markdownx_urls"),
            ),
        ),
        {"enabled": False},
    )
    # The retained admin editor keeps its staff-guarded endpoint mount; the
    # module's own public mount is gone.
    assert result.url_includes == (
        ("markdownx/", "quickscale_modules_blog.markdownx_urls"),
    )
    assert ("markdownx/", "markdownx.urls") not in result.url_includes
    assert ("blog/", "quickscale_modules_blog.urls") not in result.url_includes
    assert result.pre_home_url_includes == ()
    assert result.apps == ("rest_framework", "markdownx", "quickscale_modules_blog")
    assert result.settings["QUICKSCALE_BLOG_RSS_ENABLED"] is True


@patch("quickscale_modules_blog.adapter.build_generic_manifest_spec")
def test_adapter_delegates_to_generic_manifest(mock_build: MagicMock) -> None:
    mock_build.return_value = ModuleWiringSpec()
    result = _blog_manifest_adapter({"enabled": True})
    mock_build.assert_called_once_with(
        "blog", {"enabled": True}, post_hook=_blog_post_hook
    )
    assert isinstance(result, ModuleWiringSpec)
