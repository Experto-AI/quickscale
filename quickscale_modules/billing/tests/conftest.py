"""Shared pytest fixtures for the QuickScale billing module."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

# NOBYPASSRLS is the default. Tests that need BYPASSRLS privilege
# (migration DDL) must be explicitly marked with @pytest.mark.bypass_rls.
# The shared collection hook deselects bypass_rls-marked tests unless the env var
# is exactly 1. Set QUICKSCALE_ALLOW_BYPASSRLS=1 in the shell to include them.
# For --ds-managed modules like billing, Django setup happens before this
# conftest runs, so the boot guard already passed — this env var only affects
# the collection hook.

# The bypass_rls marker and its collection-time opt-in come from core's
# conftest plugin (decisions rule 18), so every module suite shares one copy.
from quickscale_core.testing.pytest_plugin import (  # noqa: F401
    pytest_collection_modifyitems,
    pytest_configure,
)
from quickscale_modules_orgs.models import (
    Organization,
    OrganizationMembership,
    OrgRole,
)


@pytest.fixture
def user(db):
    """Return a regular user for billing model tests."""

    user_model = get_user_model()
    return user_model.objects.create_user(
        username="billing-user",
        email="billing-user@example.com",
        password="billingpass123",
    )


@pytest.fixture
def organization(db, user):
    """Return a default organization owned by the billing test user."""

    organization = Organization.objects.create(name="TestOrg", slug="test-org")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.OWNER,
    )
    return organization


@pytest.fixture
def org_context(organization):
    """Set the current org context so TenantManager-scoped queries resolve correctly."""

    from quickscale_modules_orgs.current_org import (
        reset_current_org_id,
        set_current_org_id,
    )

    set_current_org_id(organization.pk)
    yield
    reset_current_org_id()


@pytest.fixture
def superuser(db):
    """Return a superuser for admin tests."""

    user_model = get_user_model()
    return user_model.objects.create_superuser(
        username="billing-admin",
        email="billing-admin@example.com",
        password="adminpass123",
    )


@pytest.fixture
def admin_client(superuser) -> Client:
    """Return an authenticated Django client for admin requests."""

    client = Client()
    client.force_login(superuser)
    return client
