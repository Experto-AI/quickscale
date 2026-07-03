"""Concrete models for testing the abstract listing module"""

from django.db import models

from quickscale_modules_listings.models import AbstractListing
from quickscale_modules_orgs.managers import TenantManager


class ConcreteListing(AbstractListing):
    """Concrete listing model for testing AbstractListing

    SA11.4: Requires ``TenantManager`` as the default ``objects`` manager
    so that views using ``ListingsPublicReadMixin`` + ``org_scope()``
    correctly auto-scope queries through the tenant-scoped manager's
    ``get_queryset()``.
    """

    objects = TenantManager()
    all_objects = TenantManager(super_scope=True)

    class Meta(AbstractListing.Meta):
        abstract = False
        app_label = "tests"
        verbose_name = "Test Listing"
        verbose_name_plural = "Test Listings"
        base_manager_name = "all_objects"
        constraints = [
            models.UniqueConstraint(
                fields=["slug", "organization"],
                name="tests_concretelisting_slug_org_unique",
            ),
        ]


class AlternateListing(AbstractListing):
    """Second concrete subclass for testing abstract seam (CR-001).

    Proves that ``AbstractListing.organization`` uses a per-subclass
    ``related_name`` (``%(class)s_listings``) so multiple concrete models
    can coexist without reverse-accessor collision.
    """

    objects = TenantManager()
    all_objects = TenantManager(super_scope=True)

    class Meta(AbstractListing.Meta):
        abstract = False
        app_label = "tests"
        verbose_name = "Alternate Listing"
        verbose_name_plural = "Alternate Listings"
        base_manager_name = "all_objects"
        constraints = [
            models.UniqueConstraint(
                fields=["slug", "organization"],
                name="tests_alternatelisting_slug_org_unique",
            ),
        ]
