"""Django app configuration for QuickScale social."""

from django.apps import AppConfig


class QuickscaleSocialConfig(AppConfig):
    """Configuration for the QuickScale social module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_social"
    label = "quickscale_modules_social"
    verbose_name = "QuickScale Social"
