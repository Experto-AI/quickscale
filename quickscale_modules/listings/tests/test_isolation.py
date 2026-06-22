"""Cross-tenant isolation tests for the listings module.

Phase F11.12b adds an ``organization`` FK to the ``Listing`` model and
org-scoped URL patterns.  The ``test_org_a_cannot_see_org_b_listings``
test is now active (skip marker removed).  It validates that the org-scoped
listing list returns only the requesting org's listings.
"""

import pytest


@pytest.mark.isolation
@pytest.mark.django_db
def test_org_a_cannot_see_org_b_listings(
    org_a,
    org_b,
    org_a_admin,
    client,
):
    """Org A must not be able to read Org B's listings via an org-scoped path.

    Phase F11.12b:
    1. Create a ``Listing`` owned by Org A and a ``Listing`` owned by Org B.
    2. Authenticate as an Org A admin (member of Org A).
    3. Issue a GET to ``/orgs/<org_a.slug>/listings/`` (org-scoped ListingListView).
    4. Assert that only Org A's listing is visible in the HTML response.
    """
    from quickscale_modules_listings.models import Listing

    Listing.objects.create(
        title="Org A Listing",
        slug="org-a-listing",
        description="Org A description",
        status="published",
        organization=org_a,
    )
    Listing.objects.create(
        title="Org B Listing",
        slug="org-b-listing",
        description="Org B description",
        status="published",
        organization=org_b,
    )

    client.force_login(org_a_admin)
    response = client.get(f"/listings/orgs/{org_a.slug}/")

    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}. "
        f"Response: {response.content.decode()[:500]}"
    )

    html = response.content.decode()
    assert "Org A Listing" in html, "Org A's own listing should be visible"
    assert "Org B Listing" not in html, (
        "Org B's listing must not be visible to Org A. "
        "This confirms the cross-tenant isolation gap (Finding 11)."
    )
