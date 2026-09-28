"""Project-owned tenant model used by the SA182 regression suite."""

from django.conf import settings
from django.db import models

from quickscale_modules_listings.models import AbstractListing
from quickscale_modules_orgs.models import TenantModel


class ProjectListing(AbstractListing):
    """A project extension of listings with its own tenant contract."""

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="project_listings",
    )

    class Meta(AbstractListing.Meta):
        abstract = False
        verbose_name = "Project listing"
        verbose_name_plural = "Project listings"
        indexes = [
            models.Index(
                fields=["-published_date"],
                name="sa182_project_listing_pub_idx",
            ),
            models.Index(fields=["status"], name="sa182_project_listing_status_idx"),
            models.Index(fields=["slug"], name="sa182_project_listing_slug_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["slug", "organization"],
                name="sa182_project_listing_slug_org_uq",
            ),
        ]


class ProjectListingImage(TenantModel):
    """Project-owned tenant child used to prove derived purge ordering."""

    listing = models.ForeignKey(
        ProjectListing,
        on_delete=models.PROTECT,
        related_name="images",
    )
    image_url = models.URLField()

    class Meta(TenantModel.Meta):
        verbose_name = "Project listing image"
        verbose_name_plural = "Project listing images"


class ProjectFolder(TenantModel):
    """Project-owned tenant tree used to prove self-PROTECT purge handling."""

    parent = models.ForeignKey(
        "self",
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    name = models.CharField(max_length=100)

    class Meta(TenantModel.Meta):
        verbose_name = "Project folder"
        verbose_name_plural = "Project folders"
