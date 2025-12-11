"""Django app configuration for QuickScale CRM module"""

from django.apps import AppConfig


class QuickscaleCrmConfig(AppConfig):
    """Configuration for QuickScale CRM module"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_crm"
    label = "quickscale_modules_crm"
    verbose_name = "QuickScale CRM"
