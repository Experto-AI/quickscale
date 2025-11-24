"""Tests for blog RSS feeds"""

import pytest
from django.urls import reverse
from quickscale_modules_blog.models import Post


@pytest.mark.django_db
class TestLatestPostsFeed:
    """Tests for RSS feed"""

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
