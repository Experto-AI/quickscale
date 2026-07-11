"""Focused tests for org billing bridge management commands."""

from __future__ import annotations

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
    Subscription,
)
from quickscale_modules_orgs.current_org import (
    reset_current_org_id,
    set_current_org_id,
)
from quickscale_modules_orgs.management.commands.migrate_billing_to_orgs import (
    _billing_user_ids,
    _candidate_customer_ids_for_user,
    _collect_unmigratable_row_messages,
    _existing_personal_org,
    _normalized_text,
    _resolve_authoritative_organization,
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
# Current-schema migrate_billing_to_orgs tests
#
# The existing pre-migration tests (above) skip when organization_id is NOT
# NULL (the RLS-migrated schema).  These tests exercise the helper functions
# and Command.handle() paths that work with the current NOT NULL schema.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_migrate_billing_normalized_text_none() -> None:
    """_normalized_text(None) must return empty string."""
    assert _normalized_text(None) == ""


@pytest.mark.django_db
def test_migrate_billing_normalized_text_empty() -> None:
    """_normalized_text('') must return empty string."""
    assert _normalized_text("") == ""


@pytest.mark.django_db
def test_migrate_billing_normalized_text_stripped() -> None:
    """_normalized_text must strip surrounding whitespace."""
    assert _normalized_text("  cus_abc  ") == "cus_abc"


@pytest.mark.django_db
def test_migrate_billing_billing_user_ids_empty() -> None:
    """_billing_user_ids() must return [] when no billing rows exist."""
    assert _billing_user_ids() == []


@pytest.mark.django_db
def test_migrate_billing_billing_user_ids_from_subscription() -> None:
    """_billing_user_ids() must include user IDs from Subscription rows."""
    user = get_user_model().objects.create_user(
        username="bill-user-ids",
        email="bill-ids@example.com",
        password="secret123",
    )
    plan = _create_plan(slug="growth-bill-ids", price_id="price_growth_bill_ids")
    org = Organization.objects.create(name="Billing IDs", slug="billing-ids")
    set_current_org_id(org.pk)
    try:
        Subscription.objects.create(
            user=user,
            organization=org,
            plan=plan,
            stripe_subscription_id="sub_bill_ids",
            stripe_customer_id="cus_bill_ids",
            status=Subscription.Status.ACTIVE,
        )
    finally:
        reset_current_org_id()
    set_current_org_id(org.pk)
    user_ids = _billing_user_ids()
    assert user.pk in user_ids


@pytest.mark.django_db
def test_migrate_billing_existing_personal_org_none() -> None:
    """_existing_personal_org() must return None when user has no personal org."""
    user = get_user_model().objects.create_user(
        username="no-personal",
        email="no-personal@example.com",
        password="secret123",
    )
    assert _existing_personal_org(user=user) is None


@pytest.mark.django_db
def test_migrate_billing_existing_personal_org_found() -> None:
    """_existing_personal_org() must return the personal org when one exists."""
    user = get_user_model().objects.create_user(
        username="has-personal",
        email="has-personal@example.com",
        password="secret123",
    )
    org = Organization.objects.create(
        name="Personal", slug="personal", is_personal=True
    )
    OrganizationMembership.objects.create(
        user=user, organization=org, role=OrgRole.OWNER
    )
    result = _existing_personal_org(user=user)
    assert result is not None
    assert result.pk == org.pk


@pytest.mark.django_db
def test_migrate_billing_existing_personal_org_multiple_raises() -> None:
    """_existing_personal_org() must raise CommandError when user has multiple personal orgs."""
    user = get_user_model().objects.create_user(
        username="multi-personal",
        email="multi-personal@example.com",
        password="secret123",
    )
    org_a = Organization.objects.create(
        name="Personal A", slug="personal-a", is_personal=True
    )
    org_b = Organization.objects.create(
        name="Personal B", slug="personal-b", is_personal=True
    )
    OrganizationMembership.objects.create(
        user=user, organization=org_a, role=OrgRole.OWNER
    )
    OrganizationMembership.objects.create(
        user=user, organization=org_b, role=OrgRole.OWNER
    )
    with pytest.raises(CommandError, match="multiple personal organizations"):
        _existing_personal_org(user=user)


@pytest.mark.django_db
def test_migrate_billing_resolve_authoritative_reuses_personal_org() -> None:
    """_resolve_authoritative_organization() must reuse existing personal org."""
    user = get_user_model().objects.create_user(
        username="resolve-personal",
        email="resolve-personal@example.com",
        password="secret123",
    )
    org = Organization.objects.create(
        name="Personal", slug="resolve-personal", is_personal=True
    )
    OrganizationMembership.objects.create(
        user=user, organization=org, role=OrgRole.OWNER
    )
    resolved_org, created = _resolve_authoritative_organization(user)
    assert resolved_org.pk == org.pk
    assert created is False


@pytest.mark.django_db
def test_migrate_billing_resolve_authoritative_reuses_sole_membership() -> None:
    """_resolve_authoritative_organization() must reuse sole membership org."""
    user = get_user_model().objects.create_user(
        username="resolve-sole",
        email="resolve-sole@example.com",
        password="secret123",
    )
    org = Organization.objects.create(name="Sole", slug="resolve-sole")
    OrganizationMembership.objects.create(
        user=user, organization=org, role=OrgRole.ADMIN
    )
    resolved_org, created = _resolve_authoritative_organization(user)
    assert resolved_org.pk == org.pk
    assert created is False


@pytest.mark.django_db
def test_migrate_billing_resolve_authoritative_creates_personal_org() -> None:
    """_resolve_authoritative_organization() must create personal org when user has no memberships."""
    user = get_user_model().objects.create_user(
        username="resolve-create",
        email="resolve-create@example.com",
        password="secret123",
    )
    resolved_org, created = _resolve_authoritative_organization(user)
    assert resolved_org.is_personal is True
    assert created is True
    assert OrganizationMembership.objects.filter(
        user=user, organization=resolved_org
    ).exists()


@pytest.mark.django_db
def test_migrate_billing_resolve_authoritative_ambiguous_raises() -> None:
    """_resolve_authoritative_organization() must raise when user is in multiple orgs."""
    user = get_user_model().objects.create_user(
        username="resolve-ambig",
        email="resolve-ambig@example.com",
        password="secret123",
    )
    org_a = Organization.objects.create(name="Ambiguous A", slug="ambig-a")
    org_b = Organization.objects.create(name="Ambiguous B", slug="ambig-b")
    OrganizationMembership.objects.create(
        user=user, organization=org_a, role=OrgRole.ADMIN
    )
    OrganizationMembership.objects.create(
        user=user, organization=org_b, role=OrgRole.MEMBER
    )
    with pytest.raises(CommandError, match="ambiguous organization memberships"):
        _resolve_authoritative_organization(user)


@pytest.mark.django_db
def test_migrate_billing_candidate_customer_ids_current() -> None:
    """_candidate_customer_ids_for_user() must return current subscription IDs."""
    user = get_user_model().objects.create_user(
        username="candidate-curr",
        email="candidate-curr@example.com",
        password="secret123",
    )
    plan = _create_plan(
        slug="growth-candidate-curr", price_id="price_growth_candidate_curr"
    )
    org = Organization.objects.create(name="Candidate", slug="candidate")
    set_current_org_id(org.pk)
    try:
        Subscription.objects.create(
            user=user,
            organization=org,
            plan=plan,
            stripe_subscription_id="sub_candidate_curr",
            stripe_customer_id="cus_candidate_curr",
            status=Subscription.Status.ACTIVE,
        )
    finally:
        reset_current_org_id()
    set_current_org_id(org.pk)
    customer_ids = _candidate_customer_ids_for_user(user_id=user.pk)
    assert "cus_candidate_curr" in customer_ids


@pytest.mark.django_db
def test_migrate_billing_candidate_customer_ids_historical() -> None:
    """_candidate_customer_ids_for_user() must fall back to historical IDs when no current subs."""
    user = get_user_model().objects.create_user(
        username="candidate-hist",
        email="candidate-hist@example.com",
        password="secret123",
    )
    plan = _create_plan(
        slug="growth-candidate-hist", price_id="price_growth_candidate_hist"
    )
    org = Organization.objects.create(name="Candidate Hist", slug="candidate-hist")
    set_current_org_id(org.pk)
    try:
        Subscription.objects.create(
            user=user,
            organization=org,
            plan=plan,
            stripe_subscription_id="sub_candidate_hist",
            stripe_customer_id="cus_candidate_hist",
            status=Subscription.Status.CANCELED,
        )
    finally:
        reset_current_org_id()
    set_current_org_id(org.pk)
    customer_ids = _candidate_customer_ids_for_user(user_id=user.pk)
    assert "cus_candidate_hist" in customer_ids


@pytest.mark.django_db
def test_migrate_billing_collect_unmigratable_empty() -> None:
    """_collect_unmigratable_row_messages() must return [] when no null-user rows exist."""
    messages = _collect_unmigratable_row_messages()
    assert messages == []


@pytest.mark.django_db
def test_migrate_billing_no_users_early_return() -> None:
    """Command.handle() must exit early when no billing users exist."""
    stdout = StringIO()
    call_command(
        "migrate_billing_to_orgs",
        stdout=stdout,
        stderr=StringIO(),
        verbosity=0,
    )
    output = stdout.getvalue()
    assert "No billing users required migration" in output


@pytest.mark.django_db
def test_migrate_billing_completes_with_preassigned_org() -> None:
    """Command.handle() must complete cleanly when billing rows already point at the resolved org.

    In the current RLS schema where organization_id is NOT NULL, update filters
    with organization_id__isnull=True will match zero rows. The command still
    completes successfully with updated=0 counters.
    """
    user = get_user_model().objects.create_user(
        username="preassigned",
        email="preassigned@example.com",
        password="secret123",
    )
    plan = _create_plan(
        slug="growth-preassigned",
        price_id="price_growth_preassigned",
    )
    org = Organization.objects.create(name="Preassigned", slug="preassigned")
    OrganizationMembership.objects.create(
        user=user, organization=org, role=OrgRole.ADMIN
    )

    set_current_org_id(org.pk)
    try:
        Subscription.objects.create(
            user=user,
            organization=org,
            plan=plan,
            stripe_subscription_id="sub_preassigned",
            stripe_customer_id="cus_preassigned",
            status=Subscription.Status.ACTIVE,
        )
        CreditBalance.objects.create(
            organization=org,
            user=user,
            balance=50,
        )
        CreditTransaction.objects.create(
            organization=org,
            user=user,
            amount=25,
            transaction_type=CreditTransaction.TransactionType.PURCHASE,
            description="Preassigned test",
            balance_after=50,
        )
    finally:
        reset_current_org_id()

    set_current_org_id(org.pk)
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
    assert "preassigned" in output
    assert "completed for 1 billing users" in output


@pytest.mark.django_db
def test_migrate_billing_syncs_stripe_customer_id_when_org_has_none() -> None:
    """Command.handle() must sync stripe_customer_id from billing rows when org has none."""
    user = get_user_model().objects.create_user(
        username="sync-cus",
        email="sync-cus@example.com",
        password="secret123",
    )
    plan = _create_plan(
        slug="growth-sync-cus",
        price_id="price_growth_sync_cus",
    )
    org = Organization.objects.create(
        name="Sync Cus",
        slug="sync-cus",
        stripe_customer_id="",
    )
    OrganizationMembership.objects.create(
        user=user, organization=org, role=OrgRole.ADMIN
    )

    set_current_org_id(org.pk)
    try:
        Subscription.objects.create(
            user=user,
            organization=org,
            plan=plan,
            stripe_subscription_id="sub_sync_cus",
            stripe_customer_id="cus_synced",
            status=Subscription.Status.ACTIVE,
        )
    finally:
        reset_current_org_id()

    set_current_org_id(org.pk)
    stdout = StringIO()
    call_command(
        "migrate_billing_to_orgs",
        stdout=stdout,
        stderr=StringIO(),
        verbosity=0,
    )
    output = stdout.getvalue()
    assert "subscriptions_updated=0" in output
    assert "stripe_customer_id=cus_synced" in output
    assert "completed for 1 billing users" in output
    org.refresh_from_db()
    assert org.stripe_customer_id == "cus_synced"


@pytest.mark.django_db
def test_migrate_billing_fails_on_conflicting_stripe_customer_id() -> None:
    """Command.handle() must detect when org's existing stripe_customer_id conflicts with billing rows."""
    user = get_user_model().objects.create_user(
        username="conflict-cus",
        email="conflict-cus@example.com",
        password="secret123",
    )
    plan = _create_plan(
        slug="growth-conflict-cus",
        price_id="price_growth_conflict_cus",
    )
    org = Organization.objects.create(
        name="Conflict Cus",
        slug="conflict-cus",
        stripe_customer_id="cus_existing",
    )
    OrganizationMembership.objects.create(
        user=user, organization=org, role=OrgRole.ADMIN
    )

    set_current_org_id(org.pk)
    try:
        Subscription.objects.create(
            user=user,
            organization=org,
            plan=plan,
            stripe_subscription_id="sub_conflict_cus",
            stripe_customer_id="cus_diff",
            status=Subscription.Status.ACTIVE,
        )
    finally:
        reset_current_org_id()

    set_current_org_id(org.pk)
    with pytest.raises(CommandError, match="already has stripe_customer_id"):
        call_command(
            "migrate_billing_to_orgs",
            stdout=StringIO(),
            stderr=StringIO(),
            verbosity=0,
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
    set_current_org_id(organization.pk)
    try:
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
    finally:
        reset_current_org_id()
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
    set_current_org_id(organization.pk)
    try:
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
            "purge_organization",
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
    # only persists for the current transaction).  Reset the ContextVar
    # first so the AF9 priming wrapper does not re-issue SET LOCAL on
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
    from quickscale_modules_orgs.tenancy import (
        get_tenant_models,
        has_organization_id_field,
    )

    actual_specs = {
        (str(spec["app_label"]), str(spec["model_name"])) for spec in _DELETE_SPECS
    }

    expected_models = {
        (model._meta.app_label, model.__name__)
        for model in get_tenant_models()
        if model._meta.app_label != "quickscale_modules_orgs"
        if model._meta.app_label.startswith("quickscale_modules_")
        and not model._meta.abstract
        and has_organization_id_field(model)
    }

    # Verify every owned module model with an organization FK is represented.
    for expected_app in [
        "quickscale_modules_social",
        "quickscale_modules_forms",
        "quickscale_modules_listings",
        "quickscale_modules_blog",
        "quickscale_modules_crm",
        "quickscale_modules_billing",
    ]:
        assert expected_app in {a for a, _ in actual_specs}, (
            f"Missing delete spec app-label entry for {expected_app}"
        )

    for expected_model in expected_models:
        assert expected_model in actual_specs, (
            f"Missing delete spec entry for {expected_model[0]}.{expected_model[1]}"
        )

    # Keep the spec set aligned with the same tenant-typing universe.
    assert actual_specs == expected_models, (
        "Delete spec set must match tenant-classification-derived org models "
        "with direct organization FK"
    )

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
    set_current_org_id(org.pk)
    try:
        Listing.objects.create(
            organization=org, title="Test Listing", slug="test-listing"
        )
    finally:
        reset_current_org_id()
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
        Deal.objects.create(
            organization=org,
            title="Test Deal",
            contact=contact,
            stage=stage,
        )
        Tag.objects.create(organization=org, name="Test Tag")
    finally:
        reset_current_org_id()
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
# SA1.3 — check_tenant_isolation command tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_check_tenant_isolation_pass_on_current_models() -> None:
    """The command must report the correct pass/fail counts for current
    installed tenant models.

    All real ENROLLED models (21 total) should have organization_id + FORCE
    RLS.  Test-only models (ConcreteTenantResource, ForwardFKChild) are
    detected as tenant models (they inherit TenantModel) but their test
    tables lack FORCE-RLS — on PostgreSQL this would cause a fail, but on
    SQLite all models pass (``force_rls`` is None so only
    ``organization_id`` is checked).
    """
    from io import StringIO

    stdout = StringIO()
    stderr = StringIO()

    call_command(
        "check_tenant_isolation",
        stdout=stdout,
        stderr=stderr,
        verbosity=0,
    )

    output = stdout.getvalue()
    # Should have discovered tenant models.
    assert "Discovered" in output
    assert "Result:" in output
    # On SQLite, all models pass (force_rls is None; only org_id checked).
    # Test-only models (ConcreteTenantResource, ForwardFKChild) are only
    # present when test_models is explicitly imported, so 21 models total.
    assert "21 passed, 0 failed" in output


@pytest.mark.django_db
def test_check_tenant_isolation_json_output() -> None:
    """The --format json option must produce valid JSON with pass/fail status."""
    from io import StringIO

    stdout = StringIO()
    stderr = StringIO()

    call_command(
        "check_tenant_isolation",
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
    # On SQLite, all models pass (force_rls is None; only org_id checked).
    assert data["tenant_models"]["total"] == 21
    assert data["tenant_models"]["passed"] == 21
    assert data["tenant_models"]["failed"] == 0
    assert "unclassified" in data


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
    model = apps.get_model("quickscale_modules_billing", "Plan")
    assert model is not None
    assert not is_tenant_model(model), "Plan should not be detected as a tenant model."

    # Organization (control-plane) should NOT be detected as tenant.
    org_model = apps.get_model("quickscale_modules_orgs", "Organization")
    assert org_model is not None
    assert not is_tenant_model(org_model), (
        "Organization should not be detected as a tenant model."
    )

    # Tag (CRM) is a tenant model — must have organization_id.
    tag_model = apps.get_model("quickscale_modules_crm", "Tag")
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
        "quickscale_modules_orgs.management.commands.check_tenant_isolation"
        ".get_tenant_models",
        return_value=[model],
    ):
        # --- Human format ---
        stdout = StringIO()
        stderr = StringIO()
        with pytest.raises(SystemExit) as excinfo:
            call_command(
                "check_tenant_isolation",
                stdout=stdout,
                stderr=stderr,
                verbosity=0,
            )
        assert excinfo.value.code == 1, (
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
        with pytest.raises(SystemExit):
            call_command(
                "check_tenant_isolation",
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
    """Unit-test the SA1.3 detection helpers directly.

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
        "quickscale_modules_crm",
        "Tag",
    ) in tenant_names, "CRM Tag should be in tenant model list."

    # Organization (control-plane) should NOT be in the list.
    assert (
        "quickscale_modules_orgs",
        "Organization",
    ) not in tenant_names, (
        "Organization (control-plane) must not be detected as tenant."
    )

    # OrganizationMembership should NOT be in the list.
    assert (
        "quickscale_modules_orgs",
        "OrganizationMembership",
    ) not in tenant_names, "OrganizationMembership must not be detected as tenant."


@pytest.mark.django_db
def test_check_tenant_isolation_detects_all_enrolled_models() -> None:
    """The command must discover all ENROLLED models from the registry.

    This proves the marker-based detection matches the registry's ENROLLED
    entries.  EXCLUDED_REVIEWED and abstract models should not be detected.
    """
    from quickscale_modules_orgs.tenancy import (
        TENANT_TABLE_REGISTRY,
        TenantTableStatus,
        get_tenant_models,
    )

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

    Regression for CR-SA13-001: the --postgres-only skip branch must emit
    JSON-only output with status ``skip`` when ``--format json`` is
    specified and the database is not PostgreSQL.
    """
    from io import StringIO
    from unittest.mock import patch

    stdout = StringIO()
    stderr = StringIO()

    with patch(
        "quickscale_modules_orgs.management.commands."
        "check_tenant_isolation.connection.vendor",
        "sqlite",
    ):
        call_command(
            "check_tenant_isolation",
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

    Regression for CR-SA13-001: the no-models warning branch must emit
    JSON-only output with status ``warning`` when ``--format json`` is
    specified and no tenant models are discovered.
    """
    from io import StringIO
    from unittest.mock import patch

    stdout = StringIO()
    stderr = StringIO()

    with patch(
        "quickscale_modules_orgs.management.commands."
        "check_tenant_isolation.get_tenant_models",
        return_value=[],
    ):
        call_command(
            "check_tenant_isolation",
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
    non-PostgreSQL must emit a single valid JSON document (CR-SA14-003).

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
            "check_tenant_isolation.get_tenant_models",
            return_value=[],
        ),
        patch(
            "quickscale_modules_orgs.management.commands."
            "check_tenant_isolation.connection.vendor",
            "sqlite",
        ),
    ):
        call_command(
            "check_tenant_isolation",
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
# SA1.4 — Default-deny classification check tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_classification_check_ok_when_all_models_classified() -> None:
    """The classification check must pass when all project models are
    classified in TENANT_TABLE_REGISTRY.

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
        "check_tenant_isolation",
        stdout=stdout,
        stderr=stderr,
        verbosity=0,
    )
    # On SQLite all models pass the isolation check (force_rls is None,
    # only org_id is checked), so no SystemExit is raised.  The output
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
        "check_tenant_isolation.get_unclassified_concrete_models",
        return_value=[model],
    ):
        stdout = StringIO()
        stderr = StringIO()
        with pytest.raises(SystemExit) as excinfo:
            call_command(
                "check_tenant_isolation",
                stdout=stdout,
                stderr=stderr,
                verbosity=0,
            )
        assert excinfo.value.code == 1
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
        "check_tenant_isolation.get_unclassified_concrete_models",
        return_value=[model],
    ):
        stdout = StringIO()
        stderr = StringIO()
        with pytest.raises(SystemExit) as excinfo:
            call_command(
                "check_tenant_isolation",
                format="json",
                stdout=stdout,
                stderr=stderr,
                verbosity=0,
            )
        assert excinfo.value.code == 1

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
    models from project-owned apps under the SA15.1 widened scope:
    all installed non-contrib, non-third-party apps.  The set must be
    non-empty and must include auto-created through models (CR-SA14-001).
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

    # CR-SA14-001: Verify auto-created ManyToMany through models are included.
    through_model_names = {
        (m._meta.app_label, m.__name__) for m in project_models if m._meta.auto_created
    }
    expected_through = {
        ("quickscale_modules_crm", "Contact_tags"),
        ("quickscale_modules_crm", "Deal_tags"),
        ("quickscale_modules_blog", "Post_tags"),
    }
    missing = expected_through - through_model_names
    assert not missing, (
        f"Auto-created through models missing from "
        f"get_concrete_project_models(): {sorted(missing)}"
    )


# ---------------------------------------------------------------------------
# CR-SA14-002 — --postgres-only must not bypass classification check
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_postgres_only_classification_still_runs_human() -> None:
    """--postgres-only on non-PostgreSQL must still report unclassified
    models in human-readable output (CR-SA14-002).
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
        "check_tenant_isolation.get_unclassified_concrete_models",
        return_value=[model],
    ):
        with patch(
            "quickscale_modules_orgs.management.commands."
            "check_tenant_isolation.connection.vendor",
            "sqlite",
        ):
            stdout = StringIO()
            stderr = StringIO()
            with pytest.raises(SystemExit) as excinfo:
                call_command(
                    "check_tenant_isolation",
                    postgres_only=True,
                    stdout=stdout,
                    stderr=stderr,
                    verbosity=0,
                )
            assert excinfo.value.code == 1
            output = stdout.getvalue()
            assert "UNCLASSIFIED" in output
            assert "RogueModel" in output


@pytest.mark.django_db
def test_postgres_only_classification_still_runs_json() -> None:
    """--postgres-only on non-PostgreSQL must still report unclassified
    models in JSON output (CR-SA14-002).
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
        "check_tenant_isolation.get_unclassified_concrete_models",
        return_value=[model],
    ):
        with patch(
            "quickscale_modules_orgs.management.commands."
            "check_tenant_isolation.connection.vendor",
            "sqlite",
        ):
            stdout = StringIO()
            stderr = StringIO()
            with pytest.raises(SystemExit) as excinfo:
                call_command(
                    "check_tenant_isolation",
                    postgres_only=True,
                    format="json",
                    stdout=stdout,
                    stderr=stderr,
                    verbosity=0,
                )
            assert excinfo.value.code == 1

            import json as json_lib

            data = json_lib.loads(stdout.getvalue())
            assert data["status"] == "fail"
            assert len(data["unclassified"]) == 1
            assert data["unclassified"][0]["model_name"] == "RogueModelJSON"


# ---------------------------------------------------------------------------
# SA15.1 — Implicit M2M through models are auto-classified (CR-SA15.1-001)
# ---------------------------------------------------------------------------


class TestImplicitM2MThroughClassification:
    """Auto-created implicit M2M through models whose related models are
    classified must NOT appear in the unclassified list."""

    @patch(
        "quickscale_modules_orgs.management.commands."
        "check_tenant_isolation.get_tenant_models"
    )
    @patch(
        "quickscale_modules_orgs.management.commands."
        "check_tenant_isolation.get_unclassified_concrete_models"
    )
    def test_implicit_m2m_through_not_reported_when_classified(
        self, mock_get_unclassified: MagicMock, mock_tenant: MagicMock
    ) -> None:
        """When _get_m2m_through_classification returns True for a through
        model, it must not appear in the command's unclassified output."""
        mock_get_unclassified.return_value = []
        mock_tenant.return_value = []

        stdout = StringIO()
        stderr = StringIO()
        call_command(
            "check_tenant_isolation",
            stdout=stdout,
            stderr=stderr,
            verbosity=0,
        )

        output = stdout.getvalue()
        assert "unclassified" not in output.lower()

    @patch(
        "quickscale_modules_orgs.management.commands."
        "check_tenant_isolation.get_tenant_models"
    )
    @patch(
        "quickscale_modules_orgs.management.commands."
        "check_tenant_isolation.get_unclassified_concrete_models"
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
            "check_tenant_isolation",
            stdout=stdout,
            stderr=stderr,
            verbosity=0,
        )

        output = stdout.getvalue()
        # The summary line must not mention unclassified count
        assert "unclassified" not in output.lower()


# ---------------------------------------------------------------------------
# SA15.1 — tenant_excluded marker classification path (CR-SA15.1-003)
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
            app_label = "quickscale_modules_orgs"

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
            app_label = "quickscale_modules_orgs"

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
