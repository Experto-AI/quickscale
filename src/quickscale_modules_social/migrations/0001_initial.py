"""Initial migration for the QuickScale Social module.

Collapsed SA90-MSQ migration: final-schema 0001 with SocialLink and SocialEmbed
models, NOT NULL/PROTECT organization FK (tenant_org_fk), resolution
metadata fields, and FORCE RLS policy installation.

No normalized_url global unique constraint — multiple orgs may link to
the same URL.  Resolution metadata fields are part of the initial schema
(no backfill needed for fresh installs).
"""

from __future__ import annotations

from typing import Any

import django.core.validators
import django.db.models.deletion
import django.db.models.manager
from django.db import migrations, models

from quickscale_modules_orgs.tenancy import apply_force_rls, revert_force_rls

SOCIAL_EMBED_RESOLUTION_PENDING = "pending"
SOCIAL_EMBED_RESOLUTION_RESOLVED = "resolved"
SOCIAL_EMBED_RESOLUTION_ERROR = "error"
SOCIAL_EMBED_RESOLUTION_CHOICES = (
    (SOCIAL_EMBED_RESOLUTION_PENDING, "Pending"),
    (SOCIAL_EMBED_RESOLUTION_RESOLVED, "Resolved"),
    (SOCIAL_EMBED_RESOLUTION_ERROR, "Error"),
)

SOCIAL_LINK_RLS_POLICY = "social_link_org_isolation"
SOCIAL_EMBED_RLS_POLICY = "social_embed_org_isolation"
SOCIAL_LINK_TABLE = "quickscale_modules_social_sociallink"
SOCIAL_EMBED_TABLE = "quickscale_modules_social_socialembed"
_SOCIAL_RLS_TARGETS = (
    (SOCIAL_LINK_TABLE, SOCIAL_LINK_RLS_POLICY),
    (SOCIAL_EMBED_TABLE, SOCIAL_EMBED_RLS_POLICY),
)


def _forward_rls(apps: Any, schema_editor: Any) -> None:
    """Drop stale policies then re-create from the NULLIF-guarded template."""
    del apps
    revert_force_rls(schema_editor, _SOCIAL_RLS_TARGETS)
    apply_force_rls(schema_editor, _SOCIAL_RLS_TARGETS)


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("quickscale_modules_orgs", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SocialLink",
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
                ("title", models.CharField(max_length=120)),
                ("description", models.TextField(blank=True)),
                (
                    "provider_name",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("facebook", "Facebook"),
                            ("instagram", "Instagram"),
                            ("linkedin", "LinkedIn"),
                            ("tiktok", "TikTok"),
                            ("x", "X"),
                            ("youtube", "YouTube"),
                        ],
                        db_index=True,
                        help_text="Optional canonical provider name. Leave blank to detect it from the URL.",
                        max_length=32,
                    ),
                ),
                ("url", models.URLField(max_length=500)),
                (
                    "normalized_url",
                    models.URLField(
                        blank=True,
                        editable=False,
                        max_length=500,
                    ),
                ),
                (
                    "display_order",
                    models.PositiveIntegerField(
                        db_index=True,
                        default=0,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                ("is_published", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="quickscale_modules_orgs.organization",
                    ),
                ),
            ],
            options={
                "verbose_name": "Social link",
                "verbose_name_plural": "Social links",
                "ordering": ["display_order", "title", "pk"],
                "base_manager_name": "all_objects",
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        migrations.CreateModel(
            name="SocialEmbed",
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
                ("title", models.CharField(max_length=120)),
                ("description", models.TextField(blank=True)),
                (
                    "provider_name",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("facebook", "Facebook"),
                            ("instagram", "Instagram"),
                            ("linkedin", "LinkedIn"),
                            ("tiktok", "TikTok"),
                            ("x", "X"),
                            ("youtube", "YouTube"),
                        ],
                        db_index=True,
                        help_text="Optional canonical provider name. Leave blank to detect it from the URL.",
                        max_length=32,
                    ),
                ),
                ("url", models.URLField(max_length=500)),
                (
                    "normalized_url",
                    models.URLField(
                        blank=True,
                        editable=False,
                        max_length=500,
                    ),
                ),
                (
                    "display_order",
                    models.PositiveIntegerField(
                        db_index=True,
                        default=0,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                ("is_published", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="quickscale_modules_orgs.organization",
                    ),
                ),
                (
                    "resolution_status",
                    models.CharField(
                        choices=SOCIAL_EMBED_RESOLUTION_CHOICES,
                        db_index=True,
                        default=SOCIAL_EMBED_RESOLUTION_PENDING,
                        editable=False,
                        max_length=16,
                    ),
                ),
                (
                    "resolution_error",
                    models.TextField(blank=True, default="", editable=False),
                ),
                (
                    "last_resolution_attempt_at",
                    models.DateTimeField(blank=True, null=True, editable=False),
                ),
                (
                    "last_resolved_at",
                    models.DateTimeField(blank=True, null=True, editable=False),
                ),
                (
                    "resolved_embed_url",
                    models.URLField(
                        blank=True, default="", editable=False, max_length=500
                    ),
                ),
                (
                    "resolved_thumbnail_url",
                    models.URLField(
                        blank=True, default="", editable=False, max_length=500
                    ),
                ),
                (
                    "resolved_width",
                    models.PositiveIntegerField(blank=True, null=True, editable=False),
                ),
                (
                    "resolved_height",
                    models.PositiveIntegerField(blank=True, null=True, editable=False),
                ),
                (
                    "resolved_thumbnail_width",
                    models.PositiveIntegerField(blank=True, null=True, editable=False),
                ),
                (
                    "resolved_thumbnail_height",
                    models.PositiveIntegerField(blank=True, null=True, editable=False),
                ),
            ],
            options={
                "verbose_name": "Social embed",
                "verbose_name_plural": "Social embeds",
                "ordering": ["display_order", "title", "pk"],
                "base_manager_name": "all_objects",
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        # Install FORCE RLS on social tables with current NULLIF-guarded template.
        migrations.RunPython(
            code=_forward_rls,
            reverse_code=migrations.RunPython.noop,
            hints={"target_db": "default"},
        ),
    ]
