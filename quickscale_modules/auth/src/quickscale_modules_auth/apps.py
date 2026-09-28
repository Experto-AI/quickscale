"""Django app configuration for QuickScale auth module.

Startup configuration is validated by
:func:`quickscale_modules_auth.checks.check_required_settings`, run through
``quickscale_core.runtime.register_module_checks`` from ``ready()``.
"""

from importlib import import_module

from django.apps import AppConfig

from quickscale_core.runtime import register_module_checks


class QuickscaleAuthConfig(AppConfig):
    """Configuration for QuickScale authentication module"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_auth"
    label = "quickscale_auth"
    verbose_name = "QuickScale Authentication"

    def ready(self) -> None:
        # Late import: keep the app config importable while Django is still
        # populating the app registry.
        from quickscale_modules_auth.checks import check_required_settings

        register_module_checks(self, [check_required_settings])

        # Import signal receivers when app is ready
        import_module("quickscale_modules_auth.receivers")
