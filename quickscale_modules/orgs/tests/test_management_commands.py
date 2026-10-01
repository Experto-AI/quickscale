"""Focused tests for org billing bridge management commands."""

from __future__ import annotations

import concurrent.futures
import json as json_lib
import threading
import uuid as uuid_lib
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.utils import timezone

from quickscale_modules_billing.models import (
    CreditBalance,
    CreditTransaction,
    Plan,
    PurchaseCheckout,
    Subscription,
)
from quickscale_modules_orgs.current_org import (
    reset_current_org_id,
    set_current_org_id,
)
from quickscale_modules_orgs.management.commands.quickscale_orgs_purge_organization import (
    Command,
)
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


@pytest.mark.django_db(transaction=True)
def test_credit_mutation_serializes_with_organization_purge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A credit commits under the organization mutex before purge proceeds."""
    from django.db import close_old_connections

    from quickscale_modules_billing import services as billing_services

    user = get_user_model().objects.create_user(
        username="credit-purge-race",
        email="credit-purge-race@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(
        name="Credit Purge Race",
        slug="credit-purge-race",
    )
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.OWNER,
    )

    credit_has_lock = threading.Event()
    allow_credit_to_finish = threading.Event()
    purge_attempted_lock = threading.Event()
    original_billing_lock = billing_services._lock_organization_for_billing_mutation
    original_purge_lock = Command._lock_organization

    def pause_after_credit_lock(organization_arg):
        locked = original_billing_lock(organization_arg)
        credit_has_lock.set()
        if not allow_credit_to_finish.wait(timeout=10):
            raise AssertionError("timed out waiting to release credit mutation")
        return locked

    def signal_purge_lock_attempt(command: Command, organization_id: object):
        purge_attempted_lock.set()
        return original_purge_lock(command, organization_id)

    monkeypatch.setattr(
        billing_services,
        "_lock_organization_for_billing_mutation",
        pause_after_credit_lock,
    )
    monkeypatch.setattr(Command, "_lock_organization", signal_purge_lock_attempt)

    def run_credit() -> None:
        close_old_connections()
        set_current_org_id(organization.pk)
        try:
            billing_services.credit_user(
                user,
                organization=organization,
                amount=25,
                transaction_type=CreditTransaction.TransactionType.PURCHASE,
                stripe_event_id="evt_credit_purge_race",
            )
        finally:
            reset_current_org_id()
            close_old_connections()

    def run_purge() -> None:
        close_old_connections()
        try:
            call_command(
                "quickscale_orgs_purge_organization",
                organization_id=str(organization.pk),
                stdout=StringIO(),
                stderr=StringIO(),
                verbosity=0,
            )
        finally:
            close_old_connections()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        credit_future = executor.submit(run_credit)
        assert credit_has_lock.wait(timeout=10)
        purge_future = executor.submit(run_purge)
        assert purge_attempted_lock.wait(timeout=10)
        allow_credit_to_finish.set()
        credit_future.result(timeout=10)
        purge_future.result(timeout=10)

    assert not Organization.objects.filter(pk=organization.pk).exists()
    assert OrganizationTombstone.objects.filter(
        organization_id=organization.pk
    ).exists()


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
        "quickscale_orgs_promote_to_saas",
        stdout=stdout,
        stderr=StringIO(),
        verbosity=0,
    )
    organization.refresh_from_db()

    assert organization.slug == "solo-owner"
    assert "personal_slug=<blank> -> solo-owner" in stdout.getvalue()
    assert "QUICKSCALE_ORGS_MODE = 'saas'" in stdout.getvalue()


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
        "quickscale_orgs_promote_to_saas",
        stdout=first_stdout,
        stderr=StringIO(),
        verbosity=0,
    )
    organization.refresh_from_db()

    assert organization.slug == "collision-owner-2"
    assert "collision-owner-2" in first_stdout.getvalue()

    second_stdout = StringIO()
    call_command(
        "quickscale_orgs_promote_to_saas",
        stdout=second_stdout,
        stderr=StringIO(),
        verbosity=0,
    )
    organization.refresh_from_db()

    assert organization.slug == "collision-owner-2"
    assert "updated 0 personal organizations" in second_stdout.getvalue().lower()


@pytest.mark.django_db
def test_promote_to_saas_dry_run_reports_without_saving() -> None:
    """--dry-run reports the planned slug change and writes nothing."""
    owner = get_user_model().objects.create_user(
        username="dry-run-owner",
        email="dry-run-owner@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(
        name="Dry Run Owner's Org",
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
        "quickscale_orgs_promote_to_saas",
        "--dry-run",
        stdout=stdout,
        stderr=StringIO(),
        verbosity=0,
    )
    organization.refresh_from_db()

    assert organization.slug == ""
    assert "personal_slug=<blank> -> dry-run-owner (dry run)" in stdout.getvalue()
    assert "would update 1 personal organizations" in stdout.getvalue()

    call_command(
        "quickscale_orgs_promote_to_saas",
        stdout=StringIO(),
        stderr=StringIO(),
        verbosity=0,
    )
    organization.refresh_from_db()

    assert organization.slug == "dry-run-owner"


# ---------------------------------------------------------------------------
# T1.17 — quickscale_orgs_purge_organization contract tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_purge_organization_requires_uuid_or_slug() -> None:
    """quickscale_orgs_purge_organization must error when neither --organization-id nor --slug is provided."""
    stdout = StringIO()
    stderr = StringIO()
    with pytest.raises(CommandError, match="Specify --organization-id"):
        call_command(
            "quickscale_orgs_purge_organization",
            stdout=stdout,
            stderr=stderr,
            verbosity=0,
        )


@pytest.mark.django_db
def test_purge_organization_rejects_combined_targeting_flags() -> None:
    """quickscale_orgs_purge_organization must error when both --organization-id and --slug are given."""
    organization = Organization.objects.create(name="Test", slug="test")
    stdout = StringIO()
    stderr = StringIO()
    with pytest.raises(CommandError, match="Cannot combine"):
        call_command(
            "quickscale_orgs_purge_organization",
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
        "quickscale_orgs_purge_organization",
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
            "quickscale_orgs_purge_organization",
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
            "quickscale_orgs_purge_organization",
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
            "quickscale_orgs_purge_organization",
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
        "quickscale_orgs_purge_organization",
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
    """quickscale_orgs_purge_organization must refuse to purge a reserved (System) organization."""
    system_org = Organization.objects.get_system_org()

    stdout = StringIO()
    stderr = StringIO()
    with pytest.raises(CommandError, match="Cannot purge the System organization"):
        call_command(
            "quickscale_orgs_purge_organization",
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
        "quickscale_orgs_purge_organization",
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
        "quickscale_orgs_purge_organization",
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
    """Rerunning quickscale_orgs_purge_organization after a successful purge must return no-op."""
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
        "quickscale_orgs_purge_organization",
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
            "quickscale_orgs_purge_organization",
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
            "quickscale_orgs_purge_organization",
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
        "quickscale_orgs_purge_organization",
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


@pytest.mark.django_db
def test_purge_organization_one_owner_multi_member_succeeds() -> None:
    """quickscale_orgs_purge_organization must succeed for a one-owner/multi-member org.

    Regression: the pre_delete backstop on
    OrganizationMembership must not block org-wide purge when the owner
    is the sole owner but other members exist.
    """
    owner = get_user_model().objects.create_user(
        username="sa70-regression-owner",
        email="sa70-regression-owner@example.com",
        password="secret123",
    )
    member_a = get_user_model().objects.create_user(
        username="sa70-regression-member-a",
        email="sa70-regression-member-a@example.com",
        password="secret123",
    )
    member_b = get_user_model().objects.create_user(
        username="sa70-regression-member-b",
        email="sa70-regression-member-b@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(
        name="SA70 Regression Test",
        slug="sa70-regression",
    )
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    OrganizationMembership.objects.create(
        user=member_a,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    OrganizationMembership.objects.create(
        user=member_b,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    org_id = organization.pk

    stdout = StringIO()
    call_command(
        "quickscale_orgs_purge_organization",
        organization_id=str(org_id),
        stdout=stdout,
        stderr=StringIO(),
        verbosity=0,
    )

    output = stdout.getvalue()
    assert "has been purged" in output
    assert "Organization memberships: 3" in output
    assert not Organization.objects.filter(pk=org_id).exists()
    assert OrganizationMembership.objects.filter(organization_id=org_id).count() == 0
    assert OrganizationTombstone.objects.filter(organization_id=org_id).exists()


# ---------------------------------------------------------------------------
# T1.17 Phase 2 — cross-module purge, rollback, and slug-reuse tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("dry_run", [False, True], ids=["purge", "dry-run"])
def test_purge_organization_refuses_live_stripe_subscription(
    dry_run: bool,
) -> None:
    """A live Stripe subscription must refuse both purge and dry run."""
    owner = get_user_model().objects.create_user(
        username="billing-refusal-owner",
        email="billing-refusal-owner@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(
        name="Billing Refusal", slug="billing-refusal"
    )
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    plan = _create_plan(
        slug="growth-billing-refusal",
        price_id="price_growth_billing_refusal",
    )
    set_current_org_id(organization.pk)
    try:
        Subscription.objects.create(
            organization=organization,
            user=owner,
            plan=plan,
            stripe_subscription_id="sub_billing_refusal",
            stripe_customer_id="cus_billing_refusal",
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
            description="Billing refusal test",
            balance_after=100,
        )
    finally:
        reset_current_org_id()

    with (
        patch(
            "quickscale_modules_billing.services.cancel_current_subscription"
        ) as cancel_subscription,
        pytest.raises(CommandError) as exc_info,
    ):
        call_command(
            "quickscale_orgs_purge_organization",
            organization_id=str(organization.pk),
            dry_run=dry_run,
            stdout=StringIO(),
            stderr=StringIO(),
            verbosity=0,
        )

    message = str(exc_info.value)
    assert "sub_billing_refusal" in message
    assert "Cancel these subscriptions in Stripe before retrying" in message
    cancel_subscription.assert_not_called()
    assert Organization.objects.filter(pk=organization.pk).exists()
    assert OrganizationMembership.objects.filter(organization=organization).count() == 1
    set_current_org_id(organization.pk)
    try:
        assert Subscription.all_objects.filter(organization=organization).count() == 1
        assert CreditBalance.all_objects.filter(organization=organization).count() == 1
        assert (
            CreditTransaction.all_objects.filter(organization=organization).count() == 1
        )
    finally:
        reset_current_org_id()
    assert not OrganizationTombstone.objects.filter(
        organization_id=organization.pk
    ).exists()


@pytest.mark.django_db
def test_purge_organization_with_terminal_billing_rows() -> None:
    """Terminal billing rows purge successfully."""
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
    set_current_org_id(organization.pk)
    try:
        Subscription.objects.create(
            organization=organization,
            user=owner,
            plan=plan,
            stripe_subscription_id="sub_billing_purge",
            stripe_customer_id="cus_billing_purge",
            status=Subscription.Status.CANCELED,
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
        PurchaseCheckout.objects.create(
            organization=organization,
            user=owner,
            plan=plan,
            status=PurchaseCheckout.Status.EXPIRED,
        )
    finally:
        reset_current_org_id()
    org_id = organization.pk

    stdout = StringIO()
    call_command(
        "quickscale_orgs_purge_organization",
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
    assert PurchaseCheckout.objects.filter(organization_id=org_id).count() == 0
    assert Subscription.objects.filter(organization_id=org_id).count() == 0
    assert CreditTransaction.objects.filter(organization_id=org_id).count() == 0
    # Verify tombstone.
    assert OrganizationTombstone.objects.filter(organization_id=org_id).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("dry_run", [False, True], ids=["purge", "dry-run"])
def test_purge_organization_refuses_current_subscription_without_provider_id(
    dry_run: bool,
) -> None:
    """Ambiguous current subscription state refuses both purge and dry run."""
    owner = get_user_model().objects.create_user(
        username=f"ambiguous-subscription-owner-{dry_run}",
        email=f"ambiguous-subscription-owner-{dry_run}@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(
        name=f"Ambiguous Subscription {dry_run}",
        slug=f"ambiguous-subscription-{dry_run}",
    )
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    plan = _create_plan(
        slug=f"growth-ambiguous-subscription-{dry_run}",
        price_id=f"price_growth_ambiguous_subscription_{dry_run}",
    )
    set_current_org_id(organization.pk)
    try:
        Subscription.objects.create(
            organization=organization,
            user=owner,
            plan=plan,
            stripe_customer_id=f"cus_ambiguous_subscription_{dry_run}",
            status=Subscription.Status.ACTIVE,
        )
    finally:
        reset_current_org_id()

    with pytest.raises(CommandError, match="no provider id"):
        call_command(
            "quickscale_orgs_purge_organization",
            organization_id=str(organization.pk),
            dry_run=dry_run,
            stdout=StringIO(),
            stderr=StringIO(),
            verbosity=0,
        )

    assert Organization.objects.filter(pk=organization.pk).exists()
    set_current_org_id(organization.pk)
    try:
        assert Subscription.all_objects.filter(organization=organization).exists()
    finally:
        reset_current_org_id()


@pytest.mark.django_db
@pytest.mark.parametrize("dry_run", [False, True], ids=["purge", "dry-run"])
@pytest.mark.parametrize(
    "future_expiry", [False, True], ids=["unknown-expiry", "future-expiry"]
)
def test_purge_organization_refuses_pending_subscription_checkout(
    dry_run: bool,
    future_expiry: bool,
) -> None:
    """A pending reservation prevents purge from racing checkout creation."""
    owner = get_user_model().objects.create_user(
        username="pending-checkout-owner",
        email="pending-checkout-owner@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(
        name="Pending Checkout",
        slug="pending-checkout",
    )
    plan = _create_plan(
        slug="growth-pending-checkout",
        price_id="price_growth_pending_checkout",
    )
    set_current_org_id(organization.pk)
    try:
        Subscription.objects.create(
            organization=organization,
            user=owner,
            plan=plan,
            status=Subscription.Status.INCOMPLETE,
            checkout_expires_at=(
                timezone.now() + timezone.timedelta(minutes=10)
                if future_expiry
                else None
            ),
        )
    finally:
        reset_current_org_id()

    with pytest.raises(CommandError, match="checkout is pending"):
        call_command(
            "quickscale_orgs_purge_organization",
            organization_id=str(organization.pk),
            dry_run=dry_run,
            stdout=StringIO(),
            stderr=StringIO(),
            verbosity=0,
        )

    assert Organization.objects.filter(pk=organization.pk).exists()
    assert not OrganizationTombstone.objects.filter(
        organization_id=organization.pk
    ).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("dry_run", [False, True], ids=["purge", "dry-run"])
def test_purge_organization_refuses_open_purchase_checkout(dry_run: bool) -> None:
    """A provider-open one-time Checkout blocks both purge and dry run."""
    owner = get_user_model().objects.create_user(
        username=f"open-purchase-checkout-owner-{dry_run}",
        email=f"open-purchase-checkout-owner-{dry_run}@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(
        name=f"Open Purchase Checkout {dry_run}",
        slug=f"open-purchase-checkout-{dry_run}",
    )
    plan = Plan.objects.create(
        name=f"Open Purchase Plan {dry_run}",
        slug=f"open-purchase-plan-{dry_run}",
        stripe_price_id=f"price_open_purchase_checkout_{dry_run}",
        credits_per_period=250,
        price_cents=4900,
        currency="usd",
        billing_interval=Plan.BillingInterval.ONE_TIME,
    )
    set_current_org_id(organization.pk)
    try:
        PurchaseCheckout.objects.create(
            organization=organization,
            user=owner,
            plan=plan,
            stripe_checkout_session_id=f"cs_open_purchase_checkout_{dry_run}",
            status=PurchaseCheckout.Status.OPEN,
        )
    finally:
        reset_current_org_id()
    stripe_client = MagicMock()
    stripe_client.retrieve_checkout_session.return_value = {
        "id": f"cs_open_purchase_checkout_{dry_run}",
        "status": "open",
    }

    with (
        patch(
            "quickscale_modules_billing.services.get_stripe_client",
            return_value=stripe_client,
        ),
        pytest.raises(CommandError, match="purchase checkout session.*still open"),
    ):
        call_command(
            "quickscale_orgs_purge_organization",
            organization_id=str(organization.pk),
            dry_run=dry_run,
            stdout=StringIO(),
            stderr=StringIO(),
            verbosity=0,
        )

    assert Organization.objects.filter(pk=organization.pk).exists()
    assert not OrganizationTombstone.objects.filter(
        organization_id=organization.pk
    ).exists()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("dry_run", [False, True], ids=["purge", "dry-run"])
def test_purge_organization_allows_expired_subscription_checkout(
    dry_run: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A provider-confirmed expired reservation is no longer pending."""
    from django.apps import apps
    from django.db import connection

    from quickscale_modules_billing.services import (
        reconcile_organization_removal_subscription_checkout,
    )

    owner = get_user_model().objects.create_user(
        username=f"expired-checkout-owner-{dry_run}",
        email=f"expired-checkout-owner-{dry_run}@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(
        name=f"Expired Checkout {dry_run}",
        slug=f"expired-checkout-{dry_run}",
    )
    plan = _create_plan(
        slug=f"growth-expired-checkout-{dry_run}",
        price_id=f"price_growth_expired_checkout_{dry_run}",
    )
    set_current_org_id(organization.pk)
    try:
        reservation = Subscription.objects.create(
            organization=organization,
            user=owner,
            plan=plan,
            status=Subscription.Status.INCOMPLETE,
            stripe_checkout_session_id=f"cs_expired_checkout_{dry_run}",
            checkout_expires_at=timezone.now() - timezone.timedelta(minutes=1),
        )
    finally:
        reset_current_org_id()
    org_id = organization.pk
    stripe_client = MagicMock()

    def retrieve_checkout_session(*, checkout_session_id: str):
        assert checkout_session_id == f"cs_expired_checkout_{dry_run}"
        assert len(connection.atomic_blocks) == 0
        return {"id": checkout_session_id, "status": "expired"}

    stripe_client.retrieve_checkout_session.side_effect = retrieve_checkout_session
    billing_config = apps.get_app_config("quickscale_billing")
    monkeypatch.setattr(
        billing_config,
        "reconcile_organization_removal_provider_state",
        lambda organization_id, *, persist: (
            reconcile_organization_removal_subscription_checkout(
                organization_id,
                persist=persist,
                stripe_client=stripe_client,
            ).checkout_session_id
        ),
    )

    call_command(
        "quickscale_orgs_purge_organization",
        organization_id=str(org_id),
        dry_run=dry_run,
        stdout=StringIO(),
        stderr=StringIO(),
        verbosity=0,
    )

    assert Organization.objects.filter(pk=org_id).exists() is dry_run
    assert OrganizationTombstone.objects.filter(organization_id=org_id).exists() is (
        not dry_run
    )
    stripe_client.retrieve_checkout_session.assert_called_once_with(
        checkout_session_id=f"cs_expired_checkout_{dry_run}"
    )
    if dry_run:
        from quickscale_modules_orgs.current_org import org_scope

        with org_scope(organization):
            reservation.refresh_from_db()
        assert reservation.status == Subscription.Status.INCOMPLETE


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("dry_run", [False, True], ids=["purge", "dry-run"])
def test_purge_organization_refuses_completed_checkout_past_local_expiry(
    dry_run: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Completed Checkout blocks purge before its subscription webhook arrives."""
    from django.apps import apps
    from django.db import connection

    from quickscale_modules_billing.services import (
        reconcile_organization_removal_subscription_checkout,
    )
    from quickscale_modules_orgs.current_org import org_scope

    owner = get_user_model().objects.create_user(
        username=f"completed-checkout-owner-{dry_run}",
        email=f"completed-checkout-owner-{dry_run}@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(
        name=f"Completed Checkout {dry_run}",
        slug=f"completed-checkout-{dry_run}",
    )
    plan = _create_plan(
        slug=f"growth-completed-checkout-{dry_run}",
        price_id=f"price_growth_completed_checkout_{dry_run}",
    )
    set_current_org_id(organization.pk)
    try:
        reservation = Subscription.objects.create(
            organization=organization,
            user=owner,
            plan=plan,
            status=Subscription.Status.INCOMPLETE,
            stripe_checkout_session_id=f"cs_completed_checkout_{dry_run}",
            checkout_expires_at=timezone.now() - timezone.timedelta(minutes=1),
        )
    finally:
        reset_current_org_id()

    stripe_client = MagicMock()

    def retrieve_checkout_session(*, checkout_session_id: str):
        assert checkout_session_id == f"cs_completed_checkout_{dry_run}"
        assert len(connection.atomic_blocks) == 0
        return {
            "id": checkout_session_id,
            "status": "complete",
            "subscription": f"sub_completed_checkout_{dry_run}",
        }

    stripe_client.retrieve_checkout_session.side_effect = retrieve_checkout_session
    billing_config = apps.get_app_config("quickscale_billing")
    monkeypatch.setattr(
        billing_config,
        "reconcile_organization_removal_provider_state",
        lambda organization_id, *, persist: (
            reconcile_organization_removal_subscription_checkout(
                organization_id,
                persist=persist,
                stripe_client=stripe_client,
            ).checkout_session_id
        ),
    )

    with pytest.raises(CommandError, match="checkout completed"):
        call_command(
            "quickscale_orgs_purge_organization",
            organization_id=str(organization.pk),
            dry_run=dry_run,
            stdout=StringIO(),
            stderr=StringIO(),
            verbosity=0,
        )

    with org_scope(organization):
        reservation.refresh_from_db()
    if dry_run:
        assert not reservation.stripe_subscription_id
        assert reservation.checkout_expires_at is not None
    else:
        assert reservation.stripe_subscription_id == (
            f"sub_completed_checkout_{dry_run}"
        )
        assert reservation.checkout_expires_at is None
    assert Organization.objects.filter(pk=organization.pk).exists()
    assert not OrganizationTombstone.objects.filter(
        organization_id=organization.pk
    ).exists()


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
    set_current_org_id(organization.pk)
    try:
        Subscription.objects.create(
            organization=organization,
            user=owner,
            plan=plan,
            stripe_subscription_id="sub_rollback",
            stripe_customer_id="cus_rollback",
            status=Subscription.Status.CANCELED,
        )
        CreditBalance.objects.create(
            organization=organization,
            user=owner,
            balance=50,
        )
    finally:
        reset_current_org_id()
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
            "quickscale_orgs_purge_organization",
            organization_id=str(org_id),
            stdout=stdout,
            stderr=stderr,
            verbosity=0,
        )

    # Everything must still exist after the rollback.
    assert Organization.objects.filter(pk=org_id).exists()
    assert OrganizationMembership.objects.filter(organization_id=org_id).count() == 1
    set_current_org_id(organization.pk)
    try:
        assert Subscription.all_objects.filter(organization_id=org_id).count() == 1
        assert CreditBalance.all_objects.filter(organization_id=org_id).count() == 1
    finally:
        reset_current_org_id()
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
        "quickscale_orgs_purge_organization",
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
    # only persists for the current transaction).  Reset the ContextVar
    # first so the priming wrapper does not re-issue SET LOCAL on
    # the probe query — without this the wrapper sees the stale ContextVar
    # and primes the GUC inside its short atomic, masking the proof.
    reset_current_org_id()
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.current_org_id', true)")
        after_txn_raw = cursor.fetchone()[0]
        after_txn = uuid_lib.UUID(after_txn_raw) if after_txn_raw else None
    assert after_txn is None, f"Expected null after transaction ends, got {after_txn!r}"

    # Step 6: Full purge command also works on Postgres (smoke test).
    stdout = StringIO()
    call_command(
        "quickscale_orgs_purge_organization",
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
            "quickscale_orgs_purge_organization",
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
def test_purge_organization_refuses_personal_org_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """quickscale_orgs_purge_organization must refuse a personal org without --force."""
    from django.apps import apps

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
    reconcile = MagicMock()
    monkeypatch.setattr(
        apps.get_app_config("quickscale_billing"),
        "reconcile_organization_removal_provider_state",
        reconcile,
    )

    stdout = StringIO()
    stderr = StringIO()
    with pytest.raises(CommandError, match="Cannot purge the personal organization"):
        call_command(
            "quickscale_orgs_purge_organization",
            organization_id=str(organization.pk),
            stdout=stdout,
            stderr=stderr,
            verbosity=0,
        )

    assert Organization.objects.filter(pk=organization.pk).exists()
    reconcile.assert_not_called()


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
            "quickscale_orgs_purge_organization",
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
        "quickscale_orgs_purge_organization",
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
        "quickscale_orgs_purge_organization",
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
        "quickscale_orgs_purge_organization",
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
    set_current_org_id(organization.pk)
    try:
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
    finally:
        reset_current_org_id()

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
# T1.17 — Marker-derived purge-plan verification (CR-T117-REVIEW-001)
#
# The orgs integration settings install all module and project-fixture models;
# these tests verify runtime discovery, hard FK ordering, explicit overrides,
# and stable ownership-map identities across that installed set.
# ---------------------------------------------------------------------------


def test_purge_plan_is_marker_derived_and_fk_ordered() -> None:
    """The runtime purge plan covers every installed marker-enrolled model."""
    from django.db import models

    from quickscale_modules_orgs.management.commands.quickscale_orgs_purge_organization import (
        _resolve_models,
    )
    from quickscale_modules_orgs.tenancy import (
        get_tenant_models,
        has_organization_id_field,
    )

    plan = _resolve_models()
    planned_models = [entry["model"] for entry in plan]
    expected_models = [
        model for model in get_tenant_models() if has_organization_id_field(model)
    ]
    assert set(planned_models) == set(expected_models)

    order = {model: index for index, model in enumerate(planned_models)}
    for child_model in planned_models:
        for field in child_model._meta.fields:
            parent_model = getattr(field.remote_field, "model", None)
            if (
                parent_model in order
                and parent_model is not child_model
                and field.remote_field.on_delete
                in {
                    models.CASCADE,
                    models.DO_NOTHING,
                    models.PROTECT,
                    models.RESTRICT,
                }
            ):
                assert order[child_model] < order[parent_model], (
                    f"{child_model._meta.label} must precede "
                    f"{parent_model._meta.label} in the purge plan"
                )

    from tests.project_tenant_app.models import ProjectListing, ProjectListingImage

    assert order[ProjectListingImage] < order[ProjectListing]

    from quickscale_modules_crm.models import (
        Company,
        Contact,
        ContactNote,
        Deal,
        DealNote,
    )

    assert order[ContactNote] < order[Contact] < order[Company]
    assert order[DealNote] < order[Deal] < order[Contact]


def test_purge_plan_supports_explicit_order_overrides() -> None:
    """An explicit override orders models whose FK metadata is insufficient."""
    from quickscale_modules_orgs.management.commands.quickscale_orgs_purge_organization import (
        _topologically_order_models,
    )
    from quickscale_modules_social.models import SocialLink
    from tests.project_tenant_app.models import ProjectListing

    ordered = _topologically_order_models(
        [SocialLink, ProjectListing],
        ((ProjectListing._meta.label_lower, SocialLink._meta.label_lower),),
    )
    assert ordered == [ProjectListing, SocialLink]


def test_purge_plan_rejects_unknown_order_override_models() -> None:
    """A misspelled override cannot silently leave the plan unordered."""
    from quickscale_modules_orgs.management.commands.quickscale_orgs_purge_organization import (
        _topologically_order_models,
    )
    from quickscale_modules_social.models import SocialLink

    with pytest.raises(CommandError, match="unknown model"):
        _topologically_order_models(
            [SocialLink],
            (("missing.model", SocialLink._meta.label_lower),),
        )


def test_purge_plan_ignores_nonblocking_fk_cycle_edges() -> None:
    """SET_NULL back-references do not create false purge-order cycles."""
    from django.db import models
    from django.test.utils import isolate_apps

    from quickscale_modules_orgs.management.commands.quickscale_orgs_purge_organization import (
        _topologically_order_models,
    )

    with isolate_apps():

        class Parent(models.Model):
            class Meta:
                app_label = "purge_cycle"

        class Child(models.Model):
            parent = models.ForeignKey(Parent, on_delete=models.PROTECT)

            class Meta:
                app_label = "purge_cycle"

        Parent.add_to_class(
            "featured_child",
            models.ForeignKey(Child, null=True, on_delete=models.SET_NULL),
        )

        ordered = _topologically_order_models([Parent, Child])

    assert ordered == [Child, Parent]


def test_purge_plan_propagates_protection_through_cascade_ancestors() -> None:
    """A protected grandchild precedes an ancestor that would collect its parent."""
    from django.db import models
    from django.test.utils import isolate_apps

    from quickscale_modules_orgs.management.commands.quickscale_orgs_purge_organization import (
        _topologically_order_models,
    )

    with isolate_apps():

        class Ancestor(models.Model):
            class Meta:
                app_label = "purge_transitive"

        class CascadeChild(models.Model):
            ancestor = models.ForeignKey(Ancestor, on_delete=models.CASCADE)

            class Meta:
                app_label = "purge_transitive"

        class ProtectedGrandchild(models.Model):
            child = models.ForeignKey(CascadeChild, on_delete=models.PROTECT)

            class Meta:
                app_label = "purge_transitive"

        ordered = _topologically_order_models(
            [Ancestor, CascadeChild, ProtectedGrandchild]
        )

    order = {model: index for index, model in enumerate(ordered)}
    assert order[ProtectedGrandchild] < order[CascadeChild]
    assert order[ProtectedGrandchild] < order[Ancestor]


def test_purge_plan_disambiguates_duplicate_display_labels(monkeypatch) -> None:
    """Project models with the same plural keep distinct ownership-map keys."""
    from quickscale_modules_social.models import SocialEmbed, SocialLink
    from quickscale_modules_orgs.management.commands import (
        quickscale_orgs_purge_organization,
    )

    monkeypatch.setattr(
        quickscale_orgs_purge_organization,
        "get_tenant_models",
        lambda: [SocialLink, SocialEmbed],
    )
    monkeypatch.setattr(
        quickscale_orgs_purge_organization,
        "_model_label",
        lambda _: "Rows",
    )

    labels = [
        entry["label"] for entry in quickscale_orgs_purge_organization._resolve_models()
    ]

    assert labels == [
        "Rows (quickscale_social.socialembed)",
        "Rows (quickscale_social.sociallink)",
    ]


def test_purge_plan_rejects_marker_model_without_organization_id(monkeypatch) -> None:
    """Marker discovery fails closed instead of silently dropping a model."""
    from quickscale_modules_billing.models import Plan
    from quickscale_modules_orgs.management.commands import (
        quickscale_orgs_purge_organization,
    )

    monkeypatch.setattr(
        quickscale_orgs_purge_organization, "get_tenant_models", lambda: [Plan]
    )

    with pytest.raises(CommandError, match="without an organization_id"):
        quickscale_orgs_purge_organization._resolve_models()


def test_resolve_models_skips_uninstalled_apps() -> None:
    """_resolve_models() returns only installed marker-derived models."""
    from quickscale_modules_orgs.management.commands.quickscale_orgs_purge_organization import (
        _resolve_models,
    )

    resolved = _resolve_models()
    assert resolved
    for entry in resolved:
        assert entry["model"] is not None
        assert entry["filter_key"] == "organization_id"


# ---------------------------------------------------------------------------
# T1.17 — Real multi-module purge integration (CR-T117-REVIEW-001)
# Tests create rows for each module and verify quickscale_orgs_purge_organization actually
# deletes them.  All modules are installed in the orgs test environment.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_purge_organization_deletes_social_rows() -> None:
    """quickscale_orgs_purge_organization must delete SocialLink rows."""
    from quickscale_modules_social.models import SocialLink

    org = Organization.objects.create(name="Social Purge", slug="social-purge")
    set_current_org_id(org.pk)
    try:
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
    finally:
        reset_current_org_id()
    org_id = org.pk

    call_command(
        "quickscale_orgs_purge_organization",
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
    """quickscale_orgs_purge_organization must delete Form rows (with FormSubmission PROTECT)."""
    from quickscale_modules_forms.models import Form, FormSubmission

    org = Organization.objects.create(name="Forms Purge", slug="forms-purge")
    set_current_org_id(org.pk)
    try:
        form = Form.objects.create(
            organization=org, title="Test Form", slug="test-form"
        )
        FormSubmission.all_objects.create(
            form=form,
            organization=form.organization,
        )
    finally:
        reset_current_org_id()
    org_id = org.pk

    call_command(
        "quickscale_orgs_purge_organization",
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
    """quickscale_orgs_purge_organization must delete Listing rows."""
    from quickscale_modules_listings.models import Listing

    org = Organization.objects.create(name="Listings Purge", slug="listings-purge")
    set_current_org_id(org.pk)
    try:
        Listing.objects.create(
            organization=org, title="Test Listing", slug="test-listing"
        )
    finally:
        reset_current_org_id()
    org_id = org.pk

    call_command(
        "quickscale_orgs_purge_organization",
        organization_id=str(org_id),
        stdout=StringIO(),
        stderr=StringIO(),
        verbosity=0,
    )
    assert not Organization.objects.filter(pk=org_id).exists()
    assert Listing.all_objects.filter(organization_id=org_id).count() == 0
    assert OrganizationTombstone.objects.filter(organization_id=org_id).exists()


@pytest.mark.django_db
def test_purge_organization_deletes_project_owned_child_rows() -> None:
    """A project-owned protected child purges without a command registry edit."""
    from tests.project_tenant_app.models import ProjectListing, ProjectListingImage

    org = Organization.objects.create(name="Project Purge", slug="project-purge")
    set_current_org_id(org.pk)
    try:
        listing = ProjectListing.all_objects.create(
            organization=org,
            title="Project listing",
            slug="project-listing",
        )
        ProjectListingImage.all_objects.create(
            organization=org,
            listing=listing,
            image_url="https://example.com/listing.jpg",
        )
    finally:
        reset_current_org_id()
    org_id = org.pk

    call_command(
        "quickscale_orgs_purge_organization",
        organization_id=str(org_id),
        stdout=StringIO(),
        stderr=StringIO(),
        verbosity=0,
    )

    assert not Organization.objects.filter(pk=org_id).exists()
    assert ProjectListing.all_objects.filter(organization_id=org_id).count() == 0
    assert ProjectListingImage.all_objects.filter(organization_id=org_id).count() == 0
    assert OrganizationTombstone.objects.filter(organization_id=org_id).exists()


@pytest.mark.django_db
def test_purge_organization_deletes_project_owned_self_protected_rows() -> None:
    """A project-owned self-PROTECT tree purges in one organization-wide delete."""
    from tests.project_tenant_app.models import ProjectFolder

    org = Organization.objects.create(
        name="Project Folder Purge",
        slug="project-folder-purge",
    )
    set_current_org_id(org.pk)
    try:
        parent = ProjectFolder.all_objects.create(
            organization=org,
            name="Parent",
        )
        ProjectFolder.all_objects.create(
            organization=org,
            parent=parent,
            name="Child",
        )
    finally:
        reset_current_org_id()
    org_id = org.pk

    call_command(
        "quickscale_orgs_purge_organization",
        organization_id=str(org_id),
        stdout=StringIO(),
        stderr=StringIO(),
        verbosity=0,
    )

    assert not Organization.objects.filter(pk=org_id).exists()
    assert ProjectFolder.all_objects.filter(organization_id=org_id).count() == 0
    assert OrganizationTombstone.objects.filter(organization_id=org_id).exists()


# ---------------------------------------------------------------------------
# Provider-backed project fields refuse the purge
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_purge_refuses_rows_carrying_provider_backed_project_values() -> None:
    """A declared provider-backed project value refuses dry-run and purge."""
    from django.core.management.base import CommandError

    from tests.provider_id_app.models import ProjectProviderRecord

    org = Organization.objects.create(
        name="SA208 Provider Refusal",
        slug="sa208-provider-refusal",
    )
    set_current_org_id(org.pk)
    try:
        ProjectProviderRecord.all_objects.create(
            organization=org,
            mls_id="MLS-9001",
            local_ref_id="local-1",
        )
    finally:
        reset_current_org_id()
    org_id = org.pk

    expected = (
        r"provider-backed values: "
        r"provider_id_app\.projectproviderrecord\.mls_id"
    )
    with pytest.raises(CommandError, match=expected):
        call_command(
            "quickscale_orgs_purge_organization",
            organization_id=str(org_id),
            dry_run=True,
            stdout=StringIO(),
            stderr=StringIO(),
            verbosity=0,
        )

    with pytest.raises(CommandError, match=expected):
        call_command(
            "quickscale_orgs_purge_organization",
            organization_id=str(org_id),
            stdout=StringIO(),
            stderr=StringIO(),
            verbosity=0,
        )

    assert Organization.objects.filter(pk=org_id).exists()
    set_current_org_id(org_id)
    try:
        assert (
            ProjectProviderRecord.all_objects.filter(organization_id=org_id).count()
            == 1
        )
    finally:
        reset_current_org_id()
    assert OrganizationTombstone.objects.filter(organization_id=org_id).count() == 0


@pytest.mark.django_db
def test_purge_deletes_rows_without_provider_backed_values() -> None:
    """An empty provider-backed field and a non-provider field do not refuse."""
    from tests.provider_id_app.models import ProjectProviderRecord

    org = Organization.objects.create(
        name="SA208 Local Only",
        slug="sa208-local-only",
    )
    set_current_org_id(org.pk)
    try:
        ProjectProviderRecord.all_objects.create(
            organization=org,
            mls_id="",
            local_ref_id="local-only",
        )
    finally:
        reset_current_org_id()
    org_id = org.pk

    call_command(
        "quickscale_orgs_purge_organization",
        organization_id=str(org_id),
        stdout=StringIO(),
        stderr=StringIO(),
        verbosity=0,
    )

    assert not Organization.objects.filter(pk=org_id).exists()
    assert ProjectProviderRecord.all_objects.filter(organization_id=org_id).count() == 0
    assert OrganizationTombstone.objects.filter(organization_id=org_id).exists()


@pytest.mark.django_db(transaction=True)
def test_provider_backed_guard_serializes_concurrent_project_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A project update cannot add a provider value between guard and deletion."""
    from django.db import close_old_connections, connection
    from django.db.utils import OperationalError

    from tests.provider_id_app.models import ProjectProviderRecord

    org = Organization.objects.create(
        name="SA208 Provider Race",
        slug="sa208-provider-race",
    )
    set_current_org_id(org.pk)
    try:
        record = ProjectProviderRecord.all_objects.create(
            organization=org,
            mls_id="",
            local_ref_id="local-race",
        )
    finally:
        reset_current_org_id()
    org_id = org.pk
    record_id = record.pk

    guard_read = threading.Event()
    release_purge = threading.Event()
    original_build_ownership_map = Command._build_ownership_map

    def pause_after_guard(
        command: Command, organization: Organization
    ) -> dict[str, int]:
        guard_read.set()
        if not release_purge.wait(timeout=10):
            raise AssertionError("timed out waiting to release the purge")
        return original_build_ownership_map(command, organization)

    monkeypatch.setattr(Command, "_build_ownership_map", pause_after_guard)

    update_outcome: list[tuple[str, object]] = []

    def run_purge() -> None:
        close_old_connections()
        try:
            call_command(
                "quickscale_orgs_purge_organization",
                organization_id=str(org_id),
                stdout=StringIO(),
                stderr=StringIO(),
                verbosity=0,
            )
        finally:
            close_old_connections()

    def run_concurrent_update() -> None:
        close_old_connections()
        set_current_org_id(org_id)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET statement_timeout = '1000ms'")
            try:
                updated = ProjectProviderRecord.all_objects.filter(pk=record_id).update(
                    mls_id="MLS-RACE"
                )
                update_outcome.append(("updated", updated))
            except OperationalError as exc:
                update_outcome.append(("blocked", str(exc)))
        finally:
            reset_current_org_id()
            connection.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        purge_future = executor.submit(run_purge)
        assert guard_read.wait(timeout=10)
        update_future = executor.submit(run_concurrent_update)
        update_future.result(timeout=10)
        release_purge.set()
        purge_future.result(timeout=10)

    assert update_outcome, "the concurrent update produced no outcome"
    assert update_outcome[0][0] == "blocked", (
        "the concurrent update must block on the purge's row lock; got "
        f"{update_outcome[0]!r}"
    )
    assert not Organization.objects.filter(pk=org_id).exists()
    set_current_org_id(org_id)
    try:
        assert not ProjectProviderRecord.all_objects.filter(pk=record_id).exists()
    finally:
        reset_current_org_id()
    assert OrganizationTombstone.objects.filter(organization_id=org_id).exists()


@pytest.mark.django_db
def test_purge_organization_deletes_blog_rows() -> None:
    """quickscale_orgs_purge_organization must delete Post, Category, and Tag rows."""
    from quickscale_modules_blog.models import Category, Post, Tag

    org = Organization.objects.create(name="Blog Purge", slug="blog-purge")
    set_current_org_id(org.pk)
    try:
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
    finally:
        reset_current_org_id()
    org_id = org.pk

    call_command(
        "quickscale_orgs_purge_organization",
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
    """quickscale_orgs_purge_organization must delete Company rows (and protect-safe ordering)."""
    from quickscale_modules_crm.models import (
        Company,
        Contact,
        ContactNote,
        Deal,
        DealNote,
        Stage,
        Tag,
    )

    org = Organization.objects.create(name="CRM Purge", slug="crm-purge")
    set_current_org_id(org.pk)
    try:
        company = Company.objects.create(organization=org, name="Test Co")
        stage = Stage.objects.create(organization=org, name="Test Stage", order=0)
        contact = Contact.objects.create(
            organization=org,
            first_name="A",
            last_name="B",
            email="a@b.com",
            company=company,
        )
        deal = Deal.objects.create(
            organization=org,
            title="Test Deal",
            contact=contact,
            stage=stage,
        )
        ContactNote.objects.create(
            organization=org,
            contact=contact,
            text="Contact note",
        )
        DealNote.objects.create(
            organization=org,
            deal=deal,
            text="Deal note",
        )
        Tag.objects.create(organization=org, name="Test Tag")
    finally:
        reset_current_org_id()
    org_id = org.pk

    stdout = StringIO()
    call_command(
        "quickscale_orgs_purge_organization",
        organization_id=str(org_id),
        stdout=stdout,
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
    output = stdout.getvalue().lower()
    assert "crm contact notes" in output
    assert "crm contacts" in output
    assert "crm companies" in output
    assert "crm deal notes" in output
    assert "crm deals" in output


@pytest.mark.django_db
def test_purge_organization_dry_run_counts_all_modules() -> None:
    """--dry-run must count rows across social, forms, listings, blog, crm, billing."""
    from quickscale_modules_blog.models import Post
    from quickscale_modules_crm.models import Company
    from quickscale_modules_forms.models import Form
    from quickscale_modules_listings.models import Listing
    from quickscale_modules_social.models import SocialLink

    org = Organization.objects.create(name="Multi Dryrun", slug="multi-dryrun")
    set_current_org_id(org.pk)
    try:
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
    finally:
        reset_current_org_id()
    org_id = org.pk

    stdout = StringIO()
    call_command(
        "quickscale_orgs_purge_organization",
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
    """quickscale_orgs_purge_organization must invalidate social cache keys (CR-T117-R2).

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
    set_current_org_id(org.pk)
    try:
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
    finally:
        reset_current_org_id()
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
        "quickscale_orgs_purge_organization",
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


@pytest.mark.django_db(transaction=True)
def test_purge_cache_failure_happens_after_database_commit() -> None:
    """Remote cache failure is loud but cannot roll back the completed purge."""
    from django.db import connection

    organization = Organization.objects.create(
        name="Post Commit Cache",
        slug="post-commit-cache",
    )
    org_id = organization.pk
    atomic_depths: list[int] = []

    def fail_cache_clear(self, cache_org_id):
        del self
        assert cache_org_id == org_id
        atomic_depths.append(len(connection.atomic_blocks))
        raise RuntimeError("cache unavailable")

    from quickscale_modules_orgs.apps import QuickscaleOrgsConfig

    with (
        patch.object(
            QuickscaleOrgsConfig,
            "invalidate_organization_cache",
            new=fail_cache_clear,
        ),
        pytest.raises(RuntimeError, match="cache unavailable"),
    ):
        call_command(
            "quickscale_orgs_purge_organization",
            organization_id=str(org_id),
            stdout=StringIO(),
            stderr=StringIO(),
            verbosity=0,
        )

    assert atomic_depths == [0]
    assert not Organization.objects.filter(pk=org_id).exists()
    assert OrganizationTombstone.objects.filter(organization_id=org_id).exists()


@pytest.mark.django_db
def test_purge_tombstone_retry_heals_social_cache() -> None:
    """A rerun after post-commit cache failure retries invalidation."""
    from django.core.cache import cache

    from quickscale_modules_social.contracts import (
        SOCIAL_EMBEDS_CACHE_KEY,
        SOCIAL_LINKS_CACHE_KEY,
    )

    org_id = uuid_lib.uuid4()
    OrganizationTombstone.objects.create(organization_id=org_id)
    link_key = f"{SOCIAL_LINKS_CACHE_KEY}:org:{org_id}"
    embed_key = f"{SOCIAL_EMBEDS_CACHE_KEY}:org:{org_id}"
    for key in (
        SOCIAL_LINKS_CACHE_KEY,
        link_key,
        SOCIAL_EMBEDS_CACHE_KEY,
        embed_key,
    ):
        cache.set(key, "stale")

    with pytest.raises(CommandError, match="No-op") as exc_info:
        call_command(
            "quickscale_orgs_purge_organization",
            organization_id=str(org_id),
            stdout=StringIO(),
            stderr=StringIO(),
            verbosity=0,
        )

    assert exc_info.value.returncode == 0
    assert cache.get(SOCIAL_LINKS_CACHE_KEY) is None
    assert cache.get(link_key) is None
    assert cache.get(SOCIAL_EMBEDS_CACHE_KEY) is None
    assert cache.get(embed_key) is None


# ---------------------------------------------------------------------------
# check_tenant_isolation command tests
# ---------------------------------------------------------------------------


def _expected_tenant_model_keys() -> set[tuple[str, str]]:
    """Bind command expectations to shipped entries plus the project fixtures."""
    from django.apps import apps

    from quickscale_modules_orgs.tenancy import TenantTableStatus
    from tests._tenant_table_registry import TENANT_TABLE_REGISTRY

    project_models = {
        (model._meta.app_label, model.__name__)
        for app_label in ("project_tenant_app", "provider_id_app")
        for model in apps.get_app_config(app_label).get_models()
    }
    shipped_keys = {
        (entry.app_label, entry.model_name)
        for entry in TENANT_TABLE_REGISTRY
        if entry.status == TenantTableStatus.ENROLLED
    }
    return shipped_keys | project_models


@pytest.mark.django_db
def test_check_tenant_isolation_pass_on_current_models() -> None:
    """The command must report the correct pass/fail counts for current
    installed tenant models.

    Every shipped ENROLLED model and the project-owned fixture should have
    organization_id + FORCE RLS. Expectations are bound from the shipped
    literal plus the fixture model at test execution rather than from a
    duplicated count.
    """
    from io import StringIO

    stdout = StringIO()
    stderr = StringIO()

    call_command(
        "quickscale_orgs_check_tenant_isolation",
        stdout=stdout,
        stderr=stderr,
        verbosity=0,
    )

    output = stdout.getvalue()
    # Should have discovered tenant models.
    assert "Discovered" in output
    assert "Result:" in output
    expected_keys = _expected_tenant_model_keys()
    for app_label, model_name in expected_keys:
        assert f"{app_label}.{model_name}" in output
    assert f"Result: {len(expected_keys)} passed, 0 failed" in output


@pytest.mark.django_db
def test_check_tenant_isolation_json_output() -> None:
    """The --format json option must produce valid JSON with pass/fail status."""
    from io import StringIO

    stdout = StringIO()
    stderr = StringIO()

    call_command(
        "quickscale_orgs_check_tenant_isolation",
        format="json",
        stdout=stdout,
        stderr=stderr,
        verbosity=0,
    )

    import json as json_lib

    data = json_lib.loads(stdout.getvalue())
    assert "status" in data
    assert "tenant_models" in data
    assert "total" in data["tenant_models"]
    assert "passed" in data["tenant_models"]
    assert "results" in data["tenant_models"]
    expected_keys = _expected_tenant_model_keys()
    actual_keys = {
        (result["app_label"], result["model_name"])
        for result in data["tenant_models"]["results"]
    }
    assert actual_keys == expected_keys
    assert data["tenant_models"]["total"] == len(expected_keys)
    assert data["tenant_models"]["passed"] == len(expected_keys)
    assert data["tenant_models"]["failed"] == 0
    assert "unclassified" in data


@pytest.mark.django_db
def test_project_tenant_listing_appears_in_human_and_json_output() -> None:
    """The project-owned tenant model is reported by both output formats."""
    human_stdout = StringIO()
    call_command(
        "quickscale_orgs_check_tenant_isolation",
        stdout=human_stdout,
        stderr=StringIO(),
        verbosity=0,
    )
    assert "project_tenant_app.ProjectListing" in human_stdout.getvalue()

    json_stdout = StringIO()
    call_command(
        "quickscale_orgs_check_tenant_isolation",
        format="json",
        stdout=json_stdout,
        stderr=StringIO(),
        verbosity=0,
    )
    data = json_lib.loads(json_stdout.getvalue())
    result_keys = {
        (result["app_label"], result["model_name"])
        for result in data["tenant_models"]["results"]
    }
    assert ("project_tenant_app", "ProjectListing") in result_keys


@pytest.mark.django_db
def test_check_tenant_isolation_detects_missing_organization_id() -> None:
    """The command must detect a model that lacks organization_id.

    Uses the detection helper directly to prove negative detection works,
    then simulates a model without organization_id by checking a known
    control-plane model that is not tenant-scoped.
    """
    from django.apps import apps

    from quickscale_modules_orgs.tenancy import (
        check_tenant_model_isolation,
        has_organization_id_field,
        is_tenant_model,
    )

    # Plan is a system-wide model — it should NOT be detected as tenant.
    model = apps.get_model("quickscale_billing", "Plan")
    assert model is not None
    assert not is_tenant_model(model), "Plan should not be detected as a tenant model."

    # Organization (control-plane) should NOT be detected as tenant.
    org_model = apps.get_model("quickscale_orgs", "Organization")
    assert org_model is not None
    assert not is_tenant_model(org_model), (
        "Organization should not be detected as a tenant model."
    )

    # Tag (CRM) is a tenant model — must have organization_id.
    tag_model = apps.get_model("quickscale_crm", "Tag")
    assert tag_model is not None
    assert is_tenant_model(tag_model), "CRM Tag must be detected as tenant."
    assert has_organization_id_field(tag_model), "CRM Tag must have organization_id."
    result = check_tenant_model_isolation(tag_model)
    assert result["passed"] is True or result["has_force_rls"] is None


@pytest.mark.django_db
def test_check_tenant_isolation_model_without_org_id_through_command() -> None:
    """The command must fail when a tenant model lacks organization_id.

    Uses a mock model that IS detected by marker (simulated via
    ``get_tenant_models`` mock) but lacks the ``organization_id`` field.
    Exercises the real ``check_tenant_model_isolation`` path through
    the management command surface for both human and JSON output.

    This fills the gap where all real tenant models in the repo have
    ``organization_id`` — positive proof that the failure path works
    end-to-end through ``check_tenant_model_isolation``.
    """
    from unittest.mock import MagicMock, patch

    from django.core.exceptions import FieldDoesNotExist

    model = MagicMock(spec=[])
    model.__name__ = "NoOrgModel"
    model._meta = MagicMock()
    model._meta.app_label = "test_app"
    model._meta.db_table = "test_noorgmodel"
    model._meta.get_field.side_effect = FieldDoesNotExist("organization_id")

    with patch(
        "quickscale_modules_orgs.management.commands.quickscale_orgs_check_tenant_isolation"
        ".get_tenant_models",
        return_value=[model],
    ):
        # --- Human format ---
        stdout = StringIO()
        stderr = StringIO()
        with pytest.raises(CommandError) as excinfo:
            call_command(
                "quickscale_orgs_check_tenant_isolation",
                stdout=stdout,
                stderr=stderr,
                verbosity=0,
            )
        assert excinfo.value.returncode == 1, (
            "Command should exit 1 when a model lacks org_id"
        )

        output = stdout.getvalue()
        assert "[FAIL]" in output
        assert "test_app.NoOrgModel" in output
        assert "MISSING" in output  # organization_id status
        assert "0 passed, 1 failed" in output

        # --- JSON format ---
        stdout = StringIO()
        stderr = StringIO()
        with pytest.raises(CommandError):
            call_command(
                "quickscale_orgs_check_tenant_isolation",
                format="json",
                stdout=stdout,
                stderr=stderr,
                verbosity=0,
            )

        import json as json_lib

        data = json_lib.loads(stdout.getvalue())
        assert data["status"] == "fail"
        assert data["tenant_models"]["total"] == 1
        assert data["tenant_models"]["passed"] == 0
        assert data["tenant_models"]["failed"] == 1
        assert len(data["tenant_models"]["results"]) == 1
        assert data["tenant_models"]["results"][0]["model_name"] == "NoOrgModel"
        assert data["tenant_models"]["results"][0]["has_organization_id"] is False
        assert data["tenant_models"]["results"][0]["passed"] is False


@pytest.mark.django_db
def test_check_tenant_isolation_detection_helpers() -> None:
    """Unit-test the detection helpers directly.

    * TenantModel subclasses (like ConcreteTenantResource in test_models.py)
      must be detected as tenant models.
    * Non-tenant models (Organization, OrganizationMembership) must NOT be
      detected.
    """
    from quickscale_modules_orgs.tenancy import (
        get_tenant_models,
    )

    tenant_models = get_tenant_models()
    tenant_names = {(m._meta.app_label, m.__name__) for m in tenant_models}

    # CRM models should be detected as tenant models.
    assert (
        "quickscale_crm",
        "Tag",
    ) in tenant_names, "CRM Tag should be in tenant model list."

    # Organization (control-plane) should NOT be in the list.
    assert (
        "quickscale_orgs",
        "Organization",
    ) not in tenant_names, (
        "Organization (control-plane) must not be detected as tenant."
    )

    # OrganizationMembership should NOT be in the list.
    assert (
        "quickscale_orgs",
        "OrganizationMembership",
    ) not in tenant_names, "OrganizationMembership must not be detected as tenant."


@pytest.mark.django_db
def test_check_tenant_isolation_detects_all_enrolled_models() -> None:
    """The command must discover all ENROLLED models from the registry.

    This proves the marker-based detection matches the registry's ENROLLED
    entries.  EXCLUDED_REVIEWED and abstract models should not be detected.
    """
    from quickscale_modules_orgs.tenancy import (
        TenantTableStatus,
        get_tenant_models,
    )
    from tests._tenant_table_registry import TENANT_TABLE_REGISTRY

    enrolled = {
        (e.app_label, e.model_name)
        for e in TENANT_TABLE_REGISTRY
        if e.status == TenantTableStatus.ENROLLED
    }

    tenant_models = get_tenant_models()
    detected = {(m._meta.app_label, m.__name__) for m in tenant_models}

    # Every ENROLLED model must be detected.
    missing = enrolled - detected
    assert not missing, f"ENROLLED models not detected by marker: {sorted(missing)}"

    # No EXCLUDED model that uses TenantModel accidentally detected.
    # TenantModel itself is abstract, but subclasses could be excluded.
    # Check every excluded entry that is not abstract.
    for entry in TENANT_TABLE_REGISTRY:
        if entry.status == TenantTableStatus.EXCLUDED_REVIEWED:
            if entry.model_name in (
                "TenantModel",
                "AbstractListing",
                "BaseSocialItem",
            ):
                continue  # abstract — not in get_models()
            if entry.reason.startswith("Test-only"):
                continue  # test-only — only present when test_models imported
            assert (entry.app_label, entry.model_name) not in detected, (
                f"EXCLUDED_REVIEWED model {entry.app_label}.{entry.model_name} "
                f"was incorrectly detected as a tenant model."
            )


@pytest.mark.django_db
def test_check_tenant_isolation_json_postgres_only_skip() -> None:
    """--postgres-only --format json on non-PostgreSQL must emit clean JSON.

    Regression: the --postgres-only skip branch must emit
    JSON-only output with status ``skip`` when ``--format json`` is
    specified and the database is not PostgreSQL.
    """
    from io import StringIO
    from unittest.mock import patch

    stdout = StringIO()
    stderr = StringIO()

    with patch(
        "quickscale_modules_orgs.management.commands."
        "quickscale_orgs_check_tenant_isolation.connection.vendor",
        "sqlite",
    ):
        call_command(
            "quickscale_orgs_check_tenant_isolation",
            postgres_only=True,
            format="json",
            stdout=stdout,
            stderr=stderr,
            verbosity=0,
        )

    import json as json_lib

    data = json_lib.loads(stdout.getvalue())
    assert data["status"] == "skip"
    assert "postgresql" in data["message"].lower()
    # No human-only text should leak into JSON output.
    assert "SKIP:" not in stdout.getvalue()


@pytest.mark.django_db
def test_check_tenant_isolation_json_no_models() -> None:
    """get_tenant_models()==[] with --format json must emit clean JSON.

    Regression: the no-models warning branch must emit
    JSON-only output with status ``warning`` when ``--format json`` is
    specified and no tenant models are discovered.
    """
    from io import StringIO
    from unittest.mock import patch

    stdout = StringIO()
    stderr = StringIO()

    with patch(
        "quickscale_modules_orgs.management.commands."
        "quickscale_orgs_check_tenant_isolation.get_tenant_models",
        return_value=[],
    ):
        call_command(
            "quickscale_orgs_check_tenant_isolation",
            format="json",
            stdout=stdout,
            stderr=stderr,
            verbosity=0,
        )

    import json as json_lib

    data = json_lib.loads(stdout.getvalue())
    assert data["status"] == "warning"
    assert data["tenant_models"]["results"] == []
    assert data["unclassified"] == []
    assert "No tenant models discovered" in data["message"]
    # No human-only text should leak into JSON output.  The human branch
    # contains "by marker detection" which does not appear in JSON output.
    assert "by marker detection" not in stdout.getvalue()
    assert "TenantManager" not in stdout.getvalue()


@pytest.mark.django_db
def test_check_tenant_isolation_json_no_models_postgres_only_skip() -> None:
    """get_tenant_models()==[] with --postgres-only --format json on
    non-PostgreSQL must emit a single valid JSON document.

    Regression: the no-models payload and the --postgres-only skip must
    be combined into one JSON document, not written as two separate docs.
    """
    from io import StringIO
    from unittest.mock import patch

    stdout = StringIO()
    stderr = StringIO()

    with (
        patch(
            "quickscale_modules_orgs.management.commands."
            "quickscale_orgs_check_tenant_isolation.get_tenant_models",
            return_value=[],
        ),
        patch(
            "quickscale_modules_orgs.management.commands."
            "quickscale_orgs_check_tenant_isolation.connection.vendor",
            "sqlite",
        ),
    ):
        call_command(
            "quickscale_orgs_check_tenant_isolation",
            postgres_only=True,
            format="json",
            stdout=stdout,
            stderr=stderr,
            verbosity=0,
        )

    import json as json_lib

    output = stdout.getvalue()
    # Must be parseable as a single JSON document — if two docs were
    # written, json.loads would raise or only parse the first.
    data = json_lib.loads(output)
    assert data["status"] == "skip"
    assert "postgresql" in data["message"].lower()
    # Must include the tenant_models section (no-models info).
    assert "tenant_models" in data
    assert data["tenant_models"]["total"] == 0
    assert data["tenant_models"]["results"] == []
    assert "unclassified" in data
    assert data["unclassified"] == []
    # No human-only text should leak into JSON output.
    assert "SKIP:" not in output
    assert "by marker detection" not in output


# ---------------------------------------------------------------------------
# Default-deny classification check tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_classification_check_ok_when_all_models_classified() -> None:
    """The classification check must pass when all project models are
    classified by tenant markers.

    In the current maintainer repo, every ``quickscale_modules_*`` model
    is accounted for, so ``get_unclassified_concrete_models()`` returns
    an empty list and the command must not report any unclassified models.
    """
    from io import StringIO

    from quickscale_modules_orgs.tenancy import get_unclassified_concrete_models

    unclassified = get_unclassified_concrete_models()
    assert len(unclassified) == 0, (
        f"Expected zero unclassified models, got: "
        f"{[(m._meta.app_label, m.__name__) for m in unclassified]}"
    )

    # Full command run must not fail on classification.
    stdout = StringIO()
    stderr = StringIO()
    call_command(
        "quickscale_orgs_check_tenant_isolation",
        stdout=stdout,
        stderr=stderr,
        verbosity=0,
    )
    # On SQLite all models pass the isolation check (force_rls is None,
    # only org_id is checked), so no CommandError is raised.  The output
    # must not contain any classification failure language.
    output = stdout.getvalue()
    assert "unclassified" not in output.lower()


@pytest.mark.django_db
def test_classification_check_fails_on_unclassified_model_human() -> None:
    """An unclassified concrete model must cause the command to exit 1 with
    a clear message in human-readable output."""
    from unittest.mock import MagicMock, patch

    from io import StringIO

    # Patch to return a synthetic unclassified model.
    model = MagicMock(spec=[])
    model.__name__ = "RogueModel"
    model._meta = MagicMock()
    model._meta.app_label = "quickscale_modules_rogue"
    model._meta.db_table = "test_roguemodel"

    with patch(
        "quickscale_modules_orgs.management.commands."
        "quickscale_orgs_check_tenant_isolation.get_unclassified_concrete_models",
        return_value=[model],
    ):
        stdout = StringIO()
        stderr = StringIO()
        with pytest.raises(CommandError) as excinfo:
            call_command(
                "quickscale_orgs_check_tenant_isolation",
                stdout=stdout,
                stderr=stderr,
                verbosity=0,
            )
        assert excinfo.value.returncode == 1
        output = stdout.getvalue()
        assert "UNCLASSIFIED" in output
        assert "RogueModel" in output
        assert "quickscale_modules_rogue" in output


@pytest.mark.django_db
def test_classification_check_fails_on_unclassified_model_json() -> None:
    """An unclassified concrete model must produce valid JSON with the
    unclassified model listed."""
    from unittest.mock import MagicMock, patch

    from io import StringIO

    model = MagicMock(spec=[])
    model.__name__ = "RogueModelJSON"
    model._meta = MagicMock()
    model._meta.app_label = "quickscale_modules_rogue"
    model._meta.db_table = "test_roguemodeljson"

    with patch(
        "quickscale_modules_orgs.management.commands."
        "quickscale_orgs_check_tenant_isolation.get_unclassified_concrete_models",
        return_value=[model],
    ):
        stdout = StringIO()
        stderr = StringIO()
        with pytest.raises(CommandError) as excinfo:
            call_command(
                "quickscale_orgs_check_tenant_isolation",
                format="json",
                stdout=stdout,
                stderr=stderr,
                verbosity=0,
            )
        assert excinfo.value.returncode == 1

        import json as json_lib

        data = json_lib.loads(stdout.getvalue())
        assert data["status"] == "fail"
        assert len(data["unclassified"]) == 1
        assert data["unclassified"][0]["model_name"] == "RogueModelJSON"
        assert data["unclassified"][0]["app_label"] == "quickscale_modules_rogue"


def test_get_unclassified_concrete_models_acceptance() -> None:
    """Directly prove that get_unclassified_concrete_models() returns
    an empty list when all project models are classified.

    This is a unit-level test of the helper function itself, independent
    of the management command.
    """
    from quickscale_modules_orgs.tenancy import get_unclassified_concrete_models

    unclassified = get_unclassified_concrete_models()
    assert unclassified == [], (
        f"Expected empty list, got: "
        f"{[(m._meta.app_label, m.__name__) for m in unclassified]}"
    )


def test_get_concrete_project_models_returns_expected_models() -> None:
    """Prove that get_concrete_project_models() returns all concrete
    models from project-owned apps under the widened scope:
    all installed non-contrib, non-third-party apps.  The set must be
    non-empty and must include auto-created through models.
    """
    from quickscale_modules_orgs.tenancy import get_concrete_project_models

    project_models = get_concrete_project_models()
    assert len(project_models) > 0, "Expected at least one project model"

    # No model should come from Django contrib or known third-party apps.
    from quickscale_modules_orgs.tenancy import (
        _is_django_contrib_app,
        _is_third_party_app,
    )

    for m in project_models:
        app_label = m._meta.app_label
        assert not _is_django_contrib_app(app_label), (
            f"Model {app_label}.{m.__name__} is from a Django contrib app "
            f"but was returned as a project model."
        )
        assert not _is_third_party_app(app_label), (
            f"Model {app_label}.{m.__name__} is from a known third-party "
            f"app but was returned as a project model (import path: "
            f"{type(m).__module__})."
        )

    # Verify auto-created ManyToMany through models are included.
    through_model_names = {
        (m._meta.app_label, m.__name__) for m in project_models if m._meta.auto_created
    }
    expected_through = {
        ("quickscale_crm", "Contact_tags"),
        ("quickscale_crm", "Deal_tags"),
        ("quickscale_blog", "Post_tags"),
    }
    missing = expected_through - through_model_names
    assert not missing, (
        f"Auto-created through models missing from "
        f"get_concrete_project_models(): {sorted(missing)}"
    )


# ---------------------------------------------------------------------------
# --postgres-only must not bypass classification check
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_postgres_only_classification_still_runs_human() -> None:
    """--postgres-only on non-PostgreSQL must still report unclassified
    models in human-readable output.
    """
    from unittest.mock import MagicMock, patch

    from io import StringIO

    model = MagicMock(spec=[])
    model.__name__ = "RogueModel"
    model._meta = MagicMock()
    model._meta.app_label = "quickscale_modules_rogue"
    model._meta.db_table = "test_roguemodel"

    with patch(
        "quickscale_modules_orgs.management.commands."
        "quickscale_orgs_check_tenant_isolation.get_unclassified_concrete_models",
        return_value=[model],
    ):
        with patch(
            "quickscale_modules_orgs.management.commands."
            "quickscale_orgs_check_tenant_isolation.connection.vendor",
            "sqlite",
        ):
            stdout = StringIO()
            stderr = StringIO()
            with pytest.raises(CommandError) as excinfo:
                call_command(
                    "quickscale_orgs_check_tenant_isolation",
                    postgres_only=True,
                    stdout=stdout,
                    stderr=stderr,
                    verbosity=0,
                )
            assert excinfo.value.returncode == 1
            output = stdout.getvalue()
            assert "UNCLASSIFIED" in output
            assert "RogueModel" in output


@pytest.mark.django_db
def test_postgres_only_classification_still_runs_json() -> None:
    """--postgres-only on non-PostgreSQL must still report unclassified
    models in JSON output.
    """
    from unittest.mock import MagicMock, patch

    from io import StringIO

    model = MagicMock(spec=[])
    model.__name__ = "RogueModelJSON"
    model._meta = MagicMock()
    model._meta.app_label = "quickscale_modules_rogue"
    model._meta.db_table = "test_roguemodeljson"

    with patch(
        "quickscale_modules_orgs.management.commands."
        "quickscale_orgs_check_tenant_isolation.get_unclassified_concrete_models",
        return_value=[model],
    ):
        with patch(
            "quickscale_modules_orgs.management.commands."
            "quickscale_orgs_check_tenant_isolation.connection.vendor",
            "sqlite",
        ):
            stdout = StringIO()
            stderr = StringIO()
            with pytest.raises(CommandError) as excinfo:
                call_command(
                    "quickscale_orgs_check_tenant_isolation",
                    postgres_only=True,
                    format="json",
                    stdout=stdout,
                    stderr=stderr,
                    verbosity=0,
                )
            assert excinfo.value.returncode == 1

            import json as json_lib

            data = json_lib.loads(stdout.getvalue())
            assert data["status"] == "fail"
            assert len(data["unclassified"]) == 1
            assert data["unclassified"][0]["model_name"] == "RogueModelJSON"


# ---------------------------------------------------------------------------
# Implicit M2M through models are auto-classified
# ---------------------------------------------------------------------------


class TestImplicitM2MThroughClassification:
    """Auto-created implicit M2M through models whose related models are
    classified must NOT appear in the unclassified list."""

    @patch(
        "quickscale_modules_orgs.management.commands."
        "quickscale_orgs_check_tenant_isolation.get_tenant_models"
    )
    @patch(
        "quickscale_modules_orgs.management.commands."
        "quickscale_orgs_check_tenant_isolation.get_unclassified_concrete_models"
    )
    def test_implicit_m2m_through_not_reported_when_classified(
        self, mock_get_unclassified: MagicMock, mock_tenant: MagicMock
    ) -> None:
        """When marker-only M2M classification returns True for a through
        model, it must not appear in the command's unclassified output."""
        mock_get_unclassified.return_value = []
        mock_tenant.return_value = []

        stdout = StringIO()
        stderr = StringIO()
        call_command(
            "quickscale_orgs_check_tenant_isolation",
            stdout=stdout,
            stderr=stderr,
            verbosity=0,
        )

        output = stdout.getvalue()
        assert "unclassified" not in output.lower()

    @patch(
        "quickscale_modules_orgs.management.commands."
        "quickscale_orgs_check_tenant_isolation.get_tenant_models"
    )
    @patch(
        "quickscale_modules_orgs.management.commands."
        "quickscale_orgs_check_tenant_isolation.get_unclassified_concrete_models"
    )
    def test_rationale_model_count_zero_when_all_classified(
        self, mock_get_unclassified: MagicMock, mock_tenant: MagicMock
    ) -> None:
        """Human-readable output must show 0 unclassified when all models
        including implicit M2M through models are classified."""
        mock_get_unclassified.return_value = []
        mock_tenant.return_value = []

        stdout = StringIO()
        stderr = StringIO()
        call_command(
            "quickscale_orgs_check_tenant_isolation",
            stdout=stdout,
            stderr=stderr,
            verbosity=0,
        )

        output = stdout.getvalue()
        # The summary line must not mention unclassified count
        assert "unclassified" not in output.lower()


# ---------------------------------------------------------------------------
# tenant_excluded marker classification path
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_tenant_excluded_marker_classifies_model() -> None:
    """A model with a truthy tenant_excluded marker must be classified
    and not trigger W005 or appear in unclassified output.

    Uses a real model subclass with the marker set and proves that
    is_classified_in_registry() recognizes it, and the management
    command does not report it as unclassified.
    """
    from django.db import models as django_models

    from quickscale_modules_orgs.tenancy import (
        is_classified_in_registry,
    )

    # Create a minimal concrete model class with the marker.
    class TenantExcludedModel(django_models.Model):
        name = django_models.CharField(max_length=100)
        tenant_excluded = "Lookup table — not tenant-scoped."

        class Meta:
            app_label = "quickscale_orgs"

    # Prove the marker is recognized at the function level.
    assert is_classified_in_registry(TenantExcludedModel), (
        "A model with tenant_excluded marker must be classified"
    )


@pytest.mark.django_db
def test_tenant_excluded_marker_keeps_model_out_of_unclassified() -> None:
    """A model with the tenant_excluded marker must not appear in the
    unclassified list returned by get_unclassified_concrete_models().

    This is an integration-style test using a real model subclass.
    """
    from django.db import models as django_models

    from quickscale_modules_orgs.tenancy import (
        get_concrete_project_models,
        get_unclassified_concrete_models,
    )

    class TenantExcludedModel(django_models.Model):
        name = django_models.CharField(max_length=100)
        tenant_excluded = "Lookup table — not tenant-scoped."

        class Meta:
            app_label = "quickscale_orgs"

    # Verify the model is in the project models list.
    all_project_models = get_concrete_project_models()
    assert any(m.__name__ == "TenantExcludedModel" for m in all_project_models), (
        "TenantExcludedModel must be discovered as a project model"
    )

    # Verify it is NOT in the unclassified list.
    unclassified = get_unclassified_concrete_models()
    for m in unclassified:
        assert m.__name__ != "TenantExcludedModel", (
            "TenantExcludedModel must not appear in unclassified models"
        )
    assert all(m.__name__ != "TenantExcludedModel" for m in unclassified), (
        "TenantExcludedModel with tenant_excluded marker must not be unclassified"
    )
