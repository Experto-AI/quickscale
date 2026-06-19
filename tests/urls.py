"""URL configuration for testing CRM module.

CRM owns both solo and org-scoped SaaS paths internally, so a single root
include exposes the full route contract for tests.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("quickscale_modules_orgs.urls")),
    path("", include("quickscale_modules_crm.urls")),
]
