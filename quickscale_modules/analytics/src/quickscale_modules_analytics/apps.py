"""Django app configuration for QuickScale analytics.

SA17.2 — fail-hard analytics enabled-flag setting: requires
``QUICKSCALE_ANALYTICS_ENABLED`` in Django settings at startup
instead of silently defaulting to ``True``.
"""

from __future__ import annotations

import logging

from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from quickscale_modules_analytics.services import configure_analytics_client

logger = logging.getLogger(__name__)


class QuickscaleAnalyticsConfig(AppConfig):
    """Configuration for the QuickScale analytics module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_analytics"
    label = "quickscale_modules_analytics"
    verbose_name = "QuickScale Analytics"

    def ready(self) -> None:
        # ---- SA17.2 — fail-hard analytics enabled-flag setting -------------
        # Every generated project must explicitly set this; no silent
        # fallback that enables analytics when the setting is absent.
        if not hasattr(settings, "QUICKSCALE_ANALYTICS_ENABLED"):
            raise ImproperlyConfigured(
                "The QUICKSCALE_ANALYTICS_ENABLED setting is required. "
                "Set it to True or False in your Django settings."
            )

        # Initialize analytics safely without blocking Django startup.
        try:
            configure_analytics_client()
        except Exception:
            logger.warning(
                "QuickScale analytics failed to initialize during app startup.",
                exc_info=True,
            )
