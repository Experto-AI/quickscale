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

from quickscale_core.runtime import module_settings_are_supplied
from quickscale_modules_notifications.services import NotificationSettingsSnapshot

#: The projected secret settings apply writes from the `_ENV_VAR` options
#: (rule 35).  They are not manifest options, so the generic settings check
#: does not report them; a missing one is reported here instead of raising
#: while resolving.
_PROJECTED_SECRETS = (
    "QUICKSCALE_NOTIFICATIONS_RESEND_API_KEY",
    "QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET",
)


def check_vendor_secrets(
    _app_configs: object = None,
    **kwargs: object,
) -> list[CheckMessage]:
    """Fail startup when a secret a switched-on notifications feature needs is empty.

    With notifications enabled the webhook endpoint is mounted, so its
    signing secret is required (rule 26).  The Resend API key is required only
    when the active email backend is the live Resend backend.  The declared
    settings are validated by the generic settings check registered first.
    """
    if not module_settings_are_supplied("notifications"):
        # The generic settings check names the missing declared setting;
        # Django runs every registered check independently, so this check
        # stays silent until the project is fully applied.
        return []

    snapshot = NotificationSettingsSnapshot.from_settings()
    if not snapshot.enabled:
        return []

    missing_projected = [
        name for name in _PROJECTED_SECRETS if not hasattr(settings, name)
    ]
    if missing_projected:
        return [
            Error(
                f"{', '.join(missing_projected)} not set. "
                "Run `quickscale apply` to regenerate the managed settings.",
                id="quickscale_notifications.E001",
            )
        ]

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
