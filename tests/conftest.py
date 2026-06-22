"""Pytest configuration for listings module tests"""

from decimal import Decimal

import django
import pytest
from django.conf import global_settings, settings

# Configure Django before importing models
if not settings.configured:
    from tests import settings as test_settings

    overrides = {
        name: getattr(test_settings, name)
        for name in dir(test_settings)
        if name.isupper()
    }
    settings.configure(default_settings=global_settings, **overrides)
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


# ---------------------------------------------------------------------------
# Organization fixtures for Phase F11.12b tenant-scoped listings
# ---------------------------------------------------------------------------


@pytest.fixture
def org(db):
    """Create a default test organization for listings model tests."""
    from quickscale_modules_orgs.models import Organization

    return Organization.objects.create(name="Test Org", slug="test-org")


@pytest.fixture
def org_a(db):
    """Organization A — first tenant in isolation tests."""
    from quickscale_modules_orgs.models import Organization

    return Organization.objects.create(name="Org A", slug="org-a")


@pytest.fixture
def org_b(db):
    """Organization B — second tenant in isolation tests."""
    from quickscale_modules_orgs.models import Organization

    return Organization.objects.create(name="Org B", slug="org-b")


@pytest.fixture
def org_a_admin(db, org_a):
    """Staff user who is an admin of Organization A."""
    from django.contrib.auth import get_user_model

    from quickscale_modules_orgs.models import (
        OrgRole,
        OrganizationMembership,
    )

    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="org-a-admin",
        email="org-a-admin@example.com",
        password="TestPass123!",
        is_staff=True,
    )
    OrganizationMembership.objects.create(
        user=user,
        organization=org_a,
        role=OrgRole.ADMIN,
    )
    return user


@pytest.fixture
def org_b_admin(db, org_b):
    """Staff user who is an admin of Organization B."""
    from django.contrib.auth import get_user_model

    from quickscale_modules_orgs.models import (
        OrgRole,
        OrganizationMembership,
    )

    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="org-b-admin",
        email="org-b-admin@example.com",
        password="TestPass123!",
        is_staff=True,
    )
    OrganizationMembership.objects.create(
        user=user,
        organization=org_b,
        role=OrgRole.ADMIN,
    )
    return user
