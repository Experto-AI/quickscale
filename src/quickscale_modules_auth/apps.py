"""Django app configuration for QuickScale auth module.

Startup configuration is validated by rule 3's generic settings check,
registered through ``quickscale_core.runtime`` from ``ready()``.
"""

from importlib import import_module

from django.apps import AppConfig

from quickscale_core.runtime import register_module_settings_check
from quickscale_modules_orgs.removal import RemovalBoundary


class QuickscaleAuthConfig(AppConfig):
    """Configuration for QuickScale authentication module"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_auth"
    label = "quickscale_auth"
    verbose_name = "QuickScale Authentication"

    def removal_boundary_implementations(
        self,
    ) -> dict[RemovalBoundary, tuple[str, str, str]]:
        """Declare auth's account-deletion boundary implementation (rule 34).

        Auth owns the account-deletion boundary, so it declares where that
        implementation lives instead of orgs' discharge check naming it.
        """
        return {
            RemovalBoundary.ACCOUNT_DELETE: (
                self.name,
                "quickscale_modules_auth.views",
                "AccountDeleteView.form_valid",
            ),
        }

    def ready(self) -> None:
        register_module_settings_check(self, "auth")

        # Import signal receivers when app is ready
        import_module("quickscale_modules_auth.receivers")
