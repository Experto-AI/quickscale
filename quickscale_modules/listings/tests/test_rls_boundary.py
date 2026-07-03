"""PostgreSQL RLS boundary tests for the Listings module.

T1.14 — DB-level RLS isolation proof under a restricted PostgreSQL role.

These tests verify that ``FORCE ROW LEVEL SECURITY`` on the Listing table
correctly enforces org isolation at the DB layer when
``app.current_org_id`` is set / unset.

SA11.4 — Restricted-role anonymous-read listings smoke test that proves
the full Django request path (middleware, view, template) returns
published System-org content under the NOBYPASSRLS runtime role.

Skipped on non-PostgreSQL databases (SQLite during CI unit tests).
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from django.db import connection
from django.urls import reverse

from quickscale_modules_listings.models import Listing
from quickscale_modules_orgs.models import Organization

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
        self,
        org_a: Organization,
        org_b: Organization,
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

    def test_restricted_role_sees_only_own_org_listings(
        self, org_a: Organization, org_b: Organization
    ) -> None:
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

    def test_unset_org_context_returns_zero_rows(self, org_a: Organization) -> None:
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


# ---------------------------------------------------------------------------
# SA11.4 — Restricted-role anonymous-read listings smoke test
# ---------------------------------------------------------------------------
# Proves the full Django request path (middleware, view, template, DB)
# returns published System-org listing content under the NOBYPASSRLS runtime
# role.  Without the SA11.4 migration of listings views to
# ``ListingsPublicReadMixin`` (→ ``PublicSystemOrgReadMixin``), the GUC
# is never primed and every RLS-gated query returns zero rows — turning
# this test red.
#
# Pattern follows ``quickscale_modules_blog/tests/test_rls_boundary.py:324-379``:
#   1. Create System-org listing data before SET ROLE (superuser connection).
#   2. SET ROLE to the restricted runtime role.
#   3. Make an anonymous request through the full Django stack.
#   4. Assert the response contains the expected content.
#   5. RESET ROLE.
# ---------------------------------------------------------------------------

_RESTRICTED_ANON_ROLE = "quickscale_rls_test_role"
_ANON_LISTINGS_TABLES = ("quickscale_modules_listings_listing",)
_SYSTEM_ANON_TABLES = (
    "auth_user",
    "django_session",
)
_ORGS_ANON_TABLES = ("quickscale_modules_orgs_organization",)


def _ensure_anon_listings_rls_test_role() -> None:
    """Create the restricted role with SELECT grants for anonymous listings reads.

    Grants SELECT on listings tenant tables, auth_user (for author display in
    templates), orgs tables (for System org resolution), and Django system
    tables needed for the request pipeline.

    Idempotent — subsequent calls are no-ops.
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
                    CREATE ROLE {_RESTRICTED_ANON_ROLE};
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
            """)
            cur.execute(f"GRANT USAGE ON SCHEMA public TO {_RESTRICTED_ANON_ROLE}")
            for table in _ANON_LISTINGS_TABLES:
                cur.execute(f"GRANT SELECT ON {table} TO {_RESTRICTED_ANON_ROLE}")
            for table in _SYSTEM_ANON_TABLES:
                cur.execute(f"GRANT SELECT ON {table} TO {_RESTRICTED_ANON_ROLE}")
            for table in _ORGS_ANON_TABLES:
                cur.execute(f"GRANT SELECT ON {table} TO {_RESTRICTED_ANON_ROLE}")
    finally:
        conn.close()


@pytest.mark.django_db(transaction=True)
class TestListingsRlsAnonymousReadUnderRestrictedRole:
    """Anonymous listings reads under the NOBYPASSRLS runtime role (SA11.4).

    Proves that the full Django request pipeline returns published
    System-org listing content when running under a restricted PostgreSQL
    role that does not bypass RLS.

    Exercises the shipped ``Listing`` table (``quickscale_modules_listings_listing``,
    migration-backed with FORCE-RLS) via the production URL routing, making
    this a true regression proof for the shipped table that broke anonymous
    listing reads.
    """

    @pytest.fixture(autouse=True)
    def _skip_if_not_postgres(self) -> None:
        if connection.vendor != "postgresql":
            pytest.skip("RLS anonymous-read test requires PostgreSQL")

    def test_anonymous_listings_list_under_restricted_role(
        self,
        system_org: Any,
        client: Any,
    ) -> None:
        """Anonymous /listings/ returns System-org content under restricted role.

        Exercises the full Django request pipeline — middleware, view,
        ``ListingsPublicReadMixin.dispatch()`` (which primes the GUC via
        ``org_scope()``), template rendering, and DB queries — under
        the NOBYPASSRLS runtime role.

        Uses the shipped ``Listing`` model (migration-backed with FORCE-RLS
        on ``quickscale_modules_listings_listing``) so the test proves
        RLS behavior for the production table that broke anonymous reads.
        """
        _ensure_anon_listings_rls_test_role()

        Listing.objects.create(
            title="Anonymous Can See This Listing",
            slug="anonymous-can-see-this-listing",
            description="Public System-org listing for RLS smoke test.",
            status="published",
            organization=system_org,
        )

        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ANON_ROLE}")

        try:
            response = client.get(reverse("quickscale_listings:listing_list"))
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")

        assert response.status_code == 200, (
            f"Expected 200 OK under restricted role, got {response.status_code}. "
            f"Response: {response.content.decode()[:500]}"
        )
        body = response.content.decode()
        assert "Anonymous Can See This Listing" in body, (
            "Anonymous listings list under restricted role must return "
            "published System-org content. "
            f"Got: {body[:500]}"
        )

    def test_anonymous_listings_detail_under_restricted_role(
        self,
        system_org: Any,
        client: Any,
    ) -> None:
        """Anonymous /listings/<slug>/ returns System-org content under restricted role.

        Exercises the full Django request pipeline for the detail view
        under the NOBYPASSRLS runtime role.

        Uses the shipped ``Listing`` model (migration-backed with FORCE-RLS
        on ``quickscale_modules_listings_listing``) so the test proves
        RLS behavior for the production table that broke anonymous reads.
        """
        _ensure_anon_listings_rls_test_role()

        listing = Listing.objects.create(
            title="Anonymous Can See Detail",
            slug="anonymous-can-see-detail",
            description="Public System-org listing detail for RLS smoke test.",
            status="published",
            organization=system_org,
        )

        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ANON_ROLE}")

        try:
            response = client.get(
                reverse("quickscale_listings:listing_detail", args=[listing.slug])
            )
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")

        assert response.status_code == 200, (
            f"Expected 200 OK under restricted role, got {response.status_code}. "
            f"Response: {response.content.decode()[:500]}"
        )
        body = response.content.decode()
        assert "Anonymous Can See Detail" in body, (
            "Anonymous listings detail under restricted role must return "
            "published System-org content. "
            f"Got: {body[:500]}"
        )
