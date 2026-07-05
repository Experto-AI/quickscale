"""Shared pytest fixtures for the QuickScale social module."""

from __future__ import annotations

from collections.abc import Iterator, Generator
import os
from pathlib import Path
import sys
from typing import TYPE_CHECKING, Any, cast

import django
import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client

if TYPE_CHECKING:
    from quickscale_modules_orgs.models import Organization
    from quickscale_modules_social.models import SocialEmbed, SocialLink

MODULE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = MODULE_ROOT / "src"

for path in (SRC_ROOT, MODULE_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

# SA14.4: NOBYPASSRLS is the default. Tests that need BYPASSRLS privilege
# (migration DDL) must be explicitly marked with @pytest.mark.bypass_rls.
# The collection hook below skips bypass_rls-marked tests when the env var
# is not set. Set QUICKSCALE_ALLOW_BYPASSRLS=1 in the shell to include them.
# This runs before django.setup() below — use a NOBYPASSRLS DB role.

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")
django.setup()


@pytest.fixture(autouse=True)
def _reset_test_state() -> Iterator[None]:
    """Reset per-test state: cache and ContextVar.

    ContextVars persist across tests within the same thread; this fixture
    clears the org ContextVar before each test so the baseline is always
    ``None`` (fail-closed).
    """
    from quickscale_modules_orgs.current_org import reset_current_org_id

    reset_current_org_id()
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def superuser(db: None) -> Any:
    """Return a superuser for admin tests."""
    user_model = cast(Any, get_user_model())
    return user_model.objects.create_superuser(
        username="social-admin",
        email="social-admin@example.com",
        password="adminpass123",
    )


@pytest.fixture
def admin_client(superuser: Any) -> Client:
    """Return an authenticated Django client for admin requests."""
    client = Client()
    client.force_login(superuser)
    return client


@pytest.fixture
def social_link(db: None) -> SocialLink:
    """Return a published curated social link."""
    return SocialLink.objects.create(
        title="QuickScale on LinkedIn",
        provider_name="",
        url="https://www.linkedin.com/company/quickscale/?utm_source=share",
        description="Company updates and launch notes.",
        display_order=10,
        is_published=True,
    )


@pytest.fixture
def social_embed(db: None) -> SocialEmbed:
    """Return a published curated social embed."""
    return SocialEmbed.objects.create(
        title="QuickScale launch video",
        provider_name="",
        url="https://youtu.be/abc123?si=share",
        description="Launch announcement clip.",
        display_order=5,
        is_published=True,
    )


# ---------------------------------------------------------------------------
# Organization fixtures for Phase F11.13a tenant-scoped social models
# ---------------------------------------------------------------------------


@pytest.fixture
def org(db):
    """Create a default test organization for social model tests."""
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


# ---------------------------------------------------------------------------
# T1.9 — contextvar-based org scoping helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def system_org(db) -> Organization:
    """Return the singleton System organization."""
    from quickscale_modules_orgs.models import Organization

    return Organization.objects.get_system_org()


@pytest.fixture
def org_context(request: Any, db: None) -> Generator[Organization, None, None]:
    """Set the current org context (via ContextVar) for the test duration.

    Usage::

        def test_something(org_context: Organization) -> None:
            # org_context is the org fixture (default Test Org)
            ...

    The context is reset after the test so other tests are not polluted.
    """
    from quickscale_modules_orgs.current_org import set_current_org_id

    org = request.getfixturevalue("org")
    set_current_org_id(org.id)
    yield org
    set_current_org_id(None)


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
