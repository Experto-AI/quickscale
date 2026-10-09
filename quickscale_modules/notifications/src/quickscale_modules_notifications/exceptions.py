"""Notifications module exceptions.

Every notifications exception derives from :class:`NotificationsError`, so a
caller can catch the module's whole error surface with one name.
``services.py`` re-exports these classes for callers that historically
imported them there.

The webhook-facing classes below declare the HTTP status and rule 9's
stable error code; the classes derive from :class:`Exception` only — the one
QuickScale exception handler in ``quickscale_core.runtime`` renders them
(Module Conventions rules 9, 10, and 26).
"""

from __future__ import annotations

__all__ = [
    "NotificationConfigurationError",
    "NotificationDisabledError",
    "NotificationsError",
    "NotificationTemplateError",
    "NotificationValidationError",
    "NotificationWebhookError",
    "NotificationWebhookSignatureError",
]


class NotificationsError(Exception):
    """Base error for notification operations."""


class NotificationConfigurationError(NotificationsError):
    """Raised when runtime notification configuration is invalid."""

    status_code = 500
    default_code = "configuration_error"


class NotificationDisabledError(NotificationsError):
    """Raised when the notifications runtime is disabled."""

    status_code = 404
    default_code = "not_found"


class NotificationValidationError(NotificationsError):
    """Raised when the requested notification payload is invalid."""


class NotificationTemplateError(NotificationValidationError):
    """Raised when a notification template cannot be rendered safely."""


class NotificationWebhookError(NotificationsError):
    """Raised when webhook payload ingestion fails."""

    status_code = 400
    default_code = "webhook_payload_invalid"


class NotificationWebhookSignatureError(NotificationWebhookError):
    """Raised when webhook signature validation fails."""

    status_code = 400
    default_code = "webhook_signature_invalid"
