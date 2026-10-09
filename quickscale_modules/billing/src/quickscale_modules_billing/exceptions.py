"""Billing module exceptions.

Every billing exception derives from :class:`BillingError`, so a caller can
catch the module's whole error surface with one name.  ``services.py``
re-exports these classes for callers that historically imported them there.

The classes derive from :class:`Exception` only — never from DRF's
``APIException``; an exception API callers may see declares ``status_code``
and ``default_code``, and the one QuickScale exception handler in
``quickscale_core.runtime`` renders it in rule 9's shape (Module Conventions
rules 9 and 10).
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
    "OrgSelectionRequiredError",
]


class BillingError(Exception):
    """Base error for billing runtime operations.

    An unexpected failure answers ``500`` with the stable ``billing_error``
    code; the classes below override the status and code they carry.
    """

    status_code = 500
    default_code = "billing_error"


class InsufficientCreditsError(BillingError):
    """Raised when a debit exceeds the available balance.

    The debit is well formed; the organization's balance does not cover it,
    so the answer is ``402`` with the stable ``insufficient_credits`` code.
    """

    status_code = 402
    default_code = "insufficient_credits"


class BillingConfigurationError(BillingError):
    """Raised when runtime billing configuration is invalid."""

    status_code = 500
    default_code = "configuration_error"


class BillingDisabledError(BillingError):
    """Raised when the billing runtime is disabled."""

    status_code = 404
    default_code = "not_found"


class BillingValidationError(BillingError):
    """Raised when a billing request is structurally invalid."""

    status_code = 400
    default_code = "validation_error"


class BillingSubscriptionAnomalyError(BillingError):
    """Raised when a local subscription row exists but is in an
    anomalous state — e.g. missing its Stripe subscription id.

    This is distinct from ``BillingValidationError`` so that callers
    such as account-deletion can surface the anomaly (log it, flag it)
    instead of silently treating it as "no subscription to cancel."
    """

    status_code = 400
    default_code = "subscription_anomaly"


class OrgSelectionRequiredError(BillingError):
    """Raised when a billing endpoint needs an organization context.

    A request with no organization cannot answer per-user billing questions,
    so the endpoint refuses it instead of guessing a subject.
    """

    status_code = 409
    default_code = "org_selection_required"
    default_detail = "Organization selection required."


class BillingWebhookError(BillingError):
    """Raised when Stripe webhook handling fails."""

    status_code = 400
    default_code = "webhook_payload_invalid"


class BillingWebhookSignatureError(BillingWebhookError):
    """Raised when Stripe webhook signature validation fails."""

    status_code = 400
    default_code = "webhook_signature_invalid"
