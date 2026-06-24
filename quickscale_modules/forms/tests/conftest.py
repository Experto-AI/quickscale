"""Shared pytest fixtures for Forms module tests"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from quickscale_modules_forms.models import (
    Form,
    FormField,
    FormFieldValue,
    FormSubmission,
)

User = get_user_model()


@pytest.fixture
def user(db):
    """Standard Django user"""
    return User.objects.create_user(
        username="testuser",
        email="testuser@example.com",
        password="testpass123",
    )


@pytest.fixture
def staff_user(db):
    """Staff Django user with admin access"""
    return User.objects.create_user(
        username="staffuser",
        email="staffuser@example.com",
        password="testpass123",
        is_staff=True,
    )


@pytest.fixture
def api_client():
    """DRF API client (unauthenticated)"""
    return APIClient()


@pytest.fixture
def staff_client(api_client, staff_user):
    """DRF API client authenticated as staff user"""
    api_client.force_authenticate(user=staff_user)
    return api_client


@pytest.fixture
def form(db):
    """Active form with notify email set"""
    from quickscale_modules_orgs.models import Organization

    system_org = Organization.objects.get_system_org()
    form, _ = Form.all_objects.update_or_create(
        slug="test-contact",
        defaults={
            "title": "Test Contact",
            "description": "Get in touch.",
            "success_message": "Thank you, we will be in touch.",
            "notify_emails": "admin@example.com",
            "spam_protection_enabled": True,
            "organization": system_org,
        },
    )
    return form


@pytest.fixture
def inactive_form(db):
    """Inactive form that should not be accessible via public API"""
    from quickscale_modules_orgs.models import Organization

    system_org = Organization.objects.get_system_org()
    return Form.all_objects.create(
        title="Inactive Form",
        slug="inactive",
        is_active=False,
        organization=system_org,
    )


@pytest.fixture
def form_field(db, form):
    """Text field on the contact form"""
    return FormField.objects.create(
        form=form,
        field_type=FormField.FIELD_TYPE_TEXT,
        label="Name",
        name="full_name",
        required=True,
        order=1,
    )


@pytest.fixture
def email_field(db, form):
    """Email field on the contact form"""
    return FormField.objects.create(
        form=form,
        field_type=FormField.FIELD_TYPE_EMAIL,
        label="Email",
        name="email",
        required=True,
        order=2,
    )


@pytest.fixture
def optional_field(db, form):
    """Optional text field on the contact form"""
    return FormField.objects.create(
        form=form,
        field_type=FormField.FIELD_TYPE_TEXT,
        label="Company",
        name="company",
        required=False,
        order=3,
    )


@pytest.fixture
def submission(db, form):
    """A form submission for the contact form"""
    return FormSubmission.objects.create(
        form=form,
        ip_address="127.0.0.1",
        user_agent="TestBrowser/1.0",
    )


@pytest.fixture
def field_value(db, submission, form_field):
    """A field value snapshot attached to the submission"""
    return FormFieldValue.objects.create(
        submission=submission,
        field=form_field,
        field_name="full_name",
        field_label="Name",
        value="Alice",
    )


# ---------------------------------------------------------------------------
# Organization fixtures for Phase F11.12a tenant-scoped forms
# ---------------------------------------------------------------------------


@pytest.fixture
def org(db):
    """Create a default test organization for forms model tests."""
    from quickscale_modules_orgs.models import Organization

    return Organization.objects.create(name="Test Org", slug="test-org")


@pytest.fixture
def org_form(db, org):
    """Active form owned by an organization."""
    form, _ = Form.all_objects.update_or_create(
        slug="org-contact",
        defaults={
            "title": "Org Contact",
            "description": "Org contact form.",
            "success_message": "Thank you.",
            "notify_emails": "org@example.com",
            "spam_protection_enabled": True,
            "organization": org,
        },
    )
    return form


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
