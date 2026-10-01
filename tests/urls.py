"""URL configuration for Forms module tests.

The test URLconf mirrors the manifest's ``forms/`` mount so the module's
module-relative routes resolve at their shipped ``/forms/...`` paths.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("forms/", include("quickscale_modules_forms.urls")),
]
