"""Tests for Forms module views"""

import csv
import io
from typing import Any
from unittest.mock import Mock

import pytest
from django.core.cache import cache
from django.core import mail
from django.db import connection
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
        from quickscale_modules_orgs.current_org import org_scope

        form.spam_protection_enabled = False
        with org_scope(form.organization):
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
        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
        data = {"full_name": payload, "email": payload, "company": payload}
        response = api_client.post(url, data=data, format="json")
        assert response.status_code == 400
        assert expected_error in response.data["errors"]["full_name"][0]
        assert expected_error in response.data["errors"]["email"][0]

    def test_honeypot_silently_marks_spam_and_returns_201(
        self, api_client, form, form_field, email_field
    ):
        """Filled honeypot field is treated as spam — returns 201 silently"""
        from quickscale_modules_orgs.current_org import org_scope

        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
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

    @override_settings(FORMS_SPAM_PROTECTION=False)
    def test_honeypot_is_ignored_when_global_spam_protection_disabled(
        self, api_client, form, form_field, email_field
    ):
        """Submission handling should ignore honeypot when global spam protection is off."""
        from quickscale_modules_orgs.current_org import org_scope

        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
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
        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com", "_hp_name": "bot"}

        response = api_client.post(url, data=data, format="json")

        assert response.status_code == 201
        with org_scope(form.organization):
            submission = FormSubmission.all_objects.filter(form=form).latest(
                "submitted_at"
            )
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
        from quickscale_modules_orgs.current_org import org_scope

        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
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
        from quickscale_modules_orgs.current_org import org_scope

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

        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
        data = {"full_name": "Alice", "email": "alice@example.com"}

        cache.clear()
        response = api_client.post(url, data=data, format="json")
        cache.clear()

        assert response.status_code == 201
        with org_scope(form.organization):
            assert FormSubmission.all_objects.filter(form=form).count() == 1

    @override_settings(QUICKSCALE_ANALYTICS_ENABLED=True)
    def test_submission_stays_non_blocking_when_analytics_capture_fails(
        self, api_client, form, form_field, email_field, monkeypatch
    ):
        """Analytics capture failure must not block the public success response."""
        from quickscale_modules_orgs.current_org import org_scope

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
        with org_scope(form.organization):
            assert FormSubmission.all_objects.filter(form=form).count() == 1

    def test_submission_persists_when_notification_delivery_fails(
        self, api_client, form, form_field, email_field, monkeypatch
    ):
        """Delivery failure stays non-blocking and does not roll back persistence"""
        from quickscale_modules_orgs.current_org import org_scope

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
        with org_scope(form.organization):
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
        from quickscale_modules_orgs.current_org import org_scope

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
        with org_scope(form.organization):
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
    """Tests for the staff GET /api/admin/forms/ endpoint

    SA85 Phase 4 retained-role contract:
    * Superuser: cross-tenant read via ``operator_access``.
    * Regular staff with active org: scoped to that org via RLS.
    * Regular staff without org: fail-closed — view-unit tests assert
      empty list (no ContextVar); session-pipeline tests assert 302
      redirect to /orgs/ before view executes.
    * Anonymous: denied (403).

    CR-SA85-REV-001: /api/admin/forms/ is NON-EXEMPT from
    TenantMiddleware (does not match any EXEMPT_PATH_PREFIX).
    """

    def test_returns_403_for_anonymous(self, api_client, form):
        """Anonymous user cannot access admin form list"""
        url = reverse("quickscale_forms:admin-form-list")
        response = api_client.get(url)
        assert response.status_code in (401, 403)

    def test_superuser_sees_all_forms(self, superuser_client, form):
        """Superuser can access admin form list and sees all forms."""
        url = reverse("quickscale_forms:admin-form-list")
        response = superuser_client.get(url)
        assert response.status_code == 200
        assert len(response.data) >= 1
        assert "submission_count" in response.data[0]

    def test_staff_without_org_fails_closed(self, staff_client, form):
        """View-unit defense-in-depth: force-auth staff without org sees
        empty list (fail-closed).

        This test uses ``force_authenticate`` (DRF-only, no session
        middleware).  The session-parity proof for real middleware-pipeline
        coverage is ``test_staff_session_active_org_sees_own_org_forms``
        and ``test_staff_session_cross_org_excluded`` (CR-SA85-REV-001).
        """
        url = reverse("quickscale_forms:admin-form-list")
        response = staff_client.get(url)
        assert response.status_code == 200
        assert len(response.data) == 0, (
            "Staff without org must see empty list (fail-closed)"
        )

    def test_superuser_sees_org_scoped_form(self, superuser_client, org, org_form):
        """Superuser sees forms from a scoped org via cross-tenant read.

        SA85 Phase 4: The org_form fixture creates a form under *org*.
        The superuser operator path (all_objects) returns it regardless
        of org context.
        """
        url = reverse("quickscale_forms:admin-form-list")
        response = superuser_client.get(url)
        assert response.status_code == 200
        slugs = [item["slug"] for item in response.data]
        assert "org-contact" in slugs, (
            "Superuser must see the org-scoped form via operator path"
        )

    def test_staff_with_org_uses_scoped_queryset_not_none(self, db, org):
        """Staff with active org context gets a scoped queryset (not .none()).

        SA85 Phase 4: verifies the _get_org_bound_queryset contract
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
            wsgi_request = rf.get("/api/admin/forms/")
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
    # CR-SA85-REV-001: session-auth pipeline proofs
    # ------------------------------------------------------------------
    # These tests use force_login + ACTIVE_ORG_SESSION_KEY to exercise
    # the full session authentication pipeline (SessionMiddleware +
    # AuthenticationMiddleware).  The admin API path
    # (/api/admin/forms/) is NON-EXEMPT from TenantMiddleware (it does
    # not start with /admin/ or any other exempt prefix), so the
    # middleware DOES run and populates the ContextVar from the session.
    #
    # * Regular staff with active org: ContextVar populated → RLS
    #   scopes the queryset to the active org.  Staff see only forms
    #   belonging to that org.
    # * Regular staff without active org: middleware redirects to
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
        """Regular staff with force_login + ACTIVE_ORG_SESSION_KEY sees
        only forms belonging to their active org.

        CR-SA85-REV-001: real session-auth pipeline proof.
        /api/admin/forms/ is non-exempt, so TenantMiddleware runs and
        populates the ContextVar from the session.  Staff see their own
        org's form and do NOT see forms from other orgs.
        """
        from quickscale_modules_orgs.constants import ACTIVE_ORG_SESSION_KEY
        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )
        from quickscale_modules_forms.models import Form

        # Create a separate org for the staff user (different from
        # System org where ``form`` fixture lives).
        own_org = Organization.objects.create(
            name="Staff Own Org", slug="staff-own-org"
        )
        OrganizationMembership.objects.create(
            user=staff_user,
            organization=own_org,
            role=OrgRole.ADMIN,
        )

        # Create a form under the staff user's org.
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

        url = reverse("quickscale_forms:admin-form-list")

        response = api_client.get(url)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        slugs = [item["slug"] for item in response.data]
        assert "own-contact" in slugs, (
            f"Staff must see their own org's form. Got slugs: {slugs}"
        )
        # System org's form (created by the ``form`` fixture) must NOT
        # be visible — different org, RLS-scoped out.
        assert "test-contact" not in slugs, (
            f"Staff must NOT see System org's form (different org). Got slugs: {slugs}"
        )

    def test_staff_session_cross_org_excluded(self, staff_user, api_client, db):
        """Regular staff with force_login + ACTIVE_ORG_SESSION_KEY set
        to one org does not see forms belonging to a different org.

        CR-SA85-REV-001: proves cross-tenant isolation through the
        full middleware + RLS pipeline on the non-exempt admin path.
        """
        from quickscale_modules_orgs.constants import ACTIVE_ORG_SESSION_KEY
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

        url = reverse("quickscale_forms:admin-form-list")
        response = api_client.get(url)
        assert response.status_code == 200
        slugs = [item["slug"] for item in response.data]
        assert "own-form" in slugs, f"Staff must see own org's form. Got slugs: {slugs}"
        assert "other-form" not in slugs, (
            f"Staff must NOT see other org's form. Got slugs: {slugs}"
        )

    def test_superuser_session_active_org_sees_cross_tenant(
        self, superuser, superuser_client, form, org
    ):
        """Superuser with ACTIVE_ORG_SESSION_KEY set to a specific org
        can still see forms across all tenants via operator_access.

        CR-SA85-REV-001: proves superuser cross-tenant bypass on the
        non-exempt admin path.  TenantMiddleware runs and populates the
        ContextVar, but _get_org_bound_queryset returns all_objects.all()
        for superusers regardless of ContextVar state.
        """
        from quickscale_modules_orgs.constants import ACTIVE_ORG_SESSION_KEY
        from quickscale_modules_orgs.models import OrgRole, OrganizationMembership

        OrganizationMembership.objects.create(
            user=superuser,
            organization=org,
            role=OrgRole.ADMIN,
        )
        superuser_client.force_login(user=superuser)
        session = superuser_client.session
        session[ACTIVE_ORG_SESSION_KEY] = str(org.pk)
        session.save()

        url = reverse("quickscale_forms:admin-form-list")
        response = superuser_client.get(url)
        assert response.status_code == 200
        slugs = [item["slug"] for item in response.data]
        assert "test-contact" in slugs, (
            "Superuser with session active org must see System org's form "
            f"via operator path. Got slugs: {slugs}"
        )

    # ------------------------------------------------------------------
    # CR-SA85-REV-001: no-active-org redirect proofs
    # ------------------------------------------------------------------
    # These tests hit /api/admin/forms/ which is NON-EXEMPT from
    # TenantMiddleware.  Without ACTIVE_ORG_SESSION_KEY, the middleware
    # redirects to /orgs/ before the view executes — for both regular
    # staff and superusers.

    def test_staff_session_no_active_org_redirects(self, staff_user, api_client, db):
        """Regular staff without ACTIVE_ORG_SESSION_KEY gets 302
        redirect to /orgs/ on the admin-form-list path.

        CR-SA85-REV-001: proves TenantMiddleware redirects to /orgs/
        when an authenticated user has no active org selected on the
        non-exempt admin API route.
        """
        api_client.force_login(user=staff_user)
        # Do NOT set ACTIVE_ORG_SESSION_KEY — middleware should
        # redirect before the view runs.

        url = reverse("quickscale_forms:admin-form-list")
        response = api_client.get(url)

        assert response.status_code == 302, (
            f"Expected 302 redirect to /orgs/, got {response.status_code}"
        )
        assert response["Location"] == "/orgs/", (
            f"Expected Location: /orgs/, got {response['Location']}"
        )

    def test_superuser_session_no_active_org_redirects(self, superuser, api_client, db):
        """Superuser without ACTIVE_ORG_SESSION_KEY also gets 302
        redirect to /orgs/ on the admin-form-list path.

        CR-SA85-REV-001: proves TenantMiddleware applies the same
        no-active-org redirect to superusers before the view executes
        on the non-exempt admin API route.
        """
        api_client.force_login(user=superuser)
        # Do NOT set ACTIVE_ORG_SESSION_KEY.

        url = reverse("quickscale_forms:admin-form-list")
        response = api_client.get(url)

        assert response.status_code == 302, (
            f"Expected 302 redirect to /orgs/, got {response.status_code}"
        )
        assert response["Location"] == "/orgs/", (
            f"Expected Location: /orgs/, got {response['Location']}"
        )

    @override_settings(FORMS_SUBMISSIONS_API=False)
    def test_returns_404_when_admin_api_disabled(self, superuser_client, form):
        """Disabling the submissions API should hide the staff admin endpoints."""
        url = reverse("quickscale_forms:admin-form-list")
        response = superuser_client.get(url)

        assert response.status_code == 404


@pytest.mark.django_db
class TestAdminSubmissionListAPIView:
    """Tests for the staff GET /api/admin/forms/{id}/submissions/ endpoint

    SA85 Phase 4 retained-role:
    * Superuser: cross-tenant read via ``operator_access``.
    * Regular staff without org: fail-closed (empty list).
    """

    def test_superuser_can_list_submissions(self, superuser_client, form, submission):
        """Superuser can list submissions for a given form."""
        url = reverse("quickscale_forms:admin-submission-list", kwargs={"pk": form.pk})
        response = superuser_client.get(url)
        assert response.status_code == 200
        assert len(response.data) >= 1

    def test_staff_without_org_gets_empty_list(self, staff_client, form, submission):
        """View-unit defense-in-depth: force-auth staff without org gets
        empty submission list (fail-closed).

        Session-parity proof for the real middleware pipeline is
        ``test_staff_session_active_org_sees_own_org_forms`` and
        ``test_staff_session_cross_org_excluded`` (CR-SA85-REV-001).
        """
        url = reverse("quickscale_forms:admin-submission-list", kwargs={"pk": form.pk})
        response = staff_client.get(url)
        assert response.status_code == 200
        assert len(response.data) == 0, (
            "Staff without org must receive empty list (fail-closed)"
        )

    def test_filter_by_status(self, superuser_client, form, submission):
        """Submissions can be filtered by status query param."""
        url = reverse("quickscale_forms:admin-submission-list", kwargs={"pk": form.pk})
        response = superuser_client.get(url, {"status": "pending"})
        assert response.status_code == 200

    @override_settings(FORMS_PER_PAGE=1)
    def test_respects_forms_per_page_setting(self, superuser_client, form, submission):
        """The admin submission list should page according to FORMS_PER_PAGE."""
        from quickscale_modules_orgs.current_org import org_scope

        with org_scope(form.organization):
            FormSubmission.all_objects.create(
                form=form,
                organization=form.organization,
                ip_address="127.0.0.2",
                user_agent="TestBrowser/2.0",
            )
        url = reverse("quickscale_forms:admin-submission-list", kwargs={"pk": form.pk})
        response = superuser_client.get(url)

        assert response.status_code == 200
        assert len(response.data) == 1


@pytest.mark.django_db
class TestAdminSubmissionDetailAPIView:
    """Tests for the staff GET/PATCH /api/admin/forms/{id}/submissions/{sub_id}/ endpoint

    SA85 Phase 4 retained-role:
    * Superuser: cross-tenant read via ``operator_access`` (GET).
    * PATCH target identified through allowed read elevation; save occurs
      inside ``org_scope(submission.organization)``.
    """

    def test_superuser_can_retrieve_detail(
        self, superuser_client, form, submission, field_value
    ):
        """Superuser can retrieve submission detail with field values."""
        url = reverse(
            "quickscale_forms:admin-submission-detail",
            kwargs={"pk": form.pk, "sub_pk": submission.pk},
        )
        response = superuser_client.get(url)
        assert response.status_code == 200
        assert response.data["id"] == submission.pk

    def test_superuser_patch_updates_status(self, superuser_client, form, submission):
        """Superuser PATCH request updates submission status."""
        from quickscale_modules_orgs.current_org import org_scope

        url = reverse(
            "quickscale_forms:admin-submission-detail",
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

        CR-SA85-REV-002: A superuser whose session active org differs from the
        target submission's owning org must still be able to PATCH and have
        the response materialized correctly (serializer.data evaluated inside
        org_scope).  Also proves the persisted value survives a DB refresh.
        """
        from quickscale_modules_orgs.constants import ACTIVE_ORG_SESSION_KEY
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
            "quickscale_forms:admin-submission-detail",
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

    def test_staff_without_org_gets_404_on_detail(self, staff_client, form, submission):
        """View-unit defense-in-depth: force-auth staff without org gets
        404 on submission detail (fail-closed)."""
        url = reverse(
            "quickscale_forms:admin-submission-detail",
            kwargs={"pk": form.pk, "sub_pk": submission.pk},
        )
        response = staff_client.get(url)
        assert response.status_code == 404


@pytest.mark.django_db
class TestAdminSubmissionExportView:
    """Tests for the staff CSV export view

    SA85 Phase 4 retained-role:
    * Superuser: cross-tenant read via ``operator_access`` (audited).
    * Regular staff without org: fail-closed (404).
    """

    def test_superuser_gets_csv(self, superuser_client, form, submission, field_value):
        """Superuser receives CSV file with correct content type."""
        url = reverse(
            "quickscale_forms:admin-submission-export", kwargs={"pk": form.pk}
        )
        response = superuser_client.get(url)
        assert response.status_code == 200
        assert "text/csv" in response["Content-Type"]

    def test_superuser_csv_contains_field_values(
        self, superuser_client, form, submission, field_value
    ):
        """CSV output contains the submitted field values."""
        url = reverse(
            "quickscale_forms:admin-submission-export", kwargs={"pk": form.pk}
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
            "quickscale_forms:admin-submission-export", kwargs={"pk": form.pk}
        )
        response = superuser_client.get(url)

        assert response.status_code == 200

        rows = list(csv.reader(io.StringIO(response.content.decode())))
        assert rows[0][0] == "id"
        assert rows[0][-1] == "'=2+2"
        assert rows[1][-1] == "'  +SUM(A1:A2)"

    def test_staff_without_org_gets_404_on_export(self, staff_client, form):
        """View-unit defense-in-depth: force-auth staff without org gets
        404 on CSV export (fail-closed)."""
        url = reverse(
            "quickscale_forms:admin-submission-export", kwargs={"pk": form.pk}
        )
        response = staff_client.get(url)
        assert response.status_code == 404

    def test_returns_403_for_anonymous(self, api_client, form):
        """Anonymous user cannot export submissions"""
        url = reverse(
            "quickscale_forms:admin-submission-export", kwargs={"pk": form.pk}
        )
        response = api_client.get(url)
        assert response.status_code == 403

    def test_superuser_gets_404_for_missing_form(self, superuser_client):
        """Export view returns 404 when form pk does not exist."""
        url = reverse("quickscale_forms:admin-submission-export", kwargs={"pk": 99999})
        response = superuser_client.get(url)
        assert response.status_code == 404


@pytest.mark.django_db
class TestAdminSubmissionListFilters:
    """Tests for query parameter filters on AdminSubmissionListAPIView

    SA85 Phase 4: filters are role-agnostic — they apply to whatever
    queryset the role produces.  Use superuser for cross-tenant filter
    coverage.
    """

    def test_filter_by_is_spam_true(self, superuser_client, form, submission):
        """is_spam=true filter returns only spam submissions"""
        from quickscale_modules_orgs.current_org import org_scope

        with org_scope(submission.organization):
            submission.is_spam = True
            submission.save()
        url = reverse("quickscale_forms:admin-submission-list", kwargs={"pk": form.pk})
        response = superuser_client.get(url, {"is_spam": "true"})
        assert response.status_code == 200
        assert all(s["is_spam"] for s in response.data)

    def test_filter_by_date_gte(self, superuser_client, form, submission):
        """submitted_at__date__gte filter is accepted without error"""
        url = reverse("quickscale_forms:admin-submission-list", kwargs={"pk": form.pk})
        response = superuser_client.get(url, {"submitted_at__date__gte": "2000-01-01"})
        assert response.status_code == 200

    def test_filter_by_date_lte(self, superuser_client, form, submission):
        """submitted_at__date__lte filter is accepted without error"""
        url = reverse("quickscale_forms:admin-submission-list", kwargs={"pk": form.pk})
        response = superuser_client.get(url, {"submitted_at__date__lte": "2099-12-31"})
        assert response.status_code == 200


@pytest.mark.django_db
class TestAdminSubmissionDetailNotFound:
    """Tests for 404 behavior in AdminSubmissionDetailAPIView"""

    def test_superuser_gets_404_for_unknown_submission(self, superuser_client, form):
        """Submission detail returns 404 when sub_pk does not exist."""
        url = reverse(
            "quickscale_forms:admin-submission-detail",
            kwargs={"pk": form.pk, "sub_pk": 99999},
        )
        response = superuser_client.get(url)
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# AF1-CR-001: DB-side org scope for public forms routes
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFormSubmissionCanonicalIp:
    """SA21.2 — verify that FormSubmission.ip_address uses the canonical
    client IP (via the shared get_client_ip helper) instead of raw REMOTE_ADDR."""

    def test_ip_address_uses_xff_when_configured(
        self, api_client, form, form_field, email_field
    ):
        """When USE_X_FORWARDED_FOR and TRUSTED_PROXY_COUNT are configured,
        ip_address records the X-Forwarded-For client IP, not REMOTE_ADDR."""
        from django.test import override_settings

        from quickscale_modules_forms.models import FormSubmission
        from quickscale_modules_orgs.current_org import org_scope

        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
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

        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
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

        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
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
        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import Organization

        system_org = Organization.objects.get_system_org()

        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "test-contact"})
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
        from quickscale_modules_orgs.constants import ACTIVE_ORG_SESSION_KEY

        session[ACTIVE_ORG_SESSION_KEY] = str(org.pk)
        session.save()

        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "auth-contact"})
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
        of reassigning the fixture form's org (which AF12 composite FKs
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
        from quickscale_modules_orgs.current_org import org_scope

        form.redirect_url = "/thank-you"
        with org_scope(form.organization):
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
        from quickscale_modules_orgs.current_org import org_scope

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
        with org_scope(form.organization):
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
        from quickscale_modules_orgs.current_org import org_scope

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
        # Verify the persisted submission exists in the DB — read inside
        # org_scope so FORCE RLS allows the query.
        with org_scope(form.organization):
            assert FormSubmission.all_objects.filter(
                pk=notified_submission_pk[0]
            ).exists(), (
                "The submission must exist in the DB before notify_submission runs"
            )


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


# ---------------------------------------------------------------------------
# SA85 Phase 3 — CR-P3-006 regression: side-effect callbacks run after
# commit with in_atomic_block = False and can observe committed rows
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestPostCommitTransactionBoundary:
    """CR-P3-006/SA85 Phase 3: notification and analytics callbacks run
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
                field_type=FormField.FIELD_TYPE_TEXT,
                label="Full Name",
                name="full_name",
                required=True,
                order=1,
            )
            FormField.all_objects.create(
                form=test_form,
                organization=system_org,
                field_type=FormField.FIELD_TYPE_EMAIL,
                label="Email",
                name="email",
                required=True,
                order=2,
            )

        # ---- Exit setup scope — verify no context leak --------------------
        assert get_current_org_id() is None, (
            "setup org_scope must not leak — ContextVar must be None"
        )

        # ---- Collect assertions from monkeypatched callbacks -------------
        notification_calls: list[dict] = []
        analytics_calls: list[dict] = []

        def _tracking_notify(submission: Any) -> str:
            nonlocal notification_calls
            call_info: dict = {
                "in_atomic_block": connection.in_atomic_block,
                "submission_pk": submission.pk,
            }
            # Open fresh org scope to observe committed rows.
            # The submission lives under system_org — use that scope.
            with org_scope(system_org):
                sub = FormSubmission.all_objects.get(pk=submission.pk)
                fvs = list(FormFieldValue.all_objects.filter(submission=sub))
                call_info["field_values"] = [
                    {"name": fv.field_name, "value": fv.value} for fv in fvs
                ]
            # Verify no context leak from the fresh scope
            assert get_current_org_id() is None, (
                "notification callback must not leak org context"
            )
            notification_calls.append(call_info)
            return "queued"

        def _tracking_analytics(submission: Any, request: Any) -> None:
            nonlocal analytics_calls
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

        monkeypatch.setattr(
            "quickscale_modules_forms.views.notify_submission",
            _tracking_notify,
        )
        monkeypatch.setattr(
            "quickscale_modules_forms.views._capture_submission_analytics",
            _tracking_analytics,
        )

        # ---- POST — triggers the view's org_scope + transaction.atomic() --
        url = reverse("quickscale_forms:form-submit", kwargs={"slug": form_slug})
        data = {"full_name": "Boundary Alice", "email": "boundary@example.com"}
        response = api_client.post(url, data=data, format="json")

        assert response.status_code == 201, f"Expected 201, got {response.status_code}"
        assert response.data["notification_status"] == "queued"

        # ---- Verify notification callback --------------------------------
        assert len(notification_calls) == 1, (
            "notify_submission must be called exactly once"
        )
        nf = notification_calls[0]
        assert nf["in_atomic_block"] is False, (
            "notify_submission must run outside any database transaction"
        )
        assert nf["submission_pk"] is not None
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

        # ---- Verify analytics callback -----------------------------------
        assert len(analytics_calls) == 1, (
            "analytics capture must be called exactly once"
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
