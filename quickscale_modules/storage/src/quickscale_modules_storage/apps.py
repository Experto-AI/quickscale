"""Django app configuration for QuickScale storage module."""

from django.apps import AppConfig

from quickscale_core.runtime import register_module_checks


class QuickscaleStorageConfig(AppConfig):
    """Configuration for the QuickScale storage module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_storage"
    label = "quickscale_storage"
    verbose_name = "QuickScale Storage"

    def ready(self) -> None:
        # Late import: keep the app config importable while Django is still
        # populating the app registry.
        from quickscale_modules_storage.checks import check_vendor_secrets

        register_module_checks(self, [check_vendor_secrets])
