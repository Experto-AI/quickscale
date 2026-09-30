"""Django app configuration for QuickScale social."""

from django.apps import AppConfig

from quickscale_core.runtime import register_module_settings_check


class QuickscaleSocialConfig(AppConfig):
    """Configuration for the QuickScale social module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_social"
    label = "quickscale_social"
    verbose_name = "QuickScale Social"

    def ready(self) -> None:
        """Register rule 3's generic settings check for this module."""
        register_module_settings_check(self, "social")
