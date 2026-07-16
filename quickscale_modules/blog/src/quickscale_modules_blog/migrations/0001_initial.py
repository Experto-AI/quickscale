"""Initial migration for the QuickScale Blog module.

Collapsed SA92 migration: final-schema 0001 with Category, Tag, AuthorProfile,
BlogMediaAsset, and Post models.  NOT NULL/PROTECT organization FK via
tenant_org_fk, all_objects base manager, dual-manager contract, indexes,
per-org uniqueness constraints, and FORCE RLS policy installation with
NULLIF guard refresh.
"""

from __future__ import annotations

from typing import Any

import django.db.models.deletion
import django.db.models.manager
import markdownx.models
from django.conf import settings
from django.db import migrations, models

import quickscale_modules_blog.models

from quickscale_modules_orgs.tenancy import apply_force_rls, revert_force_rls

BLOG_CATEGORY_RLS_POLICY = "blog_category_org_isolation"
BLOG_TAG_RLS_POLICY = "blog_tag_org_isolation"
BLOG_MEDIA_ASSET_RLS_POLICY = "blog_media_asset_org_isolation"
BLOG_POST_RLS_POLICY = "blog_post_org_isolation"
BLOG_CATEGORY_TABLE = "quickscale_modules_blog_category"
BLOG_TAG_TABLE = "quickscale_modules_blog_tag"
BLOG_MEDIA_ASSET_TABLE = "quickscale_modules_blog_blogmediaasset"
BLOG_POST_TABLE = "quickscale_modules_blog_post"
_BLOG_RLS_TARGETS = (
    (BLOG_CATEGORY_TABLE, BLOG_CATEGORY_RLS_POLICY),
    (BLOG_TAG_TABLE, BLOG_TAG_RLS_POLICY),
    (BLOG_MEDIA_ASSET_TABLE, BLOG_MEDIA_ASSET_RLS_POLICY),
    (BLOG_POST_TABLE, BLOG_POST_RLS_POLICY),
)


def _forward_rls(apps: Any, schema_editor: Any) -> None:
    """Drop stale policies then re-create from the NULLIF-guarded template."""
    del apps
    revert_force_rls(schema_editor, _BLOG_RLS_TARGETS)
    apply_force_rls(schema_editor, _BLOG_RLS_TARGETS)


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("quickscale_modules_orgs", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("slug", models.SlugField(blank=True, max_length=100)),
                ("description", models.TextField(blank=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="blog_categories",
                        to="quickscale_modules_orgs.organization",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "Categories",
                "ordering": ["name"],
                "base_manager_name": "all_objects",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("name", "organization"),
                        name="blog_category_name_organization_unique",
                    ),
                    models.UniqueConstraint(
                        fields=("slug", "organization"),
                        name="blog_category_slug_organization_unique",
                    ),
                ],
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        migrations.CreateModel(
            name="Tag",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=50)),
                ("slug", models.SlugField(blank=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="blog_tags",
                        to="quickscale_modules_orgs.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
                "base_manager_name": "all_objects",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("name", "organization"),
                        name="blog_tag_name_organization_unique",
                    ),
                    models.UniqueConstraint(
                        fields=("slug", "organization"),
                        name="blog_tag_slug_organization_unique",
                    ),
                ],
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        migrations.CreateModel(
            name="AuthorProfile",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("bio", models.TextField(blank=True, help_text="Author biography")),
                (
                    "avatar",
                    models.ImageField(
                        blank=True,
                        help_text="Author profile picture",
                        null=True,
                        upload_to="blog/avatars/",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="author_profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["user__username"],
            },
        ),
        migrations.CreateModel(
            name="BlogMediaAsset",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "file",
                    models.ImageField(
                        upload_to=quickscale_modules_blog.models.blog_media_upload_to
                    ),
                ),
                (
                    "alt",
                    models.CharField(
                        blank=True,
                        help_text="Alt text for the uploaded image (accessibility)",
                        max_length=200,
                    ),
                ),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("inline", "Inline"),
                            ("featured", "Featured"),
                            ("general", "General"),
                        ],
                        default="inline",
                        help_text="How the asset is intended to be used by the blog workflow",
                        max_length=20,
                    ),
                ),
                ("original_filename", models.CharField(max_length=255)),
                ("width", models.PositiveIntegerField(blank=True, null=True)),
                ("height", models.PositiveIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "uploaded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="uploaded_blog_media_assets",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="blog_media_assets",
                        to="quickscale_modules_orgs.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "base_manager_name": "all_objects",
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        migrations.CreateModel(
            name="Post",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=200)),
                ("slug", models.SlugField(blank=True, max_length=200)),
                (
                    "content",
                    markdownx.models.MarkdownxField(
                        help_text="Post content in Markdown format"
                    ),
                ),
                (
                    "excerpt",
                    models.TextField(
                        blank=True,
                        help_text="Short excerpt (auto-generated from content if not provided)",
                        max_length=500,
                    ),
                ),
                (
                    "featured_image",
                    models.ImageField(
                        blank=True,
                        help_text="Featured image for the post",
                        null=True,
                        upload_to="blog/images/",
                    ),
                ),
                (
                    "featured_image_alt",
                    models.CharField(
                        blank=True,
                        help_text="Alt text for featured image (accessibility)",
                        max_length=200,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("draft", "Draft"), ("published", "Published")],
                        default="draft",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("published_date", models.DateTimeField(blank=True, null=True)),
                (
                    "author",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="blog_posts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "category",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="posts",
                        to="quickscale_modules_blog.category",
                    ),
                ),
                (
                    "tags",
                    models.ManyToManyField(
                        blank=True,
                        related_name="posts",
                        to="quickscale_modules_blog.tag",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="blog_posts",
                        to="quickscale_modules_orgs.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["-published_date", "-created_at"],
                "base_manager_name": "all_objects",
                "indexes": [
                    models.Index(
                        fields=["-published_date"],
                        name="quickscale__publish_446271_idx",
                    ),
                    models.Index(
                        fields=["status"], name="quickscale__status_e0e305_idx"
                    ),
                    models.Index(fields=["slug"], name="quickscale__slug_9a53ab_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("slug", "organization"),
                        name="blog_post_slug_organization_unique",
                    ),
                ],
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        # Install FORCE RLS on all blog tables with current NULLIF-guarded template.
        migrations.RunPython(
            code=_forward_rls,
            reverse_code=migrations.RunPython.noop,
            hints={"target_db": "default"},
        ),
    ]
