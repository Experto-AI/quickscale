"""Django app configuration for QuickScale auth module"""

from importlib import import_module

from django.apps import AppConfig


class QuickscaleAuthConfig(AppConfig):
    """Configuration for QuickScale authentication module"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_auth"
    label = "quickscale_modules_auth"
    verbose_name = "QuickScale Authentication"

    def ready(self) -> None:
        """Import signal handlers when app is ready"""
        import_module("quickscale_modules_auth.signals")
