"""PostgreSQL RLS boundary tests for the Blog module.

T1.12 — DB-level RLS isolation proof under a restricted PostgreSQL role.

These tests verify that ``FORCE ROW LEVEL SECURITY`` on Blog tables
correctly enforces org isolation at the DB layer when
``app.current_org_id`` is set / unset.

SA11.2 — Restricted-role anonymous-read blog smoke test that proves
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

from quickscale_modules_blog.models import Category, Post, Tag

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
    """Assert the pre-provisioned RLS test role exists (SA59.3).

    The role must be pre-created by the test harness
    (``scripts/provision_test_roles.sh`` or equivalent).  Raises
    ``RuntimeError`` with setup instructions if missing.
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
            cur.execute(
                "SELECT 1 FROM pg_roles WHERE rolname = %s",
                [_RESTRICTED_ROLE],
            )
            if cur.fetchone() is None:
                raise RuntimeError(
                    f"Pre-provisioned role {_RESTRICTED_ROLE} not found. "
                    f"Run scripts/provision_test_roles.sh to create it before "
                    f"running RLS boundary tests."
                )
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
        self, org_a: Any, org_b: Any
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

    def test_restricted_role_sees_only_own_org_category(
        self, org_a: Any, org_b: Any
    ) -> None:
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

    def test_restricted_role_sees_only_own_org_tag(
        self, org_a: Any, org_b: Any
    ) -> None:
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

    def test_unset_org_context_returns_zero_rows_category(self, org_a: Any) -> None:
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


# ---------------------------------------------------------------------------
# SA11.2 — Restricted-role anonymous-read blog smoke test
# ---------------------------------------------------------------------------
# Proves the full Django request path (middleware, view, template, DB)
# returns published System-org blog content under the NOBYPASSRLS runtime
# role.  Without the SA11.3 migration of blog views to
# ``PublicSystemOrgReadMixin``, the GUC is never primed and every RLS-gated
# query returns zero rows — turning this test red.
#
# Follows the CRM pattern in ``test_isolation.py:197-246``:
#   1. Create System-org blog data before SET ROLE (superuser connection).
#   2. SET ROLE to the restricted runtime role.
#   3. Make an anonymous request through the full Django stack.
#   4. Assert the response contains the expected content.
#   5. RESET ROLE.
# ---------------------------------------------------------------------------

_RESTRICTED_ANON_ROLE = "quickscale_rls_test_role"
_ANON_BLOG_TABLES = (
    "quickscale_modules_blog_post",
    "quickscale_modules_blog_category",
    "quickscale_modules_blog_tag",
    "quickscale_modules_blog_blogmediaasset",
    "quickscale_modules_blog_post_tags",
)
_SYSTEM_ANON_TABLES = (
    "auth_user",
    "django_session",
)
_ORGS_ANON_TABLES = ("quickscale_modules_orgs_organization",)


def _ensure_anon_blog_rls_test_role() -> None:
    """Assert the pre-provisioned RLS role exists and issue table grants.

    The role must be pre-created by the test harness
    (``scripts/provision_test_roles.sh`` or equivalent).  Raises
    ``RuntimeError`` with setup instructions if missing.  Per-table
    SELECT grants are still issued here (idempotent, requires table
    existence post-migration).
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
            cur.execute(
                "SELECT 1 FROM pg_roles WHERE rolname = %s",
                [_RESTRICTED_ANON_ROLE],
            )
            if cur.fetchone() is None:
                raise RuntimeError(
                    f"Pre-provisioned role {_RESTRICTED_ANON_ROLE} not found. "
                    f"Run scripts/provision_test_roles.sh to create it before "
                    f"running anonymous-read RLS tests."
                )
            cur.execute(f"GRANT USAGE ON SCHEMA public TO {_RESTRICTED_ANON_ROLE}")
            for table in _ANON_BLOG_TABLES:
                cur.execute(f"GRANT SELECT ON {table} TO {_RESTRICTED_ANON_ROLE}")
            for table in _SYSTEM_ANON_TABLES:
                cur.execute(f"GRANT SELECT ON {table} TO {_RESTRICTED_ANON_ROLE}")
            for table in _ORGS_ANON_TABLES:
                cur.execute(f"GRANT SELECT ON {table} TO {_RESTRICTED_ANON_ROLE}")
    finally:
        conn.close()


@pytest.mark.django_db(transaction=True)
class TestBlogRlsAnonymousReadUnderRestrictedRole:
    """Anonymous blog reads under the NOBYPASSRLS runtime role (SA11.2).

    Proves that the full Django request pipeline returns published
    System-org blog content when running under a restricted PostgreSQL
    role that does not bypass RLS.
    """

    @pytest.fixture(autouse=True)
    def _skip_if_not_postgres(self) -> None:
        if connection.vendor != "postgresql":
            pytest.skip("RLS anonymous-read test requires PostgreSQL")

    def test_anonymous_blog_list_under_restricted_role(
        self,
        system_org: Any,
        author_user: Any,
        client: Any,
    ) -> None:
        """Anonymous /blog/ returns System-org content under restricted role.

        Exercises the full Django request pipeline — middleware, view,
        ``BlogPublicReadMixin.dispatch()`` (which primes the GUC via
        ``org_scope()``), template rendering, and DB queries — under
        the NOBYPASSRLS runtime role.
        """
        _ensure_anon_blog_rls_test_role()

        # Prime the org context so FORCE RLS allows the INSERT under the
        # NOBYPASSRLS restricted role (SA59.3).
        from quickscale_modules_orgs.current_org import set_current_org_id

        set_current_org_id(system_org.id)
        try:
            Post.objects.create(
                title="Anonymous Can See This",
                author=author_user,
                content="Public System-org content for RLS smoke test.",
                status="published",
                organization=system_org,
            )
        finally:
            set_current_org_id(None)

        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ANON_ROLE}")

        try:
            response = client.get(reverse("quickscale_blog:post_list"))
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")

        assert response.status_code == 200, (
            f"Expected 200 OK under restricted role, got {response.status_code}. "
            f"Response: {response.content.decode()[:500]}"
        )
        body = response.content.decode()
        assert "Anonymous Can See This" in body, (
            "Anonymous blog list under restricted role must return "
            "published System-org content. "
            f"Got: {body[:500]}"
        )

    def test_anonymous_blog_feed_under_restricted_role(
        self,
        system_org: Any,
        author_user: Any,
        client: Any,
    ) -> None:
        """Anonymous /blog/feed/ returns System-org content under restricted role.

        Exercises the full Django request pipeline for the RSS feed
        (``LatestPostsFeed.__call__``, which primes the GUC via
        ``org_scope()``), including category and tag traversal in
        ``item_categories()``, under the NOBYPASSRLS runtime role.
        """
        _ensure_anon_blog_rls_test_role()

        # Prime the org context so FORCE RLS allows the INSERT under the
        # NOBYPASSRLS restricted role (SA59.3).
        from quickscale_modules_orgs.current_org import set_current_org_id

        set_current_org_id(system_org.id)
        try:
            category = Category.objects.create(
                name="Feed Category",
                organization=system_org,
            )
            tag = Tag.objects.create(
                name="Feed Tag",
                organization=system_org,
            )
            post = Post.objects.create(
                title="Feed Post Under RLS",
                author=author_user,
                content="Public System-org content for RLS feed test.",
                status="published",
                category=category,
                organization=system_org,
            )
            post.tags.add(tag)
        finally:
            set_current_org_id(None)

        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ANON_ROLE}")

        try:
            response = client.get(reverse("quickscale_blog:feed"))
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")

        assert response.status_code == 200, (
            f"Expected 200 OK under restricted role, got {response.status_code}. "
            f"Response: {response.content.decode()[:500]}"
        )
        body = response.content.decode()
        assert "Feed Post Under RLS" in body, (
            "Anonymous blog feed under restricted role must return "
            "published System-org content. "
            f"Got: {body[:500]}"
        )
