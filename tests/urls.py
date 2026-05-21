"""URL configuration for QuickScale organizations module tests."""

from __future__ import annotations

from django.contrib import admin
from django.db import connection
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
    if connection.vendor != "postgresql":
        return "none"
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.current_org_id', true)")
        value = cursor.fetchone()[0]
    return value or "none"


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
