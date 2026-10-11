"""Focused tests for the listings manifest adapter.

The generic manifest boundary owns listings' option defaults, normalization,
checks, and static markdownx settings; these tests pin the adapter's
remaining contract — the throttle scope, the off-switch transformation, and
the sentinel.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from quickscale_core.manifest import ManifestError
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
    # The static editor extensions are declared by the manifest and applied
    # before the hook runs.
    assert result.settings["MARKDOWNX_MARKDOWN_EXTENSIONS"] == [
        "markdown.extensions.fenced_code",
        "markdown.extensions.tables",
        "markdown.extensions.toc",
    ]


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
        {"enabled": False},
    )
    # The retained admin editor keeps its staff-guarded endpoint mount; the
    # module's own public mount is gone.
    assert result.url_includes == (
        ("markdownx/", "quickscale_modules_listings.markdownx_urls"),
    )
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
