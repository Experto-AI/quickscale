"""Django app configuration for QuickScale notifications.

SA17.6 — fail-hard notifications module settings: requires
``QUICKSCALE_NOTIFICATIONS_ENABLED`` and
``QUICKSCALE_NOTIFICATIONS_PROVIDER`` in Django settings at startup
instead of silently defaulting them.
"""

from django.apps import AppConfig


class QuickscaleNotificationsConfig(AppConfig):
    """Configuration for the QuickScale notifications module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_notifications"
    label = "quickscale_modules_notifications"
    verbose_name = "QuickScale Notifications"

    def ready(self) -> None:
        """Validate required notification runtime settings at startup."""
        from quickscale_modules_notifications.services import (
            validate_required_notification_settings,
        )

        validate_required_notification_settings()
