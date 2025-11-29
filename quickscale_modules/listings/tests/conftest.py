"""Pytest configuration for listings module tests"""

from decimal import Decimal

import django
import pytest
from django.conf import settings

# Configure Django before importing models
if not settings.configured:
    from tests import settings as test_settings

    settings.configure(default_settings=test_settings)
    django.setup()

from tests.models import ConcreteListing


@pytest.fixture(scope="session")
def django_db_setup(django_db_blocker):
    """Set up test database with migrations"""
    from django.core.management import call_command

    with django_db_blocker.unblock():
        call_command("migrate", "--run-syncdb", verbosity=0)


@pytest.fixture
def listing_factory(db):
    """Factory for creating test listings"""

    def create_listing(
        title="Test Listing",
        slug="",
        description="Test description",
        price=Decimal("100.00"),
        location="Test City",
        status="draft",
        **kwargs,
    ):
        listing = ConcreteListing.objects.create(
            title=title,
            slug=slug,
            description=description,
            price=price,
            location=location,
            status=status,
            **kwargs,
        )
        return listing

    return create_listing


@pytest.fixture
def published_listing(listing_factory):
    """Create a published listing"""
    return listing_factory(
        title="Published Listing",
        status="published",
        price=Decimal("250.00"),
        location="New York",
    )


@pytest.fixture
def draft_listing(listing_factory):
    """Create a draft listing"""
    return listing_factory(
        title="Draft Listing",
        status="draft",
        price=Decimal("150.00"),
        location="Los Angeles",
    )


@pytest.fixture
def sold_listing(listing_factory):
    """Create a sold listing"""
    return listing_factory(
        title="Sold Listing",
        status="sold",
        price=Decimal("500.00"),
        location="Chicago",
    )
