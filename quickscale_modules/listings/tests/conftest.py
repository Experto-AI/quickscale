"""Pytest configuration for listings module tests"""

from __future__ import annotations

import os
from decimal import Decimal

import django
import pytest
from django.conf import global_settings, settings

# SA14.4: NOBYPASSRLS is the default. Tests that need BYPASSRLS privilege
# (migration DDL) must be explicitly marked with @pytest.mark.bypass_rls.
# The collection hook below skips bypass_rls-marked tests when the env var
# is not set. Set QUICKSCALE_ALLOW_BYPASSRLS=1 in the shell to include them.
# This runs before django.setup() below — use a NOBYPASSRLS DB role.

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
    """Set up test database with migrations.

    Run ``migrate`` first so that all migration-backed apps
    (especially ``quickscale_modules_orgs``) have their tables
    created before the ``--run-syncdb`` step.  Without this
    ordering, ``--run-syncdb`` tries to create the ``tests``
    app's FK-dependent tables (e.g. ``tests_concretelisting``
    referencing ``quickscale_modules_orgs_organization``) before
    the orgs migrations have run, causing:
      ``ProgrammingError: relation "quickscale_modules_orgs_organization" does not exist``
    """
    from django.core.management import call_command

    with django_db_blocker.unblock():
        call_command("migrate", verbosity=0)
        call_command("migrate", "--run-syncdb", verbosity=0)


@pytest.fixture
def listing_factory(db):
    """Factory for creating test listings.

    All listings require an ``organization`` (NOT NULL contract).
    If omitted, the System org is used as the default (D2).
    """
    from quickscale_modules_orgs.models import Organization

    def create_listing(
        title="Test Listing",
        slug="",
        description="Test description",
        price=Decimal("100.00"),
        location="Test City",
        status="draft",
        **kwargs,
    ):
        if "organization" not in kwargs:
            kwargs["organization"] = Organization.objects.get_system_org()
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
# Organization fixtures for tenant-scoped listings
# ---------------------------------------------------------------------------


@pytest.fixture
def system_org(db):
    """Return the singleton System organization (reserved slug __system__)."""
    from quickscale_modules_orgs.models import Organization

    return Organization.objects.get_system_org()


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


# ---------------------------------------------------------------------------
# SA14.4 — bypass_rls marker registration and collection-time opt-in
# ---------------------------------------------------------------------------


def pytest_configure(config: pytest.Config) -> None:
    """Register the bypass_rls marker to prevent PytestUnknownMarkWarning."""
    config.addinivalue_line(
        "markers",
        "bypass_rls: test requires BYPASSRLS database privilege "
        "(superuser / migration DDL). Skipped when QUICKSCALE_ALLOW_BYPASSRLS "
        "is not set.",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip bypass_rls-marked tests when QUICKSCALE_ALLOW_BYPASSRLS is not set.

    Under NOBYPASSRLS (the default), migration tests and other
    BYPASSRLS-dependent tests are deselected so the suite passes
    cleanly with a restricted DB role.
    """
    if os.environ.get("QUICKSCALE_ALLOW_BYPASSRLS") == "1":
        return  # BYPASSRLS available — run all tests
    skip_bypass_rls = pytest.mark.skip(
        reason="QUICKSCALE_ALLOW_BYPASSRLS not set — skipping BYPASSRLS-dependent test"
    )
    for item in items:
        if item.get_closest_marker("bypass_rls"):
            item.add_marker(skip_bypass_rls)
