"""Cross-tenant isolation tests for the CRM module.

Phase 14.1 of the roadmap introduces this harness to make the current
cross-tenant data leak observable and verifiable.  CRM models have no
``organization`` FK and CRM viewsets query ``Model.objects.all()`` with no
tenant scoping, so data from one organization is visible to every other
organization today.  These tests document that failure.

The ``xfail(strict=True)`` marker is applied only to the cross-tenant leak
assertion itself.  Request-path, authentication, status-code, and
response-shape regressions fail normally so that infrastructure breakage is
never masked by the expected-failure marker.  Once structural isolation is
in place (Finding 11), the marker removal becomes an explicit part of the
F11 rollout.

F11.5 Phase 1 + 2 update: Primary resource read paths (Tag, Company, Contact,
Stage, Deal, ContactNote, DealNote) are now org-scoped via OrgScopedReadMixin
on org-scoped SaaS routes.  Dashboard aggregate/recent queries and serializer
helper queries (counts, tag names) are also org-scoped.  The cross-tenant
leak for the tested path (company list) is now fixed, so the xfail marker
has been removed.  Remaining seams (bulk actions, admin/operator paths) are
out of scope for F11.5.
"""

import pytest
from quickscale_modules_orgs.constants import ACTIVE_ORG_SESSION_KEY
from tests_shared.isolation import assert_org_scoped_response


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
    another organization.  The cross-tenant leak assertion is expected to
    fail today because CRM models lack an ``organization`` FK and viewsets
    use unscoped ``Model.objects.all()`` queries (Finding 11 / Phase 14.1).
    """

    def test_org_a_request_returns_200(
        self,
        org_a,
        org_a_admin,
        client,
    ):
        """A request scoped to Org A returns 200 for an org admin.

        This assertion is NOT expected to fail.  It validates that the
        org-scoped CRM API request path, TenantMiddleware, and
        authentication all function correctly.  If this fails, it indicates
        a request-path or auth regression — not the cross-tenant leak.
        """
        from quickscale_modules_crm.models import Company

        Company.objects.create(
            name="Org A Corp", industry="Technology", organization=org_a
        )

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

        F11.5 Phase 1 + 2: This assertion now passes because CompanyViewSet
        uses OrgScopedReadMixin to scope queries to the active organization
        on org-scoped SaaS routes.  The xfail marker has been removed to
        reflect the fixed seam state.

        The test exercises a real org-scoped request path through
        TenantMiddleware, so the assertion validates the full request seam
        rather than a bare ORM query.

        Only the cross-tenant data assertion is tested here.  The
        request-path, auth, status, and response-shape checks are in
        ``test_org_a_request_returns_200`` and fail normally.
        """
        from quickscale_modules_crm.models import Company

        Company.objects.create(
            name="Org A Corp", industry="Technology", organization=org_a
        )
        Company.objects.create(
            name="Org B Corp", industry="Finance", organization=org_b
        )

        client.force_login(org_a_admin)
        _activate_org_in_session(client, org_a)
        response = client.get("/crm/api/companies/")

        # The shared helper validates status 200 + visible-names isolation.
        # In a properly isolated system, only Org A's companies should be visible.
        assert_org_scoped_response(response, expected_names={"Org A Corp"})
