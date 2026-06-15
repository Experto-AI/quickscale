"""Cross-tenant isolation tests for the listings module.

Phase 14.2 of the roadmap introduces isolation-marker stubs for every tenant
module so that the isolation gap is enumerated per module and wired into
default CI.

The listings module has no ``organization`` FK on its models and exposes only
public non-org-scoped URLs today, so the "Org A cannot read Org B listings"
request-path assertion is not expressible yet.  These tests are placed under
``@pytest.mark.skip`` until Finding 11 structural isolation lands (Phase 11.2)
and this module receives an ``organization`` FK plus org-scoped request paths.

Removing the ``skip`` marker is an explicit step of the listings module's F11
rollout slice.
"""

import pytest


@pytest.mark.isolation
@pytest.mark.skip(
    reason=(
        "listings has no organization FK on its models and no org-scoped "
        "request path today.  The 'Org A cannot see Org B listings' assertion "
        "is not expressible until Finding 11 structural isolation lands "
        "(Phase 11.2).  Removing this skip is an explicit step of the listings "
        "F11 rollout slice."
    )
)
@pytest.mark.django_db
def test_org_a_cannot_see_org_b_listings():
    """Org A must not be able to read Org B's listings via an org-scoped path.

    Intent (once Finding 11 / Phase 11.2 lands):
    1. Create an organization for Org A and an organization for Org B.
    2. Create a listing owned by Org B (via an ``organization`` FK).
    3. Authenticate as an Org A admin.
    4. Issue a GET request to the org-scoped listing list endpoint for Org A.
    5. Assert that the response contains no Org B listings (only Org A's rows).

    This test is skipped until the listings module has an ``organization`` FK
    and an org-scoped viewset/URL pattern.
    """
    raise AssertionError("Not yet implemented — see skip reason.")
