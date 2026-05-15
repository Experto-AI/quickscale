"""Tests for billing module models and metadata."""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

import quickscale_modules_billing
from quickscale_modules_billing.models import (
    CreditBalance,
    CreditTransaction,
    Plan,
    Subscription,
    WebhookEvent,
)


def test_package_version_is_exposed() -> None:
    assert quickscale_modules_billing.__version__ == "0.85.0"


@pytest.mark.django_db(transaction=True)
def test_credit_balance_get_or_create_for_user_is_transaction_ready(user) -> None:
    with transaction.atomic():
        balance, created = CreditBalance.get_or_create_for_user(user)

    assert created is True
    assert balance.user == user
    assert balance.balance == 0

    with transaction.atomic():
        same_balance, created = CreditBalance.get_or_create_for_user(user)

    assert created is False
    assert same_balance.pk == balance.pk


@pytest.mark.django_db(transaction=True)
def test_credit_balance_get_or_create_for_user_without_atomic_transaction(user) -> None:
    assert transaction.get_connection().in_atomic_block is False

    balance, created = CreditBalance.get_or_create_for_user(user)

    assert created is True
    assert balance.user == user
    assert balance.balance == 0

    same_balance, created = CreditBalance.get_or_create_for_user(user)

    assert created is False
    assert same_balance.pk == balance.pk


@pytest.mark.django_db
def test_model_string_representations(user) -> None:
    plan = Plan.objects.create(
        name="Starter",
        slug="starter",
        stripe_price_id="price_starter_monthly",
        credits_per_period=100,
        price_cents=1900,
        currency="usd",
        billing_interval=Plan.BillingInterval.MONTHLY,
    )
    balance = CreditBalance.objects.create(user=user, balance=100)
    credit_transaction = CreditTransaction.objects.create(
        user=user,
        amount=100,
        transaction_type=CreditTransaction.TransactionType.PLAN,
        stripe_event_id="evt_123",
        stripe_object_id="in_123",
        stripe_reference_data={"invoice_id": "in_123"},
        description="Monthly credits",
        balance_after=100,
    )
    subscription = Subscription.objects.create(
        user=user,
        plan=plan,
        stripe_subscription_id="sub_123",
        stripe_customer_id="cus_123",
        status=Subscription.Status.ACTIVE,
    )
    webhook_event = WebhookEvent.objects.create(
        stripe_event_id="evt_123",
        event_type="invoice.paid",
        payload={"id": "evt_123"},
    )

    assert str(plan) == "Starter"
    assert str(balance) == f"{user} (100 credits)"
    assert str(credit_transaction) == f"{user} plan 100"
    assert str(subscription) == f"{user} / starter (active)"
    assert str(webhook_event) == "invoice.paid (evt_123)"


@pytest.mark.django_db
def test_webhook_event_stripe_event_id_is_unique() -> None:
    WebhookEvent.objects.create(
        stripe_event_id="evt_duplicate",
        event_type="checkout.session.completed",
        payload={"id": "evt_duplicate"},
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            WebhookEvent.objects.create(
                stripe_event_id="evt_duplicate",
                event_type="checkout.session.completed",
                payload={"id": "evt_duplicate"},
            )
