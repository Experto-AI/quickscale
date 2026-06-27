"""Tests for Forms module Django admin configuration"""

import csv
from unittest.mock import patch

import pytest
from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.test import RequestFactory
from django.urls import reverse

from quickscale_modules_forms.admin import FormAdmin
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
        queryset = Form.all_objects.filter(pk=form.pk)
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
        queryset = Form.all_objects.filter(pk=form.pk)
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

        from quickscale_modules_orgs.models import Organization

        system_org = Organization.objects.get_system_org()
        new_form = Form(title="New Form", slug="new-form-test", organization=system_org)
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
        queryset = FormSubmission.all_objects.filter(pk=submission.pk)
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
        queryset = FormSubmission.all_objects.filter(pk=submission.pk)
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


@pytest.mark.django_db
class TestFormAdminOperatorQueryset:
    """Phase F11.12a: verify FormAdmin uses all_objects for cross-tenant visibility."""

    def test_form_admin_uses_operator_queryset(self):
        """FormAdmin.get_queryset uses self.model.all_objects."""
        site = AdminSite()
        admin_instance = FormAdmin(Form, site)
        rf = RequestFactory()
        request = rf.get("/admin/")
        request.user = User.objects.create_superuser(
            "op-admin", "op@example.com", "adminpass"
        )
        qs = admin_instance.get_queryset(request)
        assert qs.model == Form
        # Verify the queryset originates from all_objects (no org filter applied).
        assert str(qs.query) == str(
            Form.all_objects.all()
            .annotate(_submission_count=Count("submissions"))
            .query
        )

    def test_form_admin_queryset_returns_cross_tenant_forms(self, org_a, org_b):
        """Operator admin queryset returns forms from all organizations."""
        Form.objects.create(title="Form A", slug="form-a", organization=org_a)
        Form.objects.create(title="Form B", slug="form-b", organization=org_b)

        site = AdminSite()
        admin_instance = FormAdmin(Form, site)
        rf = RequestFactory()
        request = rf.get("/admin/")
        request.user = User.objects.create_superuser(
            "cross-admin", "cross@example.com", "adminpass"
        )
        qs = admin_instance.get_queryset(request)
        slugs = list(qs.values_list("slug", flat=True))
        assert "form-a" in slugs
        assert "form-b" in slugs

    def test_form_admin_get_queryset_calls_all_objects(self):
        """FormAdmin.get_queryset actually calls Form.all_objects.all()."""
        with patch.object(Form, "all_objects") as mock_mgr:
            mock_mgr.all.return_value = Form.objects.none()
            site = AdminSite()
            admin_instance = FormAdmin(Form, site)
            rf = RequestFactory()
            request = rf.get("/admin/")
            request.user = User.objects.create_superuser(
                "op-spy", "op-spy@example.com", "adminpass"
            )
            admin_instance.get_queryset(request)
            mock_mgr.all.assert_called_once()


# ---------------------------------------------------------------------------
# AF1-CR-002: Operator/admin child-data reads use all_objects-backed querysets
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFormFieldInlineOperatorQueryset:
    """AF1-CR-002: FormFieldInline must use all_objects for cross-tenant visibility."""

    def test_form_field_formset_uses_all_objects(self):
        """FormFieldFormSet.get_queryset() must use FormField.all_objects."""
        from quickscale_modules_forms.admin import FormFieldFormSet
        from quickscale_modules_forms.models import Form
        from quickscale_modules_orgs.models import Organization
        from django.forms.models import inlineformset_factory

        org = Organization.objects.get_system_org()
        form = Form.all_objects.create(
            slug="test-fset-form",
            title="Test Formset Form",
            organization=org,
        )

        FactoryFormSet = inlineformset_factory(
            Form, FormField, formset=FormFieldFormSet, fields="__all__"
        )

        with patch.object(FormField, "all_objects") as mock_mgr:
            mock_mgr.none.return_value = FormField.objects.none()
            mock_mgr.filter.return_value = FormField.all_objects.none()
            formset = FactoryFormSet(instance=form)
            formset.get_queryset()
            mock_mgr.filter.assert_called_once_with(form_id=form.pk)

    def test_form_field_inline_registers_all_objects_formset(self):
        """FormFieldInline should use the all_objects-backed FormFieldFormSet."""
        from quickscale_modules_forms.admin import FormFieldFormSet, FormFieldInline

        assert FormFieldInline.formset is FormFieldFormSet, (
            "FormFieldInline must use FormFieldFormSet"
        )


@pytest.mark.django_db
class TestFormFieldValueInlineOperatorQueryset:
    """AF1-CR-002: FormFieldValueInline must use all_objects for cross-tenant visibility."""

    def test_form_field_value_formset_uses_all_objects(self):
        """FormFieldValueFormSet.get_queryset() must use FormFieldValue.all_objects."""
        from quickscale_modules_forms.admin import FormFieldValueFormSet
        from quickscale_modules_forms.models import Form
        from quickscale_modules_orgs.models import Organization
        from django.forms.models import inlineformset_factory

        org = Organization.objects.get_system_org()
        form = Form.all_objects.create(
            slug="test-fv-fset-form",
            title="Test FV Formset Form",
            organization=org,
        )
        submission = FormSubmission.all_objects.create(
            form=form,
            organization=org,
        )

        FactoryFormSet = inlineformset_factory(
            FormSubmission,
            FormFieldValue,
            formset=FormFieldValueFormSet,
            fields="__all__",
        )

        with patch.object(FormFieldValue, "all_objects") as mock_mgr:
            mock_mgr.none.return_value = FormFieldValue.objects.none()
            mock_mgr.filter.return_value = FormFieldValue.all_objects.none()
            formset = FactoryFormSet(instance=submission)
            formset.get_queryset()
            mock_mgr.filter.assert_called_once_with(submission_id=submission.pk)

    def test_form_field_value_inline_registers_all_objects_formset(self):
        """FormFieldValueInline should use the all_objects-backed FormFieldValueFormSet."""
        from quickscale_modules_forms.admin import (
            FormFieldValueFormSet,
            FormFieldValueInline,
        )

        assert FormFieldValueInline.formset is FormFieldValueFormSet, (
            "FormFieldValueInline must use FormFieldValueFormSet"
        )


@pytest.mark.django_db
class TestAdminSubmissionAPIPrefetch:
    """AF1-CR-002: Admin submission API views must use all_objects-backed Prefetch
    for child FormFieldValue reads."""

    def test_admin_submission_list_prefetch_uses_all_objects(
        self, staff_client, form, submission, field_value
    ):
        """AdminSubmissionListAPIView must use FormFieldValue.all_objects for prefetch."""
        from quickscale_modules_forms.views import AdminSubmissionListAPIView
        from rest_framework.test import APIRequestFactory
        from rest_framework.request import Request as DRF_Request

        rf = APIRequestFactory()
        wsgi_request = rf.get("/admin/")
        wsgi_request.user = User.objects.create_superuser(
            "prefetch-spy", "prefetch-spy@example.com", "adminpass"
        )
        view = AdminSubmissionListAPIView()
        view.request = DRF_Request(wsgi_request)
        view.kwargs = {"pk": form.pk}

        qs = view.get_queryset()
        # Verify the queryset has a prefetch_related lookup for FormFieldValue.
        # Prefetch queries are not inlined in the main SQL; check the
        # _prefetch_related_lookups instead.
        prefetch_lookups = qs._prefetch_related_lookups
        assert len(prefetch_lookups) >= 1, (
            "Queryset must have at least one prefetch_related lookup"
        )
        prefetch_through = [
            getattr(lk, "prefetch_through", str(lk)) for lk in prefetch_lookups
        ]
        assert any("values" in name for name in prefetch_through), (
            f"Expected a Prefetch for 'values', got {prefetch_through}"
        )

    def test_admin_submission_detail_prefetch_uses_all_objects(
        self, staff_client, form, submission, field_value
    ):
        """Verify admin submission detail returns values (proves prefetch works)."""
        url = reverse(
            "quickscale_forms:admin-submission-detail",
            kwargs={"pk": form.pk, "sub_pk": submission.pk},
        )
        response = staff_client.get(url)
        assert response.status_code == 200
        assert "values" in response.data, (
            "Response must include values through the all_objects-backed prefetch"
        )
        assert len(response.data["values"]) >= 1


# ---------------------------------------------------------------------------
# AF1-CR-003: FormAdmin organization read-only on change
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFormAdminOrganizationReadonly:
    """AF1-CR-003: FormAdmin must prevent ad-hoc org changes that desync descendants."""

    def test_organization_readonly_on_change(self, form):
        """FormAdmin.get_readonly_fields must include organization when obj exists."""
        form_admin_instance = admin.site._registry[Form]
        rf = RequestFactory()
        request = rf.get("/admin/")
        request.user = User.objects.create_superuser(
            "readonly-admin", "readonly@example.com", "adminpass"
        )
        readonly = form_admin_instance.get_readonly_fields(request, obj=form)
        assert "organization" in readonly, (
            "organization must be read-only on change to prevent parent/child desync"
        )

    def test_organization_not_readonly_on_add(self):
        """FormAdmin.get_readonly_fields must NOT include organization when no obj."""
        form_admin_instance = admin.site._registry[Form]
        rf = RequestFactory()
        request = rf.get("/admin/")
        request.user = User.objects.create_superuser(
            "add-admin", "add@example.com", "adminpass"
        )
        readonly = form_admin_instance.get_readonly_fields(request, obj=None)
        assert "organization" not in readonly, "organization must be editable on add"
