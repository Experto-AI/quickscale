"""Focused tests for the listings manifest adapter.

The generic manifest boundary owns listings' option defaults, normalization,
checks, and settings surface; these tests pin the adapter's remaining
contract — the throttle scope and the off-switch transformation.  The one
shared staff-guarded Markdownx editor mount and its global settings are
storage's (rule 41).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from quickscale_core.manifest import ManifestError, ResolvedOptions
from quickscale_core.module_wiring import ModuleWiringSpec

from quickscale_modules_listings.adapter import (
    _listings_manifest_adapter,
    _listings_post_hook,
    get_manifest_adapter,
)


def test_get_manifest_adapter_returns_callable() -> None:
    assert callable(get_manifest_adapter())


@pytest.mark.parametrize(
    ("option_name", "value"),
    [
        ("per_page", "24"),
        ("per_page", 0),
        ("api_rate_limit", "no-rate"),
    ],
)
def test_wrong_shaped_values_are_refused(option_name: str, value: object) -> None:
    """A raw value of the wrong shape (or range/pattern) is refused."""
    with pytest.raises(ManifestError, match="modules.listings."):
        _listings_manifest_adapter({option_name: value})


def test_manifest_projects_settings_and_throttle_scope() -> None:
    result = _listings_manifest_adapter({"api_rate_limit": " 7/hour "})

    assert result.settings["QUICKSCALE_LISTINGS_PER_PAGE"] == 12
    assert result.settings["QUICKSCALE_LISTINGS_API_RATE_LIMIT"] == "7/hour"
    assert result.settings["REST_FRAMEWORK"] == {
        "DEFAULT_THROTTLE_RATES": {"quickscale_listings_api": "7/hour"},
    }
    # Rule 41: the shared Markdownx mount and its global settings are
    # storage's; listings writes none of them.
    assert "MARKDOWNX_MEDIA_PATH" not in result.settings
    assert "MARKDOWNX_MARKDOWN_EXTENSIONS" not in result.settings


def test_disabled_module_drops_url_mounts_and_keeps_apps() -> None:
    """Rule 1 (D3): off keeps the app and settings but mounts no URLs."""
    result = _listings_post_hook(
        ModuleWiringSpec(
            apps=(
                "rest_framework",
                "django_filters",
                "markdownx",
                "quickscale_modules_listings",
            ),
            settings={"QUICKSCALE_LISTINGS_API_RATE_LIMIT": "5/hour"},
            pre_home_url_includes=(),
            url_includes=(
                ("listings/", "quickscale_modules_listings.urls"),
                ("markdownx/", "quickscale_modules_listings.markdownx_urls"),
            ),
        ),
        ResolvedOptions({"enabled": False}),
    )
    # The module's public mount is gone; the shared staff-guarded Markdownx
    # editor mount belongs to storage (rule 41).
    assert result.url_includes == ()
    assert ("markdownx/", "markdownx.urls") not in result.url_includes
    assert ("listings/", "quickscale_modules_listings.urls") not in result.url_includes
    assert result.pre_home_url_includes == ()
    assert result.apps == (
        "rest_framework",
        "django_filters",
        "markdownx",
        "quickscale_modules_listings",
    )
    assert result.settings["REST_FRAMEWORK"] == {
        "DEFAULT_THROTTLE_RATES": {"quickscale_listings_api": "5/hour"},
    }


@patch("quickscale_modules_listings.adapter.build_generic_manifest_spec")
def test_adapter_delegates_to_generic_manifest(mock_build: MagicMock) -> None:
    mock_build.return_value = ModuleWiringSpec()
    result = _listings_manifest_adapter({"enabled": True})
    mock_build.assert_called_once_with(
        "listings", {"enabled": True}, post_hook=_listings_post_hook
    )
    assert isinstance(result, ModuleWiringSpec)
