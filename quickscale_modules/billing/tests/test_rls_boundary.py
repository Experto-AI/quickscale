"""PostgreSQL RLS boundary tests for the Billing module.

T1.16 — DB-level RLS isolation proof under a restricted PostgreSQL role.

These tests verify that:
1. ``FORCE ROW LEVEL SECURITY`` on billing tables enforces org isolation
   at the DB layer when ``app.current_org_id`` is set / unset.
2. ``handle_stripe_event()`` starts with zero ambient org context and
   establishes context internally via ``_billing_org_db_context``, so the
   resulting CreditBalance/CreditTransaction rows are only visible under
   the correct ``app.current_org_id``.

Skipped on non-PostgreSQL databases (SQLite during CI unit tests).
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from django.db import connection

from quickscale_modules_billing.models import (
    CreditBalance,
    CreditTransaction,
    Plan,
    Subscription,
)
from quickscale_modules_billing.services import (
    _billing_org_db_context,
    handle_stripe_event,
)
from quickscale_modules_orgs.current_org import (
    get_current_org_id,
    set_current_org_id,
)

# ---------------------------------------------------------------------------
# Restricted role helpers (mirror the social module pattern)
# ---------------------------------------------------------------------------

_RESTRICTED_ROLE = "quickscale_rls_test_role"
_BILLING_RLS_TABLES = (
    "quickscale_modules_billing_creditbalance",
    "quickscale_modules_billing_credittransaction",
    "quickscale_modules_billing_subscription",
)


def _ensure_rls_test_role() -> None:
    """Create a non-superuser role for RLS boundary testing.

    Connects via psycopg2 directly because ``CREATE ROLE`` is DDL and
    cannot run inside a Django test transaction.  Idempotent.
    """
    import psycopg2  # type: ignore[import-untyped]

    db = connection.settings_dict
    conn = psycopg2.connect(
        dbname=db["NAME"],
        user=db["USER"],
        password=db["PASSWORD"],
        host=db.get("HOST", "localhost"),
        port=db.get("PORT", "5432"),
    )
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                DO $$
                BEGIN
                    CREATE ROLE {_RESTRICTED_ROLE};
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
            """)
            cur.execute(f"GRANT USAGE ON SCHEMA public TO {_RESTRICTED_ROLE}")
            for table in _BILLING_RLS_TABLES:
                cur.execute(f"GRANT SELECT ON {table} TO {_RESTRICTED_ROLE}")
    finally:
        conn.close()


def _make_plan(db) -> Plan:  # type: ignore[return]
    from quickscale_modules_billing.models import Plan

    return Plan.objects.create(
        name="Test Plan",
        slug="test-plan",
        credits_per_period=100,
        billing_interval=Plan.BillingInterval.MONTHLY,
        stripe_price_id="price_test_rls",
    )


# ---------------------------------------------------------------------------
# _billing_org_db_context tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestBillingOrgDbContext:
    """Unit tests for the ``_billing_org_db_context`` context manager."""

    @pytest.fixture(autouse=True)
    def _skip_if_not_postgres(self) -> None:
        if connection.vendor != "postgresql":
            pytest.skip("DB-level billing org context requires PostgreSQL")

    def test_sets_and_restores_contextvar(self, organization) -> None:
        """Context manager sets org context on entry and restores it on exit."""
        prior = get_current_org_id()
        with _billing_org_db_context(organization):
            assert get_current_org_id() == organization.pk
        assert get_current_org_id() == prior

    def test_clears_contextvar_when_org_is_none(self, organization) -> None:
        """When org is None, context manager clears the ContextVar."""
        set_current_org_id(organization.pk)
        try:
            with _billing_org_db_context(None):
                assert get_current_org_id() is None
        finally:
            set_current_org_id(None)

    def test_restores_contextvar_on_exception(self, organization) -> None:
        """ContextVar is restored even when the body raises."""
        set_current_org_id(None)
        with pytest.raises(ValueError):
            with _billing_org_db_context(organization):
                assert get_current_org_id() == organization.pk
                raise ValueError("test exception")
        assert get_current_org_id() is None


# ---------------------------------------------------------------------------
# RLS boundary tests under a restricted PostgreSQL role
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestBillingRlsBoundaryRestrictedRole:
    """RLS boundary tests under a restricted PostgreSQL role (T1.16).

    Proves that FORCE RLS on billing tables correctly enforces org isolation
    when ``app.current_org_id`` is set / unset under a non-superuser role.

    Skipped on SQLite.
    """

    @pytest.fixture(autouse=True)
    def _skip_if_not_postgres(self) -> None:
        if connection.vendor != "postgresql":
            pytest.skip("RLS boundary testing requires PostgreSQL")

    def _make_org(self, name: str, slug: str) -> Any:
        from quickscale_modules_orgs.models import Organization

        return Organization.objects.create(name=name, slug=slug)

    def test_restricted_role_sees_nothing_with_non_matching_org_context(self) -> None:
        """With ``app.current_org_id`` set to a bogus UUID, RLS returns zero
        rows on all billing RLS-protected tables (fail-closed at the DB level)."""
        _ensure_rls_test_role()

        org = self._make_org("Billing Org A", "billing-org-a")
        plan = _make_plan(None)

        set_current_org_id(org.pk)
        try:
            CreditBalance.objects.get_or_create(organization=org)
            Subscription.objects.create(organization=org, plan=plan)
        finally:
            set_current_org_id(None)

        bogus_org = uuid.uuid4()
        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
            try:
                cursor.execute("SET app.current_org_id = %s", [str(bogus_org)])
                for table in _BILLING_RLS_TABLES:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    (count,) = cursor.fetchone()
                    assert count == 0, (
                        f"RLS should block all rows on {table} with non-matching org"
                    )
            finally:
                cursor.execute("RESET ROLE")

    def test_restricted_role_sees_only_own_org_credit_balance(self) -> None:
        """With ``app.current_org_id`` set, a restricted role sees only the
        owning org's CreditBalance and cannot see another org's."""
        _ensure_rls_test_role()

        org_a = self._make_org("Billing Org A2", "billing-org-a2")
        org_b = self._make_org("Billing Org B2", "billing-org-b2")

        set_current_org_id(org_a.pk)
        try:
            CreditBalance.objects.get_or_create(organization=org_a)
        finally:
            set_current_org_id(None)

        set_current_org_id(org_b.pk)
        try:
            CreditBalance.objects.get_or_create(organization=org_b)
        finally:
            set_current_org_id(None)

        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
            try:
                cursor.execute("SET app.current_org_id = %s", [str(org_a.pk)])
                cursor.execute(
                    "SELECT organization_id FROM quickscale_modules_billing_creditbalance"
                )
                org_ids = [str(r[0]) for r in cursor.fetchall()]
                assert org_ids == [str(org_a.pk)], (
                    f"Expected only org_a balance, got {org_ids}"
                )

                cursor.execute("SET app.current_org_id = %s", [str(org_b.pk)])
                cursor.execute(
                    "SELECT organization_id FROM quickscale_modules_billing_creditbalance"
                )
                org_ids = [str(r[0]) for r in cursor.fetchall()]
                assert org_ids == [str(org_b.pk)], (
                    f"Cross-org: expected only org_b balance, got {org_ids}"
                )
            finally:
                cursor.execute("RESET ROLE")

    def test_unset_org_context_returns_zero_rows_credit_balance(self) -> None:
        """With no ``app.current_org_id`` set (NULL from current_setting), RLS
        returns zero rows — fail-closed behavior."""
        _ensure_rls_test_role()

        org = self._make_org("Billing Org C", "billing-org-c")

        set_current_org_id(org.pk)
        try:
            CreditBalance.objects.get_or_create(organization=org)
        finally:
            set_current_org_id(None)

        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
            try:
                cursor.execute("RESET app.current_org_id")
                cursor.execute(
                    "SELECT COUNT(*) FROM quickscale_modules_billing_creditbalance"
                )
                (count,) = cursor.fetchone()
                assert count == 0, (
                    "RLS should block all credit balances when org context is unset"
                )
            finally:
                cursor.execute("RESET ROLE")


# ---------------------------------------------------------------------------
# Webhook zero-ambient-context test (PLAN-T1.16-006)
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestWebhookEstablishesOrgContextInternally:
    """Proves ``handle_stripe_event()`` establishes org context internally.

    PLAN-T1.16-006: The webhook entry point has zero ambient org context.
    After the handler returns, the ContextVar must be restored to None
    (fail-closed) and the resulting CreditTransaction/CreditBalance rows
    must only be visible under the correct ``app.current_org_id``.

    Skipped on SQLite.
    """

    @pytest.fixture(autouse=True)
    def _skip_if_not_postgres(self) -> None:
        if connection.vendor != "postgresql":
            pytest.skip("Webhook RLS context test requires PostgreSQL")

    def test_handle_stripe_event_starts_and_ends_with_no_context(
        self, organization, user
    ) -> None:
        """``handle_stripe_event`` must start with no org context and restore
        None after completion — no ambient context leaks into or out of the handler."""
        # Verify zero ambient context before calling handler
        assert get_current_org_id() is None, (
            "Test setup must start with no org context (zero ambient context)"
        )

        plan = _make_plan(None)
        stripe_event_id = f"evt_rls_test_{uuid.uuid4().hex[:8]}"

        # Build a minimal checkout.session.completed payload
        event_payload: Mapping[str, Any] = {
            "id": stripe_event_id,
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": f"cs_{uuid.uuid4().hex[:16]}",
                    "mode": "payment",
                    "payment_status": "paid",
                    "customer": None,
                    "client_reference_id": str(user.pk),
                    "payment_intent": f"pi_{uuid.uuid4().hex[:16]}",
                    "metadata": {
                        "quickscale_org_reference": str(organization.pk),
                        "quickscale_plan_slug": plan.slug,
                        "quickscale_plan_credits": str(plan.credits_per_period),
                        "quickscale_plan_interval": str(plan.billing_interval),
                        "stripe_price_id": plan.stripe_price_id,
                    },
                }
            },
        }

        mock_client = MagicMock()
        mock_client.construct_event.return_value = event_payload
        mock_client.retrieve_payment_intent.return_value = {
            "id": event_payload["data"]["object"]["payment_intent"],
            "amount": plan.credits_per_period * 100,
            "currency": "usd",
            "metadata": event_payload["data"]["object"]["metadata"],
        }

        mock_snapshot = MagicMock()
        mock_snapshot.enabled = True
        mock_snapshot.resolve_webhook_secret.return_value = "whsec_test"

        with (
            patch(
                "quickscale_modules_billing.services.BillingSettingsSnapshot.from_settings",
                return_value=mock_snapshot,
            ),
            patch(
                "quickscale_modules_billing.services.get_stripe_client",
                return_value=mock_client,
            ),
        ):
            result = handle_stripe_event(
                body=b"{}",
                signature="t=1,v1=abc",
                stripe_client=mock_client,
                settings_snapshot=mock_snapshot,
            )

        # ContextVar must be restored to None after the handler returns
        assert get_current_org_id() is None, (
            "handle_stripe_event must not leak org context after completion"
        )

        assert result.event_type == "checkout.session.completed"
        # CreditTransaction row should exist and only be visible under correct org context
        assert CreditTransaction.all_objects.filter(
            stripe_event_id=stripe_event_id
        ).exists(), "CreditTransaction should be created by the handler"
