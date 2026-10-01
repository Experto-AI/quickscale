"""Django app configuration for QuickScale Forms module.

Startup configuration is validated by rule 3's generic settings check,
registered through ``quickscale_core.runtime`` from ``ready()``.
"""

from django.apps import AppConfig

from quickscale_core.runtime import register_module_settings_check


class QuickscaleFormsConfig(AppConfig):
    """Configuration for QuickScale Forms module"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_forms"
    label = "quickscale_forms"
    verbose_name = "QuickScale Forms"

    def ready(self) -> None:
        from quickscale_modules_forms.checks import RETIRED_SETTINGS

        register_module_settings_check(self, "forms", retired_settings=RETIRED_SETTINGS)
