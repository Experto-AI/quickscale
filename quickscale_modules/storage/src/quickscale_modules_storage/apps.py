"""Django app configuration for QuickScale storage module."""

from django.apps import AppConfig


class QuickscaleStorageConfig(AppConfig):
    """Configuration for QuickScale storage module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_storage"
    label = "quickscale_modules_storage"
    verbose_name = "QuickScale Storage"
