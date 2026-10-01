"""Django app configuration for QuickScale listings module"""

from django.apps import AppConfig

from quickscale_core.runtime import register_module_settings_check


class QuickscaleListingsConfig(AppConfig):
    """Configuration for QuickScale listings module"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_listings"
    label = "quickscale_listings"
    verbose_name = "QuickScale Listings"

    def ready(self) -> None:
        """Register rule 3's generic settings check for this module."""
        from quickscale_modules_listings.checks import RETIRED_SETTINGS

        register_module_settings_check(
            self, "listings", retired_settings=RETIRED_SETTINGS
        )
