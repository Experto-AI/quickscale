"""Cross-tenant isolation tests for the blog module (T1.6 flat-route contract).

With the single flat URL tree (D1), org scoping is now ambient via
TenantManager auto-scoping on the ContextVar.  Anonymous/public reads
are scoped to System org (D2).  Authenticated reads use the active org
set by TenantMiddleware.

Isolation is verified by:
1. Setting the contextvar explicitly to simulate a specific org context.
2. Verifying that queries through the default manager only return that
   org's rows.
3. Verifying that the operator escape hatch (all_objects) bypasses
   scoping.
"""

import pytest
from quickscale_modules_blog.models import Post


@pytest.mark.isolation
@pytest.mark.django_db
def test_org_a_cannot_see_org_b_posts(
    org_a,
    org_b,
    org_a_admin,
):
    """Org A must not be able to read Org B's blog posts via TenantManager scoping.

    With the single flat URL tree and TenantManager auto-scoping,
    setting the contextvar to Org A's ID should only return Org A's
    posts.  Org B's posts must be invisible.
    """
    from quickscale_modules_orgs.current_org import (
        reset_current_org_id,
        set_current_org_id,
    )

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

    # Scope to Org A — only Org A's post should be visible.
    set_current_org_id(org_a.pk)
    try:
        posts = list(
            Post.objects.filter(status="published").values_list("title", flat=True)
        )
        assert "Org A Post" in posts
        assert "Org B Post" not in posts, (
            "Org B's post must not be visible when scoped to Org A"
        )
    finally:
        reset_current_org_id()


@pytest.mark.isolation
@pytest.mark.django_db
def test_operator_bypass_returns_all_orgs_posts(
    org_a,
    org_b,
    org_a_admin,
):
    """The operator escape hatch (all_objects) must return posts from all orgs."""
    Post.objects.create(
        title="Org A Post",
        slug="org-a-post-operator",
        author=org_a_admin,
        content="Org A content",
        status="published",
        organization=org_a,
    )
    Post.objects.create(
        title="Org B Post",
        slug="org-b-post-operator",
        author=org_a_admin,
        content="Org B content",
        status="published",
        organization=org_b,
    )

    titles = list(
        Post.all_objects.filter(status="published").values_list("title", flat=True)
    )
    assert "Org A Post" in titles
    assert "Org B Post" in titles
