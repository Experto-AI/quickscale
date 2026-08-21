"""Initial migration for the QuickScale Listings module."""

from __future__ import annotations

from typing import Any

import django.db.models.deletion
import django.db.models.manager
from django.db import migrations, models

from quickscale_modules_orgs.tenancy import apply_force_rls, revert_force_rls

LISTINGS_LISTING_RLS_POLICY = "listings_listing_org_isolation"
LISTINGS_LISTING_TABLE = "quickscale_modules_listings_listing"
_LISTINGS_RLS_TARGETS = ((LISTINGS_LISTING_TABLE, LISTINGS_LISTING_RLS_POLICY),)


def _forward_rls(apps: Any, schema_editor: Any) -> None:
    """Drop stale policy then re-create from the NULLIF-guarded template."""
    del apps
    revert_force_rls(schema_editor, _LISTINGS_RLS_TARGETS)
    apply_force_rls(schema_editor, _LISTINGS_RLS_TARGETS)


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("quickscale_modules_orgs", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Listing",
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
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(class)s_listings",
                        to="quickscale_modules_orgs.organization",
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
                "verbose_name": "Listing",
                "verbose_name_plural": "Listings",
                "ordering": ["-published_date", "-created_at"],
                "abstract": False,
                "base_manager_name": "all_objects",
                "indexes": [
                    models.Index(
                        fields=["-published_date"],
                        name="quickscale__publish_a4cb60_idx",
                    ),
                    models.Index(
                        fields=["status"], name="quickscale__status_e05f2c_idx"
                    ),
                    models.Index(fields=["slug"], name="quickscale__slug_e91f04_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("slug", "organization"),
                        name="listings_listing_slug_organization_unique",
                    )
                ],
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        migrations.RunPython(
            code=_forward_rls,
            reverse_code=migrations.RunPython.noop,
            hints={"target_db": "default"},
        ),
    ]
