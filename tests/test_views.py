"""Tests for Forms module views"""

from unittest.mock import Mock

import pytest
from django.core.cache import cache
from django.core import mail
from django.test import override_settings
from django.urls import reverse

from quickscale_modules_forms.models import FormSubmission


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
        submission = FormSubmission.objects.filter(form=form).latest("submitted_at")
        assert submission.is_spam is True

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
        sub = FormSubmission.objects.filter(form=form).first()
        assert sub is not None
        assert sub.values.filter(field_name="full_name").exists()

    @override_settings(QUICKSCALE_ANALYTICS_ENABLED=True)
    def test_submission_captures_analytics_when_available(
        self, api_client, form, form_field, email_field, monkeypatch
    ):
        """Successful submissions should call the guarded analytics helper when present."""
        analytics_services = Mock()
        analytics_services.get_distinct_id.return_value = "session:test-visitor"

        def analytics_is_installed(app_label: str) -> bool:
            return app_label == "quickscale_modules_analytics"

        monkeypatch.setattr(
            "quickscale_modules_forms.views.apps.is_installed",
            analytics_is_installed,
        )
        monkeypatch.setattr(
            "quickscale_modules_forms.views.import_module",
            lambda module_path: analytics_services,
        )

        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}

        cache.clear()
        response = api_client.post(url, data=data, format="json")
        cache.clear()

        assert response.status_code == 201
        analytics_services.get_distinct_id.assert_called_once()
        analytics_services.capture_form_submit.assert_called_once_with(
            "session:test-visitor",
            form.pk,
            form.title,
            extra={"form_slug": form.slug},
        )

    @override_settings(QUICKSCALE_ANALYTICS_ENABLED=True)
    def test_submission_ignores_missing_analytics_module(
        self, api_client, form, form_field, email_field, monkeypatch
    ):
        """Missing analytics package should stay a clean no-op after submit."""

        def analytics_is_installed(app_label: str) -> bool:
            return app_label == "quickscale_modules_analytics"

        def missing_analytics(_module_path: str):
            raise ImportError("analytics not installed")

        monkeypatch.setattr(
            "quickscale_modules_forms.views.apps.is_installed",
            analytics_is_installed,
        )
        monkeypatch.setattr(
            "quickscale_modules_forms.views.import_module",
            missing_analytics,
        )

        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}

        cache.clear()
        response = api_client.post(url, data=data, format="json")
        cache.clear()

        assert response.status_code == 201
        assert FormSubmission.objects.filter(form=form).count() == 1

    @override_settings(QUICKSCALE_ANALYTICS_ENABLED=False)
    def test_submission_skips_analytics_when_disabled_but_installed_and_env_present(
        self,
        api_client,
        form,
        form_field,
        email_field,
        monkeypatch,
    ):
        """Disabled analytics must not import services even when the package remains installed."""

        def analytics_is_installed(app_label: str) -> bool:
            return app_label == "quickscale_modules_analytics"

        def fail_import(module_path: str):
            raise AssertionError(
                "analytics services should not load when runtime analytics is disabled"
            )

        monkeypatch.setenv("POSTHOG_API_KEY", "test-posthog-key")
        monkeypatch.setattr(
            "quickscale_modules_forms.views.apps.is_installed",
            analytics_is_installed,
        )
        monkeypatch.setattr(
            "quickscale_modules_forms.views.import_module",
            fail_import,
        )

        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}

        cache.clear()
        response = api_client.post(url, data=data, format="json")
        cache.clear()

        assert response.status_code == 201
        assert FormSubmission.objects.filter(form=form).count() == 1

    @override_settings(QUICKSCALE_ANALYTICS_ENABLED=True)
    def test_submission_stays_non_blocking_when_analytics_capture_fails(
        self, api_client, form, form_field, email_field, monkeypatch
    ):
        """Analytics capture failure must not block the public success response."""
        analytics_services = Mock()
        analytics_services.get_distinct_id.return_value = "session:test-visitor"
        analytics_services.capture_form_submit.side_effect = RuntimeError(
            "posthog unavailable"
        )

        def analytics_is_installed(app_label: str) -> bool:
            return app_label == "quickscale_modules_analytics"

        monkeypatch.setattr(
            "quickscale_modules_forms.views.apps.is_installed",
            analytics_is_installed,
        )
        monkeypatch.setattr(
            "quickscale_modules_forms.views.import_module",
            lambda module_path: analytics_services,
        )

        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}

        cache.clear()
        response = api_client.post(url, data=data, format="json")
        cache.clear()

        assert response.status_code == 201
        assert FormSubmission.objects.filter(form=form).count() == 1

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
        assert FormSubmission.objects.filter(form=form).count() == 1
        assert (
            FormSubmission.objects.get(form=form)
            .values.filter(
                field_name="full_name",
                value="Alice",
            )
            .exists()
        )

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
        assert FormSubmission.objects.filter(form=form).count() == 1
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
        FormSubmission.objects.create(
            form=form,
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
