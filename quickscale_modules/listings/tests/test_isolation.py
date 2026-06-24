"""Cross-tenant isolation tests for the listings module.

T1.8: Single-URL contract (D1/D5).  Tenant isolation is enforced by the
``TenantManager`` (ambient ContextVar) and the ``_scope_queryset`` helper
in views.  This test validates that scoping by org context works correctly
via the view layer.
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
    """Org A must not be able to read Org B's listings via the flat listing list.

    T1.8: The flat ``/listings/`` route scopes to the ambient org from the
    ContextVar (set by ``TenantMiddleware``).  Authenticated users see only
    their own org's listings.
    """
    from django.test import RequestFactory
    from django.urls import reverse

    from quickscale_modules_listings.models import Listing
    from quickscale_modules_listings.views import ListingListView

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

    # Set the ambient org context to Org A (bypassing middleware for isolation)
    from quickscale_modules_orgs.current_org import set_current_org_id

    set_current_org_id(org_a.pk)

    factory = RequestFactory()
    url = reverse("quickscale_listings:listing_list")
    request = factory.get(url)
    request.user = org_a_admin

    view = ListingListView.as_view()
    response = view(request)
    response.render()

    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}. "
        f"Response: {response.content.decode()[:500]}"
    )

    html = response.content.decode()
    assert "Org A Listing" in html, "Org A's own listing should be visible"
    assert "Org B Listing" not in html, (
        "Org B's listing must not be visible to Org A. "
        "This confirms the cross-tenant isolation contract."
    )
