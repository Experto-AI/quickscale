"""Plan, price, and provider-identity validation.

Implementation detail of :mod:`quickscale_modules_billing.services`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from quickscale_modules_billing._payload import (
    _normalize_integer as _normalize_integer,
)
from quickscale_modules_billing._payload import (
    _normalize_mapping as _normalize_mapping,
)
from quickscale_modules_billing._payload import (
    _stripe_object_id as _stripe_object_id,
)
from quickscale_modules_billing._settings import (
    _STRIPE_RECURRING_INTERVAL_BY_PLAN_INTERVAL as _STRIPE_RECURRING_INTERVAL_BY_PLAN_INTERVAL,
)
from quickscale_modules_billing.exceptions import (
    BillingValidationError,
    BillingWebhookError,
)
from quickscale_modules_billing.models import (
    Plan,
    Subscription,
)


def _validate_one_time_purchase_plan(plan: Plan) -> None:
    if not plan.is_active:
        raise BillingValidationError("Billing plan is not active.")
    if plan.billing_interval != Plan.BillingInterval.ONE_TIME:
        raise BillingValidationError(
            "Billing plan does not support one-time purchases."
        )
    if not str(plan.stripe_price_id or "").strip():
        raise BillingValidationError("Billing plan is missing a Stripe price id.")


def _validate_recurring_subscription_plan(plan: Plan) -> None:
    if not plan.is_active:
        raise BillingValidationError("Billing plan is not active.")
    if plan.billing_interval not in _STRIPE_RECURRING_INTERVAL_BY_PLAN_INTERVAL:
        raise BillingValidationError(
            "Billing plan does not support recurring subscriptions."
        )
    if not str(plan.stripe_price_id or "").strip():
        raise BillingValidationError("Billing plan is missing a Stripe price id.")


def _validate_completed_checkout_plan(
    plan: Plan,
    *,
    expected_price_id: str,
    expected_interval: str,
) -> None:
    if not str(plan.stripe_price_id or "").strip():
        raise BillingWebhookError("Billing plan is missing a Stripe price id.")
    if plan.stripe_price_id != expected_price_id:
        raise BillingWebhookError(
            "Billing plan no longer matches the immutable checkout price."
        )
    if expected_interval and expected_interval != Plan.BillingInterval.ONE_TIME:
        raise BillingWebhookError(
            "Stripe checkout session metadata does not describe a one-time purchase."
        )


def _validate_stripe_price_parity(
    *,
    plan: Plan,
    stripe_price: Mapping[str, Any],
) -> None:
    unit_amount = _normalize_integer(stripe_price.get("unit_amount"))
    if unit_amount is None or unit_amount != plan.price_cents:
        raise BillingValidationError(
            "Billing plan price does not match the referenced Stripe price amount."
        )

    currency = str(stripe_price.get("currency") or "").strip().lower()
    if currency != plan.currency.casefold():
        raise BillingValidationError(
            "Billing plan currency does not match the referenced Stripe price."
        )

    price_type = str(stripe_price.get("type") or "").strip().lower()
    if (
        plan.billing_interval == Plan.BillingInterval.ONE_TIME
        and price_type != "one_time"
    ):
        raise BillingValidationError(
            "Billing plan must reference a one-time Stripe price for purchases."
        )
    if (
        plan.billing_interval != Plan.BillingInterval.ONE_TIME
        and price_type != "recurring"
    ):
        raise BillingValidationError(
            "Billing plan must reference a recurring Stripe price for subscriptions."
        )
    if plan.billing_interval == Plan.BillingInterval.ONE_TIME:
        return

    expected_interval = _STRIPE_RECURRING_INTERVAL_BY_PLAN_INTERVAL.get(
        plan.billing_interval,
        "",
    )
    recurring_data = _normalize_mapping(stripe_price.get("recurring") or {})
    actual_interval = str(recurring_data.get("interval") or "").strip().lower()
    if actual_interval != expected_interval:
        raise BillingValidationError(
            "Billing plan billing interval does not match the referenced Stripe price."
        )


def _validate_completed_checkout_provider_identity(
    *,
    reservation: Subscription,
    organization: Any,
    checkout_session_payload: Mapping[str, Any],
) -> tuple[str, str]:
    """Reject a completed Checkout that conflicts with locked local identity."""
    provider_subscription_id = _stripe_object_id(
        checkout_session_payload.get("subscription")
    )
    provider_customer_id = _stripe_object_id(checkout_session_payload.get("customer"))
    reservation_subscription_id = str(reservation.stripe_subscription_id or "").strip()
    reservation_customer_id = str(reservation.stripe_customer_id or "").strip()
    organization_customer_id = str(
        getattr(organization, "stripe_customer_id", "") or ""
    ).strip()
    if (
        (
            provider_subscription_id
            and reservation_subscription_id
            and provider_subscription_id != reservation_subscription_id
        )
        or (
            provider_customer_id
            and reservation_customer_id
            and provider_customer_id != reservation_customer_id
        )
        or (
            provider_customer_id
            and organization_customer_id
            and provider_customer_id != organization_customer_id
        )
    ):
        raise BillingWebhookError(
            "Completed checkout provider identity conflicts with the locked "
            "subscription reservation or organization."
        )
    return provider_subscription_id, provider_customer_id
