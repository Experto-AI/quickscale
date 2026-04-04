"""Django app configuration for QuickScale analytics."""

from __future__ import annotations

import logging

from django.apps import AppConfig

from quickscale_modules_analytics.services import configure_analytics_client

logger = logging.getLogger(__name__)


class QuickscaleAnalyticsConfig(AppConfig):
    """Configuration for the QuickScale analytics module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_analytics"
    label = "quickscale_modules_analytics"
    verbose_name = "QuickScale Analytics"

    def ready(self) -> None:
        """Initialize analytics safely without blocking Django startup."""
        try:
            configure_analytics_client()
        except Exception:
            logger.warning(
                "QuickScale analytics failed to initialize during app startup.",
                exc_info=True,
            )
