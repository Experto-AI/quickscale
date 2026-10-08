"""HTTP views for the QuickScale analytics module."""

from __future__ import annotations

from typing import Any, cast

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.views.generic import TemplateView

from quickscale_modules_analytics._settings import (
    get_analytics_runtime_settings,
)
from quickscale_modules_analytics.services import is_analytics_active
from quickscale_modules_orgs.models import OrgRole
from quickscale_modules_orgs.permissions import OrgRoleMixin


class AnalyticsDashboardView(LoginRequiredMixin, OrgRoleMixin, TemplateView):
    """Module-owned analytics overview page.

    Anonymous visitors are redirected to login; an authenticated user below
    the active organization's viewer role is refused.  Rule 19 keeps the
    minimum role fixed in code here and listed in the module README.
    """

    template_name = "quickscale_analytics/dashboard.html"
    min_org_role = OrgRole.VIEWER

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """Require login first, then the viewer org role."""
        return cast(HttpResponse, super().dispatch(request, *args, **kwargs))

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
