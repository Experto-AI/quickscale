"""Startup checks for the QuickScale billing module.

Rule 10: these functions are run from ``AppConfig.ready()`` through
``quickscale_core.runtime.register_module_checks``, which runs them eagerly
(so ``runserver``, ``migrate``, and a WSGI server all refuse to start) and
also registers them as ``quickscale_billing`` system checks.
"""

from __future__ import annotations

from django.conf import settings
from django.core.checks import CheckMessage, Error

from quickscale_core.runtime import module_settings_are_supplied
from quickscale_modules_billing.services import BillingSettingsSnapshot

#: The projected secret settings apply writes from the `_ENV_VAR` options
#: (rule 35).  They are not manifest options, so the generic settings check
#: does not report them; a missing one is reported here instead of raising
#: while resolving.
_PROJECTED_SECRETS = (
    "QUICKSCALE_BILLING_PUBLISHABLE_KEY",
    "QUICKSCALE_BILLING_SECRET_KEY",
    "QUICKSCALE_BILLING_WEBHOOK_SECRET",
)


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

    missing_projected = [
        name for name in _PROJECTED_SECRETS if not hasattr(settings, name)
    ]
    if missing_projected:
        return [
            Error(
                f"{', '.join(missing_projected)} not set. "
                "Run `quickscale apply` to regenerate the managed settings.",
                id="quickscale_billing.E001",
            )
        ]

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
