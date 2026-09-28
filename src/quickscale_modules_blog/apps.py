"""Django app configuration for QuickScale blog module"""

from django.apps import AppConfig

from quickscale_core.runtime import register_module_checks


class QuickscaleBlogConfig(AppConfig):
    """Configuration for QuickScale blog module"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_blog"
    label = "quickscale_blog"
    verbose_name = "QuickScale Blog"

    def ready(self) -> None:
        """Run the blog module startup checks through the shared helper."""
        # Late import: keep the app config importable while Django is still
        # populating the app registry.
        from quickscale_modules_blog.checks import (
            check_api_tokens,
            check_required_settings,
        )

        register_module_checks(self, [check_required_settings, check_api_tokens])
