"""Cross-tenant isolation tests for the CRM module.

Phase 14.1 of the roadmap introduces this harness to make the current
cross-tenant data leak observable and verifiable.  CRM models have no
``organization`` FK and CRM viewsets query ``Model.objects.all()`` with no
tenant scoping, so data from one organization is visible to every other
organization today.  These tests document that failure.

The ``xfail(strict=True)`` markers ensure the tests report XPASS (and
therefore fail the suite) once structural isolation is in place, so the
marker removal becomes an explicit part of the F11 rollout.
"""

import pytest


@pytest.mark.isolation
@pytest.mark.django_db
class TestCRMCrossTenantIsolation:
    """Cross-tenant isolation assertions for CRM tenant data.

    These tests confirm that one organization's data is not visible to
    another organization.  They are expected to fail today because CRM
    models lack an ``organization`` FK and viewsets use unscoped
    ``Model.objects.all()`` queries (Finding 11 / Phase 14.1).
    """

    @pytest.mark.xfail(
        reason=(
            "CRM models have no organization FK and querysets are not "
            "tenant-scoped.  Confirm cross-tenant leak exists (Phase 14.1). "
            "Remove xfail once Finding 11 structural isolation lands."
        ),
        strict=True,
    )
    def test_org_a_cannot_see_org_b_companies(
        self,
        org_a,
        org_b,
        org_a_admin,
        client,
    ):
        """A request scoped to Org A must not return Org B's companies.

        This assertion fails today because ``Company.objects.all()`` returns
        every company regardless of the requesting organization.  The failure
        is the expected outcome for Phase 14.1 — it proves the isolation gap
        exists and gives F11 a concrete pass/fail target.

        The test exercises a real org-scoped request path through
        TenantMiddleware, so the assertion validates the full request seam
        rather than a bare ORM query.
        """
        from quickscale_modules_crm.models import Company

        Company.objects.create(name="Org A Corp", industry="Technology")
        Company.objects.create(name="Org B Corp", industry="Finance")

        # Authenticate as Org A admin (who is also staff for CRM API access)
        client.force_login(org_a_admin)

        # Make a real request through the org-scoped CRM API path
        # The URL pattern /orgs/<org_slug>/crm/api/companies/ exercises
        # TenantMiddleware which extracts org_slug from the URL
        response = client.get(f"/orgs/{org_a.slug}/crm/api/companies/")

        assert response.status_code == 200, (
            f"Expected 200 OK, got {response.status_code}. "
            f"Response: {response.content.decode()[:200]}"
        )

        # Extract company names from the API response
        visible_companies = response.json()
        visible_names = {company["name"] for company in visible_companies}

        # In a properly isolated system, only Org A's companies should be visible
        assert visible_names == {"Org A Corp"}, (
            f"Expected only Org A Corp, but got {visible_names}. "
            "This confirms the cross-tenant isolation gap (Finding 11)."
        )
