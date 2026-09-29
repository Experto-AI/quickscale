"""Billing module exceptions.

Every billing exception derives from :class:`BillingError`, so a caller can
catch the module's whole error surface with one name.  ``services.py``
re-exports these classes for callers that historically imported them there.

The webhook-facing classes below also derive from DRF's
:class:`~rest_framework.exceptions.APIException`: they carry the HTTP status
and rule 9's stable error code, so billing views raise the module's own error
and the one QuickScale exception handler renders the response
(Module Conventions rules 9 and 26).
"""

from __future__ import annotations

from rest_framework.exceptions import APIException

__all__ = [
    "BillingConfigurationError",
    "BillingDisabledError",
    "BillingError",
    "BillingSubscriptionAnomalyError",
    "BillingValidationError",
    "BillingWebhookError",
    "BillingWebhookSignatureError",
    "InsufficientCreditsError",
]


class BillingError(Exception):
    """Base error for billing runtime operations."""


class InsufficientCreditsError(BillingError):
    """Raised when a debit exceeds the available balance."""


class BillingConfigurationError(BillingError, APIException):
    """Raised when runtime billing configuration is invalid."""

    status_code = 500
    default_code = "configuration_error"


class BillingDisabledError(BillingError, APIException):
    """Raised when the billing runtime is disabled."""

    status_code = 404
    default_code = "not_found"


class BillingValidationError(BillingError):
    """Raised when a billing request is structurally invalid."""


class BillingSubscriptionAnomalyError(BillingError):
    """Raised when a local subscription row exists but is in an
    anomalous state — e.g. missing its Stripe subscription id.

    This is distinct from ``BillingValidationError`` so that callers
    such as account-deletion can surface the anomaly (log it, flag it)
    instead of silently treating it as "no subscription to cancel."
    """


class BillingWebhookError(BillingError, APIException):
    """Raised when Stripe webhook handling fails."""

    status_code = 400
    default_code = "webhook_payload_invalid"


class BillingWebhookSignatureError(BillingWebhookError):
    """Raised when Stripe webhook signature validation fails."""

    status_code = 400
    default_code = "webhook_signature_invalid"
