"""Django-allauth adapter customizations"""

from typing import Any

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings


class QuickscaleAccountAdapter(DefaultAccountAdapter):
    """Custom account adapter for QuickScale authentication"""

    def is_open_for_signup(self, request: Any) -> bool:
        """Check if signup is allowed based on settings"""
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)

    def save_user(self, request: Any, user: Any, form: Any, commit: bool = True) -> Any:
        """Save user with custom logic"""
        user = super().save_user(request, user, form, commit=False)

        # Add custom user creation logic here if needed
        # For MVP, we use default django-allauth behavior

        if commit:
            user.save()

        return user

    def get_login_redirect_url(self, request: Any) -> str:
        """Return URL to redirect to after successful login"""
        # Default: redirect to profile page
        # Users can override in their settings with LOGIN_REDIRECT_URL
        return getattr(settings, "LOGIN_REDIRECT_URL", "/accounts/profile/")
