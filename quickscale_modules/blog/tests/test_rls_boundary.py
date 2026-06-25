"""PostgreSQL RLS boundary tests for the Blog module.

T1.12 — DB-level RLS isolation proof under a restricted PostgreSQL role.

These tests verify that ``FORCE ROW LEVEL SECURITY`` on Blog tables
correctly enforces org isolation at the DB layer when
``app.current_org_id`` is set / unset.

Skipped on non-PostgreSQL databases (SQLite during CI unit tests).
"""

from __future__ import annotations

import uuid

import pytest
from django.db import connection

from quickscale_modules_blog.models import Category, Tag

# ---------------------------------------------------------------------------
# Restricted role helpers (mirror the social module pattern)
# ---------------------------------------------------------------------------

_RESTRICTED_ROLE = "quickscale_rls_test_role"
_BLOG_TABLES = (
    "quickscale_modules_blog_category",
    "quickscale_modules_blog_tag",
    "quickscale_modules_blog_blogmediaasset",
    "quickscale_modules_blog_post",
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
            for table in _BLOG_TABLES:
                cur.execute(f"GRANT SELECT ON {table} TO {_RESTRICTED_ROLE}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Boundary tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestBlogRlsBoundaryRestrictedRole:
    """RLS boundary tests under a restricted PostgreSQL role (T1.12).

    Proves that FORCE RLS on Blog tables correctly enforces org isolation
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
        rows on all Blog tables (fail-closed at the DB level)."""
        _ensure_rls_test_role()

        from quickscale_modules_orgs.current_org import set_current_org_id

        set_current_org_id(org_a.id)
        try:
            Category.objects.create(
                name="Org A Category",
                slug="org-a-category",
                organization=org_a,
            )
        finally:
            set_current_org_id(None)

        bogus_org = uuid.uuid4()
        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
            try:
                cursor.execute("SET app.current_org_id = %s", [str(bogus_org)])
                for table in (
                    "quickscale_modules_blog_category",
                    "quickscale_modules_blog_tag",
                ):
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    (count,) = cursor.fetchone()
                    assert count == 0, (
                        f"RLS should block all rows on {table} with non-matching org"
                    )
            finally:
                cursor.execute("RESET ROLE")

    def test_restricted_role_sees_only_own_org_category(self, org_a, org_b) -> None:
        """With ``app.current_org_id`` set, a restricted role sees only the
        owning org's categories and cannot see another org's categories."""
        _ensure_rls_test_role()

        from quickscale_modules_orgs.current_org import set_current_org_id

        set_current_org_id(org_a.id)
        try:
            Category.objects.create(
                name="Org A Category",
                slug="org-a-category",
                organization=org_a,
            )
        finally:
            set_current_org_id(None)

        set_current_org_id(org_b.id)
        try:
            Category.objects.create(
                name="Org B Category",
                slug="org-b-category",
                organization=org_b,
            )
        finally:
            set_current_org_id(None)

        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
            try:
                cursor.execute("SET app.current_org_id = %s", [str(org_a.id)])
                cursor.execute(
                    "SELECT name FROM quickscale_modules_blog_category ORDER BY name"
                )
                names = [r[0] for r in cursor.fetchall()]
                assert names == ["Org A Category"], (
                    f"Expected only Org A Category, got {names}"
                )

                cursor.execute("SET app.current_org_id = %s", [str(org_b.id)])
                cursor.execute(
                    "SELECT name FROM quickscale_modules_blog_category ORDER BY name"
                )
                names = [r[0] for r in cursor.fetchall()]
                assert names == ["Org B Category"], (
                    f"Cross-org: expected only Org B Category, got {names}"
                )
            finally:
                cursor.execute("RESET ROLE")

    def test_restricted_role_sees_only_own_org_tag(self, org_a, org_b) -> None:
        """Cross-org isolation for Tag table."""
        _ensure_rls_test_role()

        from quickscale_modules_orgs.current_org import set_current_org_id

        set_current_org_id(org_a.id)
        try:
            Tag.objects.create(name="Org A Tag", slug="org-a-tag", organization=org_a)
        finally:
            set_current_org_id(None)

        set_current_org_id(org_b.id)
        try:
            Tag.objects.create(name="Org B Tag", slug="org-b-tag", organization=org_b)
        finally:
            set_current_org_id(None)

        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
            try:
                cursor.execute("SET app.current_org_id = %s", [str(org_a.id)])
                cursor.execute(
                    "SELECT name FROM quickscale_modules_blog_tag ORDER BY name"
                )
                names = [r[0] for r in cursor.fetchall()]
                assert names == ["Org A Tag"], f"Expected only Org A Tag, got {names}"

                cursor.execute("SET app.current_org_id = %s", [str(org_b.id)])
                cursor.execute(
                    "SELECT name FROM quickscale_modules_blog_tag ORDER BY name"
                )
                names = [r[0] for r in cursor.fetchall()]
                assert names == ["Org B Tag"], (
                    f"Cross-org: expected only Org B Tag, got {names}"
                )
            finally:
                cursor.execute("RESET ROLE")

    def test_unset_org_context_returns_zero_rows_category(self, org_a) -> None:
        """With no ``app.current_org_id`` set (NULL from current_setting), RLS
        returns zero rows — fail-closed behavior."""
        _ensure_rls_test_role()

        from quickscale_modules_orgs.current_org import set_current_org_id

        set_current_org_id(org_a.id)
        try:
            Category.objects.create(
                name="Org A Category",
                slug="org-a-category",
                organization=org_a,
            )
        finally:
            set_current_org_id(None)

        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
            try:
                cursor.execute("RESET app.current_org_id")
                cursor.execute("SELECT COUNT(*) FROM quickscale_modules_blog_category")
                (count,) = cursor.fetchone()
                assert count == 0, (
                    "RLS should block all categories when org context is unset (fail-closed)"
                )
            finally:
                cursor.execute("RESET ROLE")
