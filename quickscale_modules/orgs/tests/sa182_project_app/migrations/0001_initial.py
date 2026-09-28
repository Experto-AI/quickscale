"""Initial schema and FORCE-RLS policy for the SA182 project fixture."""

from __future__ import annotations

from typing import Any

import django.db.models.deletion
import django.db.models.manager
from django.conf import settings
from django.db import migrations, models

from quickscale_modules_orgs.tenancy import (
    add_composite_child_fk,
    add_parent_unique_constraint,
    apply_force_rls,
    remove_composite_child_fk,
    remove_parent_unique_constraint,
    revert_force_rls,
)


PROJECT_LISTING_RLS_POLICY = "sa182_project_listing_org_isolation"
PROJECT_LISTING_TABLE = "sa182_project_app_projectlisting"
PROJECT_LISTING_IMAGE_RLS_POLICY = "sa182_project_listing_image_org_isolation"
PROJECT_LISTING_IMAGE_TABLE = "sa182_project_app_projectlistingimage"
PROJECT_LISTING_PARENT_UNIQUE = "sa182_project_listing_id_org_unique"
PROJECT_LISTING_IMAGE_COMPOSITE_FK = "sa182_project_listing_image_listing_org_fk"
PROJECT_FOLDER_RLS_POLICY = "sa182_project_folder_org_isolation"
PROJECT_FOLDER_TABLE = "sa182_project_app_projectfolder"
PROJECT_FOLDER_PARENT_UNIQUE = "sa182_project_folder_id_org_unique"
PROJECT_FOLDER_PARENT_COMPOSITE_FK = "sa182_project_folder_parent_org_fk"
_PROJECT_LISTING_RLS_TARGETS = (
    (PROJECT_LISTING_TABLE, PROJECT_LISTING_RLS_POLICY),
    (PROJECT_LISTING_IMAGE_TABLE, PROJECT_LISTING_IMAGE_RLS_POLICY),
    (PROJECT_FOLDER_TABLE, PROJECT_FOLDER_RLS_POLICY),
)


def _forward_rls(apps: Any, schema_editor: Any) -> None:
    """Install the fixture's migration-owned FORCE-RLS policy."""
    del apps
    revert_force_rls(schema_editor, _PROJECT_LISTING_RLS_TARGETS)
    apply_force_rls(schema_editor, _PROJECT_LISTING_RLS_TARGETS)
    add_parent_unique_constraint(
        schema_editor,
        PROJECT_LISTING_TABLE,
        PROJECT_LISTING_PARENT_UNIQUE,
    )
    add_composite_child_fk(
        schema_editor,
        child_table=PROJECT_LISTING_IMAGE_TABLE,
        constraint_name=PROJECT_LISTING_IMAGE_COMPOSITE_FK,
        child_fk_column="listing_id",
        parent_table=PROJECT_LISTING_TABLE,
        on_delete="RESTRICT",
    )
    add_parent_unique_constraint(
        schema_editor,
        PROJECT_FOLDER_TABLE,
        PROJECT_FOLDER_PARENT_UNIQUE,
    )
    add_composite_child_fk(
        schema_editor,
        child_table=PROJECT_FOLDER_TABLE,
        constraint_name=PROJECT_FOLDER_PARENT_COMPOSITE_FK,
        child_fk_column="parent_id",
        parent_table=PROJECT_FOLDER_TABLE,
        on_delete="RESTRICT",
    )


def _reverse_rls(apps: Any, schema_editor: Any) -> None:
    """Remove the fixture's FORCE-RLS policy when reversing the migration."""
    del apps
    remove_composite_child_fk(
        schema_editor,
        child_table=PROJECT_LISTING_IMAGE_TABLE,
        constraint_name=PROJECT_LISTING_IMAGE_COMPOSITE_FK,
    )
    remove_composite_child_fk(
        schema_editor,
        child_table=PROJECT_FOLDER_TABLE,
        constraint_name=PROJECT_FOLDER_PARENT_COMPOSITE_FK,
    )
    remove_parent_unique_constraint(
        schema_editor,
        PROJECT_FOLDER_TABLE,
        PROJECT_FOLDER_PARENT_UNIQUE,
    )
    remove_parent_unique_constraint(
        schema_editor,
        PROJECT_LISTING_TABLE,
        PROJECT_LISTING_PARENT_UNIQUE,
    )
    revert_force_rls(schema_editor, _PROJECT_LISTING_RLS_TARGETS)


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("quickscale_orgs", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectListing",
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
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="project_listings",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="quickscale_orgs.organization",
                    ),
                ),
                ("title", models.CharField(max_length=200)),
                ("slug", models.SlugField(blank=True, max_length=200)),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        help_text="Listing description in Markdown format",
                    ),
                ),
                (
                    "price",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Price in default currency (leave blank for 'Contact for price')",
                        max_digits=12,
                        null=True,
                    ),
                ),
                (
                    "location",
                    models.CharField(
                        blank=True,
                        help_text="Free-text location description",
                        max_length=200,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("published", "Published"),
                            ("sold", "Sold"),
                            ("archived", "Archived"),
                        ],
                        default="draft",
                        max_length=10,
                    ),
                ),
                (
                    "featured_image",
                    models.ImageField(
                        blank=True,
                        help_text="Featured image for the listing",
                        null=True,
                        upload_to="listings/images/",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "published_date",
                    models.DateTimeField(
                        blank=True,
                        help_text="Date when listing was published",
                        null=True,
                    ),
                ),
            ],
            options={
                "verbose_name": "Project listing",
                "verbose_name_plural": "Project listings",
                "ordering": ["-published_date", "-created_at"],
                "abstract": False,
                "base_manager_name": "all_objects",
                "indexes": [
                    models.Index(
                        fields=["-published_date"],
                        name="sa182_project_listing_pub_idx",
                    ),
                    models.Index(
                        fields=["status"], name="sa182_project_listing_status_idx"
                    ),
                    models.Index(
                        fields=["slug"], name="sa182_project_listing_slug_idx"
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("slug", "organization"),
                        name="sa182_project_listing_slug_org_uq",
                    ),
                ],
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        migrations.CreateModel(
            name="ProjectListingImage",
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
                ("image_url", models.URLField()),
                (
                    "listing",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="images",
                        to="sa182_project_app.projectlisting",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="quickscale_orgs.organization",
                    ),
                ),
            ],
            options={
                "verbose_name": "Project listing image",
                "verbose_name_plural": "Project listing images",
                "base_manager_name": "all_objects",
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        migrations.CreateModel(
            name="ProjectFolder",
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
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="quickscale_orgs.organization",
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="children",
                        to="sa182_project_app.projectfolder",
                    ),
                ),
            ],
            options={
                "verbose_name": "Project folder",
                "verbose_name_plural": "Project folders",
                "base_manager_name": "all_objects",
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        migrations.RunPython(
            code=_forward_rls,
            reverse_code=_reverse_rls,
            hints={"target_db": "default"},
        ),
    ]
