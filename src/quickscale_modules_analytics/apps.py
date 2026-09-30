"""Django app configuration for QuickScale analytics.

Rule 3's generic settings check validates the declared options; then
:func:`quickscale_modules_analytics.checks.check_analytics_settings` covers
the resolved runtime, run through ``quickscale_core.runtime`` from
``ready()``.  Only an unreachable vendor is tolerated there; invalid
configuration refuses to start.
"""

from __future__ import annotations

import logging

from django.apps import AppConfig

from quickscale_core.runtime import (
    register_module_checks,
    register_module_settings_check,
)
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

        # Rule 3 first: a missing or invalid declared setting is reported by
        # the generic check before the runtime check reads it.
        register_module_settings_check(self, "analytics")
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
