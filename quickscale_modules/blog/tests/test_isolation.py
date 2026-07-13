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
    blog_org_scope,
):
    """Org A must not be able to read Org B's blog posts via TenantManager scoping.

    With the single flat URL tree and TenantManager auto-scoping,
    setting the contextvar to Org A's ID should only return Org A's
    posts.  Org B's posts must be invisible.
    """
    with blog_org_scope(org_a):
        Post.objects.create(
            title="Org A Post",
            slug="org-a-post",
            author=org_a_admin,
            content="Org A content",
            status="published",
            organization=org_a,
        )
    with blog_org_scope(org_b):
        Post.objects.create(
            title="Org B Post",
            slug="org-b-post",
            author=org_a_admin,
            content="Org B content",
            status="published",
            organization=org_b,
        )

    # Scope to Org A — only Org A's post should be visible.
    with blog_org_scope(org_a):
        posts = list(
            Post.objects.filter(status="published").values_list("title", flat=True)
        )
    assert "Org A Post" in posts
    assert "Org B Post" not in posts, (
        "Org B's post must not be visible when scoped to Org A"
    )


@pytest.mark.isolation
@pytest.mark.django_db(transaction=True)
def test_operator_bypass_returns_all_orgs_posts(
    org_a,
    org_b,
    org_a_admin,
    blog_org_scope,
):
    """``all_objects`` returns rows from all organisations when the
    cross-tenant SELECT is elevated via ``operator_access()``.

    ``all_objects`` (``super_scope=True``) bypasses the ORM-level
    ``TenantManager`` filtering but does NOT bypass PostgreSQL
    FORCE RLS.  ``operator_access()`` inside ``transaction.atomic()``
    authorises the DB-level SELECT so rows from multiple organisations
    are visible.  No writes occur inside the operator block.
    """
    from quickscale_modules_orgs.current_org import operator_access
    from django.db import transaction

    with transaction.atomic():
        with blog_org_scope(org_a):
            Post.objects.create(
                title="Org A Post",
                slug="org-a-post-operator",
                author=org_a_admin,
                content="Org A content",
                status="published",
                organization=org_a,
            )
        with blog_org_scope(org_b):
            Post.objects.create(
                title="Org B Post",
                slug="org-b-post-operator",
                author=org_a_admin,
                content="Org B content",
                status="published",
                organization=org_b,
            )

        with operator_access(
            reason="SA83 blog restricted-role cross-tenant SELECT proof"
        ):
            titles = list(
                Post.all_objects.filter(status="published").values_list(
                    "title", flat=True
                )
            )
    assert "Org A Post" in titles
    assert "Org B Post" in titles
