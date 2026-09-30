"""Django app configuration for QuickScale social."""

from collections.abc import Callable

from django.apps import AppConfig

from quickscale_core.runtime import register_module_settings_check


class QuickscaleSocialConfig(AppConfig):
    """Configuration for the QuickScale social module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_social"
    label = "quickscale_social"
    verbose_name = "QuickScale Social"

    def organization_cache_keys(
        self,
    ) -> tuple[Callable[[object], tuple[str, ...]], ...]:
        """Declare the module's organization-scoped cache keys (rule 4).

        The orgs removal boundary collects this capability and clears every
        declared key, so social owns its cache-key shapes and the boundary
        imports no part of social.
        """
        from quickscale_modules_social import services

        return (services.organization_cache_keys,)

    def ready(self) -> None:
        """Register rule 3's generic settings check for this module."""
        register_module_settings_check(self, "social")
