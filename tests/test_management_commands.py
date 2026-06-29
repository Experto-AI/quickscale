"""Focused tests for org management commands including AF3 operator-access seam."""

from __future__ import annotations

import uuid as uuid_lib
import logging
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.utils import timezone

from quickscale_modules_billing.models import (
    CreditBalance,
    CreditTransaction,
    Plan,
    Subscription,
)
from quickscale_modules_orgs.management.commands.purge_organization import Command
from quickscale_modules_orgs.models import (
    OrgRole,
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
    OrganizationTombstone,
)


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
    if not Subscription._meta.get_field("organization").null:
        pytest.skip(
            "Pre-migration scenario (billing rows without org) cannot exist — "
            "organization_id is NOT NULL via tenant_org_fk after RLS migration."
        )
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
    if not Subscription._meta.get_field("organization").null:
        pytest.skip(
            "Pre-migration scenario (billing rows without org) cannot exist — "
            "organization_id is NOT NULL via tenant_org_fk after RLS migration."
        )
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
    if not Subscription._meta.get_field("organization").null:
        pytest.skip(
            "Pre-migration scenario (billing rows without org) cannot exist — "
            "organization_id is NOT NULL via tenant_org_fk after RLS migration."
        )
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


# ---------------------------------------------------------------------------
# AF3 phase 3 — migrate_billing_to_orgs current-schema seam tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_migrate_billing_to_orgs_current_schema_success(caplog) -> None:
    """migrate_billing_to_orgs succeeds when billing rows already have orgs.

    Current schema organisation_id is NOT NULL.  Billing rows already carry
    an organisation FK.  The command should still run without errors, report
    zero ``*_updated``, sync the ``stripe_customer_id`` from billing rows,
    and emit a ``succeeded`` audit record.
    """
    caplog.set_level(logging.INFO)

    user = get_user_model().objects.create_user(
        username="current-schema",
        email="current-schema@example.com",
        password="secret123",
    )
    org = Organization.objects.create(name="Current Schema", slug="current-schema")
    OrganizationMembership.objects.create(
        user=user,
        organization=org,
        role=OrgRole.OWNER,
    )
    plan = _create_plan(
        slug="growth-current-schema", price_id="price_growth_current_schema"
    )
    Subscription.objects.create(
        user=user,
        organization=org,
        plan=plan,
        stripe_subscription_id="sub_current_schema",
        stripe_customer_id="cus_current_schema",
        status=Subscription.Status.ACTIVE,
    )
    CreditBalance.objects.create(user=user, organization=org, balance=50)
    CreditTransaction.objects.create(
        user=user,
        organization=org,
        amount=50,
        transaction_type=CreditTransaction.TransactionType.PURCHASE,
        description="Current schema test",
        balance_after=50,
    )

    stdout = StringIO()
    call_command(
        "migrate_billing_to_orgs",
        stdout=stdout,
        stderr=StringIO(),
        verbosity=0,
    )

    output = stdout.getvalue()
    assert "subscriptions_updated=0" in output
    assert "balances_updated=0" in output
    assert "transactions_updated=0" in output
    assert "current-schema" in output
    assert "completed" in output

    # stripe_customer_id should be synced since the org had none.
    org.refresh_from_db()
    assert org.stripe_customer_id == "cus_current_schema"

    # Verify the operator-access audit log.
    msgs = [r.getMessage() for r in caplog.records]
    matching = [
        m
        for m in msgs
        if "operator_access:" in m and "command=migrate_billing_to_orgs" in m
    ]
    assert len(matching) >= 1, f"No audit log found in: {msgs}"
    msg = matching[-1]
    assert "status=succeeded" in msg
    assert "scope=all_billing_users" in msg
    assert "error_class=" in msg
    assert str(org.pk) in msg


@pytest.mark.django_db
def test_migrate_billing_to_orgs_current_schema_failure(caplog) -> None:
    """When billing users have ambiguous org memberships, the command raises
    ``CommandError``, leaves associations unchanged, and records
    ``status="failed"`` with ``error_class``."""
    caplog.set_level(logging.INFO)

    user = get_user_model().objects.create_user(
        username="ambiguous-current",
        email="ambiguous-current@example.com",
        password="secret123",
    )
    first_org = Organization.objects.create(name="First Current", slug="first-current")
    second_org = Organization.objects.create(
        name="Second Current", slug="second-current"
    )
    OrganizationMembership.objects.create(
        user=user,
        organization=first_org,
        role=OrgRole.MEMBER,
    )
    OrganizationMembership.objects.create(
        user=user,
        organization=second_org,
        role=OrgRole.MEMBER,
    )
    plan = _create_plan(
        slug="growth-current-fail", price_id="price_growth_current_fail"
    )
    Subscription.objects.create(
        user=user,
        organization=first_org,
        plan=plan,
        stripe_subscription_id="sub_current_fail",
        stripe_customer_id="cus_current_fail",
        status=Subscription.Status.ACTIVE,
    )

    stdout = StringIO()
    stderr = StringIO()
    with pytest.raises(CommandError, match="ambiguous organization memberships"):
        call_command(
            "migrate_billing_to_orgs",
            stdout=stdout,
            stderr=stderr,
            verbosity=0,
        )

    # Verify billing ownership is unchanged after the failure.
    sub = Subscription.all_objects.get(stripe_subscription_id="sub_current_fail")
    assert sub.organization_id == first_org.pk, (
        "Subscription must still point at first_org after failed migration"
    )

    # Verify the operator-access audit log records the failure with
    # non-empty org attribution (pre-populated before the ambiguity check).
    msgs = [r.getMessage() for r in caplog.records]
    matching = [
        m
        for m in msgs
        if "operator_access:" in m and "command=migrate_billing_to_orgs" in m
    ]
    assert len(matching) >= 1, f"No audit log found in: {msgs}"
    msg = matching[-1]
    assert "status=failed" in msg
    assert "error_class=CommandError" in msg
    # At least the ambiguous user's billing org should appear in
    # target_orgs since it was set before the CommandError.
    assert f"target_orgs={first_org.pk}" in msg, (
        f"Expected target_orgs to contain first_org PK in: {msg}"
    )
    assert "touched_orgs=" in msg


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


# ---------------------------------------------------------------------------
# T1.17 — purge_organization contract tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_purge_organization_requires_uuid_or_slug() -> None:
    """purge_organization must error when neither --organization-id nor --slug is provided."""
    stdout = StringIO()
    stderr = StringIO()
    with pytest.raises(CommandError, match="Specify --organization-id"):
        call_command(
            "purge_organization",
            stdout=stdout,
            stderr=stderr,
            verbosity=0,
        )


@pytest.mark.django_db
def test_purge_organization_rejects_combined_targeting_flags() -> None:
    """purge_organization must error when both --organization-id and --slug are given."""
    organization = Organization.objects.create(name="Test", slug="test")
    stdout = StringIO()
    stderr = StringIO()
    with pytest.raises(CommandError, match="Cannot combine"):
        call_command(
            "purge_organization",
            organization_id=str(organization.pk),
            slug="test",
            stdout=stdout,
            stderr=stderr,
            verbosity=0,
        )


@pytest.mark.django_db
def test_purge_organization_slug_preflight_is_non_destructive() -> None:
    """--slug must only look up and print counts, never delete."""
    owner = get_user_model().objects.create_user(
        username="purge-preflight-owner",
        email="purge-preflight-owner@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(
        name="Preflight Test", slug="preflight-test"
    )
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    OrganizationInvitation.objects.create(
        organization=organization,
        email="invitee@example.com",
        role=OrgRole.ADMIN,
        invited_by=owner,
        expires_at=timezone.now() + timezone.timedelta(days=1),
    )

    stdout = StringIO()
    call_command(
        "purge_organization",
        slug="preflight-test",
        stdout=stdout,
        stderr=StringIO(),
        verbosity=0,
    )

    output = stdout.getvalue()
    assert "Preflight" in output
    assert "Organization memberships: 1" in output
    assert "Organization invitations: 1" in output
    # Verify no deletion occurred.
    assert Organization.objects.filter(pk=organization.pk).exists()
    assert OrganizationMembership.objects.filter(organization=organization).count() == 1
    assert OrganizationInvitation.objects.filter(organization=organization).count() == 1


@pytest.mark.django_db
def test_purge_organization_slug_preflight_fails_on_missing_slug() -> None:
    """--slug must error when the slug does not match any organization."""
    stdout = StringIO()
    stderr = StringIO()
    with pytest.raises(CommandError, match="No organization found with slug"):
        call_command(
            "purge_organization",
            slug="nonexistent-slug",
            stdout=stdout,
            stderr=stderr,
            verbosity=0,
        )


@pytest.mark.django_db
def test_purge_organization_missing_uuid_no_tombstone_errors() -> None:
    """--organization-id with a live UUID miss and no tombstone must error."""
    missing_uuid = "00000000-0000-0000-0000-000000000001"
    stdout = StringIO()
    stderr = StringIO()
    with pytest.raises(CommandError, match="No organization found with UUID"):
        call_command(
            "purge_organization",
            organization_id=missing_uuid,
            stdout=stdout,
            stderr=stderr,
            verbosity=0,
        )


@pytest.mark.django_db
def test_purge_organization_missing_uuid_with_tombstone_is_noop() -> None:
    """--organization-id with a tombstoned UUID must return no-op success."""
    purged_org_id = uuid_lib.uuid4()
    OrganizationTombstone.objects.create(organization_id=purged_org_id)

    stdout = StringIO()
    stderr = StringIO()
    with pytest.raises(CommandError, match="No-op"):
        call_command(
            "purge_organization",
            organization_id=str(purged_org_id),
            stdout=stdout,
            stderr=stderr,
            verbosity=0,
        )

    output = stdout.getvalue()
    assert "already purged" in output
    assert "Memberships deleted: 0" in output
    assert "Invitations deleted: 0" in output


@pytest.mark.django_db
def test_purge_organization_dry_run_is_noop() -> None:
    """--dry-run must show counts without deleting any rows."""
    owner = get_user_model().objects.create_user(
        username="dryrun-owner",
        email="dryrun-owner@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Dry Run Test", slug="dry-run-test")
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    OrganizationInvitation.objects.create(
        organization=organization,
        email="invitee@example.com",
        role=OrgRole.ADMIN,
        invited_by=owner,
        expires_at=timezone.now() + timezone.timedelta(days=1),
    )

    stdout = StringIO()
    call_command(
        "purge_organization",
        organization_id=str(organization.pk),
        dry_run=True,
        stdout=stdout,
        stderr=StringIO(),
        verbosity=0,
    )

    output = stdout.getvalue()
    assert "Dry run" in output
    assert "Organization memberships: 1" in output
    assert "Organization invitations: 1" in output
    # Verify no deletion occurred.
    assert Organization.objects.filter(pk=organization.pk).exists()
    assert OrganizationMembership.objects.filter(organization=organization).count() == 1
    assert OrganizationInvitation.objects.filter(organization=organization).count() == 1


@pytest.mark.django_db
def test_purge_organization_reserved_org_refused() -> None:
    """purge_organization must refuse to purge a reserved (System) organization."""
    system_org = Organization.objects.get_system_org()

    stdout = StringIO()
    stderr = StringIO()
    with pytest.raises(CommandError, match="Cannot purge the System organization"):
        call_command(
            "purge_organization",
            organization_id=str(system_org.pk),
            stdout=stdout,
            stderr=stderr,
            verbosity=0,
        )


@pytest.mark.django_db
def test_purge_organization_invitations_appear_in_dry_run_counts() -> None:
    """The ownership map must include OrganizationInvitation rows in dry-run output."""
    owner = get_user_model().objects.create_user(
        username="invite-counts-owner",
        email="invite-counts-owner@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(
        name="Invite Count Test", slug="invite-count-test"
    )
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    # Create multiple invitations.
    for i in range(3):
        OrganizationInvitation.objects.create(
            organization=organization,
            email=f"invitee{i}@example.com",
            role=OrgRole.ADMIN,
            invited_by=owner,
            expires_at=timezone.now() + timezone.timedelta(days=1),
        )

    stdout = StringIO()
    call_command(
        "purge_organization",
        organization_id=str(organization.pk),
        dry_run=True,
        stdout=stdout,
        stderr=StringIO(),
        verbosity=0,
    )

    output = stdout.getvalue()
    assert "Organization memberships: 1" in output
    assert "Organization invitations: 3" in output


@pytest.mark.django_db
def test_purge_organization_creates_tombstone() -> None:
    """A successful purge must create a tombstone record."""
    owner = get_user_model().objects.create_user(
        username="tombstone-test-owner",
        email="tombstone-test-owner@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(
        name="Tombstone Test", slug="tombstone-test"
    )
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    org_id = organization.pk

    stdout = StringIO()
    call_command(
        "purge_organization",
        organization_id=str(org_id),
        stdout=stdout,
        stderr=StringIO(),
        verbosity=0,
    )

    output = stdout.getvalue()
    assert "has been purged" in output
    assert "Tombstone recorded" in output
    assert not Organization.objects.filter(pk=org_id).exists()
    assert OrganizationTombstone.objects.filter(organization_id=org_id).exists()


@pytest.mark.django_db
def test_purge_organization_rerun_after_purge_is_noop() -> None:
    """Rerunning purge_organization after a successful purge must return no-op."""
    owner = get_user_model().objects.create_user(
        username="rerun-owner",
        email="rerun-owner@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Rerun Test", slug="rerun-test")
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    org_id = organization.pk

    # First run — purge.
    first_stdout = StringIO()
    call_command(
        "purge_organization",
        organization_id=str(org_id),
        stdout=first_stdout,
        stderr=StringIO(),
        verbosity=0,
    )
    assert "has been purged" in first_stdout.getvalue()
    assert OrganizationTombstone.objects.filter(organization_id=org_id).exists()

    # Second run — should be no-op.
    second_stdout = StringIO()
    second_stderr = StringIO()
    with pytest.raises(CommandError, match="No-op"):
        call_command(
            "purge_organization",
            organization_id=str(org_id),
            stdout=second_stdout,
            stderr=second_stderr,
            verbosity=0,
        )

    output = second_stdout.getvalue()
    assert "already purged" in output.lower()
    assert "Memberships deleted: 0" in output
    assert "Invitations deleted: 0" in output


@pytest.mark.django_db
def test_purge_organization_rejects_invalid_uuid_format() -> None:
    """--organization-id must reject non-UUID strings."""
    stdout = StringIO()
    stderr = StringIO()
    with pytest.raises(CommandError, match="valid UUID"):
        call_command(
            "purge_organization",
            organization_id="not-a-uuid",
            stdout=stdout,
            stderr=stderr,
            verbosity=0,
        )


@pytest.mark.django_db
def test_purge_organization_deletes_memberships_and_invitations() -> None:
    """A successful purge must delete memberships and invitations."""
    owner = get_user_model().objects.create_user(
        username="full-purge-owner",
        email="full-purge-owner@example.com",
        password="secret123",
    )
    member_user = get_user_model().objects.create_user(
        username="full-purge-member",
        email="full-purge-member@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Full Purge", slug="full-purge")
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    OrganizationMembership.objects.create(
        user=member_user,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    OrganizationInvitation.objects.create(
        organization=organization,
        email="invitee@example.com",
        role=OrgRole.ADMIN,
        invited_by=owner,
        expires_at=timezone.now() + timezone.timedelta(days=1),
    )
    org_id = organization.pk

    stdout = StringIO()
    call_command(
        "purge_organization",
        organization_id=str(org_id),
        stdout=stdout,
        stderr=StringIO(),
        verbosity=0,
    )

    output = stdout.getvalue()
    assert "has been purged" in output
    assert "Organization memberships: 2" in output
    assert "Organization invitations: 1" in output
    assert "Total rows deleted: 3" in output
    assert not Organization.objects.filter(pk=org_id).exists()
    assert OrganizationMembership.objects.filter(organization_id=org_id).count() == 0
    assert OrganizationInvitation.objects.filter(organization_id=org_id).count() == 0


# ---------------------------------------------------------------------------
# T1.17 Phase 2 — cross-module purge, rollback, and slug-reuse tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_purge_organization_with_billing_rows() -> None:
    """A successful purge must delete billing rows (CreditTransaction, Subscription, CreditBalance)."""
    from quickscale_modules_billing.models import (
        CreditBalance,
        CreditTransaction,
        Plan,
        Subscription,
    )

    owner = get_user_model().objects.create_user(
        username="billing-purge-owner",
        email="billing-purge-owner@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(
        name="Billing Purge", slug="billing-purge"
    )
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    plan = Plan.objects.create(
        name="Growth",
        slug="growth-billing-purge",
        stripe_price_id="price_growth_billing_purge",
        credits_per_period=250,
        price_cents=4900,
        currency="usd",
        billing_interval=Plan.BillingInterval.MONTHLY,
    )
    Subscription.objects.create(
        organization=organization,
        user=owner,
        plan=plan,
        stripe_subscription_id="sub_billing_purge",
        stripe_customer_id="cus_billing_purge",
        status=Subscription.Status.ACTIVE,
    )
    CreditBalance.objects.create(
        organization=organization,
        user=owner,
        balance=100,
    )
    CreditTransaction.objects.create(
        organization=organization,
        user=owner,
        amount=100,
        transaction_type=CreditTransaction.TransactionType.PURCHASE,
        description="Billing purge test",
        balance_after=100,
    )
    org_id = organization.pk

    stdout = StringIO()
    call_command(
        "purge_organization",
        organization_id=str(org_id),
        stdout=stdout,
        stderr=StringIO(),
        verbosity=0,
    )

    output = stdout.getvalue()
    assert "has been purged" in output
    assert not Organization.objects.filter(pk=org_id).exists()
    # Verify billing rows are deleted.
    assert CreditBalance.objects.filter(organization_id=org_id).count() == 0
    assert Subscription.objects.filter(organization_id=org_id).count() == 0
    assert CreditTransaction.objects.filter(organization_id=org_id).count() == 0
    # Verify tombstone.
    assert OrganizationTombstone.objects.filter(organization_id=org_id).exists()


@pytest.mark.django_db
def test_purge_organization_rollback_on_error() -> None:
    """If anything fails inside the purge transaction, all rows must remain intact."""
    from unittest.mock import patch

    from quickscale_modules_billing.models import (
        CreditBalance,
        Plan,
        Subscription,
    )

    owner = get_user_model().objects.create_user(
        username="rollback-owner",
        email="rollback-owner@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(
        name="Rollback Test", slug="rollback-test"
    )
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    plan = Plan.objects.create(
        name="Growth",
        slug="growth-rollback",
        stripe_price_id="price_growth_rollback",
        credits_per_period=250,
        price_cents=4900,
        currency="usd",
        billing_interval=Plan.BillingInterval.MONTHLY,
    )
    Subscription.objects.create(
        organization=organization,
        user=owner,
        plan=plan,
        stripe_subscription_id="sub_rollback",
        stripe_customer_id="cus_rollback",
        status=Subscription.Status.ACTIVE,
    )
    CreditBalance.objects.create(
        organization=organization,
        user=owner,
        balance=50,
    )
    org_id = organization.pk

    # Simulate a failure after some rows have been deleted by patching
    # _delete_owned_rows to raise an error midway.
    original_delete_owned = Command._delete_owned_rows

    def failing_delete(self, org):
        original_delete_owned(self, org)
        raise RuntimeError("Simulated purge failure")

    stdout = StringIO()
    stderr = StringIO()
    with (
        pytest.raises(RuntimeError, match="Simulated purge failure"),
        patch.object(Command, "_delete_owned_rows", new=failing_delete),
    ):
        call_command(
            "purge_organization",
            organization_id=str(org_id),
            stdout=stdout,
            stderr=stderr,
            verbosity=0,
        )

    # Everything must still exist after the rollback.
    # Use all_objects (super-scope bypass) since the purge finally block
    # resets the ContextVar — TenantManager.objects would return .none().
    assert Organization.objects.filter(pk=org_id).exists()
    assert OrganizationMembership.objects.filter(organization_id=org_id).count() == 1
    assert Subscription.all_objects.filter(organization_id=org_id).count() == 1
    assert CreditBalance.all_objects.filter(organization_id=org_id).count() == 1
    assert not OrganizationTombstone.objects.filter(organization_id=org_id).exists()


@pytest.mark.django_db
def test_purge_organization_slug_reuse_safe() -> None:
    """After a successful purge, a new organization with the same slug must be creatable."""
    owner = get_user_model().objects.create_user(
        username="slug-reuse-owner",
        email="slug-reuse-owner@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(
        name="Slug Reuse Test", slug="slug-reuse"
    )
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    org_id = organization.pk

    # Purge.
    call_command(
        "purge_organization",
        organization_id=str(org_id),
        stdout=StringIO(),
        stderr=StringIO(),
        verbosity=0,
    )

    assert not Organization.objects.filter(pk=org_id).exists()

    # Create a new org with the same slug.
    new_org = Organization.objects.create(
        name="Replacement Org",
        slug="slug-reuse",
    )
    assert new_org.pk != org_id
    assert Organization.objects.filter(slug="slug-reuse").count() == 1


# ---------------------------------------------------------------------------
# T1.17 Phase 2 — Postgres-backed RLS context proof
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_purge_organization_sets_db_current_org_id_on_postgres() -> None:
    """The non-middleware purge path must establish DB-side app.current_org_id.

    On PostgreSQL this proves ``SET LOCAL app.current_org_id`` is set by
    ``set_current_org_for_context()`` inside ``transaction.atomic()``.
    Skipped automatically on SQLite.
    """
    from django.db import connection, transaction

    if connection.vendor != "postgresql":
        pytest.skip("current_setting validation requires PostgreSQL")

    from quickscale_modules_orgs.current_org import (
        reset_current_org_id,
        set_current_org_for_context,
    )

    owner = get_user_model().objects.create_user(
        username="pg-rls-owner",
        email="pg-rls-owner@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="PG RLS Test", slug="pg-rls-test")
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    org_id = organization.pk

    # Step 1: No org context inside an active transaction before the call.
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.current_org_id', true)")
            before_raw = cursor.fetchone()[0]
            before = uuid_lib.UUID(before_raw) if before_raw else None
        # Expect None/null because no SET LOCAL has been issued in this txn.
        assert before is None, (
            f"Expected null before set_current_org_for_context, got {before!r}"
        )

        # Step 2: Establish org context.
        reset_current_org_id()
        set_current_org_for_context(org_id=org_id)

        # Step 3: Verify the DB-side setting matches the org ID.
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.current_org_id', true)")
            after_raw = cursor.fetchone()[0]
            after = uuid_lib.UUID(after_raw) if after_raw else None
        assert after is not None, "Expected a UUID after set_current_org_for_context"
        assert str(after) == str(org_id), (
            f"Expected current_setting to return {org_id}, got {after!r}"
        )

        # Step 4: Python-side ContextVar is also set.
        from quickscale_modules_orgs.current_org import get_current_org_id

        assert get_current_org_id() == org_id

    # Step 5: After the atomic block, the local setting is gone (SET LOCAL
    # only persists for the current transaction).
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.current_org_id', true)")
        after_txn_raw = cursor.fetchone()[0]
        after_txn = uuid_lib.UUID(after_txn_raw) if after_txn_raw else None
    assert after_txn is None, f"Expected null after transaction ends, got {after_txn!r}"
    # Python-side ContextVar was not reset (caller must reset it explicitly).
    # That's the contract documented in current_org.py.

    # Step 6: Full purge command also works on Postgres (smoke test).
    stdout = StringIO()
    call_command(
        "purge_organization",
        organization_id=str(org_id),
        stdout=stdout,
        stderr=StringIO(),
        verbosity=0,
    )
    output = stdout.getvalue()
    assert "has been purged" in output
    assert not Organization.objects.filter(pk=org_id).exists()
    assert OrganizationTombstone.objects.filter(organization_id=org_id).exists()


# ---------------------------------------------------------------------------
# T1.17 Change-review regression tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_purge_organization_slug_preflight_refuses_system_org() -> None:
    """--slug preflight must refuse the System org (CR-T117-002)."""
    system_org = Organization.objects.get_system_org()

    stdout = StringIO()
    stderr = StringIO()
    with pytest.raises(CommandError, match="Cannot purge the System organization"):
        call_command(
            "purge_organization",
            slug=system_org.slug,
            stdout=stdout,
            stderr=stderr,
            verbosity=0,
        )
    # System org must still exist after the slug preflight refusal.
    assert Organization.objects.filter(pk=system_org.pk).exists()


# ---------------------------------------------------------------------------
# T1.17 — --force and personal-org guard contract tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_purge_organization_refuses_personal_org_by_default() -> None:
    """purge_organization must refuse a personal org without --force."""
    owner = get_user_model().objects.create_user(
        username="personal-guard-owner",
        email="personal-guard-owner@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(
        name="Personal Guard Test",
        slug="personal-guard-test",
        is_personal=True,
    )
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )

    stdout = StringIO()
    stderr = StringIO()
    with pytest.raises(CommandError, match="Cannot purge the personal organization"):
        call_command(
            "purge_organization",
            organization_id=str(organization.pk),
            stdout=stdout,
            stderr=stderr,
            verbosity=0,
        )

    assert Organization.objects.filter(pk=organization.pk).exists()


@pytest.mark.django_db
def test_purge_organization_slug_preflight_refuses_personal_org() -> None:
    """--slug preflight must refuse a personal org (consistent guard)."""
    owner = get_user_model().objects.create_user(
        username="slug-personal-guard",
        email="slug-personal-guard@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(
        name="Slug Personal Guard",
        slug="slug-personal-guard",
        is_personal=True,
    )
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )

    stdout = StringIO()
    stderr = StringIO()
    with pytest.raises(CommandError, match="Cannot purge the personal organization"):
        call_command(
            "purge_organization",
            slug=organization.slug,
            stdout=stdout,
            stderr=stderr,
            verbosity=0,
        )

    assert Organization.objects.filter(pk=organization.pk).exists()


@pytest.mark.django_db
def test_purge_organization_force_overrides_system_org_guard() -> None:
    """--force must allow purging the System organization."""
    system_org = Organization.objects.get_system_org()

    stdout = StringIO()
    call_command(
        "purge_organization",
        organization_id=str(system_org.pk),
        force=True,
        stdout=stdout,
        stderr=StringIO(),
        verbosity=0,
    )

    output = stdout.getvalue()
    assert "has been purged" in output
    assert not Organization.objects.filter(pk=system_org.pk).exists()
    assert OrganizationTombstone.objects.filter(organization_id=system_org.pk).exists()


@pytest.mark.django_db
def test_purge_organization_force_overrides_personal_org_guard() -> None:
    """--force must allow purging a personal organization."""
    owner = get_user_model().objects.create_user(
        username="force-personal-owner",
        email="force-personal-owner@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(
        name="Force Personal",
        slug="force-personal",
        is_personal=True,
    )
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    org_id = organization.pk

    stdout = StringIO()
    call_command(
        "purge_organization",
        organization_id=str(org_id),
        force=True,
        stdout=stdout,
        stderr=StringIO(),
        verbosity=0,
    )

    output = stdout.getvalue()
    assert "has been purged" in output
    assert not Organization.objects.filter(pk=org_id).exists()
    assert OrganizationTombstone.objects.filter(organization_id=org_id).exists()


@pytest.mark.django_db
def test_purge_organization_dry_run_with_force_bypasses_guard() -> None:
    """--dry-run with --force should show counts for a reserved org (not error)."""
    system_org = Organization.objects.get_system_org()

    stdout = StringIO()
    call_command(
        "purge_organization",
        organization_id=str(system_org.pk),
        dry_run=True,
        force=True,
        stdout=stdout,
        stderr=StringIO(),
        verbosity=0,
    )

    output = stdout.getvalue()
    assert "Dry run" in output
    # System org still exists after dry run.
    assert Organization.objects.filter(pk=system_org.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_purge_organization_guarded_context_counts_billing_rows() -> None:
    """_build_ownership_map_guarded must establish org context so that
    RLS-protected models (billing Subscription, CreditBalance) are
    countable under TenantManager (CR-T117-001, CR-T117-003).

    Proves by:
    1. Creating billing rows for an org — these use TenantManager which
       returns .none() when the ContextVar is unset (simulating RLS).
    2. Clearing ambient context.
    3. Calling _build_ownership_map_guarded — which should set the
       ContextVar inside the atomic block.
    4. Spying on get_current_org_id() to confirm it returns the org ID
       DURING map construction (not before, not after).
    5. Asserting the resulting map includes the billing counts — which
       would be 0 if the ContextVar were not established.
    """
    from unittest.mock import patch

    from quickscale_modules_billing.models import (
        CreditBalance,
        CreditTransaction,
        Plan,
        Subscription,
    )
    from quickscale_modules_orgs.current_org import (
        get_current_org_id,
        set_current_org_id,
    )

    owner = get_user_model().objects.create_user(
        username="guarded-counts-owner",
        email="guarded-counts-owner@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(
        name="Guarded Counts Test", slug="guarded-counts-test"
    )
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    plan = Plan.objects.create(
        name="Growth",
        slug="growth-guarded-counts",
        stripe_price_id="price_growth_guarded_counts",
        credits_per_period=250,
        price_cents=4900,
        currency="usd",
        billing_interval=Plan.BillingInterval.MONTHLY,
    )
    Subscription.objects.create(
        organization=organization,
        user=owner,
        plan=plan,
        stripe_subscription_id="sub_guarded_counts",
        stripe_customer_id="cus_guarded_counts",
        status=Subscription.Status.ACTIVE,
    )
    CreditBalance.objects.create(
        organization=organization,
        user=owner,
        balance=100,
    )
    CreditTransaction.objects.create(
        organization=organization,
        user=owner,
        amount=50,
        transaction_type=CreditTransaction.TransactionType.PURCHASE,
        description="Guarded counts test",
        balance_after=100,
    )

    # Ensure no ambient context before the call (simulating the RLS path
    # where TenantManager.objects would return .none()).
    set_current_org_id(None)
    assert get_current_org_id() is None

    # Spy on _build_ownership_map to record ContextVar state during
    # counting of the billing rows (RLS-sensitive models).
    captured_context_during_map: list[uuid_lib.UUID | None] = []

    original_build_map = Command._build_ownership_map

    def spying_build_map(self, org):
        captured_context_during_map.append(get_current_org_id())
        result = original_build_map(self, org)
        captured_context_during_map.append(get_current_org_id())
        return result

    cmd = Command()
    cmd.stdout = StringIO()
    cmd.stderr = StringIO()

    with patch.object(Command, "_build_ownership_map", new=spying_build_map):
        ownership_map = cmd._build_ownership_map_guarded(organization)

    # The ContextVar must be set to the org ID DURING map construction.
    assert len(captured_context_during_map) == 2
    assert captured_context_during_map[0] == organization.pk, (
        "ContextVar must be set when counting begins"
    )
    assert captured_context_during_map[1] == organization.pk, (
        "ContextVar must remain set during counting"
    )

    # After the guarded call, context is reset (the finally block).
    assert get_current_org_id() is None, "ContextVar must be reset after guarded build"

    # The map must include the billing rows.  Without the guarded context
    # these would be 0 because TenantManager returns .none() when the
    # ContextVar is unset.
    assert ownership_map.get("Subscriptions", 0) >= 1, (
        "Subscriptions count must be non-zero — proves TenantManager "
        "could see the rows because context was established"
    )
    assert ownership_map.get("Credit balances", 0) >= 1
    assert ownership_map.get("Credit transactions", 0) >= 1


# ---------------------------------------------------------------------------
# T1.17 — Multi-module delete spec verification (CR-T117-REVIEW-001)
#
# The purge command uses apps.get_model() to resolve cross-module models,
# so full integration coverage requires the target modules to be installed.
# The orgs test environment installs only orgs + billing.  This test
# validates the delete specs structure directly — each entry's app_label,
# model_name, filter_key, and label — and proves _resolve_models() and
# _get_qs() handle uninstalled modules gracefully.
# ---------------------------------------------------------------------------


def test_purge_delete_specs_are_complete() -> None:
    """_DELETE_SPECS must contain entries for every owned module.

    This is a structure-level test that does not require those modules to
    be installed — it validates the spec metadata directly.
    """
    from quickscale_modules_orgs.management.commands.purge_organization import (
        _DELETE_SPECS,
    )

    app_labels = {str(spec["app_label"]) for spec in _DELETE_SPECS}
    model_names = {str(spec["model_name"]) for spec in _DELETE_SPECS}

    # Verify every owned module is represented in the specs.
    for expected_app in [
        "quickscale_modules_social",
        "quickscale_modules_forms",
        "quickscale_modules_listings",
        "quickscale_modules_blog",
        "quickscale_modules_crm",
        "quickscale_modules_billing",
    ]:
        assert expected_app in app_labels, (
            f"Missing delete spec entry for {expected_app}"
        )

    # Verify key model entries exist.
    expected_models = {
        "SocialLink",
        "SocialEmbed",
        "FormFieldValue",
        "FormField",
        "FormSubmission",
        "Form",
        "Listing",
        "Post",
        "Category",
        "Tag",
        "BlogMediaAsset",
        "DealNote",
        "ContactNote",
        "Deal",
        "Contact",
        "Company",
        "Stage",
        "Tag",  # CRM Tag
        "CreditTransaction",
        "Subscription",
        "CreditBalance",
    }
    for model_name in expected_models:
        assert model_name in model_names, f"Missing delete spec entry for {model_name}"

    # Verify CRM delete ordering: DealNote before Deal before Stage.
    deal_note_idx = next(
        i
        for i, s in enumerate(_DELETE_SPECS)
        if s["app_label"] == "quickscale_modules_crm" and s["model_name"] == "DealNote"
    )
    deal_idx = next(
        i
        for i, s in enumerate(_DELETE_SPECS)
        if s["app_label"] == "quickscale_modules_crm" and s["model_name"] == "Deal"
    )
    stage_idx = next(
        i
        for i, s in enumerate(_DELETE_SPECS)
        if s["app_label"] == "quickscale_modules_crm" and s["model_name"] == "Stage"
    )
    assert deal_note_idx < deal_idx, "DealNote must be deleted before Deal (CASCADE)"
    assert deal_idx < stage_idx, (
        "Deal must be deleted before Stage (PROTECT on deal FK)"
    )


def test_resolve_models_skips_uninstalled_apps() -> None:
    """_resolve_models() returns resolved models for installed apps (not None)."""
    from quickscale_modules_orgs.management.commands.purge_organization import (
        _resolve_models,
    )

    resolved = _resolve_models()
    # All modules are installed in the orgs test environment, so every
    # entry must have a resolved model (not None).
    for entry in resolved:
        assert entry["model"] is not None, (
            f"Model for '{entry['label']}' must be resolved (module is installed)"
        )


# ---------------------------------------------------------------------------
# T1.17 — Real multi-module purge integration (CR-T117-REVIEW-001)
# Tests create rows for each module and verify purge_organization actually
# deletes them.  All modules are installed in the orgs test environment.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_purge_organization_deletes_social_rows() -> None:
    """purge_organization must delete SocialLink rows."""
    from quickscale_modules_social.models import SocialLink

    org = Organization.objects.create(name="Social Purge", slug="social-purge")
    SocialLink.objects.bulk_create(
        [
            SocialLink(
                organization=org,
                title="Test Link",
                url="https://www.linkedin.com/company/quickscale",
                description="Test",
                display_order=0,
            ),
        ]
    )
    org_id = org.pk

    call_command(
        "purge_organization",
        organization_id=str(org_id),
        stdout=StringIO(),
        stderr=StringIO(),
        verbosity=0,
    )
    assert not Organization.objects.filter(pk=org_id).exists()
    assert SocialLink.all_objects.filter(organization_id=org_id).count() == 0
    assert OrganizationTombstone.objects.filter(organization_id=org_id).exists()


@pytest.mark.django_db
def test_purge_organization_deletes_forms_rows() -> None:
    """purge_organization must delete Form rows (with FormSubmission PROTECT)."""
    from quickscale_modules_forms.models import Form, FormSubmission

    org = Organization.objects.create(name="Forms Purge", slug="forms-purge")
    form = Form.objects.create(organization=org, title="Test Form", slug="test-form")
    FormSubmission.all_objects.create(
        form=form,
        organization=form.organization,
    )
    org_id = org.pk

    call_command(
        "purge_organization",
        organization_id=str(org_id),
        stdout=StringIO(),
        stderr=StringIO(),
        verbosity=0,
    )
    assert not Organization.objects.filter(pk=org_id).exists()
    assert Form.all_objects.filter(organization_id=org_id).count() == 0
    assert FormSubmission.all_objects.filter(organization_id=org_id).count() == 0
    assert OrganizationTombstone.objects.filter(organization_id=org_id).exists()


@pytest.mark.django_db
def test_purge_organization_deletes_listings_rows() -> None:
    """purge_organization must delete Listing rows."""
    from quickscale_modules_listings.models import Listing

    org = Organization.objects.create(name="Listings Purge", slug="listings-purge")
    Listing.objects.create(organization=org, title="Test Listing", slug="test-listing")
    org_id = org.pk

    call_command(
        "purge_organization",
        organization_id=str(org_id),
        stdout=StringIO(),
        stderr=StringIO(),
        verbosity=0,
    )
    assert not Organization.objects.filter(pk=org_id).exists()
    assert Listing.all_objects.filter(organization_id=org_id).count() == 0
    assert OrganizationTombstone.objects.filter(organization_id=org_id).exists()


@pytest.mark.django_db
def test_purge_organization_deletes_blog_rows() -> None:
    """purge_organization must delete Post, Category, and Tag rows."""
    from quickscale_modules_blog.models import Category, Post, Tag

    org = Organization.objects.create(name="Blog Purge", slug="blog-purge")
    category = Category.objects.create(
        organization=org, name="Test Cat", slug="test-cat"
    )
    Tag.objects.create(organization=org, name="Test Tag", slug="test-tag")
    Post.objects.create(
        organization=org,
        title="Test Post",
        slug="test-post",
        category=category,
        content="# Hello",
    )
    org_id = org.pk

    call_command(
        "purge_organization",
        organization_id=str(org_id),
        stdout=StringIO(),
        stderr=StringIO(),
        verbosity=0,
    )
    assert not Organization.objects.filter(pk=org_id).exists()
    assert Post.all_objects.filter(organization_id=org_id).count() == 0
    assert Category.all_objects.filter(organization_id=org_id).count() == 0
    assert Tag.all_objects.filter(organization_id=org_id).count() == 0
    assert OrganizationTombstone.objects.filter(organization_id=org_id).exists()


@pytest.mark.django_db
def test_purge_organization_deletes_crm_rows() -> None:
    """purge_organization must delete Company rows (and protect-safe ordering)."""
    from quickscale_modules_crm.models import (
        Company,
        Contact,
        Deal,
        Stage,
        Tag,
    )

    org = Organization.objects.create(name="CRM Purge", slug="crm-purge")
    company = Company.objects.create(organization=org, name="Test Co")
    stage = Stage.objects.create(organization=org, name="Test Stage", order=0)
    contact = Contact.objects.create(
        organization=org,
        first_name="A",
        last_name="B",
        email="a@b.com",
        company=company,
    )
    Deal.objects.create(
        organization=org,
        title="Test Deal",
        contact=contact,
        stage=stage,
    )
    Tag.objects.create(organization=org, name="Test Tag")
    org_id = org.pk

    call_command(
        "purge_organization",
        organization_id=str(org_id),
        stdout=StringIO(),
        stderr=StringIO(),
        verbosity=0,
    )
    assert not Organization.objects.filter(pk=org_id).exists()
    assert Company.all_objects.filter(organization_id=org_id).count() == 0
    assert Contact.all_objects.filter(organization_id=org_id).count() == 0
    assert Deal.all_objects.filter(organization_id=org_id).count() == 0
    assert Stage.all_objects.filter(organization_id=org_id).count() == 0
    assert Tag.all_objects.filter(organization_id=org_id).count() == 0
    assert OrganizationTombstone.objects.filter(organization_id=org_id).exists()


@pytest.mark.django_db
def test_purge_organization_dry_run_counts_all_modules() -> None:
    """--dry-run must count rows across social, forms, listings, blog, crm, billing."""
    from quickscale_modules_blog.models import Post
    from quickscale_modules_crm.models import Company
    from quickscale_modules_forms.models import Form
    from quickscale_modules_listings.models import Listing
    from quickscale_modules_social.models import SocialLink

    org = Organization.objects.create(name="Multi Dryrun", slug="multi-dryrun")
    SocialLink.objects.bulk_create(
        [
            SocialLink(
                organization=org,
                title="SL",
                url="https://www.linkedin.com/company/quickscale",
                display_order=0,
            ),
        ]
    )
    Form.objects.create(organization=org, title="F", slug="f")
    Listing.objects.create(organization=org, title="L")
    Post.objects.create(organization=org, title="P", slug="p", content="x")
    Company.objects.create(organization=org, name="Dryrun Co")
    org_id = org.pk

    stdout = StringIO()
    call_command(
        "purge_organization",
        organization_id=str(org_id),
        dry_run=True,
        stdout=stdout,
        stderr=StringIO(),
        verbosity=0,
    )

    output = stdout.getvalue()
    assert "Dry run" in output
    assert "Social links: 1" in output
    assert "Forms: 1" in output
    assert "Listings: 1" in output
    assert "Blog posts: 1" in output
    assert "CRM companies: 1" in output
    assert Organization.objects.filter(pk=org_id).exists()


@pytest.mark.django_db
def test_purge_organization_clears_social_cache() -> None:
    """purge_organization must invalidate social cache keys (CR-T117-R2).

    SocialLink/SocialEmbed rows are deleted via QuerySet.delete() which
    bypasses BaseSocialItem.delete() cache invalidation.  The command
    must explicitly clear the org-partitioned cache keys.
    """
    from django.core.cache import cache

    from quickscale_modules_social.contracts import (
        SOCIAL_EMBEDS_CACHE_KEY,
        SOCIAL_LINKS_CACHE_KEY,
    )
    from quickscale_modules_social.models import SocialLink

    org = Organization.objects.create(name="Cache Purge", slug="cache-purge")
    SocialLink.objects.bulk_create(
        [
            SocialLink(
                organization=org,
                title="CL",
                url="https://www.linkedin.com/company/quickscale",
                display_order=0,
            ),
        ]
    )
    org_id = org.pk

    # Seed cache keys before purge.
    link_key = f"{SOCIAL_LINKS_CACHE_KEY}:org:{org_id}"
    embed_key = f"{SOCIAL_EMBEDS_CACHE_KEY}:org:{org_id}"
    cache.set(SOCIAL_LINKS_CACHE_KEY, "stale")
    cache.set(link_key, "stale")
    cache.set(SOCIAL_EMBEDS_CACHE_KEY, "stale")
    cache.set(embed_key, "stale")

    assert cache.get(SOCIAL_LINKS_CACHE_KEY) == "stale"
    assert cache.get(link_key) == "stale"

    call_command(
        "purge_organization",
        organization_id=str(org_id),
        stdout=StringIO(),
        stderr=StringIO(),
        verbosity=0,
    )

    # Cache keys must be cleared after purge.
    assert cache.get(SOCIAL_LINKS_CACHE_KEY) is None
    assert cache.get(link_key) is None
    assert cache.get(SOCIAL_EMBEDS_CACHE_KEY) is None
    assert cache.get(embed_key) is None


# ---------------------------------------------------------------------------
# AF3 phase 2 — operator_access helper tests (success + failure paths)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_operator_access_success_path_creates_audit_log(caplog) -> None:
    """operator_access must emit a succeeded structured log with stable fields."""
    caplog.set_level(logging.INFO)
    from quickscale_modules_orgs.operator_access import operator_access

    with operator_access(reason="test success") as log:
        log.command = "test_command"
        log.actor_identifier = "test_suite"
        log.target_scope = "all_orgs"
        log.target_org_ids = ["org-1", "org-2"]
        log.touched_org_ids = ["org-1"]

    # Verify the audit log message has all stable fields.
    msg = caplog.records[-1].getMessage()
    assert "operator_access:" in msg
    assert "status=succeeded" in msg
    assert "command=test_command" in msg
    assert "scope=all_orgs" in msg
    assert "reason=test success" in msg
    assert "actor=test_suite" in msg
    assert "target_orgs=org-1,org-2" in msg
    assert "touched_orgs=org-1" in msg
    assert "error_class=" in msg


@pytest.mark.django_db
def test_operator_access_failure_path_records_error_class(caplog) -> None:
    """When the body raises, operator_access must log status='failed' and error_class."""
    caplog.set_level(logging.INFO)
    from quickscale_modules_orgs.operator_access import operator_access

    with pytest.raises(RuntimeError, match="simulated failure"):
        with operator_access(reason="test failure") as log:
            log.command = "test_command"
            log.actor_identifier = "test_suite"
            log.target_scope = "single_org"
            log.target_org_ids = ["org-1"]
            log.touched_org_ids = ["org-1"]
            raise RuntimeError("simulated failure")

    # Verify the audit log captures the failure.
    msg = caplog.records[-1].getMessage()
    assert "operator_access:" in msg
    assert "status=failed" in msg
    assert "error_class=RuntimeError" in msg


@pytest.mark.django_db
def test_operator_access_without_optional_fields(caplog) -> None:
    """operator_access must handle a bare yield without field population."""
    caplog.set_level(logging.INFO)
    from quickscale_modules_orgs.operator_access import operator_access

    with operator_access(reason="bare test") as log:
        log.command = "bare_command"

    msg = caplog.records[-1].getMessage()
    assert "operator_access:" in msg
    assert "status=succeeded" in msg
    assert "command=bare_command" in msg
    # Optional fields should appear with empty defaults.
    assert "target_orgs=" in msg
    assert "touched_orgs=" in msg


# ---------------------------------------------------------------------------
# AF3 phase 2 — purge_organization seam audit tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_purge_organization_success_audit_record(caplog) -> None:
    """A successful purge must log a 'succeeded' audit record with stable fields."""
    caplog.set_level(logging.INFO)
    owner = get_user_model().objects.create_user(
        username="audit-success-owner",
        email="audit-success-owner@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(
        name="Audit Success Test", slug="audit-success-test"
    )
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    org_id = organization.pk

    stdout = StringIO()
    call_command(
        "purge_organization",
        organization_id=str(org_id),
        stdout=stdout,
        stderr=StringIO(),
        verbosity=0,
    )

    output = stdout.getvalue()
    assert "has been purged" in output
    assert OrganizationTombstone.objects.filter(organization_id=org_id).exists()

    # Verify the operator-access audit log message.
    msgs = [r.getMessage() for r in caplog.records]
    matching = [
        m for m in msgs if "operator_access:" in m and "command=purge_organization" in m
    ]
    assert len(matching) >= 1, f"No purge audit log found in: {msgs}"
    msg = matching[-1]
    assert "status=succeeded" in msg
    assert "scope=single_org" in msg
    assert str(org_id) in msg
    assert "error_class=" in msg


@pytest.mark.django_db
def test_purge_organization_failure_audit_record(caplog) -> None:
    """When purge fails, the audit log must have status='failed' and error_class."""
    caplog.set_level(logging.INFO)
    from unittest.mock import patch

    owner = get_user_model().objects.create_user(
        username="audit-fail-owner",
        email="audit-fail-owner@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(
        name="Audit Failure Test", slug="audit-failure-test"
    )
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    org_id = organization.pk

    # Force a failure during the operator_access body by patching
    # _delete_owned_rows to raise an error.
    from quickscale_modules_orgs.management.commands.purge_organization import Command

    original_delete_owned = Command._delete_owned_rows

    def failing_delete(self, org):
        original_delete_owned(self, org)
        raise RuntimeError("Simulated purge audit failure")

    stdout = StringIO()
    stderr = StringIO()
    with (
        pytest.raises(RuntimeError, match="Simulated purge audit failure"),
        patch.object(Command, "_delete_owned_rows", new=failing_delete),
    ):
        call_command(
            "purge_organization",
            organization_id=str(org_id),
            stdout=stdout,
            stderr=stderr,
            verbosity=0,
        )

    # The audit log must have status='failed' with error_class.
    msgs = [r.getMessage() for r in caplog.records]
    matching = [
        m for m in msgs if "operator_access:" in m and "command=purge_organization" in m
    ]
    assert len(matching) >= 1, f"No purge audit log found in: {msgs}"
    msg = matching[-1]
    assert "status=failed" in msg
    assert "error_class=RuntimeError" in msg

    # The database must be rolled back (original purge safeguard).
    assert Organization.objects.filter(pk=org_id).exists()
    assert not OrganizationTombstone.objects.filter(organization_id=org_id).exists()


# ---------------------------------------------------------------------------
# AF3 phase 4 — positive-proof manifest: every in-scope management command
# must import AND invoke operator_access from the shared seam.
# ---------------------------------------------------------------------------

# These are the exact four management-command files adopted into the seam.
# Paths are relative to the repo root, using the src/ layout.
_AF3_COMMAND_PATHS: list[str] = [
    "quickscale_modules/orgs/src/quickscale_modules_orgs/management/commands/purge_organization.py",
    "quickscale_modules/orgs/src/quickscale_modules_orgs/management/commands/migrate_billing_to_orgs.py",
    "quickscale_modules/forms/src/quickscale_modules_forms/management/commands/forms_anonymize_submissions.py",
    "quickscale_modules/forms/src/quickscale_modules_forms/management/commands/forms_seed_presets.py",
]


@pytest.mark.parametrize("rel_path", _AF3_COMMAND_PATHS)
def test_af3_command_imports_and_invokes_operator_access(rel_path: str) -> None:
    """Every AF3-adopted management command must import AND invoke
    ``operator_access()`` — not just carry the import statement.

    Uses AST parsing so that docstring or comment references to
    ``operator_access`` do not false-pass the invocation check.
    """
    import ast
    import pathlib

    repo_root = pathlib.Path(__file__).resolve().parents[3]
    full_path = repo_root / rel_path
    assert full_path.exists(), f"Command file not found: {full_path}"

    source = full_path.read_text()
    tree = ast.parse(source)

    # 1. Structural import check — look for an ImportFrom node that
    #    imports operator_access from the seam.
    has_import = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "quickscale_modules_orgs.operator_access"
        and any(alias.name == "operator_access" for alias in node.names)
        for node in ast.walk(tree)
    )
    assert has_import, (
        f"{rel_path} does not import operator_access. "
        "Every AF3 command must route privileged access through the shared seam."
    )

    # 2. Structural invocation check — require ``operator_access(...)``
    #    as the context expression of a ``with`` statement.  Bare calls or
    #    stored contextmanager references are not sufficient — every AF3
    #    command must use ``with operator_access(reason=...) as record:``.
    has_with = any(isinstance(node, ast.With) for node in ast.walk(tree)) and any(
        isinstance(item.context_expr, ast.Call)
        and isinstance(item.context_expr.func, ast.Name)
        and item.context_expr.func.id == "operator_access"
        for node in ast.walk(tree)
        if isinstance(node, ast.With)
        for item in node.items
    )
    assert has_with, (
        f"{rel_path} imports operator_access but no AST-level "
        "'with operator_access(...):' statement was found. "
        "Every AF3 command must use "
        "'with operator_access(reason=...) as record:'."
    )


# ---------------------------------------------------------------------------
# AF3 phase 4 — zero-direct-.all_objects. guard for the full management-
# command surface (all modules, not just the four AF3 files).
#
# The single centralized exception is ``operator_queryset()`` in
# ``operator_access.py`` itself — that file is NOT a management command.
# Every other management command file must route operator-level reads
# through ``operator_queryset()``.
# ---------------------------------------------------------------------------


def _all_management_command_paths(repo_root: object) -> list[str]:
    """Glob all management command *.py files across all modules."""
    import pathlib

    repo = pathlib.Path(repo_root)
    base = repo / "quickscale_modules"
    paths: list[str] = []
    for module_dir in sorted(base.iterdir()):
        src_dir = module_dir / "src"
        if not src_dir.is_dir():
            continue
        for pkg_dir in src_dir.iterdir():
            if pkg_dir.name == "__pycache__":
                continue
            commands_dir = pkg_dir / "management" / "commands"
            if not commands_dir.is_dir():
                continue
            for f in sorted(commands_dir.iterdir()):
                if f.suffix == ".py" and f.name != "__init__.py":
                    paths.append(str(f.relative_to(repo)))
    return paths


def _ast_has_direct_all_objects(source: str) -> list[int]:
    """Return line numbers of AST-level ``.all_objects.`` attribute accesses.

    Uses Python's ``ast`` module so that references inside string literals
    (docstrings, comments) are naturally excluded — only real attribute
    access expressions count.
    """
    import ast

    lines: list[int] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    for node in ast.walk(tree):
        # Look for Attribute nodes where attr is 'all_objects' and the
        # parent is another Attribute (meaning it's chained: .all_objects.
        # rather than just `all_objects` as a standalone name).
        if isinstance(node, ast.Attribute) and node.attr == "all_objects":
            lines.append(node.lineno)
    return sorted(set(lines))


def test_af3_all_commands_no_direct_all_objects() -> None:
    """No management command file across any module may reference
    ``.all_objects.`` directly.  The single centralized exception is
    ``operator_queryset()`` in ``operator_access.py`` itself.

    Operator-scoped queries in management commands must go through
    ``operator_queryset()`` or ``operator_access()`` from the shared seam.

    This test reports all violations together in a single assertion.
    """
    import pathlib

    repo_root = pathlib.Path(__file__).resolve().parents[3]
    violations: list[str] = []
    for rel_path in _all_management_command_paths(repo_root):
        full_path = repo_root / rel_path
        if not full_path.exists():
            violations.append(f"{rel_path} (file not found)")
            continue
        source = full_path.read_text()
        bad_lines = _ast_has_direct_all_objects(source)
        if bad_lines:
            violations.append(f"{rel_path}: line(s) {bad_lines}")
    assert not violations, (
        "Direct .all_objects. references found in management command files "
        f"(expected zero outside {_AF3_COMMAND_PATHS[0]}):\n"
        + "\n".join(f"  - {v}" for v in violations)
    )


# ---------------------------------------------------------------------------
# Regression: AST-based parser must detect .all_objects. inside real code
# even when the file has a one-line docstring containing that pattern.
# ---------------------------------------------------------------------------


def test_ast_detects_all_objects_in_one_line_docstring_file() -> None:
    """A file with a one-line docstring containing ``.all_objects.``
    followed by real code with ``.all_objects.`` must have the real-code
    reference detected."""
    source = (
        '"""A one-line docstring with .all_objects. reference."""\n'
        "x = Model.all_objects.filter(pk=1)  # real code\n"
    )
    lines = _ast_has_direct_all_objects(source)
    assert lines == [2], f"Expected line 2 (real code) detected, got {lines}"


def test_ast_ignores_all_objects_in_docstring_only() -> None:
    """A file with only a one-line docstring containing ``.all_objects.``
    and no real-code reference must report zero violations."""
    source = '"""A docstring with .all_objects. but no real code."""\n'
    lines = _ast_has_direct_all_objects(source)
    assert lines == [], f"Expected zero lines detected, got {lines}"


# ---------------------------------------------------------------------------
# AF3 phase 4 — deferred non-management runtime .all_objects. manifest.
#
# These entrypoints still reference ``.all_objects.`` for operator-level
# reads outside management commands.  Each is tracked for a future phase;
# none block the management-command seam rollout.
#
# This manifest is tested structurally: every listed path must contain at
# least one non-comment ``.all_objects.`` reference (proving the entrypoint
# still exists) and is annotated with its deferred-remediation label.
#
# The single centralized seam exception (``operator_queryset()`` in
# ``quickscale_modules_orgs/operator_access.py``) is *not* listed here
# because it is the intended design — the only place outside deferred
# files where ``.all_objects.`` may appear.
# ---------------------------------------------------------------------------

# (app_label, location, deferred phase, reason)
_AF3_DEFERRED_ALL_OBJECTS: list[tuple[str, str, str, str]] = [
    (
        "quickscale_modules_orgs",
        "permissions.py",
        "AF3 deferred",
        "Permission checks use all_objects to discover org resources across tenant boundaries.",
    ),
    (
        "quickscale_modules_forms",
        "admin.py",
        "AF3 deferred",
        "Admin list views use all_objects for cross-org visibility.",
    ),
    (
        "quickscale_modules_forms",
        "notifications.py",
        "AF3 deferred",
        "Notification dispatch queries submissions across org boundaries.",
    ),
    (
        "quickscale_modules_forms",
        "views.py",
        "AF3 deferred",
        "Public-facing endpoints read forms across org boundaries via all_objects.",
    ),
    (
        "quickscale_modules_billing",
        "admin.py",
        "AF3 deferred",
        "Admin list views use all_objects for cross-org billing visibility.",
    ),
    (
        "quickscale_modules_billing",
        "services.py",
        "AF3 deferred",
        "Stripe webhook handlers query billing rows across org boundaries.",
    ),
    (
        "quickscale_modules_billing",
        "views.py",
        "AF3 deferred",
        "Billing dashboard views may reference all_objects for cross-org data.",
    ),
    (
        "quickscale_modules_crm",
        "admin.py",
        "AF3 deferred",
        "Admin list views use all_objects for cross-org CRM visibility.",
    ),
    (
        "quickscale_modules_crm",
        "models.py",
        "AF3 deferred",
        "Model-level lookups reference all_objects for operator-level access.",
    ),
    (
        "quickscale_modules_crm",
        "serializers.py",
        "AF3 deferred",
        "Serializer queries may use all_objects for cross-org reads.",
    ),
    (
        "quickscale_modules_crm",
        "services.py",
        "AF3 deferred",
        "CRM service functions query across org boundaries.",
    ),
    (
        "quickscale_modules_crm",
        "views.py",
        "AF3 deferred",
        "CRM view queries may reference all_objects.",
    ),
    (
        "quickscale_modules_blog",
        "admin.py",
        "AF3 deferred",
        "Admin list views use all_objects for cross-org blog visibility.",
    ),
    (
        "quickscale_modules_blog",
        "feeds.py",
        "AF3 deferred",
        "RSS/Atom feeds fetch public posts across org boundaries.",
    ),
    (
        "quickscale_modules_blog",
        "views.py",
        "AF3 deferred",
        "Blog views may query across org boundaries.",
    ),
    (
        "quickscale_modules_social",
        "models.py",
        "AF3 deferred",
        "Social model methods reference all_objects for operator-level cache operations.",
    ),
]


def test_af3_deferred_all_objects_manifest_remains_accurate() -> None:
    """Every entry in the deferred manifest must still contain a non-comment
    ``.all_objects.`` reference — proving the entrypoint has not been
    inadvertently removed without updating the manifest.

    The centralized seam exception (``operator_queryset()`` in
    ``operator_access.py``) is excluded from this manifest because it is
    the intended single bypass for management commands.
    """
    import pathlib

    repo_root = pathlib.Path(__file__).resolve().parents[3]
    missing: list[str] = []
    for app_label, location, phase, reason in _AF3_DEFERRED_ALL_OBJECTS:
        module_name = app_label.replace("quickscale_modules_", "")
        full_path = (
            repo_root
            / "quickscale_modules"
            / module_name
            / "src"
            / app_label
            / location
        )
        if not full_path.exists():
            missing.append(f"{app_label}/{location} (file not found at {full_path})")
            continue

        source = full_path.read_text()
        has_all_objects = any(
            ".all_objects." in line and not line.strip().startswith("#")
            for line in source.splitlines()
        )
        if not has_all_objects:
            missing.append(
                f"{app_label}/{location} has no non-comment .all_objects. reference"
            )

    assert not missing, "Deferred manifest entries missing or stale:\n" + "\n".join(
        f"  - {m}" for m in missing
    )


def _all_non_management_module_paths(repo_root: object) -> list[str]:
    """Glob all non-management, non-__init__ Python files under
    ``quickscale_modules/*/src/*/``, excluding management/commands/."""
    import pathlib

    repo = pathlib.Path(repo_root)
    base = repo / "quickscale_modules"
    paths: list[str] = []
    for module_dir in sorted(base.iterdir()):
        src_dir = module_dir / "src"
        if not src_dir.is_dir():
            continue
        for pkg_dir in src_dir.iterdir():
            if pkg_dir.name == "__pycache__":
                continue
            for f in sorted(pkg_dir.rglob("*.py")):
                if f.name == "__init__.py":
                    continue
                if "management" in f.parts:
                    continue
                paths.append(str(f.relative_to(repo)))
    return paths


def test_af3_all_non_management_all_objects_set_equality() -> None:
    """Assert that the set of non-management files with AST-level
    ``.all_objects.`` references matches the 16-entry deferred manifest
    plus the centralized ``operator_access.py`` exception exactly.

    Any extra file outside the manifest means a new callsite was introduced
    without updating the manifest.  Any missing file means a manifest entry
    no longer has an AST-level reference.
    """
    import pathlib

    repo_root = pathlib.Path(__file__).resolve().parents[3]

    # Build the expected set: 16 deferred manifest files + operator_access.py
    expected: set[str] = set()
    for app_label, location, phase, reason in _AF3_DEFERRED_ALL_OBJECTS:
        module_name = app_label.replace("quickscale_modules_", "")
        expected.add(f"quickscale_modules/{module_name}/src/{app_label}/{location}")
    # Centralized seam exception.
    expected.add(
        "quickscale_modules/orgs/src/quickscale_modules_orgs/operator_access.py"
    )

    # Build the actual set: all non-management files with AST-level
    # .all_objects. references.
    actual: set[str] = set()
    for rel_path in _all_non_management_module_paths(repo_root):
        full_path = repo_root / rel_path
        source = full_path.read_text(encoding="utf-8")
        if _ast_has_direct_all_objects(source):
            actual.add(rel_path)

    # Assert set equality.
    extraneous = actual - expected
    missing = expected - actual

    assert not extraneous, (
        f"{len(extraneous)} file(s) contain AST-level .all_objects. references "
        "but are not in the deferred manifest or operator_access.py exception:\n"
        + "\n".join(f"  + {p}" for p in sorted(extraneous))
    )
    assert not missing, (
        f"{len(missing)} deferred-manifest entry/entries no longer contain "
        "an AST-level .all_objects. reference:\n"
        + "\n".join(f"  - {p}" for p in sorted(missing))
    )
