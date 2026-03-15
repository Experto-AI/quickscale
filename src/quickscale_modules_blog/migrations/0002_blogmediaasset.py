import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import quickscale_modules_blog.models


class Migration(migrations.Migration):
    dependencies = [
        ("quickscale_modules_blog", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
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
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
