"""URL configuration for testing"""

from django.shortcuts import render
from django.http import HttpResponse
from django.urls import include, path


def home_view(request):
    """Dummy home view for testing"""
    return render(request, "base.html")


def dummy_password_change(request):
    """Dummy password change view for testing"""
    return HttpResponse("Change Password")


urlpatterns = [
    path("", home_view, name="home"),
    # Include allauth URLs for login, signup, etc.
    path("accounts/", include("allauth.urls")),
    # Add dummy URL for allauth password change (for template rendering in tests)
    path(
        "accounts/password/change/",
        dummy_password_change,
        name="account_change_password",
    ),
    # QuickScale auth URLs
    path(
        "accounts/",
        include(
            ("quickscale_modules_auth.urls", "quickscale_auth"),
            namespace="quickscale_auth",
        ),
    ),
]
