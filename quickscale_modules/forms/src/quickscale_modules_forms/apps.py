"""Django app configuration for QuickScale Forms module.

SA17.4 — fail-hard forms settings: requires ``FORMS_SUBMISSIONS_API``,
``FORMS_RATE_LIMIT``, and ``FORMS_SPAM_PROTECTION`` in Django settings at
startup instead of silently defaulting them.
"""

from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class QuickscaleFormsConfig(AppConfig):
    """Configuration for QuickScale Forms module"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_forms"
    label = "quickscale_modules_forms"
    verbose_name = "QuickScale Forms"

    def ready(self) -> None:
        # ---- SA17.4 — fail-hard forms settings --------------------------
        # Every generated project must explicitly set these; no silent
        # fallback that defaults them when absent.
        if not hasattr(settings, "FORMS_SUBMISSIONS_API"):
            raise ImproperlyConfigured(
                "The FORMS_SUBMISSIONS_API setting is required. "
                "Set it to True or False in your Django settings."
            )
        if not hasattr(settings, "FORMS_RATE_LIMIT"):
            raise ImproperlyConfigured(
                "The FORMS_RATE_LIMIT setting is required. "
                "Set it to a throttle rate string (e.g. '5/hour') in your Django settings."
            )
        if not hasattr(settings, "FORMS_SPAM_PROTECTION"):
            raise ImproperlyConfigured(
                "The FORMS_SPAM_PROTECTION setting is required. "
                "Set it to True or False in your Django settings."
            )
