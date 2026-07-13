"""PostgreSQL RLS boundary tests for the Forms module.

T1.13 — DB-level RLS isolation proof under a restricted PostgreSQL role.

These tests verify that ``FORCE ROW LEVEL SECURITY`` on the Form table
correctly enforces org isolation at the DB layer when
``app.current_org_id`` is set / unset.

Skipped on non-PostgreSQL databases (SQLite during CI unit tests).
"""

from __future__ import annotations

import uuid

import pytest
from django.db import connection

from quickscale_modules_forms.models import Form

# ---------------------------------------------------------------------------
# Restricted role helpers (mirror the social module pattern)
# ---------------------------------------------------------------------------

_RESTRICTED_ROLE = "quickscale_rls_test_role"
_FORMS_TABLES = (
    "quickscale_modules_forms_form",
    "quickscale_modules_forms_formfield",
    "quickscale_modules_forms_formsubmission",
    "quickscale_modules_forms_formfieldvalue",
)


def _ensure_rls_test_role() -> None:
    """Assert the pre-provisioned RLS test role exists (SA59.3, SA77).

    The role must be pre-created by the test harness
    (``scripts/provision_test_roles.sh`` or equivalent).  Raises
    ``RuntimeError`` with setup instructions if missing.  Per-table
    SELECT grants are still issued here (idempotent, requires table
    existence post-migration).

    SA77: converted from ``psycopg2`` direct connection to Django's
    managed ``connection.cursor()`` so the helper works under
    restricted-role (NOBYPASSRLS) environments where a separate
    psycopg2 connection may fail or misbehave.  Best-effort GRANTs
    are wrapped in savepoints (``transaction.atomic()``) so
    permission-denied failures under a non-owner database role do
    not abort the outer test transaction.
    """
    from django.db import connection, transaction

    with connection.cursor() as cur:
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
        # Best-effort grants wrapped in savepoints so permission-denied
        # failures under NOBYPASSRLS do not abort the outer test
        # transaction (SA77).
        try:
            with transaction.atomic():
                cur.execute(f"GRANT USAGE ON SCHEMA public TO {_RESTRICTED_ROLE}")
        except Exception:
            pass
        for table in _FORMS_TABLES:
            try:
                with transaction.atomic():
                    cur.execute(f"GRANT SELECT ON {table} TO {_RESTRICTED_ROLE}")
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Boundary tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestFormsRlsBoundaryRestrictedRole:
    """RLS boundary tests under a restricted PostgreSQL role (T1.13).

    Proves that FORCE RLS on the Form table correctly enforces org isolation
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
        rows on the Form table (fail-closed at the DB level)."""
        _ensure_rls_test_role()

        from quickscale_modules_orgs.current_org import set_current_org_id

        set_current_org_id(org_a.id)
        try:
            Form.objects.create(
                title="Org A Form",
                slug="org-a-form",
                organization=org_a,
            )
        finally:
            set_current_org_id(None)

        bogus_org = uuid.uuid4()
        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
            try:
                cursor.execute("SET app.current_org_id = %s", [str(bogus_org)])
                cursor.execute("SELECT COUNT(*) FROM quickscale_modules_forms_form")
                (count,) = cursor.fetchone()
                assert count == 0, (
                    "RLS should block all forms with a non-matching org context"
                )
            finally:
                cursor.execute("RESET ROLE")
                cursor.execute("RESET app.current_org_id")
                cursor.execute("RESET app.operator_access")

    def test_restricted_role_sees_only_own_org_forms(self, org_a, org_b) -> None:
        """With ``app.current_org_id`` set, a restricted role sees only the
        owning org's forms and cannot see another org's forms."""
        _ensure_rls_test_role()

        from quickscale_modules_orgs.current_org import set_current_org_id

        set_current_org_id(org_a.id)
        try:
            Form.objects.create(
                title="Org A Form",
                slug="org-a-form",
                organization=org_a,
            )
        finally:
            set_current_org_id(None)

        set_current_org_id(org_b.id)
        try:
            Form.objects.create(
                title="Org B Form",
                slug="org-b-form",
                organization=org_b,
            )
        finally:
            set_current_org_id(None)

        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
            try:
                cursor.execute("SET app.current_org_id = %s", [str(org_a.id)])
                cursor.execute(
                    "SELECT title FROM quickscale_modules_forms_form ORDER BY title"
                )
                titles = [r[0] for r in cursor.fetchall()]
                assert titles == ["Org A Form"], (
                    f"Expected only Org A Form, got {titles}"
                )

                cursor.execute("SET app.current_org_id = %s", [str(org_b.id)])
                cursor.execute(
                    "SELECT title FROM quickscale_modules_forms_form ORDER BY title"
                )
                titles = [r[0] for r in cursor.fetchall()]
                assert titles == ["Org B Form"], (
                    f"Cross-org: expected only Org B Form, got {titles}"
                )
            finally:
                cursor.execute("RESET ROLE")
                cursor.execute("RESET app.current_org_id")
                cursor.execute("RESET app.operator_access")

    def test_unset_org_context_returns_zero_rows(self, org_a) -> None:
        """With no ``app.current_org_id`` set (NULL from current_setting), RLS
        returns zero rows — fail-closed behavior."""
        _ensure_rls_test_role()

        from quickscale_modules_orgs.current_org import set_current_org_id

        set_current_org_id(org_a.id)
        try:
            Form.objects.create(
                title="Org A Form",
                slug="org-a-form",
                organization=org_a,
            )
        finally:
            set_current_org_id(None)

        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
            try:
                cursor.execute("RESET app.current_org_id")
                cursor.execute("SELECT COUNT(*) FROM quickscale_modules_forms_form")
                (count,) = cursor.fetchone()
                assert count == 0, (
                    "RLS should block all forms when org context is unset (fail-closed)"
                )
            finally:
                cursor.execute("RESET ROLE")
                cursor.execute("RESET app.current_org_id")
                cursor.execute("RESET app.operator_access")
