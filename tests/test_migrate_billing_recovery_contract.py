"""Fail-closed connection contract for the retired billing recovery command."""

from __future__ import annotations

from io import StringIO
import os
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command

from quickscale_modules_billing.models import (
    CreditBalance,
    CreditTransaction,
    Plan,
    Subscription,
)
from quickscale_modules_orgs.current_org import reset_current_org_id, set_current_org_id

from quickscale_modules_orgs.management.commands.quickscale_orgs_migrate_billing_to_orgs import (
    _lock_planned_users,
    _lock_target_organizations,
    _require_explicit_recovery_connection,
)
from quickscale_modules_orgs.models import OrgRole, Organization, OrganizationMembership


def _mock_connection(*, role_flags: tuple[bool, bool] | None) -> MagicMock:
    mock_connection = MagicMock()
    mock_connection.vendor = "postgresql"
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = role_flags
    mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
    return mock_connection


def test_recovery_connection_requires_explicit_acknowledgement() -> None:
    """A bypassing role alone is insufficient without the reviewed opt-in."""
    mock_connection = _mock_connection(role_flags=(True, False))

    with patch.dict(os.environ, {}, clear=True):
        with patch(
            "quickscale_modules_orgs.management.commands.quickscale_orgs_migrate_billing_to_orgs.connection",
            mock_connection,
        ):
            with pytest.raises(
                CommandError, match="explicit QUICKSCALE_ALLOW_BYPASSRLS"
            ):
                _require_explicit_recovery_connection()

    mock_connection.cursor.assert_not_called()


def test_recovery_connection_rejects_restricted_runtime_role() -> None:
    """The ordinary runtime role cannot turn RLS-hidden rows into a success no-op."""
    mock_connection = _mock_connection(role_flags=(False, False))

    with patch.dict(os.environ, {"QUICKSCALE_ALLOW_BYPASSRLS": "1"}, clear=True):
        with patch(
            "quickscale_modules_orgs.management.commands.quickscale_orgs_migrate_billing_to_orgs.connection",
            mock_connection,
        ):
            with pytest.raises(
                CommandError, match="refuses the restricted runtime role"
            ):
                _require_explicit_recovery_connection()


@pytest.mark.parametrize("role_flags", [(True, False), (False, True)])
def test_recovery_connection_accepts_explicit_bypassing_role(
    role_flags: tuple[bool, bool],
) -> None:
    """An acknowledged BYPASSRLS or SUPERUSER connection reaches the backfill."""
    mock_connection = _mock_connection(role_flags=role_flags)

    with patch.dict(os.environ, {"QUICKSCALE_ALLOW_BYPASSRLS": "1"}, clear=True):
        with patch(
            "quickscale_modules_orgs.management.commands.quickscale_orgs_migrate_billing_to_orgs.connection",
            mock_connection,
        ):
            _require_explicit_recovery_connection()


def test_recovery_connection_rejects_unknown_current_role() -> None:
    """A missing role-catalog row fails closed instead of guessing privilege."""
    mock_connection = _mock_connection(role_flags=None)

    with patch.dict(os.environ, {"QUICKSCALE_ALLOW_BYPASSRLS": "1"}, clear=True):
        with patch(
            "quickscale_modules_orgs.management.commands.quickscale_orgs_migrate_billing_to_orgs.connection",
            mock_connection,
        ):
            with pytest.raises(
                CommandError, match="refuses the restricted runtime role"
            ):
                _require_explicit_recovery_connection()


@pytest.mark.django_db
def test_recovery_command_executes_scoped_plan_after_connection_guard() -> None:
    """The normal-role suite covers the algorithm after the isolated guard."""
    user = get_user_model().objects.create_user(
        username="recovery-coverage",
        email="recovery-coverage@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(
        name="Recovery Coverage",
        slug="recovery-coverage",
    )
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    plan = Plan.objects.create(
        name="Recovery",
        slug="recovery-coverage",
        stripe_price_id="price_recovery_coverage",
        credits_per_period=100,
        price_cents=1000,
        currency="usd",
        billing_interval=Plan.BillingInterval.MONTHLY,
    )

    set_current_org_id(organization.pk)
    try:
        Subscription.objects.create(
            user=user,
            organization=organization,
            plan=plan,
            stripe_subscription_id="sub_recovery_coverage",
            stripe_customer_id="cus_recovery_coverage",
            status=Subscription.Status.ACTIVE,
        )
        CreditBalance.objects.create(
            user=user,
            organization=organization,
            balance=100,
        )
        CreditTransaction.objects.create(
            user=user,
            organization=organization,
            amount=100,
            transaction_type=CreditTransaction.TransactionType.PURCHASE,
            description="Recovery coverage",
            balance_after=100,
        )

        stdout = StringIO()
        with (
            patch(
                "quickscale_modules_orgs.management.commands."
                "quickscale_orgs_migrate_billing_to_orgs._require_explicit_recovery_connection"
            ),
            patch(
                "quickscale_modules_orgs.management.commands."
                "quickscale_orgs_migrate_billing_to_orgs._lock_target_organizations",
                wraps=_lock_target_organizations,
            ) as lock_targets,
        ):
            call_command(
                "quickscale_orgs_migrate_billing_to_orgs",
                stdout=stdout,
                stderr=StringIO(),
                verbosity=0,
            )
    finally:
        reset_current_org_id()

    organization.refresh_from_db()
    assert organization.stripe_customer_id == "cus_recovery_coverage"
    assert "subscriptions_updated=0" in stdout.getvalue()
    assert "balances_updated=0" in stdout.getvalue()
    assert "transactions_updated=0" in stdout.getvalue()
    assert "completed for 1 billing users" in stdout.getvalue()
    lock_targets.assert_called_once_with({organization.pk})


@pytest.mark.django_db
def test_recovery_command_rejects_customer_owned_by_another_organization() -> None:
    """Recovery never promotes one Stripe customer onto a second organization."""
    user = get_user_model().objects.create_user(
        username="recovery-customer-collision",
        email="recovery-customer-collision@example.com",
        password="secret123",
    )
    owning_organization = Organization.objects.create(
        name="Recovery Existing Customer Owner",
        slug="recovery-existing-customer-owner",
        stripe_customer_id="cus_recovery_cross_org",
    )
    target_organization = Organization.objects.create(
        name="Recovery Customer Collision Target",
        slug="recovery-customer-collision-target",
    )
    OrganizationMembership.objects.create(
        user=user,
        organization=target_organization,
        role=OrgRole.ADMIN,
    )
    plan = Plan.objects.create(
        name="Recovery Customer Collision",
        slug="recovery-customer-collision",
        stripe_price_id="price_recovery_customer_collision",
        credits_per_period=100,
        price_cents=1000,
        currency="usd",
        billing_interval=Plan.BillingInterval.MONTHLY,
    )
    set_current_org_id(target_organization.pk)
    try:
        subscription = Subscription.objects.create(
            user=user,
            organization=target_organization,
            plan=plan,
            stripe_subscription_id="sub_recovery_customer_collision",
            stripe_customer_id="cus_recovery_cross_org",
            status=Subscription.Status.CANCELED,
        )
    finally:
        reset_current_org_id()

    with (
        patch(
            "quickscale_modules_orgs.management.commands."
            "quickscale_orgs_migrate_billing_to_orgs._require_explicit_recovery_connection"
        ),
        pytest.raises(CommandError, match="already owned by organization"),
    ):
        call_command(
            "quickscale_orgs_migrate_billing_to_orgs",
            stdout=StringIO(),
            stderr=StringIO(),
            verbosity=0,
        )

    target_organization.refresh_from_db()
    owning_organization.refresh_from_db()
    subscription.refresh_from_db()
    assert target_organization.stripe_customer_id == ""
    assert owning_organization.stripe_customer_id == "cus_recovery_cross_org"
    assert subscription.organization_id == target_organization.pk


@pytest.mark.django_db
def test_recovery_command_revalidates_authoritative_org_after_lock() -> None:
    """A membership change during lock acquisition invalidates the stale plan."""
    user = get_user_model().objects.create_user(
        username="recovery-lock-revalidation",
        email="recovery-lock-revalidation@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(
        name="Recovery Lock Target",
        slug="recovery-lock-target",
    )
    competing_organization = Organization.objects.create(
        name="Recovery Competing Target",
        slug="recovery-competing-target",
    )
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    plan = Plan.objects.create(
        name="Recovery Lock Revalidation",
        slug="recovery-lock-revalidation",
        stripe_price_id="price_recovery_lock_revalidation",
        credits_per_period=100,
        price_cents=1000,
        currency="usd",
        billing_interval=Plan.BillingInterval.MONTHLY,
    )
    set_current_org_id(organization.pk)
    try:
        Subscription.objects.create(
            user=user,
            organization=organization,
            plan=plan,
            stripe_subscription_id="sub_recovery_lock_revalidation",
            stripe_customer_id="cus_recovery_lock_revalidation",
            status=Subscription.Status.ACTIVE,
        )
    finally:
        reset_current_org_id()

    def add_competing_membership(organization_ids):
        locked = _lock_target_organizations(organization_ids)
        OrganizationMembership.objects.create(
            user=user,
            organization=competing_organization,
            role=OrgRole.MEMBER,
        )
        return locked

    with (
        patch(
            "quickscale_modules_orgs.management.commands."
            "quickscale_orgs_migrate_billing_to_orgs._require_explicit_recovery_connection"
        ),
        patch(
            "quickscale_modules_orgs.management.commands."
            "quickscale_orgs_migrate_billing_to_orgs._lock_target_organizations",
            side_effect=add_competing_membership,
        ),
        pytest.raises(CommandError, match="ambiguous organization memberships"),
    ):
        call_command(
            "quickscale_orgs_migrate_billing_to_orgs",
            stdout=StringIO(),
            stderr=StringIO(),
            verbosity=0,
        )

    assert not OrganizationMembership.objects.filter(
        user=user,
        organization=competing_organization,
    ).exists()
    organization.refresh_from_db()
    assert organization.stripe_customer_id == ""


@pytest.mark.django_db(transaction=True)
def test_recovery_command_blocks_membership_insertion_while_users_are_locked() -> None:
    """A second-org membership cannot appear between revalidation and updates."""
    import concurrent.futures
    import threading

    from django.db import close_old_connections

    user = get_user_model().objects.create_user(
        username="recovery-user-lock",
        email="recovery-user-lock@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(
        name="Recovery User Lock",
        slug="recovery-user-lock",
    )
    competing_organization = Organization.objects.create(
        name="Recovery User Lock Competing",
        slug="recovery-user-lock-competing",
    )
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    plan = Plan.objects.create(
        name="Recovery User Lock",
        slug="recovery-user-lock",
        stripe_price_id="price_recovery_user_lock",
        credits_per_period=100,
        price_cents=1000,
        currency="usd",
        billing_interval=Plan.BillingInterval.MONTHLY,
    )
    set_current_org_id(organization.pk)
    try:
        Subscription.objects.create(
            user=user,
            organization=organization,
            plan=plan,
            stripe_subscription_id="sub_recovery_user_lock",
            status=Subscription.Status.ACTIVE,
        )
    finally:
        reset_current_org_id()

    users_locked = threading.Event()
    release_recovery = threading.Event()
    membership_started = threading.Event()
    membership_finished = threading.Event()

    def lock_users_and_pause(user_model, user_ids):
        locked_users = _lock_planned_users(user_model, user_ids)
        users_locked.set()
        if not release_recovery.wait(timeout=10):
            raise AssertionError("timed out waiting to release billing recovery")
        return locked_users

    def run_recovery() -> str:
        close_old_connections()
        set_current_org_id(organization.pk)
        stdout = StringIO()
        try:
            call_command(
                "quickscale_orgs_migrate_billing_to_orgs",
                stdout=stdout,
                stderr=StringIO(),
                verbosity=0,
            )
            return stdout.getvalue()
        finally:
            reset_current_org_id()
            close_old_connections()

    def add_competing_membership() -> None:
        close_old_connections()
        membership_started.set()
        try:
            OrganizationMembership.objects.create(
                user=user,
                organization=competing_organization,
                role=OrgRole.MEMBER,
            )
            membership_finished.set()
        finally:
            close_old_connections()

    with (
        patch(
            "quickscale_modules_orgs.management.commands."
            "quickscale_orgs_migrate_billing_to_orgs._require_explicit_recovery_connection"
        ),
        patch(
            "quickscale_modules_orgs.management.commands."
            "quickscale_orgs_migrate_billing_to_orgs._lock_planned_users",
            side_effect=lock_users_and_pause,
        ),
        concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor,
    ):
        recovery_future = executor.submit(run_recovery)
        assert users_locked.wait(timeout=10)
        membership_future = executor.submit(add_competing_membership)
        assert membership_started.wait(timeout=10)
        assert not membership_finished.wait(timeout=0.5)
        release_recovery.set()
        assert "completed for 1 billing users" in recovery_future.result(timeout=10)
        membership_future.result(timeout=10)

    assert membership_finished.is_set()
    assert OrganizationMembership.objects.filter(
        user=user,
        organization=competing_organization,
    ).exists()
