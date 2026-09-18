"""Subscription-domain service tests for the QuickScale billing module."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import pytest
import quickscale_modules_billing.services as billing_services
from django.db import IntegrityError
from django.utils import timezone

from quickscale_modules_billing.models import (
    CreditBalance,
    CreditTransaction,
    Plan,
    Subscription,
    WebhookEvent,
)
from quickscale_modules_billing.services import (
    BillingValidationError,
    BillingWebhookError,
    StripeClient,
    create_subscription_checkout_session,
    handle_stripe_event,
)
from quickscale_modules_orgs.current_org import org_scope


def _create_recurring_plan(
    *,
    slug: str = "starter-monthly",
    price_id: str = "price_starter_monthly",
    price_cents: int = 1900,
    interval: str = Plan.BillingInterval.MONTHLY,
    is_active: bool = True,
) -> Plan:
    return Plan.objects.create(
        name="Starter Recurring",
        slug=slug,
        stripe_price_id=price_id,
        credits_per_period=100,
        price_cents=price_cents,
        currency="usd",
        billing_interval=interval,
        is_active=is_active,
    )


def _user_reference(user: Any) -> str:
    return f"{user._meta.label_lower}:{user.pk}"


def _organization_reference(organization: Any) -> str:
    return f"{organization._meta.label_lower}:{organization.pk}"


def _invoice_event(
    *,
    event_id: str,
    event_type: str,
    invoice_id: str,
    customer_id: str,
    price_id: str,
    subscription_id: str = "sub_123",
    billing_reason: str | None = "subscription_cycle",
    user_reference: str | None = None,
) -> dict[str, Any]:
    subscription_details: dict[str, Any] = {}
    if user_reference:
        subscription_details["metadata"] = {
            "quickscale_user_reference": user_reference,
        }
    invoice_object: dict[str, Any] = {
        "id": invoice_id,
        "customer": customer_id,
        "subscription": subscription_id,
        "subscription_details": subscription_details,
        "metadata": {},
        "lines": {
            "data": [
                {
                    "price": {
                        "id": price_id,
                    }
                }
            ]
        },
    }
    if billing_reason is not None:
        invoice_object["billing_reason"] = billing_reason
    return {
        "id": event_id,
        "type": event_type,
        "data": {"object": invoice_object},
    }


def _subscription_event(
    *,
    event_id: str,
    event_type: str,
    subscription_id: str,
    customer_id: str,
    price_id: str,
    status: str,
    user_reference: str | None = None,
) -> dict[str, Any]:
    metadata = {}
    if user_reference:
        metadata["quickscale_user_reference"] = user_reference
        metadata["stripe_price_id"] = price_id
    return {
        "id": event_id,
        "type": event_type,
        "data": {
            "object": {
                "id": subscription_id,
                "customer": customer_id,
                "status": status,
                "current_period_start": 1_700_000_000,
                "current_period_end": 1_700_086_400,
                "metadata": metadata,
                "items": {
                    "data": [
                        {
                            "price": {
                                "id": price_id,
                            }
                        }
                    ]
                },
            }
        },
    }


def _subscription_checkout_completed_event(
    *,
    event_id: str,
    checkout_session_id: str,
    customer_id: str,
    subscription_id: str = "",
    metadata: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": checkout_session_id,
                "mode": "subscription",
                "payment_status": "paid",
                "customer": customer_id,
                "subscription": subscription_id,
                "metadata": dict(metadata or {}),
            }
        },
    }


@dataclass
class FakeSubscriptionStripeClient:
    """Minimal Stripe fake for recurring subscription service tests."""

    prices: dict[str, dict[str, Any]] = field(default_factory=dict)
    customers: list[dict[str, Any]] = field(default_factory=list)
    checkout_sessions: dict[str, dict[str, Any]] = field(default_factory=dict)
    event: dict[str, Any] | None = None
    create_subscription_checkout_error: Exception | None = None
    searched_references: list[str] = field(default_factory=list)
    created_customers: list[dict[str, Any]] = field(default_factory=list)
    created_subscription_checkout_payloads: list[dict[str, Any]] = field(
        default_factory=list
    )
    retrieved_price_ids: list[str] = field(default_factory=list)
    retrieved_checkout_session_ids: list[str] = field(default_factory=list)
    construct_calls: list[dict[str, Any]] = field(default_factory=list)

    def search_customers(
        self,
        *,
        user_reference: str = "",
        organization_reference: str = "",
    ) -> list[dict[str, Any]]:
        self.searched_references.append(organization_reference or user_reference)
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

    def create_subscription_checkout_session(
        self,
        *,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        session_metadata: dict[str, str],
        subscription_metadata: dict[str, str],
        client_reference_id: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        self.created_subscription_checkout_payloads.append(
            {
                "customer_id": customer_id,
                "price_id": price_id,
                "success_url": success_url,
                "cancel_url": cancel_url,
                "session_metadata": dict(session_metadata),
                "subscription_metadata": dict(subscription_metadata),
                "client_reference_id": client_reference_id,
                "idempotency_key": idempotency_key or "",
            }
        )
        if self.create_subscription_checkout_error is not None:
            raise self.create_subscription_checkout_error
        return {
            "id": f"cs_sub_{len(self.created_subscription_checkout_payloads)}",
            "url": "https://checkout.stripe.test/subscription/123",
            "status": "open",
            "expires_at": 2_000_000_000,
        }

    def retrieve_checkout_session(self, *, checkout_session_id: str) -> dict[str, Any]:
        self.retrieved_checkout_session_ids.append(checkout_session_id)
        return dict(self.checkout_sessions.get(checkout_session_id, {}))

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


def _simulate_subscription_reservation_conflict(
    monkeypatch: pytest.MonkeyPatch,
    *,
    organization: Any,
    recovered_reservation: Subscription,
) -> None:
    original_resolve = billing_services._resolve_authoritative_subscription_reservation
    resolve_calls = 0

    def create_with_conflict(*args: Any, **kwargs: Any) -> Subscription:
        raise IntegrityError(
            "duplicate key value violates unique current subscription constraint"
        )

    def resolve_with_recovered_row(
        *,
        organization: Any | None = None,
        customer_id: str = "",
        for_update: bool = False,
    ) -> Subscription | None:
        nonlocal resolve_calls
        if not customer_id:
            resolve_calls += 1
            if resolve_calls == 2:
                recovered_reservation.status = Subscription.Status.INCOMPLETE
                recovered_reservation.save(update_fields=["status"])
        return original_resolve(
            organization=organization,
            customer_id=customer_id,
            for_update=for_update,
        )

    monkeypatch.setattr(Subscription.objects, "create", create_with_conflict)
    monkeypatch.setattr(Subscription.all_objects, "create", create_with_conflict)
    monkeypatch.setattr(
        billing_services,
        "_resolve_authoritative_subscription_reservation",
        resolve_with_recovered_row,
    )


@pytest.mark.django_db
def test_create_subscription_checkout_session_retries_blank_reservation_idempotently(
    user, organization, org_context
) -> None:
    plan = _create_recurring_plan()
    fake_client = FakeSubscriptionStripeClient(
        prices={
            plan.stripe_price_id: {
                "id": plan.stripe_price_id,
                "unit_amount": plan.price_cents,
                "currency": plan.currency,
                "type": "recurring",
                "recurring": {"interval": "month"},
            }
        },
        create_subscription_checkout_error=RuntimeError(
            "Stripe session creation failed."
        ),
    )

    with pytest.raises(RuntimeError, match="session creation failed"):
        create_subscription_checkout_session(
            user,
            plan,
            "https://app.example.com/billing/subscription/success",
            "https://app.example.com/billing/subscription/cancel",
            organization=organization,
            stripe_client=fake_client,
        )

    reservation = Subscription.all_objects.get(organization=organization)

    assert reservation.status == Subscription.Status.INCOMPLETE
    assert reservation.stripe_customer_id == "cus_created_1"
    assert Subscription.all_objects.filter(Subscription.current_status_q()).count() == 1

    with pytest.raises(RuntimeError, match="session creation failed"):
        create_subscription_checkout_session(
            user,
            plan,
            "https://app.example.com/billing/subscription/success",
            "https://app.example.com/billing/subscription/cancel",
            organization=organization,
            stripe_client=fake_client,
        )

    assert len(fake_client.created_subscription_checkout_payloads) == 2
    first_payload, second_payload = fake_client.created_subscription_checkout_payloads
    reservation_reference = billing_services._subscription_checkout_reference(
        reservation
    )
    assert first_payload["idempotency_key"] == second_payload["idempotency_key"]
    assert first_payload["idempotency_key"]
    assert (
        first_payload["session_metadata"]["quickscale_subscription_checkout_reference"]
        == reservation_reference
    )
    assert second_payload["session_metadata"] == first_payload["session_metadata"]


@pytest.mark.django_db
def test_subscription_checkout_retry_rejects_a_different_owner(
    user,
    organization,
    org_context,
) -> None:
    from quickscale_modules_orgs.models import OrgRole, OrganizationMembership

    plan = _create_recurring_plan(price_id="price_different_owner_retry")
    fake_client = FakeSubscriptionStripeClient(
        prices={
            plan.stripe_price_id: {
                "id": plan.stripe_price_id,
                "unit_amount": plan.price_cents,
                "currency": plan.currency,
                "type": "recurring",
                "recurring": {"interval": "month"},
            }
        },
        create_subscription_checkout_error=RuntimeError(
            "Stripe session creation failed."
        ),
    )

    with pytest.raises(RuntimeError, match="session creation failed"):
        create_subscription_checkout_session(
            user,
            plan,
            "https://app.example.com/billing/subscription/success",
            "https://app.example.com/billing/subscription/cancel",
            organization=organization,
            stripe_client=fake_client,
        )

    other_owner = type(user).objects.create_user(
        username="subscription-retry-other-owner",
        email="subscription-retry-other-owner@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=other_owner,
        organization=organization,
        role=OrgRole.OWNER,
    )

    with pytest.raises(BillingValidationError, match="current recurring subscription"):
        create_subscription_checkout_session(
            other_owner,
            plan,
            "https://app.example.com/billing/subscription/success",
            "https://app.example.com/billing/subscription/cancel",
            organization=organization,
            stripe_client=fake_client,
        )

    reservation = Subscription.all_objects.get(organization=organization)
    assert reservation.user_id == user.pk
    assert len(fake_client.created_subscription_checkout_payloads) == 1


@pytest.mark.django_db
def test_create_subscription_checkout_session_retries_after_customer_lookup_failure(
    user,
    organization,
    org_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_recurring_plan(price_id="price_customer_lookup_retry")
    fake_client = FakeSubscriptionStripeClient(
        prices={
            plan.stripe_price_id: {
                "id": plan.stripe_price_id,
                "unit_amount": plan.price_cents,
                "currency": plan.currency,
                "type": "recurring",
                "recurring": {"interval": "month"},
            }
        }
    )
    provider_search = fake_client.search_customers

    def fail_customer_lookup(**kwargs: Any) -> list[dict[str, Any]]:
        raise RuntimeError("Stripe customer lookup failed.")

    monkeypatch.setattr(fake_client, "search_customers", fail_customer_lookup)

    with pytest.raises(RuntimeError, match="customer lookup failed"):
        create_subscription_checkout_session(
            user,
            plan,
            "https://app.example.com/billing/subscription/success",
            "https://app.example.com/billing/subscription/cancel",
            organization=organization,
            stripe_client=fake_client,
        )

    reservation = Subscription.all_objects.get(organization=organization)
    assert reservation.stripe_customer_id in {None, ""}
    assert reservation.stripe_checkout_session_id in {None, ""}

    monkeypatch.setattr(fake_client, "search_customers", provider_search)
    checkout_url = create_subscription_checkout_session(
        user,
        plan,
        "https://app.example.com/billing/subscription/success",
        "https://app.example.com/billing/subscription/cancel",
        organization=organization,
        stripe_client=fake_client,
    )

    reservation.refresh_from_db()
    assert checkout_url == "https://checkout.stripe.test/subscription/123"
    assert reservation.stripe_customer_id == "cus_created_1"
    assert reservation.stripe_checkout_session_id == "cs_sub_1"
    assert Subscription.all_objects.filter(Subscription.current_status_q()).count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("event_type", "expected_status", "expected_subscription_id"),
    [
        (
            "checkout.session.completed",
            Subscription.Status.INCOMPLETE,
            "sub_response_lost_completed",
        ),
        ("checkout.session.expired", Subscription.Status.INCOMPLETE_EXPIRED, ""),
    ],
    ids=["completed", "expired"],
)
def test_response_lost_subscription_checkout_reconciles_exact_reservation(
    user,
    organization,
    org_context,
    monkeypatch: pytest.MonkeyPatch,
    event_type: str,
    expected_status: str,
    expected_subscription_id: str,
) -> None:
    suffix = event_type.rsplit(".", maxsplit=1)[-1]
    plan = _create_recurring_plan(
        slug=f"response-lost-subscription-{suffix}",
        price_id=f"price_response_lost_subscription_{suffix}",
    )
    fake_client = FakeSubscriptionStripeClient(
        prices={
            plan.stripe_price_id: {
                "id": plan.stripe_price_id,
                "unit_amount": plan.price_cents,
                "currency": plan.currency,
                "type": "recurring",
                "recurring": {"interval": "month"},
            }
        }
    )
    provider_create = fake_client.create_subscription_checkout_session

    def create_then_lose_response(**kwargs: Any) -> dict[str, Any]:
        provider_create(**kwargs)
        raise RuntimeError("provider response lost")

    fake_client.create_subscription_checkout_session = create_then_lose_response  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="response lost"):
        create_subscription_checkout_session(
            user,
            plan,
            "https://app.example.com/billing/subscription/success",
            "https://app.example.com/billing/subscription/cancel",
            organization=organization,
            stripe_client=fake_client,
        )

    reservation = Subscription.all_objects.get(organization=organization)
    created_payload = fake_client.created_subscription_checkout_payloads[0]
    reservation_reference = billing_services._subscription_checkout_reference(
        reservation
    )
    assert reservation.status == Subscription.Status.INCOMPLETE
    assert reservation.stripe_checkout_session_id in {None, ""}
    assert created_payload["idempotency_key"]
    assert (
        created_payload["session_metadata"][
            "quickscale_subscription_checkout_reference"
        ]
        == reservation_reference
    )

    event_id = f"evt_response_lost_subscription_{suffix}"
    fake_client.event = _subscription_checkout_completed_event(
        event_id=event_id,
        checkout_session_id=f"cs_response_lost_subscription_{suffix}",
        customer_id="cus_created_1",
        subscription_id=expected_subscription_id,
        metadata=created_payload["session_metadata"],
    )
    fake_client.event["type"] = event_type
    monkeypatch.setenv(
        "QUICKSCALE_BILLING_WEBHOOK_SECRET",
        f"whsec_response_lost_subscription_{suffix}",
    )

    result = handle_stripe_event(
        body=f'{{"id":"{event_id}"}}'.encode(),
        signature="t=1,v1=test-signature",
        stripe_client=fake_client,
    )

    reservation.refresh_from_db()
    assert result.status == "processed"
    assert reservation.status == expected_status
    assert str(reservation.stripe_subscription_id or "") == expected_subscription_id
    assert (
        reservation.stripe_checkout_session_id
        == f"cs_response_lost_subscription_{suffix}"
    )
    assert CreditTransaction.all_objects.count() == 0


@pytest.mark.django_db
def test_create_subscription_checkout_session_reuses_live_checkout_session_url(
    user, organization, org_context
) -> None:
    plan = _create_recurring_plan()
    live_expiry = timezone.now() + timedelta(hours=1)
    Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_customer_id="cus_live",
        stripe_checkout_session_id="cs_live",
        status=Subscription.Status.INCOMPLETE,
        checkout_expires_at=live_expiry,
    )
    fake_client = FakeSubscriptionStripeClient(
        prices={
            plan.stripe_price_id: {
                "id": plan.stripe_price_id,
                "unit_amount": plan.price_cents,
                "currency": plan.currency,
                "type": "recurring",
                "recurring": {"interval": "month"},
            }
        },
        checkout_sessions={
            "cs_live": {
                "id": "cs_live",
                "url": "https://checkout.stripe.test/subscription/live",
                "status": "open",
                "expires_at": int((timezone.now() + timedelta(hours=1)).timestamp()),
            }
        },
    )

    checkout_url = create_subscription_checkout_session(
        user,
        plan,
        "https://app.example.com/billing/subscription/success",
        "https://app.example.com/billing/subscription/cancel",
        organization=organization,
        stripe_client=fake_client,
    )

    assert checkout_url == "https://checkout.stripe.test/subscription/live"
    assert fake_client.retrieved_checkout_session_ids == ["cs_live"]
    assert fake_client.created_subscription_checkout_payloads == []
    assert Subscription.all_objects.filter(Subscription.current_status_q()).count() == 1


@pytest.mark.django_db
def test_create_subscription_checkout_session_expires_stale_reservation_and_recreates(
    user, organization, org_context
) -> None:
    plan = _create_recurring_plan()
    stale_reservation = Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_customer_id="cus_stale",
        stripe_checkout_session_id="cs_stale",
        status=Subscription.Status.INCOMPLETE,
        checkout_expires_at=timezone.now() - timedelta(minutes=5),
    )
    fake_client = FakeSubscriptionStripeClient(
        prices={
            plan.stripe_price_id: {
                "id": plan.stripe_price_id,
                "unit_amount": plan.price_cents,
                "currency": plan.currency,
                "type": "recurring",
                "recurring": {"interval": "month"},
            }
        },
        checkout_sessions={
            "cs_stale": {
                "id": "cs_stale",
                "status": "expired",
            }
        },
    )

    checkout_url = create_subscription_checkout_session(
        user,
        plan,
        "https://app.example.com/billing/subscription/success",
        "https://app.example.com/billing/subscription/cancel",
        organization=organization,
        stripe_client=fake_client,
    )

    stale_reservation.refresh_from_db()
    current_reservation = Subscription.all_objects.filter(
        Subscription.current_status_q()
    ).get(organization=organization)

    assert checkout_url == "https://checkout.stripe.test/subscription/123"
    assert stale_reservation.status == Subscription.Status.INCOMPLETE_EXPIRED
    assert current_reservation.pk != stale_reservation.pk
    assert current_reservation.stripe_customer_id == "cus_stale"
    assert current_reservation.stripe_checkout_session_id == "cs_sub_1"
    assert fake_client.retrieved_checkout_session_ids == ["cs_stale"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("stripe_price", "message"),
    [
        (
            {
                "unit_amount": 2900,
                "currency": "usd",
                "type": "recurring",
                "recurring": {"interval": "month"},
            },
            "price does not match",
        ),
        (
            {
                "unit_amount": 1900,
                "currency": "eur",
                "type": "recurring",
                "recurring": {"interval": "month"},
            },
            "currency does not match",
        ),
        (
            {
                "unit_amount": 1900,
                "currency": "usd",
                "type": "one_time",
            },
            "recurring Stripe price",
        ),
        (
            {
                "unit_amount": 1900,
                "currency": "usd",
                "type": "recurring",
                "recurring": {"interval": "year"},
            },
            "billing interval does not match",
        ),
    ],
)
def test_create_subscription_checkout_session_rejects_price_parity_mismatches(
    user,
    organization,
    stripe_price: dict[str, Any],
    message: str,
) -> None:
    plan = _create_recurring_plan()
    fake_client = FakeSubscriptionStripeClient(
        prices={
            plan.stripe_price_id: {
                "id": plan.stripe_price_id,
                **stripe_price,
            }
        }
    )

    with pytest.raises(BillingValidationError, match=message):
        create_subscription_checkout_session(
            user,
            plan,
            "https://app.example.com/billing/subscription/success",
            "https://app.example.com/billing/subscription/cancel",
            organization=organization,
            stripe_client=fake_client,
        )

    assert Subscription.all_objects.count() == 0


@pytest.mark.django_db
def test_create_subscription_checkout_session_reuses_customer_on_recreated_reservation(
    user, organization, org_context
) -> None:
    plan = _create_recurring_plan()
    Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_customer_id="cus_survivor",
        stripe_subscription_id="sub_historical",
        status=Subscription.Status.CANCELED,
    )
    Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_customer_id="cus_survivor",
        status=Subscription.Status.INCOMPLETE_EXPIRED,
    )
    fake_client = FakeSubscriptionStripeClient(
        prices={
            plan.stripe_price_id: {
                "id": plan.stripe_price_id,
                "unit_amount": plan.price_cents,
                "currency": plan.currency,
                "type": "recurring",
                "recurring": {"interval": "month"},
            }
        }
    )

    checkout_url = create_subscription_checkout_session(
        user,
        plan,
        "https://app.example.com/billing/subscription/success",
        "https://app.example.com/billing/subscription/cancel",
        organization=organization,
        stripe_client=fake_client,
    )

    current_reservation = Subscription.all_objects.filter(
        Subscription.current_status_q()
    ).get(organization=organization)

    assert checkout_url == "https://checkout.stripe.test/subscription/123"
    assert current_reservation.stripe_customer_id == "cus_survivor"
    assert fake_client.searched_references == []
    assert fake_client.created_customers == []


@pytest.mark.django_db
def test_create_subscription_checkout_session_reuses_live_reservation_after_create_race(
    user,
    organization,
    org_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_recurring_plan()
    recovered_reservation = Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_customer_id="cus_race",
        stripe_checkout_session_id="cs_race",
        status=Subscription.Status.CANCELED,
        checkout_expires_at=timezone.now() + timedelta(hours=1),
    )
    fake_client = FakeSubscriptionStripeClient(
        prices={
            plan.stripe_price_id: {
                "id": plan.stripe_price_id,
                "unit_amount": plan.price_cents,
                "currency": plan.currency,
                "type": "recurring",
                "recurring": {"interval": "month"},
            }
        },
        checkout_sessions={
            "cs_race": {
                "id": "cs_race",
                "url": "https://checkout.stripe.test/subscription/race",
                "status": "open",
                "expires_at": int((timezone.now() + timedelta(hours=1)).timestamp()),
            }
        },
    )
    _simulate_subscription_reservation_conflict(
        monkeypatch,
        organization=organization,
        recovered_reservation=recovered_reservation,
    )

    checkout_url = create_subscription_checkout_session(
        user,
        plan,
        "https://app.example.com/billing/subscription/success",
        "https://app.example.com/billing/subscription/cancel",
        organization=organization,
        stripe_client=fake_client,
    )

    recovered_reservation.refresh_from_db()

    assert checkout_url == "https://checkout.stripe.test/subscription/race"
    assert recovered_reservation.status == Subscription.Status.INCOMPLETE
    assert (
        Subscription.all_objects.filter(Subscription.current_status_q())
        .get(organization=organization)
        .pk
        == recovered_reservation.pk
    )
    assert fake_client.created_subscription_checkout_payloads == []
    assert fake_client.retrieved_checkout_session_ids == ["cs_race"]


@pytest.mark.django_db
def test_create_subscription_checkout_session_raises_validation_error_after_create_race(
    user,
    organization,
    org_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_recurring_plan()
    conflicting_plan = _create_recurring_plan(
        slug="pro-monthly",
        price_id="price_pro_monthly",
        price_cents=2900,
    )
    conflicting_reservation = Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=conflicting_plan,
        stripe_customer_id="cus_conflict",
        stripe_checkout_session_id="cs_conflict",
        status=Subscription.Status.CANCELED,
        checkout_expires_at=timezone.now() + timedelta(hours=1),
    )
    fake_client = FakeSubscriptionStripeClient(
        prices={
            plan.stripe_price_id: {
                "id": plan.stripe_price_id,
                "unit_amount": plan.price_cents,
                "currency": plan.currency,
                "type": "recurring",
                "recurring": {"interval": "month"},
            }
        }
    )
    _simulate_subscription_reservation_conflict(
        monkeypatch,
        organization=organization,
        recovered_reservation=conflicting_reservation,
    )

    with pytest.raises(
        BillingValidationError,
        match="User already has a current recurring subscription.",
    ):
        create_subscription_checkout_session(
            user,
            plan,
            "https://app.example.com/billing/subscription/success",
            "https://app.example.com/billing/subscription/cancel",
            organization=organization,
            stripe_client=fake_client,
        )

    conflicting_reservation.refresh_from_db()

    assert conflicting_reservation.status == Subscription.Status.CANCELED
    assert Subscription.all_objects.filter(Subscription.current_status_q()).count() == 0
    assert fake_client.created_subscription_checkout_payloads == []


@pytest.mark.django_db
def test_create_subscription_checkout_session_blocks_completed_reservation(
    user,
    organization,
    org_context,
) -> None:
    plan = _create_recurring_plan()
    completed_reservation = Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_customer_id="cus_complete",
        stripe_checkout_session_id="cs_complete",
        status=Subscription.Status.INCOMPLETE,
        checkout_expires_at=timezone.now() + timedelta(hours=1),
    )
    fake_client = FakeSubscriptionStripeClient(
        prices={
            plan.stripe_price_id: {
                "id": plan.stripe_price_id,
                "unit_amount": plan.price_cents,
                "currency": plan.currency,
                "type": "recurring",
                "recurring": {"interval": "month"},
            }
        },
        checkout_sessions={
            "cs_complete": {
                "id": "cs_complete",
                "url": "https://checkout.stripe.test/subscription/complete",
                "status": "complete",
                "subscription": "sub_complete",
                "expires_at": int((timezone.now() + timedelta(hours=1)).timestamp()),
            }
        },
    )

    with pytest.raises(BillingValidationError, match="checkout completed"):
        create_subscription_checkout_session(
            user,
            plan,
            "https://app.example.com/billing/subscription/success",
            "https://app.example.com/billing/subscription/cancel",
            organization=organization,
            stripe_client=fake_client,
        )

    completed_reservation.refresh_from_db()

    assert completed_reservation.status == Subscription.Status.INCOMPLETE
    assert completed_reservation.stripe_subscription_id == "sub_complete"
    assert completed_reservation.checkout_expires_at is None
    assert Subscription.all_objects.filter(Subscription.current_status_q()).count() == 1
    assert fake_client.created_subscription_checkout_payloads == []
    assert fake_client.retrieved_checkout_session_ids == ["cs_complete"]


@pytest.mark.django_db
def test_completed_checkout_retrieval_rejects_customer_identity_conflict(
    user,
    organization,
    org_context,
) -> None:
    plan = _create_recurring_plan(price_id="price_complete_customer_conflict")
    organization.stripe_customer_id = "cus_complete_expected"
    organization.save(update_fields=["stripe_customer_id"])
    original_expiry = timezone.now() + timedelta(hours=1)
    reservation = Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_customer_id="cus_complete_expected",
        stripe_checkout_session_id="cs_complete_customer_conflict",
        status=Subscription.Status.INCOMPLETE,
        checkout_expires_at=original_expiry,
    )
    fake_client = FakeSubscriptionStripeClient(
        prices={
            plan.stripe_price_id: {
                "id": plan.stripe_price_id,
                "unit_amount": plan.price_cents,
                "currency": plan.currency,
                "type": "recurring",
                "recurring": {"interval": "month"},
            }
        },
        checkout_sessions={
            "cs_complete_customer_conflict": {
                "id": "cs_complete_customer_conflict",
                "status": "complete",
                "customer": "cus_complete_conflict",
                "subscription": "sub_complete_conflict",
            }
        },
    )

    with pytest.raises(BillingWebhookError, match="provider identity conflicts"):
        create_subscription_checkout_session(
            user,
            plan,
            "https://app.example.com/billing/subscription/success",
            "https://app.example.com/billing/subscription/cancel",
            organization=organization,
            stripe_client=fake_client,
        )

    reservation.refresh_from_db()
    organization.refresh_from_db()
    assert reservation.stripe_subscription_id in {None, ""}
    assert reservation.stripe_customer_id == "cus_complete_expected"
    assert reservation.checkout_expires_at == original_expiry
    assert organization.stripe_customer_id == "cus_complete_expected"
    assert fake_client.created_subscription_checkout_payloads == []


@pytest.mark.django_db
def test_handle_stripe_event_updates_pending_row_on_subscription_created(
    user,
    organization,
    org_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_recurring_plan(price_id="price_created")
    pending_reservation = Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_customer_id="cus_created",
        stripe_checkout_session_id="cs_created",
        status=Subscription.Status.INCOMPLETE,
    )
    sub_created_event = _subscription_event(
        event_id="evt_subscription_created",
        event_type="customer.subscription.created",
        subscription_id="sub_created",
        customer_id="cus_created",
        price_id=plan.stripe_price_id,
        status="active",
    )
    sub_created_event["data"]["object"]["metadata"]["quickscale_org_reference"] = (
        _organization_reference(organization)
    )
    fake_client = FakeSubscriptionStripeClient(
        event=sub_created_event,
    )
    monkeypatch.setenv(
        "QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_subscription_created"
    )

    result = handle_stripe_event(
        body=b'{"id":"evt_subscription_created"}',
        signature="t=1,v1=test-signature",
        stripe_client=fake_client,
    )

    pending_reservation.refresh_from_db()

    assert result.status == "processed"
    assert Subscription.all_objects.filter(Subscription.current_status_q()).count() == 1
    assert pending_reservation.status == Subscription.Status.ACTIVE
    assert pending_reservation.stripe_subscription_id == "sub_created"
    assert pending_reservation.current_period_start is not None
    assert pending_reservation.current_period_end is not None


@pytest.mark.django_db
def test_delayed_subscription_event_preserves_authoritative_customer_identity(
    user,
    organization,
    org_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_recurring_plan(price_id="price_delayed_customer")
    organization.stripe_customer_id = "cus_current_customer"
    organization.save(update_fields=["stripe_customer_id"])
    Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_customer_id="cus_current_customer",
        stripe_subscription_id="sub_current_customer",
        status=Subscription.Status.ACTIVE,
    )
    historical_subscription = Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_customer_id="cus_historical_customer",
        stripe_subscription_id="sub_historical_customer",
        status=Subscription.Status.CANCELED,
    )
    event = _subscription_event(
        event_id="evt_delayed_historical_subscription",
        event_type="customer.subscription.deleted",
        subscription_id="sub_historical_customer",
        customer_id="cus_historical_customer",
        price_id=plan.stripe_price_id,
        status="canceled",
    )
    event["data"]["object"]["metadata"]["quickscale_org_reference"] = (
        _organization_reference(organization)
    )
    fake_client = FakeSubscriptionStripeClient(event=event)
    monkeypatch.setenv(
        "QUICKSCALE_BILLING_WEBHOOK_SECRET",
        "whsec_delayed_historical_subscription",
    )

    with pytest.raises(BillingWebhookError, match="organization's current"):
        handle_stripe_event(
            body=b'{"id":"evt_delayed_historical_subscription"}',
            signature="t=1,v1=test-signature",
            stripe_client=fake_client,
        )

    organization.refresh_from_db()
    historical_subscription.refresh_from_db()
    webhook_event = WebhookEvent.objects.get(
        stripe_event_id="evt_delayed_historical_subscription"
    )
    assert organization.stripe_customer_id == "cus_current_customer"
    assert historical_subscription.stripe_customer_id == "cus_historical_customer"
    assert historical_subscription.stripe_subscription_id == "sub_historical_customer"
    assert webhook_event.processed is False


@pytest.mark.django_db
def test_handle_stripe_event_reconciles_incomplete_reservation_before_crediting(
    user,
    organization,
    org_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_recurring_plan(price_id="price_invoice_first_incomplete")
    pending_reservation = Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_customer_id="cus_invoice_first_incomplete",
        stripe_checkout_session_id="cs_invoice_first_incomplete",
        status=Subscription.Status.INCOMPLETE,
    )
    reconcile_event = _invoice_event(
        event_id="evt_invoice_first_incomplete",
        event_type="invoice.paid",
        invoice_id="in_invoice_first_incomplete",
        customer_id="cus_invoice_first_incomplete",
        price_id=plan.stripe_price_id,
        subscription_id="sub_invoice_first_incomplete",
        billing_reason="subscription_create",
    )
    reconcile_event["data"]["object"]["metadata"]["quickscale_org_reference"] = (
        _organization_reference(organization)
    )
    fake_client = FakeSubscriptionStripeClient(
        event=reconcile_event,
    )
    monkeypatch.setenv(
        "QUICKSCALE_BILLING_WEBHOOK_SECRET",
        "whsec_invoice_first_incomplete",
    )

    paid_result = handle_stripe_event(
        body=b'{"id":"evt_invoice_first_incomplete"}',
        signature="t=1,v1=test-signature",
        stripe_client=fake_client,
    )

    pending_reservation.refresh_from_db()

    assert paid_result.status == "processed"
    assert Subscription.all_objects.filter(Subscription.current_status_q()).count() == 1
    assert (
        Subscription.all_objects.filter(Subscription.current_status_q())
        .get(organization=organization)
        .pk
        == pending_reservation.pk
    )
    assert pending_reservation.status == Subscription.Status.ACTIVE
    assert pending_reservation.stripe_subscription_id == "sub_invoice_first_incomplete"
    assert (
        CreditBalance.all_objects.get(organization=organization).balance
        == plan.credits_per_period
    )

    fake_client.event = _subscription_event(
        event_id="evt_invoice_first_incomplete_late_update",
        event_type="customer.subscription.updated",
        subscription_id="sub_invoice_first_incomplete",
        customer_id="cus_invoice_first_incomplete",
        price_id=plan.stripe_price_id,
        status="active",
    )
    updated_result = handle_stripe_event(
        body=b'{"id":"evt_invoice_first_incomplete_late_update"}',
        signature="t=1,v1=test-signature",
        stripe_client=fake_client,
    )

    pending_reservation.refresh_from_db()

    assert updated_result.status == "processed"
    assert Subscription.all_objects.filter(Subscription.current_status_q()).count() == 1
    assert (
        Subscription.all_objects.filter(Subscription.current_status_q())
        .get(organization=organization)
        .pk
        == pending_reservation.pk
    )
    assert pending_reservation.current_period_start is not None
    assert pending_reservation.current_period_end is not None
    assert CreditTransaction.all_objects.filter(organization=organization).count() == 1


@pytest.mark.django_db
def test_handle_stripe_event_marks_subscription_past_due_on_payment_failed(
    user,
    organization,
    org_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_recurring_plan(price_id="price_failed")
    subscription = Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_customer_id="cus_failed",
        stripe_subscription_id="sub_failed",
        status=Subscription.Status.ACTIVE,
    )
    past_due_event = _invoice_event(
        event_id="evt_payment_failed",
        event_type="invoice.payment_failed",
        invoice_id="in_payment_failed",
        customer_id="cus_failed",
        price_id=plan.stripe_price_id,
        subscription_id="sub_failed",
    )
    past_due_event["data"]["object"]["metadata"]["quickscale_org_reference"] = (
        _organization_reference(organization)
    )
    fake_client = FakeSubscriptionStripeClient(
        event=past_due_event,
    )
    monkeypatch.setenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_payment_failed")

    result = handle_stripe_event(
        body=b'{"id":"evt_payment_failed"}',
        signature="t=1,v1=test-signature",
        stripe_client=fake_client,
    )

    subscription.refresh_from_db()

    assert result.status == "processed"
    assert subscription.status == Subscription.Status.PAST_DUE


@pytest.mark.django_db
def test_invoice_payment_failed_rejects_conflicting_provider_identity(
    user,
    organization,
    org_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_recurring_plan(price_id="price_failed_identity_conflict")
    organization.stripe_customer_id = "cus_current_identity"
    organization.save(update_fields=["stripe_customer_id"])
    subscription = Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_customer_id="cus_current_identity",
        stripe_subscription_id="sub_current_identity",
        status=Subscription.Status.ACTIVE,
    )
    event = _invoice_event(
        event_id="evt_failed_identity_conflict",
        event_type="invoice.payment_failed",
        invoice_id="in_failed_identity_conflict",
        customer_id="cus_conflicting_identity",
        price_id=plan.stripe_price_id,
        subscription_id="sub_conflicting_identity",
    )
    event["data"]["object"]["metadata"]["quickscale_org_reference"] = (
        _organization_reference(organization)
    )
    fake_client = FakeSubscriptionStripeClient(event=event)
    monkeypatch.setenv(
        "QUICKSCALE_BILLING_WEBHOOK_SECRET",
        "whsec_failed_identity_conflict",
    )

    with pytest.raises(BillingWebhookError, match="failed invoice conflicts"):
        handle_stripe_event(
            body=b'{"id":"evt_failed_identity_conflict"}',
            signature="t=1,v1=test-signature",
            stripe_client=fake_client,
        )

    subscription.refresh_from_db()
    organization.refresh_from_db()
    webhook_event = WebhookEvent.objects.get(
        stripe_event_id="evt_failed_identity_conflict"
    )
    assert subscription.status == Subscription.Status.ACTIVE
    assert subscription.stripe_subscription_id == "sub_current_identity"
    assert subscription.stripe_customer_id == "cus_current_identity"
    assert organization.stripe_customer_id == "cus_current_identity"
    assert webhook_event.processed is False


@pytest.mark.django_db
def test_handle_stripe_event_recovers_after_payment_failed_and_resync(
    user,
    organization,
    org_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_recurring_plan(price_id="price_recovery")
    subscription = Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_customer_id="cus_recovery",
        stripe_subscription_id="sub_recovery",
        status=Subscription.Status.ACTIVE,
    )
    monkeypatch.setenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_recovery")
    fake_client = FakeSubscriptionStripeClient(
        event=_invoice_event(
            event_id="evt_failed_recovery",
            user_reference=_user_reference(user),
            event_type="invoice.payment_failed",
            invoice_id="in_failed_recovery",
            customer_id="cus_recovery",
            price_id=plan.stripe_price_id,
            subscription_id="sub_recovery",
        )
    )

    failed_result = handle_stripe_event(
        body=b'{"id":"evt_failed_recovery"}',
        signature="t=1,v1=test-signature",
        stripe_client=fake_client,
    )

    fake_client.event = _subscription_event(
        event_id="evt_resynced_active",
        event_type="customer.subscription.updated",
        subscription_id="sub_recovery",
        customer_id="cus_recovery",
        price_id=plan.stripe_price_id,
        status="active",
    )
    updated_result = handle_stripe_event(
        body=b'{"id":"evt_resynced_active"}',
        signature="t=1,v1=test-signature",
        stripe_client=fake_client,
    )

    fake_client.event = _invoice_event(
        event_id="evt_paid_recovery",
        event_type="invoice.paid",
        invoice_id="in_paid_recovery",
        customer_id="cus_recovery",
        price_id=plan.stripe_price_id,
        subscription_id="sub_recovery",
        billing_reason="subscription_cycle",
    )
    paid_result = handle_stripe_event(
        body=b'{"id":"evt_paid_recovery"}',
        signature="t=1,v1=test-signature",
        stripe_client=fake_client,
    )

    subscription.refresh_from_db()

    assert failed_result.status == "processed"
    assert updated_result.status == "processed"
    assert paid_result.status == "processed"
    assert subscription.status == Subscription.Status.ACTIVE
    assert (
        CreditBalance.all_objects.get(organization=organization).balance
        == plan.credits_per_period
    )
    assert CreditTransaction.all_objects.filter(organization=organization).count() == 1


@pytest.mark.django_db
def test_handle_stripe_event_recovers_after_payment_failed_on_later_invoice_paid(
    user,
    organization,
    org_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_recurring_plan(price_id="price_recovery_invoice_paid")
    subscription = Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_customer_id="cus_recovery_invoice_paid",
        stripe_subscription_id="sub_recovery_invoice_paid",
        status=Subscription.Status.ACTIVE,
    )
    monkeypatch.setenv(
        "QUICKSCALE_BILLING_WEBHOOK_SECRET",
        "whsec_recovery_invoice_paid",
    )
    fake_client = FakeSubscriptionStripeClient(
        event=_invoice_event(
            event_id="evt_failed_recovery_invoice_paid",
            event_type="invoice.payment_failed",
            invoice_id="in_failed_recovery_invoice_paid",
            customer_id="cus_recovery_invoice_paid",
            price_id=plan.stripe_price_id,
            subscription_id="sub_recovery_invoice_paid",
        )
    )

    failed_result = handle_stripe_event(
        body=b'{"id":"evt_failed_recovery_invoice_paid"}',
        signature="t=1,v1=test-signature",
        stripe_client=fake_client,
    )

    fake_client.event = _invoice_event(
        event_id="evt_paid_recovery_invoice_paid",
        event_type="invoice.paid",
        invoice_id="in_paid_recovery_invoice_paid",
        customer_id="cus_recovery_invoice_paid",
        price_id=plan.stripe_price_id,
        subscription_id="sub_recovery_invoice_paid",
        billing_reason="subscription_cycle",
    )
    paid_result = handle_stripe_event(
        body=b'{"id":"evt_paid_recovery_invoice_paid"}',
        signature="t=1,v1=test-signature",
        stripe_client=fake_client,
    )

    subscription.refresh_from_db()

    assert failed_result.status == "processed"
    assert paid_result.status == "processed"
    assert subscription.status == Subscription.Status.ACTIVE
    assert (
        CreditBalance.all_objects.get(organization=organization).balance
        == plan.credits_per_period
    )
    assert CreditTransaction.all_objects.filter(organization=organization).count() == 1


@pytest.mark.django_db
def test_handle_stripe_event_rejects_unsupported_subscription_status(
    user,
    organization,
    org_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_recurring_plan(price_id="price_future")
    Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_customer_id="cus_future",
        stripe_subscription_id="sub_future",
        status=Subscription.Status.ACTIVE,
    )
    fake_client = FakeSubscriptionStripeClient(
        event=_subscription_event(
            event_id="evt_future_status",
            event_type="customer.subscription.updated",
            subscription_id="sub_future",
            customer_id="cus_future",
            price_id=plan.stripe_price_id,
            status="future_state",
        )
    )
    monkeypatch.setenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_future_status")

    with pytest.raises(BillingWebhookError, match="not supported"):
        handle_stripe_event(
            body=b'{"id":"evt_future_status"}',
            signature="t=1,v1=test-signature",
            stripe_client=fake_client,
        )

    webhook_event = WebhookEvent.objects.get(stripe_event_id="evt_future_status")

    assert webhook_event.processed is False
    assert "not supported" in webhook_event.processing_error


@pytest.mark.django_db
def test_handle_stripe_event_does_not_credit_subscription_checkout_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = FakeSubscriptionStripeClient(
        event=_subscription_checkout_completed_event(
            event_id="evt_subscription_checkout_completed",
            checkout_session_id="cs_subscription_completed",
            customer_id="cus_subscription_completed",
        )
    )
    monkeypatch.setenv(
        "QUICKSCALE_BILLING_WEBHOOK_SECRET",
        "whsec_subscription_checkout_completed",
    )

    result = handle_stripe_event(
        body=b'{"id":"evt_subscription_checkout_completed"}',
        signature="t=1,v1=test-signature",
        stripe_client=fake_client,
    )

    assert result.status == "processed"
    assert CreditTransaction.all_objects.count() == 0


@pytest.mark.django_db
def test_subscription_checkout_completion_binds_provider_identity_before_webhook(
    user,
    organization,
    org_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_recurring_plan(price_id="price_checkout_completion_identity")
    organization.stripe_customer_id = "cus_checkout_completion_identity"
    organization.save(update_fields=["stripe_customer_id"])
    reservation = Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_customer_id="cus_checkout_completion_identity",
        stripe_checkout_session_id="cs_checkout_completion_identity",
        checkout_expires_at=timezone.now() - timedelta(minutes=5),
        status=Subscription.Status.INCOMPLETE,
    )
    fake_client = FakeSubscriptionStripeClient(
        event=_subscription_checkout_completed_event(
            event_id="evt_checkout_completion_identity",
            checkout_session_id="cs_checkout_completion_identity",
            customer_id="cus_checkout_completion_identity",
            subscription_id="sub_checkout_completion_identity",
        )
    )
    monkeypatch.setenv(
        "QUICKSCALE_BILLING_WEBHOOK_SECRET",
        "whsec_checkout_completion_identity",
    )

    result = handle_stripe_event(
        body=b'{"id":"evt_checkout_completion_identity"}',
        signature="t=1,v1=test-signature",
        stripe_client=fake_client,
    )

    reservation.refresh_from_db()
    assert result.status == "processed"
    assert reservation.stripe_subscription_id == "sub_checkout_completion_identity"
    assert CreditTransaction.all_objects.count() == 0


@pytest.mark.django_db
def test_subscription_checkout_completion_rejects_customer_identity_conflict(
    user,
    organization,
    org_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_recurring_plan(price_id="price_checkout_customer_conflict")
    organization.stripe_customer_id = "cus_checkout_expected"
    organization.save(update_fields=["stripe_customer_id"])
    reservation = Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_customer_id="cus_checkout_expected",
        stripe_checkout_session_id="cs_checkout_customer_conflict",
        status=Subscription.Status.INCOMPLETE,
    )
    event = _subscription_checkout_completed_event(
        event_id="evt_checkout_customer_conflict",
        checkout_session_id="cs_checkout_customer_conflict",
        customer_id="cus_checkout_conflict",
        subscription_id="sub_checkout_conflict",
    )
    event["data"]["object"]["metadata"] = {
        "quickscale_org_reference": _organization_reference(organization)
    }
    fake_client = FakeSubscriptionStripeClient(event=event)
    monkeypatch.setenv(
        "QUICKSCALE_BILLING_WEBHOOK_SECRET",
        "whsec_checkout_customer_conflict",
    )

    with pytest.raises(BillingWebhookError, match="provider identity conflicts"):
        handle_stripe_event(
            body=b'{"id":"evt_checkout_customer_conflict"}',
            signature="t=1,v1=test-signature",
            stripe_client=fake_client,
        )

    reservation.refresh_from_db()
    organization.refresh_from_db()
    webhook_event = WebhookEvent.objects.get(
        stripe_event_id="evt_checkout_customer_conflict"
    )
    assert reservation.stripe_subscription_id in {None, ""}
    assert reservation.stripe_customer_id == "cus_checkout_expected"
    assert organization.stripe_customer_id == "cus_checkout_expected"
    assert webhook_event.processed is False


@pytest.mark.django_db
def test_subscription_checkout_completion_rejects_conflicting_organizations(
    user,
    organization,
    org_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_recurring_plan(price_id="price_cross_org_subscription")
    organization.stripe_customer_id = "cus_cross_org_subscription_expected"
    organization.save(update_fields=["stripe_customer_id"])
    conflicting_organization = type(organization).objects.create(
        name="Conflicting Subscription Org",
        slug="conflicting-subscription-org",
        stripe_customer_id="cus_cross_org_subscription",
    )
    reservation = Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_customer_id="cus_cross_org_subscription_expected",
        stripe_checkout_session_id="cs_cross_org_subscription",
        status=Subscription.Status.INCOMPLETE,
    )
    event = _subscription_checkout_completed_event(
        event_id="evt_cross_org_subscription",
        checkout_session_id="cs_cross_org_subscription",
        customer_id="cus_cross_org_subscription",
        subscription_id="sub_cross_org_subscription",
    )
    event["data"]["object"]["metadata"] = {
        "quickscale_org_reference": _organization_reference(organization)
    }
    fake_client = FakeSubscriptionStripeClient(event=event)
    monkeypatch.setenv(
        "QUICKSCALE_BILLING_WEBHOOK_SECRET",
        "whsec_cross_org_subscription",
    )

    with pytest.raises(BillingWebhookError, match="conflicting organizations"):
        handle_stripe_event(
            body=b'{"id":"evt_cross_org_subscription"}',
            signature="t=1,v1=test-signature",
            stripe_client=fake_client,
        )

    reservation.refresh_from_db()
    webhook_event = WebhookEvent.objects.get(
        stripe_event_id="evt_cross_org_subscription"
    )
    assert reservation.stripe_subscription_id in {None, ""}
    assert reservation.stripe_customer_id == "cus_cross_org_subscription_expected"
    assert reservation.status == Subscription.Status.INCOMPLETE
    assert webhook_event.processed is False
    with org_scope(organization):
        assert CreditTransaction.all_objects.count() == 0
    with org_scope(conflicting_organization):
        assert CreditTransaction.all_objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("billing_reason", "event_id", "invoice_id"),
    [
        ("manual", "evt_manual_invoice", "in_manual_invoice"),
        ("", "evt_blank_reason_invoice", "in_blank_reason_invoice"),
        (None, "evt_missing_reason_invoice", "in_missing_reason_invoice"),
    ],
    ids=["manual", "blank", "missing"],
)
def test_handle_stripe_event_ignores_non_creditable_invoice_paid_reason(
    user,
    organization,
    org_context,
    monkeypatch: pytest.MonkeyPatch,
    billing_reason: str | None,
    event_id: str,
    invoice_id: str,
) -> None:
    plan = _create_recurring_plan(price_id="price_manual_invoice")
    Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_customer_id="cus_manual_invoice",
        stripe_subscription_id="sub_manual_invoice",
        status=Subscription.Status.ACTIVE,
    )
    fake_client = FakeSubscriptionStripeClient(
        event=_invoice_event(
            event_id=event_id,
            event_type="invoice.paid",
            invoice_id=invoice_id,
            customer_id="cus_manual_invoice",
            price_id=plan.stripe_price_id,
            subscription_id="sub_manual_invoice",
            billing_reason=billing_reason,
        )
    )
    monkeypatch.setenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_manual_invoice")

    result = handle_stripe_event(
        body=f'{{"id":"{event_id}"}}'.encode("utf-8"),
        signature="t=1,v1=test-signature",
        stripe_client=fake_client,
    )

    assert result.status == "processed"
    assert CreditTransaction.all_objects.count() == 0
    assert CreditBalance.all_objects.count() == 0


def test_stripe_client_create_subscription_checkout_session_uses_checkout_api() -> None:
    stripe_module = SimpleNamespace(
        api_key="",
        checkout=SimpleNamespace(
            Session=SimpleNamespace(
                create=lambda **kwargs: {
                    "id": "cs_subscription_created",
                    "url": "https://checkout.stripe.test/subscription/created",
                    **kwargs,
                },
                retrieve=lambda checkout_session_id: {"id": checkout_session_id},
            )
        ),
    )
    stripe_client = StripeClient(stripe_module=stripe_module, api_key="sk_test")

    checkout_session = stripe_client.create_subscription_checkout_session(
        customer_id="cus_wrapper",
        price_id="price_wrapper",
        success_url="https://app.example.com/billing/subscription/success",
        cancel_url="https://app.example.com/billing/subscription/cancel",
        session_metadata={"quickscale_user_reference": "auth.user:1"},
        subscription_metadata={"quickscale_user_reference": "auth.user:1"},
        client_reference_id="auth.user:1",
        idempotency_key="subscription-checkout-key",
    )

    assert checkout_session == {
        "id": "cs_subscription_created",
        "url": "https://checkout.stripe.test/subscription/created",
        "mode": "subscription",
        "customer": "cus_wrapper",
        "line_items": [{"price": "price_wrapper", "quantity": 1}],
        "success_url": "https://app.example.com/billing/subscription/success",
        "cancel_url": "https://app.example.com/billing/subscription/cancel",
        "client_reference_id": "auth.user:1",
        "metadata": {"quickscale_user_reference": "auth.user:1"},
        "subscription_data": {"metadata": {"quickscale_user_reference": "auth.user:1"}},
        "idempotency_key": "subscription-checkout-key",
    }
    assert stripe_module.api_key == "sk_test"


def test_stripe_client_retrieve_checkout_session_returns_normalized_mapping() -> None:
    stripe_module = SimpleNamespace(
        api_key="",
        checkout=SimpleNamespace(
            Session=SimpleNamespace(
                create=lambda **kwargs: {"id": "unused"},
                retrieve=lambda checkout_session_id: {
                    "id": checkout_session_id,
                    "url": "https://checkout.stripe.test/subscription/retrieved",
                    "status": "open",
                },
            )
        ),
    )
    stripe_client = StripeClient(stripe_module=stripe_module, api_key="sk_test")

    checkout_session = stripe_client.retrieve_checkout_session(
        checkout_session_id="cs_retrieved"
    )

    assert checkout_session == {
        "id": "cs_retrieved",
        "url": "https://checkout.stripe.test/subscription/retrieved",
        "status": "open",
    }
    assert stripe_module.api_key == "sk_test"
