"""Tests for notifications AppConfig startup behavior.

SA17.6 — fail-hard notifications module settings: require explicit
``QUICKSCALE_NOTIFICATIONS_ENABLED`` and
``QUICKSCALE_NOTIFICATIONS_PROVIDER`` at startup instead of silently
defaulting them.
"""

from importlib import import_module
from typing import Any

import pytest
from django.apps import apps
from django.core.exceptions import ImproperlyConfigured

from quickscale_modules_notifications.apps import QuickscaleNotificationsConfig
from quickscale_modules_notifications.services import NotificationSettingsSnapshot


def _build_config() -> QuickscaleNotificationsConfig:
    return QuickscaleNotificationsConfig(
        "quickscale_modules_notifications",
        import_module("quickscale_modules_notifications"),
    )


def test_app_config_is_registered() -> None:
    config = apps.get_app_config("quickscale_modules_notifications")

    assert config.name == "quickscale_modules_notifications"
    assert config.verbose_name == "QuickScale Notifications"


def test_app_config_ready_is_safe_to_call() -> None:
    _build_config().ready()


@pytest.mark.parametrize(
    "setting_name",
    [
        "QUICKSCALE_NOTIFICATIONS_ENABLED",
        "QUICKSCALE_NOTIFICATIONS_PROVIDER",
    ],
)
def test_ready_raises_when_required_notification_setting_missing(
    settings: Any,
    setting_name: str,
) -> None:
    delattr(settings, setting_name)

    with pytest.raises(ImproperlyConfigured, match=setting_name):
        _build_config().ready()


@pytest.mark.parametrize(
    "setting_name",
    [
        "QUICKSCALE_NOTIFICATIONS_ENABLED",
        "QUICKSCALE_NOTIFICATIONS_PROVIDER",
    ],
)
def test_snapshot_from_settings_raises_when_required_notification_setting_missing(
    settings: Any,
    setting_name: str,
) -> None:
    delattr(settings, setting_name)

    with pytest.raises(ImproperlyConfigured, match=setting_name):
        NotificationSettingsSnapshot.from_settings()


def test_snapshot_from_settings_uses_explicit_runtime_values(settings: Any) -> None:
    settings.QUICKSCALE_NOTIFICATIONS_ENABLED = False
    settings.QUICKSCALE_NOTIFICATIONS_PROVIDER = "smtp"

    snapshot = NotificationSettingsSnapshot.from_settings()

    assert snapshot.enabled is False
    assert snapshot.provider_name == "smtp"
