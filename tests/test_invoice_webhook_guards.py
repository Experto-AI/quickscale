"""Webhook guards for invoices that must not mutate billing state."""

from __future__ import annotations

from typing import Any

import pytest
from django.conf import settings

from quickscale_modules_billing.models import (
    BillingCustomer,
    CreditBalance,
    CreditTransaction,
    Plan,
    Subscription,
)
from quickscale_modules_billing.services import handle_stripe_event

from tests._stripe_payloads import invoice_event, subscription_object


class _StripeClient:
    """Minimal fake that serves one event and an optional subscription."""

    def __init__(
        self,
        event: dict[str, Any],
        *,
        subscription_payload: dict[str, Any] | None = None,
    ) -> None:
        self.event = event
        self.subscription_payload = subscription_payload
        self.retrieved_subscription_ids: list[str] = []

    def construct_event(
        self,
        *,
        body: bytes,
        signature: str,
        webhook_secret: str,
    ) -> dict[str, Any]:
        del body, signature, webhook_secret
        return self.event

    def retrieve_subscription(self, *, stripe_subscription_id: str) -> dict[str, Any]:
        self.retrieved_subscription_ids.append(stripe_subscription_id)
        if self.subscription_payload is None:
            raise AssertionError("Unexpected Stripe subscription retrieval.")
        return self.subscription_payload


def _create_plan(*, price_id: str, credits_per_period: int = 100) -> Plan:
    return Plan.objects.create(
        name="Starter",
        slug=f"starter-{price_id}",
        stripe_price_id=price_id,
        credits_per_period=credits_per_period,
        price_cents=1900,
        currency="usd",
        billing_interval=Plan.BillingInterval.MONTHLY,
    )


def _create_subscription(
    user: Any,
    organization: Any,
    plan: Plan,
    *,
    customer_id: str,
    subscription_id: str,
    status: str = Subscription.Status.ACTIVE,
) -> Subscription:
    return Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        status=status,
    )


def _handle_event(
    monkeypatch: pytest.MonkeyPatch,
    *,
    event: dict[str, Any],
    stripe_client: _StripeClient,
) -> Any:
    secret = "whsec_invoice_guard"
    monkeypatch.setattr(settings, "QUICKSCALE_BILLING_WEBHOOK_SECRET", secret)
    return handle_stripe_event(
        body=f'{{"id":"{event["id"]}"}}'.encode("utf-8"),
        signature="t=1,v1=test-signature",
        stripe_client=stripe_client,
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("billing_reason", "suffix"),
    [
        ("manual", "manual"),
        ("", "blank"),
        (None, "missing"),
    ],
    ids=["manual", "blank", "missing"],
)
def test_payment_failed_ignores_non_subscription_billing_reasons(
    user,
    organization,
    org_context,
    monkeypatch: pytest.MonkeyPatch,
    billing_reason: str | None,
    suffix: str,
) -> None:
    plan = _create_plan(price_id=f"price_failed_{suffix}")
    customer_id = f"cus_failed_{suffix}"
    subscription_id = f"sub_failed_{suffix}"
    BillingCustomer.objects.create(
        organization=organization,
        stripe_customer_id=customer_id,
    )
    subscription = _create_subscription(
        user,
        organization,
        plan,
        customer_id=customer_id,
        subscription_id=subscription_id,
    )
    event = invoice_event(
        event_id=f"evt_failed_{suffix}",
        event_type="invoice.payment_failed",
        invoice_id=f"in_failed_{suffix}",
        customer_id=customer_id,
        price_id=plan.stripe_price_id,
        subscription_id=subscription_id,
        billing_reason=billing_reason,
    )
    stripe_client = _StripeClient(
        event,
        subscription_payload=subscription_object(
            subscription_id=subscription_id,
            customer_id=customer_id,
            price_id=plan.stripe_price_id,
            status="past_due",
        ),
    )

    result = _handle_event(monkeypatch, event=event, stripe_client=stripe_client)

    subscription.refresh_from_db()
    assert result.status == "processed"
    assert subscription.status == Subscription.Status.ACTIVE
    assert stripe_client.retrieved_subscription_ids == []


@pytest.mark.django_db
def test_payment_failed_ignores_an_invoice_without_a_subscription_id(
    user,
    organization,
    org_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_plan(price_id="price_failed_no_subscription")
    customer_id = "cus_failed_no_subscription"
    BillingCustomer.objects.create(
        organization=organization,
        stripe_customer_id=customer_id,
    )
    subscription = _create_subscription(
        user,
        organization,
        plan,
        customer_id=customer_id,
        subscription_id="sub_failed_no_subscription",
    )
    event = invoice_event(
        event_id="evt_failed_no_subscription",
        event_type="invoice.payment_failed",
        invoice_id="in_failed_no_subscription",
        customer_id=customer_id,
        price_id=plan.stripe_price_id,
        subscription_id="",
        billing_reason="subscription_cycle",
    )
    stripe_client = _StripeClient(event)

    result = _handle_event(monkeypatch, event=event, stripe_client=stripe_client)

    subscription.refresh_from_db()
    assert result.status == "processed"
    assert subscription.status == Subscription.Status.ACTIVE
    assert stripe_client.retrieved_subscription_ids == []


@pytest.mark.django_db
def test_zero_credit_plan_activates_without_a_ledger_write(
    user,
    organization,
    org_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_plan(price_id="price_zero_credits", credits_per_period=0)
    customer_id = "cus_zero_credits"
    subscription_id = "sub_zero_credits"
    BillingCustomer.objects.create(
        organization=organization,
        stripe_customer_id=customer_id,
    )
    subscription = _create_subscription(
        user,
        organization,
        plan,
        customer_id=customer_id,
        subscription_id=subscription_id,
    )
    event = invoice_event(
        event_id="evt_zero_credits",
        event_type="invoice.paid",
        invoice_id="in_zero_credits",
        customer_id=customer_id,
        price_id=plan.stripe_price_id,
        subscription_id=subscription_id,
        billing_reason="subscription_cycle",
    )
    stripe_client = _StripeClient(event)

    result = _handle_event(monkeypatch, event=event, stripe_client=stripe_client)
    retry_result = _handle_event(monkeypatch, event=event, stripe_client=stripe_client)

    subscription.refresh_from_db()
    assert result.status == "processed"
    assert retry_result.duplicate is True
    assert subscription.status == Subscription.Status.ACTIVE
    assert stripe_client.retrieved_subscription_ids == []
    assert CreditTransaction.all_objects.count() == 0
    assert CreditBalance.all_objects.count() == 0


@pytest.mark.django_db
def test_zero_credit_plan_activates_an_incomplete_subscription(
    user,
    organization,
    org_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The provider activation path also skips the zero-amount credit."""
    plan = _create_plan(price_id="price_zero_credits_incomplete", credits_per_period=0)
    customer_id = "cus_zero_credits_incomplete"
    subscription_id = "sub_zero_credits_incomplete"
    BillingCustomer.objects.create(
        organization=organization,
        stripe_customer_id=customer_id,
    )
    subscription = _create_subscription(
        user,
        organization,
        plan,
        customer_id=customer_id,
        subscription_id=subscription_id,
        status=Subscription.Status.INCOMPLETE,
    )
    event = invoice_event(
        event_id="evt_zero_credits_incomplete",
        event_type="invoice.paid",
        invoice_id="in_zero_credits_incomplete",
        customer_id=customer_id,
        price_id=plan.stripe_price_id,
        subscription_id=subscription_id,
        billing_reason="subscription_create",
    )
    stripe_client = _StripeClient(
        event,
        subscription_payload=subscription_object(
            subscription_id=subscription_id,
            customer_id=customer_id,
            price_id=plan.stripe_price_id,
            status="active",
        ),
    )

    result = _handle_event(monkeypatch, event=event, stripe_client=stripe_client)

    subscription.refresh_from_db()
    assert result.status == "processed"
    assert subscription.status == Subscription.Status.ACTIVE
    assert stripe_client.retrieved_subscription_ids == [subscription_id]
    assert CreditTransaction.all_objects.count() == 0
    assert CreditBalance.all_objects.count() == 0
