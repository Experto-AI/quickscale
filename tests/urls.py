"""URL configuration for testing"""

from django.http import HttpResponse
from django.urls import include, path


def home_view(request):
    """Dummy home view for testing"""
    return HttpResponse("Home")


def dummy_password_change(request):
    """Dummy password change view for testing"""
    return HttpResponse("Change Password")


urlpatterns = [
    path("", home_view, name="home"),
    # Add dummy URL for allauth password change (for template rendering in tests)
    path(
        "accounts/password/change/",
        dummy_password_change,
        name="account_change_password",
    ),
    path(
        "accounts/",
        include(
            ("quickscale_modules_auth.urls", "quickscale_auth"),
            namespace="quickscale_auth",
        ),
    ),
]
