"""Django app configuration for QuickScale backups module."""

from django.apps import AppConfig


class QuickscaleBackupsConfig(AppConfig):
    """Configuration for the QuickScale backups module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_backups"
    label = "quickscale_modules_backups"
    verbose_name = "QuickScale Backups"
