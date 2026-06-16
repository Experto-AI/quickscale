"""Cross-tenant isolation tests for the blog module.

Phase 14.2 of the roadmap introduces isolation-marker stubs for every tenant
module so that the isolation gap is enumerated per module and wired into
default CI.

The blog module has no ``organization`` FK on its models and exposes only
public non-org-scoped URLs today, so the "Org A cannot read Org B posts"
request-path assertion is not expressible yet.  These tests are placed under
``@pytest.mark.skip`` until Finding 11 structural isolation lands (Phase 11.2)
and this module receives an ``organization`` FK plus org-scoped request paths.

Phase 14.1 applies the shared ``assert_org_scoped_response`` helper to the
blog module so that the same reusable cross-tenant assertion is used across
all tenant modules.  Once the skip is removed, the test will use the shared
helper to validate that an org-scoped blog API response contains only the
requesting org's posts.

Removing the ``skip`` marker is an explicit step of the blog module's F11
rollout slice.
"""

import pytest

from tests_shared.isolation import assert_org_scoped_response


@pytest.mark.isolation
@pytest.mark.skip(
    reason=(
        "blog has no organization FK on its models and no org-scoped request "
        "path today.  The 'Org A cannot see Org B posts' assertion is not "
        "expressible until Finding 11 structural isolation lands (Phase 11.2). "
        "Removing this skip is an explicit step of the blog F11 rollout slice."
    )
)
@pytest.mark.django_db
def test_org_a_cannot_see_org_b_posts(
    org_a,
    org_b,
    org_a_admin,
    client,
):
    """Org A must not be able to read Org B's blog posts via an org-scoped path.

    Intent (once Finding 11 / Phase 11.2 lands):
    1. Create an organization for Org A and an organization for Org B.
    2. Create a ``Post`` owned by Org B (via an ``organization`` FK).
    3. Authenticate as an Org A admin.
    4. Issue a GET request to the org-scoped blog post list endpoint for Org A.
    5. Assert that the response contains no Org B posts (only Org A's rows).

    The shared ``assert_org_scoped_response`` helper validates the status
    code and visible-names isolation in one call, consistent with the CRM
    isolation test (Phase 14.1).

    This test is skipped until the blog module has an ``organization`` FK and
    an org-scoped viewset/URL pattern.
    """
    from quickscale_modules_blog.models import Post

    Post.objects.create(title="Org A Post", slug="org-a-post", author=org_a_admin)
    Post.objects.create(
        title="Org B Post",
        slug="org-b-post",
        author=org_a_admin,  # placeholder — will use org_b_admin once fixtures exist
    )

    client.force_login(org_a_admin)
    response = client.get(f"/orgs/{org_a.slug}/blog/api/posts/")

    # The shared helper validates status 200 + visible-names isolation.
    # In a properly isolated system, only Org A's posts should be visible.
    assert_org_scoped_response(response, expected_names={"Org A Post"})
