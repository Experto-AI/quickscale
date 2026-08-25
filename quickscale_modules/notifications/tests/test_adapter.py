"""Focused tests for the notifications manifest adapter."""

from __future__ import annotations

import pytest

from quickscale_modules_notifications.adapter import (
    _notifications_derived_settings,
    _notifications_manifest_adapter,
    get_manifest_adapter,
)


def test_get_manifest_adapter_returns_callable() -> None:
    assert get_manifest_adapter() is _notifications_manifest_adapter


def test_default_delivery_is_console_safe() -> None:
    spec = _notifications_manifest_adapter({})

    assert "anymail" not in spec.apps
    assert spec.settings["EMAIL_BACKEND"] == (
        "django.core.mail.backends.console.EmailBackend"
    )
    assert spec.settings["DEFAULT_FROM_EMAIL"] == "noreply@example.com"
    assert ("", "quickscale_modules_notifications.urls") in spec.url_includes


def test_live_resend_delivery_adds_anymail_and_email_settings() -> None:
    spec = _notifications_manifest_adapter(
        {
            "sender_name": "Ops",
            "sender_email": "ops@example.com",
            "resend_domain": "mg.example.com",
            "resend_api_key_env_var": "OPS_RESEND_API_KEY",
        }
    )

    assert spec.apps[0] == "anymail"
    assert spec.settings["EMAIL_BACKEND"] == "anymail.backends.resend.EmailBackend"
    assert spec.settings["DEFAULT_FROM_EMAIL"] == "ops@example.com"
    assert spec.settings["SERVER_EMAIL"] == "ops@example.com"


def test_disabled_notifications_leave_email_backend_unmanaged() -> None:
    spec = _notifications_manifest_adapter({"enabled": False})

    assert "quickscale_modules_notifications" in spec.apps
    assert "EMAIL_BACKEND" not in spec.settings
    assert "DEFAULT_FROM_EMAIL" not in spec.settings


def test_required_derived_reads_fail_hard() -> None:
    with pytest.raises(KeyError, match="enabled"):
        _notifications_derived_settings({})
