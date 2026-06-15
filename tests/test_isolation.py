"""Cross-tenant isolation tests for the forms module.

Phase 14.2 of the roadmap introduces isolation-marker stubs for every tenant
module so that the isolation gap is enumerated per module and wired into
default CI.

The forms module has no ``organization`` FK on its models and exposes only
public non-org-scoped URLs today, so the "Org A cannot read Org B form
submissions" request-path assertion is not expressible yet.  These tests are
placed under ``@pytest.mark.skip`` until Finding 11 structural isolation lands
(Phase 11.2) and this module receives an ``organization`` FK plus org-scoped
request paths.

Removing the ``skip`` marker is an explicit step of the forms module's F11
rollout slice.
"""

import pytest


@pytest.mark.isolation
@pytest.mark.skip(
    reason=(
        "forms has no organization FK on its models and no org-scoped request "
        "path today.  The 'Org A cannot see Org B form submissions' assertion "
        "is not expressible until Finding 11 structural isolation lands "
        "(Phase 11.2).  Removing this skip is an explicit step of the forms "
        "F11 rollout slice."
    )
)
@pytest.mark.django_db
def test_org_a_cannot_see_org_b_form_submissions():
    """Org A must not be able to read Org B's form submissions via an org-scoped path.

    Intent (once Finding 11 / Phase 11.2 lands):
    1. Create an organization for Org A and an organization for Org B.
    2. Create a form submission owned by Org B (via an ``organization`` FK).
    3. Authenticate as an Org A admin.
    4. Issue a GET request to the org-scoped form submission list endpoint for Org A.
    5. Assert that the response contains no Org B submissions (only Org A's rows).

    This test is skipped until the forms module has an ``organization`` FK and
    an org-scoped viewset/URL pattern.
    """
    raise AssertionError("Not yet implemented — see skip reason.")
