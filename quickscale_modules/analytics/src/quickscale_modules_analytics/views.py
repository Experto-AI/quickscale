"""HTTP views for the QuickScale analytics module."""

from __future__ import annotations

from typing import Any

from django.views.generic import TemplateView

from quickscale_modules_analytics.services import (
    get_analytics_runtime_settings,
    is_analytics_active,
)


class AnalyticsDashboardView(TemplateView):
    """Module-owned analytics overview page."""

    template_name = "quickscale_modules_analytics/dashboard.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        snapshot = get_analytics_runtime_settings()
        context.update(
            {
                "analytics_active": is_analytics_active(),
                "analytics_provider": snapshot.provider,
                "analytics_enabled": snapshot.enabled,
                "posthog_host": snapshot.resolve_posthog_host(),
            }
        )
        return context
