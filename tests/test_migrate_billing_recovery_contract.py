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

from quickscale_modules_orgs.management.commands.migrate_billing_to_orgs import (
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
            "quickscale_modules_orgs.management.commands.migrate_billing_to_orgs.connection",
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
            "quickscale_modules_orgs.management.commands.migrate_billing_to_orgs.connection",
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
            "quickscale_modules_orgs.management.commands.migrate_billing_to_orgs.connection",
            mock_connection,
        ):
            _require_explicit_recovery_connection()


def test_recovery_connection_rejects_unknown_current_role() -> None:
    """A missing role-catalog row fails closed instead of guessing privilege."""
    mock_connection = _mock_connection(role_flags=None)

    with patch.dict(os.environ, {"QUICKSCALE_ALLOW_BYPASSRLS": "1"}, clear=True):
        with patch(
            "quickscale_modules_orgs.management.commands.migrate_billing_to_orgs.connection",
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
        with patch(
            "quickscale_modules_orgs.management.commands."
            "migrate_billing_to_orgs._require_explicit_recovery_connection"
        ):
            call_command(
                "migrate_billing_to_orgs",
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
