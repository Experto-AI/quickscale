"""Stripe webhook dispatch.

Implementation detail of :mod:`quickscale_modules_billing.services`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
Checkout event handling lives in
:mod:`quickscale_modules_billing._webhooks_checkout` and invoice event
handling in :mod:`quickscale_modules_billing._webhooks_invoice`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.db import transaction

from quickscale_modules_billing._settings import (
    STRIPE_EVENT_TYPE_CHECKOUT_SESSION_ASYNC_PAYMENT_FAILED as STRIPE_EVENT_TYPE_CHECKOUT_SESSION_ASYNC_PAYMENT_FAILED,
)
from quickscale_modules_billing._settings import (
    STRIPE_EVENT_TYPE_CHECKOUT_SESSION_ASYNC_PAYMENT_SUCCEEDED as STRIPE_EVENT_TYPE_CHECKOUT_SESSION_ASYNC_PAYMENT_SUCCEEDED,
)
from quickscale_modules_billing._settings import (
    STRIPE_EVENT_TYPE_CHECKOUT_SESSION_COMPLETED as STRIPE_EVENT_TYPE_CHECKOUT_SESSION_COMPLETED,
)
from quickscale_modules_billing._settings import (
    STRIPE_EVENT_TYPE_CHECKOUT_SESSION_EXPIRED as STRIPE_EVENT_TYPE_CHECKOUT_SESSION_EXPIRED,
)
from quickscale_modules_billing._settings import (
    STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_CREATED as STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_CREATED,
)
from quickscale_modules_billing._settings import (
    STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_DELETED as STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_DELETED,
)
from quickscale_modules_billing._settings import (
    STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_UPDATED as STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_UPDATED,
)
from quickscale_modules_billing._settings import (
    STRIPE_EVENT_TYPE_INVOICE_PAID as STRIPE_EVENT_TYPE_INVOICE_PAID,
)
from quickscale_modules_billing._settings import (
    STRIPE_EVENT_TYPE_INVOICE_PAYMENT_FAILED as STRIPE_EVENT_TYPE_INVOICE_PAYMENT_FAILED,
)
from quickscale_modules_billing._settings import (
    StripeWebhookResult as StripeWebhookResult,
)
import quickscale_modules_billing._subscription_events as _subscription_events
import quickscale_modules_billing._webhooks_checkout as _webhooks_checkout
import quickscale_modules_billing._webhooks_invoice as _webhooks_invoice
from quickscale_modules_billing.exceptions import (
    BillingError,
    BillingWebhookError,
)
from quickscale_modules_billing.models import (
    WebhookEvent,
)


def _process_verified_stripe_event(
    *,
    webhook_event: WebhookEvent,
    event_payload: Mapping[str, Any],
    event_type: str,
    stripe_client: Any,
) -> StripeWebhookResult:
    """Process one verified event while its session-level mutex is held."""
    with transaction.atomic():
        locked_event = WebhookEvent.objects.select_for_update().get(pk=webhook_event.pk)
        if locked_event.processed:
            return StripeWebhookResult(
                duplicate=True,
                event_type=locked_event.event_type,
                status="duplicate",
            )

    # Provider I/O happens outside a database transaction. The session-level
    # advisory mutex remains held so another delivery of this event cannot
    # enter its handler before the final processed state is persisted.
    processing_status = "ignored"
    processing_error_message = ""
    try:
        if event_type == STRIPE_EVENT_TYPE_CHECKOUT_SESSION_COMPLETED:
            _webhooks_checkout._handle_checkout_session_completed_event(
                event_payload,
                stripe_client=stripe_client,
            )
            processing_status = "processed"
        elif event_type == STRIPE_EVENT_TYPE_CHECKOUT_SESSION_ASYNC_PAYMENT_SUCCEEDED:
            _webhooks_checkout._handle_checkout_session_async_payment_succeeded_event(
                event_payload,
                stripe_client=stripe_client,
            )
            processing_status = "processed"
        elif event_type == STRIPE_EVENT_TYPE_CHECKOUT_SESSION_ASYNC_PAYMENT_FAILED:
            _webhooks_checkout._handle_checkout_session_async_payment_failed_event(
                event_payload
            )
            processing_status = "processed"
        elif event_type == STRIPE_EVENT_TYPE_CHECKOUT_SESSION_EXPIRED:
            _webhooks_checkout._handle_checkout_session_expired_event(event_payload)
            processing_status = "processed"
        elif event_type == STRIPE_EVENT_TYPE_INVOICE_PAID:
            _webhooks_invoice._handle_invoice_paid_event(
                event_payload,
                stripe_client=stripe_client,
            )
            processing_status = "processed"
        elif event_type == STRIPE_EVENT_TYPE_INVOICE_PAYMENT_FAILED:
            _webhooks_invoice._handle_invoice_payment_failed_event(event_payload)
            processing_status = "processed"
        elif event_type in {
            STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_CREATED,
            STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_UPDATED,
            STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_DELETED,
        }:
            _subscription_events._handle_subscription_event(
                event_payload, event_type=event_type
            )
            processing_status = "processed"
        else:
            processing_status = "ignored"
    except BillingError as exc:
        processing_error_message = str(exc)

    # Persist result (short atomic, no Stripe round-trips)
    with transaction.atomic():
        WebhookEvent.objects.filter(pk=webhook_event.pk).update(
            event_type=event_type,
            payload=event_payload,
            processed=(not processing_error_message),
            processing_error=processing_error_message,
        )

    if processing_error_message:
        raise BillingWebhookError(processing_error_message)

    return StripeWebhookResult(
        duplicate=False,
        event_type=event_type,
        status=processing_status,
    )
