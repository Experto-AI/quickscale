"""Shared pytest fixtures for Forms module tests"""

from __future__ import annotations

import os
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import django
import pytest
from django.conf import settings

# SA14.4: NOBYPASSRLS is the default. Tests that need BYPASSRLS privilege
# (migration DDL) must be explicitly marked with @pytest.mark.bypass_rls.
# The collection hook below skips bypass_rls-marked tests when the env var
# is not set. Set QUICKSCALE_ALLOW_BYPASSRLS=1 in the shell to include them.
# This runs before django.setup() below — use a NOBYPASSRLS DB role.

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


# SA97: shared per-test state reset fixture replaces the private
# ``_reset_test_state`` copy.  See ``tests_shared/reset_state.py``.
from tests_shared.reset_state import reset_test_state  # noqa: E402, F401


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
    """Staff Django user with admin access (not a superuser).

    This fixture provides a plain staff user for view-unit defense-in-depth
    tests (CR-SA85-REV-001).  Session-parity proofs that exercise the real
    middleware pipeline use ``force_login`` + ``ACTIVE_ORG_SESSION_KEY``
    instead.
    """
    return User.objects.create_user(
        username="staffuser",
        email="staffuser@example.com",
        password="testpass123",
        is_staff=True,
    )


@pytest.fixture
def superuser(db):
    """Superuser with Django admin access.

    SA85 Phase 4: superuser is the only role permitted cross-tenant SELECT
    via ``operator_access``.
    """
    return User.objects.create_user(
        username="superuser",
        email="superuser@example.com",
        password="testpass123",
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def api_client():
    """DRF API client (unauthenticated)"""
    return APIClient()


@pytest.fixture
def staff_client(api_client, staff_user):
    """DRF API client authenticated as staff user (non-superuser).

    Uses ``force_authenticate`` (DRF-only, no session middleware).
    This is a view-unit defense-in-depth fixture (CR-SA85-REV-001).
    Session-parity proofs that exercise the real middleware pipeline
    use ``force_login`` + ``ACTIVE_ORG_SESSION_KEY`` instead.
    """
    api_client.force_authenticate(user=staff_user)
    return api_client


@pytest.fixture
def superuser_client(api_client, superuser):
    """DRF API client authenticated as superuser.

    SA85 Phase 4: use this fixture for tests that verify cross-tenant
    read access via ``operator_access``.
    """
    api_client.force_authenticate(user=superuser)
    return api_client


@pytest.fixture
def form(db):
    """Active form with notify email set.

    Wrapped in ``org_scope`` so the ContextVar and DB GUC are set only
    for the duration of the fixture body and cleaned up before the
    fixture returns — test bodies do not inherit fixture-held org context
    (SA85 Phase 1).
    """
    from quickscale_modules_orgs.current_org import org_scope
    from quickscale_modules_orgs.models import Organization

    system_org = Organization.objects.get_system_org()
    with org_scope(system_org):
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
    """Inactive form that should not be accessible via public API.

    Wrapped in ``org_scope`` so the ContextVar and DB GUC are set only
    for the duration of the fixture body and cleaned up before the
    fixture returns (SA85 Phase 1).
    """
    from quickscale_modules_orgs.current_org import org_scope
    from quickscale_modules_orgs.models import Organization

    system_org = Organization.objects.get_system_org()
    with org_scope(system_org):
        return Form.all_objects.create(
            title="Inactive Form",
            slug="inactive",
            is_active=False,
            organization=system_org,
        )


@pytest.fixture
def form_field(db, form):
    """Text field on the contact form.

    Wrapped in ``org_scope`` so the ContextVar and DB GUC are set only
    for the duration of the fixture body (SA85 Phase 1).
    """
    from quickscale_modules_orgs.current_org import org_scope

    with org_scope(form.organization):
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
    """Email field on the contact form.

    Wrapped in ``org_scope`` so the ContextVar and DB GUC are set only
    for the duration of the fixture body (SA85 Phase 1).
    """
    from quickscale_modules_orgs.current_org import org_scope

    with org_scope(form.organization):
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
    """Optional text field on the contact form.

    Wrapped in ``org_scope`` so the ContextVar and DB GUC are set only
    for the duration of the fixture body (SA85 Phase 1).
    """
    from quickscale_modules_orgs.current_org import org_scope

    with org_scope(form.organization):
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
    """A form submission for the contact form.

    Wrapped in ``org_scope`` so the ContextVar and DB GUC are set only
    for the duration of the fixture body (SA85 Phase 1).
    """
    from quickscale_modules_orgs.current_org import org_scope

    with org_scope(form.organization):
        return FormSubmission.all_objects.create(
            form=form,
            organization=form.organization,
            ip_address="127.0.0.1",
            user_agent="TestBrowser/1.0",
        )


@pytest.fixture
def field_value(db, submission, form_field):
    """A field value snapshot attached to the submission.

    Wrapped in ``org_scope`` so the ContextVar and DB GUC are set only
    for the duration of the fixture body (SA85 Phase 1).
    """
    from quickscale_modules_orgs.current_org import org_scope

    with org_scope(submission.organization):
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
    """Active form owned by an organization.

    Wrapped in ``org_scope`` so the ContextVar and DB GUC are set only
    for the duration of the fixture body (SA85 Phase 1).
    """
    from quickscale_modules_orgs.current_org import org_scope

    with org_scope(org):
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
