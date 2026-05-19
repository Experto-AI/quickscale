"""Minimal Phase 2 URL surface for org onboarding and org-scoped requests."""

from django.urls import path

from .views import org_detail_view, org_index_view, org_new_view

urlpatterns = [
    path("orgs/", org_index_view, name="org-index"),
    path("orgs/new/", org_new_view, name="org-new"),
    path("orgs/<slug:org_slug>/", org_detail_view, name="org-detail"),
]
