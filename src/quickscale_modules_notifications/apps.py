"""Django app configuration for QuickScale notifications."""

from django.apps import AppConfig


class QuickscaleNotificationsConfig(AppConfig):
    """Configuration for the QuickScale notifications module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_notifications"
    label = "quickscale_modules_notifications"
    verbose_name = "QuickScale Notifications"
