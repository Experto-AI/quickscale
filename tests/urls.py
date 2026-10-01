"""URL configuration for testing the CRM module.

The test URLconf mirrors the manifest's ``crm/`` mount so the module's
module-relative routes resolve at their shipped ``/crm/...`` paths.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("orgs/", include("quickscale_modules_orgs.urls")),
    path("crm/", include("quickscale_modules_crm.urls")),
]
