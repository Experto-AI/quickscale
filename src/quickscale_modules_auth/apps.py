"""Django app configuration for QuickScale auth module

SA11.7 — fail-hard auth signup-open default: raises
``ImproperlyConfigured`` at startup when ``ACCOUNT_ALLOW_REGISTRATION``
is not set, instead of silently defaulting to open registration.
"""

from importlib import import_module

from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class QuickscaleAuthConfig(AppConfig):
    """Configuration for QuickScale authentication module"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_auth"
    label = "quickscale_modules_auth"
    verbose_name = "QuickScale Authentication"

    def ready(self) -> None:
        # ---- SA11.7 — fail-hard auth signup-open default -----------------
        # Every generated project must explicitly set this; no silent
        # fallback that enables open registration.
        if not hasattr(settings, "ACCOUNT_ALLOW_REGISTRATION"):
            raise ImproperlyConfigured(
                "The ACCOUNT_ALLOW_REGISTRATION setting is required. "
                "Set it to True or False in your Django settings."
            )

        # Import signal handlers when app is ready
        import_module("quickscale_modules_auth.signals")
