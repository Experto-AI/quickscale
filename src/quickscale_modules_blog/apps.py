"""Django app configuration for QuickScale blog module"""

from django.apps import AppConfig


class QuickscaleBlogConfig(AppConfig):
    """Configuration for QuickScale blog module"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_blog"
    label = "quickscale_modules_blog"
    verbose_name = "QuickScale Blog"

    def ready(self) -> None:
        """Import signal handlers when app is ready"""
        # No signals needed for blog module yet
        pass
