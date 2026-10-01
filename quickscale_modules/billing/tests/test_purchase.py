"""Purchase-domain tests for the QuickScale billing module."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest
import stripe
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from quickscale_modules_billing import services as billing_services
from quickscale_modules_billing.models import (
    CreditBalance,
    CreditTransaction,
    Plan,
    PurchaseCheckout,
    WebhookEvent,
)
from quickscale_modules_billing.serializers import (
    CreateCheckoutSessionSerializer,
    CreditBalanceSerializer,
    CreditTransactionSerializer,
)
from quickscale_modules_billing.services import (
    BillingError,
    BillingValidationError,
    BillingWebhookError,
    StripeClient,
    StripeWebhookResult,
    create_checkout_session,
    credit_user,
    handle_stripe_event,
    reconcile_purchase_checkouts_for_removal,
)
from quickscale_modules_orgs.current_org import org_scope

from tests.stripe_payloads import (
    checkout_session_event,
    normalize_stripe_object,
)


def _organization_reference(organization: Any) -> str:
    return f"{organization._meta.label_lower}:{organization.pk}"


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
    """Build a dahlia checkout.session.completed event from a real SDK object."""
    return checkout_session_event(
        event_id=event_id,
        event_type="checkout.session.completed",
        checkout_session_id=checkout_session_id,
        customer_id=customer_id,
        metadata=metadata,
        payment_intent_id=payment_intent_id,
        mode=mode,
        payment_status=payment_status,
        client_reference_id=client_reference_id,
    )


@dataclass
class FakePurchaseStripeClient:
    """Minimal Stripe fake for purchase-domain service tests."""

    prices: dict[str, dict[str, Any]] = field(default_factory=dict)
    customers: list[dict[str, Any]] = field(default_factory=list)
    payment_intents: dict[str, dict[str, Any]] = field(default_factory=dict)
    checkout_sessions: dict[str, dict[str, Any]] = field(default_factory=dict)
    event: dict[str, Any] | None = None
    searched_references: list[str] = field(default_factory=list)
    created_customers: list[dict[str, Any]] = field(default_factory=list)
    created_checkout_payloads: list[dict[str, Any]] = field(default_factory=list)
    retrieved_price_ids: list[str] = field(default_factory=list)
    retrieved_payment_intent_ids: list[str] = field(default_factory=list)
    retrieved_checkout_session_ids: list[str] = field(default_factory=list)
    construct_calls: list[dict[str, Any]] = field(default_factory=list)

    def search_customers(
        self,
        *,
        user_reference: str = "",
        organization_reference: str = "",
    ) -> list[dict[str, Any]]:
        self.searched_references.append(organization_reference or user_reference)
        return [
            normalize_stripe_object(stripe.Customer, customer)
            for customer in self.customers
        ]

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
        return normalize_stripe_object(stripe.Customer, customer)

    def retrieve_price(self, *, price_id: str) -> dict[str, Any]:
        self.retrieved_price_ids.append(price_id)
        return normalize_stripe_object(
            stripe.Price,
            dict(self.prices.get(price_id, {})),
        )

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
        idempotency_key: str | None = None,
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
                "idempotency_key": idempotency_key or "",
            }
        )
        return normalize_stripe_object(
            stripe.checkout.Session,
            {
                "id": "cs_test_123",
                "url": "https://checkout.stripe.test/session/123",
            },
        )

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
        return normalize_stripe_object(stripe.Event, dict(self.event))

    def retrieve_payment_intent(self, *, payment_intent_id: str) -> dict[str, Any]:
        self.retrieved_payment_intent_ids.append(payment_intent_id)
        return normalize_stripe_object(
            stripe.PaymentIntent,
            dict(self.payment_intents.get(payment_intent_id, {})),
        )

    def retrieve_checkout_session(
        self,
        *,
        checkout_session_id: str,
    ) -> dict[str, Any]:
        self.retrieved_checkout_session_ids.append(checkout_session_id)
        return normalize_stripe_object(
            stripe.checkout.Session,
            dict(self.checkout_sessions.get(checkout_session_id, {})),
        )


@pytest.mark.django_db
def test_create_checkout_session_returns_stripe_url_and_attaches_metadata(
    user, organization, org_context
) -> None:
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
        organization=organization,
        stripe_client=fake_client,
    )

    assert checkout_url == "https://checkout.stripe.test/session/123"
    reservation = PurchaseCheckout.all_objects.get(organization=organization)
    reservation_reference = billing_services._purchase_checkout_reference(reservation)
    assert reservation.user == user
    assert reservation.plan == plan
    assert reservation.status == PurchaseCheckout.Status.OPEN
    assert reservation.stripe_checkout_session_id == "cs_test_123"
    assert fake_client.retrieved_price_ids == [plan.stripe_price_id]
    assert fake_client.searched_references == [_organization_reference(organization)]
    assert fake_client.created_customers[0]["email"] == ""
    assert fake_client.created_customers[0]["name"] == ""
    assert fake_client.created_checkout_payloads == [
        {
            "customer_id": "cus_created_1",
            "price_id": plan.stripe_price_id,
            "success_url": "https://app.example.com/billing/purchase/success",
            "cancel_url": "https://app.example.com/billing/purchase/cancel",
            "session_metadata": {
                "quickscale_org_reference": _organization_reference(organization),
                "quickscale_org_model": organization._meta.label_lower,
                "quickscale_org_pk": str(organization.pk),
                "quickscale_user_reference": _user_reference(user),
                "quickscale_user_model": user._meta.label_lower,
                "quickscale_user_pk": str(user.pk),
                "quickscale_plan_slug": plan.slug,
                "quickscale_plan_credits": str(plan.credits_per_period),
                "quickscale_plan_interval": plan.billing_interval,
                "stripe_price_id": plan.stripe_price_id,
                "quickscale_purchase_checkout_reference": reservation_reference,
            },
            "payment_intent_metadata": {
                "quickscale_org_reference": _organization_reference(organization),
                "quickscale_org_model": organization._meta.label_lower,
                "quickscale_org_pk": str(organization.pk),
                "quickscale_user_reference": _user_reference(user),
                "quickscale_user_model": user._meta.label_lower,
                "quickscale_user_pk": str(user.pk),
                "quickscale_plan_slug": plan.slug,
                "quickscale_plan_credits": str(plan.credits_per_period),
                "quickscale_plan_interval": plan.billing_interval,
                "stripe_price_id": plan.stripe_price_id,
                "quickscale_purchase_checkout_reference": reservation_reference,
            },
            "client_reference_id": _user_reference(user),
            "idempotency_key": billing_services._build_purchase_checkout_create_idempotency_key(
                reservation_reference
            ),
        }
    ]


@pytest.mark.django_db
def test_create_checkout_session_retains_preparing_reservation_on_provider_error(
    user,
    organization,
    org_context,
) -> None:
    plan = _create_one_time_plan(slug="checkout-provider-error")
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
    fake_client.create_checkout_session = lambda **kwargs: (  # type: ignore[method-assign]
        (_ for _ in ()).throw(RuntimeError("provider unavailable"))
    )

    with pytest.raises(RuntimeError, match="provider unavailable"):
        create_checkout_session(
            user,
            plan,
            "https://app.example.com/billing/purchase/success",
            "https://app.example.com/billing/purchase/cancel",
            organization=organization,
            stripe_client=fake_client,
        )

    reservation = PurchaseCheckout.all_objects.get(organization=organization)
    assert reservation.status == PurchaseCheckout.Status.PREPARING
    assert reservation.stripe_checkout_session_id is None


@pytest.mark.django_db
def test_create_checkout_session_retries_preparing_reservation_idempotently(
    user,
    organization,
    org_context,
) -> None:
    plan = _create_one_time_plan(slug="checkout-response-loss-retry")
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
    provider_create = fake_client.create_checkout_session

    def create_then_lose_response(**kwargs: Any) -> dict[str, Any]:
        provider_create(**kwargs)
        raise RuntimeError("provider response lost")

    fake_client.create_checkout_session = create_then_lose_response  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="response lost"):
        create_checkout_session(
            user,
            plan,
            "https://app.example.com/billing/purchase/success",
            "https://app.example.com/billing/purchase/cancel",
            organization=organization,
            stripe_client=fake_client,
        )

    preparing_reservation = PurchaseCheckout.all_objects.get(organization=organization)
    fake_client.create_checkout_session = provider_create  # type: ignore[method-assign]
    checkout_url = create_checkout_session(
        user,
        plan,
        "https://app.example.com/billing/purchase/success",
        "https://app.example.com/billing/purchase/cancel",
        organization=organization,
        stripe_client=fake_client,
    )

    preparing_reservation.refresh_from_db()
    assert checkout_url == "https://checkout.stripe.test/session/123"
    assert preparing_reservation.status == PurchaseCheckout.Status.OPEN
    assert preparing_reservation.stripe_checkout_session_id == "cs_test_123"
    assert PurchaseCheckout.all_objects.filter(organization=organization).count() == 1
    first_payload, second_payload = fake_client.created_checkout_payloads
    assert first_payload["idempotency_key"] == second_payload["idempotency_key"]
    assert first_payload["session_metadata"] == second_payload["session_metadata"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("event_type", "expected_status", "expected_balance"),
    [
        (
            "checkout.session.completed",
            PurchaseCheckout.Status.COMPLETED,
            250,
        ),
        ("checkout.session.expired", PurchaseCheckout.Status.EXPIRED, None),
    ],
    ids=["completed", "expired"],
)
def test_response_lost_purchase_checkout_reaches_terminal_state_from_webhook(
    user,
    organization,
    org_context,
    monkeypatch: pytest.MonkeyPatch,
    event_type: str,
    expected_status: str,
    expected_balance: int | None,
) -> None:
    suffix = event_type.rsplit(".", maxsplit=1)[-1]
    plan = _create_one_time_plan(
        slug=f"response-lost-{suffix}",
        price_id=f"price_response_lost_{suffix}",
    )
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
    provider_create = fake_client.create_checkout_session

    def create_then_lose_response(**kwargs: Any) -> dict[str, Any]:
        provider_create(**kwargs)
        raise RuntimeError("provider response lost")

    fake_client.create_checkout_session = create_then_lose_response  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="response lost"):
        create_checkout_session(
            user,
            plan,
            "https://app.example.com/billing/purchase/success",
            "https://app.example.com/billing/purchase/cancel",
            organization=organization,
            stripe_client=fake_client,
        )

    reservation = PurchaseCheckout.all_objects.get(organization=organization)
    created_payload = fake_client.created_checkout_payloads[0]
    assert reservation.status == PurchaseCheckout.Status.PREPARING
    assert reservation.stripe_checkout_session_id is None
    assert created_payload["idempotency_key"]
    event_id = f"evt_response_lost_{suffix}"
    fake_client.event = _checkout_session_completed_event(
        event_id=event_id,
        checkout_session_id=f"cs_response_lost_{suffix}",
        customer_id="cus_created_1",
        payment_intent_id=f"pi_response_lost_{suffix}",
        metadata=created_payload["session_metadata"],
    )
    fake_client.event["type"] = event_type
    monkeypatch.setenv(
        "QUICKSCALE_BILLING_WEBHOOK_SECRET",
        f"whsec_response_lost_{suffix}",
    )

    result = handle_stripe_event(
        body=f'{{"id":"{event_id}"}}'.encode(),
        signature="t=1,v1=test-signature",
        stripe_client=fake_client,
    )

    reservation.refresh_from_db()
    assert result.status == "processed"
    assert reservation.status == expected_status
    assert reservation.stripe_checkout_session_id == f"cs_response_lost_{suffix}"
    if expected_balance is None:
        assert not CreditBalance.all_objects.filter(organization=organization).exists()
    else:
        assert (
            CreditBalance.all_objects.get(organization=organization).balance
            == expected_balance
        )
    assert (
        reconcile_purchase_checkouts_for_removal(
            organization.pk,
            persist=True,
            stripe_client=fake_client,
        )
        == ()
    )


@pytest.mark.django_db
def test_create_checkout_session_persists_provider_id_when_url_is_missing(
    user,
    organization,
    org_context,
) -> None:
    plan = _create_one_time_plan(slug="checkout-missing-url")
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
    fake_client.create_checkout_session = lambda **kwargs: {  # type: ignore[method-assign]
        "id": "cs_missing_url"
    }

    with pytest.raises(BillingError, match="did not return a hosted URL"):
        create_checkout_session(
            user,
            plan,
            "https://app.example.com/billing/purchase/success",
            "https://app.example.com/billing/purchase/cancel",
            organization=organization,
            stripe_client=fake_client,
        )

    reservation = PurchaseCheckout.all_objects.get(organization=organization)
    assert reservation.status == PurchaseCheckout.Status.OPEN
    assert reservation.stripe_checkout_session_id == "cs_missing_url"


@pytest.mark.django_db(transaction=True)
def test_purchase_checkout_creation_holds_provider_mutation_lock(
    user,
    organization,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two one-time Checkout attempts for one org cannot overlap."""
    import concurrent.futures
    import threading

    from django.db import close_old_connections

    plan = _create_one_time_plan(slug="purchase-provider-lock")
    first_entered = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()
    call_count = 0
    call_count_lock = threading.Lock()

    def fake_create(*args, **kwargs) -> str:
        del args, kwargs
        nonlocal call_count
        with call_count_lock:
            call_count += 1
            call_number = call_count
        if call_number == 1:
            first_entered.set()
            if not release_first.wait(timeout=10):
                raise AssertionError("timed out waiting to release first checkout")
        else:
            second_entered.set()
        return f"https://checkout.example.com/{call_number}"

    monkeypatch.setattr(billing_services, "_create_checkout_session", fake_create)

    def create_checkout() -> str:
        close_old_connections()
        try:
            return billing_services.create_checkout_session(
                user,
                plan,
                "https://app.example.com/success",
                "https://app.example.com/cancel",
                organization=organization,
            )
        finally:
            close_old_connections()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(create_checkout)
        assert first_entered.wait(timeout=10)
        second_future = executor.submit(create_checkout)
        assert not second_entered.wait(timeout=0.5)
        release_first.set()
        assert first_future.result(timeout=10).endswith("/1")
        assert second_future.result(timeout=10).endswith("/2")

    assert second_entered.is_set()


@pytest.mark.django_db
@pytest.mark.parametrize("persist", [False, True], ids=["dry-run", "persist"])
def test_purchase_checkout_removal_reconciliation_accepts_only_provider_expiry(
    user,
    organization,
    org_context,
    persist: bool,
) -> None:
    plan = _create_one_time_plan(slug=f"reconcile-expired-{persist}")
    checkout_id = f"cs_reconcile_expired_{persist}"
    reservation = PurchaseCheckout.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_checkout_session_id=checkout_id,
        status=PurchaseCheckout.Status.OPEN,
        checkout_expires_at=timezone.now() - timezone.timedelta(minutes=1),
    )
    fake_client = FakePurchaseStripeClient(
        checkout_sessions={checkout_id: {"id": checkout_id, "status": "expired"}}
    )

    expired_ids = reconcile_purchase_checkouts_for_removal(
        organization.pk,
        persist=persist,
        stripe_client=fake_client,
    )
    reservation.refresh_from_db()

    assert expired_ids == (checkout_id,)
    assert reservation.status == (
        PurchaseCheckout.Status.EXPIRED if persist else PurchaseCheckout.Status.OPEN
    )
    assert fake_client.retrieved_checkout_session_ids == [checkout_id]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("provider_status", "message"),
    [("open", "is still open"), ("complete", "may require credit synchronization")],
)
def test_purchase_checkout_removal_reconciliation_rejects_live_provider_state(
    user,
    organization,
    org_context,
    provider_status: str,
    message: str,
) -> None:
    plan = _create_one_time_plan(slug=f"reconcile-{provider_status}")
    checkout_id = f"cs_reconcile_{provider_status}"
    PurchaseCheckout.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_checkout_session_id=checkout_id,
        status=PurchaseCheckout.Status.OPEN,
    )
    fake_client = FakePurchaseStripeClient(
        checkout_sessions={checkout_id: {"id": checkout_id, "status": provider_status}}
    )

    with pytest.raises(BillingValidationError, match=message):
        reconcile_purchase_checkouts_for_removal(
            organization.pk,
            persist=True,
            stripe_client=fake_client,
        )


@pytest.mark.django_db
def test_purchase_checkout_removal_reconciliation_rejects_preparing_reservation(
    user,
    organization,
    org_context,
) -> None:
    plan = _create_one_time_plan(slug="reconcile-preparing")
    PurchaseCheckout.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        status=PurchaseCheckout.Status.PREPARING,
    )

    with pytest.raises(BillingError, match="still being prepared"):
        reconcile_purchase_checkouts_for_removal(
            organization.pk,
            persist=True,
            stripe_client=FakePurchaseStripeClient(),
        )


@pytest.mark.django_db
def test_create_checkout_session_rejects_non_one_time_plan(
    user, organization, org_context
) -> None:
    monthly_plan = _create_monthly_plan()

    with pytest.raises(BillingValidationError, match="one-time purchases"):
        create_checkout_session(
            user,
            monthly_plan,
            "https://app.example.com/billing/purchase/success",
            "https://app.example.com/billing/purchase/cancel",
            organization=organization,
            stripe_client=FakePurchaseStripeClient(),
        )


@pytest.mark.django_db
def test_create_checkout_session_rejects_mismatched_stripe_price(
    user, organization, org_context
) -> None:
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
            organization=organization,
            stripe_client=fake_client,
        )

    assert not PurchaseCheckout.all_objects.filter(organization=organization).exists()


@pytest.mark.django_db
def test_create_checkout_session_serializer_validates_one_time_plan() -> None:
    plan = _create_one_time_plan(slug="credits-500")
    serializer = CreateCheckoutSessionSerializer(data={"plan_slug": plan.slug})

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["plan"] == plan


@pytest.mark.django_db
def test_create_checkout_session_serializer_rejects_redirect_fields() -> None:
    plan = _create_one_time_plan(slug="credits-redirect-contract")
    serializer = CreateCheckoutSessionSerializer(
        data={
            "plan_slug": plan.slug,
            "success_url": "https://app.example.com/billing/purchase/success",
            "cancel_url": "https://app.example.com/billing/purchase/cancel",
        }
    )

    assert serializer.is_valid() is False
    assert serializer.errors == {
        "cancel_url": ["This field is not allowed."],
        "success_url": ["This field is not allowed."],
    }


@pytest.mark.django_db
def test_create_checkout_session_serializer_rejects_non_one_time_plan() -> None:
    monthly_plan = _create_monthly_plan(slug="starter-monthly-serializer")
    serializer = CreateCheckoutSessionSerializer(data={"plan_slug": monthly_plan.slug})

    assert serializer.is_valid() is False
    assert serializer.errors == {
        "plan_slug": ["Billing plan does not support one-time purchases."]
    }


@pytest.mark.django_db
def test_create_checkout_session_serializer_rejects_unknown_plan() -> None:
    serializer = CreateCheckoutSessionSerializer(data={"plan_slug": "missing-plan"})

    assert serializer.is_valid() is False
    assert serializer.errors == {"plan_slug": ["Unknown billing plan."]}


@pytest.mark.django_db
def test_create_checkout_session_serializer_rejects_inactive_plan() -> None:
    inactive_plan = _create_one_time_plan(slug="inactive-plan", is_active=False)
    serializer = CreateCheckoutSessionSerializer(data={"plan_slug": inactive_plan.slug})

    assert serializer.is_valid() is False
    assert serializer.errors == {"plan_slug": ["Billing plan is not active."]}


@pytest.mark.django_db
def test_credit_balance_serializer_serializes_balance_snapshot(
    user, organization, org_context
) -> None:
    balance = CreditBalance.all_objects.create(
        organization=organization, user=user, balance=325
    )
    serializer = CreditBalanceSerializer(balance)

    assert serializer.data["balance"] == 325
    assert serializer.data["updated_at"] is not None


@pytest.mark.django_db
def test_credit_transaction_serializer_serializes_purchase_transaction(
    user, organization, org_context
) -> None:
    transaction_row = credit_user(
        user,
        amount=125,
        organization=organization,
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
    organization,
    org_context,
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
                "quickscale_org_reference": _organization_reference(organization),
                "quickscale_user_reference": _user_reference(user),
                "quickscale_plan_slug": plan.slug,
                "quickscale_plan_credits": str(plan.credits_per_period),
                "quickscale_plan_interval": plan.billing_interval,
                "stripe_price_id": plan.stripe_price_id,
            },
        )
    )
    monkeypatch.setenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_purchase")
    reservation = PurchaseCheckout.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_checkout_session_id="cs_purchase_123",
        status=PurchaseCheckout.Status.OPEN,
    )

    result = handle_stripe_event(
        body=b'{"id":"evt_checkout_purchase"}',
        signature="t=1,v1=test-signature",
        stripe_client=fake_client,
    )

    transaction_row = CreditTransaction.all_objects.get(organization=organization)
    webhook_event = WebhookEvent.objects.get(stripe_event_id="evt_checkout_purchase")
    reservation.refresh_from_db()

    assert result.duplicate is False
    assert result.status == "processed"
    assert (
        CreditBalance.all_objects.get(organization=organization).balance
        == plan.credits_per_period
    )
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
    assert reservation.status == PurchaseCheckout.Status.COMPLETED
    assert fake_client.retrieved_payment_intent_ids == []


@pytest.mark.django_db
def test_purchase_checkout_completion_rejects_conflicting_organizations(
    user,
    organization,
    org_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_one_time_plan(
        slug="cross-org-purchase",
        price_id="price_cross_org_purchase",
    )
    conflicting_organization = type(organization).objects.create(
        name="Conflicting Purchase Org",
        slug="conflicting-purchase-org",
        stripe_customer_id="cus_cross_org_purchase",
    )
    reservation = PurchaseCheckout.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_checkout_session_id="cs_cross_org_purchase",
        status=PurchaseCheckout.Status.OPEN,
    )
    fake_client = FakePurchaseStripeClient(
        event=_checkout_session_completed_event(
            event_id="evt_cross_org_purchase",
            checkout_session_id="cs_cross_org_purchase",
            customer_id="cus_cross_org_purchase",
            payment_intent_id="pi_cross_org_purchase",
            metadata={
                "quickscale_org_reference": _organization_reference(organization),
                "quickscale_user_reference": _user_reference(user),
                "quickscale_plan_slug": plan.slug,
                "quickscale_plan_credits": str(plan.credits_per_period),
                "quickscale_plan_interval": plan.billing_interval,
                "stripe_price_id": plan.stripe_price_id,
            },
        )
    )
    monkeypatch.setenv(
        "QUICKSCALE_BILLING_WEBHOOK_SECRET",
        "whsec_cross_org_purchase",
    )

    with pytest.raises(BillingWebhookError, match="conflicting organizations"):
        handle_stripe_event(
            body=b'{"id":"evt_cross_org_purchase"}',
            signature="t=1,v1=test-signature",
            stripe_client=fake_client,
        )

    reservation.refresh_from_db()
    webhook_event = WebhookEvent.objects.get(stripe_event_id="evt_cross_org_purchase")
    assert reservation.status == PurchaseCheckout.Status.OPEN
    assert webhook_event.processed is False
    with org_scope(organization):
        assert CreditTransaction.all_objects.count() == 0
        assert CreditBalance.all_objects.count() == 0
    with org_scope(conflicting_organization):
        assert CreditTransaction.all_objects.count() == 0
        assert CreditBalance.all_objects.count() == 0


@pytest.mark.django_db
def test_handle_stripe_event_suppresses_second_checkout_session_business_object(
    user,
    organization,
    org_context,
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
                "quickscale_org_reference": _organization_reference(organization),
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
            "quickscale_org_reference": _organization_reference(organization),
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
    assert CreditTransaction.all_objects.filter(organization=organization).count() == 1
    assert (
        CreditBalance.all_objects.get(organization=organization).balance
        == plan.credits_per_period
    )
    assert WebhookEvent.objects.count() == 2


@pytest.mark.django_db
def test_handle_stripe_event_uses_payment_intent_metadata_fallback_for_purchase(
    user,
    organization,
    org_context,
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
                    "quickscale_org_reference": _organization_reference(organization),
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
    assert (
        CreditBalance.all_objects.get(organization=organization).balance
        == plan.credits_per_period
    )
    assert fake_client.retrieved_payment_intent_ids == ["pi_purchase_fallback"]


@pytest.mark.django_db
def test_handle_stripe_event_credits_purchase_from_purchase_time_metadata_when_plan_drifts(
    user,
    organization,
    org_context,
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
                "quickscale_org_reference": _organization_reference(organization),
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

    transaction_row = CreditTransaction.all_objects.get(organization=organization)
    webhook_event = WebhookEvent.objects.get(
        stripe_event_id="evt_checkout_purchase_time"
    )

    assert result.duplicate is False
    assert result.status == "processed"
    assert CreditTransaction.all_objects.filter(organization=organization).count() == 1
    assert (
        CreditBalance.all_objects.get(organization=organization).balance
        == stored_credits
    )
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
    organization,
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
        reverse("quickscale_billing:stripe_webhook"),
        data=b'{"id":"evt_view_purchase"}',
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="t=1,v1=view-purchase-signature",
    )

    assert response.status_code == 200
    assert response.json() == {"status": "accepted", "duplicate": False}


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
        reverse("quickscale_billing:stripe_webhook"),
        data=b"{}",
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="t=1,v1=view-purchase-error",
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "webhook_payload_invalid",
            "message": "Stripe checkout session payment is not settled.",
        }
    }


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
        idempotency_key="checkout-key",
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
        "idempotency_key": "checkout-key",
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
