"""Tests for blog views"""

import pytest
from django.urls import reverse
from quickscale_modules_blog.models import Category, Post, Tag


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

    def test_post_detail_draft_not_found(self, client, author_user):
        """Test that draft posts return 404"""
        post = Post.objects.create(
            title="Draft Post",
            author=author_user,
            content="Draft content",
            status="draft",
        )
        response = client.get(reverse("quickscale_blog:post_detail", args=[post.slug]))
        assert response.status_code == 404


@pytest.mark.django_db
class TestCategoryListView:
    """Tests for CategoryListView"""

    def test_category_list_view(self, client, author_user):
        """Test category list displays published posts in category"""
        category = Category.objects.create(name="Tech")
        Post.objects.create(
            title="Tech Post",
            author=author_user,
            content="Content",
            status="published",
            category=category,
        )
        Post.objects.create(
            title="Draft Tech Post",
            author=author_user,
            content="Content",
            status="draft",
            category=category,
        )

        response = client.get(
            reverse("quickscale_blog:category_list", args=[category.slug])
        )
        assert response.status_code == 200
        assert "Tech Post" in str(response.content)
        assert "Draft Tech Post" not in str(response.content)
        assert response.context["category"] == category

    def test_category_list_view_nonexistent(self, client):
        """Test category list with nonexistent slug raises DoesNotExist"""
        from quickscale_modules_blog.models import Category

        with pytest.raises(Category.DoesNotExist):
            client.get(reverse("quickscale_blog:category_list", args=["nonexistent"]))


@pytest.mark.django_db
class TestTagListView:
    """Tests for TagListView"""

    def test_tag_list_view(self, client, author_user):
        """Test tag list displays published posts with tag"""
        tag = Tag.objects.create(name="Python")
        post = Post.objects.create(
            title="Python Post",
            author=author_user,
            content="Content",
            status="published",
        )
        post.tags.add(tag)

        draft = Post.objects.create(
            title="Draft Python",
            author=author_user,
            content="Content",
            status="draft",
        )
        draft.tags.add(tag)

        response = client.get(reverse("quickscale_blog:tag_list", args=[tag.slug]))
        assert response.status_code == 200
        assert "Python Post" in str(response.content)
        assert "Draft Python" not in str(response.content)
        assert response.context["tag"] == tag

    def test_tag_list_view_nonexistent(self, client):
        """Test tag list with nonexistent slug raises DoesNotExist"""
        from quickscale_modules_blog.models import Tag

        with pytest.raises(Tag.DoesNotExist):
            client.get(reverse("quickscale_blog:tag_list", args=["nonexistent"]))
