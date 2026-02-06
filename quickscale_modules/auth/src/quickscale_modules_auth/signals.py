"""Signal handlers for authentication events"""

from typing import Any

from allauth.account.signals import user_signed_up
from django.dispatch import receiver


@receiver(user_signed_up)
def on_user_signed_up(
    sender: Any,  # noqa: ARG001  # Required by Django signal API
    request: Any,
    user: Any,
    **kwargs: Any,  # noqa: ARG001
) -> None:
    """Handle post-registration actions"""
    # Placeholder for custom post-registration logic
    # Examples:
    # - Send welcome email
    # - Create user profile
    # - Log registration event
    # - Trigger onboarding flow

    # For MVP, we keep this simple - users can extend in their project
    pass
