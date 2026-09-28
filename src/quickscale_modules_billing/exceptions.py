"""Billing module exceptions.

Every billing exception derives from :class:`BillingError`, so a caller can
catch the module's whole error surface with one name.  ``services.py``
re-exports these classes for callers that historically imported them there.
"""

from __future__ import annotations

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


class BillingConfigurationError(BillingError):
    """Raised when runtime billing configuration is invalid."""


class BillingDisabledError(BillingError):
    """Raised when the billing runtime is disabled."""


class BillingValidationError(BillingError):
    """Raised when a billing request is structurally invalid."""


class BillingSubscriptionAnomalyError(BillingError):
    """Raised when a local subscription row exists but is in an
    anomalous state — e.g. missing its Stripe subscription id.

    This is distinct from ``BillingValidationError`` so that callers
    such as account-deletion can surface the anomaly (log it, flag it)
    instead of silently treating it as "no subscription to cancel."
    """


class BillingWebhookError(BillingError):
    """Raised when Stripe webhook handling fails."""


class BillingWebhookSignatureError(BillingWebhookError):
    """Raised when Stripe webhook signature validation fails."""
