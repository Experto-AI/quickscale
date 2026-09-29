"""PostgreSQL RLS boundary tests for the social module.

These tests verify that ``FORCE ROW LEVEL SECURITY`` on the social tables
enforces organization isolation at the DB layer when
``app.current_org_id`` is set, set to a non-matching value, or unset.

Skipped on non-PostgreSQL databases (SQLite during unit runs).
"""

from __future__ import annotations

import uuid

import pytest
from django.db import connection

from quickscale_modules_orgs.current_org import set_current_org_id
from quickscale_modules_social.models import SocialEmbed, SocialLink

_RESTRICTED_ROLE = "quickscale_rls_test_role"
_SOCIAL_TABLE_BY_MODEL = {
    SocialLink: "quickscale_social_sociallink",
    SocialEmbed: "quickscale_social_socialembed",
}
_SOCIAL_TENANT_MODELS = tuple(_SOCIAL_TABLE_BY_MODEL)
_SOCIAL_URL_BY_MODEL = {
    SocialLink: "https://www.linkedin.com/company/quickscale-rls-boundary/",
    SocialEmbed: "https://www.youtube.com/shorts/quickscaleRls",
}


def _model_id(model: type) -> str:
    """Return the model name as a pytest parameter id."""
    return model.__name__


def _ensure_rls_test_role() -> None:
    """Assert the pre-provisioned RLS test role exists.

    The role must be pre-created by the test harness (the repository's
    PostgreSQL provisioning station).  Raises ``RuntimeError`` with setup
    instructions if it is missing.  Per-table SELECT grants are best-effort
    and wrapped in savepoints so permission-denied failures under a
    non-owner database role do not abort the outer test transaction.
    """
    from django.db import transaction

    with connection.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s",
            [_RESTRICTED_ROLE],
        )
        if cur.fetchone() is None:
            raise RuntimeError(
                f"Pre-provisioned role {_RESTRICTED_ROLE} not found. "
                "Provision the repository's PostgreSQL test roles before "
                "running RLS boundary tests."
            )
        try:
            with transaction.atomic():
                cur.execute(f"GRANT USAGE ON SCHEMA public TO {_RESTRICTED_ROLE}")
        except Exception:
            pass
        for table in _SOCIAL_TABLE_BY_MODEL.values():
            try:
                with transaction.atomic():
                    cur.execute(f"GRANT SELECT ON {table} TO {_RESTRICTED_ROLE}")
            except Exception:
                pass


def _create_item(model: type, *, organization: object, title: str) -> object:
    """Create one social item while its organization's context is active."""
    set_current_org_id(getattr(organization, "id", None))
    try:
        return model.objects.create(
            title=title,
            provider_name="",
            url=_SOCIAL_URL_BY_MODEL[model],
            description=f"{title} description",
            display_order=10,
            is_published=True,
            organization=organization,
        )
    finally:
        set_current_org_id(None)


def _reset_restricted_session(cursor) -> None:
    """Return the connection to the test role and clear the RLS GUCs."""
    cursor.execute("RESET ROLE")
    cursor.execute("RESET app.current_org_id")
    cursor.execute("RESET app.operator_access")


@pytest.mark.django_db(transaction=True)
class TestSocialRlsBoundaryRestrictedRole:
    """RLS boundary proofs under a restricted PostgreSQL role.

    Proves that FORCE RLS on the social tables enforces org isolation when
    ``app.current_org_id`` is set, set to a non-matching value, or unset
    under a non-superuser role.  Skipped on SQLite.
    """

    @pytest.fixture(autouse=True)
    def _skip_if_not_postgres(self) -> None:
        if connection.vendor != "postgresql":
            pytest.skip("RLS boundary testing requires PostgreSQL")

    @pytest.mark.parametrize("model", _SOCIAL_TENANT_MODELS, ids=_model_id)
    def test_restricted_role_sees_nothing_with_non_matching_org_context(
        self, model, org_a, org_b
    ) -> None:
        """A bogus org context returns zero rows (fail-closed at the DB)."""
        _ensure_rls_test_role()
        _create_item(model, organization=org_a, title="Org A Item")
        table = _SOCIAL_TABLE_BY_MODEL[model]

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

    @pytest.mark.parametrize("model", _SOCIAL_TENANT_MODELS, ids=_model_id)
    def test_restricted_role_sees_only_own_org_rows(self, model, org_a, org_b) -> None:
        """With the context set, the restricted role sees only that org's rows."""
        _ensure_rls_test_role()
        _create_item(model, organization=org_a, title="Org A Item")
        _create_item(model, organization=org_b, title="Org B Item")
        table = _SOCIAL_TABLE_BY_MODEL[model]

        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
            try:
                cursor.execute("SET app.current_org_id = %s", [str(org_a.id)])
                cursor.execute(f"SELECT title FROM {table} ORDER BY title")
                titles = [row[0] for row in cursor.fetchall()]
                assert titles == ["Org A Item"], (
                    f"Expected only Org A Item, got {titles}"
                )

                cursor.execute("SET app.current_org_id = %s", [str(org_b.id)])
                cursor.execute(f"SELECT title FROM {table} ORDER BY title")
                titles = [row[0] for row in cursor.fetchall()]
                assert titles == ["Org B Item"], (
                    f"Cross-org: expected only Org B Item, got {titles}"
                )
            finally:
                _reset_restricted_session(cursor)

    @pytest.mark.parametrize("model", _SOCIAL_TENANT_MODELS, ids=_model_id)
    def test_unset_org_context_returns_zero_rows(self, model, org_a) -> None:
        """No org context returns zero rows — fail-closed behavior."""
        _ensure_rls_test_role()
        _create_item(model, organization=org_a, title="Org A Item")
        table = _SOCIAL_TABLE_BY_MODEL[model]

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
