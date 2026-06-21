"""Tests for blog RSS feeds

Phase 2 (F11.11) adds org-scoped feed tests for ``LatestPostsFeedOrgScoped``.
"""

import pytest
from django.urls import reverse
from quickscale_modules_blog.models import Post


@pytest.mark.django_db
class TestLatestPostsFeed:
    """Tests for flat (solo) RSS feed"""

    def test_feed_returns_published_posts(self, client, author_user):
        """Test feed returns only published posts"""
        Post.objects.create(
            title="Published Post",
            author=author_user,
            content="Content",
            status="published",
        )
        Post.objects.create(
            title="Draft Post",
            author=author_user,
            content="Content",
            status="draft",
        )

        response = client.get(reverse("quickscale_blog:feed"))
        assert response.status_code == 200
        assert "Published Post" in str(response.content)
        assert "Draft Post" not in str(response.content)

    def test_feed_handles_published_post_without_author(self, client):
        """Test feed renders when a published post has no author"""
        Post.objects.create(
            title="Authorless Post",
            author=None,
            content="Content",
            status="published",
        )

        response = client.get(reverse("quickscale_blog:feed"))

        assert response.status_code == 200
        assert "Authorless Post" in response.content.decode()
        assert "Unknown author" not in response.content.decode()


@pytest.mark.django_db
class TestOrgScopedFeed:
    """Tests for org-scoped RSS feed (Phase 2, F11.11)"""

    def test_org_feed_returns_only_same_org_posts(
        self,
        client,
        org_a,
        org_b,
        org_a_admin,
    ):
        """Test that the org-scoped feed only returns posts for the active org."""
        Post.objects.create(
            title="Org A Post",
            author=org_a_admin,
            content="Content",
            status="published",
            organization=org_a,
        )
        Post.objects.create(
            title="Org B Post",
            author=org_a_admin,
            content="Content",
            status="published",
            organization=org_b,
        )

        client.force_login(org_a_admin)
        response = client.get(
            reverse(
                "quickscale_blog:org-feed",
                kwargs={"org_slug": org_a.slug},
            )
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert "Org A Post" in content
        assert "Org B Post" not in content, (
            "Org B's post should not appear in Org A's feed"
        )

    def test_org_feed_handles_published_post_without_author(
        self,
        client,
        org_a,
        org_a_admin,
    ):
        """Test org-scoped feed renders when a published post has no author."""
        Post.objects.create(
            title="Org A Authorless",
            author=None,
            content="Content",
            status="published",
            organization=org_a,
        )

        client.force_login(org_a_admin)
        response = client.get(
            reverse(
                "quickscale_blog:org-feed",
                kwargs={"org_slug": org_a.slug},
            )
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert "Org A Authorless" in content
        assert "Unknown author" not in content
