"""Django app configuration for QuickScale listings module"""

from django.apps import AppConfig


class QuickscaleListingsConfig(AppConfig):
    """Configuration for QuickScale listings module"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_listings"
    label = "quickscale_modules_listings"
    verbose_name = "QuickScale Listings"

    def ready(self) -> None:
        """Import signal handlers when app is ready"""
        # No signals needed for listings module yet
        pass
