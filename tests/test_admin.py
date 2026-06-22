"""Tests for blog admin configuration"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.test.utils import override_settings

from quickscale_modules_blog.admin import (
    BlogMediaAssetAdmin,
    CategoryAdmin,
    PostAdmin,
    TagAdmin,
)
from quickscale_modules_blog.models import BlogMediaAsset, Category, Post, Tag

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
        from quickscale_modules_orgs.models import Organization

        admin_user = User.objects.create_superuser(
            username="posting_admin_blank_user",
            email="posting_admin_blank@example.com",
            password="pass123",
        )
        org = Organization.objects.create(name="Test Org", slug="test-org")

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
                "organization": str(org.pk),
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
        from quickscale_modules_orgs.models import Organization

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

        org = Organization.objects.create(name="Test Org", slug="test-org")

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
                "organization": str(org.pk),
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


@pytest.mark.django_db
class TestBlogAdminOperatorPaths:
    """Phase F11.11: verify blog admin surfaces use all_objects for cross-tenant visibility."""

    def test_category_admin_uses_operator_queryset(self):
        """CategoryAdmin.get_queryset uses Category.all_objects."""
        site = AdminSite()
        admin_instance = CategoryAdmin(Category, site)
        factory = RequestFactory()
        request = factory.get("/admin/")
        request.user = User.objects.create_superuser(
            username="cat-admin", email="cat@example.com", password="pass123"
        )
        qs = admin_instance.get_queryset(request)
        assert qs.model == Category
        assert str(qs.query) == str(Category.all_objects.all().query)

    def test_tag_admin_uses_operator_queryset(self):
        """TagAdmin.get_queryset uses Tag.all_objects."""
        site = AdminSite()
        admin_instance = TagAdmin(Tag, site)
        factory = RequestFactory()
        request = factory.get("/admin/")
        request.user = User.objects.create_superuser(
            username="tag-admin", email="tag@example.com", password="pass123"
        )
        qs = admin_instance.get_queryset(request)
        assert qs.model == Tag
        assert str(qs.query) == str(Tag.all_objects.all().query)

    def test_post_admin_uses_operator_queryset(self):
        """PostAdmin.get_queryset uses Post.all_objects."""
        site = AdminSite()
        admin_instance = PostAdmin(Post, site)
        factory = RequestFactory()
        request = factory.get("/admin/")
        request.user = User.objects.create_superuser(
            username="post-admin", email="post@example.com", password="pass123"
        )
        qs = admin_instance.get_queryset(request)
        assert qs.model == Post
        assert str(qs.query) == str(Post.all_objects.all().query)

    def test_blog_media_asset_admin_uses_operator_queryset(self):
        """BlogMediaAssetAdmin.get_queryset uses BlogMediaAsset.all_objects."""
        site = AdminSite()
        admin_instance = BlogMediaAssetAdmin(BlogMediaAsset, site)
        factory = RequestFactory()
        request = factory.get("/admin/")
        request.user = User.objects.create_superuser(
            username="media-admin", email="media@example.com", password="pass123"
        )
        qs = admin_instance.get_queryset(request)
        assert qs.model == BlogMediaAsset
        assert str(qs.query) == str(BlogMediaAsset.all_objects.all().query)

    def test_admin_queryset_returns_cross_tenant_posts(self, org_a, org_b):
        """Operator admin queryset returns posts from all organizations."""
        from quickscale_modules_blog.models import Post

        Post.objects.create(
            title="Post A", content="A", organization=org_a, status="draft"
        )
        Post.objects.create(
            title="Post B", content="B", organization=org_b, status="draft"
        )

        site = AdminSite()
        admin_instance = PostAdmin(Post, site)
        factory = RequestFactory()
        request = factory.get("/admin/")
        request.user = User.objects.create_superuser(
            username="cross-admin", email="cross@example.com", password="pass123"
        )
        qs = admin_instance.get_queryset(request)
        titles = list(qs.values_list("title", flat=True))
        assert "Post A" in titles
        assert "Post B" in titles

    # ------------------------------------------------------------------
    # Spy-based seam verification: prove all_objects is actually called
    # ------------------------------------------------------------------

    def test_category_admin_get_queryset_calls_all_objects(self):
        """CategoryAdmin.get_queryset actually calls Category.all_objects.all()."""
        with patch.object(Category, "all_objects") as mock_mgr:
            mock_mgr.all.return_value = Category.objects.none()
            site = AdminSite()
            admin_instance = CategoryAdmin(Category, site)
            factory = RequestFactory()
            request = factory.get("/admin/")
            request.user = User.objects.create_superuser(
                username="cat-spy", email="cat-spy@example.com", password="pass123"
            )
            admin_instance.get_queryset(request)
            mock_mgr.all.assert_called_once()

    def test_tag_admin_get_queryset_calls_all_objects(self):
        """TagAdmin.get_queryset actually calls Tag.all_objects.all()."""
        with patch.object(Tag, "all_objects") as mock_mgr:
            mock_mgr.all.return_value = Tag.objects.none()
            site = AdminSite()
            admin_instance = TagAdmin(Tag, site)
            factory = RequestFactory()
            request = factory.get("/admin/")
            request.user = User.objects.create_superuser(
                username="tag-spy", email="tag-spy@example.com", password="pass123"
            )
            admin_instance.get_queryset(request)
            mock_mgr.all.assert_called_once()

    def test_post_admin_get_queryset_calls_all_objects(self):
        """PostAdmin.get_queryset actually calls Post.all_objects.all()."""
        with patch.object(Post, "all_objects") as mock_mgr:
            mock_mgr.all.return_value = Post.objects.none()
            site = AdminSite()
            admin_instance = PostAdmin(Post, site)
            factory = RequestFactory()
            request = factory.get("/admin/")
            request.user = User.objects.create_superuser(
                username="post-spy", email="post-spy@example.com", password="pass123"
            )
            admin_instance.get_queryset(request)
            mock_mgr.all.assert_called_once()

    def test_blog_media_asset_admin_get_queryset_calls_all_objects(self):
        """BlogMediaAssetAdmin.get_queryset actually calls BlogMediaAsset.all_objects.all()."""
        with patch.object(BlogMediaAsset, "all_objects") as mock_mgr:
            mock_mgr.all.return_value = BlogMediaAsset.objects.none()
            site = AdminSite()
            admin_instance = BlogMediaAssetAdmin(BlogMediaAsset, site)
            factory = RequestFactory()
            request = factory.get("/admin/")
            request.user = User.objects.create_superuser(
                username="media-spy", email="media-spy@example.com", password="pass123"
            )
            admin_instance.get_queryset(request)
            mock_mgr.all.assert_called_once()


@pytest.mark.django_db
class TestBlogAdminOrgAwareMixin:
    """Phase F11.13b: verify org-aware safeguards on blog admin operator path."""

    # ------------------------------------------------------------------
    # PostAdmin: organization required on add, read-only on change
    # ------------------------------------------------------------------

    def test_post_admin_org_required_on_add_form(self):
        """PostAdmin add form requires organization."""
        site = AdminSite()
        admin = PostAdmin(Post, site)
        factory = RequestFactory()
        request = factory.get("/admin/")
        request.user = User.objects.create_superuser(
            username="org-req-admin",
            email="org-req@example.com",
            password="pass123",
        )

        form_class = admin.get_form(request, obj=None, change=False)
        assert "organization" in form_class.base_fields
        assert form_class.base_fields["organization"].required is True

    def test_post_admin_org_readonly_on_change_form(self):
        """PostAdmin change form shows organization as read-only."""
        site = AdminSite()
        admin = PostAdmin(Post, site)
        factory = RequestFactory()
        request = factory.get("/admin/")

        post = Post.objects.create(title="Change Org", content="...", status="draft")
        readonly = admin.get_readonly_fields(request, obj=post)
        assert "organization" in readonly

    def test_post_admin_org_not_readonly_on_add_form(self):
        """PostAdmin add form does NOT force organization read-only."""
        site = AdminSite()
        admin = PostAdmin(Post, site)
        factory = RequestFactory()
        request = factory.get("/admin/")

        readonly = admin.get_readonly_fields(request, obj=None)
        assert "organization" not in readonly

    # ------------------------------------------------------------------
    # CategoryAdmin: organization required on add, read-only on change
    # ------------------------------------------------------------------

    def test_category_admin_org_required_on_add_form(self):
        """CategoryAdmin add form requires organization."""
        site = AdminSite()
        admin = CategoryAdmin(Category, site)
        factory = RequestFactory()
        request = factory.get("/admin/")

        form_class = admin.get_form(request, obj=None, change=False)
        assert "organization" in form_class.base_fields
        assert form_class.base_fields["organization"].required is True

    def test_category_admin_org_readonly_on_change_form(self):
        """CategoryAdmin change form shows organization as read-only."""
        site = AdminSite()
        admin = CategoryAdmin(Category, site)
        factory = RequestFactory()
        request = factory.get("/admin/")

        cat = Category.objects.create(name="ReadOnly Cat", slug="readonly-cat")
        readonly = admin.get_readonly_fields(request, obj=cat)
        assert "organization" in readonly

    def test_category_admin_org_not_readonly_on_add_form(self):
        """CategoryAdmin add form does NOT force organization read-only."""
        site = AdminSite()
        admin = CategoryAdmin(Category, site)
        factory = RequestFactory()
        request = factory.get("/admin/")

        readonly = admin.get_readonly_fields(request, obj=None)
        assert "organization" not in readonly

    # ------------------------------------------------------------------
    # TagAdmin: organization required on add, read-only on change
    # ------------------------------------------------------------------

    def test_tag_admin_org_required_on_add_form(self):
        """TagAdmin add form requires organization."""
        site = AdminSite()
        admin = TagAdmin(Tag, site)
        factory = RequestFactory()
        request = factory.get("/admin/")

        form_class = admin.get_form(request, obj=None, change=False)
        assert "organization" in form_class.base_fields
        assert form_class.base_fields["organization"].required is True

    def test_tag_admin_org_readonly_on_change_form(self):
        """TagAdmin change form shows organization as read-only."""
        site = AdminSite()
        admin = TagAdmin(Tag, site)
        factory = RequestFactory()
        request = factory.get("/admin/")

        tag = Tag.objects.create(name="ReadOnly Tag", slug="readonly-tag")
        readonly = admin.get_readonly_fields(request, obj=tag)
        assert "organization" in readonly

    # ------------------------------------------------------------------
    # BlogMediaAssetAdmin: organization required on add, read-only on change
    # ------------------------------------------------------------------

    def test_media_asset_admin_org_required_on_add_form(self):
        """BlogMediaAssetAdmin add form requires organization."""
        site = AdminSite()
        admin = BlogMediaAssetAdmin(BlogMediaAsset, site)
        factory = RequestFactory()
        request = factory.get("/admin/")

        form_class = admin.get_form(request, obj=None, change=False)
        assert "organization" in form_class.base_fields
        assert form_class.base_fields["organization"].required is True

    def test_media_asset_admin_org_readonly_on_change_form(self):
        """BlogMediaAssetAdmin change form shows organization as read-only."""
        site = AdminSite()
        admin = BlogMediaAssetAdmin(BlogMediaAsset, site)
        factory = RequestFactory()
        request = factory.get("/admin/")

        import io
        from django.core.files.uploadedfile import SimpleUploadedFile

        asset = BlogMediaAsset.objects.create(
            original_filename="test.png",
            file=SimpleUploadedFile("test.png", io.BytesIO(b"dummy").read()),
        )
        readonly = admin.get_readonly_fields(request, obj=asset)
        assert "organization" in readonly

    # ------------------------------------------------------------------
    # PostAdmin same-org validation for category (FK) and tags (M2M)
    # ------------------------------------------------------------------

    def test_post_admin_add_rejects_cross_org_category(self, org_a, org_b):
        """PostAdmin add form rejects category from a different org."""
        site = AdminSite()
        admin = PostAdmin(Post, site)
        factory = RequestFactory()
        request = factory.post("/admin/")
        request.user = User.objects.create_superuser(
            username="cross-cat-admin",
            email="cross-cat@example.com",
            password="pass123",
        )

        cat_a = Category.objects.create(name="Cat A", slug="cat-a", organization=org_a)

        form_class = admin.get_form(request, obj=None, change=False)
        form = form_class(
            data={
                "title": "Cross-Org Post",
                "content": "Content",
                "status": "draft",
                "organization": str(org_b.pk),
                "category": str(cat_a.pk),
                "tags": [],
            }
        )

        assert not form.is_valid()
        assert "category" in form.errors

    def test_post_admin_add_accepts_same_org_category(self, org_a):
        """PostAdmin add form accepts category from the same org."""
        site = AdminSite()
        admin = PostAdmin(Post, site)
        factory = RequestFactory()
        request = factory.post("/admin/")
        request.user = User.objects.create_superuser(
            username="same-cat-admin",
            email="same-cat@example.com",
            password="pass123",
        )

        cat = Category.objects.create(
            name="Cat Same", slug="cat-same", organization=org_a
        )

        form_class = admin.get_form(request, obj=None, change=False)
        form = form_class(
            data={
                "title": "Same-Org Post",
                "content": "Content",
                "status": "draft",
                "organization": str(org_a.pk),
                "category": str(cat.pk),
                "tags": [],
            }
        )

        assert form.is_valid(), form.errors.as_text()

    def test_post_admin_add_rejects_cross_org_tag(self, org_a, org_b):
        """PostAdmin add form rejects tag from a different org."""
        site = AdminSite()
        admin = PostAdmin(Post, site)
        factory = RequestFactory()
        request = factory.post("/admin/")
        request.user = User.objects.create_superuser(
            username="cross-tag-admin",
            email="cross-tag@example.com",
            password="pass123",
        )

        tag_b = Tag.objects.create(name="Tag B", slug="tag-b", organization=org_b)

        form_class = admin.get_form(request, obj=None, change=False)
        form = form_class(
            data={
                "title": "Cross-Org Tag Post",
                "content": "Content",
                "status": "draft",
                "organization": str(org_a.pk),
                "category": "",
                "tags": [str(tag_b.pk)],
            }
        )

        assert not form.is_valid()
        assert "tags" in form.errors

    def test_post_admin_add_accepts_same_org_tag(self, org_a):
        """PostAdmin add form accepts tag from the same org."""
        site = AdminSite()
        admin = PostAdmin(Post, site)
        factory = RequestFactory()
        request = factory.post("/admin/")
        request.user = User.objects.create_superuser(
            username="same-tag-admin",
            email="same-tag@example.com",
            password="pass123",
        )

        tag = Tag.objects.create(name="Tag Same", slug="tag-same", organization=org_a)

        form_class = admin.get_form(request, obj=None, change=False)
        form = form_class(
            data={
                "title": "Same-Org Tag Post",
                "content": "Content",
                "status": "draft",
                "organization": str(org_a.pk),
                "category": "",
                "tags": [str(tag.pk)],
            }
        )

        assert form.is_valid(), form.errors.as_text()

    def test_post_admin_accepts_null_org_category(self):
        """PostAdmin accepts a category with no org (legacy compat) when the
        post itself has an org."""
        from quickscale_modules_orgs.models import Organization

        site = AdminSite()
        admin = PostAdmin(Post, site)
        factory = RequestFactory()
        request = factory.post("/admin/")
        request.user = User.objects.create_superuser(
            username="null-cat-admin",
            email="null-cat@example.com",
            password="pass123",
        )

        org = Organization.objects.create(name="Test Org", slug="test-org")
        cat_no_org = Category.objects.create(
            name="No Org Cat", slug="no-org-cat", organization=None
        )

        form_class = admin.get_form(request, obj=None, change=False)
        form = form_class(
            data={
                "title": "Null-Org Cat Post",
                "content": "Content",
                "status": "draft",
                "organization": str(org.pk),
                "category": str(cat_no_org.pk),
                "tags": [],
            }
        )

        assert form.is_valid(), form.errors.as_text()
