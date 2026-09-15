"""Project-owned tenant model used by the SA182 regression suite."""

from django.db import models

from quickscale_modules_listings.models import AbstractListing
from quickscale_modules_orgs.managers import TenantManager


class ProjectListing(AbstractListing):
    """A project extension of listings with its own tenant contract."""

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
