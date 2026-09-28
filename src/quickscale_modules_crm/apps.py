"""Django app configuration for QuickScale CRM module.

Startup configuration is validated by
:func:`quickscale_modules_crm.checks.check_required_settings`, run through
``quickscale_core.runtime.register_module_checks`` from ``ready()``.
"""

from django.apps import AppConfig

from quickscale_core.runtime import register_module_checks


class QuickscaleCrmConfig(AppConfig):
    """Configuration for QuickScale CRM module"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_crm"
    label = "quickscale_crm"
    verbose_name = "QuickScale CRM"

    def ready(self) -> None:
        # ---- SA7.1 — organization_created signal receiver -----------------
        # Import receivers to connect the seed_crm_default_stages_on_org_created
        # receiver.  The @receiver decorator runs at import time, so importing
        # the module is sufficient.
        import quickscale_modules_crm.receivers  # noqa: F401

        # Late import: keep the app config importable while Django is still
        # populating the app registry.
        from quickscale_modules_crm.checks import check_required_settings

        register_module_checks(self, [check_required_settings])
