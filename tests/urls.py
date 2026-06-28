"""URL configuration for QuickScale organizations module tests."""

from __future__ import annotations

from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from django.views import View

from quickscale_modules_orgs.models import OrgRole
from quickscale_modules_orgs.permissions import (
    OrgRoleMixin,
    require_org_feature,
    require_org_role,
)


def _current_org_id() -> str:
    """Read the current org ID from the ContextVar.

    Phase 3: middleware no longer does SET LOCAL, so test views read
    the ContextVar instead of the DB-level current_setting. Callers
    that need DB-level RLS manage their own transaction.atomic() +
    tenant_context().
    """
    from quickscale_modules_orgs.current_org import get_current_org_id

    org_id = get_current_org_id()
    return str(org_id) if org_id is not None else "none"


def _current_org_slug(request) -> str:
    organization = getattr(request, "org", None)
    return organization.slug if organization is not None else "none"


def home_view(request):
    return HttpResponse(f"{_current_org_slug(request)}|{_current_org_id()}")


def healthcheck_view(request):
    return HttpResponse(f"{_current_org_slug(request)}|{_current_org_id()}")


def accounts_profile_view(request):
    return HttpResponse(f"{_current_org_slug(request)}|{_current_org_id()}")


def current_org_id_view(request, org_slug: str):
    return HttpResponse(_current_org_id())


def api_org_context_view(request, org_slug: str):
    return HttpResponse(f"{_current_org_slug(request)}|{_current_org_id()}")


@require_org_role(OrgRole.ADMIN)
def admin_only_view(request, org_slug: str):
    return HttpResponse(_current_org_slug(request))


@require_org_role(OrgRole.OWNER)
def owner_only_view(request, org_slug: str):
    return HttpResponse(_current_org_slug(request))


@require_org_feature("crm")
def feature_view(request, org_slug: str):
    return HttpResponse("crm")


class AdminOnlyMixinView(OrgRoleMixin, View):
    min_org_role = OrgRole.ADMIN

    def get(self, request, org_slug: str):
        return HttpResponse(_current_org_slug(request))


urlpatterns = [
    path("", home_view, name="home"),
    path("healthcheck/", healthcheck_view, name="healthcheck"),
    path("accounts/profile/", accounts_profile_view, name="accounts-profile"),
    path(
        "api/orgs/<slug:org_slug>/context/",
        api_org_context_view,
        name="api-org-context",
    ),
    path(
        "orgs/<slug:org_slug>/current-org-id/",
        current_org_id_view,
        name="current-org-id",
    ),
    path(
        "orgs/<slug:org_slug>/admin-only/",
        admin_only_view,
        name="admin-only",
    ),
    path(
        "orgs/<slug:org_slug>/owner-only/",
        owner_only_view,
        name="owner-only",
    ),
    path(
        "orgs/<slug:org_slug>/admin-mixin/",
        AdminOnlyMixinView.as_view(),
        name="admin-mixin",
    ),
    path(
        "orgs/<slug:org_slug>/feature/",
        feature_view,
        name="feature-view",
    ),
    path("", include("quickscale_modules_orgs.urls")),
    path("admin/", admin.site.urls),
]
