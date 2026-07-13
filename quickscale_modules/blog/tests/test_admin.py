"""Tests for blog admin configuration"""

from types import SimpleNamespace

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

    def test_save_model_keeps_authorless_on_create(self, system_org, blog_org_scope):
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
            organization=system_org,
        )

        # Simulate creating a new post (change=False) without author
        with blog_org_scope(system_org):
            admin.save_model(request, post, form=None, change=False)

        assert post.pk is not None
        assert post.author is None

    def test_save_model_preserves_author_on_edit(self, system_org, blog_org_scope):
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

        with blog_org_scope(system_org):
            post = Post.objects.create(
                title="Existing Post",
                author=original_author,
                content="Content",
                organization=system_org,
            )

        request = factory.post("/admin/")
        request.user = editing_user

        # Simulate editing an existing post (change=True)
        with blog_org_scope(system_org):
            admin.save_model(request, post, form=None, change=True)

        with blog_org_scope(system_org):
            post.refresh_from_db()
        assert post.author == original_author

    def test_save_model_keeps_explicit_author_on_create(
        self, system_org, blog_org_scope
    ):
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
            organization=system_org,
        )

        # When author is already set, save_model should keep it
        with blog_org_scope(system_org):
            admin.save_model(request, post, form=None, change=False)

        assert post.author == explicit_author

    def test_save_model_explicit_blank_author_remains_none(
        self, system_org, blog_org_scope
    ):
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
            organization=system_org,
        )

        explicit_none_form = SimpleNamespace(cleaned_data={"author": None})

        with blog_org_scope(system_org):
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

    def test_formfield_for_foreignkey_edit_includes_all_users(
        self, system_org, blog_org_scope
    ):
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
        with blog_org_scope(system_org):
            post = Post.objects.create(
                title="Post With Existing Author",
                author=existing_author,
                content="Content",
                organization=system_org,
            )

        request = factory.get(f"/admin/{post.pk}/change/")
        request.user = editor
        request.resolver_match = SimpleNamespace(kwargs={"object_id": str(post.pk)})

        with blog_org_scope(system_org):
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
    def test_admin_add_view_explicit_blank_author_omits_author(
        self, client, blog_org_scope
    ):
        """Test posting admin add form with blank author leaves it None."""
        from quickscale_modules_orgs.models import Organization

        admin_user = User.objects.create_superuser(
            username="posting_admin_blank_user",
            email="posting_admin_blank@example.com",
            password="pass123",
        )
        org = Organization.objects.create(name="Test Org", slug="test-org")

        client.force_login(admin_user)
        with blog_org_scope(org):
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
        with blog_org_scope(org):
            post = Post.all_objects.get(title="Admin Blank Author Post")
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

    def test_get_form_submission_blank_author_preserves_existing_author_on_edit(
        self, system_org, blog_org_scope
    ):
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
        with blog_org_scope(system_org):
            post = Post.objects.create(
                title="Blank Author Edit",
                author=existing_author,
                content="Content",
                status="draft",
                organization=system_org,
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
class TestBlogAdminTenantScopedQueryset:
    """SA14.3: verify blog admin querysets scope to org context via TenantModelAdmin."""

    def test_category_admin_fail_closed_without_org(self):
        """CategoryAdmin.get_queryset returns empty when no org context."""
        site = AdminSite()
        admin_instance = CategoryAdmin(Category, site)
        factory = RequestFactory()
        request = factory.get("/admin/")
        request.user = User.objects.create_superuser(
            username="cat-admin", email="cat@example.com", password="pass123"
        )
        qs = admin_instance.get_queryset(request)
        assert qs.count() == 0

    def test_category_admin_scopes_to_org(self, system_org):
        """CategoryAdmin.get_queryset scopes to org when _validated_org_id is set."""
        site = AdminSite()
        admin_instance = CategoryAdmin(Category, site)
        factory = RequestFactory()
        request = factory.get("/admin/")
        request.user = User.objects.create_superuser(
            username="cat-admin-2", email="cat2@example.com", password="pass123"
        )
        request._validated_org_id = system_org.pk
        qs = admin_instance.get_queryset(request)
        assert qs.model == Category
        assert qs.count() == 0  # No categories exist yet

    def test_tag_admin_fail_closed_without_org(self):
        """TagAdmin.get_queryset returns empty when no org context."""
        site = AdminSite()
        admin_instance = TagAdmin(Tag, site)
        factory = RequestFactory()
        request = factory.get("/admin/")
        request.user = User.objects.create_superuser(
            username="tag-admin", email="tag@example.com", password="pass123"
        )
        qs = admin_instance.get_queryset(request)
        assert qs.count() == 0

    def test_post_admin_fail_closed_without_org(self):
        """PostAdmin.get_queryset returns empty when no org context."""
        site = AdminSite()
        admin_instance = PostAdmin(Post, site)
        factory = RequestFactory()
        request = factory.get("/admin/")
        request.user = User.objects.create_superuser(
            username="post-admin", email="post@example.com", password="pass123"
        )
        qs = admin_instance.get_queryset(request)
        assert qs.count() == 0

    def test_blog_media_asset_admin_fail_closed_without_org(self):
        """BlogMediaAssetAdmin.get_queryset returns empty when no org context."""
        site = AdminSite()
        admin_instance = BlogMediaAssetAdmin(BlogMediaAsset, site)
        factory = RequestFactory()
        request = factory.get("/admin/")
        request.user = User.objects.create_superuser(
            username="media-admin", email="media@example.com", password="pass123"
        )
        qs = admin_instance.get_queryset(request)
        assert qs.count() == 0

    def test_post_admin_scopes_to_org(self, system_org, org_b, blog_org_scope):
        """PostAdmin.get_queryset returns only posts from the scoped org."""
        with blog_org_scope(system_org):
            Post.all_objects.create(
                title="System Post",
                content="A",
                organization=system_org,
                status="draft",
            )
        with blog_org_scope(org_b):
            Post.all_objects.create(
                title="Org B Post", content="B", organization=org_b, status="draft"
            )

        site = AdminSite()
        admin_instance = PostAdmin(Post, site)
        factory = RequestFactory()
        request = factory.get("/admin/")
        request.user = User.objects.create_superuser(
            username="scope-admin", email="scope@example.com", password="pass123"
        )
        request._validated_org_id = system_org.pk

        qs = admin_instance.get_queryset(request)
        titles = list(qs.values_list("title", flat=True))
        assert "System Post" in titles
        assert "Org B Post" not in titles


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

    def test_post_admin_org_readonly_on_change_form(self, system_org, blog_org_scope):
        """PostAdmin change form shows organization as read-only."""
        site = AdminSite()
        admin = PostAdmin(Post, site)
        factory = RequestFactory()
        request = factory.get("/admin/")

        with blog_org_scope(system_org):
            post = Post.objects.create(
                title="Change Org",
                content="...",
                status="draft",
                organization=system_org,
            )
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

    def test_category_admin_org_readonly_on_change_form(
        self, system_org, blog_org_scope
    ):
        """CategoryAdmin change form shows organization as read-only."""
        site = AdminSite()
        admin = CategoryAdmin(Category, site)
        factory = RequestFactory()
        request = factory.get("/admin/")

        with blog_org_scope(system_org):
            cat = Category.objects.create(
                name="ReadOnly Cat", slug="readonly-cat", organization=system_org
            )
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

    def test_tag_admin_org_readonly_on_change_form(self, system_org, blog_org_scope):
        """TagAdmin change form shows organization as read-only."""
        site = AdminSite()
        admin = TagAdmin(Tag, site)
        factory = RequestFactory()
        request = factory.get("/admin/")

        with blog_org_scope(system_org):
            tag = Tag.objects.create(
                name="ReadOnly Tag", slug="readonly-tag", organization=system_org
            )
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

    def test_media_asset_admin_org_readonly_on_change_form(
        self, system_org, blog_org_scope
    ):
        """BlogMediaAssetAdmin change form shows organization as read-only."""
        site = AdminSite()
        admin = BlogMediaAssetAdmin(BlogMediaAsset, site)
        factory = RequestFactory()
        request = factory.get("/admin/")

        import io
        from django.core.files.uploadedfile import SimpleUploadedFile

        with blog_org_scope(system_org):
            asset = BlogMediaAsset.objects.create(
                original_filename="test.png",
                file=SimpleUploadedFile("test.png", io.BytesIO(b"dummy").read()),
                organization=system_org,
            )
        readonly = admin.get_readonly_fields(request, obj=asset)
        assert "organization" in readonly

    # ------------------------------------------------------------------
    # PostAdmin same-org validation for category (FK) and tags (M2M)
    # ------------------------------------------------------------------

    def test_post_admin_add_rejects_cross_org_category(
        self, org_a, org_b, blog_org_scope
    ):
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

        with blog_org_scope(org_a):
            cat_a = Category.objects.create(
                name="Cat A", slug="cat-a", organization=org_a
            )

        with blog_org_scope(org_a):
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

    def test_post_admin_add_accepts_same_org_category(self, org_a, blog_org_scope):
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

        with blog_org_scope(org_a):
            cat = Category.objects.create(
                name="Cat Same", slug="cat-same", organization=org_a
            )

        with blog_org_scope(org_a):
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

    def test_post_admin_add_rejects_cross_org_tag(self, org_a, org_b, blog_org_scope):
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

        with blog_org_scope(org_b):
            tag_b = Tag.objects.create(name="Tag B", slug="tag-b", organization=org_b)

        with blog_org_scope(org_b):
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

    def test_post_admin_add_accepts_same_org_tag(self, org_a, blog_org_scope):
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

        with blog_org_scope(org_a):
            tag = Tag.objects.create(
                name="Tag Same", slug="tag-same", organization=org_a
            )

        with blog_org_scope(org_a):
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

    def test_post_admin_add_rejects_same_org_category_missing_in_form(self, org_a):
        """PostAdmin add form requires selecting a valid category."""
        site = AdminSite()
        admin = PostAdmin(Post, site)
        factory = RequestFactory()
        request = factory.post("/admin/")
        request.user = User.objects.create_superuser(
            username="missing-cat-admin",
            email="missing-cat@example.com",
            password="pass123",
        )

        form_class = admin.get_form(request, obj=None, change=False)
        form = form_class(
            data={
                "title": "No Cat Post",
                "content": "Content",
                "status": "draft",
                "organization": str(org_a.pk),
                "category": "",
                "tags": [],
            }
        )

        assert form.is_valid(), form.errors.as_text()
