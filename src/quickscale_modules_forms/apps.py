"""Django app configuration for QuickScale Forms module.

Startup configuration is validated by
:func:`quickscale_modules_forms.checks.check_required_settings`, run through
``quickscale_core.runtime.register_module_checks`` from ``ready()``.
"""

from django.apps import AppConfig

from quickscale_core.runtime import register_module_checks


class QuickscaleFormsConfig(AppConfig):
    """Configuration for QuickScale Forms module"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_forms"
    label = "quickscale_forms"
    verbose_name = "QuickScale Forms"

    def ready(self) -> None:
        # Late import: keep the app config importable while Django is still
        # populating the app registry.
        from quickscale_modules_forms.checks import check_required_settings

        register_module_checks(self, [check_required_settings])
