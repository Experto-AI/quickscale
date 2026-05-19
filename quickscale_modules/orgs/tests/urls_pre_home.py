"""Pre-home URL configuration used to validate the solo org root contract."""

from __future__ import annotations

from django.contrib import admin
from django.urls import include, path

from tests.urls import (
    AdminOnlyMixinView,
    accounts_profile_view,
    admin_only_view,
    current_org_id_view,
    feature_view,
    healthcheck_view,
    home_view,
    owner_only_view,
)


urlpatterns = [
    path("", include("quickscale_modules_orgs.urls")),
    path("", home_view, name="home"),
    path("healthcheck/", healthcheck_view, name="healthcheck"),
    path("accounts/profile/", accounts_profile_view, name="accounts-profile"),
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
    path("admin/", admin.site.urls),
]
