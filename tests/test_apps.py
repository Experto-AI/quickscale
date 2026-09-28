"""Tests for analytics AppConfig startup behavior."""

from __future__ import annotations

from importlib import import_module
from unittest.mock import patch

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import SystemCheckError
from django.core.management.commands import migrate, runserver
from django.test import override_settings

from quickscale_modules_analytics.apps import QuickscaleAnalyticsConfig
from quickscale_modules_analytics.checks import check_analytics_settings


@patch("quickscale_modules_analytics.apps.configure_analytics_client")
def test_ready_configures_analytics_client(
    mock_configure_analytics_client, monkeypatch
) -> None:
    """App startup should delegate to the analytics client configurator."""
    # pytest-django runs tests with DEBUG=False, so the startup check needs a
    # non-empty key before ready() reaches the configurator.
    monkeypatch.setenv("POSTHOG_API_KEY", "test-posthog-key")
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
    mock_configure_analytics_client, monkeypatch
) -> None:
    """Unexpected startup exceptions must not block Django app loading."""
    monkeypatch.setenv("POSTHOG_API_KEY", "test-posthog-key")
    config = QuickscaleAnalyticsConfig(
        "quickscale_modules_analytics",
        import_module("quickscale_modules_analytics"),
    )

    config.ready()

    mock_configure_analytics_client.assert_called_once_with()


@override_settings()  # clear QUICKSCALE_ANALYTICS_ENABLED from overrides
def test_ready_raises_improperly_configured_when_enabled_setting_missing(
    settings,
) -> None:
    """Missing QUICKSCALE_ANALYTICS_ENABLED must raise at startup."""
    # Ensure the setting is not present
    del settings.QUICKSCALE_ANALYTICS_ENABLED

    config = QuickscaleAnalyticsConfig(
        "quickscale_modules_analytics",
        import_module("quickscale_modules_analytics"),
    )

    with pytest.raises(
        ImproperlyConfigured,
        match="QUICKSCALE_ANALYTICS_ENABLED",
    ):
        config.ready()


def test_check_reports_unsupported_provider(settings) -> None:
    """A provider other than PostHog is invalid configuration."""
    settings.QUICKSCALE_ANALYTICS_PROVIDER = "plausible"

    messages = check_analytics_settings()

    assert messages
    assert "QUICKSCALE_ANALYTICS_PROVIDER" in messages[0].msg


def test_check_reports_empty_api_key_for_live_analytics(settings, monkeypatch) -> None:
    """Analytics without the DEBUG exclusion needs a non-empty PostHog key."""
    settings.DEBUG = False
    settings.QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG = False
    monkeypatch.delenv("POSTHOG_API_KEY", raising=False)

    messages = check_analytics_settings()

    assert messages
    assert "POSTHOG_API_KEY" in messages[0].msg


@pytest.mark.parametrize(
    "malformed_host",
    ["not-a-url", "https://:443", "ftp://example.com", "https://example.com:bad"],
)
def test_check_reports_malformed_posthog_host(
    settings, monkeypatch, malformed_host
) -> None:
    """A host that is not an absolute http(s) URL with a hostname is invalid."""
    settings.DEBUG = False
    settings.QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG = False
    settings.QUICKSCALE_ANALYTICS_POSTHOG_HOST = malformed_host
    monkeypatch.setenv("POSTHOG_API_KEY", "test-posthog-key")

    messages = check_analytics_settings()

    assert messages
    assert "QUICKSCALE_ANALYTICS_POSTHOG_HOST" in messages[0].msg


def test_check_skips_empty_api_key_when_debug_excluded(settings, monkeypatch) -> None:
    """A DEBUG-excluded runtime never resolves the key, so it is not required."""
    settings.DEBUG = True
    settings.QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG = True
    monkeypatch.delenv("POSTHOG_API_KEY", raising=False)

    assert check_analytics_settings() == []


@override_settings()
def test_missing_enabled_setting_fails_check_migrate_and_runserver(settings) -> None:
    """The registered check fails check, migrate, and runserver alike."""
    del settings.QUICKSCALE_ANALYTICS_ENABLED

    with pytest.raises(SystemCheckError, match="QUICKSCALE_ANALYTICS_ENABLED"):
        call_command("check")
    with pytest.raises(SystemCheckError, match="QUICKSCALE_ANALYTICS_ENABLED"):
        migrate.Command().check()
    with pytest.raises(SystemCheckError, match="QUICKSCALE_ANALYTICS_ENABLED"):
        runserver.Command().check()
