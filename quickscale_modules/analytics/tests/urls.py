"""URL configuration for analytics module tests."""

from django.urls import include, path

urlpatterns = [
    path("analytics/", include("quickscale_modules_analytics.urls")),
]
