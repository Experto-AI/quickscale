"""Tests for blog views"""

import pytest
from django.urls import reverse
from quickscale_modules_blog.models import Post


@pytest.mark.django_db
class TestPostListView:
    """Tests for PostListView"""

    def test_post_list_view(self, client, author_user):
        """Test post list displays published posts"""
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

        response = client.get(reverse("quickscale_blog:post_list"))
        assert response.status_code == 200
        assert "Published Post" in str(response.content)
        assert "Draft Post" not in str(response.content)


@pytest.mark.django_db
class TestPostDetailView:
    """Tests for PostDetailView"""

    def test_post_detail_view(self, client, author_user):
        """Test post detail view"""
        post = Post.objects.create(
            title="Test Post",
            author=author_user,
            content="Test content",
            status="published",
        )

        response = client.get(reverse("quickscale_blog:post_detail", args=[post.slug]))
        assert response.status_code == 200
        assert "Test Post" in str(response.content)
