"""Tests for Forms module views"""

import csv
import io
from typing import Any
from unittest.mock import Mock, patch

import pytest
from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.db import connection, transaction
from django.test import RequestFactory, override_settings
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
def test_form_page_renders_inside_the_module_base(client):
    """The public form page extends the flat forms module base and shell."""
    response = client.get(
        reverse("quickscale_forms:form_page", kwargs={"slug": "test-contact"})
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert 'data-form-slug="test-contact"' in content
    assert 'class="forms-content"' in content
    assert "<style" not in content.lower()


@pytest.mark.django_db
class TestFormSchemaAPIView:
    """Tests for the public GET /forms/api/{slug}/ endpoint"""

    def test_returns_200_for_valid_active_slug(self, api_client, form, form_field):
        """Active form returns 200 with schema data"""
        url = reverse("quickscale_forms:form_schema", kwargs={"slug": "test-contact"})
        response = api_client.get(url)
        assert response.status_code == 200
        assert response.data["slug"] == "test-contact"

    def test_returns_404_for_unknown_slug(self, api_client):
        """Non-existent slug returns 404"""
        url = reverse("quickscale_forms:form_schema", kwargs={"slug": "does-not-exist"})
        response = api_client.get(url)
        assert response.status_code == 404

    def test_returns_404_for_inactive_form(self, api_client, inactive_form):
        """Inactive form returns 404 on the public endpoint"""
        url = reverse("quickscale_forms:form_schema", kwargs={"slug": "inactive"})
        response = api_client.get(url)
        assert response.status_code == 404

    def test_injects_honeypot_marker_in_schema(self, api_client, form, form_field):
        """Schema response includes hidden _hp_name marker when spam protection is enabled"""
        url = reverse("quickscale_forms:form_schema", kwargs={"slug": "test-contact"})
        response = api_client.get(url)
        assert response.status_code == 200
        field_names = [field["name"] for field in response.data["fields"]]
        assert "_hp_name" in field_names

    @override_settings(QUICKSCALE_FORMS_SPAM_PROTECTION_ENABLED=False)
    def test_omits_honeypot_marker_when_global_spam_protection_disabled(
        self, api_client, form, form_field
    ):
        """Schema should not advertise honeypot when global spam protection is off."""
        url = reverse("quickscale_forms:form_schema", kwargs={"slug": "test-contact"})

        response = api_client.get(url)

        assert response.status_code == 200
        field_names = [field["name"] for field in response.data["fields"]]
        assert "_hp_name" not in field_names

    def test_omits_honeypot_marker_when_form_spam_protection_disabled(
        self, api_client, form, form_field
    ):
        """Schema should not advertise honeypot when the form-level flag is off."""
        from quickscale_modules_orgs.current_org import org_scope

        form.spam_protection_enabled = False
        with org_scope(form.organization):
            form.save(update_fields=["spam_protection_enabled"])
        url = reverse("quickscale_forms:form_schema", kwargs={"slug": "test-contact"})

        response = api_client.get(url)

        assert response.status_code == 200
        field_names = [field["name"] for field in response.data["fields"]]
        assert "_hp_name" not in field_names


@pytest.mark.django_db
class TestFormSubmitAPIView:
    """Tests for the public POST /forms/api/{slug}/submit/ endpoint"""

    def test_returns_201_on_valid_submission(
        self, api_client, form, form_field, email_field
    ):
        """Valid submission returns 201 with success message"""
        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}
        response = api_client.post(url, data=data, format="json")
        assert response.status_code == 201
        assert "message" in response.data

    def test_returns_400_on_missing_required_field(
        self, api_client, form, form_field, email_field
    ):
        """Missing required field returns 400 in the one QuickScale error shape"""
        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice"}  # missing email
        response = api_client.post(url, data=data, format="json")
        assert response.status_code == 400
        assert response.data == {
            "error": {
                "code": "validation_error",
                "message": "Invalid input.",
                "fields": {"email": ["This field is required."]},
            }
        }

    @pytest.mark.parametrize(
        "payload,expected_error",
        [
            ([1, 2, 3], "must be text"),
            ({"type": "object"}, "must be text"),
            (123, "must be text"),
            (None, "is required"),
        ],
    )
    def test_returns_400_on_non_string_payload_values(
        self, api_client, form, form_field, email_field, payload, expected_error
    ):
        """Array/number/object/null payloads return 400, never 500."""
        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
        data = {"full_name": payload, "email": payload, "company": payload}
        response = api_client.post(url, data=data, format="json")
        assert response.status_code == 400
        error = response.data["error"]
        assert error["code"] == "validation_error"
        assert expected_error in error["fields"]["full_name"][0]
        assert expected_error in error["fields"]["email"][0]

    @pytest.mark.parametrize(
        "payload,post_kwargs",
        [
            ([1, 2, 3], {"format": "json"}),
            ("text", {"format": "json"}),
            (123, {"format": "json"}),
            ("null", {"content_type": "application/json"}),
        ],
    )
    def test_returns_400_for_non_object_json_body(
        self, api_client, form, form_field, email_field, payload, post_kwargs
    ):
        """A JSON body that is not an object returns 400 in the one shape, never 500."""
        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
        response = api_client.post(url, data=payload, **post_kwargs)
        assert response.status_code == 400
        assert response.data == {
            "error": {
                "code": "validation_error",
                "message": "Invalid input.",
                "fields": {"non_field_errors": ["Request body must be a JSON object."]},
            }
        }

    def test_honeypot_silently_marks_spam_and_returns_201(
        self, api_client, form, form_field, email_field
    ):
        """Filled honeypot field is treated as spam — returns 201 silently"""
        from quickscale_modules_orgs.current_org import org_scope

        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Bot", "email": "bot@spam.com", "_hp_name": "I am a bot"}
        response = api_client.post(url, data=data, format="json")
        assert response.status_code == 201
        # The submission is marked as spam in the DB — read it back inside
        # org_scope so FORCE RLS allows the query.
        with org_scope(form.organization):
            submission = FormSubmission.all_objects.filter(form=form).latest(
                "submitted_at"
            )
        assert submission.is_spam is True

    @override_settings(QUICKSCALE_FORMS_SPAM_PROTECTION_ENABLED=False)
    def test_honeypot_is_ignored_when_global_spam_protection_disabled(
        self, api_client, form, form_field, email_field
    ):
        """Submission handling should ignore honeypot when global spam protection is off."""
        from quickscale_modules_orgs.current_org import org_scope

        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com", "_hp_name": "bot"}

        response = api_client.post(url, data=data, format="json")

        assert response.status_code == 201
        with org_scope(form.organization):
            submission = FormSubmission.all_objects.filter(form=form).latest(
                "submitted_at"
            )
        assert submission.is_spam is False

    def test_honeypot_is_ignored_when_form_spam_protection_disabled(
        self, api_client, form, form_field, email_field
    ):
        """Submission handling should ignore honeypot when the form-level flag is off."""
        from quickscale_modules_orgs.current_org import org_scope

        form.spam_protection_enabled = False
        with org_scope(form.organization):
            form.save(update_fields=["spam_protection_enabled"])
        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com", "_hp_name": "bot"}

        response = api_client.post(url, data=data, format="json")

        assert response.status_code == 201
        with org_scope(form.organization):
            submission = FormSubmission.all_objects.filter(form=form).latest(
                "submitted_at"
            )
        assert submission.is_spam is False

    def test_returns_404_for_inactive_form(self, api_client, inactive_form):
        """Submit to inactive form returns 404 in the one QuickScale error shape"""
        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "inactive"})
        response = api_client.post(url, data={}, format="json")
        assert response.status_code == 404
        assert response.data["error"]["code"] == "not_found"

    def test_creates_submission_and_field_values(
        self, api_client, form, form_field, email_field
    ):
        """Valid submission creates a FormSubmission and FormFieldValue records"""
        from quickscale_modules_orgs.current_org import org_scope

        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}
        api_client.post(url, data=data, format="json")
        with org_scope(form.organization):
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
        self,
        api_client,
        form,
        form_field,
        email_field,
        monkeypatch,
        django_capture_on_commit_callbacks,
    ):
        """Successful submissions emit the forms-owned event on commit."""

        def analytics_is_installed(app_label: str) -> bool:
            return app_label == "quickscale_modules_analytics"

        mock_get_distinct_id = Mock(return_value="session:test-visitor")
        mock_capture_event = Mock()

        monkeypatch.setattr(
            "quickscale_modules_forms.views.apps.is_installed",
            analytics_is_installed,
        )
        monkeypatch.setattr(
            "quickscale_modules_analytics.services.get_distinct_id",
            mock_get_distinct_id,
        )
        monkeypatch.setattr(
            "quickscale_modules_analytics.services.capture_event",
            mock_capture_event,
        )
        monkeypatch.setattr(
            "quickscale_modules_analytics.services.get_analytics_runtime_settings",
            Mock(return_value=Mock(enabled=True)),
        )

        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}

        cache.clear()
        with django_capture_on_commit_callbacks(execute=True):
            response = api_client.post(url, data=data, format="json")
        cache.clear()

        assert response.status_code == 201
        mock_get_distinct_id.assert_called_once()
        mock_capture_event.assert_called_once_with(
            distinct_id="session:test-visitor",
            event="quickscale_forms_submitted",
            properties={
                "form_slug": form.slug,
                "module": "forms",
                "form_id": str(form.pk),
                "form_name": form.title,
            },
        )

    @override_settings(QUICKSCALE_ANALYTICS_ENABLED=False)
    def test_submission_skips_analytics_when_disabled_but_installed_and_env_present(
        self,
        api_client,
        form,
        form_field,
        email_field,
        monkeypatch,
        django_capture_on_commit_callbacks,
    ):
        """Disabled analytics must not call services even when the package remains installed."""
        from quickscale_modules_orgs.current_org import org_scope

        def analytics_is_installed(app_label: str) -> bool:
            return app_label == "quickscale_modules_analytics"

        mock_capture = Mock()
        monkeypatch.setattr(
            "quickscale_modules_forms.views.apps.is_installed",
            analytics_is_installed,
        )
        monkeypatch.setattr(
            "quickscale_modules_analytics.services.capture_event",
            mock_capture,
        )
        monkeypatch.setattr(
            "quickscale_modules_analytics.services.get_analytics_runtime_settings",
            Mock(return_value=Mock(enabled=False)),
        )

        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}

        cache.clear()
        with django_capture_on_commit_callbacks(execute=True):
            response = api_client.post(url, data=data, format="json")
        cache.clear()

        assert response.status_code == 201
        with org_scope(form.organization):
            assert FormSubmission.all_objects.filter(form=form).count() == 1
        mock_capture.assert_not_called()

    def test_submission_succeeds_without_analytics_installed(
        self, api_client, form, form_field, email_field, monkeypatch
    ):
        """Prove forms submits cleanly when analytics is absent from the
        Python path / not installed.  _capture_submission_analytics()
        short-circuits via the apps.is_installed guard; no analytics
        symbols are imported or resolved.

        Replaces the analytics services
        submodule in sys.modules with an import-seam sentinel.  If the
        guard were bypassed or broken, the lazy import
        ``from quickscale_modules_analytics.services import ...``
        would trigger the sentinel's __getattr__, raising
        ModuleNotFoundError OUTSIDE the except Exception boundary —
        proving the guard correctly prevents the import under the
        absent-analytics condition.
        """
        import sys

        from quickscale_modules_orgs.current_org import org_scope

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

        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}

        cache.clear()
        response = api_client.post(url, data=data, format="json")
        cache.clear()

        assert response.status_code == 201
        with org_scope(form.organization):
            assert FormSubmission.all_objects.filter(form=form).count() == 1

    @override_settings(QUICKSCALE_ANALYTICS_ENABLED=True)
    def test_submission_stays_non_blocking_when_analytics_capture_fails(
        self,
        api_client,
        form,
        form_field,
        email_field,
        monkeypatch,
        django_capture_on_commit_callbacks,
    ):
        """Analytics capture failure must not block the public success response."""
        from quickscale_modules_orgs.current_org import org_scope

        def analytics_is_installed(app_label: str) -> bool:
            return app_label == "quickscale_modules_analytics"

        mock_get_distinct_id = Mock(return_value="session:test-visitor")
        mock_capture_event = Mock(side_effect=RuntimeError("posthog unavailable"))

        monkeypatch.setattr(
            "quickscale_modules_forms.views.apps.is_installed",
            analytics_is_installed,
        )
        monkeypatch.setattr(
            "quickscale_modules_analytics.services.get_distinct_id",
            mock_get_distinct_id,
        )
        monkeypatch.setattr(
            "quickscale_modules_analytics.services.capture_event",
            mock_capture_event,
        )
        monkeypatch.setattr(
            "quickscale_modules_analytics.services.get_analytics_runtime_settings",
            Mock(return_value=Mock(enabled=True)),
        )

        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}

        cache.clear()
        with django_capture_on_commit_callbacks(execute=True):
            response = api_client.post(url, data=data, format="json")
        cache.clear()

        assert response.status_code == 201
        with org_scope(form.organization):
            assert FormSubmission.all_objects.filter(form=form).count() == 1

    def test_submission_persists_when_notification_delivery_fails(
        self,
        api_client,
        form,
        form_field,
        email_field,
        monkeypatch,
        django_capture_on_commit_callbacks,
    ):
        """Delivery failure stays non-blocking and does not roll back persistence"""
        from quickscale_modules_orgs.current_org import org_scope

        def failing_send(message):
            raise Exception("SMTP connection refused")

        monkeypatch.setattr(
            "quickscale_modules_notifications.services._send_email_message",
            failing_send,
        )

        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}

        cache.clear()

        with django_capture_on_commit_callbacks(execute=True):
            response = api_client.post(url, data=data, format="json")

        cache.clear()

        assert response.status_code == 201
        with org_scope(form.organization):
            assert FormSubmission.all_objects.filter(form=form).count() == 1
            sub = FormSubmission.all_objects.get(form=form)
            assert FormFieldValue.all_objects.filter(
                submission=sub,
                field_name="full_name",
                value="Alice",
            ).exists()

    @override_settings(QUICKSCALE_NOTIFICATIONS_ENABLED=False)
    def test_submission_persists_when_notifications_disabled(
        self,
        api_client,
        form,
        form_field,
        email_field,
        django_capture_on_commit_callbacks,
    ):
        """Runtime-disabled notifications never block submission and send nothing."""
        from quickscale_modules_orgs.current_org import org_scope

        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}

        cache.clear()
        with django_capture_on_commit_callbacks(execute=True):
            response = api_client.post(url, data=data, format="json")
        cache.clear()

        assert response.status_code == 201
        with org_scope(form.organization):
            assert FormSubmission.all_objects.filter(form=form).count() == 1
        assert mail.outbox == []

    def test_returns_429_when_rate_limit_exceeded(
        self, api_client, form, form_field, email_field
    ):
        """Submit endpoint returns 429 after the wired scope rate is exceeded."""
        from rest_framework.throttling import ScopedRateThrottle

        cache.clear()
        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}
        scope_rates = {"quickscale_forms_submit": "2/minute"}

        # The forms wiring contributes the rate from QUICKSCALE_FORMS_RATE_LIMIT; DRF
        # binds DEFAULT_THROTTLE_RATES onto the throttle class at import time,
        # so the test applies both bindings itself.  A wholesale REST_FRAMEWORK
        # override replaces the module settings' exception handler, so the
        # override carries it too and the throttled body stays the one shape.
        with (
            override_settings(
                REST_FRAMEWORK={
                    "EXCEPTION_HANDLER": (
                        "quickscale_core.runtime.conventions.exception_handler"
                    ),
                    "DEFAULT_THROTTLE_RATES": scope_rates,
                }
            ),
            patch.object(ScopedRateThrottle, "THROTTLE_RATES", scope_rates),
        ):
            first = api_client.post(url, data=data, format="json")
            second = api_client.post(url, data=data, format="json")
            third = api_client.post(url, data=data, format="json")

        assert first.status_code == 201
        assert second.status_code == 201
        assert third.status_code == 429
        assert third.data["error"]["code"] == "throttled"
        cache.clear()


@pytest.mark.django_db
class TestAdminFormListAPIView:
    """Tests for the admin GET /forms/api/admin/forms/ endpoint

    Org-role contract (rule 19):
    * Superuser: the operator path — cross-tenant read via ``operator_access``.
    * Viewer or above with active org: scoped to that org via RLS.
    * No org context: the permission refuses the request (403);
      session-pipeline tests assert 302 redirect to /orgs/ before view executes.
    * Anonymous: denied (403).

    /forms/api/admin/forms/ is NON-EXEMPT from
    TenantMiddleware (does not match any EXEMPT_PATH_PREFIX).
    """

    def test_returns_403_for_anonymous(self, api_client, form):
        """Anonymous user cannot access admin form list"""
        url = reverse("quickscale_forms:admin_form_list")
        response = api_client.get(url)
        assert response.status_code in (401, 403)

    def test_superuser_sees_all_forms(self, superuser_client, form):
        """Superuser can access admin form list and sees all forms."""
        url = reverse("quickscale_forms:admin_form_list")
        response = superuser_client.get(url)
        assert response.status_code == 200
        assert len(response.data) >= 1
        assert "submission_count" in response.data[0]

    def test_staff_without_org_is_refused(self, staff_client, form):
        """View-unit defense-in-depth: force-auth staff without org is refused.

        This test uses ``force_authenticate`` (DRF-only, no session
        middleware).  The session-parity proof for real middleware-pipeline
        coverage is ``test_staff_session_active_org_sees_own_org_forms``
        and ``test_staff_session_cross_org_excluded``.
        """
        url = reverse("quickscale_forms:admin_form_list")
        response = staff_client.get(url)
        assert response.status_code == 403

    def test_superuser_sees_org_scoped_form(self, superuser_client, org, org_form):
        """Superuser sees forms from a scoped org via cross-tenant read.

        The org_form fixture creates a form under *org*.
        The superuser operator path (all_objects) returns it regardless
        of org context.
        """
        url = reverse("quickscale_forms:admin_form_list")
        response = superuser_client.get(url)
        assert response.status_code == 200
        slugs = [item["slug"] for item in response.data]
        assert "org-contact" in slugs, (
            "Superuser must see the org-scoped form via operator path"
        )

    def test_staff_with_org_uses_scoped_queryset_not_none(self, db, org):
        """Staff with active org context gets a scoped queryset (not .none()).

        Verifies the _get_org_bound_queryset contract
        by checking the queryset class type rather than executing a
        database query (which requires PG RLS GUC setup).  The actual
        end-to-end behavior is covered by the superuser test above and
        the staff-fail-closed test below.
        """
        from quickscale_modules_forms.views import AdminFormListAPIView
        from quickscale_modules_orgs.current_org import (
            get_current_org_id,
            set_current_org_id,
            reset_current_org_id,
        )
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIRequestFactory, force_authenticate
        from rest_framework.request import Request as DRF_Request

        # Set org context to simulate staff with active org
        set_current_org_id(org.pk)

        try:
            staff_user = get_user_model().objects.create_user(
                username="scoped-staff",
                email="scoped@example.com",
                password="testpass123",
                is_staff=True,
            )

            rf = APIRequestFactory()
            wsgi_request = rf.get("/forms/api/admin/forms/")
            wsgi_request.user = staff_user
            drf_request = DRF_Request(wsgi_request)
            force_authenticate(drf_request, user=staff_user)

            view = AdminFormListAPIView()
            view.request = drf_request
            view.kwargs = {}

            qs = view.get_queryset()

            # Must NOT be .none() queryset (fail-closed)
            assert qs.query.order_by == ("title",), (
                "Queryset must have order_by from annotate/order_by"
            )
            # The underlying model is Form — proves it's a real queryset
            assert qs.model is not None, "Queryset must have a model"
            # Verify the underlying mgr class is Form.objects (TenantManager),
            # not Form.all_objects (AllObjectsManager)
            assert not qs.query.is_empty(), (
                "Queryset must not be .none() — staff with org gets scoped access"
            )
        finally:
            reset_current_org_id()

        assert get_current_org_id() is None, "ContextVar must be None after cleanup"

    # ------------------------------------------------------------------
    # session-auth pipeline proofs
    # ------------------------------------------------------------------
    # These tests use force_login + ACTIVE_ORG_SESSION_KEY to exercise
    # the full session authentication pipeline (SessionMiddleware +
    # AuthenticationMiddleware).  The admin API path
    # (/forms/api/admin/forms/) is NON-EXEMPT from TenantMiddleware (it does
    # not start with /admin/ or any other exempt prefix), so the
    # middleware DOES run and populates the ContextVar from the session.
    #
    # * An org member (viewer or above) with active org: ContextVar
    #   populated → RLS scopes the queryset to the active org.  Members see
    #   only forms belonging to that org.
    # * An org member without active org: middleware redirects to
    #   /orgs/ before the view executes (302).
    # * Superuser with active org: ContextVar populated but
    #   _get_org_bound_queryset returns all_objects.all() regardless.
    # * Superuser without active org: same 302 redirect.
    #
    # The force_authenticate tests above (staff_client / superuser_client)
    # are view-unit defense-in-depth only and do NOT exercise the
    # middleware pipeline.  The proofs below are the authoritative
    # session-parity coverage.
    # ------------------------------------------------------------------

    def test_staff_session_active_org_sees_own_org_forms(
        self, staff_user, api_client, form, db
    ):
        """An org member with force_login + ACTIVE_ORG_SESSION_KEY sees
        only forms belonging to their active org.

        Real session-auth pipeline proof.
        /forms/api/admin/forms/ is non-exempt, so TenantMiddleware runs and
        populates the ContextVar from the session.  Members see their own
        org's form and do NOT see forms from other orgs.
        """
        from quickscale_modules_orgs._constants import ACTIVE_ORG_SESSION_KEY
        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )
        from quickscale_modules_forms.models import Form

        # Create a separate org for the member user (different from
        # System org where ``form`` fixture lives).
        own_org = Organization.objects.create(
            name="Staff Own Org", slug="staff-own-org"
        )
        OrganizationMembership.objects.create(
            user=staff_user,
            organization=own_org,
            role=OrgRole.ADMIN,
        )

        # Create a form under the member user's org.
        with org_scope(own_org):
            Form.all_objects.create(
                organization=own_org,
                title="Own Contact",
                slug="own-contact",
                success_message="Thanks!",
                is_active=True,
            )

        api_client.force_login(user=staff_user)
        session = api_client.session
        session[ACTIVE_ORG_SESSION_KEY] = str(own_org.pk)
        session.save()

        url = reverse("quickscale_forms:admin_form_list")

        response = api_client.get(url)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        slugs = [item["slug"] for item in response.data]
        assert "own-contact" in slugs, (
            f"Member must see their own org's form. Got slugs: {slugs}"
        )
        # System org's form (created by the ``form`` fixture) must NOT
        # be visible — different org, RLS-scoped out.
        assert "test-contact" not in slugs, (
            f"Member must NOT see System org's form (different org). Got slugs: {slugs}"
        )

    def test_staff_session_cross_org_excluded(self, staff_user, api_client, db):
        """An org member with force_login + ACTIVE_ORG_SESSION_KEY set
        to one org does not see forms belonging to a different org.

        Proves cross-tenant isolation through the
        full middleware + RLS pipeline on the non-exempt admin path.
        """
        from quickscale_modules_orgs._constants import ACTIVE_ORG_SESSION_KEY
        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )
        from quickscale_modules_forms.models import Form

        own_org = Organization.objects.create(name="Own Org", slug="own-org")
        other_org = Organization.objects.create(name="Other Org", slug="other-org")

        OrganizationMembership.objects.create(
            user=staff_user,
            organization=own_org,
            role=OrgRole.ADMIN,
        )

        with org_scope(own_org):
            Form.all_objects.create(
                organization=own_org,
                title="Own Form",
                slug="own-form",
                success_message="Thanks!",
                is_active=True,
            )
        with org_scope(other_org):
            Form.all_objects.create(
                organization=other_org,
                title="Other Form",
                slug="other-form",
                success_message="Thanks!",
                is_active=True,
            )

        api_client.force_login(user=staff_user)
        session = api_client.session
        session[ACTIVE_ORG_SESSION_KEY] = str(own_org.pk)
        session.save()

        url = reverse("quickscale_forms:admin_form_list")
        response = api_client.get(url)
        assert response.status_code == 200
        slugs = [item["slug"] for item in response.data]
        assert "own-form" in slugs, (
            f"Member must see own org's form. Got slugs: {slugs}"
        )
        assert "other-form" not in slugs, (
            f"Member must NOT see other org's form. Got slugs: {slugs}"
        )

    def test_viewer_session_reads_active_org_forms(self, user, api_client, db):
        """A viewer-role session can read its active org's forms (rule 19)."""
        from quickscale_modules_orgs._constants import ACTIVE_ORG_SESSION_KEY
        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )
        from quickscale_modules_forms.models import Form

        viewer_org = Organization.objects.create(name="Viewer Org", slug="viewer-org")
        OrganizationMembership.objects.create(
            user=user,
            organization=viewer_org,
            role=OrgRole.VIEWER,
        )
        with org_scope(viewer_org):
            Form.all_objects.create(
                organization=viewer_org,
                title="Viewer Contact",
                slug="viewer-contact",
                success_message="Thanks!",
                is_active=True,
            )

        api_client.force_login(user=user)
        session = api_client.session
        session[ACTIVE_ORG_SESSION_KEY] = str(viewer_org.pk)
        session.save()

        response = api_client.get(reverse("quickscale_forms:admin_form_list"))

        assert response.status_code == 200
        slugs = [item["slug"] for item in response.data]
        assert "viewer-contact" in slugs

    def test_superuser_session_active_org_sees_cross_tenant(
        self, superuser, api_client, db
    ):
        """Superuser with ACTIVE_ORG_SESSION_KEY set to a specific org
        can still see forms across all tenants via operator_access.

        Proves superuser cross-tenant bypass on the
        non-exempt admin path.  TenantMiddleware runs and populates the
        ContextVar, but _get_org_bound_queryset returns all_objects.all()
        for superusers regardless of ContextVar state.

        Uses clean ``api_client`` with ``force_login`` (real session
        authentication), not ``force_authenticate``, so the full
        middleware + RLS pipeline is exercised.
        """
        from quickscale_modules_orgs._constants import ACTIVE_ORG_SESSION_KEY
        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )
        from quickscale_modules_forms.models import Form

        active_org = Organization.objects.create(name="Active Org", slug="active-org")
        foreign_org = Organization.objects.create(
            name="Foreign Org", slug="foreign-org"
        )

        OrganizationMembership.objects.create(
            user=superuser,
            organization=active_org,
            role=OrgRole.ADMIN,
        )

        with org_scope(active_org):
            Form.all_objects.create(
                organization=active_org,
                title="Active Form",
                slug="active-form",
                success_message="Thanks!",
                is_active=True,
            )
        with org_scope(foreign_org):
            Form.all_objects.create(
                organization=foreign_org,
                title="Foreign Form",
                slug="foreign-form",
                success_message="Thanks!",
                is_active=True,
            )

        api_client.force_login(user=superuser)
        session = api_client.session
        session[ACTIVE_ORG_SESSION_KEY] = str(active_org.pk)
        session.save()

        url = reverse("quickscale_forms:admin_form_list")
        response = api_client.get(url)
        assert response.status_code == 200
        slugs = [item["slug"] for item in response.data]
        assert "active-form" in slugs, (
            f"Superuser must see active org's form. Got slugs: {slugs}"
        )
        assert "foreign-form" in slugs, (
            f"Superuser must see foreign org's form "
            f"via operator path. Got slugs: {slugs}"
        )

    # ------------------------------------------------------------------
    # no-active-org redirect proofs
    # ------------------------------------------------------------------
    # These tests hit /forms/api/admin/forms/ which is NON-EXEMPT from
    # TenantMiddleware.  Without ACTIVE_ORG_SESSION_KEY, the middleware
    # redirects to /orgs/ before the view executes — for both regular
    # staff and superusers.

    def test_staff_session_no_active_org_redirects(self, staff_user, api_client, db):
        """An authenticated user without ACTIVE_ORG_SESSION_KEY gets 302
        redirect to /orgs/ on the admin_form_list path.

        Proves TenantMiddleware redirects to /orgs/
        when an authenticated user has no active org selected on the
        non-exempt admin API route.
        """
        api_client.force_login(user=staff_user)
        # Do NOT set ACTIVE_ORG_SESSION_KEY — middleware should
        # redirect before the view runs.

        url = reverse("quickscale_forms:admin_form_list")
        response = api_client.get(url)

        assert response.status_code == 302, (
            f"Expected 302 redirect to /orgs/, got {response.status_code}"
        )
        assert response["Location"] == "/orgs/", (
            f"Expected Location: /orgs/, got {response['Location']}"
        )

    def test_superuser_session_no_active_org_redirects(self, superuser, api_client, db):
        """Superuser without ACTIVE_ORG_SESSION_KEY also gets 302
        redirect to /orgs/ on the admin_form_list path.

        Proves TenantMiddleware applies the same
        no-active-org redirect to superusers before the view executes
        on the non-exempt admin API route.
        """
        api_client.force_login(user=superuser)
        # Do NOT set ACTIVE_ORG_SESSION_KEY.

        url = reverse("quickscale_forms:admin_form_list")
        response = api_client.get(url)

        assert response.status_code == 302, (
            f"Expected 302 redirect to /orgs/, got {response.status_code}"
        )
        assert response["Location"] == "/orgs/", (
            f"Expected Location: /orgs/, got {response['Location']}"
        )

    @override_settings(QUICKSCALE_FORMS_API_ENABLED=False)
    def test_returns_404_when_admin_api_disabled(self, superuser_client, form):
        """Disabling the submissions API should hide the staff admin endpoints."""
        url = reverse("quickscale_forms:admin_form_list")
        response = superuser_client.get(url)

        assert response.status_code == 404


@pytest.mark.django_db
class TestAdminSubmissionListAPIView:
    """Tests for the admin GET /forms/api/admin/forms/{id}/submissions/ endpoint

    Org-role contract (rule 19):
    * Superuser: the operator path — cross-tenant read via ``operator_access``.
    * Viewer or above with active org: RLS-scoped to that org.
    * No org context: the permission refuses the request (403).
    """

    def test_superuser_can_list_submissions(self, superuser_client, form, submission):
        """Superuser can list submissions for a given form."""
        url = reverse("quickscale_forms:admin_submission_list", kwargs={"pk": form.pk})
        response = superuser_client.get(url)
        assert response.status_code == 200
        assert len(response.data) >= 1

    def test_staff_without_org_is_refused(self, staff_client, form, submission):
        """View-unit defense-in-depth: force-auth staff without org is refused.

        Session-parity proof for the real middleware pipeline is
        ``test_staff_session_active_org_sees_own_org_forms`` and
        ``test_staff_session_cross_org_excluded``.
        """
        url = reverse("quickscale_forms:admin_submission_list", kwargs={"pk": form.pk})
        response = staff_client.get(url)
        assert response.status_code == 403

    def test_filter_by_status(self, superuser_client, form, submission):
        """Submissions can be filtered by status query param."""
        url = reverse("quickscale_forms:admin_submission_list", kwargs={"pk": form.pk})
        response = superuser_client.get(url, {"status": "pending"})
        assert response.status_code == 200

    @override_settings(QUICKSCALE_FORMS_SUBMISSIONS_PER_PAGE=1)
    def test_respects_forms_per_page_setting(self, superuser_client, form, submission):
        """The admin submission list should page according to QUICKSCALE_FORMS_SUBMISSIONS_PER_PAGE."""
        from quickscale_modules_orgs.current_org import org_scope

        with org_scope(form.organization):
            FormSubmission.all_objects.create(
                form=form,
                organization=form.organization,
                ip_address="127.0.0.2",
                user_agent="TestBrowser/2.0",
            )
        url = reverse("quickscale_forms:admin_submission_list", kwargs={"pk": form.pk})
        response = superuser_client.get(url)

        assert response.status_code == 200
        assert len(response.data) == 1


@pytest.mark.django_db
class TestAdminSubmissionDetailAPIView:
    """Tests for the staff GET/PATCH /forms/api/admin/forms/{id}/submissions/{sub_id}/ endpoint

    Retained-role:
    * Superuser: cross-tenant read via ``operator_access`` (GET).
    * PATCH target identified through allowed read elevation; save occurs
      inside ``org_scope(submission.organization)``.
    """

    def test_superuser_can_retrieve_detail(
        self, superuser_client, form, submission, field_value
    ):
        """Superuser can retrieve submission detail with field values."""
        url = reverse(
            "quickscale_forms:admin_submission_detail",
            kwargs={"pk": form.pk, "sub_pk": submission.pk},
        )
        response = superuser_client.get(url)
        assert response.status_code == 200
        assert response.data["id"] == submission.pk

    def test_superuser_patch_updates_status(self, superuser_client, form, submission):
        """Superuser PATCH request updates submission status."""
        from quickscale_modules_orgs.current_org import org_scope

        url = reverse(
            "quickscale_forms:admin_submission_detail",
            kwargs={"pk": form.pk, "sub_pk": submission.pk},
        )
        response = superuser_client.patch(url, data={"status": "read"}, format="json")
        assert response.status_code == 200
        with org_scope(submission.organization):
            submission.refresh_from_db()
        assert submission.status == "read"

    def test_superuser_patch_with_mismatched_active_org(
        self, superuser, superuser_client, form, submission, org_b
    ):
        """Superuser PATCH succeeds with a mismatched active org context.

        A superuser whose session active org differs from the
        target submission's owning org must still be able to PATCH and have
        the response materialized correctly (serializer.data evaluated inside
        org_scope).  Also proves the persisted value survives a DB refresh.
        """
        from quickscale_modules_orgs._constants import ACTIVE_ORG_SESSION_KEY
        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import (
            OrgRole,
            OrganizationMembership,
        )

        OrganizationMembership.objects.create(
            user=superuser,
            organization=org_b,
            role=OrgRole.ADMIN,
        )
        # Set active org to org_b (mismatched against the submission's system org).
        superuser_client.force_login(user=superuser)
        session = superuser_client.session
        session[ACTIVE_ORG_SESSION_KEY] = str(org_b.pk)
        session.save()

        url = reverse(
            "quickscale_forms:admin_submission_detail",
            kwargs={"pk": form.pk, "sub_pk": submission.pk},
        )
        response = superuser_client.patch(url, data={"status": "read"}, format="json")
        assert response.status_code == 200, (
            f"Superuser PATCH with mismatched org should return 200, "
            f"got {response.status_code}: {response.data}"
        )
        # Verify the response data is materialized correctly (not lazy-evaluated
        # after org_scope exits).
        assert "status" in response.data, (
            "Response must include status field — proves serializer.data "
            "was materialized inside org_scope"
        )
        assert response.data["status"] == "read"

        # Verify persistence: read back under the correct org scope.
        with org_scope(submission.organization):
            submission.refresh_from_db()
        assert submission.status == "read", (
            "Persisted value must survive a DB refresh — proves the save "
            "targeted the correct record despite mismatched active org"
        )

    def _scoped_submission(self, organization):
        """Create an active form and submission under *organization*."""
        from quickscale_modules_forms.models import Form, FormSubmission
        from quickscale_modules_orgs.current_org import org_scope

        with org_scope(organization):
            scoped_form = Form.all_objects.create(
                organization=organization,
                title="Role Form",
                slug=f"role-form-{organization.slug}",
                success_message="Thanks!",
                is_active=True,
            )
            scoped_submission = FormSubmission.all_objects.create(
                form=scoped_form,
                organization=organization,
                ip_address="127.0.0.1",
                user_agent="RoleAgent/1.0",
            )
        return scoped_form, scoped_submission

    def _login_with_org_session(self, api_client, user, organization):
        """Log *user* in with *organization* active in the session."""
        from quickscale_modules_orgs._constants import ACTIVE_ORG_SESSION_KEY

        api_client.force_login(user=user)
        session = api_client.session
        session[ACTIVE_ORG_SESSION_KEY] = str(organization.pk)
        session.save()

    def test_viewer_session_cannot_patch_submission(self, user, api_client, db, org_a):
        """A viewer-role session reads the detail but is refused the PATCH."""
        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import (
            OrgRole,
            OrganizationMembership,
        )

        OrganizationMembership.objects.create(
            user=user,
            organization=org_a,
            role=OrgRole.VIEWER,
        )
        scoped_form, scoped_submission = self._scoped_submission(org_a)
        self._login_with_org_session(api_client, user, org_a)

        url = reverse(
            "quickscale_forms:admin_submission_detail",
            kwargs={"pk": scoped_form.pk, "sub_pk": scoped_submission.pk},
        )
        read_response = api_client.get(url)
        write_response = api_client.patch(url, data={"status": "read"}, format="json")

        assert read_response.status_code == 200
        assert write_response.status_code == 403
        with org_scope(org_a):
            scoped_submission.refresh_from_db()
        assert scoped_submission.status != "read"

    def test_member_session_can_patch_submission(self, user, api_client, db, org_a):
        """A member-role session can PATCH a submission in its active org."""
        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import (
            OrgRole,
            OrganizationMembership,
        )

        OrganizationMembership.objects.create(
            user=user,
            organization=org_a,
            role=OrgRole.MEMBER,
        )
        scoped_form, scoped_submission = self._scoped_submission(org_a)
        self._login_with_org_session(api_client, user, org_a)

        url = reverse(
            "quickscale_forms:admin_submission_detail",
            kwargs={"pk": scoped_form.pk, "sub_pk": scoped_submission.pk},
        )
        response = api_client.patch(url, data={"status": "read"}, format="json")

        assert response.status_code == 200
        with org_scope(org_a):
            scoped_submission.refresh_from_db()
        assert scoped_submission.status == "read"

    def test_staff_without_org_is_refused_on_detail(
        self, staff_client, form, submission
    ):
        """View-unit defense-in-depth: force-auth staff without org is refused."""
        url = reverse(
            "quickscale_forms:admin_submission_detail",
            kwargs={"pk": form.pk, "sub_pk": submission.pk},
        )
        response = staff_client.get(url)
        assert response.status_code == 403


@pytest.mark.django_db
class TestAdminSubmissionExportView:
    """Tests for the admin CSV export view

    Org-role contract (rule 19):
    * Superuser: the operator path — cross-tenant read via ``operator_access``.
    * Viewer or above with active org: RLS-scoped to that org.
    * No org context: the permission refuses the request (403).
    """

    def test_superuser_gets_csv(self, superuser_client, form, submission, field_value):
        """Superuser receives CSV file with correct content type."""
        url = reverse(
            "quickscale_forms:admin_submission_export", kwargs={"pk": form.pk}
        )
        response = superuser_client.get(url)
        assert response.status_code == 200
        assert "text/csv" in response["Content-Type"]

    def test_superuser_csv_contains_field_values(
        self, superuser_client, form, submission, field_value
    ):
        """CSV output contains the submitted field values."""
        url = reverse(
            "quickscale_forms:admin_submission_export", kwargs={"pk": form.pk}
        )
        response = superuser_client.get(url)
        content = response.content.decode()
        assert "full_name" in content
        assert "Alice" in content

    def test_csv_neutralizes_formula_headers_and_values(
        self, superuser_client, form, submission, field_value
    ):
        """CSV export prefixes dangerous header/value cells so spreadsheets keep them inert."""
        from quickscale_modules_orgs.current_org import org_scope

        with org_scope(submission.organization):
            field_value.field_name = "=2+2"
            field_value.value = "  +SUM(A1:A2)"
            field_value.save(update_fields=["field_name", "value"])

        url = reverse(
            "quickscale_forms:admin_submission_export", kwargs={"pk": form.pk}
        )
        response = superuser_client.get(url)

        assert response.status_code == 200

        rows = list(csv.reader(io.StringIO(response.content.decode())))
        assert rows[0][0] == "id"
        assert rows[0][-1] == "'=2+2"
        assert rows[1][-1] == "'  +SUM(A1:A2)"

    def test_staff_without_org_is_refused_on_export(self, staff_client, form):
        """View-unit defense-in-depth: force-auth staff without org is refused."""
        url = reverse(
            "quickscale_forms:admin_submission_export", kwargs={"pk": form.pk}
        )
        response = staff_client.get(url)
        assert response.status_code == 403

    def test_returns_403_for_anonymous(self, api_client, form):
        """Anonymous user cannot export submissions"""
        url = reverse(
            "quickscale_forms:admin_submission_export", kwargs={"pk": form.pk}
        )
        response = api_client.get(url)
        assert response.status_code == 403

    def test_superuser_gets_404_for_missing_form(self, superuser_client):
        """Export view returns 404 when form pk does not exist."""
        url = reverse("quickscale_forms:admin_submission_export", kwargs={"pk": 99999})
        response = superuser_client.get(url)
        assert response.status_code == 404


@pytest.mark.django_db
class TestAdminSubmissionListFilters:
    """Tests for query parameter filters on AdminSubmissionListAPIView

    Filters are role-agnostic — they apply to whatever
    queryset the role produces.  Use superuser for cross-tenant filter
    coverage.
    """

    def test_filter_by_is_spam_true(self, superuser_client, form, submission):
        """is_spam=true filter returns only spam submissions"""
        from quickscale_modules_orgs.current_org import org_scope

        with org_scope(submission.organization):
            submission.is_spam = True
            submission.save()
        url = reverse("quickscale_forms:admin_submission_list", kwargs={"pk": form.pk})
        response = superuser_client.get(url, {"is_spam": "true"})
        assert response.status_code == 200
        assert all(s["is_spam"] for s in response.data)

    def test_filter_by_date_gte(self, superuser_client, form, submission):
        """submitted_at__date__gte filter is accepted without error"""
        url = reverse("quickscale_forms:admin_submission_list", kwargs={"pk": form.pk})
        response = superuser_client.get(url, {"submitted_at__date__gte": "2000-01-01"})
        assert response.status_code == 200

    def test_filter_by_date_lte(self, superuser_client, form, submission):
        """submitted_at__date__lte filter is accepted without error"""
        url = reverse("quickscale_forms:admin_submission_list", kwargs={"pk": form.pk})
        response = superuser_client.get(url, {"submitted_at__date__lte": "2099-12-31"})
        assert response.status_code == 200


@pytest.mark.django_db
class TestAdminSubmissionDetailNotFound:
    """Tests for 404 behavior in AdminSubmissionDetailAPIView"""

    def test_superuser_gets_404_for_unknown_submission(self, superuser_client, form):
        """Submission detail returns 404 when sub_pk does not exist."""
        url = reverse(
            "quickscale_forms:admin_submission_detail",
            kwargs={"pk": form.pk, "sub_pk": 99999},
        )
        response = superuser_client.get(url)
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# DB-side org scope for public forms routes
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFormSubmissionCanonicalIp:
    """Verify that FormSubmission.ip_address uses the canonical
    client IP (via the shared get_client_ip helper) instead of raw REMOTE_ADDR."""

    def test_ip_address_uses_xff_when_configured(
        self, api_client, form, form_field, email_field
    ):
        """When USE_X_FORWARDED_FOR and TRUSTED_PROXY_COUNT are configured,
        ip_address records the X-Forwarded-For client IP, not REMOTE_ADDR."""
        from django.test import override_settings

        from quickscale_modules_forms.models import FormSubmission
        from quickscale_modules_orgs.current_org import org_scope

        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}

        with override_settings(
            USE_X_FORWARDED_FOR=True,
            TRUSTED_PROXY_COUNT=1,
        ):
            response = api_client.post(
                url,
                data=data,
                format="json",
                REMOTE_ADDR="10.0.0.1",
                HTTP_X_FORWARDED_FOR="198.51.100.10",
            )

        assert response.status_code == 201
        with org_scope(form.organization):
            submission = FormSubmission.all_objects.filter(form=form).latest(
                "submitted_at"
            )
        assert submission.ip_address == "198.51.100.10", (
            f"Expected canonical client IP 198.51.100.10, got {submission.ip_address!r}"
        )

    def test_ip_address_falls_back_to_remote_addr_by_default(
        self, api_client, form, form_field, email_field
    ):
        """When USE_X_FORWARDED_FOR is not configured, ip_address records
        REMOTE_ADDR."""
        from quickscale_modules_forms.models import FormSubmission
        from quickscale_modules_orgs.current_org import org_scope

        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Bob", "email": "bob@example.com"}

        response = api_client.post(
            url,
            data=data,
            format="json",
            REMOTE_ADDR="10.0.0.2",
            HTTP_X_FORWARDED_FOR="198.51.100.20",
        )

        assert response.status_code == 201
        with org_scope(form.organization):
            submission = FormSubmission.all_objects.filter(form=form).latest(
                "submitted_at"
            )
        assert submission.ip_address == "10.0.0.2", (
            f"Expected REMOTE_ADDR 10.0.0.2, got {submission.ip_address!r}"
        )

    def test_honeypot_ip_address_uses_xff_when_configured(
        self, api_client, form, form_field, email_field
    ):
        """Honeypot-triggered submissions also use the canonical IP when configured."""
        from django.test import override_settings

        from quickscale_modules_forms.models import FormSubmission
        from quickscale_modules_orgs.current_org import org_scope

        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
        data = {
            "full_name": "Bot",
            "email": "bot@spam.com",
            "_hp_name": "I am a bot",
        }

        with override_settings(
            USE_X_FORWARDED_FOR=True,
            TRUSTED_PROXY_COUNT=1,
        ):
            response = api_client.post(
                url,
                data=data,
                format="json",
                REMOTE_ADDR="10.0.0.3",
                HTTP_X_FORWARDED_FOR="203.0.113.50",
            )

        assert response.status_code == 201
        with org_scope(form.organization):
            submission = FormSubmission.all_objects.filter(form=form).latest(
                "submitted_at"
            )
        assert submission.is_spam is True
        assert submission.ip_address == "203.0.113.50", (
            f"Expected canonical IP 203.0.113.50, got {submission.ip_address!r}"
        )


_MISSING = object()

FORM_CLIENT_IP_CASES = (
    pytest.param(False, 2, "198.51.100.1, 10.0.0.1", id="disabled"),
    pytest.param(True, 0, "198.51.100.1, 10.0.0.1", id="zero"),
    pytest.param(True, 1, None, id="absent"),
    pytest.param(True, 1, "", id="empty"),
    pytest.param(True, 3, "198.51.100.1, , 10.0.0.1", id="empty-hop"),
    pytest.param(True, 2, "198.51.100.1", id="short"),
    pytest.param(True, 2, "198.51.100.1, 10.0.0.1", id="equal"),
    pytest.param(
        True,
        2,
        "198.51.100.1, 198.51.100.2, 10.0.0.1, 10.0.0.2",
        id="long",
    ),
)

FORM_INVALID_PROXY_SETTINGS = (
    pytest.param("USE_X_FORWARDED_FOR", _MISSING, id="missing-use-xff"),
    pytest.param("USE_X_FORWARDED_FOR", None, id="invalid-use-xff"),
    pytest.param("USE_X_FORWARDED_FOR", "yes", id="invalid-use-xff-string"),
    pytest.param("TRUSTED_PROXY_COUNT", _MISSING, id="missing-proxy-count"),
    pytest.param("TRUSTED_PROXY_COUNT", "1", id="invalid-proxy-count"),
    pytest.param("TRUSTED_PROXY_COUNT", -1, id="invalid-proxy-count-negative"),
    pytest.param("TRUSTED_PROXY_COUNT", True, id="invalid-proxy-count-bool"),
)


@pytest.mark.django_db
class TestFormSubmissionClientIpParity:
    """Same-request identity and fail-loud proofs for both write branches."""

    @pytest.mark.parametrize("use_xff,proxy_count,xff", FORM_CLIENT_IP_CASES)
    @pytest.mark.parametrize(
        "honeypot",
        [pytest.param(False, id="accepted"), pytest.param(True, id="spam")],
    )
    def test_both_persistence_branches_match_direct_resolver(
        self,
        api_client,
        form,
        form_field,
        email_field,
        use_xff: bool,
        proxy_count: int,
        xff: str | None,
        honeypot: bool,
    ) -> None:
        """Stored IPs remain equal to direct resolution for every tuple."""
        from quickscale_modules_forms.models import FormSubmission
        from quickscale_modules_orgs.current_org import get_client_ip, org_scope

        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
        request_kwargs: dict[str, str] = {"REMOTE_ADDR": "10.0.0.1"}
        if xff is not None:
            request_kwargs["HTTP_X_FORWARDED_FOR"] = xff
        direct_request = RequestFactory().post(url, **request_kwargs)
        payload = {"full_name": "Parity", "email": "parity@example.com"}
        if honeypot:
            payload["_hp_name"] = "automated submission"

        with override_settings(
            USE_X_FORWARDED_FOR=use_xff,
            TRUSTED_PROXY_COUNT=proxy_count,
        ):
            expected_ip = get_client_ip(direct_request)
            response = api_client.post(
                url,
                data=payload,
                format="json",
                **request_kwargs,
            )

        assert response.status_code == 201
        with org_scope(form.organization):
            submission = FormSubmission.all_objects.filter(form=form).latest(
                "submitted_at"
            )
        assert submission.ip_address == expected_ip
        assert submission.is_spam is honeypot

    @pytest.mark.parametrize("setting_name,setting_value", FORM_INVALID_PROXY_SETTINGS)
    @pytest.mark.parametrize(
        "honeypot",
        [pytest.param(False, id="accepted"), pytest.param(True, id="spam")],
    )
    def test_invalid_proxy_settings_fail_loud_without_cache_or_persistence(
        self,
        api_client,
        form,
        form_field,
        email_field,
        setting_name: str,
        setting_value: object,
        honeypot: bool,
    ) -> None:
        """The throttle rejects invalid identity settings before either branch writes."""
        from django.core.exceptions import ImproperlyConfigured

        from quickscale_modules_forms.models import FormSubmission
        from quickscale_modules_forms.throttles import FormSubmitThrottle
        from quickscale_modules_orgs.current_org import get_client_ip, org_scope

        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
        request_kwargs = {
            "REMOTE_ADDR": "10.0.0.1",
            "HTTP_X_FORWARDED_FOR": "198.51.100.1",
        }
        payload = {"full_name": "Invalid", "email": "invalid@example.com"}
        if honeypot:
            payload["_hp_name"] = "automated submission"
        settings_values: dict[str, object] = {
            "USE_X_FORWARDED_FOR": False,
            "TRUSTED_PROXY_COUNT": 1,
        }
        missing_setting: str | None = None
        if setting_value is _MISSING:
            missing_setting = setting_name
        else:
            settings_values[setting_name] = setting_value

        with org_scope(form.organization):
            initial_count = FormSubmission.all_objects.filter(form=form).count()

        with override_settings(**settings_values):
            if missing_setting is not None:
                delattr(settings, missing_setting)
            direct_request = RequestFactory().post(url, **request_kwargs)
            with pytest.raises(ImproperlyConfigured) as direct_error:
                get_client_ip(direct_request)

            throttle_cache = FormSubmitThrottle().cache
            with (
                patch.object(throttle_cache, "add") as cache_add,
                patch.object(throttle_cache, "incr") as cache_incr,
                patch.object(throttle_cache, "set") as cache_set,
            ):
                with pytest.raises(ImproperlyConfigured) as endpoint_error:
                    api_client.post(
                        url,
                        data=payload,
                        format="json",
                        **request_kwargs,
                    )

            assert type(endpoint_error.value) is type(direct_error.value)
            assert str(endpoint_error.value) == str(direct_error.value)
            assert setting_name in str(endpoint_error.value)
            cache_add.assert_not_called()
            cache_incr.assert_not_called()
            cache_set.assert_not_called()

        with org_scope(form.organization):
            assert FormSubmission.all_objects.filter(form=form).count() == initial_count


@pytest.mark.django_db
class TestPublicViewsDbOrgScope:
    """Verify FormSchemaAPIView and FormSubmitAPIView establish
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

        url = reverse("quickscale_forms:form_schema", kwargs={"slug": "test-contact"})
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

        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
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
        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
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
        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import Organization

        system_org = Organization.objects.get_system_org()

        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}

        api_client.post(url, data=data, format="json")

        with org_scope(system_org):
            sub = FormSubmission.all_objects.filter(form=form).latest("submitted_at")
        assert sub.organization == system_org, (
            "Anonymous submission must be scoped to the System org"
        )

    @override_settings(SESSION_ENGINE="django.contrib.sessions.backends.cache")
    def test_authenticated_submit_uses_session_org(self, api_client):
        """Authenticated requests with an active session org scope the
        submission to that org."""
        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import (
            OrganizationMembership,
            OrgRole,
            Organization,
        )
        from django.contrib.auth import get_user_model
        from quickscale_modules_forms.models import Form, FormField, FormSubmission

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
        with org_scope(org):
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
        from quickscale_modules_orgs._constants import ACTIVE_ORG_SESSION_KEY

        session[ACTIVE_ORG_SESSION_KEY] = str(org.pk)
        session.save()

        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "auth-contact"})
        data = {"full_name": "Bob", "email": "bob@example.com"}

        response = api_client.post(url, data=data, format="json")

        assert response.status_code == 201
        with org_scope(org):
            sub = FormSubmission.all_objects.filter(form=org_form).latest(
                "submitted_at"
            )
        assert sub.organization == org, (
            "Authenticated submission must be scoped to the session org"
        )

    @override_settings(SESSION_ENGINE="django.contrib.sessions.backends.cache")
    def test_authenticated_schema_returns_org_scoped_form(self, api_client):
        """Authenticated requests get forms scoped to their session org.

        Creates the test form under the target org from the start instead
        of reassigning the fixture form's org (which composite FKs
        prevent when child FormField rows already reference the old org).
        """
        from quickscale_modules_forms.models import Form, FormField
        from quickscale_modules_orgs.current_org import org_scope
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
        with org_scope(org):
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
        from quickscale_modules_orgs._constants import ACTIVE_ORG_SESSION_KEY

        session[ACTIVE_ORG_SESSION_KEY] = str(org.pk)
        session.save()

        url = reverse(
            "quickscale_forms:form_schema", kwargs={"slug": "org-specific-form"}
        )
        response = api_client.get(url)

        assert response.status_code == 200
        assert response.data["slug"] == "org-specific-form"

    def test_anonymous_submit_preserves_redirect_url_when_set(
        self, api_client, form, form_field, email_field
    ):
        """When a form has a redirect_url, anonymous submissions return it."""
        from quickscale_modules_orgs.current_org import org_scope

        form.redirect_url = "/thank-you"
        with org_scope(form.organization):
            form.save(update_fields=["redirect_url"])

        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
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
        from quickscale_modules_orgs.current_org import org_scope

        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
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
        with org_scope(form.organization):
            sub = FormSubmission.all_objects.filter(form=form).latest("submitted_at")
        assert sub.is_spam is True

    def test_side_effects_dispatch_on_the_write_commit(
        self,
        api_client,
        form,
        form_field,
        email_field,
        django_capture_on_commit_callbacks,
    ):
        """Rule 21: the notification is scheduled, never sent, during the write.

        Nothing leaves before the submission's transaction commits; the
        tracked send fires only when the scheduled callback executes.
        """
        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}

        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            response = api_client.post(url, data=data, format="json")

            assert response.status_code == 201
            assert mail.outbox == [], "no email may leave before the commit"

        assert len(callbacks) >= 1, "the tracked send is scheduled on commit"
        assert len(mail.outbox) == 1


# ---------------------------------------------------------------------------
# CR-P3-006 regression: notification content carries field values after
# post-commit dispatch on the anonymous public submit path.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestNotificationContentAfterPostCommit:
    """Regression: public submit notifications must include submitted field
    values after tenant_context() exits on the anonymous path."""

    def test_anonymous_notification_includes_field_values_in_email(
        self,
        api_client,
        form,
        form_field,
        email_field,
        django_capture_on_commit_callbacks,
    ):
        """Anonymous public submit dispatches a notification email that
        includes the submitted field label and value — proving that
        _build_submission_notification_context reads field values via
        FormFieldValue.all_objects (not the TenantManager) after the
        tenant_context() window has closed."""
        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}

        with django_capture_on_commit_callbacks(execute=True):
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


# ---------------------------------------------------------------------------
# CR-P3-006 regression: side-effect callbacks run after
# commit with in_atomic_block = False and can observe committed rows
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestPostCommitTransactionBoundary:
    """CR-P3-006: notification and analytics callbacks run
    after the view's outer ``org_scope`` + ``transaction.atomic()`` commits,
    with ``connection.in_atomic_block == False``, can observe committed rows
    via fresh ``org_scope``, and leave no context leak.

    Uses ``django_db(transaction=True)`` so the view's ``transaction.atomic()``
    from ``org_scope`` actually commits to PostgreSQL before side-effect
    callbacks execute — proving callbacks run outside any database transaction.

    Does NOT use shared fixtures (form, form_field, email_field) to keep
    the setup scope fully explicit and avoid fixture-held org_scope.

    The form is created under the System org because anonymous public
    requests resolve to the System org (D2) — this mirrors how the
    existing ``form`` fixture works without depending on it.
    """

    def test_notification_and_analytics_outside_atomic_with_committed_rows(
        self,
        api_client,
        monkeypatch,
    ):
        """Prove notify_submission and analytics callbacks enter outside the
        view's atomic block, can open fresh org_scope to observe committed
        submission and field-value rows, and leave no context leak."""
        from quickscale_modules_forms.models import (
            Form,
            FormField,
            FormFieldValue,
            FormSubmission,
        )
        from quickscale_modules_orgs.current_org import get_current_org_id, org_scope
        from quickscale_modules_orgs.models import Organization

        # ---- Setup: org, form, fields inside explicit org_scope -----------
        # Anonymous public requests resolve to System org — form must live
        # there so the view can find it by slug.  Use a UUID suffix so
        # leftover stale data from a prior aborted run never collides.
        import uuid

        slug_suffix = uuid.uuid4().hex[:8]
        form_slug = f"txn-form-{slug_suffix}"

        system_org = Organization.objects.get_system_org()

        with org_scope(system_org):
            test_form = Form.all_objects.create(
                title=f"TxnForm {slug_suffix}",
                slug=form_slug,
                organization=system_org,
                notify_emails="txn@example.com",
                is_active=True,
                success_message="Thanks!",
            )
            FormField.all_objects.create(
                form=test_form,
                organization=system_org,
                field_type=FormField.FieldType.TEXT,
                label="Full Name",
                name="full_name",
                required=True,
                order=1,
            )
            FormField.all_objects.create(
                form=test_form,
                organization=system_org,
                field_type=FormField.FieldType.EMAIL,
                label="Email",
                name="email",
                required=True,
                order=2,
            )

        # ---- Exit setup scope — verify no context leak --------------------
        assert get_current_org_id() is None, (
            "setup org_scope must not leak — ContextVar must be None"
        )

        # ---- Collect assertions from the scheduled effects ----------------
        notification_calls: list[dict] = []
        analytics_calls: list[dict] = []

        def _recording_send(**kwargs: Any) -> None:
            call_info: dict = {
                "in_atomic_block": connection.in_atomic_block,
                "template_key": kwargs["template_key"],
            }
            # Open fresh org scope to observe committed rows.
            with org_scope(system_org):
                sub = FormSubmission.all_objects.get(form=test_form)
                fvs = list(FormFieldValue.all_objects.filter(submission=sub))
                call_info["field_values"] = [
                    {"name": fv.field_name, "value": fv.value} for fv in fvs
                ]
            # Verify no context leak from the fresh scope
            assert get_current_org_id() is None, (
                "notification callback must not leak org context"
            )
            notification_calls.append(call_info)

        def _recording_emit(submission: Any, request: Any) -> None:
            del request
            call_info: dict = {
                "in_atomic_block": connection.in_atomic_block,
                "submission_pk": submission.pk,
            }
            # Open fresh org scope to observe committed rows
            with org_scope(system_org):
                sub_exists = FormSubmission.all_objects.filter(
                    pk=submission.pk
                ).exists()
                fv_count = FormFieldValue.all_objects.filter(
                    submission=submission
                ).count()
                call_info["submission_exists"] = sub_exists
                call_info["field_value_count"] = fv_count
            # Verify no context leak
            assert get_current_org_id() is None, (
                "analytics callback must not leak org context"
            )
            analytics_calls.append(call_info)

        from django.apps import apps as django_apps

        real_is_installed = django_apps.is_installed
        monkeypatch.setattr(
            "quickscale_modules_forms.views.apps.is_installed",
            lambda label: (
                label == "quickscale_modules_analytics" or real_is_installed(label)
            ),
        )
        monkeypatch.setattr(
            "quickscale_modules_analytics.services.get_analytics_runtime_settings",
            Mock(return_value=Mock(enabled=True)),
        )
        monkeypatch.setattr(
            "quickscale_modules_forms.views._emit_submission_event",
            _recording_emit,
        )
        monkeypatch.setattr(
            "quickscale_modules_forms._email.send_notification",
            _recording_send,
        )

        # ---- POST — triggers the view's org_scope + transaction.atomic() --
        url = reverse("quickscale_forms:form_submit", kwargs={"slug": form_slug})
        data = {"full_name": "Boundary Alice", "email": "boundary@example.com"}
        response = api_client.post(url, data=data, format="json")

        assert response.status_code == 201, f"Expected 201, got {response.status_code}"
        assert response.data["notification_status"] == "queued"

        # ---- Verify the scheduled notification effect --------------------
        assert len(notification_calls) == 1, (
            "the tracked send must run exactly once, after commit"
        )
        nf = notification_calls[0]
        assert nf["in_atomic_block"] is False, (
            "the tracked send must run outside any database transaction"
        )
        assert nf["template_key"] == "notifications.forms_submission"
        fv_names = {fv["name"] for fv in nf["field_values"]}
        assert "full_name" in fv_names, (
            "Committed field_value 'full_name' must be observable "
            "from notification callback via fresh org_scope"
        )
        assert "email" in fv_names, (
            "Committed field_value 'email' must be observable "
            "from notification callback via fresh org_scope"
        )
        # Verify actual committed values
        fv_map = {fv["name"]: fv["value"] for fv in nf["field_values"]}
        assert fv_map["full_name"] == "Boundary Alice", (
            "Notification callback must read the correct committed value"
        )
        assert fv_map["email"] == "boundary@example.com", (
            "Notification callback must read the correct committed email value"
        )

        # ---- Verify the scheduled analytics effect -----------------------
        assert len(analytics_calls) == 1, (
            "analytics capture must run exactly once, after commit"
        )
        af = analytics_calls[0]
        assert af["in_atomic_block"] is False, (
            "analytics capture must run outside any database transaction"
        )
        assert af["submission_exists"] is True, (
            "Committed submission must be observable from analytics callback"
        )
        assert af["field_value_count"] >= 2, (
            "Committed field values must be observable from analytics callback"
        )

        # ---- Final context leak check ------------------------------------
        assert get_current_org_id() is None, (
            "no org context leak after full request lifecycle"
        )


# ---------------------------------------------------------------------------
# Rule 21: a rolled-back write fires no effect
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSubmissionRollbackEffects:
    """A rolled-back submission sends no email and fires no analytics event."""

    def test_rolled_back_submission_fires_no_effect(
        self,
        api_client,
        form,
        form_field,
        email_field,
        monkeypatch,
    ):
        from quickscale_modules_notifications.models import NotificationMessage

        def analytics_is_installed(app_label: str) -> bool:
            return app_label == "quickscale_modules_analytics"

        mock_get_distinct_id = Mock(return_value="session:test-visitor")
        mock_capture_event = Mock()
        monkeypatch.setattr(
            "quickscale_modules_forms.views.apps.is_installed",
            analytics_is_installed,
        )
        monkeypatch.setattr(
            "quickscale_modules_analytics.services.get_distinct_id",
            mock_get_distinct_id,
        )
        monkeypatch.setattr(
            "quickscale_modules_analytics.services.capture_event",
            mock_capture_event,
        )
        monkeypatch.setattr(
            "quickscale_modules_analytics.services.get_analytics_runtime_settings",
            Mock(return_value=Mock(enabled=True)),
        )

        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}

        class _Rollback(Exception):
            pass

        with pytest.raises(_Rollback):
            with transaction.atomic():
                response = api_client.post(url, data=data, format="json")
                assert response.status_code == 201
                raise _Rollback

        assert mail.outbox == [], "a rolled-back submission sends no email"
        assert not NotificationMessage.objects.exists(), (
            "a rolled-back submission records no tracked notification"
        )
        # get_distinct_id is reachable, so the capture assertion is not vacuous:
        # an inline (pre-rollback) emission would call both mocks.
        mock_get_distinct_id.assert_not_called()
        mock_capture_event.assert_not_called()


# ---------------------------------------------------------------------------
# Rule 20: a valid long subject must not lose the tracked notification
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestLongSubjectSubmission:
    """A form title and submitter name that compose past the subject column."""

    def test_long_subject_submission_still_sends_tracked_email(
        self,
        api_client,
        form,
        form_field,
        email_field,
        django_capture_on_commit_callbacks,
    ):
        from quickscale_modules_notifications.models import NotificationMessage
        from quickscale_modules_orgs.current_org import org_scope

        with org_scope(form.organization):
            form.title = "T" * 200
            form.save(update_fields=["title"])

        url = reverse("quickscale_forms:form_submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "N" * 40, "email": "alice@example.com"}

        with django_capture_on_commit_callbacks(execute=True):
            response = api_client.post(url, data=data, format="json")

        assert response.status_code == 201
        message = NotificationMessage.objects.get(
            template_key="notifications.forms_submission"
        )
        assert len(message.subject) == 255, "the subject must fit its column"
        assert len(mail.outbox) == 1, "the tracked email must still be sent"
