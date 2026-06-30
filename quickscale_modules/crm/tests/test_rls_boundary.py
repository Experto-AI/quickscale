"""PostgreSQL RLS boundary tests for the CRM module.

T1.11 — DB-level RLS isolation proof under a restricted PostgreSQL role.

These tests verify that ``FORCE ROW LEVEL SECURITY`` on CRM tables
correctly enforces org isolation at the DB layer when
``app.current_org_id`` is set / unset.

Skipped on non-PostgreSQL databases (SQLite during CI unit tests).
"""

from __future__ import annotations

import uuid

import pytest
from django.db import connection

from quickscale_modules_crm.models import Company, Contact, Tag

# ---------------------------------------------------------------------------
# Restricted role helpers (mirror the social module pattern)
# ---------------------------------------------------------------------------

_RESTRICTED_ROLE = "quickscale_rls_test_role"
_CRM_TABLES = (
    "quickscale_modules_crm_tag",
    "quickscale_modules_crm_company",
    "quickscale_modules_crm_contact",
    "quickscale_modules_crm_stage",
    "quickscale_modules_crm_deal",
    "quickscale_modules_crm_contactnote",
    "quickscale_modules_crm_dealnote",
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
            for table in _CRM_TABLES:
                cur.execute(f"GRANT SELECT ON {table} TO {_RESTRICTED_ROLE}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Boundary tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestCrmRlsBoundaryRestrictedRole:
    """RLS boundary tests under a restricted PostgreSQL role (T1.11).

    Proves that FORCE RLS on CRM tables correctly enforces org isolation
    when ``app.current_org_id`` is set / unset under a non-superuser role.

    Skipped on SQLite.
    """

    @pytest.fixture(autouse=True)
    def _skip_if_not_postgres(self) -> None:
        if connection.vendor != "postgresql":
            pytest.skip("RLS boundary testing requires PostgreSQL")

    def test_restricted_role_sees_nothing_with_non_matching_org_context(
        self, org_a, org_b
    ) -> None:
        """With ``app.current_org_id`` set to a bogus UUID, RLS returns zero
        rows on all CRM tables (fail-closed at the DB level)."""
        _ensure_rls_test_role()

        from quickscale_modules_orgs.current_org import set_current_org_id

        set_current_org_id(org_a.id)
        try:
            Tag.objects.create(name="Org A Tag", organization=org_a)
            Company.objects.create(name="Org A Company", organization=org_a)
            Contact.objects.create(
                first_name="Alice",
                last_name="A",
                email="alice@example.com",
                organization=org_a,
            )
        finally:
            set_current_org_id(None)

        bogus_org = uuid.uuid4()
        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
            try:
                cursor.execute("SET app.current_org_id = %s", [str(bogus_org)])
                for table in _CRM_TABLES:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    (count,) = cursor.fetchone()
                    assert count == 0, (
                        f"RLS should block all rows on {table} with non-matching org"
                    )
            finally:
                cursor.execute("RESET ROLE")

    def test_restricted_role_sees_only_own_org_contact(self, org_a, org_b) -> None:
        """With ``app.current_org_id`` set, a restricted role sees only the
        owning org's contacts and cannot see another org's contacts."""
        _ensure_rls_test_role()

        from quickscale_modules_orgs.current_org import set_current_org_id

        set_current_org_id(org_a.id)
        try:
            Contact.objects.create(
                first_name="Alice",
                last_name="A",
                email="alice@example.com",
                organization=org_a,
            )
        finally:
            set_current_org_id(None)

        set_current_org_id(org_b.id)
        try:
            Contact.objects.create(
                first_name="Bob",
                last_name="B",
                email="bob@example.com",
                organization=org_b,
            )
        finally:
            set_current_org_id(None)

        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
            try:
                # Org A context
                cursor.execute("SET app.current_org_id = %s", [str(org_a.id)])
                cursor.execute(
                    "SELECT first_name FROM quickscale_modules_crm_contact ORDER BY first_name"
                )
                names = [r[0] for r in cursor.fetchall()]
                assert names == ["Alice"], f"Expected only Alice, got {names}"

                # Switch to Org B context
                cursor.execute("SET app.current_org_id = %s", [str(org_b.id)])
                cursor.execute(
                    "SELECT first_name FROM quickscale_modules_crm_contact ORDER BY first_name"
                )
                names = [r[0] for r in cursor.fetchall()]
                assert names == ["Bob"], f"Cross-org: expected only Bob, got {names}"
            finally:
                cursor.execute("RESET ROLE")

    def test_restricted_role_sees_only_own_org_company(self, org_a, org_b) -> None:
        """Cross-org isolation for Company table."""
        _ensure_rls_test_role()

        from quickscale_modules_orgs.current_org import set_current_org_id

        set_current_org_id(org_a.id)
        try:
            Company.objects.create(name="Acme Corp", organization=org_a)
        finally:
            set_current_org_id(None)

        set_current_org_id(org_b.id)
        try:
            Company.objects.create(name="Beta Ltd", organization=org_b)
        finally:
            set_current_org_id(None)

        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
            try:
                cursor.execute("SET app.current_org_id = %s", [str(org_a.id)])
                cursor.execute(
                    "SELECT name FROM quickscale_modules_crm_company ORDER BY name"
                )
                names = [r[0] for r in cursor.fetchall()]
                assert names == ["Acme Corp"], f"Expected only Acme Corp, got {names}"

                cursor.execute("SET app.current_org_id = %s", [str(org_b.id)])
                cursor.execute(
                    "SELECT name FROM quickscale_modules_crm_company ORDER BY name"
                )
                names = [r[0] for r in cursor.fetchall()]
                assert names == ["Beta Ltd"], (
                    f"Cross-org: expected only Beta Ltd, got {names}"
                )
            finally:
                cursor.execute("RESET ROLE")

    # ------------------------------------------------------------------
    # AF9 Phase 3 — Restricted-role cursor proof (PR-AF9-003)
    # ------------------------------------------------------------------

    def test_af9_priming_proof_restricted_role_cursor(self, org_a) -> None:
        """PR-AF9-003: The AF9 execute wrapper primes the GUC from the
        ContextVar under a restricted PostgreSQL role.

        Unlike the existing T1.11 tests that manually issue
        ``SET app.current_org_id`` on the cursor, this test calls
        ``set_current_org_id(org.pk)`` and lets the AF9 execute wrapper
        derive the GUC.  Under the restricted role, a SELECT on an
        RLS-protected table must return the expected rows — proving
        the wrapper correctly issues ``SET LOCAL`` on the live cursor
        before tenant SQL executes.

        Steps:
        1. Pre-seed CRM data under the superuser connection.
        2. Call ``set_current_org_id(org.pk)`` — no manual SET LOCAL.
        3. ``SET ROLE`` to the restricted role.
        4. Run a SELECT through the connection cursor.
        5. The AF9 execute wrapper fires, issues ``SET LOCAL`` from
           the ContextVar, then runs the SELECT.
        6. Assert the RLS-gated query returns the expected rows.
        """
        from quickscale_modules_orgs.current_org import set_current_org_id

        _ensure_rls_test_role()

        # Pre-seed data under superuser connection.
        set_current_org_id(org_a.id)
        try:
            Tag.objects.create(name="AF9 Tag", organization=org_a)
            Company.objects.create(name="AF9 Company", organization=org_a)
        finally:
            set_current_org_id(None)

        # Set the ContextVar — the AF9 wrapper derives the GUC from this.
        set_current_org_id(org_a.id)
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
                try:
                    # SELECT triggers the AF9 execute wrapper, which
                    # issues SET LOCAL from the ContextVar before
                    # running the query — no manual SET required.
                    cursor.execute(
                        "SELECT name FROM quickscale_modules_crm_tag ORDER BY name"
                    )
                    names = [r[0] for r in cursor.fetchall()]
                    assert names == ["AF9 Tag"], (
                        f"Expected AF9 Tag, got {names}. "
                        "The AF9 wrapper must prime app.current_org_id "
                        "from the ContextVar for the restricted-role cursor."
                    )
                finally:
                    cursor.execute("RESET ROLE")
        finally:
            set_current_org_id(None)

    def test_unset_org_context_returns_zero_rows_contacts(self, org_a) -> None:
        """With no ``app.current_org_id`` set (NULL from current_setting), RLS
        returns zero rows — fail-closed behavior."""
        _ensure_rls_test_role()

        from quickscale_modules_orgs.current_org import set_current_org_id

        set_current_org_id(org_a.id)
        try:
            Contact.objects.create(
                first_name="Alice",
                last_name="A",
                email="alice@example.com",
                organization=org_a,
            )
        finally:
            set_current_org_id(None)

        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
            try:
                # Reset so current_setting returns NULL
                cursor.execute("RESET app.current_org_id")
                cursor.execute("SELECT COUNT(*) FROM quickscale_modules_crm_contact")
                (count,) = cursor.fetchone()
                assert count == 0, (
                    "RLS should block all contacts when org context is unset (fail-closed)"
                )
            finally:
                cursor.execute("RESET ROLE")
