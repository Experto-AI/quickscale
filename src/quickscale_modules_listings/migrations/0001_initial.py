"""T1.8: Squashed initial migration — NOT NULL organization contract.

Replaces the Phase F11.12b additive approach (0001 + 0002_org_ownership)
with a single clean migration matching the D5 NOT NULL contract.

Changes from the additive schema:
- ``organization`` is NOT NULL / PROTECT (via ``tenant_org_fk()``)
- No partial ``UniqueConstraint`` for ``(slug) WHERE organization IS NULL``
  (unreachable when organization is NOT NULL)
- ``slug`` has no global ``unique=True`` (per-org unique via constraint below)
- Per-org slug uniqueness via ``(slug, organization)`` constraint
"""

import django.db.models.deletion
from django.db import migrations, models


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
                        db_index=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(class)s_listings",
                        to="quickscale_modules_orgs.Organization",
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
            },
        ),
        migrations.AddIndex(
            model_name="listing",
            index=models.Index(
                fields=["-published_date"], name="quickscale__publish_a4cb60_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="listing",
            index=models.Index(fields=["status"], name="quickscale__status_e05f2c_idx"),
        ),
        migrations.AddIndex(
            model_name="listing",
            index=models.Index(fields=["slug"], name="quickscale__slug_e91f04_idx"),
        ),
        migrations.AddConstraint(
            model_name="listing",
            constraint=models.UniqueConstraint(
                fields=["slug", "organization"],
                name="listings_listing_slug_organization_unique",
            ),
        ),
    ]
