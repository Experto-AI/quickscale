"""Pytest configuration for blog module tests"""

import os
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import django
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model

# Configure Django before importing models
if not settings.configured:
    settings_path = Path(__file__).with_name("settings.py")
    settings_module_name = "quickscale_modules_blog_test_settings"
    settings_spec = spec_from_file_location(settings_module_name, settings_path)
    if settings_spec is None or settings_spec.loader is None:
        raise RuntimeError(f"Unable to load blog test settings from {settings_path}")
    test_settings = module_from_spec(settings_spec)
    sys.modules[settings_module_name] = test_settings
    settings_spec.loader.exec_module(test_settings)

    os.environ["DJANGO_SETTINGS_MODULE"] = settings_module_name
    django.setup()

User = get_user_model()


@pytest.fixture(scope="session")
def django_db_setup(django_db_blocker):
    """Set up test database with migrations"""
    from django.core.management import call_command

    with django_db_blocker.unblock():
        call_command("migrate", "--run-syncdb", verbosity=0)


@pytest.fixture
def user(db):
    """Create a test user with a personal org (SaaS mode)."""
    from quickscale_modules_orgs.models import Organization

    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )
    Organization.objects.create_personal_for(user)
    return user


@pytest.fixture
def author_user(db):
    """Create a test user for blog posts with a personal org (SaaS mode)."""
    from quickscale_modules_orgs.models import Organization

    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="author",
        email="author@example.com",
        password="authorpass123",
        first_name="Test",
        last_name="Author",
    )
    Organization.objects.create_personal_for(user)
    return user


# ---------------------------------------------------------------------------
# Organization fixtures for Phase 1 (F11.11) tenant-scoped blog models
# ---------------------------------------------------------------------------


@pytest.fixture
def org(db):
    """Create a default test organization for blog model tests."""
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
