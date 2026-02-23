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
    return Form.objects.create(
        title="Contact",
        slug="contact",
        description="Get in touch.",
        success_message="Thank you, we will be in touch.",
        notify_emails="admin@example.com",
        spam_protection_enabled=True,
    )


@pytest.fixture
def inactive_form(db):
    """Inactive form that should not be accessible via public API"""
    return Form.objects.create(
        title="Inactive Form",
        slug="inactive",
        is_active=False,
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
