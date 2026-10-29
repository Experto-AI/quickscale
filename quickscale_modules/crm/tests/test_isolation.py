"""Cross-tenant isolation tests for the CRM module.

CRM tenant tables carry a NOT NULL organization FK.  ``TenantManager``
scoping and PostgreSQL FORCE RLS isolate one organization's rows from
another's on every org-scoped read path.  These tests prove that a request
scoped to one organization returns only that organization's rows and that
the operator escape hatch still exposes every organization.

``test_restricted_role_authenticated_list_view`` exercises the full Django
request path under the NOBYPASSRLS runtime role without presetting the GUC.
The connection-layer execute wrapper primes ``app.current_org_id`` from the
ContextVar; without it, every RLS-gated query returns zero rows.
"""

import pytest
from django.db import connection as dj_connection
from quickscale_modules_orgs._constants import ACTIVE_ORG_SESSION_KEY
from tests_shared.isolation import assert_org_scoped_response

# ---------------------------------------------------------------------------
# Restricted-role helpers (isolation-conformance CI job)
# ---------------------------------------------------------------------------

_RESTRICTED_ROLE = "quickscale_rls_test_role"
_CRM_TABLES = (
    "quickscale_crm_tag",
    "quickscale_crm_company",
    "quickscale_crm_contact",
    "quickscale_crm_stage",
    "quickscale_crm_deal",
    "quickscale_crm_contactnote",
    "quickscale_crm_dealnote",
)
_SYSTEM_TABLES = (
    "auth_user",
    "auth_group",
    "auth_group_permissions",
    "auth_user_groups",
    "auth_user_user_permissions",
    "auth_permission",
    "django_content_type",
    "django_session",
    "django_migrations",
)
_ORGS_TABLES = (
    "quickscale_orgs_organization",
    "quickscale_orgs_organizationmembership",
)


def _ensure_rls_test_role_with_grants() -> None:
    """Assert the pre-provisioned RLS test role exists and issue grants.

    The role must be pre-created by the test harness
    (``scripts/provision_test_roles.sh`` or equivalent).  Raises
    ``RuntimeError`` with setup instructions if missing.  Per-table
    grants are still issued here (idempotent, requires table existence
    post-migration).

    This is a broader version of the per-module ``_ensure_rls_test_role``
    helpers — it grants ALL on CRM tenant tables and orgs infrastructure
    tables (needed for ``ensure_org_default_stages`` locking and stage
    seeding), and SELECT on system Django tables (auth, sessions, content
    types), so that the full Django request pipeline passes under
    ``SET ROLE``.
    """
    import psycopg2

    db = dj_connection.settings_dict
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
                    f"running isolation-conformance tests."
                )
            cur.execute(f"GRANT USAGE ON SCHEMA public TO {_RESTRICTED_ROLE}")
            for table in _CRM_TABLES:
                cur.execute(f"GRANT ALL ON {table} TO {_RESTRICTED_ROLE}")
            for table in _SYSTEM_TABLES:
                cur.execute(f"GRANT SELECT ON {table} TO {_RESTRICTED_ROLE}")
            for table in _ORGS_TABLES:
                cur.execute(f"GRANT ALL ON {table} TO {_RESTRICTED_ROLE}")
    finally:
        conn.close()


def _activate_org_in_session(client, organization):
    """Set the active org in the client session for TenantMiddleware."""
    session = client.session
    session[ACTIVE_ORG_SESSION_KEY] = str(organization.id)
    session.save()


@pytest.mark.isolation
@pytest.mark.django_db
class TestCRMCrossTenantIsolation:
    """Cross-tenant isolation assertions for CRM tenant data.

    These tests confirm that one organization's data is not visible to
    another organization through the org-scoped request path.
    """

    def test_org_a_request_returns_200(
        self,
        org_a,
        org_a_admin,
        client,
    ):
        """A request scoped to Org A returns 200 for an org admin.

        This assertion validates that the org-scoped CRM API request path,
        TenantMiddleware, and authentication all function correctly.  A
        failure indicates a request-path or auth regression.
        """
        from quickscale_modules_crm.models import Company
        from quickscale_modules_orgs.current_org import set_current_org_id

        # Prime the org context so FORCE RLS allows the INSERT under the
        # NOBYPASSRLS restricted role.
        set_current_org_id(org_a.id)
        try:
            Company.objects.create(
                name="Org A Corp", industry="Technology", organization=org_a
            )
        finally:
            set_current_org_id(None)

        client.force_login(org_a_admin)
        _activate_org_in_session(client, org_a)
        response = client.get("/crm/api/companies/")

        assert response.status_code == 200, (
            f"Expected 200 OK, got {response.status_code}. "
            f"Response: {response.content.decode()[:200]}"
        )

    def test_org_a_cannot_see_org_b_companies(
        self,
        org_a,
        org_b,
        org_a_admin,
        client,
    ):
        """A request scoped to Org A must not return Org B's companies.

        ``OrgScopedReadMixin`` scopes the view to the active organization on
        org-scoped SaaS routes, so the test exercises the real request path
        through TenantMiddleware rather than a bare ORM query.  Only the
        cross-tenant data assertion is tested here; the request-path, auth,
        status, and response-shape checks are in
        ``test_org_a_request_returns_200`` and fail normally.
        """
        from quickscale_modules_crm.models import Company
        from quickscale_modules_orgs.current_org import set_current_org_id

        # Prime the org context so FORCE RLS allows INSERTs under the
        # NOBYPASSRLS restricted role.
        set_current_org_id(org_a.id)
        try:
            Company.objects.create(
                name="Org A Corp", industry="Technology", organization=org_a
            )
        finally:
            set_current_org_id(None)
        set_current_org_id(org_b.id)
        try:
            Company.objects.create(
                name="Org B Corp", industry="Finance", organization=org_b
            )
        finally:
            set_current_org_id(None)

        client.force_login(org_a_admin)
        _activate_org_in_session(client, org_a)
        response = client.get("/crm/api/companies/")

        # The shared helper validates status 200 + visible-names isolation.
        # In a properly isolated system, only Org A's companies should be visible.
        assert_org_scoped_response(response, expected_names={"Org A Corp"})

    @pytest.mark.isolation
    @pytest.mark.django_db(transaction=True)
    def test_restricted_role_authenticated_list_view(
        self,
        org_a,
        org_a_admin,
        client,
    ):
        """Authenticated list view under restricted role returns owner's rows.

        Exercises the full Django request pipeline (middleware, auth, view,
        serializer, ORM) under the NOBYPASSRLS runtime role without
        presetting the GUC.  Without the connection-layer execute wrapper
        that issues ``SET LOCAL app.current_org_id`` from the ContextVar,
        every RLS-gated query returns zero rows; this is the red-green proof
        that the wrapper is installed.
        """
        from quickscale_modules_crm.models import Company
        from quickscale_modules_crm.services import ensure_org_default_stages
        from quickscale_modules_orgs.current_org import set_current_org_id
        from django.db import connection

        _ensure_rls_test_role_with_grants()

        # Prime the org context so FORCE RLS allows INSERTs under the
        # NOBYPASSRLS restricted role.
        set_current_org_id(org_a.id)
        try:
            Company.objects.create(
                name="Org A Corp", industry="Technology", organization=org_a
            )
        finally:
            set_current_org_id(None)

        client.force_login(org_a_admin)
        _activate_org_in_session(client, org_a)

        # Seed default stages before SET ROLE.  Prime the org context so
        # FORCE RLS allows the INSERT under the NOBYPASSRLS role.
        set_current_org_id(org_a.id)
        try:
            ensure_org_default_stages(org_a)
        finally:
            set_current_org_id(None)

        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")

        try:
            response = client.get("/crm/api/companies/")
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")

        assert response.status_code == 200, (
            f"Expected 200 OK under restricted role, got {response.status_code}. "
            f"Response: {response.content.decode()[:200]}"
        )
        assert_org_scoped_response(response, expected_names={"Org A Corp"})
