"""URL configuration for testing CRM module"""

from django.urls import include, path

urlpatterns = [
    path("", include("quickscale_modules_crm.urls")),
]
