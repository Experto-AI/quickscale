"""Shared pytest fixtures for the QuickScale billing module."""

from __future__ import annotations

import os

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

# SA14.4: NOBYPASSRLS is the default. Tests that need BYPASSRLS privilege
# (migration DDL) must be explicitly marked with @pytest.mark.bypass_rls.
# The collection hook below skips bypass_rls-marked tests when the env var
# is not set. Set QUICKSCALE_ALLOW_BYPASSRLS=1 in the shell to include them.
# For --ds-managed modules like billing, Django setup happens before this
# conftest runs, so the boot guard already passed — this env var only affects
# the collection hook.

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
