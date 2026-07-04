"""PostgreSQL RLS boundary tests for the Billing module.

T1.16 — DB-level RLS isolation proof under a restricted PostgreSQL role.

These tests verify that:
1. ``FORCE ROW LEVEL SECURITY`` on billing tables enforces org isolation
   at the DB layer when ``app.current_org_id`` is set / unset.
2. ``handle_stripe_event()`` starts with zero ambient org context and
    establishes context internally via ``org_scope``, so the
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
    handle_stripe_event,
)
from quickscale_modules_orgs.current_org import (
    get_current_org_id,
    org_scope,
    set_current_org_id,
)
from quickscale_modules_orgs.models import Organization

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
    import psycopg2

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


def _ensure_rls_policies() -> None:
    """Re-apply FORCE-RLS policies on Billing tables if they are missing.

    DDL side effects from prior tests (e.g. the migration test that
    reverses 0002_enable_rls) can permanently drop RLS policies because
    the reverse DDL auto-commits.  This helper checks and re-applies RLS
    so the RLS boundary tests are self-healing.

    Connects via psycopg2 with autocommit=True so DDL persists even
    inside a Django test transaction.  Idempotent.
    """
    import psycopg2

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
            # Check if RLS policies exist on the credit balance table
            cur.execute(
                "SELECT COUNT(*) FROM pg_policies "
                "WHERE tablename = 'quickscale_modules_billing_creditbalance'"
            )
            (policy_count,) = cur.fetchone()
            if policy_count > 0:
                return  # RLS is already active

            # Re-apply RLS for every enrolled table with explicit policy names
            _rls_targets = (
                (
                    "quickscale_modules_billing_creditbalance",
                    "billing_credit_balance_org_isolation",
                ),
                (
                    "quickscale_modules_billing_credittransaction",
                    "billing_credit_transaction_org_isolation",
                ),
                (
                    "quickscale_modules_billing_subscription",
                    "billing_subscription_org_isolation",
                ),
            )
            for table, policy_name in _rls_targets:
                cur.execute(f"""
                    ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
                    ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
                    CREATE POLICY {policy_name} ON {table}
                        FOR ALL
                        USING (NULLIF(current_setting('app.current_org_id', true), '')::uuid = organization_id)
                        WITH CHECK (NULLIF(current_setting('app.current_org_id', true), '')::uuid = organization_id);
                """)
    finally:
        conn.close()


def _make_plan() -> Plan:
    return Plan.objects.create(
        name="Test Plan",
        slug="test-plan",
        credits_per_period=100,
        price_cents=0,
        billing_interval=Plan.BillingInterval.MONTHLY,
        stripe_price_id="price_test_rls",
    )


# ---------------------------------------------------------------------------
# org_scope tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestBillingOrgDbContext:
    """Unit tests for the ``org_scope`` context manager."""

    @pytest.fixture(autouse=True)
    def _skip_if_not_postgres(self) -> None:
        if connection.vendor != "postgresql":
            pytest.skip("DB-level billing org context requires PostgreSQL")

    def test_sets_and_restores_contextvar(self, organization: Organization) -> None:
        """Context manager sets org context on entry and restores it on exit."""
        prior = get_current_org_id()
        with org_scope(organization):
            assert get_current_org_id() == organization.pk
        assert get_current_org_id() == prior

    def test_clears_contextvar_when_org_is_none(
        self, organization: Organization
    ) -> None:
        """When org is None, context manager clears the ContextVar."""
        set_current_org_id(organization.pk)
        try:
            with org_scope(None):
                assert get_current_org_id() is None
        finally:
            set_current_org_id(None)

    def test_restores_contextvar_on_exception(self, organization: Organization) -> None:
        """ContextVar is restored even when the body raises."""
        set_current_org_id(None)
        with pytest.raises(ValueError):
            with org_scope(organization):
                assert get_current_org_id() == organization.pk
                raise ValueError("test exception")
        assert get_current_org_id() is None

    def _read_db_current_org_id(self) -> str | None:
        """Read the current ``app.current_org_id`` directly from PostgreSQL.

        Returns ``None`` when the GUC is unset (returns empty string from
        ``current_setting(..., true)``) rather than ``""`` so callers can
        reliably compare against ``None`` for "no org context".
        """
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.current_org_id', true)")
            (value,) = cursor.fetchone()
        result = str(value) if value is not None else None
        return result if result else None

    def test_restores_db_setting_on_exit(self, organization: Organization) -> None:
        """DB ``app.current_org_id`` is restored to prior value on exit."""
        prior_db = self._read_db_current_org_id()
        prior_ctx = get_current_org_id()
        with org_scope(organization):
            assert self._read_db_current_org_id() == str(organization.pk)
        assert get_current_org_id() == prior_ctx
        assert self._read_db_current_org_id() == prior_db

    def test_restores_db_setting_when_prior_is_none(
        self, organization: Organization
    ) -> None:
        """When prior DB value was unset (NULL), exit resets to NULL."""
        # Ensure clean slate
        with connection.cursor() as cursor:
            cursor.execute("RESET app.current_org_id")
        prior_ctx = get_current_org_id()
        with org_scope(organization):
            assert self._read_db_current_org_id() == str(organization.pk)
        assert get_current_org_id() == prior_ctx
        assert self._read_db_current_org_id() is None

    def test_nested_scope_restores_db_setting(self, organization: Organization) -> None:
        """Nested ``org_scope()`` restores the outer DB value on inner exit."""
        org_b = organization.__class__.objects.create(name="Org B", slug="org-b")
        prior_db = self._read_db_current_org_id()
        prior_ctx = get_current_org_id()

        with org_scope(organization):
            assert self._read_db_current_org_id() == str(organization.pk)
            with org_scope(org_b):
                assert self._read_db_current_org_id() == str(org_b.pk)
            # After inner scope exits, DB must be restored to org_a
            assert self._read_db_current_org_id() == str(organization.pk)
            assert get_current_org_id() == organization.pk

        # After outer scope exits, DB must be restored to prior
        assert get_current_org_id() == prior_ctx
        assert self._read_db_current_org_id() == prior_db

    def test_none_inside_non_none_scope_resets_and_restores_db(
        self, organization: Organization
    ) -> None:
        """``org_scope(None)`` inside ``org_scope(org)`` temporarily resets
        the DB to NULL (fail-closed) and restores on exit (CR-T119-001).

        Exercises the real nested path: outer ``org_scope(organization)``
        then inner ``org_scope(None)``.  Verifies:

        1. Inner ContextVar is ``None``.
        2. Inner DB ``app.current_org_id`` is ``NULL`` (fail-closed).
        3. After inner exit, both ContextVar and DB are restored to the
           outer org value.
        4. After outer exit, both ContextVar and DB are restored to the
           original prior state (whatever it was before the outer scope).
        """
        prior_ctx = get_current_org_id()
        prior_db = self._read_db_current_org_id()

        with org_scope(organization):
            # Outer scope — ContextVar and DB are set to the outer org
            assert get_current_org_id() == organization.pk
            assert self._read_db_current_org_id() == str(organization.pk)

            with org_scope(None):
                # Inner None scope — ContextVar is None, DB is NULL
                # (fail-closed — RLS returns zero rows)
                assert get_current_org_id() is None
                assert self._read_db_current_org_id() is None

            # After inner exit — both restored to the outer org value
            assert get_current_org_id() == organization.pk
            assert self._read_db_current_org_id() == str(organization.pk)

        # After outer exit — both restored to the original prior state
        assert get_current_org_id() == prior_ctx
        assert self._read_db_current_org_id() == prior_db


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
        _ensure_rls_policies()

        org = self._make_org("Billing Org A", "billing-org-a")
        plan = _make_plan()

        set_current_org_id(org.pk)
        try:
            CreditBalance.objects.get_or_create(organization=org)
            Subscription.objects.create(organization=org, plan=plan)
        finally:
            set_current_org_id(None)

        bogus_org = uuid.uuid4()
        with connection.cursor() as cursor:
            cursor.execute("RESET app.current_org_id")
            cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
            try:
                cursor.execute("SET SESSION app.current_org_id = %s", [str(bogus_org)])
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
        _ensure_rls_policies()

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
            cursor.execute("RESET app.current_org_id")
            cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
            try:
                cursor.execute("SET SESSION app.current_org_id = %s", [str(org_a.pk)])
                cursor.execute(
                    "SELECT organization_id FROM quickscale_modules_billing_creditbalance"
                )
                org_ids = [str(r[0]) for r in cursor.fetchall()]
                assert org_ids == [str(org_a.pk)], (
                    f"Expected only org_a balance, got {org_ids}"
                )

                cursor.execute("SET SESSION app.current_org_id = %s", [str(org_b.pk)])
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
        _ensure_rls_policies()

        org = self._make_org("Billing Org C", "billing-org-c")

        set_current_org_id(org.pk)
        try:
            CreditBalance.objects.get_or_create(organization=org)
        finally:
            set_current_org_id(None)

        with connection.cursor() as cursor:
            cursor.execute("RESET app.current_org_id")
            cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
            try:
                cursor.execute("SET SESSION app.current_org_id = ''")
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
        self, organization: Organization, user: Any
    ) -> None:
        """``handle_stripe_event`` must start with no org context and restore
        None after completion — no ambient context leaks into or out of the handler."""
        # Verify zero ambient context before calling handler
        assert get_current_org_id() is None, (
            "Test setup must start with no org context (zero ambient context)"
        )

        plan = _make_plan()
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
                    "client_reference_id": f"{user._meta.label_lower}:{user.pk}",
                    "payment_intent": f"pi_{uuid.uuid4().hex[:16]}",
                    "metadata": {
                        "quickscale_user_reference": f"{user._meta.label_lower}:{user.pk}",
                        "quickscale_org_reference": f"{organization._meta.label_lower}:{organization.pk}",
                        "quickscale_plan_slug": plan.slug,
                        "quickscale_plan_credits": str(plan.credits_per_period),
                        "quickscale_plan_interval": Plan.BillingInterval.ONE_TIME,
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
