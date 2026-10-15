"""Startup checks for the QuickScale notifications module.

Rule 10: these functions are run from ``AppConfig.ready()`` through
``quickscale_core.runtime.register_module_checks``, so a failure refuses
``runserver``, ``migrate``, and ``manage.py check`` alike.  Rule 26 (inbound
webhooks) and rule 35 (secrets) settle what a missing or unusable secret does:
it fails startup, while an unreachable vendor at send time stays a runtime
concern.
"""

from __future__ import annotations

from django.conf import settings
from django.core.checks import CheckMessage, Error

from quickscale_core.runtime import (
    module_settings_are_supplied,
    projected_setting_names,
)
from quickscale_modules_notifications._webhooks import (
    _WH_SEC_PREFIX,
    _decode_svix_secret,
)
from quickscale_modules_notifications.exceptions import (
    NotificationWebhookSignatureError,
)
from quickscale_modules_notifications.services import NotificationSettingsSnapshot

# The projected settings apply writes beyond the declared options — the
# `_ENV_VAR` secret settings (rule 35) and the manifest's derived settings — are
# read from the module's manifest projection (rule 6), so a rename lands once,
# in `module.yml`.  They are not manifest options, so the generic settings check
# does not report them; a missing one is reported below instead of raising
# while resolving.

#: E003's wording for a secret that is neither empty nor a usable Svix value.
_SVIX_SHAPE_PROBLEM = (
    "is not a valid Svix signing secret: expected a `whsec_` prefix followed by base64"
)


def _svix_secret_problem(secret: str) -> str:
    """Return why E003 refuses *secret*, or an empty string when it conforms.

    The endpoint's own decoder is the authority for the key bytes, so a value
    it cannot decode fails startup instead of failing every webhook at
    request time.  The documented Resend form is always ``whsec_``-prefixed,
    which the decoder alone does not require.
    """
    if not secret:
        return "is empty"
    if not secret.startswith(_WH_SEC_PREFIX):
        return _SVIX_SHAPE_PROBLEM
    try:
        _decode_svix_secret(secret)
    except NotificationWebhookSignatureError:
        return _SVIX_SHAPE_PROBLEM
    return ""


def check_vendor_secrets(
    _app_configs: object = None,
    **kwargs: object,
) -> list[CheckMessage]:
    """Fail startup when a secret a switched-on notifications feature needs is unusable.

    With notifications enabled the webhook endpoint is mounted, so its
    signing secret is required (rule 26) and must be one the endpoint can
    decode: a ``whsec_`` prefix and a non-empty base64 key.  The Resend API
    key is required only when the active email backend is the live Resend
    backend.  The declared settings are validated by the generic settings
    check registered first.
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
        name
        for name in projected_setting_names("notifications")
        if not hasattr(settings, name)
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
    webhook_problem = _svix_secret_problem(snapshot.resolve_webhook_secret())
    if webhook_problem:
        messages.append(
            Error(
                "Notifications is enabled but the webhook signing secret "
                f"environment variable {snapshot.webhook_secret_env_var!r} "
                "named by QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR "
                f"{webhook_problem}. Set the secret or set "
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
