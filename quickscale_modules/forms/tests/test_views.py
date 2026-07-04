"""Tests for Forms module views"""

import csv
import io
from unittest.mock import Mock

import pytest
from django.core.cache import cache
from django.core import mail
from django.test import override_settings
from django.urls import reverse

from quickscale_modules_forms.models import (
    FormFieldValue,
    FormSubmission,
)


@pytest.fixture(autouse=True)
def clear_forms_test_cache():
    """Keep throttle-backed API tests isolated across the module."""
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestFormSchemaAPIView:
    """Tests for the public GET /api/forms/{slug}/ endpoint"""

    def test_returns_200_for_valid_active_slug(self, api_client, form, form_field):
        """Active form returns 200 with schema data"""
        url = reverse("quickscale_forms:form-schema", kwargs={"slug": "test-contact"})
        response = api_client.get(url)
        assert response.status_code == 200
        assert response.data["slug"] == "test-contact"

    def test_returns_404_for_unknown_slug(self, api_client):
        """Non-existent slug returns 404"""
        url = reverse("quickscale_forms:form-schema", kwargs={"slug": "does-not-exist"})
        response = api_client.get(url)
        assert response.status_code == 404

    def test_returns_404_for_inactive_form(self, api_client, inactive_form):
        """Inactive form returns 404 on the public endpoint"""
        url = reverse("quickscale_forms:form-schema", kwargs={"slug": "inactive"})
        response = api_client.get(url)
        assert response.status_code == 404

    def test_injects_honeypot_marker_in_schema(self, api_client, form, form_field):
        """Schema response includes hidden _hp_name marker when spam protection is enabled"""
        url = reverse("quickscale_forms:form-schema", kwargs={"slug": "test-contact"})
        response = api_client.get(url)
        assert response.status_code == 200
        field_names = [field["name"] for field in response.data["fields"]]
        assert "_hp_name" in field_names

    @override_settings(FORMS_SPAM_PROTECTION=False)
    def test_omits_honeypot_marker_when_global_spam_protection_disabled(
        self, api_client, form, form_field
    ):
        """Schema should not advertise honeypot when global spam protection is off."""
        url = reverse("quickscale_forms:form-schema", kwargs={"slug": "test-contact"})

        response = api_client.get(url)

        assert response.status_code == 200
        field_names = [field["name"] for field in response.data["fields"]]
        assert "_hp_name" not in field_names

    def test_omits_honeypot_marker_when_form_spam_protection_disabled(
        self, api_client, form, form_field
    ):
        """Schema should not advertise honeypot when the form-level flag is off."""
        form.spam_protection_enabled = False
        form.save(update_fields=["spam_protection_enabled"])
        url = reverse("quickscale_forms:form-schema", kwargs={"slug": "test-contact"})

        response = api_client.get(url)

        assert response.status_code == 200
        field_names = [field["name"] for field in response.data["fields"]]
        assert "_hp_name" not in field_names


@pytest.mark.django_db
class TestFormSubmitAPIView:
    """Tests for the public POST /api/forms/{slug}/submit/ endpoint"""

    def test_returns_201_on_valid_submission(
        self, api_client, form, form_field, email_field
    ):
        """Valid submission returns 201 with success message"""
        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}
        response = api_client.post(url, data=data, format="json")
        assert response.status_code == 201
        assert "message" in response.data

    def test_returns_400_on_missing_required_field(
        self, api_client, form, form_field, email_field
    ):
        """Missing required field returns 400 with field errors"""
        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice"}  # missing email
        response = api_client.post(url, data=data, format="json")
        assert response.status_code == 400
        assert "errors" in response.data

    def test_honeypot_silently_marks_spam_and_returns_201(
        self, api_client, form, form_field, email_field
    ):
        """Filled honeypot field is treated as spam — returns 201 silently"""
        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Bot", "email": "bot@spam.com", "_hp_name": "I am a bot"}
        response = api_client.post(url, data=data, format="json")
        assert response.status_code == 201
        # The submission is marked as spam in the DB
        submission = FormSubmission.all_objects.filter(form=form).latest("submitted_at")
        assert submission.is_spam is True

    @override_settings(FORMS_SPAM_PROTECTION=False)
    def test_honeypot_is_ignored_when_global_spam_protection_disabled(
        self, api_client, form, form_field, email_field
    ):
        """Submission handling should ignore honeypot when global spam protection is off."""
        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com", "_hp_name": "bot"}

        response = api_client.post(url, data=data, format="json")

        assert response.status_code == 201
        submission = FormSubmission.all_objects.filter(form=form).latest("submitted_at")
        assert submission.is_spam is False

    def test_honeypot_is_ignored_when_form_spam_protection_disabled(
        self, api_client, form, form_field, email_field
    ):
        """Submission handling should ignore honeypot when the form-level flag is off."""
        form.spam_protection_enabled = False
        form.save(update_fields=["spam_protection_enabled"])
        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com", "_hp_name": "bot"}

        response = api_client.post(url, data=data, format="json")

        assert response.status_code == 201
        submission = FormSubmission.all_objects.filter(form=form).latest("submitted_at")
        assert submission.is_spam is False

    def test_returns_404_for_inactive_form(self, api_client, inactive_form):
        """Submit to inactive form returns 404"""
        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "inactive"})
        response = api_client.post(url, data={}, format="json")
        assert response.status_code == 404

    def test_creates_submission_and_field_values(
        self, api_client, form, form_field, email_field
    ):
        """Valid submission creates a FormSubmission and FormFieldValue records"""
        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}
        api_client.post(url, data=data, format="json")
        sub = FormSubmission.all_objects.filter(form=form).first()
        assert sub is not None
        # NOTE: sub.values uses TenantManager which scopes to the org contextvar.
        # The tenant_context() context manager in the view restores the contextvar
        # to None after the request, so use all_objects for the assertion.
        assert FormFieldValue.all_objects.filter(
            submission=sub, field_name="full_name"
        ).exists()

    @override_settings(QUICKSCALE_ANALYTICS_ENABLED=True)
    def test_submission_captures_analytics_when_available(
        self, api_client, form, form_field, email_field, monkeypatch
    ):
        """Successful submissions should call the guarded analytics helper when present."""

        def analytics_is_installed(app_label: str) -> bool:
            return app_label == "quickscale_modules_analytics"

        mock_get_distinct_id = Mock(return_value="session:test-visitor")
        mock_capture_form_submit = Mock()

        monkeypatch.setattr(
            "quickscale_modules_forms.views.apps.is_installed",
            analytics_is_installed,
        )
        monkeypatch.setattr(
            "quickscale_modules_analytics.services.get_distinct_id",
            mock_get_distinct_id,
        )
        monkeypatch.setattr(
            "quickscale_modules_analytics.services.capture_form_submit",
            mock_capture_form_submit,
        )

        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}

        cache.clear()
        response = api_client.post(url, data=data, format="json")
        cache.clear()

        assert response.status_code == 201
        mock_get_distinct_id.assert_called_once()
        mock_capture_form_submit.assert_called_once_with(
            "session:test-visitor",
            form.pk,
            form.title,
            extra={"form_slug": form.slug},
        )

    @override_settings(QUICKSCALE_ANALYTICS_ENABLED=False)
    def test_submission_skips_analytics_when_disabled_but_installed_and_env_present(
        self,
        api_client,
        form,
        form_field,
        email_field,
        monkeypatch,
    ):
        """Disabled analytics must not call services even when the package remains installed."""

        def analytics_is_installed(app_label: str) -> bool:
            return app_label == "quickscale_modules_analytics"

        mock_capture = Mock()
        monkeypatch.setattr(
            "quickscale_modules_forms.views.apps.is_installed",
            analytics_is_installed,
        )
        monkeypatch.setattr(
            "quickscale_modules_analytics.services.capture_form_submit",
            mock_capture,
        )

        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}

        cache.clear()
        response = api_client.post(url, data=data, format="json")
        cache.clear()

        assert response.status_code == 201
        assert FormSubmission.all_objects.filter(form=form).count() == 1
        mock_capture.assert_not_called()

    def test_submission_succeeds_without_analytics_installed(
        self, api_client, form, form_field, email_field, monkeypatch
    ):
        """Prove forms submits cleanly when analytics is absent from the
        Python path / not installed.  _capture_submission_analytics()
        short-circuits via the apps.is_installed guard; no analytics
        symbols are imported or resolved.

        CR-SA17.7-002 (resolved): Replaces the analytics services
        submodule in sys.modules with an import-seam sentinel.  If the
        guard were bypassed or broken, the lazy import
        ``from quickscale_modules_analytics.services import ...``
        would trigger the sentinel's __getattr__, raising
        ModuleNotFoundError OUTSIDE the except Exception boundary —
        proving the guard correctly prevents the import under the
        absent-analytics condition.
        """
        import sys

        # Replace the analytics services submodule in sys.modules with
        # a sentinel that raises ModuleNotFoundError on any attribute
        # access.  monkeypatch.setitem restores the original module
        # on teardown so other tests are unaffected.
        # NOTE: Using monkeypatch.setitem (not setattr with a dotted
        # path) avoids auto-importing the real analytics module.
        class _ImportBlocker:
            """Raises ModuleNotFoundError when accessed — proving the
            lazy import seam was reached despite the guard."""

            __slots__ = ()

            def __getattr__(self, name):
                raise ModuleNotFoundError(
                    "quickscale_modules_analytics.services blocked — "
                    "guard would have been bypassed"
                )

        monkeypatch.setitem(
            sys.modules,
            "quickscale_modules_analytics.services",
            _ImportBlocker(),
        )

        # Patch is_installed to simulate analytics not being a Django
        # app.  Use direct module-object monkeypatch (NOT dotted-path)
        # to avoid triggering an auto-import of analytics.
        import quickscale_modules_forms.views as _forms_views

        monkeypatch.setattr(
            _forms_views.apps,
            "is_installed",
            lambda label: False,
        )

        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}

        cache.clear()
        response = api_client.post(url, data=data, format="json")
        cache.clear()

        assert response.status_code == 201
        assert FormSubmission.all_objects.filter(form=form).count() == 1

    @override_settings(QUICKSCALE_ANALYTICS_ENABLED=True)
    def test_submission_stays_non_blocking_when_analytics_capture_fails(
        self, api_client, form, form_field, email_field, monkeypatch
    ):
        """Analytics capture failure must not block the public success response."""

        def analytics_is_installed(app_label: str) -> bool:
            return app_label == "quickscale_modules_analytics"

        mock_get_distinct_id = Mock(return_value="session:test-visitor")
        mock_capture_form_submit = Mock(side_effect=RuntimeError("posthog unavailable"))

        monkeypatch.setattr(
            "quickscale_modules_forms.views.apps.is_installed",
            analytics_is_installed,
        )
        monkeypatch.setattr(
            "quickscale_modules_analytics.services.get_distinct_id",
            mock_get_distinct_id,
        )
        monkeypatch.setattr(
            "quickscale_modules_analytics.services.capture_form_submit",
            mock_capture_form_submit,
        )

        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}

        cache.clear()
        response = api_client.post(url, data=data, format="json")
        cache.clear()

        assert response.status_code == 201
        assert FormSubmission.all_objects.filter(form=form).count() == 1

    def test_submission_persists_when_notification_delivery_fails(
        self, api_client, form, form_field, email_field, monkeypatch
    ):
        """Delivery failure stays non-blocking and does not roll back persistence"""

        def failing_send(*args, **kwargs):
            raise Exception("SMTP connection refused")

        monkeypatch.setattr(
            "quickscale_modules_forms.notifications.EmailMultiAlternatives.send",
            failing_send,
        )

        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}

        cache.clear()

        response = api_client.post(url, data=data, format="json")

        cache.clear()

        assert response.status_code == 201
        assert FormSubmission.all_objects.filter(form=form).count() == 1
        sub = FormSubmission.all_objects.get(form=form)
        assert FormFieldValue.all_objects.filter(
            submission=sub,
            field_name="full_name",
            value="Alice",
        ).exists()

    @override_settings(QUICKSCALE_NOTIFICATIONS_ENABLED=False)
    def test_submission_uses_untracked_email_when_notifications_installed_but_disabled(
        self,
        api_client,
        form,
        form_field,
        email_field,
        monkeypatch,
    ):
        """Disabled tracked notifications fall back to untracked email after submit"""

        def notifications_are_installed(app_label: str) -> bool:
            return app_label == "quickscale_modules_notifications"

        def fail_import(module_path: str):
            raise AssertionError(
                "tracked notifications service should not load when disabled"
            )

        monkeypatch.setattr(
            "quickscale_modules_forms.notifications.apps.is_installed",
            notifications_are_installed,
        )
        monkeypatch.setattr(
            "quickscale_modules_forms.notifications.import_module",
            fail_import,
        )

        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}

        cache.clear()
        response = api_client.post(url, data=data, format="json")
        cache.clear()

        assert response.status_code == 201
        assert FormSubmission.all_objects.filter(form=form).count() == 1
        assert len(mail.outbox) == 1
        assert "admin@example.com" in mail.outbox[0].recipients()

    @override_settings(FORMS_RATE_LIMIT="2/minute")
    def test_returns_429_when_rate_limit_exceeded(
        self, api_client, form, form_field, email_field
    ):
        """Submit endpoint returns 429 after configured FORMS_RATE_LIMIT is exceeded"""
        cache.clear()
        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}

        first = api_client.post(url, data=data, format="json")
        second = api_client.post(url, data=data, format="json")
        third = api_client.post(url, data=data, format="json")

        assert first.status_code == 201
        assert second.status_code == 201
        assert third.status_code == 429
        cache.clear()


@pytest.mark.django_db
class TestAdminFormListAPIView:
    """Tests for the staff GET /api/admin/forms/ endpoint"""

    def test_returns_403_for_anonymous(self, api_client, form):
        """Anonymous user cannot access admin form list"""
        url = reverse("quickscale_forms:admin-form-list")
        response = api_client.get(url)
        assert response.status_code in (401, 403)

    def test_returns_200_for_staff(self, staff_client, form):
        """Staff user can access admin form list"""
        url = reverse("quickscale_forms:admin-form-list")
        response = staff_client.get(url)
        assert response.status_code == 200
        assert len(response.data) >= 1
        assert "submission_count" in response.data[0]

    @override_settings(FORMS_SUBMISSIONS_API=False)
    def test_returns_404_when_admin_api_disabled(self, staff_client, form):
        """Disabling the submissions API should hide the staff admin endpoints."""
        url = reverse("quickscale_forms:admin-form-list")
        response = staff_client.get(url)

        assert response.status_code == 404


@pytest.mark.django_db
class TestAdminSubmissionListAPIView:
    """Tests for the staff GET /api/admin/forms/{id}/submissions/ endpoint"""

    def test_returns_submissions_for_form(self, staff_client, form, submission):
        """Staff can list submissions for a given form"""
        url = reverse("quickscale_forms:admin-submission-list", kwargs={"pk": form.pk})
        response = staff_client.get(url)
        assert response.status_code == 200
        assert len(response.data) >= 1

    def test_filter_by_status(self, staff_client, form, submission):
        """Submissions can be filtered by status query param"""
        url = reverse("quickscale_forms:admin-submission-list", kwargs={"pk": form.pk})
        response = staff_client.get(url, {"status": "pending"})
        assert response.status_code == 200

    @override_settings(FORMS_PER_PAGE=1)
    def test_respects_forms_per_page_setting(self, staff_client, form, submission):
        """The admin submission list should page according to FORMS_PER_PAGE."""
        FormSubmission.all_objects.create(
            form=form,
            organization=form.organization,
            ip_address="127.0.0.2",
            user_agent="TestBrowser/2.0",
        )
        url = reverse("quickscale_forms:admin-submission-list", kwargs={"pk": form.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        assert len(response.data) == 1


@pytest.mark.django_db
class TestAdminSubmissionDetailAPIView:
    """Tests for the staff GET/PATCH /api/admin/forms/{id}/submissions/{sub_id}/ endpoint"""

    def test_returns_submission_detail(
        self, staff_client, form, submission, field_value
    ):
        """Staff can retrieve submission detail with field values"""
        url = reverse(
            "quickscale_forms:admin-submission-detail",
            kwargs={"pk": form.pk, "sub_pk": submission.pk},
        )
        response = staff_client.get(url)
        assert response.status_code == 200
        assert response.data["id"] == submission.pk

    def test_patch_updates_status(self, staff_client, form, submission):
        """PATCH request updates submission status"""
        url = reverse(
            "quickscale_forms:admin-submission-detail",
            kwargs={"pk": form.pk, "sub_pk": submission.pk},
        )
        response = staff_client.patch(url, data={"status": "read"}, format="json")
        assert response.status_code == 200
        submission.refresh_from_db()
        assert submission.status == "read"


@pytest.mark.django_db
class TestAdminSubmissionExportView:
    """Tests for the staff CSV export view"""

    def test_returns_csv_for_staff(self, staff_client, form, submission, field_value):
        """Staff receives CSV file with correct content type"""
        url = reverse(
            "quickscale_forms:admin-submission-export", kwargs={"pk": form.pk}
        )
        response = staff_client.get(url)
        assert response.status_code == 200
        assert "text/csv" in response["Content-Type"]

    def test_csv_contains_field_values(
        self, staff_client, form, submission, field_value
    ):
        """CSV output contains the submitted field values"""
        url = reverse(
            "quickscale_forms:admin-submission-export", kwargs={"pk": form.pk}
        )
        response = staff_client.get(url)
        content = response.content.decode()
        assert "full_name" in content
        assert "Alice" in content

    def test_csv_neutralizes_formula_headers_and_values(
        self, staff_client, form, submission, field_value
    ):
        """CSV export prefixes dangerous header/value cells so spreadsheets keep them inert."""
        field_value.field_name = "=2+2"
        field_value.value = "  +SUM(A1:A2)"
        field_value.save(update_fields=["field_name", "value"])

        url = reverse(
            "quickscale_forms:admin-submission-export", kwargs={"pk": form.pk}
        )
        response = staff_client.get(url)

        assert response.status_code == 200

        rows = list(csv.reader(io.StringIO(response.content.decode())))
        assert rows[0][0] == "id"
        assert rows[0][-1] == "'=2+2"
        assert rows[1][-1] == "'  +SUM(A1:A2)"

    def test_returns_403_for_anonymous(self, api_client, form):
        """Anonymous user cannot export submissions"""
        url = reverse(
            "quickscale_forms:admin-submission-export", kwargs={"pk": form.pk}
        )
        response = api_client.get(url)
        assert response.status_code == 403

    def test_returns_404_for_missing_form(self, staff_client):
        """Export view returns 404 when form pk does not exist"""
        url = reverse("quickscale_forms:admin-submission-export", kwargs={"pk": 99999})
        response = staff_client.get(url)
        assert response.status_code == 404


@pytest.mark.django_db
class TestAdminSubmissionListFilters:
    """Tests for query parameter filters on AdminSubmissionListAPIView"""

    def test_filter_by_is_spam_true(self, staff_client, form, submission):
        """is_spam=true filter returns only spam submissions"""
        submission.is_spam = True
        submission.save()
        url = reverse("quickscale_forms:admin-submission-list", kwargs={"pk": form.pk})
        response = staff_client.get(url, {"is_spam": "true"})
        assert response.status_code == 200
        assert all(s["is_spam"] for s in response.data)

    def test_filter_by_date_gte(self, staff_client, form, submission):
        """submitted_at__date__gte filter is accepted without error"""
        url = reverse("quickscale_forms:admin-submission-list", kwargs={"pk": form.pk})
        response = staff_client.get(url, {"submitted_at__date__gte": "2000-01-01"})
        assert response.status_code == 200

    def test_filter_by_date_lte(self, staff_client, form, submission):
        """submitted_at__date__lte filter is accepted without error"""
        url = reverse("quickscale_forms:admin-submission-list", kwargs={"pk": form.pk})
        response = staff_client.get(url, {"submitted_at__date__lte": "2099-12-31"})
        assert response.status_code == 200


@pytest.mark.django_db
class TestAdminSubmissionDetailNotFound:
    """Tests for 404 behavior in AdminSubmissionDetailAPIView"""

    def test_returns_404_for_unknown_submission(self, staff_client, form):
        """Submission detail returns 404 when sub_pk does not exist"""
        url = reverse(
            "quickscale_forms:admin-submission-detail",
            kwargs={"pk": form.pk, "sub_pk": 99999},
        )
        response = staff_client.get(url)
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# AF1-CR-001: DB-side org scope for public forms routes
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPublicViewsDbOrgScope:
    """AF1-CR-001: Verify FormSchemaAPIView and FormSubmitAPIView establish
    DB-side app.current_org_id via tenant_context(), not just ContextVar state."""

    def test_form_schema_view_sets_db_current_org_id(
        self, api_client, form, monkeypatch
    ):
        """FormSchemaAPIView.get_object() must call set_db_current_org_id
        (proving tenant_context is entered for the DB side)."""
        from quickscale_modules_orgs.models import Organization

        system_org = Organization.objects.get_system_org()
        called_with = None

        def _track_db_set(org_id):
            nonlocal called_with
            called_with = org_id

        monkeypatch.setattr(
            "quickscale_modules_orgs.current_org.set_db_current_org_id",
            _track_db_set,
        )

        url = reverse("quickscale_forms:form-schema", kwargs={"slug": "test-contact"})
        api_client.get(url)

        assert called_with is not None, (
            "set_db_current_org_id was never called during schema GET"
        )
        assert str(called_with) == str(system_org.pk), (
            "DB-side org must be set to the resolved org (System org for anonymous)"
        )

    def test_form_submit_view_sets_db_current_org_id(
        self, api_client, form, form_field, email_field, monkeypatch
    ):
        """FormSubmitAPIView.create() must call set_db_current_org_id
        (proving tenant_context is entered for the DB side)."""
        from quickscale_modules_orgs.models import Organization

        system_org = Organization.objects.get_system_org()
        called_with = None

        def _track_db_set(org_id):
            nonlocal called_with
            called_with = org_id

        monkeypatch.setattr(
            "quickscale_modules_orgs.current_org.set_db_current_org_id",
            _track_db_set,
        )

        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}
        api_client.post(url, data=data, format="json")

        assert called_with is not None, (
            "set_db_current_org_id was never called during form submit"
        )
        assert str(called_with) == str(system_org.pk), (
            "DB-side org must be set to the resolved org (System org for anonymous)"
        )


# ---------------------------------------------------------------------------
# CR-P3-004: Forms caller-parity — authenticated-session and anonymous
# public-request coverage with exact POST response-field assertions.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFormCallerParity:
    """Exact POST response-field assertions for the public forms endpoints.

    CR-P3-004: verifies that tenant_context() + transaction.atomic() work
    correctly for both authenticated (session org) and anonymous (System org)
    requests.
    """

    def test_anonymous_submit_returns_exact_201_fields(
        self, api_client, form, form_field, email_field
    ):
        """Anonymous form submission returns 201 with message, redirect_url,
        and notification_status fields."""
        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}

        response = api_client.post(url, data=data, format="json")

        assert response.status_code == 201
        assert "message" in response.data
        assert "redirect_url" in response.data
        assert "notification_status" in response.data
        assert response.data["redirect_url"] is None
        assert response.data["message"] == form.success_message

    def test_anonymous_submit_creates_submission_under_system_org(
        self, api_client, form, form_field, email_field
    ):
        """Anonymous submissions should be associated with the System org."""
        from quickscale_modules_orgs.models import Organization

        system_org = Organization.objects.get_system_org()

        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}

        api_client.post(url, data=data, format="json")

        sub = FormSubmission.all_objects.filter(form=form).latest("submitted_at")
        assert sub.organization == system_org, (
            "Anonymous submission must be scoped to the System org"
        )

    def test_authenticated_submit_uses_session_org(self, api_client):
        """Authenticated requests with an active session org scope the
        submission to that org."""
        from quickscale_modules_orgs.models import (
            OrganizationMembership,
            OrgRole,
            Organization,
        )
        from django.contrib.auth import get_user_model
        from quickscale_modules_forms.models import Form, FormField

        user = get_user_model().objects.create_user(
            username="auth-form-user",
            email="auth-form@example.com",
            password="secret123",
        )
        org = Organization.objects.create(name="AuthFormOrg", slug="auth-form-org")
        OrganizationMembership.objects.create(
            user=user,
            organization=org,
            role=OrgRole.MEMBER,
        )

        # Create a form and field under the authenticated user's org
        org_form = Form.all_objects.create(
            organization=org,
            title="Auth Contact",
            slug="auth-contact",
            success_message="Thanks!",
            is_active=True,
        )
        FormField.all_objects.create(
            form=org_form,
            name="full_name",
            label="Full Name",
            field_type="text",
            required=True,
            order=1,
            organization=org,
        )
        FormField.all_objects.create(
            form=org_form,
            name="email",
            label="Email",
            field_type="email",
            required=True,
            order=2,
            organization=org,
        )

        api_client.force_login(user)
        session = api_client.session
        from quickscale_modules_orgs.constants import ACTIVE_ORG_SESSION_KEY

        session[ACTIVE_ORG_SESSION_KEY] = str(org.pk)
        session.save()

        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "auth-contact"})
        data = {"full_name": "Bob", "email": "bob@example.com"}

        response = api_client.post(url, data=data, format="json")

        assert response.status_code == 201
        sub = FormSubmission.all_objects.filter(form=org_form).latest("submitted_at")
        assert sub.organization == org, (
            "Authenticated submission must be scoped to the session org"
        )

    def test_authenticated_schema_returns_org_scoped_form(self, api_client):
        """Authenticated requests get forms scoped to their session org.

        Creates the test form under the target org from the start instead
        of reassigning the fixture form's org (which AF12 composite FKs
        prevent when child FormField rows already reference the old org).
        """
        from quickscale_modules_forms.models import Form, FormField
        from quickscale_modules_orgs.models import (
            OrganizationMembership,
            OrgRole,
            Organization,
        )
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username="auth-schema-user",
            email="auth-schema@example.com",
            password="secret123",
        )
        org = Organization.objects.create(name="SchemaOrg", slug="schema-org")
        OrganizationMembership.objects.create(
            user=user,
            organization=org,
            role=OrgRole.MEMBER,
        )

        # Create form under the target org directly (no reassignment needed).
        new_form = Form.all_objects.create(
            organization=org,
            title="Org Contact",
            slug="org-specific-form",
            success_message="Thanks!",
            is_active=True,
        )
        FormField.all_objects.create(
            form=new_form,
            name="full_name",
            label="Full Name",
            field_type="text",
            required=True,
            order=1,
            organization=org,
        )

        api_client.force_login(user)
        session = api_client.session
        from quickscale_modules_orgs.constants import ACTIVE_ORG_SESSION_KEY

        session[ACTIVE_ORG_SESSION_KEY] = str(org.pk)
        session.save()

        url = reverse(
            "quickscale_forms:form-schema", kwargs={"slug": "org-specific-form"}
        )
        response = api_client.get(url)

        assert response.status_code == 200
        assert response.data["slug"] == "org-specific-form"

    def test_anonymous_submit_preserves_redirect_url_when_set(
        self, api_client, form, form_field, email_field
    ):
        """When a form has a redirect_url, anonymous submissions return it."""
        form.redirect_url = "/thank-you"
        form.save(update_fields=["redirect_url"])

        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}

        response = api_client.post(url, data=data, format="json")

        assert response.status_code == 201
        assert response.data["redirect_url"] == "/thank-you"

    def test_anonymous_honeypot_submit_returns_201_with_message(
        self, api_client, form, form_field, email_field
    ):
        """Honeypot-triggered anonymous submissions return 201 with message
        and redirect_url (silent spam acceptance). notification_status is
        intentionally absent in the honeypot fast-path response."""
        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
        data = {
            "full_name": "Bot",
            "email": "bot@spam.com",
            "_hp_name": "I am a bot",
        }

        response = api_client.post(url, data=data, format="json")

        assert response.status_code == 201
        assert "message" in response.data
        assert "redirect_url" in response.data
        assert response.data["message"] == form.success_message
        sub = FormSubmission.all_objects.filter(form=form).latest("submitted_at")
        assert sub.is_spam is True

    def test_side_effects_dispatch_after_submission_committed(
        self, api_client, form, form_field, email_field, monkeypatch
    ):
        """CR-P3-006: notify_submission and analytics run AFTER the outer
        atomic commits.  If they were inside the atomic, a notification
        failure would roll back the submission transaction, or the response
        would be delayed until side effects complete.

        This test monkeypatches notify_submission to verify it runs at all,
        and that the submission already exists when notification fires.
        """
        notified_submission_pk = [None]

        def _track_notification(submission):
            notified_submission_pk[0] = submission.pk
            return "queued"

        monkeypatch.setattr(
            "quickscale_modules_forms.views.notify_submission",
            _track_notification,
        )

        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}

        response = api_client.post(url, data=data, format="json")

        assert response.status_code == 201
        assert notified_submission_pk[0] is not None, (
            "notify_submission must be called after the submission is persisted"
        )
        # Verify the persisted submission exists in the DB
        assert FormSubmission.all_objects.filter(
            pk=notified_submission_pk[0]
        ).exists(), "The submission must exist in the DB before notify_submission runs"


# ---------------------------------------------------------------------------
# CR-P3-006 regression: notification content carries field values after
# post-commit dispatch on the anonymous public submit path.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestNotificationContentAfterPostCommit:
    """Regression: public submit notifications must include submitted field
    values after tenant_context() exits on the anonymous path."""

    def test_anonymous_notification_includes_field_values_in_email(
        self, api_client, form, form_field, email_field
    ):
        """Anonymous public submit dispatches a notification email that
        includes the submitted field label and value — proving that
        _build_submission_notification_content reads field values via
        FormFieldValue.all_objects (not the TenantManager) after the
        tenant_context() window has closed."""
        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}

        response = api_client.post(url, data=data, format="json")

        assert response.status_code == 201
        # The notification email should contain the submitted field content
        assert len(mail.outbox) >= 1, "Notification email should be sent"
        email_body = mail.outbox[0].body
        # Field labels from fixture — check their values are present
        assert "Alice" in email_body, (
            "Notification email must include the submitted field value"
        )
        assert "alice@example.com" in email_body, (
            "Notification email must include the email field value"
        )
        # Field labels and values in field_pairs format
        assert "Name:" in email_body, (
            "Notification email must include the field label from field_pairs"
        )
        assert "Email:" in email_body, (
            "Notification email must include the email field label"
        )
