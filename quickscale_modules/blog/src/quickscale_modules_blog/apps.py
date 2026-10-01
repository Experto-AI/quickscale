"""Django app configuration for QuickScale blog module"""

from django.apps import AppConfig

from quickscale_core.runtime import (
    register_module_checks,
    register_module_settings_check,
)


class QuickscaleBlogConfig(AppConfig):
    """Configuration for QuickScale blog module"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_blog"
    label = "quickscale_blog"
    verbose_name = "QuickScale Blog"

    def ready(self) -> None:
        """Run the blog startup checks through the shared helpers."""
        # Late import: keep the app config importable while Django is still
        # populating the app registry.
        from quickscale_modules_blog.checks import RETIRED_SETTINGS, check_media_url

        register_module_checks(self, [check_media_url])
        register_module_settings_check(self, "blog", retired_settings=RETIRED_SETTINGS)
