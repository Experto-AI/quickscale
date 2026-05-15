"""Django app configuration for QuickScale billing."""

from django.apps import AppConfig


class QuickscaleBillingConfig(AppConfig):
    """Configuration for the QuickScale billing module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_billing"
    label = "quickscale_modules_billing"
    verbose_name = "QuickScale Billing"
