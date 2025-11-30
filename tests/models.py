"""Concrete models for testing the abstract listing module"""

from quickscale_modules_listings.models import AbstractListing


class ConcreteListing(AbstractListing):
    """Concrete listing model for testing AbstractListing"""

    class Meta(AbstractListing.Meta):
        abstract = False
        app_label = "tests"
        verbose_name = "Test Listing"
        verbose_name_plural = "Test Listings"
