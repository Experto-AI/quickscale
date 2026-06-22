"""Concrete models for testing the abstract listing module"""

from django.db import models

from quickscale_modules_listings.models import AbstractListing


class ConcreteListing(AbstractListing):
    """Concrete listing model for testing AbstractListing"""

    class Meta(AbstractListing.Meta):
        abstract = False
        app_label = "tests"
        verbose_name = "Test Listing"
        verbose_name_plural = "Test Listings"
        constraints = [
            models.UniqueConstraint(
                fields=["slug", "organization"],
                name="tests_concretelisting_slug_org_unique",
            ),
            models.UniqueConstraint(
                fields=["slug"],
                name="tests_concretelisting_slug_org_null_unique",
                condition=models.Q(organization__isnull=True),
            ),
        ]


class AlternateListing(AbstractListing):
    """Second concrete subclass for testing abstract seam (CR-001).

    Proves that ``AbstractListing.organization`` uses a per-subclass
    ``related_name`` (``%(class)s_listings``) so multiple concrete models
    can coexist without reverse-accessor collision.
    """

    class Meta(AbstractListing.Meta):
        abstract = False
        app_label = "tests"
        verbose_name = "Alternate Listing"
        verbose_name_plural = "Alternate Listings"
