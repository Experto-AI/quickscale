"""Django app configuration for QuickScale billing.

SA17.2 — fail-hard billing enabled-flag setting: requires
``QUICKSCALE_BILLING_ENABLED`` in Django settings at startup
instead of silently defaulting to ``True``.
"""

from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class QuickscaleBillingConfig(AppConfig):
    """Configuration for the QuickScale billing module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_billing"
    label = "quickscale_modules_billing"
    verbose_name = "QuickScale Billing"

    def ready(self) -> None:
        # ---- SA17.2 — fail-hard billing enabled-flag setting -------------
        # Every generated project must explicitly set this; no silent
        # fallback that enables billing when the setting is absent.
        if not hasattr(settings, "QUICKSCALE_BILLING_ENABLED"):
            raise ImproperlyConfigured(
                "The QUICKSCALE_BILLING_ENABLED setting is required. "
                "Set it to True or False in your Django settings."
            )
