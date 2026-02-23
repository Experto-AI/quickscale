"""Django app configuration for QuickScale Forms module"""

from django.apps import AppConfig


class QuickscaleFormsConfig(AppConfig):
    """Configuration for QuickScale Forms module"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_forms"
    label = "quickscale_modules_forms"
    verbose_name = "QuickScale Forms"
