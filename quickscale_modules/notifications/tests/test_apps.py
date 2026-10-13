"""Tests for notifications AppConfig startup behavior.

Fail-hard notifications module settings: require explicit
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
        "QUICKSCALE_NOTIFICATIONS_SENDER_NAME",
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
        "QUICKSCALE_NOTIFICATIONS_SENDER_NAME",
    ],
)
def test_snapshot_from_settings_reads_declared_settings_directly(
    settings: Any,
    setting_name: str,
) -> None:
    """Rule 3: a missing declared setting raises instead of defaulting."""
    delattr(settings, setting_name)

    with pytest.raises(AttributeError):
        NotificationSettingsSnapshot.from_settings()


def test_snapshot_from_settings_uses_explicit_runtime_values(settings: Any) -> None:
    settings.QUICKSCALE_NOTIFICATIONS_ENABLED = False
    settings.QUICKSCALE_NOTIFICATIONS_PROVIDER = "smtp"

    snapshot = NotificationSettingsSnapshot.from_settings()

    assert snapshot.enabled is False
    assert snapshot.provider_name == "smtp"


def test_ready_raises_when_provider_missing(settings: Any) -> None:
    """The declared provider setting is enforced by the generic settings check."""
    delattr(settings, "QUICKSCALE_NOTIFICATIONS_PROVIDER")

    with pytest.raises(
        ImproperlyConfigured,
        match="QUICKSCALE_NOTIFICATIONS_PROVIDER",
    ):
        _build_config().ready()


def test_vendor_secret_check_reports_empty_webhook_secret(settings: Any) -> None:
    """An enabled notifications runtime needs its webhook signing secret."""
    settings.QUICKSCALE_NOTIFICATIONS_ENABLED = True
    settings.QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET = ""

    messages = check_vendor_secrets()

    text = " ".join(message.msg for message in messages)
    assert "QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET" in text


@pytest.mark.parametrize(
    "secret",
    [
        "test-webhook-secret",  # no `whsec_` prefix; also invalid base64
        "YWFhYWFhYWFhYWFhYWFhYQ==",  # no `whsec_` prefix; valid base64
        "whsec_not base64!!",  # prefix present, remainder is not base64
        "whsec_",  # prefix present, decodes to an empty HMAC key
    ],
)
def test_vendor_secret_check_reports_malformed_webhook_secret(
    settings: Any, secret: str
) -> None:
    """E003 refuses a secret the webhook endpoint's contract does not accept."""
    settings.QUICKSCALE_NOTIFICATIONS_ENABLED = True
    settings.QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET = secret

    messages = check_vendor_secrets()

    assert [message.id for message in messages] == ["quickscale_notifications.E003"]
    assert "whsec_" in str(messages[0].msg)


def test_ready_refuses_unprefixed_webhook_secret(settings: Any) -> None:
    """The eager AppConfig.ready() pass refuses a valid-base64 unprefixed secret."""
    settings.QUICKSCALE_NOTIFICATIONS_ENABLED = True
    settings.QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET = "YWFhYWFhYWFhYWFhYWFhYQ=="

    with pytest.raises(ImproperlyConfigured, match="quickscale_notifications.E003"):
        _build_config().ready()


def test_vendor_secret_check_accepts_svix_shaped_webhook_secret(settings: Any) -> None:
    """A `whsec_` secret whose remainder is non-empty base64 passes the check."""
    settings.QUICKSCALE_NOTIFICATIONS_ENABLED = True
    settings.QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET = "whsec_YWFhYWFhYWFhYWFhYWFhYQ=="

    assert check_vendor_secrets() == []


def test_vendor_secret_check_reports_empty_resend_key_for_live_backend(
    settings: Any,
) -> None:
    """Live Resend delivery needs the Resend API key."""
    settings.QUICKSCALE_NOTIFICATIONS_ENABLED = True
    settings.EMAIL_BACKEND = "anymail.backends.resend.EmailBackend"
    settings.QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET = "whsec_test"
    settings.QUICKSCALE_NOTIFICATIONS_RESEND_API_KEY = ""

    messages = check_vendor_secrets()

    assert messages
    assert "RESEND_API_KEY" in messages[0].msg


def test_vendor_secret_check_passes_when_disabled(settings: Any) -> None:
    """A disabled notifications runtime needs no vendor secrets."""
    settings.QUICKSCALE_NOTIFICATIONS_ENABLED = False
    settings.QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET = ""

    assert check_vendor_secrets() == []


def test_vendor_secret_check_reports_missing_projected_settings(settings: Any) -> None:
    """An older managed wiring without the projected secret settings fails loudly."""
    settings.QUICKSCALE_NOTIFICATIONS_ENABLED = True
    del settings.QUICKSCALE_NOTIFICATIONS_RESEND_API_KEY
    del settings.QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET

    messages = check_vendor_secrets()

    assert len(messages) == 1
    assert "QUICKSCALE_NOTIFICATIONS_RESEND_API_KEY" in messages[0].msg
    assert "QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET" in messages[0].msg
    assert "quickscale apply" in messages[0].msg


@pytest.mark.django_db
def test_missing_setting_fails_check_migrate_and_runserver(settings: Any) -> None:
    """The registered check fails check, migrate, and runserver alike."""
    from django.core.management import call_command
    from django.core.management.base import SystemCheckError
    from django.core.management.commands import migrate, runserver

    delattr(settings, "QUICKSCALE_NOTIFICATIONS_ENABLED")

    with pytest.raises(SystemCheckError, match="QUICKSCALE_NOTIFICATIONS_ENABLED"):
        call_command("check")
    with pytest.raises(SystemCheckError, match="QUICKSCALE_NOTIFICATIONS_ENABLED"):
        migrate.Command().check()
    with pytest.raises(SystemCheckError, match="QUICKSCALE_NOTIFICATIONS_ENABLED"):
        runserver.Command().check()
