"""PostgreSQL RLS boundary tests for the Listings module.

T1.14 — DB-level RLS isolation proof under a restricted PostgreSQL role.

These tests verify that ``FORCE ROW LEVEL SECURITY`` on the Listing table
correctly enforces org isolation at the DB layer when
``app.current_org_id`` is set / unset.

Skipped on non-PostgreSQL databases (SQLite during CI unit tests).
"""

from __future__ import annotations

import uuid

import pytest
from django.db import connection

from quickscale_modules_listings.models import Listing

# ---------------------------------------------------------------------------
# Restricted role helpers (mirror the social module pattern)
# ---------------------------------------------------------------------------

_RESTRICTED_ROLE = "quickscale_rls_test_role"
_LISTINGS_TABLES = ("quickscale_modules_listings_listing",)


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
            for table in _LISTINGS_TABLES:
                cur.execute(f"GRANT SELECT ON {table} TO {_RESTRICTED_ROLE}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Boundary tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestListingsRlsBoundaryRestrictedRole:
    """RLS boundary tests under a restricted PostgreSQL role (T1.14).

    Proves that FORCE RLS on the Listing table correctly enforces org isolation
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
        rows on the Listing table (fail-closed at the DB level)."""
        _ensure_rls_test_role()

        from quickscale_modules_orgs.current_org import set_current_org_id

        set_current_org_id(org_a.id)
        try:
            Listing.objects.create(
                title="Org A Listing",
                slug="org-a-listing",
                organization=org_a,
            )
        finally:
            set_current_org_id(None)

        bogus_org = uuid.uuid4()
        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
            try:
                cursor.execute("SET app.current_org_id = %s", [str(bogus_org)])
                cursor.execute(
                    "SELECT COUNT(*) FROM quickscale_modules_listings_listing"
                )
                (count,) = cursor.fetchone()
                assert count == 0, (
                    "RLS should block all listings with a non-matching org context"
                )
            finally:
                cursor.execute("RESET ROLE")

    def test_restricted_role_sees_only_own_org_listings(self, org_a, org_b) -> None:
        """With ``app.current_org_id`` set, a restricted role sees only the
        owning org's listings and cannot see another org's listings."""
        _ensure_rls_test_role()

        from quickscale_modules_orgs.current_org import set_current_org_id

        set_current_org_id(org_a.id)
        try:
            Listing.objects.create(
                title="Org A Listing",
                slug="org-a-listing",
                organization=org_a,
            )
        finally:
            set_current_org_id(None)

        set_current_org_id(org_b.id)
        try:
            Listing.objects.create(
                title="Org B Listing",
                slug="org-b-listing",
                organization=org_b,
            )
        finally:
            set_current_org_id(None)

        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
            try:
                cursor.execute("SET app.current_org_id = %s", [str(org_a.id)])
                cursor.execute(
                    "SELECT title FROM quickscale_modules_listings_listing ORDER BY title"
                )
                titles = [r[0] for r in cursor.fetchall()]
                assert titles == ["Org A Listing"], (
                    f"Expected only Org A Listing, got {titles}"
                )

                cursor.execute("SET app.current_org_id = %s", [str(org_b.id)])
                cursor.execute(
                    "SELECT title FROM quickscale_modules_listings_listing ORDER BY title"
                )
                titles = [r[0] for r in cursor.fetchall()]
                assert titles == ["Org B Listing"], (
                    f"Cross-org: expected only Org B Listing, got {titles}"
                )
            finally:
                cursor.execute("RESET ROLE")

    def test_unset_org_context_returns_zero_rows(self, org_a) -> None:
        """With no ``app.current_org_id`` set (NULL from current_setting), RLS
        returns zero rows — fail-closed behavior."""
        _ensure_rls_test_role()

        from quickscale_modules_orgs.current_org import set_current_org_id

        set_current_org_id(org_a.id)
        try:
            Listing.objects.create(
                title="Org A Listing",
                slug="org-a-listing",
                organization=org_a,
            )
        finally:
            set_current_org_id(None)

        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
            try:
                cursor.execute("RESET app.current_org_id")
                cursor.execute(
                    "SELECT COUNT(*) FROM quickscale_modules_listings_listing"
                )
                (count,) = cursor.fetchone()
                assert count == 0, (
                    "RLS should block all listings when org context is unset (fail-closed)"
                )
            finally:
                cursor.execute("RESET ROLE")
