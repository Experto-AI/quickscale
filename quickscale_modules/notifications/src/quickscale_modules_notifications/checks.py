"""Startup checks for the QuickScale notifications module.

Rule 10: these functions are run from ``AppConfig.ready()`` through
``quickscale_core.runtime.register_module_checks``, so a failure refuses
``runserver``, ``migrate``, and ``manage.py check`` alike.  Rule 26 (inbound
webhooks) and rule 35 (secrets) settle what a missing secret does: it fails
startup, while an unreachable vendor at send time stays a runtime concern.
"""

from __future__ import annotations

from django.conf import settings
from django.core.checks import CheckMessage, Error

from quickscale_modules_notifications.services import NotificationSettingsSnapshot


def check_required_settings(
    app_configs: object = None,
    **kwargs: object,
) -> list[CheckMessage]:
    """Fail startup when a required notifications runtime setting is absent."""
    messages: list[CheckMessage] = []
    if not hasattr(settings, "QUICKSCALE_NOTIFICATIONS_ENABLED"):
        messages.append(
            Error(
                "The QUICKSCALE_NOTIFICATIONS_ENABLED setting is required. "
                "Set it to True or False in your Django settings.",
                id="quickscale_notifications.E001",
            )
        )
    if not hasattr(settings, "QUICKSCALE_NOTIFICATIONS_PROVIDER"):
        messages.append(
            Error(
                "The QUICKSCALE_NOTIFICATIONS_PROVIDER setting is required. "
                "Set it to the configured provider name in your Django settings.",
                id="quickscale_notifications.E002",
            )
        )
    return messages


def check_vendor_secrets(
    app_configs: object = None,
    **kwargs: object,
) -> list[CheckMessage]:
    """Fail startup when a secret a switched-on notifications feature needs is empty.

    With notifications enabled the webhook endpoint is mounted, so its
    signing secret is required (rule 26).  The Resend API key is required only
    when the active email backend is the live Resend backend.
    """
    if not (
        hasattr(settings, "QUICKSCALE_NOTIFICATIONS_ENABLED")
        and hasattr(settings, "QUICKSCALE_NOTIFICATIONS_PROVIDER")
    ):
        # check_required_settings reports the missing setting itself.
        return []

    snapshot = NotificationSettingsSnapshot.from_settings()
    if not snapshot.enabled:
        return []

    messages: list[CheckMessage] = []
    if not snapshot.resolve_webhook_secret():
        messages.append(
            Error(
                "Notifications is enabled but the webhook signing secret "
                f"environment variable {snapshot.webhook_secret_env_var!r} "
                "named by QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR is "
                "empty. Set the secret or set "
                "QUICKSCALE_NOTIFICATIONS_ENABLED=False.",
                id="quickscale_notifications.E003",
            )
        )
    if snapshot.live_delivery_enabled() and not snapshot.resolve_resend_api_key():
        messages.append(
            Error(
                "Notifications is enabled with the live Resend email backend "
                "but the Resend API key environment variable "
                f"{snapshot.resend_api_key_env_var!r} named by "
                "QUICKSCALE_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR is empty. "
                "Set the key or change EMAIL_BACKEND.",
                id="quickscale_notifications.E004",
            )
        )
    return messages
