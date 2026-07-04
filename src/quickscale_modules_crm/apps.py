"""Django app configuration for QuickScale CRM module.

SA17.3 — fail-hard CRM API-enable flag and page-size settings:
requires ``CRM_ENABLE_API`` in Django settings at startup instead of
silently defaulting to ``True``.
"""

from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class QuickscaleCrmConfig(AppConfig):
    """Configuration for QuickScale CRM module"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_crm"
    label = "quickscale_modules_crm"
    verbose_name = "QuickScale CRM"

    def ready(self) -> None:
        # ---- SA7.1 — organization_created signal receiver -----------------
        # Import signals to connect the seed_crm_default_stages_on_org_created
        # receiver.  The @receiver decorator runs at import time, so importing
        # the module is sufficient.
        import quickscale_modules_crm.signals  # noqa: F401

        # ---- SA17.3 — fail-hard CRM API-enable setting --------------------
        # Every generated project must explicitly set this; no silent
        # fallback that enables the CRM API when the setting is absent.
        if not hasattr(settings, "CRM_ENABLE_API"):
            raise ImproperlyConfigured(
                "The CRM_ENABLE_API setting is required. "
                "Set it to True or False in your Django settings."
            )
