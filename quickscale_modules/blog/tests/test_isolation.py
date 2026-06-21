"""Cross-tenant isolation tests for the blog module.

Phase 2 (F11.11) delivers org-scoped URL patterns and view isolation.
The ``test_org_a_cannot_see_org_b_posts`` test is now active (skip marker
removed).  It validates that the org-scoped post list (HTML) returns only
the requesting org's posts.

The test uses the HTML ``PostListView`` at ``/orgs/<slug>/blog/`` and checks
response content directly since the blog module uses template views rather
than JSON API endpoints for list rendering.  AuthorProfile is global and
not org-scoped, consistent with the Phase 2 plan.
"""

import pytest


@pytest.mark.isolation
@pytest.mark.django_db
def test_org_a_cannot_see_org_b_posts(
    org_a,
    org_b,
    org_a_admin,
    client,
):
    """Org A must not be able to read Org B's blog posts via an org-scoped path.

    Phase 2 (F11.11):
    1. Create a ``Post`` owned by Org A and a ``Post`` owned by Org B.
    2. Authenticate as an Org A admin (member of Org A).
    3. Issue a GET to ``/orgs/<org_a.slug>/blog/`` (org-scoped PostListView).
    4. Assert that only Org A's post is visible in the HTML response.
    """
    from quickscale_modules_blog.models import Post

    Post.objects.create(
        title="Org A Post",
        slug="org-a-post",
        author=org_a_admin,
        content="Org A content",
        status="published",
        organization=org_a,
    )
    Post.objects.create(
        title="Org B Post",
        slug="org-b-post",
        author=org_a_admin,
        content="Org B content",
        status="published",
        organization=org_b,
    )

    client.force_login(org_a_admin)
    response = client.get(f"/orgs/{org_a.slug}/blog/")

    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}. "
        f"Response: {response.content.decode()[:500]}"
    )

    html = response.content.decode()
    assert "Org A Post" in html, "Org A's own post should be visible"
    assert "Org B Post" not in html, (
        "Org B's post must not be visible to Org A. "
        "This confirms the cross-tenant isolation gap (Finding 11)."
    )
