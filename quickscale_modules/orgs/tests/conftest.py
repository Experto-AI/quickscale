"""Shared pytest fixtures for the QuickScale organizations module.

This conftest provides organization fixtures used across orgs test files.
It also exposes a ``superuser`` and ``admin_client`` fixture for admin tests.

The test runner uses ``--ds=tests.settings`` via pytest-django, so Django
setup is handled by the test framework — no manual ``django.setup()`` needed
here.
"""

from __future__ import annotations

import os

from collections.abc import Iterator
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client

# SA14.4: NOBYPASSRLS is the default. Tests that need BYPASSRLS privilege
# (migration DDL) must be explicitly marked with @pytest.mark.bypass_rls.
# The collection hook below skips bypass_rls-marked tests when the env var
# is not set. Set QUICKSCALE_ALLOW_BYPASSRLS=1 in the shell to include them.
#
# NOTE: For modules that use pytest-django's --ds flag (like orgs), the
# conftest module-level code runs after Django setup. The boot guard already
# ran during setup — use a restricted (NOBYPASSRLS) DB role for testing.

from quickscale_modules_orgs.current_org import reset_current_org_id


@pytest.fixture(autouse=True)
def _reset_test_state() -> Iterator[None]:
    """Reset per-test state: ContextVar and cache.

    ContextVars persist across tests within the same thread; this fixture
    clears the org ContextVar before each test so the baseline is always
    ``None`` (fail-closed).
    """
    reset_current_org_id()
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def superuser(db: None) -> Any:
    """Return a superuser for admin tests."""
    user_model = cast(Any, get_user_model())
    return user_model.objects.create_superuser(
        username="orgs-admin",
        email="orgs-admin@example.com",
        password="adminpass123",
    )


@pytest.fixture
def admin_client(superuser: Any) -> Client:
    """Return an authenticated Django client for admin requests."""
    client = Client()
    client.force_login(superuser)
    return client


# ---------------------------------------------------------------------------
# Organization fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def org(db: None) -> Any:
    """Create a default test organization."""
    from quickscale_modules_orgs.models import Organization

    return Organization.objects.create(name="Test Org", slug="test-org")


@pytest.fixture
def org_a(db: None) -> Any:
    """Organization A — first tenant in isolation tests."""
    from quickscale_modules_orgs.models import Organization

    return Organization.objects.create(name="Org A", slug="org-a")


@pytest.fixture
def org_b(db: None) -> Any:
    """Organization B — second tenant in isolation tests."""
    from quickscale_modules_orgs.models import Organization

    return Organization.objects.create(name="Org B", slug="org-b")


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
