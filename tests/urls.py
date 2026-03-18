"""URL configuration for storage module tests."""

from django.urls import path

urlpatterns = [
    path("health/", lambda request: None),
]
