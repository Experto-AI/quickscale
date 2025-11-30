"""User models for QuickScale authentication"""

from django.contrib.auth.models import AbstractUser
from django.urls import reverse


class User(AbstractUser):
    """
    Custom user model extending Django's AbstractUser

    Provides foundation for authentication with django-allauth integration.
    Uses email and username for authentication (configurable via AUTH_USER_MODEL).
    """

    # Optional: Add custom fields here
    # For MVP, we keep it simple and extend AbstractUser without custom fields
    # Users can add custom fields in their project if needed

    class Meta:
        db_table = "quickscale_auth_user"
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["-date_joined"]

    def get_absolute_url(self) -> str:
        """Return the URL to access the user's profile"""
        return reverse("quickscale_auth:profile")

    def __str__(self) -> str:
        """Return string representation of the user"""
        return self.get_full_name() or self.username

    def get_display_name(self) -> str:
        """Return the display name (full name or username)"""
        return self.get_full_name() or self.username
