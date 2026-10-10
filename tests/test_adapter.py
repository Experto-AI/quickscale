"""Focused tests for the analytics manifest adapter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from quickscale_core.manifest import ManifestError
from quickscale_core.module_wiring import ModuleWiringSpec

from quickscale_modules_analytics.adapter import (
    _analytics_manifest_adapter,
    _analytics_post_hook,
    get_manifest_adapter,
)


def _settings(**overrides: object) -> dict[str, object]:
    settings: dict[str, object] = {
        "QUICKSCALE_ANALYTICS_ENABLED": True,
        "QUICKSCALE_ANALYTICS_PROVIDER": "posthog",
        "QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR": "POSTHOG_API_KEY",
        "QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR": "POSTHOG_HOST",
        "QUICKSCALE_ANALYTICS_POSTHOG_HOST": "https://us.i.posthog.com",
    }
    settings.update(overrides)
    return settings


def test_get_manifest_adapter_returns_callable() -> None:
    assert callable(get_manifest_adapter())


@pytest.mark.parametrize(
    "key",
    [
        "QUICKSCALE_ANALYTICS_PROVIDER",
        "QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR",
        "QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR",
        "QUICKSCALE_ANALYTICS_POSTHOG_HOST",
    ],
)
def test_empty_required_setting_raises_manifest_error(key: str) -> None:
    with pytest.raises(ManifestError, match=key):
        _analytics_post_hook(
            ModuleWiringSpec(settings=_settings(**{key: ""})),
            {"enabled": True},
        )


def test_disabled_analytics_keeps_apps_and_drops_public_urls() -> None:
    """Rule 1 (D3): off keeps apps/middleware/settings, drops URLs."""
    settings = _settings(
        QUICKSCALE_ANALYTICS_ENABLED=False,
        QUICKSCALE_ANALYTICS_PROVIDER="",
    )
    result = _analytics_post_hook(
        ModuleWiringSpec(
            apps=("quickscale_modules_analytics",),
            middleware=("x.middleware.TrackMiddleware",),
            url_includes=(("analytics/", "quickscale_modules_analytics.urls"),),
            settings=settings,
        ),
        {"enabled": False},
    )
    assert result.apps == ("quickscale_modules_analytics",)
    assert result.middleware == ("x.middleware.TrackMiddleware",)
    assert result.url_includes == ()
    assert result.pre_home_url_includes == ()
    assert result.spa_routes == ()
    # The settings surface is retained, including the secret projections.
    for key in settings:
        assert key in result.settings
    assert (
        result.settings["QUICKSCALE_ANALYTICS_POSTHOG_API_KEY"]
        == "__QS_ENV__:POSTHOG_API_KEY"
    )
    assert (
        result.settings["QUICKSCALE_ANALYTICS_POSTHOG_HOST_OVERRIDE"]
        == "__QS_ENV__:POSTHOG_HOST"
    )


def test_enabled_post_hook_projects_secret_settings_from_env_var_names() -> None:
    result = _analytics_post_hook(
        ModuleWiringSpec(settings=_settings()),
        {"enabled": True},
    )

    assert (
        result.settings["QUICKSCALE_ANALYTICS_POSTHOG_API_KEY"]
        == "__QS_ENV__:POSTHOG_API_KEY"
    )
    assert (
        result.settings["QUICKSCALE_ANALYTICS_POSTHOG_HOST_OVERRIDE"]
        == "__QS_ENV__:POSTHOG_HOST"
    )


def test_enabled_post_hook_projects_configured_env_var_names() -> None:
    result = _analytics_post_hook(
        ModuleWiringSpec(
            settings=_settings(
                QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR="OPS_POSTHOG_KEY",
                QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR="OPS_POSTHOG_HOST",
            )
        ),
        {"enabled": True},
    )

    assert (
        result.settings["QUICKSCALE_ANALYTICS_POSTHOG_API_KEY"]
        == "__QS_ENV__:OPS_POSTHOG_KEY"
    )
    assert (
        result.settings["QUICKSCALE_ANALYTICS_POSTHOG_HOST_OVERRIDE"]
        == "__QS_ENV__:OPS_POSTHOG_HOST"
    )


def test_post_hook_coerces_settings() -> None:
    result = _analytics_post_hook(
        ModuleWiringSpec(
            apps=("analytics",),
            settings=_settings(
                QUICKSCALE_ANALYTICS_ENABLED=1,
                QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG=0,
            ),
        ),
        {"enabled": True},
    )
    assert result.settings["QUICKSCALE_ANALYTICS_ENABLED"] is True
    assert result.settings["QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG"] is False


@patch("quickscale_modules_analytics.adapter.build_generic_manifest_spec")
def test_adapter_delegates_to_generic_manifest(mock_build: MagicMock) -> None:
    mock_build.return_value = ModuleWiringSpec()
    result = _analytics_manifest_adapter({"enabled": True})
    mock_build.assert_called_once_with(
        "analytics", {"enabled": True}, post_hook=_analytics_post_hook
    )
    assert isinstance(result, ModuleWiringSpec)
