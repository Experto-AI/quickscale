"""Startup checks for the QuickScale billing module.

Rule 10: these functions are run from ``AppConfig.ready()`` through
``quickscale_core.runtime.register_module_checks``, which runs them eagerly
(so ``runserver``, ``migrate``, and a WSGI server all refuse to start) and
also registers them as ``quickscale_billing`` system checks.
"""

from __future__ import annotations

from django.conf import settings
from django.core.checks import CheckMessage, Error

from quickscale_modules_billing.services import BillingSettingsSnapshot


def check_billing_settings(
    app_configs: object = None,
    **kwargs: object,
) -> list[CheckMessage]:
    """Fail startup on invalid billing configuration.

    Invalid configuration is a missing ``QUICKSCALE_BILLING_ENABLED`` flag, or
    an enabled billing module whose Stripe secret key or webhook signing
    secret resolves empty.  The module's manifest default enables billing, so
    an operator who does not use Stripe switches billing off explicitly.
    """
    messages: list[CheckMessage] = []
    if not hasattr(settings, "QUICKSCALE_BILLING_ENABLED"):
        messages.append(
            Error(
                "The QUICKSCALE_BILLING_ENABLED setting is required. "
                "Set it to True or False in your Django settings.",
                id="quickscale_billing.E001",
            )
        )
        return messages

    snapshot = BillingSettingsSnapshot.from_settings()
    if not snapshot.enabled:
        return messages

    if not snapshot.resolve_secret_key():
        messages.append(
            Error(
                "Billing is enabled but the Stripe secret key environment "
                f"variable {snapshot.secret_key_env_var!r} named by "
                "QUICKSCALE_BILLING_SECRET_KEY_ENV_VAR is empty. Set the key "
                "or set QUICKSCALE_BILLING_ENABLED=False.",
                id="quickscale_billing.E002",
            )
        )
    if not snapshot.resolve_webhook_secret():
        messages.append(
            Error(
                "Billing is enabled but the Stripe webhook signing secret "
                f"environment variable {snapshot.webhook_secret_env_var!r} "
                "named by QUICKSCALE_BILLING_WEBHOOK_SECRET_ENV_VAR is empty. "
                "Set the secret or set QUICKSCALE_BILLING_ENABLED=False.",
                id="quickscale_billing.E003",
            )
        )
    return messages
