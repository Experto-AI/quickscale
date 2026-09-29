"""Notifications module exceptions.

Every notifications exception derives from :class:`NotificationError`, so a
caller can catch the module's whole error surface with one name.
``services.py`` re-exports these classes for callers that historically
imported them there.

The webhook-facing classes below also derive from DRF's
:class:`~rest_framework.exceptions.APIException`: they carry the HTTP status
and rule 9's stable error code, so notification views raise the module's own
error and the one QuickScale exception handler renders the response
(Module Conventions rules 9 and 26).
"""

from __future__ import annotations

from rest_framework.exceptions import APIException

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


class NotificationConfigurationError(NotificationError, APIException):
    """Raised when runtime notification configuration is invalid."""

    status_code = 500
    default_code = "configuration_error"


class NotificationDisabledError(NotificationError, APIException):
    """Raised when the notifications runtime is disabled."""

    status_code = 404
    default_code = "not_found"


class NotificationValidationError(NotificationError):
    """Raised when the requested notification payload is invalid."""


class NotificationTemplateError(NotificationValidationError):
    """Raised when a notification template cannot be rendered safely."""


class NotificationWebhookError(NotificationError, APIException):
    """Raised when webhook payload ingestion fails."""

    status_code = 400
    default_code = "webhook_payload_invalid"


class NotificationWebhookSignatureError(NotificationWebhookError):
    """Raised when webhook signature validation fails."""

    status_code = 400
    default_code = "webhook_signature_invalid"
