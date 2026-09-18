"""Project-owned tenant model used by the SA182 regression suite."""

from django.conf import settings
from django.db import models

from quickscale_modules_listings.models import AbstractListing
from quickscale_modules_orgs.managers import TenantManager
from quickscale_modules_orgs.tenancy import tenant_org_fk


class ProjectListing(AbstractListing):
    """A project extension of listings with its own tenant contract."""

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="project_listings",
    )

    objects = TenantManager()
    all_objects = TenantManager(super_scope=True)

    class Meta(AbstractListing.Meta):
        abstract = False
        base_manager_name = "all_objects"
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


class ProjectListingImage(models.Model):
    """Project-owned tenant child used to prove derived purge ordering."""

    organization = tenant_org_fk(related_name="project_listing_images")
    listing = models.ForeignKey(
        ProjectListing,
        on_delete=models.PROTECT,
        related_name="images",
    )
    image_url = models.URLField()

    objects = TenantManager()
    all_objects = TenantManager(super_scope=True)

    class Meta:
        base_manager_name = "all_objects"
        verbose_name = "Project listing image"
        verbose_name_plural = "Project listing images"


class ProjectFolder(models.Model):
    """Project-owned tenant tree used to prove self-PROTECT purge handling."""

    organization = tenant_org_fk(related_name="project_folders")
    parent = models.ForeignKey(
        "self",
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    name = models.CharField(max_length=100)

    objects = TenantManager()
    all_objects = TenantManager(super_scope=True)

    class Meta:
        base_manager_name = "all_objects"
        verbose_name = "Project folder"
        verbose_name_plural = "Project folders"
