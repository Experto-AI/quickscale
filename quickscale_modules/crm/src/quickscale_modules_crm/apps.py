"""Django app configuration for QuickScale CRM module.

Startup configuration is validated by rule 3's generic settings check,
registered through ``quickscale_core.runtime`` from ``ready()``.
"""

from django.apps import AppConfig

from quickscale_core.runtime import register_module_settings_check


class QuickscaleCrmConfig(AppConfig):
    """Configuration for QuickScale CRM module"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_crm"
    label = "quickscale_crm"
    verbose_name = "QuickScale CRM"

    #: Display prefix for the module's models in organization-removal summaries.
    removal_label_prefix = "CRM"

    def ready(self) -> None:
        # ---- SA7.1 — organization_created signal receiver -----------------
        # Import receivers to connect the seed_crm_default_stages_on_org_created
        # receiver.  The @receiver decorator runs at import time, so importing
        # the module is sufficient.
        import quickscale_modules_crm.receivers  # noqa: F401

        from quickscale_modules_crm.checks import RETIRED_SETTINGS

        register_module_settings_check(self, "crm", retired_settings=RETIRED_SETTINGS)
