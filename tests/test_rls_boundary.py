"""PostgreSQL RLS boundary tests for the Forms module.

T1.13 — DB-level RLS isolation proof under a restricted PostgreSQL role.

These tests verify that ``FORCE ROW LEVEL SECURITY`` on all four Forms tenant
tables correctly enforces org isolation at the DB layer when
``app.current_org_id`` is set, set to a non-matching value, or unset.

Skipped on non-PostgreSQL databases (SQLite during CI unit tests).
"""

from __future__ import annotations

import uuid

import pytest
from django.db import connection

from quickscale_modules_forms.models import (
    Form,
    FormField,
    FormFieldValue,
    FormSubmission,
)

# ---------------------------------------------------------------------------
# Restricted role helpers (mirror the social module pattern)
# ---------------------------------------------------------------------------

_RESTRICTED_ROLE = "quickscale_rls_test_role"
_FORMS_TABLE_BY_MODEL = {
    Form: "quickscale_forms_form",
    FormField: "quickscale_forms_formfield",
    FormSubmission: "quickscale_forms_formsubmission",
    FormFieldValue: "quickscale_forms_formfieldvalue",
}
_FORMS_TENANT_MODELS = tuple(_FORMS_TABLE_BY_MODEL)
_FORMS_TABLES = tuple(_FORMS_TABLE_BY_MODEL.values())


def _model_id(model: type) -> str:
    """Return the model name as a pytest parameter id."""
    return model.__name__


def _ensure_rls_test_role() -> None:
    """Assert the pre-provisioned RLS test role exists.

    The role must be pre-created by the test harness
    (``scripts/provision_test_roles.sh`` or equivalent).  Raises
    ``RuntimeError`` with setup instructions if missing.  Per-table
    SELECT grants are still issued here (idempotent, requires table
    existence post-migration).

    Converted from ``psycopg2`` direct connection to Django's
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
        # transaction.
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


def _create_tenant_row(model: type, *, organization: object, suffix: str) -> object:
    """Create one row of *model* with its parents under the org context."""
    from quickscale_modules_orgs.current_org import set_current_org_id

    set_current_org_id(organization.id)
    try:
        form = Form.objects.create(
            title=f"{suffix} Form",
            slug=f"{suffix}-form-{organization.slug}",
            organization=organization,
        )
        if model is Form:
            return form
        field = FormField.objects.create(
            form=form,
            field_type=FormField.FieldType.TEXT,
            label=f"{suffix} Field",
            name=f"{suffix}-field",
            order=1,
            organization=organization,
        )
        if model is FormField:
            return field
        submission = FormSubmission.objects.create(
            form=form,
            organization=organization,
        )
        if model is FormSubmission:
            return submission
        return FormFieldValue.objects.create(
            submission=submission,
            field=field,
            field_name=field.name,
            field_label=field.label,
            value=f"{suffix} value",
            organization=organization,
        )
    finally:
        set_current_org_id(None)


def _reset_restricted_session(cursor) -> None:
    """Return the connection to the test role and clear the RLS GUCs."""
    cursor.execute("RESET ROLE")
    cursor.execute("RESET app.current_org_id")
    cursor.execute("RESET app.operator_access")


# ---------------------------------------------------------------------------
# Boundary tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestFormsRlsBoundaryRestrictedRole:
    """RLS boundary tests under a restricted PostgreSQL role (T1.13).

    Proves that FORCE RLS on every Forms tenant table correctly enforces org
    isolation when ``app.current_org_id`` is set, set to a non-matching value,
    or unset under a non-superuser role.

    Skipped on SQLite.
    """

    @pytest.fixture(autouse=True)
    def _skip_if_not_postgres(self) -> None:
        if connection.vendor != "postgresql":
            pytest.skip("RLS boundary testing requires PostgreSQL")

    @pytest.mark.parametrize("model", _FORMS_TENANT_MODELS, ids=_model_id)
    def test_restricted_role_sees_nothing_with_non_matching_org_context(
        self, model, org_a
    ) -> None:
        """A bogus org context returns zero rows on every tenant table."""
        _ensure_rls_test_role()
        _create_tenant_row(model, organization=org_a, suffix="org-a")
        table = _FORMS_TABLE_BY_MODEL[model]

        bogus_org = uuid.uuid4()
        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
            try:
                cursor.execute("SET app.current_org_id = %s", [str(bogus_org)])
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                (count,) = cursor.fetchone()
                assert count == 0, (
                    f"RLS should block all {table} rows with a non-matching org context"
                )
            finally:
                _reset_restricted_session(cursor)

    @pytest.mark.parametrize("model", _FORMS_TENANT_MODELS, ids=_model_id)
    def test_restricted_role_sees_only_own_org_rows(self, model, org_a, org_b) -> None:
        """With the context set, the restricted role sees only that org's row."""
        _ensure_rls_test_role()
        _create_tenant_row(model, organization=org_a, suffix="org-a")
        _create_tenant_row(model, organization=org_b, suffix="org-b")
        table = _FORMS_TABLE_BY_MODEL[model]

        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
            try:
                for organization in (org_a, org_b):
                    cursor.execute(
                        "SET app.current_org_id = %s", [str(organization.id)]
                    )
                    cursor.execute(
                        f"SELECT organization_id FROM {table} ORDER BY organization_id"
                    )
                    org_ids = [str(row[0]) for row in cursor.fetchall()]
                    assert org_ids == [str(organization.id)], (
                        f"Cross-org: expected only {organization.slug} rows in "
                        f"{table}, got {org_ids}"
                    )
            finally:
                _reset_restricted_session(cursor)

    @pytest.mark.parametrize("model", _FORMS_TENANT_MODELS, ids=_model_id)
    def test_unset_org_context_returns_zero_rows(self, model, org_a) -> None:
        """No org context returns zero rows on every tenant table."""
        _ensure_rls_test_role()
        _create_tenant_row(model, organization=org_a, suffix="org-a")
        table = _FORMS_TABLE_BY_MODEL[model]

        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
            try:
                cursor.execute("RESET app.current_org_id")
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                (count,) = cursor.fetchone()
                assert count == 0, (
                    f"RLS should block all {table} rows when the org context is "
                    "unset (fail-closed)"
                )
            finally:
                _reset_restricted_session(cursor)
