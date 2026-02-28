"""Tests for blog admin configuration"""

from types import SimpleNamespace

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

    def test_save_model_blank_author_defaults_to_request_user(self):
        """Test that blank author selection still resolves to request user on create"""
        site = AdminSite()
        admin = PostAdmin(Post, site)
        factory = RequestFactory()

        request_user = User.objects.create_user(
            username="request_user_none",
            email="request_none@example.com",
            password="pass123",
        )
        request = factory.post("/admin/")
        request.user = request_user

        post = Post(
            title="Post Without Author",
            content="Content",
            status="draft",
        )

        explicit_none_form = SimpleNamespace(cleaned_data={"author": None})

        admin.save_model(request, post, form=explicit_none_form, change=False)

        assert post.author == request_user

    def test_formfield_for_foreignkey_create_includes_current_user_and_blank(self):
        """Test author dropdown includes no-author and current user options on create"""
        site = AdminSite()
        admin = PostAdmin(Post, site)
        factory = RequestFactory()
        request = factory.get("/admin/")
        request.user = User.objects.create_user(
            username="dropdown_user",
            email="dropdown@example.com",
            password="pass123",
        )

        form_field = admin.formfield_for_foreignkey(
            Post._meta.get_field("author"), request
        )

        assert form_field.empty_label == "No author"
        assert list(form_field.queryset.values_list("pk", flat=True)) == [
            request.user.pk
        ]

    def test_formfield_for_foreignkey_edit_includes_existing_author(self):
        """Test author dropdown keeps existing author option on edit"""
        site = AdminSite()
        admin = PostAdmin(Post, site)
        factory = RequestFactory()

        existing_author = User.objects.create_user(
            username="existing_author",
            email="existing@author.com",
            password="pass123",
        )
        editor = User.objects.create_user(
            username="editor_user",
            email="editor_user@example.com",
            password="pass123",
        )
        post = Post.objects.create(
            title="Post With Existing Author",
            author=existing_author,
            content="Content",
        )

        request = factory.get(f"/admin/{post.pk}/change/")
        request.user = editor
        request.resolver_match = SimpleNamespace(kwargs={"object_id": str(post.pk)})

        form_field = admin.formfield_for_foreignkey(
            Post._meta.get_field("author"), request
        )

        assert set(form_field.queryset.values_list("pk", flat=True)) == {
            editor.pk,
            existing_author.pk,
        }

    def test_get_form_clean_author_defaults_to_request_user_on_create(self):
        """Test form clean_author maps blank author to request user on create"""
        site = AdminSite()
        admin = PostAdmin(Post, site)
        factory = RequestFactory()

        request_user = User.objects.create_user(
            username="form_create_user",
            email="form_create@example.com",
            password="pass123",
        )
        request = factory.post("/admin/")
        request.user = request_user

        form_class = admin.get_form(request, obj=None, change=False)
        form = form_class()
        form.cleaned_data = {"author": None}

        assert form.clean_author() == request_user

    def test_get_form_clean_author_preserves_existing_author_on_edit(self):
        """Test form clean_author keeps current instance author on edit when blank"""
        site = AdminSite()
        admin = PostAdmin(Post, site)
        factory = RequestFactory()

        existing_author = User.objects.create_user(
            username="form_existing_author",
            email="form_existing@example.com",
            password="pass123",
        )
        editor = User.objects.create_user(
            username="form_editor_user",
            email="form_editor@example.com",
            password="pass123",
        )
        post = Post.objects.create(
            title="Form Edit Post",
            author=existing_author,
            content="Content",
        )

        request = factory.post(f"/admin/{post.pk}/change/")
        request.user = editor

        form_class = admin.get_form(request, obj=post, change=True)
        form = form_class(instance=post)
        form.cleaned_data = {"author": None}

        assert form.clean_author() == existing_author
