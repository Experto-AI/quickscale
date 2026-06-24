"""Tests for Forms module models"""

import pytest
from django.db import IntegrityError
from django.test import override_settings

from quickscale_modules_forms.models import Form, FormField, FormSubmission


@pytest.mark.django_db
class TestFormModel:
    """Tests for the Form model"""

    @pytest.fixture(autouse=True)
    def _system_org(self, db):
        """Ensure System org exists for all Form tests."""
        from quickscale_modules_orgs.models import Organization

        return Organization.objects.get_system_org()

    def test_form_str_returns_title(self, _system_org):
        """__str__ returns the form title"""
        form = Form.objects.create(
            title="Test Contact", slug="test-contact", organization=_system_org
        )
        assert str(form) == "Test Contact"

    def test_form_slug_uniqueness_per_org(self):
        """Form slug must be unique within an organization"""
        from quickscale_modules_orgs.models import Organization

        org = Organization.objects.create(name="Test Org", slug="test-org")
        Form.objects.create(title="First", slug="unique-slug", organization=org)
        with pytest.raises(IntegrityError):
            Form.objects.create(title="Second", slug="unique-slug", organization=org)

    def test_form_slug_can_duplicate_across_orgs(self):
        """Same slug is allowed in different organizations"""
        from quickscale_modules_orgs.models import Organization

        org_a = Organization.objects.create(name="Org A", slug="org-a")
        org_b = Organization.objects.create(name="Org B", slug="org-b")
        Form.objects.create(title="First", slug="same-slug", organization=org_a)
        # Should not raise — different orgs
        Form.objects.create(title="Second", slug="same-slug", organization=org_b)

    def test_form_data_retention_days_default_is_365(self, _system_org):
        """data_retention_days defaults to 365"""
        form = Form.objects.create(
            title="Test", slug="test-retention", organization=_system_org
        )
        assert form.data_retention_days == 365

    @override_settings(FORMS_DATA_RETENTION_DAYS=730)
    def test_form_data_retention_days_default_comes_from_setting(self, _system_org):
        """New forms should inherit the settings-backed retention default."""
        form = Form.objects.create(
            title="Configured", slug="configured-retention", organization=_system_org
        )

        assert form.data_retention_days == 730

    @override_settings(FORMS_DATA_RETENTION_DAYS=730)
    def test_form_explicit_data_retention_days_preserves_per_row_value(
        self, _system_org
    ):
        """Explicit per-form retention must win over the global default."""
        form = Form.objects.create(
            title="Explicit",
            slug="explicit-retention",
            data_retention_days=14,
            organization=_system_org,
        )

        assert form.data_retention_days == 14

    def test_form_is_active_defaults_to_true(self, _system_org):
        """is_active defaults to True"""
        form = Form.objects.create(
            title="Test", slug="test-active", organization=_system_org
        )
        assert form.is_active is True

    def test_form_spam_protection_defaults_to_true(self, _system_org):
        """spam_protection_enabled defaults to True"""
        form = Form.objects.create(
            title="Test", slug="test-spam", organization=_system_org
        )
        assert form.spam_protection_enabled is True

    def test_form_success_message_default(self, _system_org):
        """success_message has a sensible default value"""
        form = Form.objects.create(
            title="Test", slug="test-msg", organization=_system_org
        )
        assert "Thank you" in form.success_message


@pytest.mark.django_db
class TestFormFieldModel:
    """Tests for the FormField model"""

    def test_formfield_ordering_by_order(self, form):
        """Fields are ordered by the 'order' field"""
        FormField.objects.create(
            form=form, field_type="text", label="B", name="field_b", order=2
        )
        FormField.objects.create(
            form=form, field_type="text", label="A", name="field_a", order=1
        )
        names = list(form.fields.values_list("name", flat=True))
        assert names == ["field_a", "field_b"]

    def test_formfield_unique_together_form_and_name(self, form):
        """Two fields on the same form cannot share the same name"""
        FormField.objects.create(
            form=form, field_type="text", label="First", name="dup", order=1
        )
        with pytest.raises(IntegrityError):
            FormField.objects.create(
                form=form, field_type="email", label="Second", name="dup", order=2
            )

    def test_formfield_str(self, form, form_field):
        """__str__ returns form title and field label"""
        assert "Test Contact" in str(form_field)
        assert "Name" in str(form_field)

    def test_formfield_is_active_defaults_to_true(self, form):
        """is_active defaults to True"""
        field = FormField.objects.create(
            form=form, field_type="text", label="X", name="x_field", order=1
        )
        assert field.is_active is True


@pytest.mark.django_db
class TestFormSubmissionModel:
    """Tests for the FormSubmission model"""

    def test_formsubmission_default_status_is_pending(self, form):
        """status defaults to 'pending'"""
        submission = FormSubmission.objects.create(form=form)
        assert submission.status == FormSubmission.STATUS_PENDING

    def test_formsubmission_is_spam_defaults_to_false(self, form):
        """is_spam defaults to False"""
        submission = FormSubmission.objects.create(form=form)
        assert submission.is_spam is False

    def test_formsubmission_str(self, submission):
        """__str__ includes submission id and form title"""
        assert str(submission.pk) in str(submission)
        assert "Test Contact" in str(submission)


@pytest.mark.django_db
class TestFormFieldValueModel:
    """Tests for the FormFieldValue model"""

    def test_formfieldvalue_field_set_null_when_field_deleted(
        self, submission, form_field, field_value
    ):
        """When a FormField is deleted, FormFieldValue.field becomes NULL but field_name is preserved"""
        field_name_snapshot = field_value.field_name
        form_field.delete()
        field_value.refresh_from_db()
        assert field_value.field is None
        assert field_value.field_name == field_name_snapshot

    def test_formfieldvalue_str(self, field_value):
        """__str__ includes label and truncated value"""
        result = str(field_value)
        assert "Name" in result
        assert "Alice" in result
