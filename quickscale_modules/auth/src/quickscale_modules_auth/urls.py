"""URL patterns for authentication"""

from django.urls import include, path

from quickscale_modules_auth.views import (
    AccountDeleteView,
    ProfileUpdateView,
    ProfileView,
)

app_name = "quickscale_auth"

urlpatterns = [
    # django-allauth URLs (login, logout, signup, password reset)
    path("", include("allauth.urls")),
    # Custom profile management URLs
    path("profile/", ProfileView.as_view(), name="profile"),
    path("profile/edit/", ProfileUpdateView.as_view(), name="profile-edit"),
    path("account/delete/", AccountDeleteView.as_view(), name="account-delete"),
]
