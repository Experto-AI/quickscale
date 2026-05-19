"""Django URL surface for the QuickScale organizations module."""

from django.urls import path

from .views import (
    MemberListView,
    OrgCreateView,
    OrgDashboardView,
    OrgListView,
    OrgSettingsView,
)

urlpatterns = [
    path("", OrgDashboardView.as_view(), name="org-home"),
    path("orgs/", OrgListView.as_view(), name="org-index"),
    path("orgs/new/", OrgCreateView.as_view(), name="org-new"),
    path("orgs/<slug:org_slug>/", OrgDashboardView.as_view(), name="org-detail"),
    path(
        "orgs/<slug:org_slug>/members/",
        MemberListView.as_view(),
        name="org-members",
    ),
    path(
        "orgs/<slug:org_slug>/settings/",
        OrgSettingsView.as_view(),
        name="org-settings",
    ),
]
