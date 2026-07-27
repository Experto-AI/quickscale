"""Tests for billing module models and metadata."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

import quickscale_modules_billing
from quickscale_modules_billing.models import (
    CreditBalance,
    CreditTransaction,
    Plan,
    Subscription,
    WebhookEvent,
)
from quickscale_modules_orgs.current_org import org_scope
from quickscale_modules_orgs.models import Organization


def test_package_version_is_exposed() -> None:
    assert quickscale_modules_billing.__version__ == "0.87.0"


@pytest.mark.django_db(transaction=True)
def test_credit_balance_get_or_create_for_org_is_transaction_ready(
    user, organization, org_context
) -> None:
    with transaction.atomic():
        balance, created = CreditBalance.get_or_create_for_org(organization)

    assert created is True
    assert balance.organization == organization
    assert balance.balance == 0

    with transaction.atomic():
        same_balance, created = CreditBalance.get_or_create_for_org(organization)

    assert created is False
    assert same_balance.pk == balance.pk


@pytest.mark.django_db(transaction=True)
def test_credit_balance_get_or_create_for_org_without_atomic_transaction(
    user, organization, org_context
) -> None:
    assert transaction.get_connection().in_atomic_block is False

    balance, created = CreditBalance.get_or_create_for_org(organization)

    assert created is True
    assert balance.organization == organization
    assert balance.balance == 0

    same_balance, created = CreditBalance.get_or_create_for_org(organization)

    assert created is False
    assert same_balance.pk == balance.pk


@pytest.mark.django_db
def test_model_string_representations(user, organization, org_context) -> None:
    plan = Plan.objects.create(
        name="Starter",
        slug="starter",
        stripe_price_id="price_starter_monthly",
        credits_per_period=100,
        price_cents=1900,
        currency="usd",
        billing_interval=Plan.BillingInterval.MONTHLY,
    )
    balance = CreditBalance.all_objects.create(
        organization=organization, user=user, balance=100
    )
    credit_transaction = CreditTransaction.all_objects.create(
        user=user,
        organization=organization,
        amount=100,
        transaction_type=CreditTransaction.TransactionType.PLAN,
        stripe_event_id="evt_123",
        stripe_object_id="in_123",
        stripe_reference_data={"invoice_id": "in_123"},
        description="Monthly credits",
        balance_after=100,
    )
    subscription = Subscription.all_objects.create(
        user=user,
        organization=organization,
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
    assert str(balance) == f"{organization} (100 credits)"
    assert str(credit_transaction) == f"{user} plan 100"
    assert str(subscription) == f"{organization} / starter (active)"
    assert str(webhook_event) == "invoice.paid (evt_123)"


@pytest.mark.django_db(transaction=True)
def test_credit_transaction_preserves_org_ledger_history_when_actor_is_deleted(
    user,
    organization,
    org_context,
) -> None:
    transaction_row = CreditTransaction.all_objects.create(
        user=user,
        organization=organization,
        amount=25,
        transaction_type=CreditTransaction.TransactionType.PURCHASE,
        description="Deleted user provenance",
        balance_after=25,
    )

    transaction_pk = transaction_row.pk
    user.delete()

    preserved_row = CreditTransaction.all_objects.get(pk=transaction_pk)

    assert preserved_row.user is None
    assert preserved_row.organization == organization
    assert str(preserved_row) == "TestOrg purchase 25"


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


@pytest.mark.django_db
def test_plan_features_default_to_empty_list() -> None:
    plan = Plan.objects.create(
        name="Starter",
        slug="starter-features",
        stripe_price_id="price_starter_features",
        credits_per_period=100,
        price_cents=1900,
        currency="usd",
        billing_interval=Plan.BillingInterval.MONTHLY,
    )

    assert plan.features == []


@pytest.mark.django_db
def test_subscription_current_status_helpers_and_queryset(
    user, organization, org_context
) -> None:
    user_model = get_user_model()
    other_user = user_model.objects.create_user(
        username="billing-current-other",
        email="billing-current-other@example.com",
        password="billingpass123",
    )
    other_org = Organization.objects.create(name="OtherOrg", slug="other-org")
    plan = Plan.objects.create(
        name="Growth",
        slug="growth",
        stripe_price_id="price_growth_monthly",
        credits_per_period=250,
        price_cents=4900,
        currency="usd",
        billing_interval=Plan.BillingInterval.MONTHLY,
    )
    with org_scope(organization):
        Subscription.all_objects.create(
            user=user,
            organization=organization,
            plan=plan,
            stripe_subscription_id="sub_old_canceled",
            stripe_customer_id="cus_old_canceled",
            status=Subscription.Status.CANCELED,
        )
        current_subscription = Subscription.all_objects.create(
            user=user,
            organization=organization,
            plan=plan,
            stripe_subscription_id="sub_current_active",
            stripe_customer_id="cus_current_active",
            status=Subscription.Status.ACTIVE,
        )
    with org_scope(other_org):
        current_trial = Subscription.all_objects.create(
            user=other_user,
            organization=other_org,
            plan=plan,
            stripe_subscription_id="sub_current_trial",
            stripe_customer_id="cus_current_trial",
            status=Subscription.Status.TRIALING,
        )
        Subscription.all_objects.create(
            user=other_user,
            organization=other_org,
            plan=plan,
            stripe_subscription_id="sub_expired",
            stripe_customer_id="cus_expired",
            status=Subscription.Status.INCOMPLETE_EXPIRED,
        )

    assert Subscription.current_statuses() == (
        Subscription.Status.INCOMPLETE,
        Subscription.Status.TRIALING,
        Subscription.Status.ACTIVE,
        Subscription.Status.PAST_DUE,
        Subscription.Status.UNPAID,
        Subscription.Status.PAUSED,
    )
    assert Subscription.is_current_status(Subscription.Status.ACTIVE) is True
    assert Subscription.is_current_status(Subscription.Status.PAUSED) is True
    assert Subscription.is_current_status(Subscription.Status.CANCELED) is False
    assert Subscription.is_current_status(None) is False
    with org_scope(organization):
        assert list(
            Subscription.all_objects.filter(Subscription.current_status_q())
        ) == [
            current_subscription,
        ]
    with org_scope(other_org):
        assert list(
            Subscription.all_objects.filter(Subscription.current_status_q())
        ) == [
            current_trial,
        ]


@pytest.mark.django_db(transaction=True)
def test_subscription_partial_unique_constraints_ignore_unset_external_ids(
    user,
    organization,
    org_context,
) -> None:
    user_model = get_user_model()
    other_user = user_model.objects.create_user(
        username="billing-constraint-other",
        email="billing-constraint-other@example.com",
        password="billingpass123",
    )
    duplicate_subscription_user = user_model.objects.create_user(
        username="billing-constraint-sub-duplicate",
        email="billing-constraint-sub-duplicate@example.com",
        password="billingpass123",
    )
    duplicate_session_user = user_model.objects.create_user(
        username="billing-constraint-session-duplicate",
        email="billing-constraint-session-duplicate@example.com",
        password="billingpass123",
    )
    plan = Plan.objects.create(
        name="Scale",
        slug="scale",
        stripe_price_id="price_scale_monthly",
        credits_per_period=500,
        price_cents=9900,
        currency="usd",
        billing_interval=Plan.BillingInterval.MONTHLY,
    )

    Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_subscription_id=None,
        stripe_customer_id=None,
        stripe_checkout_session_id=None,
        status=Subscription.Status.CANCELED,
    )
    Subscription.all_objects.create(
        user=other_user,
        organization=organization,
        plan=plan,
        stripe_subscription_id=None,
        stripe_customer_id=None,
        stripe_checkout_session_id=None,
        status=Subscription.Status.INCOMPLETE_EXPIRED,
    )
    Subscription.all_objects.create(
        user=other_user,
        organization=organization,
        plan=plan,
        stripe_subscription_id="sub_populated_unique",
        stripe_customer_id="cus_populated_unique",
        stripe_checkout_session_id="cs_populated_unique",
        status=Subscription.Status.CANCELED,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        Subscription.all_objects.create(
            user=duplicate_subscription_user,
            organization=organization,
            plan=plan,
            stripe_subscription_id="sub_populated_unique",
            stripe_customer_id="cus_duplicate_subscription",
            status=Subscription.Status.CANCELED,
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        Subscription.all_objects.create(
            user=duplicate_session_user,
            organization=organization,
            plan=plan,
            stripe_subscription_id="sub_session_unique",
            stripe_customer_id="cus_duplicate_session",
            stripe_checkout_session_id="cs_populated_unique",
            status=Subscription.Status.CANCELED,
        )


@pytest.mark.django_db(transaction=True)
def test_credit_balance_enforces_single_authoritative_row_per_organization(
    user,
    organization,
    org_context,
) -> None:
    other_user = get_user_model().objects.create_user(
        username="billing-balance-other",
        email="billing-balance-other@example.com",
        password="billingpass123",
    )

    CreditBalance.all_objects.create(
        organization=organization,
        user=user,
        balance=100,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        CreditBalance.all_objects.create(
            organization=organization,
            user=other_user,
            balance=50,
        )


@pytest.mark.django_db(transaction=True)
def test_credit_balance_supports_org_authority_with_nullable_user_provenance(
    organization,
    org_context,
) -> None:
    balance = CreditBalance.all_objects.create(
        organization=organization,
        user=None,
        balance=25,
    )

    assert balance.organization == organization
    assert balance.user is None


@pytest.mark.django_db(transaction=True)
def test_subscription_enforces_single_current_row_per_organization(
    user,
    organization,
    org_context,
) -> None:
    plan = Plan.objects.create(
        name="Enterprise",
        slug="enterprise",
        stripe_price_id="price_enterprise_monthly",
        credits_per_period=1000,
        price_cents=19900,
        currency="usd",
        billing_interval=Plan.BillingInterval.MONTHLY,
    )
    other_organization = Organization.objects.create(name="Nova", slug="nova")
    other_user = get_user_model().objects.create_user(
        username="billing-org-constraint-other",
        email="billing-org-constraint-other@example.com",
        password="billingpass123",
    )

    Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_subscription_id=None,
        stripe_customer_id=None,
        stripe_checkout_session_id="cs_pending_current",
        status=Subscription.Status.INCOMPLETE,
    )

    with org_scope(other_organization):
        Subscription.all_objects.create(
            user=user,
            organization=other_organization,
            plan=plan,
            stripe_subscription_id="sub_second_org",
            stripe_customer_id="cus_second_org",
            status=Subscription.Status.ACTIVE,
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        Subscription.all_objects.create(
            user=other_user,
            organization=organization,
            plan=plan,
            stripe_subscription_id="sub_second_current",
            stripe_customer_id="cus_second_current",
            status=Subscription.Status.ACTIVE,
        )

    Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_subscription_id="sub_terminal_history",
        stripe_customer_id="cus_terminal_history",
        status=Subscription.Status.CANCELED,
    )
