"""Django app configuration for QuickScale notifications."""

from django.apps import AppConfig

from quickscale_core.runtime import register_module_checks


class QuickscaleNotificationsConfig(AppConfig):
    """Configuration for the QuickScale notifications module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_notifications"
    label = "quickscale_notifications"
    verbose_name = "QuickScale Notifications"

    def ready(self) -> None:
        # Late import: checks.py reads the notifications settings snapshot,
        # which touches models, so it must load after the app registry is ready.
        from quickscale_modules_notifications.checks import (
            check_required_settings,
            check_vendor_secrets,
        )

        register_module_checks(self, [check_required_settings, check_vendor_secrets])
