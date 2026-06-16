"""URL configuration for testing CRM module.

CRM owns both solo and org-scoped SaaS paths internally, so a single root
include exposes the full route contract for tests.
"""

from django.urls import include, path

urlpatterns = [
    path("", include("quickscale_modules_crm.urls")),
]
