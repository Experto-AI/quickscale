"""Initial migration for the QuickScale social module."""

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

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
                        help_text=(
                            "Optional canonical provider name. Leave blank to detect it from the URL."
                        ),
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
                        unique=True,
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
                        help_text=(
                            "Optional canonical provider name. Leave blank to detect it from the URL."
                        ),
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
                        unique=True,
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
            ],
            options={
                "verbose_name": "Social embed",
                "verbose_name_plural": "Social embeds",
                "ordering": ["display_order", "title", "pk"],
            },
        ),
    ]
