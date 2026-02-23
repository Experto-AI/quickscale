"""Tests for Forms module Django admin configuration"""

import csv
import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.urls import reverse

from quickscale_modules_forms.models import (
    Form,
    FormField,
    FormFieldValue,
    FormSubmission,
)

User = get_user_model()


@pytest.mark.django_db
class TestFormAdminRegistration:
    """Tests for FormAdmin registration and configuration"""

    def test_form_admin_registered(self):
        """Form model is registered with the admin site"""
        assert admin.site.is_registered(Form)

    def test_formsubmission_admin_registered(self):
        """FormSubmission model is registered with the admin site"""
        assert admin.site.is_registered(FormSubmission)

    def test_form_admin_list_display_includes_submission_count(self):
        """submission_count appears in list_display"""
        form_admin = admin.site._registry[Form]
        assert "submission_count" in form_admin.list_display

    def test_form_admin_prepopulated_slug_field(self):
        """slug field is auto-populated from title"""
        form_admin = admin.site._registry[Form]
        assert "slug" in form_admin.prepopulated_fields

    def test_formfield_inline_in_form_admin(self):
        """FormFieldInline is present as inline in FormAdmin"""
        form_admin = admin.site._registry[Form]
        inline_models = [inline.model for inline in form_admin.inlines]
        assert FormField in inline_models

    def test_formfieldvalue_inline_cannot_delete(self):
        """FormFieldValueInline has can_delete=False"""
        sub_admin = admin.site._registry[FormSubmission]
        for inline in sub_admin.inlines:
            if inline.model == FormFieldValue:
                assert inline.can_delete is False
                break
        else:
            pytest.fail("FormFieldValueInline not found in FormSubmissionAdmin")


@pytest.mark.django_db
class TestFormAdminActions:
    """Tests for FormAdmin bulk actions"""

    def test_mark_inactive_action_updates_is_active(self, form):
        """mark_inactive bulk action sets is_active=False on all selected forms"""
        form_admin_instance = admin.site._registry[Form]
        rf = RequestFactory()
        request = rf.get("/admin/")
        request.user = User.objects.create_superuser(
            "admin", "admin@example.com", "adminpass"
        )
        queryset = Form.objects.filter(pk=form.pk)
        form_admin_instance.mark_inactive(request, queryset)
        form.refresh_from_db()
        assert form.is_active is False

    def test_mark_active_action_updates_is_active(self, form):
        """mark_active bulk action sets is_active=True on all selected forms"""
        form.is_active = False
        form.save()
        form_admin_instance = admin.site._registry[Form]
        rf = RequestFactory()
        request = rf.get("/admin/")
        request.user = User.objects.create_superuser(
            "superadmin", "super@example.com", "adminpass"
        )
        queryset = Form.objects.filter(pk=form.pk)
        form_admin_instance.mark_active(request, queryset)
        form.refresh_from_db()
        assert form.is_active is True


@pytest.mark.django_db
class TestFormAdminSaveModel:
    """Tests for save_model override in FormAdmin"""

    def test_save_model_sets_created_by_on_creation(self, form):
        """save_model sets created_by to the request user when creating a new form"""
        user = User.objects.create_superuser(
            "savemodel_admin", "save@example.com", "adminpass"
        )
        form_admin_instance = admin.site._registry[Form]
        rf = RequestFactory()
        request = rf.get("/admin/")
        request.user = user

        new_form = Form(title="New Form", slug="new-form-test")
        # Simulate Django admin save on a new object
        form_admin_instance.save_model(request, new_form, form=None, change=False)
        assert new_form.created_by == user


@pytest.mark.django_db
class TestFormSubmissionAdminActions:
    """Tests for FormSubmissionAdmin bulk actions"""

    def test_mark_as_spam_action(self, submission):
        """mark_as_spam action sets is_spam=True"""
        sub_admin_instance = admin.site._registry[FormSubmission]
        rf = RequestFactory()
        request = rf.get("/admin/")
        request.user = User.objects.create_superuser(
            "spamadmin", "spam@example.com", "adminpass"
        )
        queryset = FormSubmission.objects.filter(pk=submission.pk)
        sub_admin_instance.mark_as_spam(request, queryset)
        submission.refresh_from_db()
        assert submission.is_spam is True

    def test_mark_as_read_action(self, submission):
        """mark_as_read action sets status to 'read'"""
        sub_admin_instance = admin.site._registry[FormSubmission]
        rf = RequestFactory()
        request = rf.get("/admin/")
        request.user = User.objects.create_superuser(
            "readadmin", "read@example.com", "adminpass"
        )
        queryset = FormSubmission.objects.filter(pk=submission.pk)
        sub_admin_instance.mark_as_read(request, queryset)
        submission.refresh_from_db()
        assert submission.status == FormSubmission.STATUS_READ


@pytest.mark.django_db
class TestAdminCsvExportCoverage:
    """Tests for CSV export endpoint coverage in admin-focused test module"""

    def test_csv_export_sets_attachment_filename(
        self, staff_client, form, submission, field_value
    ):
        """CSV export response includes attachment content disposition"""
        url = reverse(
            "quickscale_forms:admin-submission-export", kwargs={"pk": form.pk}
        )
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "attachment; filename=" in response["Content-Disposition"]
        assert f"submissions_{form.pk}_" in response["Content-Disposition"]
        assert response["Content-Disposition"].endswith('.csv"')

    def test_csv_export_contains_expected_header_columns(
        self, staff_client, form, submission, field_value
    ):
        """CSV export contains base columns and dynamic field columns"""
        url = reverse(
            "quickscale_forms:admin-submission-export", kwargs={"pk": form.pk}
        )
        response = staff_client.get(url)

        assert response.status_code == 200
        rows = list(csv.reader(response.content.decode().splitlines()))
        assert rows
        header = rows[0]
        assert header[:5] == ["id", "submitted_at", "status", "is_spam", "ip_address"]
        assert "full_name" in header
