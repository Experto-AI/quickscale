"""Tests for blog admin configuration"""

from types import SimpleNamespace

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.test.utils import override_settings

from quickscale_modules_blog.admin import PostAdmin
from quickscale_modules_blog.models import Post

User = get_user_model()


@pytest.mark.django_db
class TestPostAdmin:
    """Tests for PostAdmin save_model behavior"""

    def test_save_model_keeps_authorless_on_create(self):
        """Test that save_model does not force an author when explicitly omitted"""
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
        assert post.author is None

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

    def test_save_model_explicit_blank_author_remains_none(self):
        """Test that explicitly selecting blank author yields an authorless post"""
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

        assert post.author is None

    def test_formfield_for_foreignkey_create_includes_request_user_and_blank(self):
        """Test author dropdown includes request user and a blank option on create"""
        site = AdminSite()
        admin = PostAdmin(Post, site)
        factory = RequestFactory()
        request = factory.get("/admin/")
        request.user = User.objects.create_user(
            username="dropdown_user",
            email="dropdown@example.com",
            password="pass123",
        )
        User.objects.create_user(
            username="another_dropdown_user",
            email="another_dropdown@example.com",
            password="pass123",
        )

        form_field = admin.formfield_for_foreignkey(
            Post._meta.get_field("author"), request
        )

        assert form_field.empty_label == "No author"
        assert list(form_field.queryset.values_list("pk", flat=True)) == [
            request.user.pk,
        ]

    def test_formfield_for_foreignkey_create_is_not_required(self):
        """Test author dropdown is optional on create"""
        site = AdminSite()
        admin = PostAdmin(Post, site)
        factory = RequestFactory()
        request = factory.get("/admin/")
        request.user = User.objects.create_user(
            username="optional_author_user",
            email="optional_author@example.com",
            password="pass123",
        )

        form_field = admin.formfield_for_foreignkey(
            Post._meta.get_field("author"), request
        )

        assert form_field.required is False

    def test_formfield_for_foreignkey_edit_includes_all_users(self):
        """Test author dropdown keeps all user options on edit"""
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

    @override_settings(ALLOWED_HOSTS=["testserver"])
    def test_admin_add_view_renders_author_dropdown_initializes_with_request_user(
        self, client
    ):
        """Test the real admin add view initializes author to request user."""
        admin_user = User.objects.create_superuser(
            username="admin_dropdown_user",
            email="admin_dropdown@example.com",
            password="pass123",
        )

        client.force_login(admin_user)
        response = client.get("/admin/quickscale_modules_blog/post/add/")

        assert response.status_code == 200
        assert '<select name="author"' in response.content.decode()

        author_field = response.context["adminform"].form.fields["author"]
        assert author_field.required is False
        assert author_field.empty_label == "No author"
        assert author_field.initial == admin_user

    @override_settings(ALLOWED_HOSTS=["testserver"])
    def test_admin_add_view_rejects_selecting_non_allowed_user_as_author(self, client):
        """Test posting the admin add form rejects selecting non-allowed user author."""
        admin_user = User.objects.create_superuser(
            username="posting_admin_user",
            email="posting_admin@example.com",
            password="pass123",
        )
        selectable_author = User.objects.create_user(
            username="posting_selectable_author",
            email="posting_selectable_author@example.com",
            password="pass123",
        )

        client.force_login(admin_user)
        response = client.post(
            "/admin/quickscale_modules_blog/post/add/",
            data={
                "title": "Admin Selected Author Post",
                "slug": "",
                "author": str(selectable_author.pk),
                "content": "Content",
                "excerpt": "",
                "featured_image": "",
                "featured_image_alt": "",
                "status": "draft",
                "category": "",
                "tags": [],
                "published_date_0": "",
                "published_date_1": "",
                "_save": "Save",
            },
        )

        assert response.status_code == 200
        assert "Select a valid choice" in response.content.decode()

    @override_settings(ALLOWED_HOSTS=["testserver"])
    def test_admin_add_view_explicit_blank_author_omits_author(self, client):
        """Test posting admin add form with blank author leaves it None."""
        admin_user = User.objects.create_superuser(
            username="posting_admin_blank_user",
            email="posting_admin_blank@example.com",
            password="pass123",
        )

        client.force_login(admin_user)
        response = client.post(
            "/admin/quickscale_modules_blog/post/add/",
            data={
                "title": "Admin Blank Author Post",
                "slug": "",
                "author": "",
                "content": "Content",
                "excerpt": "",
                "featured_image": "",
                "featured_image_alt": "",
                "status": "draft",
                "category": "",
                "tags": [],
                "published_date_0": "",
                "published_date_1": "",
                "_save": "Save",
            },
        )

        assert response.status_code == 302
        post = Post.objects.get(title="Admin Blank Author Post")
        assert post.author is None

    def test_get_form_submission_blank_author_is_valid_on_create(self):
        """Test full admin form submission accepts blank author on create"""
        site = AdminSite()
        admin = PostAdmin(Post, site)
        factory = RequestFactory()

        request_user = User.objects.create_user(
            username="form_submit_create_user",
            email="form_submit_create@example.com",
            password="pass123",
        )
        request = factory.post("/admin/")
        request.user = request_user

        form_class = admin.get_form(request, obj=None, change=False)
        form = form_class(
            data={
                "title": "Blank Author Create",
                "slug": "",
                "author": "",
                "content": "Content",
                "excerpt": "",
                "featured_image": "",
                "featured_image_alt": "",
                "status": "draft",
                "category": "",
                "tags": [],
                "published_date_0": "",
                "published_date_1": "",
            }
        )

        assert form.is_valid(), form.errors.as_text()
        assert form.cleaned_data["author"] is None

    def test_get_form_submission_blank_author_preserves_existing_author_on_edit(self):
        """Test full admin form submission keeps existing author on edit"""
        site = AdminSite()
        admin = PostAdmin(Post, site)
        factory = RequestFactory()

        existing_author = User.objects.create_user(
            username="form_submit_existing_author",
            email="form_submit_existing@example.com",
            password="pass123",
        )
        editor = User.objects.create_superuser(
            username="form_submit_editor",
            email="form_submit_editor@example.com",
            password="pass123",
        )
        post = Post.objects.create(
            title="Blank Author Edit",
            author=existing_author,
            content="Content",
            status="draft",
        )

        request = factory.post(f"/admin/{post.pk}/change/")
        request.user = editor
        request.resolver_match = SimpleNamespace(kwargs={"object_id": str(post.pk)})

        form_class = admin.get_form(request, obj=post, change=True)
        form = form_class(
            data={
                "title": post.title,
                "slug": post.slug,
                "author": "",
                "content": post.content,
                "excerpt": post.excerpt,
                "featured_image": "",
                "featured_image_alt": post.featured_image_alt,
                "status": post.status,
                "category": "",
                "tags": [],
                "published_date_0": "",
                "published_date_1": "",
            },
            instance=post,
        )

        assert form.is_valid(), form.errors.as_text()
        assert form.cleaned_data["author"] is None
