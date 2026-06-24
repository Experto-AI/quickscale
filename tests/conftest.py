"""Shared pytest fixtures for the QuickScale billing module."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from quickscale_modules_orgs.models import Organization


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
def organization(db):
    """Return a default organization for billing model tests."""

    return Organization.objects.create(name="TestOrg", slug="test-org")


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
