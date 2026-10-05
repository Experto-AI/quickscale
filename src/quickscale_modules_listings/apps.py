"""Django app configuration for QuickScale listings module"""

from django.apps import AppConfig

from quickscale_core.runtime import (
    PersonalDataExclusion,
    register_module_settings_check,
)


class QuickscaleListingsConfig(AppConfig):
    """Configuration for QuickScale listings module"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_listings"
    label = "quickscale_listings"
    verbose_name = "QuickScale Listings"

    def personal_data_declarations(
        self,
    ) -> tuple[PersonalDataExclusion, ...]:
        """Declare the personal-data rows listings owns (rule 49).

        Listings carry no user link of their own; the one candidate field is
        the organization-owned listing image, excluded with its reason.
        """
        return (
            PersonalDataExclusion(
                app_label=self.label,
                model_name="Listing",
                field_name="featured_image",
                reason="Organization-owned listing image; retained as-is.",
            ),
        )

    def ready(self) -> None:
        """Register rule 3's generic settings check for this module."""
        from quickscale_modules_listings.checks import RETIRED_SETTINGS

        register_module_settings_check(
            self, "listings", retired_settings=RETIRED_SETTINGS
        )
