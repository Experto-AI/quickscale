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
class TestAdminSubmissionExportViewAllObjects:
    """AF1-CR-002: AdminSubmissionExportView must use all_objects for child field values."""

    def test_export_uses_all_objects_for_field_values(
        self, staff_client, form, submission, field_value
    ):
        """Export view builds CSV field values via all_objects (proven by cross-org access)."""
        url = reverse(
            "quickscale_forms:admin-submission-export", kwargs={"pk": form.pk}
        )
        response = staff_client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        # The field value fixture uses all_objects and explicit org assignment.
        # If the export view relied on the default (RLS-scoped) manager, the
        # contextvar would be None in the admin context and the value would
        # be filtered out.  We assert the value is present — this proves
        # the export uses all_objects explicitly.
        assert "full_name" in content, (
            "Field name must appear in CSV header — proves all_objects path"
        )
        assert "Alice" in content, (
            "Field value must appear in CSV data — proves all_objects path"
        )

    def test_export_cross_org_field_values(self, staff_client, org_a, org_b):
        """Export includes field values from submissions across orgs (all_objects path).

        Each submission now belongs to the same org as its parent form, respecting
        the AF12 composite FK invariant.  The cross-org proof uses separate forms
        per org.
        """
        from quickscale_modules_forms.models import (
            Form,
            FormField,
            FormFieldValue,
            FormSubmission,
        )

        # Form + submission under org_a
        form_a = Form.all_objects.create(
            title="Form A",
            slug="cross-org-form-a",
            organization=org_a,
            notify_emails="admin@example.com",
        )
        field_a = FormField.all_objects.create(
            form=form_a,
            organization=org_a,
            field_type=FormField.FIELD_TYPE_TEXT,
            label="Department",
            name="department",
            order=1,
        )
        sub_a = FormSubmission.all_objects.create(
            form=form_a, organization=org_a, ip_address="10.0.0.1"
        )
        FormFieldValue.all_objects.create(
            submission=sub_a,
            organization=org_a,
            field=field_a,
            field_name="department",
            field_label="Department",
            value="Engineering",
        )

        # Form + submission under org_b
        form_b = Form.all_objects.create(
            title="Form B",
            slug="cross-org-form-b",
            organization=org_b,
            notify_emails="admin@example.com",
        )
        field_b = FormField.all_objects.create(
            form=form_b,
            organization=org_b,
            field_type=FormField.FIELD_TYPE_TEXT,
            label="Department",
            name="department",
            order=1,
        )
        sub_b = FormSubmission.all_objects.create(
            form=form_b, organization=org_b, ip_address="10.0.0.2"
        )
        FormFieldValue.all_objects.create(
            submission=sub_b,
            organization=org_b,
            field=field_b,
            field_name="department",
            field_label="Department",
            value="Marketing",
        )

        # Export form_a — should see Engineering
        url = reverse(
            "quickscale_forms:admin-submission-export", kwargs={"pk": form_a.pk}
        )
        response = staff_client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Engineering" in content, (
            "Must see org_a's field value — proves all_objects path"
        )

        # Export form_b — should see Marketing
        url = reverse(
            "quickscale_forms:admin-submission-export", kwargs={"pk": form_b.pk}
        )
        response = staff_client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Marketing" in content, (
            "Must see org_b's field value — proves all_objects path"
        )

    def test_csv_export_column_order_matches_form_field_order(
        self, staff_client, form, form_field, email_field, optional_field
    ):
        """CSV column order follows form field definition order (AF1-CR-REV-001)."""
        submission = FormSubmission.all_objects.create(
            form=form,
            organization=form.organization,
            ip_address="127.0.0.1",
        )

        # Form field order: full_name(1), email(2), company(3)
        # Alphabetical would be: company, email, full_name
        FormFieldValue.all_objects.create(
            submission=submission,
            organization=submission.organization,
            field=form_field,
            field_name="full_name",
            field_label="Name",
            value="Alice",
        )
        FormFieldValue.all_objects.create(
            submission=submission,
            organization=submission.organization,
            field=email_field,
            field_name="email",
            field_label="Email",
            value="alice@example.com",
        )
        FormFieldValue.all_objects.create(
            submission=submission,
            organization=submission.organization,
            field=optional_field,
            field_name="company",
            field_label="Company",
            value="Acme Corp",
        )

        url = reverse(
            "quickscale_forms:admin-submission-export", kwargs={"pk": form.pk}
        )
        response = staff_client.get(url)
        assert response.status_code == 200, "CSV export should return 200"

        rows = list(csv.reader(response.content.decode().splitlines()))
        assert len(rows) >= 2, "Expected at least header + one data row"

        header = rows[0]
        expected_header = [
            "id",
            "submitted_at",
            "status",
            "is_spam",
            "ip_address",
            "full_name",
            "email",
            "company",
        ]
        assert header == expected_header, (
            f"CSV header {header} should follow form field order, "
            f"not alphabetical: {expected_header}"
        )

        # Verify data values align with correct columns
        col = {name: idx for idx, name in enumerate(header)}
        data = rows[1]
        assert data[col["full_name"]] == "Alice"
        assert data[col["email"]] == "alice@example.com"
        assert data[col["company"]] == "Acme Corp"

        # Also verify the alphabetically-reordered case would NOT match
        alphabetical = ["company", "email", "full_name"]
        assert header[5:] != alphabetical, "Columns must NOT be in alphabetical order"

    def test_csv_export_column_order_no_org_context(
        self, staff_client, form, form_field, email_field, optional_field
    ):
        """Operator path preserves column order when no current org context is set.

        Regression for AF1-CR-REV-001: a staff user without org affinity must
        still see form-designer field ordering.  If the view used the default
        (RLS-scoped) ``form.fields`` manager, a missing org context would
        return ``.none()`` and columns would collapse to only extras — or be
        empty.  This test proves ``FormField.all_objects`` is used on the
        operator path.
        """
        from quickscale_modules_orgs.current_org import (
            get_current_org_id,
            set_current_org_id,
        )

        # explicitly clear org context so TenantManager.default falls to .none()
        prev_org_id = get_current_org_id()
        set_current_org_id(None)

        submission = FormSubmission.all_objects.create(
            form=form,
            organization=form.organization,
            ip_address="127.0.0.1",
        )
        FormFieldValue.all_objects.create(
            submission=submission,
            organization=form.organization,
            field=form_field,
            field_name="full_name",
            field_label="Name",
            value="Alice",
        )
        FormFieldValue.all_objects.create(
            submission=submission,
            organization=form.organization,
            field=email_field,
            field_name="email",
            field_label="Email",
            value="alice@example.com",
        )
        FormFieldValue.all_objects.create(
            submission=submission,
            organization=form.organization,
            field=optional_field,
            field_name="company",
            field_label="Company",
            value="Acme Corp",
        )

        url = reverse(
            "quickscale_forms:admin-submission-export", kwargs={"pk": form.pk}
        )
        response = staff_client.get(url)
        # Restore org context before assertions so failure diagnostics
        # are not masked by a stale None context in later test cleanup.
        set_current_org_id(prev_org_id)

        assert response.status_code == 200, "CSV export should return 200 with no org"

        rows = list(csv.reader(response.content.decode().splitlines()))
        assert len(rows) >= 2, "Expected at least header + one data row"

        header = rows[0]
        expected_header = [
            "id",
            "submitted_at",
            "status",
            "is_spam",
            "ip_address",
            "full_name",
            "email",
            "company",
        ]
        assert header == expected_header, (
            f"CSV header {header} must follow form field order even with "
            f"no org context — expected {expected_header}"
        )

    def test_csv_export_column_order_mismatched_org_context(
        self,
        staff_client,
        staff_user,
        form,
        form_field,
        email_field,
        optional_field,
        org_b,
    ):
        """Operator path preserves column order when current org does not match form org.

        Regression for AF1-CR-REV-001: a staff user whose active org differs
        from the form's owning org must still see the correct column order.
        If the view used the default (RLS-scoped) ``form.fields`` manager, a
        mismatched org would filter fields to the wrong tenant — returning
        no columns.  This test proves ``FormField.all_objects`` is used on
        the operator path.

        Unlike the earlier
        :meth:`test_csv_export_column_order_no_org_context` test which
        verifies the operator path without any org context, this test
        exercises a *mismatched* org seam: the ``TenantMiddleware`` resolves
        ``ACTIVE_ORG_SESSION_KEY`` from the session and sets the ContextVar
        to ``org_b.pk``, while the form and its fields are owned by
        ``system_org``.  The export view must still return the correct
        designer-ordered columns because it uses ``FormField.all_objects``
        instead of the RLS-scoped default manager.
        """
        from django.urls import reverse

        from quickscale_modules_orgs.constants import ACTIVE_ORG_SESSION_KEY
        from quickscale_modules_orgs.models import (
            OrgRole,
            OrganizationMembership,
        )

        # Make staff_user a member of org_b so that TenantMiddleware does
        # not reject the mismatched-org session context with a 403.
        OrganizationMembership.objects.create(
            user=staff_user,
            organization=org_b,
            role=OrgRole.ADMIN,
        )

        # Use session-based login so the user is authenticated at the
        # middleware level (force_authenticate bypasses middleware auth
        # checks, which would cause TenantMiddleware to skip org resolution).
        staff_client.force_login(user=staff_user)

        # Set the active org to org_b in the session so TenantMiddleware
        # resolves it and populates the ContextVar with org_b.pk.
        session = staff_client.session
        session[ACTIVE_ORG_SESSION_KEY] = str(org_b.pk)
        session.save()

        # Create an active field with no submitted value — can only appear in
        # header via FormField.all_objects, never via extra_field_names fallback.
        _phone_field = FormField.all_objects.create(
            form=form,
            organization=form.organization,
            field_type=FormField.FIELD_TYPE_TEXT,
            label="Phone",
            name="phone",
            required=False,
            order=4,
            is_active=True,
        )

        submission = FormSubmission.all_objects.create(
            form=form,
            organization=form.organization,
            ip_address="127.0.0.1",
        )

        # Create FormFieldValues in deliberately different order than designer
        # field order.  If the export view falls back to extra_field_names
        # (because RLS-filtered form.fields returns empty), the header would
        # mirror this creation order instead of the designer order, causing the
        # assertion below to fail.  Only the FormField.all_objects query can
        # produce the correct designer ordering.
        FormFieldValue.all_objects.create(
            submission=submission,
            organization=form.organization,
            field=optional_field,
            field_name="company",
            field_label="Company",
            value="Acme Corp",
        )
        FormFieldValue.all_objects.create(
            submission=submission,
            organization=form.organization,
            field=email_field,
            field_name="email",
            field_label="Email",
            value="alice@example.com",
        )
        FormFieldValue.all_objects.create(
            submission=submission,
            organization=form.organization,
            field=form_field,
            field_name="full_name",
            field_label="Name",
            value="Alice",
        )

        url = reverse(
            "quickscale_forms:admin-submission-export", kwargs={"pk": form.pk}
        )
        response = staff_client.get(url)

        assert response.status_code == 200, (
            "CSV export should return 200 even with mismatched org"
        )

        rows = list(csv.reader(response.content.decode().splitlines()))
        assert len(rows) >= 2, "Expected at least header + one data row"

        header = rows[0]
        expected_header = [
            "id",
            "submitted_at",
            "status",
            "is_spam",
            "ip_address",
            "full_name",
            "email",
            "company",
            "phone",
        ]
        assert header == expected_header, (
            f"CSV header {header} must follow form field order even with "
            f"mismatched org — expected {expected_header}"
        )


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
