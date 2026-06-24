"""Pytest fixtures for CRM module tests"""

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
from quickscale_modules_orgs.current_org import (
    reset_current_org_id,
    set_current_org_id,
)
from quickscale_modules_orgs.models import (
    OrgRole,
    Organization,
    OrganizationMembership,
)


@pytest.fixture(autouse=True)
def _reset_crm_org_contextvar() -> None:
    """Reset the org contextvar before each test to prevent cross-test leakage."""
    reset_current_org_id()


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
        is_personal=True, memberships__user=staff_user
    )
    set_current_org_id(personal_org.id)
    return staff_user


@pytest.fixture
def staff_personal_org(staff_user):
    """Return the personal org for the staff user."""
    return Organization.objects.get(is_personal=True, memberships__user=staff_user)


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


@pytest.fixture
def authenticated_client(staff_user):
    """Create a staff-authenticated API client with personal org context.

    T1.5: sets the org contextvar before each request so that TenantManager
    auto-scoping works correctly even without middleware.
    """
    from quickscale_modules_orgs.models import Organization

    personal_org = Organization.objects.get(
        is_personal=True, memberships__user=staff_user
    )
    personal_org_id = personal_org.id

    class OrgEnrichedAPIClient(APIClient):
        """APIClient that sets contextvar for TenantManager auto-scoping."""

        def request(self, **kwargs):
            set_current_org_id(personal_org_id)
            try:
                return super().request(**kwargs)
            finally:
                reset_current_org_id()

    client = OrgEnrichedAPIClient()
    client.force_authenticate(user=staff_user)
    client._personal_org = personal_org
    return client


@pytest.fixture
def non_staff_authenticated_client(user):
    """Create a non-staff authenticated API client"""
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def tag(db, staff_user):
    """Create a test tag stamped with the staff user's personal org (Phase 2)."""
    from quickscale_modules_orgs.models import Organization

    personal_org = Organization.objects.get(
        is_personal=True, memberships__user=staff_user
    )
    return Tag.objects.create(name="VIP", organization=personal_org)


@pytest.fixture
def company(db, staff_user):
    """Create a test company stamped with the staff user's personal org (Phase 2)."""
    from quickscale_modules_orgs.models import Organization

    personal_org = Organization.objects.get(
        is_personal=True, memberships__user=staff_user
    )
    return Company.objects.create(
        name="Acme Corp",
        industry="Technology",
        website="https://acme.example.com",
        organization=personal_org,
    )


@pytest.fixture
def contact(db, company):
    """Create a test contact stamped with the company's org (Phase 2)."""
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
    """Create a test stage stamped with the staff user's personal org (Phase 2)."""
    from quickscale_modules_orgs.models import Organization

    personal_org = Organization.objects.get(
        is_personal=True, memberships__user=staff_user
    )
    return Stage.objects.create(name="Prospecting", order=1, organization=personal_org)


@pytest.fixture
def closed_won_stage(db, staff_user):
    """Create Closed-Won stage stamped with personal org (Phase 2)."""
    from quickscale_modules_orgs.models import Organization

    personal_org = Organization.objects.get(
        is_personal=True, memberships__user=staff_user
    )
    return Stage.objects.create(name="Closed-Won", order=3, organization=personal_org)


@pytest.fixture
def closed_lost_stage(db, staff_user):
    """Create Closed-Lost stage stamped with personal org (Phase 2)."""
    from quickscale_modules_orgs.models import Organization

    personal_org = Organization.objects.get(
        is_personal=True, memberships__user=staff_user
    )
    return Stage.objects.create(name="Closed-Lost", order=4, organization=personal_org)


@pytest.fixture
def deal(db, contact, stage, user):
    """Create a test deal stamped with the contact's org (Phase 2)."""
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
    """Create a test contact note"""
    return ContactNote.objects.create(
        contact=contact,
        created_by=user,
        text="Discussed pricing options",
    )


@pytest.fixture
def deal_note(db, deal, user):
    """Create a test deal note"""
    return DealNote.objects.create(
        deal=deal,
        created_by=user,
        text="Follow up next week",
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
