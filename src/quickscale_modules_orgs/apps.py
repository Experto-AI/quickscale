"""Django app configuration for QuickScale organizations."""

from django.apps import AppConfig


class QuickscaleOrgsConfig(AppConfig):
    """Configuration for the QuickScale organizations module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_orgs"
    label = "quickscale_modules_orgs"
    verbose_name = "QuickScale Organizations"
