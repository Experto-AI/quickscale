"""Initial migration for the QuickScale social module.

T1.9 squashed migration — clean NOT NULL/PROTECT contract per D5.

- ``organization`` is a NOT NULL PROTECT-guarded FK to Organization
  (``tenant_org_fk()``).
- ``normalized_url`` has no global unique constraint (multiple orgs may
  link to the same URL).
- Resolution metadata fields live in the initial schema (no backfill
  needed — no existing users per D5).
"""

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


SOCIAL_EMBED_RESOLUTION_PENDING = "pending"
SOCIAL_EMBED_RESOLUTION_RESOLVED = "resolved"
SOCIAL_EMBED_RESOLUTION_ERROR = "error"
SOCIAL_EMBED_RESOLUTION_CHOICES = (
    (SOCIAL_EMBED_RESOLUTION_PENDING, "Pending"),
    (SOCIAL_EMBED_RESOLUTION_RESOLVED, "Resolved"),
    (SOCIAL_EMBED_RESOLUTION_ERROR, "Error"),
)


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("quickscale_modules_orgs", "0003_alter_organization_is_system"),
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
                        # No longer globally unique — multiple orgs may link to the same URL.
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
            },
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
            },
        ),
    ]
