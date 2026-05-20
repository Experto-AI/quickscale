"""Focused tests for org billing bridge management commands."""

from __future__ import annotations

from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command

from quickscale_modules_billing.models import (
    CreditBalance,
    CreditTransaction,
    Plan,
    Subscription,
)
from quickscale_modules_orgs.models import OrgRole, Organization, OrganizationMembership


def _create_plan(*, slug: str, price_id: str) -> Plan:
    return Plan.objects.create(
        name="Growth",
        slug=slug,
        stripe_price_id=price_id,
        credits_per_period=250,
        price_cents=4900,
        currency="usd",
        billing_interval=Plan.BillingInterval.MONTHLY,
    )


@pytest.mark.django_db
def test_migrate_billing_to_orgs_creates_personal_org_and_is_idempotent() -> None:
    user = get_user_model().objects.create_user(
        username="builder",
        email="builder@example.com",
        password="secret123",
    )
    plan = _create_plan(
        slug="growth-migrate-personal", price_id="price_growth_migrate_personal"
    )
    subscription = Subscription.objects.create(
        user=user,
        plan=plan,
        stripe_subscription_id="sub_builder",
        stripe_customer_id="cus_builder",
        status=Subscription.Status.ACTIVE,
    )
    balance = CreditBalance.objects.create(user=user, balance=75)
    transaction_row = CreditTransaction.objects.create(
        user=user,
        amount=25,
        transaction_type=CreditTransaction.TransactionType.PURCHASE,
        description="Builder bridge",
        balance_after=75,
    )

    first_stdout = StringIO()
    call_command(
        "migrate_billing_to_orgs",
        stdout=first_stdout,
        stderr=StringIO(),
        verbosity=0,
    )

    organization = Organization.objects.get(is_personal=True, memberships__user=user)
    subscription.refresh_from_db()
    balance.refresh_from_db()
    transaction_row.refresh_from_db()

    assert subscription.organization == organization
    assert balance.organization == organization
    assert transaction_row.organization == organization
    assert organization.stripe_customer_id == "cus_builder"
    assert (
        OrganizationMembership.objects.get(user=user, organization=organization).role
        == OrgRole.OWNER
    )
    assert "user=builder" in first_stdout.getvalue()
    assert "created_personal_org=yes" in first_stdout.getvalue()

    second_stdout = StringIO()
    call_command(
        "migrate_billing_to_orgs",
        stdout=second_stdout,
        stderr=StringIO(),
        verbosity=0,
    )

    assert (
        Organization.objects.filter(is_personal=True, memberships__user=user).count()
        == 1
    )
    assert (
        OrganizationMembership.objects.filter(
            user=user, organization=organization
        ).count()
        == 1
    )
    assert "subscriptions_updated=0" in second_stdout.getvalue()
    assert "balances_updated=0" in second_stdout.getvalue()
    assert "transactions_updated=0" in second_stdout.getvalue()


@pytest.mark.django_db
def test_migrate_billing_to_orgs_reuses_sole_existing_membership() -> None:
    user = get_user_model().objects.create_user(
        username="member-bridge",
        email="member-bridge@example.com",
        password="secret123",
    )
    plan = _create_plan(
        slug="growth-migrate-sole", price_id="price_growth_migrate_sole"
    )
    organization = Organization.objects.create(name="Atlas", slug="atlas")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    subscription = Subscription.objects.create(
        user=user,
        plan=plan,
        stripe_subscription_id="sub_member_bridge",
        stripe_customer_id="cus_member_bridge",
        status=Subscription.Status.ACTIVE,
    )
    balance = CreditBalance.objects.create(user=user, balance=90)

    stdout = StringIO()
    call_command(
        "migrate_billing_to_orgs",
        stdout=stdout,
        stderr=StringIO(),
        verbosity=0,
    )

    subscription.refresh_from_db()
    balance.refresh_from_db()
    organization.refresh_from_db()

    assert subscription.organization == organization
    assert balance.organization == organization
    assert organization.stripe_customer_id == "cus_member_bridge"
    assert (
        Organization.objects.filter(is_personal=True, memberships__user=user).count()
        == 0
    )
    assert "created_personal_org=no" in stdout.getvalue()


@pytest.mark.django_db
def test_migrate_billing_to_orgs_fails_on_ambiguous_memberships_without_updates() -> (
    None
):
    user = get_user_model().objects.create_user(
        username="ambiguous-billing-user",
        email="ambiguous-billing-user@example.com",
        password="secret123",
    )
    plan = _create_plan(
        slug="growth-migrate-ambiguous", price_id="price_growth_migrate_ambiguous"
    )
    first_org = Organization.objects.create(name="Alpha", slug="alpha")
    second_org = Organization.objects.create(name="Bravo", slug="bravo")
    OrganizationMembership.objects.create(
        user=user,
        organization=first_org,
        role=OrgRole.ADMIN,
    )
    OrganizationMembership.objects.create(
        user=user,
        organization=second_org,
        role=OrgRole.MEMBER,
    )
    subscription = Subscription.objects.create(
        user=user,
        plan=plan,
        stripe_subscription_id="sub_ambiguous_billing_user",
        stripe_customer_id="cus_ambiguous_billing_user",
        status=Subscription.Status.ACTIVE,
    )

    with pytest.raises(CommandError, match="ambiguous organization memberships"):
        call_command(
            "migrate_billing_to_orgs",
            stdout=StringIO(),
            stderr=StringIO(),
            verbosity=0,
        )

    subscription.refresh_from_db()
    assert subscription.organization is None
    assert (
        Organization.objects.filter(is_personal=True, memberships__user=user).count()
        == 0
    )


@pytest.mark.django_db
def test_promote_to_saas_fills_blank_personal_slug_from_owner_and_prints_setting_reminder() -> (
    None
):
    owner = get_user_model().objects.create_user(
        username="solo-owner",
        email="solo-owner@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(
        name="Solo Owner's Org",
        slug="",
        is_personal=True,
    )
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )

    stdout = StringIO()
    call_command(
        "promote_to_saas",
        stdout=stdout,
        stderr=StringIO(),
        verbosity=0,
    )
    organization.refresh_from_db()

    assert organization.slug == "solo-owner"
    assert "personal_slug=<blank> -> solo-owner" in stdout.getvalue()
    assert "QUICKSCALE_MODE = 'saas'" in stdout.getvalue()


@pytest.mark.django_db
def test_promote_to_saas_suffixes_collisions_and_is_idempotent() -> None:
    owner = get_user_model().objects.create_user(
        username="collision-owner",
        email="collision-owner@example.com",
        password="secret123",
    )
    Organization.objects.create(name="Existing", slug="collision-owner")
    organization = Organization.objects.create(
        name="Collision Owner's Org",
        slug="",
        is_personal=True,
    )
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )

    first_stdout = StringIO()
    call_command(
        "promote_to_saas",
        stdout=first_stdout,
        stderr=StringIO(),
        verbosity=0,
    )
    organization.refresh_from_db()

    assert organization.slug == "collision-owner-2"
    assert "collision-owner-2" in first_stdout.getvalue()

    second_stdout = StringIO()
    call_command(
        "promote_to_saas",
        stdout=second_stdout,
        stderr=StringIO(),
        verbosity=0,
    )
    organization.refresh_from_db()

    assert organization.slug == "collision-owner-2"
    assert "updated 0 personal organizations" in second_stdout.getvalue().lower()
