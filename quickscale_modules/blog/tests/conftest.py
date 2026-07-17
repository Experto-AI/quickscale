"""Pytest configuration for blog module tests"""

import os
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import django
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model

# SA14.4: NOBYPASSRLS is the default. Tests that need BYPASSRLS privilege
# (migration DDL) must be explicitly marked with @pytest.mark.bypass_rls.
# The collection hook below skips bypass_rls-marked tests when the env var
# is not set. Set QUICKSCALE_ALLOW_BYPASSRLS=1 in the shell to include them.
# This runs before django.setup() below — use a NOBYPASSRLS DB role.

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


@pytest.fixture(scope="session", autouse=True)
def _sa61_media_root_tmp_path(tmp_path_factory):
    """SA61: Redirect MEDIA_ROOT to a pytest-managed temporary directory so
    uploaded test media files are never written into the tracked worktree.
    Individual tests that also override MEDIA_ROOT (e.g. with a function-scoped
    tmp_path) are unaffected — the most recent override wins per-test.
    """
    from django.conf import settings

    settings.MEDIA_ROOT = str(tmp_path_factory.mktemp("media"))


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
def system_org(db):
    """Return the singleton System organization (reserved slug __system__)."""
    from quickscale_modules_orgs.models import Organization

    return Organization.objects.get_system_org()


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


# SA97: shared per-test state reset fixture replaces the private
# ``_reset_current_org_context`` copy.  Blog's previous ContextVar-only
# reset is upgraded to the full superset (GUCs, AF9 memo, cache).
# See ``tests_shared/reset_state.py``.
from tests_shared.reset_state import reset_test_state  # noqa: E402, F401


@pytest.fixture
def blog_org_scope():
    """Expose ``org_scope()`` for blog test use as a context manager.

    Wraps the unified ``org_scope()`` entry point from
    ``quickscale_modules_orgs.current_org`` so blog tests can scope
    data creation and request execution under an explicit org context
    without leaking ``app.current_org_id`` GUC state across role
    boundaries (SA83).
    """
    from quickscale_modules_orgs.current_org import org_scope

    return org_scope


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
