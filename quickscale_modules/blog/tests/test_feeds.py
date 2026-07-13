"""Tests for blog RSS feed (T1.6: System-org scoped)."""

import pytest
from django.urls import reverse
from quickscale_modules_blog.models import Post


@pytest.mark.django_db
class TestLatestPostsFeed:
    """Tests for RSS feed (System org, D2)"""

    def test_feed_returns_published_posts(
        self, client, author_user, system_org, blog_org_scope
    ):
        """Test feed returns only published posts from the System org."""
        with blog_org_scope(system_org):
            Post.objects.create(
                title="Published Post",
                author=author_user,
                content="Content",
                status="published",
                organization=system_org,
            )
            Post.objects.create(
                title="Draft Post",
                author=author_user,
                content="Content",
                status="draft",
                organization=system_org,
            )

        with blog_org_scope(None):
            response = client.get(reverse("quickscale_blog:feed"))
        assert response.status_code == 200
        assert "Published Post" in str(response.content)
        assert "Draft Post" not in str(response.content)

    def test_feed_returns_only_system_org_posts(
        self, client, author_user, system_org, org, blog_org_scope
    ):
        """Test feed returns only System-org posts, not other org's posts."""
        with blog_org_scope(system_org):
            Post.objects.create(
                title="System Post",
                author=author_user,
                content="Content",
                status="published",
                organization=system_org,
            )
        with blog_org_scope(org):
            Post.objects.create(
                title="Other Org Post",
                author=author_user,
                content="Content",
                status="published",
                organization=org,
            )

        with blog_org_scope(None):
            response = client.get(reverse("quickscale_blog:feed"))

        assert response.status_code == 200
        content = response.content.decode()
        assert "System Post" in content
        assert "Other Org Post" not in content

    def test_feed_handles_published_post_without_author(
        self, client, system_org, blog_org_scope
    ):
        """Test feed renders when a published post has no author"""
        with blog_org_scope(system_org):
            Post.objects.create(
                title="Authorless Post",
                author=None,
                content="Content",
                status="published",
                organization=system_org,
            )

        with blog_org_scope(None):
            response = client.get(reverse("quickscale_blog:feed"))

        assert response.status_code == 200
        assert "Authorless Post" in response.content.decode()
        assert "Unknown author" not in response.content.decode()
