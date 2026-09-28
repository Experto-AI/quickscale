"""Notifications module exceptions.

Every notifications exception derives from :class:`NotificationError`, so a
caller can catch the module's whole error surface with one name.
``services.py`` re-exports these classes for callers that historically
imported them there.
"""

from __future__ import annotations

__all__ = [
    "NotificationConfigurationError",
    "NotificationDisabledError",
    "NotificationError",
    "NotificationTemplateError",
    "NotificationValidationError",
    "NotificationWebhookError",
    "NotificationWebhookSignatureError",
]


class NotificationError(Exception):
    """Base error for notification operations."""


class NotificationConfigurationError(NotificationError):
    """Raised when runtime notification configuration is invalid."""


class NotificationDisabledError(NotificationError):
    """Raised when the notifications runtime is disabled."""


class NotificationValidationError(NotificationError):
    """Raised when the requested notification payload is invalid."""


class NotificationTemplateError(NotificationValidationError):
    """Raised when a notification template cannot be rendered safely."""


class NotificationWebhookError(NotificationError):
    """Raised when webhook payload ingestion fails."""


class NotificationWebhookSignatureError(NotificationWebhookError):
    """Raised when webhook signature validation fails."""
