"""Startup checks for the QuickScale billing module.

Rule 10: these functions are run from ``AppConfig.ready()`` through
``quickscale_core.runtime.register_module_checks``, which runs them eagerly
(so ``runserver``, ``migrate``, and a WSGI server all refuse to start) and
also registers them as ``quickscale_billing`` system checks.
"""

from __future__ import annotations

from django.core.checks import CheckMessage, Error

from quickscale_core.runtime import module_settings_are_supplied
from quickscale_modules_billing.services import BillingSettingsSnapshot

# The projected settings apply writes beyond the declared options — the
# `_ENV_VAR` secret settings (rule 35) and the manifest's derived settings —
# are validated by the generic settings check (rule 10), which names a
# missing one before this check reads it; a module check does not re-test a
# projected setting's presence.


def check_billing_settings(
    _app_configs: object = None,
    **kwargs: object,
) -> list[CheckMessage]:
    """Fail startup on an invalid resolved billing runtime.

    Invalid configuration is an enabled billing module whose Stripe secret
    key or webhook signing secret resolves empty.  The module's manifest
    default enables billing, so an operator who does not use Stripe switches
    billing off explicitly.  The declared options themselves are validated by
    the generic settings check registered first.
    """
    if not module_settings_are_supplied("billing"):
        # The generic settings check names the missing declared setting;
        # Django runs every registered check independently, so this check
        # stays silent until the project is fully applied.
        return []

    messages: list[CheckMessage] = []
    snapshot = BillingSettingsSnapshot.from_settings()
    if not snapshot.enabled:
        return messages

    if not snapshot.resolve_secret_key():
        messages.append(
            Error(
                "Billing is enabled but the applied Stripe secret key setting "
                "QUICKSCALE_BILLING_SECRET_KEY is empty (it renders the "
                f"environment variable {snapshot.secret_key_env_var!r} named "
                "by QUICKSCALE_BILLING_SECRET_KEY_ENV_VAR). Set the key or set "
                "QUICKSCALE_BILLING_ENABLED=False.",
                id="quickscale_billing.E002",
            )
        )
    if not snapshot.resolve_webhook_secret():
        messages.append(
            Error(
                "Billing is enabled but the applied Stripe webhook signing "
                "secret setting QUICKSCALE_BILLING_WEBHOOK_SECRET is empty (it "
                f"renders the environment variable "
                f"{snapshot.webhook_secret_env_var!r} named by "
                "QUICKSCALE_BILLING_WEBHOOK_SECRET_ENV_VAR). Set the secret or "
                "set QUICKSCALE_BILLING_ENABLED=False.",
                id="quickscale_billing.E003",
            )
        )
    return messages
