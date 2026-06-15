"""Cross-tenant isolation tests for the social module.

Phase 14.2 of the roadmap introduces isolation-marker stubs for every tenant
module so that the isolation gap is enumerated per module and wired into
default CI.

The social module is model-only (it exposes no URLs) and has no ``organization``
FK on its models today, so the "Org A cannot read Org B social links"
assertion is not expressible yet.  These tests are placed under
``@pytest.mark.skip`` until Finding 11 structural isolation lands (Phase 11.2)
and this module receives an ``organization`` FK plus org-scoped request paths.

Removing the ``skip`` marker is an explicit step of the social module's F11
rollout slice.
"""

import pytest


@pytest.mark.isolation
@pytest.mark.skip(
    reason=(
        "social is a model-only module with no organization FK and no "
        "org-scoped request path today.  The 'Org A cannot see Org B social "
        "links' assertion is not expressible until Finding 11 structural "
        "isolation lands (Phase 11.2).  Removing this skip is an explicit "
        "step of the social F11 rollout slice."
    )
)
@pytest.mark.django_db
def test_org_a_cannot_see_org_b_social_links():
    """Org A must not be able to read Org B's social links via an org-scoped path.

    Intent (once Finding 11 / Phase 11.2 lands):
    1. Create an organization for Org A and an organization for Org B.
    2. Create a social link owned by Org B (via an ``organization`` FK).
    3. Authenticate as an Org A admin.
    4. Issue a GET request to the org-scoped social link list endpoint for Org A.
    5. Assert that the response contains no Org B social links (only Org A's rows).

    This test is skipped until the social module has an ``organization`` FK and
    an org-scoped viewset/URL pattern.
    """
    raise AssertionError("Not yet implemented — see skip reason.")
