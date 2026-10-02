"""Tests for subscription Checkout creation and provider reconciliation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from django.utils import timezone

from quickscale_modules_billing import services as billing_services
from quickscale_modules_billing.exceptions import (
    BillingError,
    BillingValidationError,
)
from quickscale_modules_billing.models import Plan, Subscription


def _create_plan(*, price_id: str = "price_checkout") -> Plan:
    return Plan.objects.create(
        name="Checkout",
        slug=f"checkout-{price_id}",
        stripe_price_id=price_id,
        credits_per_period=100,
        price_cents=1900,
        currency="usd",
        billing_interval=Plan.BillingInterval.MONTHLY,
    )


@dataclass
class _FakeCheckoutClient:
    """Minimal provider double for Checkout creation and reconciliation."""

    price: dict[str, Any] = field(default_factory=dict)
    checkout_sessions: dict[str, dict[str, Any]] = field(default_factory=dict)
    created_session: dict[str, Any] = field(default_factory=dict)
    created_customer: dict[str, Any] = field(default_factory=dict)

    def retrieve_price(self, *, price_id: str) -> dict[str, Any]:
        del price_id
        return dict(self.price)

    def retrieve_checkout_session(self, *, checkout_session_id: str) -> dict[str, Any]:
        return dict(self.checkout_sessions.get(checkout_session_id, {}))

    def create_subscription_checkout_session(self, **kwargs: Any) -> dict[str, Any]:
        del kwargs
        return dict(self.created_session)

    def search_customers(self, **kwargs: Any) -> list[dict[str, Any]]:
        del kwargs
        return []

    def create_customer(self, **kwargs: Any) -> dict[str, Any]:
        del kwargs
        return dict(self.created_customer) or {"id": "cus_created"}


def _matching_price(plan: Plan) -> dict[str, Any]:
    return {
        "unit_amount": plan.price_cents,
        "currency": plan.currency,
        "type": "recurring",
        "recurring": {"interval": "month"},
    }


def _create_reservation(
    *, user: Any, organization: Any, plan: Plan, **overrides: Any
) -> Subscription:
    values: dict[str, Any] = {
        "user": user,
        "organization": organization,
        "plan": plan,
        "status": Subscription.Status.INCOMPLETE,
    }
    values.update(overrides)
    return Subscription.all_objects.create(**values)


@pytest.mark.django_db
def test_subscription_checkout_requires_both_urls(
    user, organization, org_context
) -> None:
    plan = _create_plan()
    with pytest.raises(BillingValidationError, match="URLs are required"):
        billing_services.create_subscription_checkout_session(
            user,
            plan=plan,
            success_url="",
            cancel_url="https://app.example.com/cancel",
            organization=organization,
        )


@pytest.mark.django_db
def test_subscription_checkout_replaces_an_expired_session(
    user, organization, org_context
) -> None:
    plan = _create_plan()
    _create_reservation(
        user=user,
        organization=organization,
        plan=plan,
        stripe_checkout_session_id="cs_old",
        stripe_customer_id="cus_keep",
    )
    client = _FakeCheckoutClient(
        price=_matching_price(plan),
        checkout_sessions={"cs_old": {"id": "cs_old", "status": "expired"}},
        created_session={"id": "cs_new", "url": "https://checkout.example.com/new"},
    )

    url = billing_services.create_subscription_checkout_session(
        user,
        plan=plan,
        success_url="https://app.example.com/success",
        cancel_url="https://app.example.com/cancel",
        organization=organization,
        stripe_client=client,
    )

    assert url == "https://checkout.example.com/new"


@pytest.mark.django_db
def test_subscription_checkout_requires_a_provider_session_id(
    user, organization, org_context
) -> None:
    plan = _create_plan()
    client = _FakeCheckoutClient(
        price=_matching_price(plan),
        created_session={"url": "https://checkout.example.com/new"},
    )

    with pytest.raises(BillingError, match="did not return an id"):
        billing_services.create_subscription_checkout_session(
            user,
            plan=plan,
            success_url="https://app.example.com/success",
            cancel_url="https://app.example.com/cancel",
            organization=organization,
            stripe_client=client,
        )


@pytest.mark.django_db
def test_subscription_checkout_requires_a_provider_url(
    user, organization, org_context
) -> None:
    plan = _create_plan()
    client = _FakeCheckoutClient(
        price=_matching_price(plan),
        created_session={"id": "cs_new"},
    )

    with pytest.raises(BillingError, match="did not return a hosted URL"):
        billing_services.create_subscription_checkout_session(
            user,
            plan=plan,
            success_url="https://app.example.com/success",
            cancel_url="https://app.example.com/cancel",
            organization=organization,
            stripe_client=client,
        )


@pytest.mark.django_db
def test_account_deletion_reconciliation_without_an_organization() -> None:
    result = billing_services.reconcile_account_deletion_subscription_checkout(999999)
    assert result == billing_services.SubscriptionCheckoutReconciliation()


@pytest.mark.django_db
def test_account_deletion_reconciliation_persists_a_completed_checkout(
    user, organization, org_context
) -> None:
    plan = _create_plan()
    reservation = _create_reservation(
        user=user,
        organization=organization,
        plan=plan,
        stripe_checkout_session_id="cs_complete",
    )
    client = _FakeCheckoutClient(
        checkout_sessions={
            "cs_complete": {
                "id": "cs_complete",
                "status": "complete",
                "subscription": {"id": "sub_completed"},
                "customer": "cus_completed",
            }
        },
    )

    with pytest.raises(BillingValidationError, match="completed"):
        billing_services.reconcile_account_deletion_subscription_checkout(
            organization.pk,
            stripe_client=client,
        )

    reservation.refresh_from_db()
    assert reservation.stripe_subscription_id == "sub_completed"
    assert reservation.checkout_expires_at is None


@pytest.mark.django_db
def test_organization_removal_reconciliation_refuses_an_open_checkout(
    user, organization, org_context
) -> None:
    plan = _create_plan()
    _create_reservation(
        user=user,
        organization=organization,
        plan=plan,
        stripe_checkout_session_id="cs_open",
        checkout_expires_at=timezone.now() - timedelta(hours=1),
    )
    client = _FakeCheckoutClient(
        checkout_sessions={"cs_open": {"id": "cs_open", "status": "open"}},
    )

    with pytest.raises(BillingValidationError, match="still open"):
        billing_services.reconcile_organization_removal_subscription_checkout(
            organization.pk,
            persist=False,
            stripe_client=client,
        )


@pytest.mark.django_db
def test_organization_removal_reconciliation_refuses_an_unknown_status(
    user, organization, org_context
) -> None:
    plan = _create_plan()
    _create_reservation(
        user=user,
        organization=organization,
        plan=plan,
        stripe_checkout_session_id="cs_unknown",
        checkout_expires_at=timezone.now() - timedelta(hours=1),
    )
    client = _FakeCheckoutClient(
        checkout_sessions={"cs_unknown": {"id": "cs_unknown", "status": "mystery"}},
    )

    with pytest.raises(BillingError, match="unsupported or blank status"):
        billing_services.reconcile_organization_removal_subscription_checkout(
            organization.pk,
            persist=False,
            stripe_client=client,
        )


@pytest.mark.django_db
def test_authoritative_reservation_requires_a_selector() -> None:
    assert billing_services._resolve_authoritative_subscription_reservation() is None


@pytest.mark.django_db
def test_subscription_reservation_reuse_requires_incomplete_status(
    user, organization, org_context
) -> None:
    plan = _create_plan()
    reservation = _create_reservation(
        user=user,
        organization=organization,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        stripe_subscription_id="sub_active",
    )

    assert (
        billing_services._subscription_reservation_can_be_reused(reservation, plan=plan)
        is False
    )


@pytest.mark.django_db
def test_subscription_reservation_without_expiry_is_not_replaced(
    user, organization, org_context
) -> None:
    plan = _create_plan()
    reservation = _create_reservation(
        user=user,
        organization=organization,
        plan=plan,
        stripe_checkout_session_id="cs_nonexpiring",
    )

    assert (
        billing_services._subscription_reservation_needs_replacement(reservation)
        is False
    )


@pytest.mark.django_db
def test_conflicting_reservation_recovery_returns_none(
    user, organization, org_context
) -> None:
    plan = _create_plan()

    assert (
        billing_services._recover_conflicting_subscription_reservation(
            user=user,
            organization=organization,
            plan=plan,
        )
        is None
    )

    _create_reservation(
        user=user,
        organization=organization,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        stripe_subscription_id="sub_taken",
    )

    assert (
        billing_services._recover_conflicting_subscription_reservation(
            user=user,
            organization=organization,
            plan=plan,
        )
        is None
    )


@pytest.mark.django_db
def test_prepare_reservation_refuses_a_bound_subscription(
    user, organization, org_context
) -> None:
    plan = _create_plan()
    _create_reservation(
        user=user,
        organization=organization,
        plan=plan,
        stripe_subscription_id="sub_bound",
    )

    with pytest.raises(BillingValidationError, match="current recurring subscription"):
        billing_services._prepare_subscription_checkout_reservation(
            user=user,
            organization=organization,
            plan=plan,
        )


@pytest.mark.django_db
def test_prepare_reservation_replaces_an_elapsed_checkout(
    user, organization, org_context
) -> None:
    plan = _create_plan()
    expired = _create_reservation(
        user=user,
        organization=organization,
        plan=plan,
        stripe_checkout_session_id="cs_elapsed",
        checkout_expires_at=timezone.now() - timedelta(hours=1),
        stripe_customer_id="cus_keep",
    )

    reservation, created = billing_services._prepare_subscription_checkout_reservation(
        user=user,
        organization=organization,
        plan=plan,
    )

    assert created is False
    assert reservation.pk != expired.pk
    assert reservation.stripe_customer_id == "cus_keep"
    expired.refresh_from_db()
    assert expired.status == Subscription.Status.INCOMPLETE_EXPIRED


@pytest.mark.django_db
def test_reuse_live_checkout_requires_retrieval_support(
    user, organization, org_context
) -> None:
    plan = _create_plan()
    reservation = _create_reservation(
        user=user,
        organization=organization,
        plan=plan,
        stripe_checkout_session_id="cs_any",
    )

    with pytest.raises(BillingError, match="retrieval is unavailable"):
        billing_services._reuse_live_subscription_checkout_url(
            reservation=reservation,
            stripe_client=SimpleNamespace(),
        )


@pytest.mark.django_db
def test_reuse_live_checkout_returns_empty_for_an_expired_session(
    user, organization, org_context
) -> None:
    plan = _create_plan()
    reservation = _create_reservation(
        user=user,
        organization=organization,
        plan=plan,
        stripe_checkout_session_id="cs_expired",
    )
    client = _FakeCheckoutClient(
        checkout_sessions={"cs_expired": {"id": "cs_expired", "status": "expired"}},
    )

    assert (
        billing_services._reuse_live_subscription_checkout_url(
            reservation=reservation,
            stripe_client=client,
        )
        == ""
    )


@pytest.mark.django_db
def test_reuse_live_checkout_refuses_an_unknown_status(
    user, organization, org_context
) -> None:
    plan = _create_plan()
    reservation = _create_reservation(
        user=user,
        organization=organization,
        plan=plan,
        stripe_checkout_session_id="cs_unknown",
    )
    client = _FakeCheckoutClient(
        checkout_sessions={"cs_unknown": {"id": "cs_unknown", "status": "mystery"}},
    )

    with pytest.raises(BillingError, match="unsupported or blank status"):
        billing_services._reuse_live_subscription_checkout_url(
            reservation=reservation,
            stripe_client=client,
        )


@pytest.mark.django_db
def test_reuse_live_checkout_refuses_an_open_session_without_a_url(
    user, organization, org_context
) -> None:
    plan = _create_plan()
    reservation = _create_reservation(
        user=user,
        organization=organization,
        plan=plan,
        stripe_checkout_session_id="cs_open",
    )
    client = _FakeCheckoutClient(
        checkout_sessions={"cs_open": {"id": "cs_open", "status": "open"}},
    )

    with pytest.raises(BillingError, match="did not return a reusable hosted URL"):
        billing_services._reuse_live_subscription_checkout_url(
            reservation=reservation,
            stripe_client=client,
        )
