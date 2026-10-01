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
        {},
    )
    assert result.settings["QUICKSCALE_BLOG_POSTS_PER_PAGE"] == 10
    assert result.settings["QUICKSCALE_BLOG_RSS_ENABLED"] is True
    assert result.settings["QUICKSCALE_BLOG_API_RATE_LIMIT"] == "5/hour"
    assert result.settings["REST_FRAMEWORK"] == {
        "DEFAULT_THROTTLE_RATES": {"quickscale_blog_api": "5/hour"}
    }
    assert result.settings["MARKDOWNX_MEDIA_PATH"] == "blog/markdownx/"


@patch("quickscale_modules_blog.adapter.build_generic_manifest_spec")
def test_adapter_delegates_to_generic_manifest(mock_build: MagicMock) -> None:
    mock_build.return_value = ModuleWiringSpec()
    result = _blog_manifest_adapter({"enabled": True})
    mock_build.assert_called_once_with(
        "blog", {"enabled": True}, post_hook=_blog_post_hook
    )
    assert isinstance(result, ModuleWiringSpec)
