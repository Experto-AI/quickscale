"""Tests for blog admin configuration"""

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from quickscale_modules_blog.admin import PostAdmin
from quickscale_modules_blog.models import Post

User = get_user_model()


@pytest.mark.django_db
class TestPostAdmin:
    """Tests for PostAdmin save_model behavior"""

    def test_save_model_sets_author_on_create(self):
        """Test that save_model sets author to request user for new posts"""
        site = AdminSite()
        admin = PostAdmin(Post, site)
        factory = RequestFactory()
        request = factory.post("/admin/")
        request.user = User.objects.create_user(
            username="admin_user",
            email="admin@example.com",
            password="pass123",
        )

        post = Post(
            title="Admin Created Post",
            content="Content",
            status="draft",
        )

        # Simulate creating a new post (change=False) without author
        admin.save_model(request, post, form=None, change=False)

        assert post.pk is not None
        assert post.author == request.user

    def test_save_model_preserves_author_on_edit(self):
        """Test that save_model preserves existing author on edit"""
        site = AdminSite()
        admin = PostAdmin(Post, site)
        factory = RequestFactory()

        original_author = User.objects.create_user(
            username="original_author",
            email="original@example.com",
            password="pass123",
        )
        editing_user = User.objects.create_user(
            username="editor",
            email="editor@example.com",
            password="pass123",
        )

        post = Post.objects.create(
            title="Existing Post",
            author=original_author,
            content="Content",
        )

        request = factory.post("/admin/")
        request.user = editing_user

        # Simulate editing an existing post (change=True)
        admin.save_model(request, post, form=None, change=True)

        post.refresh_from_db()
        assert post.author == original_author

    def test_save_model_keeps_explicit_author_on_create(self):
        """Test that save_model keeps explicitly set author on new posts"""
        site = AdminSite()
        admin = PostAdmin(Post, site)
        factory = RequestFactory()

        explicit_author = User.objects.create_user(
            username="explicit_author",
            email="explicit@example.com",
            password="pass123",
        )
        request_user = User.objects.create_user(
            username="request_user",
            email="request@example.com",
            password="pass123",
        )

        request = factory.post("/admin/")
        request.user = request_user

        post = Post(
            title="Post With Author",
            author=explicit_author,
            content="Content",
        )

        # When author is already set, save_model should keep it
        admin.save_model(request, post, form=None, change=False)

        assert post.author == explicit_author
