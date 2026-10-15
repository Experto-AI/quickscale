"""Focused tests for the analytics manifest adapter.

The generic manifest boundary owns analytics' option defaults, normalization,
checks, and secret projections; these tests pin the adapter's remaining
contract — the off-switch transformation, the manifest-owned settings
surface, and the fail-closed boundary behaviour.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from quickscale_core.manifest import ManifestError, ResolvedOptions
from quickscale_core.module_wiring import ModuleWiringSpec

from quickscale_modules_analytics.adapter import (
    _analytics_manifest_adapter,
    _analytics_post_hook,
    get_manifest_adapter,
)


def test_get_manifest_adapter_returns_callable() -> None:
    assert callable(get_manifest_adapter())


@pytest.mark.parametrize(
    "options",
    [
        {"provider": ""},
        {"provider": "unknown"},
        {"posthog_host": ""},
        {"posthog_api_key_env_var": "lower_case"},
        {"anonymous_by_default": "yes"},
    ],
)
def test_invalid_supplied_options_are_refused(options: dict[str, object]) -> None:
    """Invalid values fail closed at the manifest boundary, before any hook."""
    with pytest.raises(ManifestError, match="modules.analytics."):
        _analytics_manifest_adapter(dict(options))


def test_disabled_analytics_keeps_apps_and_drops_public_urls() -> None:
    """Rule 1 (D3): off keeps apps/middleware/settings, drops URLs."""
    result = _analytics_manifest_adapter({"enabled": False})

    assert result.apps == ("quickscale_modules_analytics",)
    assert result.url_includes == ()
    assert result.pre_home_url_includes == ()
    assert result.spa_routes == ()
    assert result.settings["QUICKSCALE_ANALYTICS_ENABLED"] is False
    # The settings surface is retained, including the secret projections.
    assert (
        result.settings["QUICKSCALE_ANALYTICS_POSTHOG_API_KEY"]
        == "__QS_ENV__:POSTHOG_API_KEY"
    )
    assert (
        result.settings["QUICKSCALE_ANALYTICS_POSTHOG_HOST_OVERRIDE"]
        == "__QS_ENV__:POSTHOG_HOST"
    )


def test_manifest_projects_secret_settings_from_env_var_names() -> None:
    result = _analytics_manifest_adapter({})

    assert (
        result.settings["QUICKSCALE_ANALYTICS_POSTHOG_API_KEY"]
        == "__QS_ENV__:POSTHOG_API_KEY"
    )
    assert (
        result.settings["QUICKSCALE_ANALYTICS_POSTHOG_HOST_OVERRIDE"]
        == "__QS_ENV__:POSTHOG_HOST"
    )


def test_manifest_projects_configured_env_var_names() -> None:
    result = _analytics_manifest_adapter(
        {
            "posthog_api_key_env_var": "OPS_POSTHOG_KEY",
            "posthog_host_env_var": "OPS_POSTHOG_HOST",
        }
    )

    assert (
        result.settings["QUICKSCALE_ANALYTICS_POSTHOG_API_KEY"]
        == "__QS_ENV__:OPS_POSTHOG_KEY"
    )
    assert (
        result.settings["QUICKSCALE_ANALYTICS_POSTHOG_HOST_OVERRIDE"]
        == "__QS_ENV__:OPS_POSTHOG_HOST"
    )


def test_manifest_owns_canonical_types() -> None:
    """Canonical boolean values survive the adapter without re-coercion."""
    result = _analytics_manifest_adapter({"exclude_debug": False})

    assert result.settings["QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG"] is False


def test_post_hook_only_transforms_when_disabled() -> None:
    """The hook returns the assembled spec unchanged while enabled."""
    spec = ModuleWiringSpec(
        apps=("analytics",),
        url_includes=(("analytics/", "quickscale_modules_analytics.urls"),),
        settings={"QUICKSCALE_ANALYTICS_ENABLED": True},
    )

    assert _analytics_post_hook(spec, ResolvedOptions({"enabled": True})) is spec


@patch("quickscale_modules_analytics.adapter.build_generic_manifest_spec")
def test_adapter_delegates_to_generic_manifest(mock_build: MagicMock) -> None:
    mock_build.return_value = ModuleWiringSpec()
    result = _analytics_manifest_adapter({"enabled": True})
    mock_build.assert_called_once_with(
        "analytics", {"enabled": True}, post_hook=_analytics_post_hook
    )
    assert isinstance(result, ModuleWiringSpec)
