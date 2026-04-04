"""Tests for analytics AppConfig startup behavior."""

from __future__ import annotations

from importlib import import_module
from unittest.mock import patch

from quickscale_modules_analytics.apps import QuickscaleAnalyticsConfig


@patch("quickscale_modules_analytics.apps.configure_analytics_client")
def test_ready_configures_analytics_client(mock_configure_analytics_client) -> None:
    """App startup should delegate to the analytics client configurator."""
    config = QuickscaleAnalyticsConfig(
        "quickscale_modules_analytics",
        import_module("quickscale_modules_analytics"),
    )

    config.ready()

    mock_configure_analytics_client.assert_called_once_with()


@patch(
    "quickscale_modules_analytics.apps.configure_analytics_client",
    side_effect=RuntimeError("boom"),
)
def test_ready_never_raises_when_configuration_fails(
    mock_configure_analytics_client,
) -> None:
    """Unexpected startup exceptions must not block Django app loading."""
    config = QuickscaleAnalyticsConfig(
        "quickscale_modules_analytics",
        import_module("quickscale_modules_analytics"),
    )

    config.ready()

    mock_configure_analytics_client.assert_called_once_with()
