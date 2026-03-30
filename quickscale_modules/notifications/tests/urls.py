"""URL configuration for notifications module tests."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("quickscale_modules_notifications.urls")),
    path("", include("quickscale_modules_forms.urls")),
]
