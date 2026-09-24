"""Dahlia-shaped Stripe payload builders for the billing test suite.

Every builder returns a plain JSON-shaped dict that was produced by a real
Stripe SDK object (``construct_from(...).to_dict()``), so the fixtures follow
the payload shape the pinned SDK actually produces instead of a hand-written
literal. A future SDK release that changes one of these shapes then fails a
test here rather than in production.
"""

from __future__ import annotations

from typing import Any

import stripe

from quickscale_modules_billing.services import STRIPE_API_VERSION

TEST_API_KEY = "sk_test_quickscale_billing"


def normalize_stripe_object(
    resource: Any,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Round-trip *payload* through a real SDK resource and return plain JSON."""
    return resource.construct_from(payload, TEST_API_KEY).to_dict()


def stripe_event(
    *,
    event_id: str,
    event_type: str,
    event_object: dict[str, Any],
    object_type: str,
    api_version: str = STRIPE_API_VERSION,
) -> dict[str, Any]:
    """Build a signed-event payload at the pinned (or an explicit) API version."""
    return normalize_stripe_object(
        stripe.Event,
        {
            "id": event_id,
            "object": "event",
            "type": event_type,
            "api_version": api_version,
            "data": {"object": {"object": object_type, **event_object}},
        },
    )


def invoice_object(
    *,
    invoice_id: str,
    customer_id: str,
    price_id: str,
    subscription_id: str = "sub_123",
    billing_reason: str | None = "subscription_cycle",
    invoice_metadata: dict[str, str] | None = None,
    subscription_metadata: dict[str, str] | None = None,
    line_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a dahlia Invoice object.

    The subscription id and its metadata snapshot live at
    ``parent.subscription_details``; each line item's price lives at
    ``pricing.price_details.price``.
    """
    if line_items is None:
        line_items = [
            {
                "id": f"il_{price_id}",
                "object": "line_item",
                "pricing": {
                    "type": "price_details",
                    "price_details": {"price": price_id},
                },
            }
        ]
    payload: dict[str, Any] = {
        "id": invoice_id,
        "object": "invoice",
        "customer": customer_id,
        "metadata": dict(invoice_metadata or {}),
        "lines": {"object": "list", "data": line_items},
        "parent": {
            "type": "subscription_details",
            "subscription_details": {
                "subscription": subscription_id,
                "metadata": dict(subscription_metadata or {}),
            },
        },
    }
    if billing_reason is not None:
        payload["billing_reason"] = billing_reason
    return normalize_stripe_object(stripe.Invoice, payload)


def invoice_event(
    *,
    event_id: str,
    event_type: str,
    invoice_id: str,
    customer_id: str,
    price_id: str,
    subscription_id: str = "sub_123",
    billing_reason: str | None = "subscription_cycle",
    user_reference: str | None = None,
    api_version: str = STRIPE_API_VERSION,
) -> dict[str, Any]:
    """Build an invoice event with optional subscription-details user metadata."""
    subscription_metadata: dict[str, str] = {}
    if user_reference:
        subscription_metadata["quickscale_user_reference"] = user_reference
    return stripe_event(
        event_id=event_id,
        event_type=event_type,
        object_type="invoice",
        api_version=api_version,
        event_object=invoice_object(
            invoice_id=invoice_id,
            customer_id=customer_id,
            price_id=price_id,
            subscription_id=subscription_id,
            billing_reason=billing_reason,
            subscription_metadata=subscription_metadata,
        ),
    )


def subscription_object(
    *,
    subscription_id: str,
    customer_id: str,
    price_id: str = "price_unused",
    status: str,
    metadata: dict[str, str] | None = None,
    item_periods: list[tuple[int, int]] | None = None,
    cancel_at_period_end: bool | None = None,
) -> dict[str, Any]:
    """Build a dahlia Subscription object with item-level period bounds."""
    periods = item_periods or [(1_700_000_000, 1_700_086_400)]
    items = [
        {
            "id": f"si_{index}",
            "object": "subscription_item",
            "price": {"id": price_id, "object": "price"},
            "current_period_start": period_start,
            "current_period_end": period_end,
        }
        for index, (period_start, period_end) in enumerate(periods)
    ]
    payload: dict[str, Any] = {
        "id": subscription_id,
        "object": "subscription",
        "customer": customer_id,
        "status": status,
        "metadata": dict(metadata or {}),
        "items": {"object": "list", "data": items},
    }
    if cancel_at_period_end is not None:
        payload["cancel_at_period_end"] = cancel_at_period_end
    return normalize_stripe_object(stripe.Subscription, payload)


def subscription_event(
    *,
    event_id: str,
    event_type: str,
    subscription_id: str,
    customer_id: str,
    price_id: str,
    status: str,
    user_reference: str | None = None,
    api_version: str = STRIPE_API_VERSION,
) -> dict[str, Any]:
    """Build a customer.subscription.* event with dahlia item period bounds."""
    metadata: dict[str, str] = {}
    if user_reference:
        metadata["quickscale_user_reference"] = user_reference
        metadata["stripe_price_id"] = price_id
    return stripe_event(
        event_id=event_id,
        event_type=event_type,
        object_type="subscription",
        api_version=api_version,
        event_object=subscription_object(
            subscription_id=subscription_id,
            customer_id=customer_id,
            price_id=price_id,
            status=status,
            metadata=metadata,
        ),
    )


def checkout_session_event(
    *,
    event_id: str,
    event_type: str,
    checkout_session_id: str,
    customer_id: str,
    metadata: dict[str, str] | None = None,
    subscription_id: str = "",
    payment_intent_id: str = "",
    mode: str = "payment",
    payment_status: str = "paid",
    client_reference_id: str = "",
    api_version: str = STRIPE_API_VERSION,
) -> dict[str, Any]:
    """Build a checkout.session.* event (Checkout Session fields are unchanged)."""
    event_object: dict[str, Any] = {
        "id": checkout_session_id,
        "mode": mode,
        "payment_status": payment_status,
        "customer": customer_id,
        "metadata": dict(metadata or {}),
    }
    if subscription_id:
        event_object["subscription"] = subscription_id
    if payment_intent_id:
        event_object["payment_intent"] = payment_intent_id
    if client_reference_id:
        event_object["client_reference_id"] = client_reference_id
    return stripe_event(
        event_id=event_id,
        event_type=event_type,
        object_type="checkout.session",
        api_version=api_version,
        event_object=event_object,
    )
