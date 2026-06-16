"""URL configuration for the QuickScale analytics module."""

from django.urls import path

from quickscale_modules_analytics.views import AnalyticsDashboardView

app_name = "quickscale_analytics"

urlpatterns = [
    path(
        "",
        AnalyticsDashboardView.as_view(),
        name="analytics-dashboard",
    ),
]
