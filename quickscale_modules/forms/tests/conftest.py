"""Shared pytest fixtures for Forms module tests"""

import os
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import django
import pytest
from django.conf import settings

# Configure Django before importing models
if not settings.configured:
    settings_path = Path(__file__).with_name("settings.py")
    settings_module_name = "quickscale_modules_forms_test_settings"
    settings_spec = spec_from_file_location(settings_module_name, settings_path)
    if settings_spec is None or settings_spec.loader is None:
        raise RuntimeError(f"Unable to load forms test settings from {settings_path}")
    test_settings = module_from_spec(settings_spec)
    sys.modules[settings_module_name] = test_settings
    settings_spec.loader.exec_module(test_settings)

    os.environ["DJANGO_SETTINGS_MODULE"] = settings_module_name
    django.setup()


@pytest.fixture(scope="session")
def django_db_setup(django_db_blocker):
    """Set up test database with migrations"""
    from django.core.management import call_command

    with django_db_blocker.unblock():
        call_command("migrate", "--run-syncdb", verbosity=0)


from django.contrib.auth import get_user_model  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402

from quickscale_modules_forms.models import (  # noqa: E402
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
    from quickscale_modules_orgs.current_org import set_current_org_id
    from quickscale_modules_orgs.models import Organization

    system_org = Organization.objects.get_system_org()
    set_current_org_id(system_org.pk)
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
    return FormField.all_objects.create(
        form=form,
        organization=form.organization,
        field_type=FormField.FIELD_TYPE_TEXT,
        label="Name",
        name="full_name",
        required=True,
        order=1,
    )


@pytest.fixture
def email_field(db, form):
    """Email field on the contact form"""
    return FormField.all_objects.create(
        form=form,
        organization=form.organization,
        field_type=FormField.FIELD_TYPE_EMAIL,
        label="Email",
        name="email",
        required=True,
        order=2,
    )


@pytest.fixture
def optional_field(db, form):
    """Optional text field on the contact form"""
    return FormField.all_objects.create(
        form=form,
        organization=form.organization,
        field_type=FormField.FIELD_TYPE_TEXT,
        label="Company",
        name="company",
        required=False,
        order=3,
    )


@pytest.fixture
def submission(db, form):
    """A form submission for the contact form"""
    return FormSubmission.all_objects.create(
        form=form,
        organization=form.organization,
        ip_address="127.0.0.1",
        user_agent="TestBrowser/1.0",
    )


@pytest.fixture
def field_value(db, submission, form_field):
    """A field value snapshot attached to the submission"""
    return FormFieldValue.all_objects.create(
        submission=submission,
        organization=submission.organization,
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
    from quickscale_modules_orgs.current_org import set_current_org_id

    set_current_org_id(org.pk)
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
