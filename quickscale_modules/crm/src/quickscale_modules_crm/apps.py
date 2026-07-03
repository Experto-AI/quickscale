"""Django app configuration for QuickScale CRM module"""

from django.apps import AppConfig


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
