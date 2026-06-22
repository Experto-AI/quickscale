"""Phase F11.12b: Add organization FK and per-org slug uniqueness to Listing.

Steps:
1. Add nullable ``organization`` FK to ``quickscale_modules_orgs.Organization``.
2. Remove global ``unique=True`` from ``slug`` (moved to per-org constraint).
3. Add ``UniqueConstraint`` on ``(slug, organization)`` for per-org slug uniqueness.
4. Add partial ``UniqueConstraint`` on ``(slug) WHERE organization IS NULL``
   to preserve flat-route slug uniqueness (CR-003).
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Add organization ownership and per-org uniqueness for Listing."""

    dependencies = [
        ("quickscale_modules_listings", "0001_initial"),
        ("quickscale_modules_orgs", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="listing",
            name="organization",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="%(class)s_listings",
                to="quickscale_modules_orgs.Organization",
            ),
        ),
        migrations.AlterField(
            model_name="listing",
            name="slug",
            field=models.SlugField(blank=True, max_length=200),
        ),
        migrations.AddConstraint(
            model_name="listing",
            constraint=models.UniqueConstraint(
                fields=["slug", "organization"],
                name="listings_listing_slug_organization_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="listing",
            constraint=models.UniqueConstraint(
                fields=["slug"],
                name="listings_listing_slug_org_null_unique",
                condition=models.Q(organization__isnull=True),
            ),
        ),
    ]
