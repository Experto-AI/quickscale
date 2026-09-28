"""Django app configuration for QuickScale analytics.

Startup configuration is validated by
:func:`quickscale_modules_analytics.checks.check_analytics_settings`, run
through ``quickscale_core.runtime.register_module_checks`` from ``ready()``.
Only an unreachable vendor is tolerated there; invalid configuration refuses
to start.
"""

from __future__ import annotations

import logging

from django.apps import AppConfig

from quickscale_core.runtime import register_module_checks
from quickscale_modules_analytics.services import configure_analytics_client

logger = logging.getLogger(__name__)


class QuickscaleAnalyticsConfig(AppConfig):
    """Configuration for the QuickScale analytics module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_analytics"
    label = "quickscale_analytics"
    verbose_name = "QuickScale Analytics"

    def ready(self) -> None:
        # Late import: keep the app config importable while Django is still
        # populating the app registry.
        from quickscale_modules_analytics.checks import check_analytics_settings

        register_module_checks(self, [check_analytics_settings])

        # Initialize analytics safely without blocking Django startup: the
        # vendor may be unreachable, and a vendor outage must not fail a
        # request process (rule 10).
        try:
            configure_analytics_client()
        except Exception:
            logger.warning(
                "QuickScale analytics failed to initialize during app startup.",
                exc_info=True,
            )
