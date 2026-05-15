"""Purchase-domain tests for the QuickScale billing module."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse

from quickscale_modules_billing.models import (
    CreditBalance,
    CreditTransaction,
    Plan,
    WebhookEvent,
)
from quickscale_modules_billing.serializers import (
    CreateCheckoutSessionSerializer,
    CreditBalanceSerializer,
    CreditTransactionSerializer,
)
from quickscale_modules_billing.services import (
    BillingValidationError,
    BillingWebhookError,
    StripeClient,
    StripeWebhookResult,
    create_checkout_session,
    credit_user,
    handle_stripe_event,
)


def _create_one_time_plan(
    *,
    slug: str = "credits-pack",
    price_id: str = "price_credits_pack",
    credits: int = 250,
    price_cents: int = 4900,
    is_active: bool = True,
) -> Plan:
    return Plan.objects.create(
        name="Credits Pack",
        slug=slug,
        stripe_price_id=price_id,
        credits_per_period=credits,
        price_cents=price_cents,
        currency="usd",
        billing_interval=Plan.BillingInterval.ONE_TIME,
        is_active=is_active,
    )


def _create_monthly_plan(*, slug: str = "starter-monthly") -> Plan:
    return Plan.objects.create(
        name="Starter Monthly",
        slug=slug,
        stripe_price_id=f"price_{slug}",
        credits_per_period=100,
        price_cents=1900,
        currency="usd",
        billing_interval=Plan.BillingInterval.MONTHLY,
        is_active=True,
    )


def _user_reference(user: Any) -> str:
    return f"{user._meta.label_lower}:{user.pk}"


def _checkout_session_completed_event(
    *,
    event_id: str,
    checkout_session_id: str,
    customer_id: str,
    payment_intent_id: str,
    metadata: dict[str, str],
    client_reference_id: str = "",
    payment_status: str = "paid",
    mode: str = "payment",
) -> dict[str, Any]:
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": checkout_session_id,
                "mode": mode,
                "payment_status": payment_status,
                "customer": customer_id,
                "payment_intent": payment_intent_id,
                "client_reference_id": client_reference_id,
                "metadata": metadata,
            }
        },
    }


@dataclass
class FakePurchaseStripeClient:
    """Minimal Stripe fake for purchase-domain service tests."""

    prices: dict[str, dict[str, Any]] = field(default_factory=dict)
    customers: list[dict[str, Any]] = field(default_factory=list)
    payment_intents: dict[str, dict[str, Any]] = field(default_factory=dict)
    event: dict[str, Any] | None = None
    searched_references: list[str] = field(default_factory=list)
    created_customers: list[dict[str, Any]] = field(default_factory=list)
    created_checkout_payloads: list[dict[str, Any]] = field(default_factory=list)
    retrieved_price_ids: list[str] = field(default_factory=list)
    retrieved_payment_intent_ids: list[str] = field(default_factory=list)
    construct_calls: list[dict[str, Any]] = field(default_factory=list)

    def search_customers(self, *, user_reference: str) -> list[dict[str, Any]]:
        self.searched_references.append(user_reference)
        return list(self.customers)

    def create_customer(
        self,
        *,
        email: str,
        name: str,
        metadata: dict[str, str],
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        customer = {
            "id": f"cus_created_{len(self.created_customers) + 1}",
            "email": email,
            "name": name,
            "metadata": dict(metadata),
        }
        self.created_customers.append(
            {**customer, "idempotency_key": idempotency_key or ""}
        )
        return customer

    def retrieve_price(self, *, price_id: str) -> dict[str, Any]:
        self.retrieved_price_ids.append(price_id)
        return dict(self.prices.get(price_id, {}))

    def create_checkout_session(
        self,
        *,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        session_metadata: dict[str, str],
        payment_intent_metadata: dict[str, str],
        client_reference_id: str,
    ) -> dict[str, Any]:
        self.created_checkout_payloads.append(
            {
                "customer_id": customer_id,
                "price_id": price_id,
                "success_url": success_url,
                "cancel_url": cancel_url,
                "session_metadata": dict(session_metadata),
                "payment_intent_metadata": dict(payment_intent_metadata),
                "client_reference_id": client_reference_id,
            }
        )
        return {
            "id": "cs_test_123",
            "url": "https://checkout.stripe.test/session/123",
        }

    def construct_event(
        self,
        *,
        body: bytes,
        signature: str,
        webhook_secret: str,
    ) -> dict[str, Any]:
        self.construct_calls.append(
            {
                "body": body,
                "signature": signature,
                "webhook_secret": webhook_secret,
            }
        )
        assert self.event is not None
        return dict(self.event)

    def retrieve_payment_intent(self, *, payment_intent_id: str) -> dict[str, Any]:
        self.retrieved_payment_intent_ids.append(payment_intent_id)
        return dict(self.payment_intents.get(payment_intent_id, {}))


@pytest.mark.django_db
def test_create_checkout_session_returns_stripe_url_and_attaches_metadata(user) -> None:
    plan = _create_one_time_plan()
    fake_client = FakePurchaseStripeClient(
        prices={
            plan.stripe_price_id: {
                "id": plan.stripe_price_id,
                "unit_amount": plan.price_cents,
                "currency": plan.currency,
                "type": "one_time",
            }
        }
    )

    checkout_url = create_checkout_session(
        user,
        plan,
        "https://app.example.com/billing/purchase/success",
        "https://app.example.com/billing/purchase/cancel",
        stripe_client=fake_client,
    )

    assert checkout_url == "https://checkout.stripe.test/session/123"
    assert fake_client.retrieved_price_ids == [plan.stripe_price_id]
    assert fake_client.searched_references == [_user_reference(user)]
    assert fake_client.created_customers[0]["email"] == ""
    assert fake_client.created_customers[0]["name"] == ""
    assert fake_client.created_checkout_payloads == [
        {
            "customer_id": "cus_created_1",
            "price_id": plan.stripe_price_id,
            "success_url": "https://app.example.com/billing/purchase/success",
            "cancel_url": "https://app.example.com/billing/purchase/cancel",
            "session_metadata": {
                "quickscale_user_reference": _user_reference(user),
                "quickscale_user_model": user._meta.label_lower,
                "quickscale_user_pk": str(user.pk),
                "quickscale_plan_slug": plan.slug,
                "quickscale_plan_credits": str(plan.credits_per_period),
                "quickscale_plan_interval": plan.billing_interval,
                "stripe_price_id": plan.stripe_price_id,
            },
            "payment_intent_metadata": {
                "quickscale_user_reference": _user_reference(user),
                "quickscale_user_model": user._meta.label_lower,
                "quickscale_user_pk": str(user.pk),
                "quickscale_plan_slug": plan.slug,
                "quickscale_plan_credits": str(plan.credits_per_period),
                "quickscale_plan_interval": plan.billing_interval,
                "stripe_price_id": plan.stripe_price_id,
            },
            "client_reference_id": _user_reference(user),
        }
    ]


@pytest.mark.django_db
def test_create_checkout_session_rejects_non_one_time_plan(user) -> None:
    monthly_plan = _create_monthly_plan()

    with pytest.raises(BillingValidationError, match="one-time purchases"):
        create_checkout_session(
            user,
            monthly_plan,
            "https://app.example.com/billing/purchase/success",
            "https://app.example.com/billing/purchase/cancel",
            stripe_client=FakePurchaseStripeClient(),
        )


@pytest.mark.django_db
def test_create_checkout_session_rejects_mismatched_stripe_price(user) -> None:
    plan = _create_one_time_plan(price_cents=4900)
    fake_client = FakePurchaseStripeClient(
        prices={
            plan.stripe_price_id: {
                "id": plan.stripe_price_id,
                "unit_amount": 5900,
                "currency": plan.currency,
                "type": "one_time",
            }
        }
    )

    with pytest.raises(BillingValidationError, match="does not match"):
        create_checkout_session(
            user,
            plan,
            "https://app.example.com/billing/purchase/success",
            "https://app.example.com/billing/purchase/cancel",
            stripe_client=fake_client,
        )


@pytest.mark.django_db
def test_create_checkout_session_serializer_validates_one_time_plan() -> None:
    plan = _create_one_time_plan(slug="credits-500")
    serializer = CreateCheckoutSessionSerializer(
        data={
            "plan_slug": plan.slug,
            "success_url": "https://app.example.com/billing/purchase/success",
            "cancel_url": "https://app.example.com/billing/purchase/cancel",
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["plan"] == plan


@pytest.mark.django_db
def test_create_checkout_session_serializer_rejects_non_one_time_plan() -> None:
    monthly_plan = _create_monthly_plan(slug="starter-monthly-serializer")
    serializer = CreateCheckoutSessionSerializer(
        data={
            "plan_slug": monthly_plan.slug,
            "success_url": "https://app.example.com/billing/purchase/success",
            "cancel_url": "https://app.example.com/billing/purchase/cancel",
        }
    )

    assert serializer.is_valid() is False
    assert serializer.errors == {
        "plan_slug": ["Billing plan does not support one-time purchases."]
    }


@pytest.mark.django_db
def test_create_checkout_session_serializer_rejects_unknown_plan() -> None:
    serializer = CreateCheckoutSessionSerializer(
        data={
            "plan_slug": "missing-plan",
            "success_url": "https://app.example.com/billing/purchase/success",
            "cancel_url": "https://app.example.com/billing/purchase/cancel",
        }
    )

    assert serializer.is_valid() is False
    assert serializer.errors == {"plan_slug": ["Unknown billing plan."]}


@pytest.mark.django_db
def test_create_checkout_session_serializer_rejects_inactive_plan() -> None:
    inactive_plan = _create_one_time_plan(slug="inactive-plan", is_active=False)
    serializer = CreateCheckoutSessionSerializer(
        data={
            "plan_slug": inactive_plan.slug,
            "success_url": "https://app.example.com/billing/purchase/success",
            "cancel_url": "https://app.example.com/billing/purchase/cancel",
        }
    )

    assert serializer.is_valid() is False
    assert serializer.errors == {"plan_slug": ["Billing plan is not active."]}


@pytest.mark.django_db
def test_credit_balance_serializer_serializes_balance_snapshot(user) -> None:
    balance = CreditBalance.objects.create(user=user, balance=325)
    serializer = CreditBalanceSerializer(balance)

    assert serializer.data["balance"] == 325
    assert serializer.data["updated_at"] is not None


@pytest.mark.django_db
def test_credit_transaction_serializer_serializes_purchase_transaction(user) -> None:
    transaction_row = credit_user(
        user,
        amount=125,
        transaction_type=CreditTransaction.TransactionType.PURCHASE,
        description="Credits purchase",
        stripe_event_id="evt_purchase_serializer",
        stripe_object_id="cs_purchase_serializer",
        stripe_reference_data={"checkout_session_id": "cs_purchase_serializer"},
    )
    serializer = CreditTransactionSerializer(transaction_row)

    assert serializer.data == {
        "id": transaction_row.pk,
        "amount": 125,
        "transaction_type": CreditTransaction.TransactionType.PURCHASE,
        "description": "Credits purchase",
        "balance_after": 125,
        "created_at": transaction_row.created_at.isoformat().replace("+00:00", "Z"),
    }


@pytest.mark.django_db
def test_handle_stripe_event_credits_purchase_from_checkout_session_metadata(
    user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_one_time_plan(
        slug="metadata-plan", price_id="price_metadata_purchase"
    )
    fake_client = FakePurchaseStripeClient(
        event=_checkout_session_completed_event(
            event_id="evt_checkout_purchase",
            checkout_session_id="cs_purchase_123",
            customer_id="cus_purchase_123",
            payment_intent_id="pi_purchase_123",
            metadata={
                "quickscale_user_reference": _user_reference(user),
                "quickscale_plan_slug": plan.slug,
                "quickscale_plan_credits": str(plan.credits_per_period),
                "quickscale_plan_interval": plan.billing_interval,
                "stripe_price_id": plan.stripe_price_id,
            },
        )
    )
    monkeypatch.setenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_purchase")

    result = handle_stripe_event(
        body=b'{"id":"evt_checkout_purchase"}',
        signature="t=1,v1=test-signature",
        stripe_client=fake_client,
    )

    transaction_row = CreditTransaction.objects.get(user=user)
    webhook_event = WebhookEvent.objects.get(stripe_event_id="evt_checkout_purchase")

    assert result.duplicate is False
    assert result.status == "processed"
    assert CreditBalance.objects.get(user=user).balance == plan.credits_per_period
    assert (
        transaction_row.transaction_type == CreditTransaction.TransactionType.PURCHASE
    )
    assert transaction_row.stripe_object_id == "cs_purchase_123"
    assert transaction_row.stripe_reference_data == {
        "checkout_session_id": "cs_purchase_123",
        "payment_intent_id": "pi_purchase_123",
        "stripe_customer_id": "cus_purchase_123",
        "stripe_price_id": plan.stripe_price_id,
    }
    assert webhook_event.processed is True
    assert fake_client.retrieved_payment_intent_ids == []


@pytest.mark.django_db
def test_handle_stripe_event_suppresses_second_checkout_session_business_object(
    user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_one_time_plan(slug="dedupe-plan", price_id="price_dedupe_purchase")
    fake_client = FakePurchaseStripeClient(
        event=_checkout_session_completed_event(
            event_id="evt_checkout_first",
            checkout_session_id="cs_purchase_duplicate",
            customer_id="cus_purchase_duplicate",
            payment_intent_id="pi_purchase_duplicate",
            metadata={
                "quickscale_user_reference": _user_reference(user),
                "quickscale_plan_slug": plan.slug,
                "quickscale_plan_credits": str(plan.credits_per_period),
                "quickscale_plan_interval": plan.billing_interval,
                "stripe_price_id": plan.stripe_price_id,
            },
        )
    )
    monkeypatch.setenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_purchase_duplicate")

    first_result = handle_stripe_event(
        body=b'{"id":"evt_checkout_first"}',
        signature="t=1,v1=test-signature",
        stripe_client=fake_client,
    )
    fake_client.event = _checkout_session_completed_event(
        event_id="evt_checkout_second",
        checkout_session_id="cs_purchase_duplicate",
        customer_id="cus_purchase_duplicate",
        payment_intent_id="pi_purchase_duplicate",
        metadata={
            "quickscale_user_reference": _user_reference(user),
            "quickscale_plan_slug": plan.slug,
            "quickscale_plan_credits": str(plan.credits_per_period),
            "quickscale_plan_interval": plan.billing_interval,
            "stripe_price_id": plan.stripe_price_id,
        },
    )
    second_result = handle_stripe_event(
        body=b'{"id":"evt_checkout_second"}',
        signature="t=1,v1=test-signature",
        stripe_client=fake_client,
    )

    assert first_result.status == "processed"
    assert second_result.duplicate is False
    assert second_result.status == "processed"
    assert CreditTransaction.objects.filter(user=user).count() == 1
    assert CreditBalance.objects.get(user=user).balance == plan.credits_per_period
    assert WebhookEvent.objects.count() == 2


@pytest.mark.django_db
def test_handle_stripe_event_uses_payment_intent_metadata_fallback_for_purchase(
    user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_one_time_plan(
        slug="fallback-plan", price_id="price_purchase_fallback"
    )
    fake_client = FakePurchaseStripeClient(
        event=_checkout_session_completed_event(
            event_id="evt_checkout_fallback",
            checkout_session_id="cs_purchase_fallback",
            customer_id="cus_purchase_fallback",
            payment_intent_id="pi_purchase_fallback",
            metadata={},
        ),
        payment_intents={
            "pi_purchase_fallback": {
                "id": "pi_purchase_fallback",
                "metadata": {
                    "quickscale_user_reference": _user_reference(user),
                    "quickscale_plan_slug": plan.slug,
                    "quickscale_plan_credits": str(plan.credits_per_period),
                    "quickscale_plan_interval": plan.billing_interval,
                    "stripe_price_id": plan.stripe_price_id,
                },
            }
        },
    )
    monkeypatch.setenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_purchase_fallback")

    result = handle_stripe_event(
        body=b'{"id":"evt_checkout_fallback"}',
        signature="t=1,v1=test-signature",
        stripe_client=fake_client,
    )

    assert result.status == "processed"
    assert CreditBalance.objects.get(user=user).balance == plan.credits_per_period
    assert fake_client.retrieved_payment_intent_ids == ["pi_purchase_fallback"]


@pytest.mark.django_db
def test_handle_stripe_event_credits_purchase_from_purchase_time_metadata_when_plan_drifts(
    user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_one_time_plan(
        slug="purchase-time-plan",
        price_id="price_purchase_time",
        credits=250,
    )
    stored_credits = plan.credits_per_period
    fake_client = FakePurchaseStripeClient(
        event=_checkout_session_completed_event(
            event_id="evt_checkout_purchase_time",
            checkout_session_id="cs_purchase_time",
            customer_id="cus_purchase_time",
            payment_intent_id="pi_purchase_time",
            metadata={
                "quickscale_user_reference": _user_reference(user),
                "quickscale_plan_slug": plan.slug,
                "quickscale_plan_credits": str(plan.credits_per_period),
                "quickscale_plan_interval": plan.billing_interval,
                "stripe_price_id": plan.stripe_price_id,
            },
        )
    )
    monkeypatch.setenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_purchase_time")

    plan.slug = "purchase-time-plan-renamed"
    plan.credits_per_period = 500
    plan.billing_interval = Plan.BillingInterval.MONTHLY
    plan.save(update_fields=["slug", "credits_per_period", "billing_interval"])

    result = handle_stripe_event(
        body=b'{"id":"evt_checkout_purchase_time"}',
        signature="t=1,v1=test-signature",
        stripe_client=fake_client,
    )

    transaction_row = CreditTransaction.objects.get(user=user)
    webhook_event = WebhookEvent.objects.get(
        stripe_event_id="evt_checkout_purchase_time"
    )

    assert result.duplicate is False
    assert result.status == "processed"
    assert CreditTransaction.objects.filter(user=user).count() == 1
    assert CreditBalance.objects.get(user=user).balance == stored_credits
    assert transaction_row.amount == stored_credits
    assert transaction_row.stripe_reference_data == {
        "checkout_session_id": "cs_purchase_time",
        "payment_intent_id": "pi_purchase_time",
        "stripe_customer_id": "cus_purchase_time",
        "stripe_price_id": plan.stripe_price_id,
    }
    assert webhook_event.processed is True
    assert webhook_event.processing_error == ""


@pytest.mark.django_db
def test_handle_stripe_event_rejects_unpaid_checkout_session(
    user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_one_time_plan(slug="unpaid-plan", price_id="price_purchase_unpaid")
    fake_client = FakePurchaseStripeClient(
        event=_checkout_session_completed_event(
            event_id="evt_checkout_unpaid",
            checkout_session_id="cs_purchase_unpaid",
            customer_id="cus_purchase_unpaid",
            payment_intent_id="pi_purchase_unpaid",
            metadata={
                "quickscale_user_reference": _user_reference(user),
                "quickscale_plan_slug": plan.slug,
                "quickscale_plan_credits": str(plan.credits_per_period),
                "quickscale_plan_interval": plan.billing_interval,
                "stripe_price_id": plan.stripe_price_id,
            },
            payment_status="unpaid",
        )
    )
    monkeypatch.setenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_purchase_unpaid")

    with pytest.raises(BillingWebhookError, match="not settled"):
        handle_stripe_event(
            body=b'{"id":"evt_checkout_unpaid"}',
            signature="t=1,v1=test-signature",
            stripe_client=fake_client,
        )

    webhook_event = WebhookEvent.objects.get(stripe_event_id="evt_checkout_unpaid")

    assert webhook_event.processed is False
    assert (
        webhook_event.processing_error
        == "Stripe checkout session payment is not settled."
    )


def test_purchase_webhook_view_accepts_checkout_session_completed_event(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "quickscale_modules_billing.views.handle_stripe_event",
        lambda **kwargs: StripeWebhookResult(
            duplicate=False,
            event_type="checkout.session.completed",
            status="processed",
        ),
    )

    response = client.post(
        reverse("quickscale_billing:stripe-webhook"),
        data=b'{"id":"evt_view_purchase"}',
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="t=1,v1=view-purchase-signature",
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "accepted",
        "duplicate": False,
        "event_type": "checkout.session.completed",
        "processing_status": "processed",
    }


def test_purchase_webhook_view_maps_processing_errors_to_400(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "quickscale_modules_billing.views.handle_stripe_event",
        lambda **kwargs: (_ for _ in ()).throw(
            BillingWebhookError("Stripe checkout session payment is not settled.")
        ),
    )

    response = client.post(
        reverse("quickscale_billing:stripe-webhook"),
        data=b"{}",
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="t=1,v1=view-purchase-error",
    )

    assert response.status_code == 400
    assert response.json()["error"] == "Stripe checkout session payment is not settled."


def test_stripe_client_create_checkout_session_uses_checkout_api() -> None:
    stripe_module = SimpleNamespace(
        api_key="",
        checkout=SimpleNamespace(
            Session=SimpleNamespace(
                create=lambda **kwargs: {
                    "id": "cs_created",
                    "url": "https://checkout.stripe.test/session/created",
                    **kwargs,
                }
            )
        ),
    )
    stripe_client = StripeClient(stripe_module=stripe_module, api_key="sk_test")

    checkout_session = stripe_client.create_checkout_session(
        customer_id="cus_wrapper",
        price_id="price_wrapper",
        success_url="https://app.example.com/billing/purchase/success",
        cancel_url="https://app.example.com/billing/purchase/cancel",
        session_metadata={"quickscale_user_reference": "auth.user:1"},
        payment_intent_metadata={"quickscale_user_reference": "auth.user:1"},
        client_reference_id="auth.user:1",
    )

    assert checkout_session == {
        "id": "cs_created",
        "url": "https://checkout.stripe.test/session/created",
        "mode": "payment",
        "customer": "cus_wrapper",
        "line_items": [{"price": "price_wrapper", "quantity": 1}],
        "success_url": "https://app.example.com/billing/purchase/success",
        "cancel_url": "https://app.example.com/billing/purchase/cancel",
        "client_reference_id": "auth.user:1",
        "metadata": {"quickscale_user_reference": "auth.user:1"},
        "payment_intent_data": {
            "metadata": {"quickscale_user_reference": "auth.user:1"}
        },
    }
    assert stripe_module.api_key == "sk_test"


def test_stripe_client_retrieve_payment_intent_returns_normalized_mapping() -> None:
    stripe_module = SimpleNamespace(
        api_key="",
        PaymentIntent=SimpleNamespace(
            retrieve=lambda payment_intent_id: {
                "id": payment_intent_id,
                "metadata": {"quickscale_user_reference": "auth.user:1"},
            }
        ),
    )
    stripe_client = StripeClient(stripe_module=stripe_module, api_key="sk_test")

    payment_intent = stripe_client.retrieve_payment_intent(
        payment_intent_id="pi_wrapper"
    )

    assert payment_intent == {
        "id": "pi_wrapper",
        "metadata": {"quickscale_user_reference": "auth.user:1"},
    }
    assert stripe_module.api_key == "sk_test"


def test_stripe_client_retrieve_price_returns_normalized_mapping() -> None:
    stripe_module = SimpleNamespace(
        api_key="",
        Price=SimpleNamespace(
            retrieve=lambda price_id: {
                "id": price_id,
                "unit_amount": 4900,
                "currency": "usd",
                "type": "one_time",
            }
        ),
    )
    stripe_client = StripeClient(stripe_module=stripe_module, api_key="sk_test")

    stripe_price = stripe_client.retrieve_price(price_id="price_wrapper")

    assert stripe_price == {
        "id": "price_wrapper",
        "unit_amount": 4900,
        "currency": "usd",
        "type": "one_time",
    }
    assert stripe_module.api_key == "sk_test"
