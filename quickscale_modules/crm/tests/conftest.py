"""Pytest fixtures for CRM module tests"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from quickscale_modules_crm.models import (
    Company,
    Contact,
    ContactNote,
    Deal,
    DealNote,
    Stage,
    Tag,
)
from quickscale_modules_orgs.constants import ACTIVE_ORG_SESSION_KEY
from quickscale_modules_orgs.current_org import (
    org_scope,
    reset_current_org_id,
    set_current_org_id,
)
from quickscale_modules_orgs.models import (
    OrgRole,
    Organization,
    OrganizationMembership,
)

# shared per-test state reset fixture replaces the private
# ``_reset_crm_test_state`` copy.  See ``tests_shared/reset_state.py``.
from tests_shared.reset_state import reset_test_state  # noqa: F401


@pytest.fixture
def user(db):
    """Create a test user with a personal org (Phase 2: solo routes require org context)."""
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="testuser",
        email="testuser@example.com",
        password="TestPass123!",
    )
    # Phase 2: create personal org for solo route org context.
    from quickscale_modules_orgs.models import Organization

    Organization.objects.create_personal_for(user)
    return user


@pytest.fixture
def staff_user(db):
    """Create a staff test user with a personal org.

    T1.5: sets the org contextvar to the personal org so that TenantManager
    auto-scoping works for model-level tests and serializer queries.
    """
    user_model = get_user_model()
    staff_user = user_model.objects.create_user(
        username="staffuser",
        email="staffuser@example.com",
        password="TestPass123!",
    )
    staff_user.is_staff = True
    staff_user.save(update_fields=["is_staff"])
    Organization.objects.create_personal_for(staff_user)
    # Set contextvar to personal org for TenantManager auto-scoping.
    personal_org = Organization.objects.get(
        is_personal=True, quickscale_orgs_memberships__user=staff_user
    )
    set_current_org_id(personal_org.id)
    return staff_user


@pytest.fixture
def staff_personal_org(staff_user):
    """Return the personal org for the staff user."""
    return Organization.objects.get(
        is_personal=True, quickscale_orgs_memberships__user=staff_user
    )


@pytest.fixture
def superuser(db):
    """Create a Django superuser — the platform operator who accesses /admin/."""
    user_model = get_user_model()
    return user_model.objects.create_superuser(
        username="operator",
        email="operator@example.com",
        password="TestPass123!",
    )


@pytest.fixture
def admin_client(superuser):
    """A Django test client authenticated as the platform-operator superuser."""
    from django.test import Client

    client = Client()
    client.force_login(superuser)
    return client


@pytest.fixture
def api_client():
    """Create an API client"""
    return APIClient()


class OrgEnrichedAPIClient(APIClient):
    """APIClient that sets the session org and ContextVar for org scoping.

    Each request resets the fixture-seeded current-org so ``org_scope``
    enters from a fail-closed baseline (ContextVar=None).  On exit,
    ``org_scope`` restores to None — proving the Python ContextVar, DB GUC,
    and RLS row invisibility are restored after each synthetic request.
    """

    def request(self, **kwargs):
        reset_current_org_id()
        with org_scope(self._personal_org):
            return super().request(**kwargs)


def _org_session_client(user, organization):
    """Build an org-enriched API client for *user* with *organization* active."""
    client = OrgEnrichedAPIClient()
    client.force_login(user)
    session = client.session
    session[ACTIVE_ORG_SESSION_KEY] = str(organization.id)
    session.save()
    client._personal_org = organization
    return client


def _role_user(username: str, role: OrgRole):
    """Create a user whose personal-org membership carries *role*."""
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="TestPass123!",
    )
    organization = Organization.objects.create_personal_for(user)
    OrganizationMembership.objects.filter(user=user, organization=organization).update(
        role=role
    )
    return user, organization


@pytest.fixture
def authenticated_client(staff_user):
    """Create an org-member-authenticated API client with personal org context.

    Uses session-based auth (``force_login``) and sets the active
    org in the session so ``TenantMiddleware`` resolves ``request.org``.
    Also primes the ContextVar for TenantManager auto-scoping at the DB
    level.
    """
    personal_org = Organization.objects.get(
        is_personal=True, quickscale_orgs_memberships__user=staff_user
    )
    return _org_session_client(staff_user, personal_org)


@pytest.fixture
def viewer_client(db):
    """An API client for a user whose only org role is viewer."""
    user, organization = _role_user("crm-viewer", OrgRole.VIEWER)
    return _org_session_client(user, organization)


@pytest.fixture
def member_client(db):
    """An API client for a user whose only org role is member."""
    user, organization = _role_user("crm-member", OrgRole.MEMBER)
    return _org_session_client(user, organization)


@pytest.fixture
def orgless_authenticated_client(user):
    """Create an authenticated API client with no active-organization context.

    ``force_authenticate`` skips the session, so ``TenantMiddleware`` never
    resolves ``request.org``: the org-role permission must fail closed.
    """
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def tag(db, staff_user):
    """Create a test tag stamped with the staff user's personal org (Phase 2).

    Wrapped in ``org_scope`` so the ContextVar and DB GUC are set for the
    duration of the fixture body (FORCE RLS requires ``app.current_org_id``
    to be set for INSERTs under the restricted test role).
    """
    from quickscale_modules_orgs.models import Organization

    personal_org = Organization.objects.get(
        is_personal=True, quickscale_orgs_memberships__user=staff_user
    )
    with org_scope(personal_org):
        return Tag.objects.create(name="VIP", organization=personal_org)


@pytest.fixture
def company(db, staff_user):
    """Create a test company stamped with the staff user's personal org (Phase 2).

    Wrapped in ``org_scope`` so the ContextVar and DB GUC are set for the
    duration of the fixture body (FORCE RLS requires ``app.current_org_id``
    to be set for INSERTs under the restricted test role).
    """
    from quickscale_modules_orgs.models import Organization

    personal_org = Organization.objects.get(
        is_personal=True, quickscale_orgs_memberships__user=staff_user
    )
    with org_scope(personal_org):
        return Company.objects.create(
            name="Acme Corp",
            industry="Technology",
            website="https://acme.example.com",
            organization=personal_org,
        )


@pytest.fixture
def contact(db, company):
    """Create a test contact stamped with the company's org (Phase 2).

    Wrapped in ``org_scope`` so the ContextVar and DB GUC are set for the
    duration of the fixture body (FORCE RLS requires ``app.current_org_id``
    to be set for INSERTs under the restricted test role).
    """

    with org_scope(company.organization):
        return Contact.objects.create(
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            phone="+1234567890",
            title="Sales Manager",
            company=company,
            organization=company.organization,
        )


@pytest.fixture
def stage(db, staff_user):
    """Create a test stage stamped with the staff user's personal org (Phase 2).

    Wrapped in ``org_scope`` so the ContextVar and DB GUC are set for the
    duration of the fixture body (FORCE RLS requires ``app.current_org_id``
    to be set for INSERTs under the restricted test role).
    """
    from quickscale_modules_orgs.models import Organization

    personal_org = Organization.objects.get(
        is_personal=True, quickscale_orgs_memberships__user=staff_user
    )
    with org_scope(personal_org):
        return Stage.objects.create(
            name="Prospecting", order=1, organization=personal_org
        )


@pytest.fixture
def closed_won_stage(db, staff_user):
    """Create Closed-Won stage stamped with personal org (Phase 2).

    Wrapped in ``org_scope`` so the ContextVar and DB GUC are set for the
    duration of the fixture body.
    """
    from quickscale_modules_orgs.models import Organization

    personal_org = Organization.objects.get(
        is_personal=True, quickscale_orgs_memberships__user=staff_user
    )
    with org_scope(personal_org):
        return Stage.objects.create(
            name="Closed-Won", order=3, organization=personal_org
        )


@pytest.fixture
def closed_lost_stage(db, staff_user):
    """Create Closed-Lost stage stamped with personal org (Phase 2).

    Wrapped in ``org_scope`` so the ContextVar and DB GUC are set for the
    duration of the fixture body.
    """
    from quickscale_modules_orgs.models import Organization

    personal_org = Organization.objects.get(
        is_personal=True, quickscale_orgs_memberships__user=staff_user
    )
    with org_scope(personal_org):
        return Stage.objects.create(
            name="Closed-Lost", order=4, organization=personal_org
        )


@pytest.fixture
def deal(db, contact, stage, user):
    """Create a test deal stamped with the contact's org (Phase 2).

    Wrapped in ``org_scope`` so the ContextVar and DB GUC are set for the
    duration of the fixture body (FORCE RLS requires ``app.current_org_id``
    to be set for INSERTs under the restricted test role).
    """

    with org_scope(contact.organization):
        return Deal.objects.create(
            title="Enterprise Deal",
            contact=contact,
            amount=Decimal("50000.00"),
            stage=stage,
            probability=75,
            owner=user,
            organization=contact.organization,
        )


@pytest.fixture
def contact_note(db, contact, user):
    """Create a test contact note

    Wrapped in ``org_scope`` so the ContextVar and DB GUC are set for the
    duration of the fixture body (FORCE RLS requires ``app.current_org_id``
    to be set for INSERTs under the restricted test role).
    """

    with org_scope(contact.organization):
        return ContactNote.objects.create(
            contact=contact,
            created_by=user,
            text="Discussed pricing options",
            organization=contact.organization,
        )


@pytest.fixture
def deal_note(db, deal, user):
    """Create a test deal note

    Wrapped in ``org_scope`` so the ContextVar and DB GUC are set for the
    duration of the fixture body (FORCE RLS requires ``app.current_org_id``
    to be set for INSERTs under the restricted test role).
    """

    with org_scope(deal.organization):
        return DealNote.objects.create(
            deal=deal,
            created_by=user,
            text="Follow up next week",
            organization=deal.organization,
        )


# ---------------------------------------------------------------------------
# Organization-scoped fixtures for cross-tenant isolation coverage
# ---------------------------------------------------------------------------


@pytest.fixture
def org_a(db):
    """Organization A — first tenant in isolation tests."""
    return Organization.objects.create(name="Org A", slug="org-a")


@pytest.fixture
def org_b(db):
    """Organization B — second tenant in isolation tests."""
    return Organization.objects.create(name="Org B", slug="org-b")


@pytest.fixture
def org_a_admin(db, org_a):
    """Staff user who is an admin of Organization A."""
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
# NOBYPASSRLS is the default. Tests that need BYPASSRLS privilege
# (migration DDL) must be explicitly marked with @pytest.mark.bypass_rls.
# The collection hook below deselects bypass_rls-marked tests unless the env var
# is exactly 1. Set QUICKSCALE_ALLOW_BYPASSRLS=1 in the shell to include them.
# For --ds-managed modules like crm, Django setup happens before this
# conftest runs, so the boot guard already passed — this import is only for
# the collection hook.
# ---------------------------------------------------------------------------

import os  # noqa: E402


def pytest_configure(config: pytest.Config) -> None:
    """Register the bypass_rls marker to prevent PytestUnknownMarkWarning."""
    config.addinivalue_line(
        "markers",
        "bypass_rls: test requires BYPASSRLS database privilege "
        "(superuser / migration DDL). Deselected unless QUICKSCALE_ALLOW_BYPASSRLS "
        "is exactly '1'.",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Deselect bypass_rls tests unless QUICKSCALE_ALLOW_BYPASSRLS is exactly "1".

    Under NOBYPASSRLS (the default), migration tests and other
    BYPASSRLS-dependent tests are deselected so the suite passes
    cleanly with a restricted DB role.
    """
    if os.environ.get("QUICKSCALE_ALLOW_BYPASSRLS") == "1":
        return  # Explicit BYPASSRLS authorization — run all tests
    selected: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        if item.get_closest_marker("bypass_rls"):
            deselected.append(item)
        else:
            selected.append(item)
    items[:] = selected
    if deselected:
        config.hook.pytest_deselected(items=deselected)
