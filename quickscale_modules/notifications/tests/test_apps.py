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
from quickscale_modules_notifications.checks import check_vendor_secrets
from quickscale_modules_notifications.services import NotificationSettingsSnapshot


def _build_config() -> QuickscaleNotificationsConfig:
    return QuickscaleNotificationsConfig(
        "quickscale_modules_notifications",
        import_module("quickscale_modules_notifications"),
    )


def test_app_config_is_registered() -> None:
    config = apps.get_app_config("quickscale_notifications")

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


def test_vendor_secret_check_reports_empty_webhook_secret(
    settings: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An enabled notifications runtime needs its webhook signing secret."""
    settings.QUICKSCALE_NOTIFICATIONS_ENABLED = True
    monkeypatch.delenv("QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET", raising=False)

    messages = check_vendor_secrets()

    text = " ".join(message.msg for message in messages)
    assert "QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET" in text


def test_vendor_secret_check_reports_empty_resend_key_for_live_backend(
    settings: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Live Resend delivery needs the Resend API key."""
    settings.QUICKSCALE_NOTIFICATIONS_ENABLED = True
    settings.EMAIL_BACKEND = "anymail.backends.resend.EmailBackend"
    monkeypatch.setenv("QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.delenv("RESEND_API_KEY", raising=False)

    messages = check_vendor_secrets()

    assert messages
    assert "RESEND_API_KEY" in messages[0].msg


def test_vendor_secret_check_passes_when_disabled(
    settings: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A disabled notifications runtime needs no vendor secrets."""
    settings.QUICKSCALE_NOTIFICATIONS_ENABLED = False
    monkeypatch.delenv("QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET", raising=False)

    assert check_vendor_secrets() == []


@pytest.mark.django_db
def test_missing_setting_fails_check_migrate_and_runserver(settings: Any) -> None:
    """The registered check fails check, migrate, and runserver alike."""
    from django.core.management import call_command
    from django.core.management.base import SystemCheckError
    from django.core.management.commands import migrate, runserver

    delattr(settings, "QUICKSCALE_NOTIFICATIONS_PROVIDER")

    with pytest.raises(SystemCheckError, match="QUICKSCALE_NOTIFICATIONS_PROVIDER"):
        call_command("check")
    with pytest.raises(SystemCheckError, match="QUICKSCALE_NOTIFICATIONS_PROVIDER"):
        migrate.Command().check()
    with pytest.raises(SystemCheckError, match="QUICKSCALE_NOTIFICATIONS_PROVIDER"):
        runserver.Command().check()
