"""URL configuration for testing CRM module"""

from django.urls import include, path

urlpatterns = [
    # Non-scoped path for existing view tests (reverse() finds this first)
    path("", include("quickscale_modules_crm.urls")),
    # Org-scoped CRM API for cross-tenant isolation testing
    path("orgs/<slug:org_slug>/crm/", include("quickscale_modules_crm.urls")),
]
