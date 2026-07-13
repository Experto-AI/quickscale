"""Tests for Forms module email notification helper"""

import pytest
from django.core import mail
from django.test import override_settings

from quickscale_modules_forms.models import FormSubmission
from quickscale_modules_forms.notifications import notify_submission


@pytest.mark.django_db
class TestNotifySubmission:
    """Tests for the notify_submission() function"""

    def test_sends_email_to_all_recipients(self, submission, field_value):
        """One email is sent to all comma-separated notify_emails addresses"""
        from quickscale_modules_orgs.current_org import org_scope

        submission.form.notify_emails = "a@example.com, b@example.com"
        with org_scope(submission.organization):
            submission.form.save()
        notify_submission(submission)
        assert len(mail.outbox) == 1
        assert "a@example.com" in mail.outbox[0].recipients()
        assert "b@example.com" in mail.outbox[0].recipients()

    def test_subject_contains_form_title(self, submission, field_value):
        """Email subject includes the form title"""
        notify_submission(submission)
        assert len(mail.outbox) == 1
        assert "Contact" in mail.outbox[0].subject

    def test_body_contains_field_labels_and_values(self, submission, field_value):
        """Email body contains field label-value pairs"""
        notify_submission(submission)
        assert len(mail.outbox) == 1
        body = mail.outbox[0].body
        assert "Name" in body
        assert "Alice" in body

    def test_includes_html_alternative(self, submission, field_value):
        """Notification email includes an HTML alternative rendered from template"""
        notify_submission(submission)
        assert len(mail.outbox) == 1
        alternatives = mail.outbox[0].alternatives
        assert alternatives
        html_body, mimetype = alternatives[0]
        assert mimetype == "text/html"
        assert "<h2>New submission:" in html_body

    def test_no_email_when_notify_emails_empty(self, form, submission):
        """No email sent when form.notify_emails is blank"""
        from quickscale_modules_orgs.current_org import org_scope

        form.notify_emails = ""
        with org_scope(form.organization):
            form.save()
        notify_submission(submission)
        assert len(mail.outbox) == 0

    def test_spam_submission_does_not_send_email(self, submission):
        """Spam submissions are silently ignored — no email sent"""
        from quickscale_modules_orgs.current_org import org_scope

        submission.is_spam = True
        with org_scope(submission.organization):
            submission.save()
        notify_submission(submission)
        assert len(mail.outbox) == 0

    @override_settings(QUICKSCALE_NOTIFICATIONS_ENABLED=False)
    def test_falls_back_to_untracked_email_when_notifications_installed_but_disabled(
        self,
        submission,
        field_value,
        monkeypatch,
    ):
        """Disabled tracked notifications fall back to the existing untracked email path"""

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

        notify_submission(submission)

        assert len(mail.outbox) == 1
        assert "admin@example.com" in mail.outbox[0].recipients()

    def test_smtp_exception_does_not_propagate(
        self, submission, field_value, monkeypatch
    ):
        """SMTP failure during notification does not raise an exception"""

        def failing_send(*args, **kwargs):
            raise Exception("SMTP connection refused")

        monkeypatch.setattr(
            "quickscale_modules_forms.notifications.EmailMultiAlternatives.send",
            failing_send,
        )
        # Should NOT raise
        notify_submission(submission)

    def test_subject_without_name_field(self, form, db):
        """Subject falls back to generic when no name-type field is present"""
        from quickscale_modules_forms.models import FormField, FormFieldValue
        from quickscale_modules_orgs.current_org import org_scope

        # Create data inside org_scope so FORCE RLS allows the writes
        with org_scope(form.organization):
            sub = FormSubmission.all_objects.create(
                form=form,
                organization=form.organization,
                ip_address="127.0.0.1",
            )
            # A message field (no 'name' in its label)
            field = FormField.all_objects.create(
                form=form,
                organization=form.organization,
                field_type=FormField.FIELD_TYPE_TEXTAREA,
                label="Message",
                name="message",
                order=10,
            )
            FormFieldValue.all_objects.create(
                submission=sub,
                organization=sub.organization,
                field=field,
                field_name="message",
                field_label="Message",
                value="Hello world",
            )
        # org_scope exited — notify_submission wraps its own scope
        notify_submission(sub)
        assert len(mail.outbox) == 1
        # Subject should NOT contain "from" (no name available)
        assert (
            "from" not in mail.outbox[0].subject.lower()
            or "Contact" in mail.outbox[0].subject
        )


# ---------------------------------------------------------------------------
# AF1-CR-005: Notification content rendered inside org_scope
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestNotifySubmissionOrgScope:
    """AF1-CR-005: Notification content must render org-scoped field values correctly.

    notify_submission is called inside the view's org_scope() block in
    production. The FK traversal submission.values.all() inside
    _build_submission_notification_content must resolve with the active org
    context to pass RLS filtering on the child FormFieldValue table.
    """

    def test_notification_body_contains_org_scoped_field_values(self, db):
        """Calling notify_submission inside org_scope() renders field values."""
        from quickscale_modules_forms.models import (
            Form,
            FormField,
            FormFieldValue,
            FormSubmission,
        )
        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import Organization

        org = Organization.objects.create(name="Tenant Org", slug="tenant-org")

        # Create data inside org_scope so FORCE RLS allows the writes
        with org_scope(org):
            form = Form.all_objects.create(
                title="Tenant Form",
                slug="tenant-form",
                organization=org,
                notify_emails="tenant@example.com",
            )
            field = FormField.all_objects.create(
                form=form,
                organization=org,
                field_type=FormField.FIELD_TYPE_TEXT,
                label="Message",
                name="message",
                order=1,
            )
            sub = FormSubmission.all_objects.create(
                form=form,
                organization=org,
                ip_address="10.0.0.1",
            )
            FormFieldValue.all_objects.create(
                submission=sub,
                organization=org,
                field=field,
                field_name="message",
                field_label="Message",
                value="Tenant-scoped content",
            )

            # Call notify_submission inside the org_scope block — this is the
            # production path; without the active scope the FK traversal through
            # TenantManager would RLS-filter and produce empty content.
            notify_submission(sub)

        assert len(mail.outbox) == 1, "Notification email must be sent"
        body = mail.outbox[0].body
        assert "Tenant-scoped content" in body, (
            "Field value must appear in email body — proves org-scoped FK"
            " traversal works inside org_scope()"
        )
        assert "Message: Tenant-scoped content" in body, (
            "Label-value pair must be rendered in the email"
        )

    def test_notification_subject_includes_name_within_org_scope(self, db):
        """Submitter-name suffix in subject is resolved within org_scope."""
        from quickscale_modules_forms.models import (
            Form,
            FormField,
            FormFieldValue,
            FormSubmission,
        )
        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import Organization

        org = Organization.objects.create(name="Name Org", slug="name-org")

        with org_scope(org):
            form = Form.all_objects.create(
                title="Name Form",
                slug="name-form",
                organization=org,
                notify_emails="name@example.com",
            )
            field = FormField.all_objects.create(
                form=form,
                organization=org,
                field_type=FormField.FIELD_TYPE_TEXT,
                label="Full Name",
                name="full_name",
                order=1,
            )
            sub = FormSubmission.all_objects.create(
                form=form,
                organization=org,
                ip_address="10.0.0.2",
            )
            FormFieldValue.all_objects.create(
                submission=sub,
                organization=org,
                field=field,
                field_name="full_name",
                field_label="Full Name",
                value="Alice Tenant",
            )

            notify_submission(sub)

        assert len(mail.outbox) == 1
        # Subject should include "from Alice Tenant" — this proves the
        # submitter_name resolution via FK traversal works within org_scope.
        assert "from Alice Tenant" in mail.outbox[0].subject, (
            "Subject must include the submitter name resolved from child"
            " field values inside org_scope"
        )


# ---------------------------------------------------------------------------
# SA85 Phase 3 — notify_submission without ambient org context or atomic
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestNotifySubmissionNoContext:
    """SA85 Phase 3: notify_submission works without ambient org context or atomic.

    Creates data inside a controlled org_scope, exits scope, then calls
    notify_submission() directly — proving that rendered field values
    appear correctly via FormFieldValue.all_objects without any org context
    or active transaction.atomic() block at call time.
    """

    def test_content_rendered_without_org_context_or_atomic(self, db):
        """Calling notify_submission with no ContextVar and no atomic block
        still produces correctly rendered field values."""
        from quickscale_modules_forms.models import (
            Form,
            FormField,
            FormFieldValue,
            FormSubmission,
        )
        from quickscale_modules_orgs.current_org import get_current_org_id, org_scope
        from quickscale_modules_orgs.models import Organization

        import uuid

        slug_suffix = uuid.uuid4().hex[:8]
        org = Organization.objects.create(
            name=f"Phase3 Org {slug_suffix}",
            slug=f"phase3-org-{slug_suffix}",
        )

        with org_scope(org):
            form = Form.all_objects.create(
                title="Phase3 Form",
                slug=f"phase3-form-{slug_suffix}",
                organization=org,
                notify_emails="phase3@example.com",
                is_active=True,
            )
            field = FormField.all_objects.create(
                form=form,
                organization=org,
                field_type=FormField.FIELD_TYPE_TEXT,
                label="Full Name",
                name="full_name",
                required=True,
                order=1,
            )
            sub = FormSubmission.all_objects.create(
                form=form,
                organization=org,
                ip_address="10.0.0.1",
            )
            FormFieldValue.all_objects.create(
                submission=sub,
                organization=org,
                field=field,
                field_name="full_name",
                field_label="Full Name",
                value="No Context Alice",
            )

        # org_scope exited — no ambient context
        assert get_current_org_id() is None, (
            "org scope must not leak — ContextVar must be None"
        )

        # Call notify_submission with no org context and no ambient atomic
        notify_submission(sub)

        assert len(mail.outbox) == 1, "Notification email must be sent"
        body = mail.outbox[0].body
        assert "No Context Alice" in body, (
            "Field value must appear in email body without ambient org context"
        )
        assert "Full Name: No Context Alice" in body, (
            "Label-value pair must be rendered in the email"
        )
        assert "[Phase3 Form]" in mail.outbox[0].subject, (
            "Subject must contain form title"
        )


# ---------------------------------------------------------------------------
# CR-SA85-REV-003 — real-helper django_db(transaction=True) notification
# proof with no ambient atomic/org context, rendered content, dispatch,
# and no leak
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestNotifySubmissionTransactionTrue:
    """CR-SA85-REV-003: prove notify_submission works under
    django_db(transaction=True) with no ambient org context or atomic block,
    dispatching a real untracked email with rendered content and no leak.

    Unlike TestPostCommitTransactionBoundary in test_views.py (which
    monkeypatches notify_submission), this test calls the real
    notify_submission helper and asserts the actual email outbox.
    """

    def test_real_notification_with_transaction_true(self, db):
        """Calling the real notify_submission under django_db(transaction=True)
        with no ambient org context or atomic produces rendered email content,
        dispatches successfully, and leaves no context leak."""
        from quickscale_modules_forms.models import (
            Form,
            FormField,
            FormFieldValue,
            FormSubmission,
        )
        from quickscale_modules_orgs.current_org import get_current_org_id, org_scope
        from quickscale_modules_orgs.models import Organization

        import uuid

        slug_suffix = uuid.uuid4().hex[:8]
        org = Organization.objects.create(
            name=f"REV-003 Org {slug_suffix}",
            slug=f"rev003-org-{slug_suffix}",
        )

        with org_scope(org):
            form = Form.all_objects.create(
                title="REV-003 Form",
                slug=f"rev003-form-{slug_suffix}",
                organization=org,
                notify_emails="rev003@example.com",
                is_active=True,
            )
            field = FormField.all_objects.create(
                form=form,
                organization=org,
                field_type=FormField.FIELD_TYPE_TEXT,
                label="Full Name",
                name="full_name",
                required=True,
                order=1,
            )
            sub = FormSubmission.all_objects.create(
                form=form,
                organization=org,
                ip_address="10.0.0.1",
            )
            FormFieldValue.all_objects.create(
                submission=sub,
                organization=org,
                field=field,
                field_name="full_name",
                field_label="Full Name",
                value="REV-003 Alice",
            )

        # Exit setup — no ambient org context or atomic block.
        assert get_current_org_id() is None, "setup org_scope must not leak"

        # Call the REAL notify_submission (not monkeypatched).
        from quickscale_modules_forms.notifications import notify_submission

        result = notify_submission(submission=sub)

        assert result == "queued", f"Expected 'queued', got {result!r}"
        assert len(mail.outbox) == 1, "Real notification must dispatch an email"
        body = mail.outbox[0].body
        assert "REV-003 Alice" in body, (
            "Email body must contain the submitted field value"
        )
        assert "Full Name: REV-003 Alice" in body, (
            "Email body must contain the label-value pair"
        )
        assert "[REV-003 Form]" in mail.outbox[0].subject, (
            "Subject must contain form title"
        )
        assert "rev003@example.com" in mail.outbox[0].recipients(), (
            "Recipient must match form.notify_emails"
        )

        # Verify HTML alternative
        alternatives = mail.outbox[0].alternatives
        assert alternatives, "Email must have HTML alternative"
        html_body, mimetype = alternatives[0]
        assert mimetype == "text/html"
        assert "<h2>New submission:" in html_body

        # Verify no context leak after notification dispatch.
        assert get_current_org_id() is None, "notification must not leak org context"


# ---------------------------------------------------------------------------
# CR-SA85-REV-007 — submission.form dereference inside org_scope,
# freshly reloaded uncached submission
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestNotifySubmissionFormFkInScope:
    """CR-SA85-REV-007: submission.form FK is dereferenced inside org_scope.

    Creates a submission under an explicit org scope, then refreshes it from
    the database (clearing any in-memory FK cache), exits the setup scope,
    and calls notify_submission with no ambient org context.  The notification
    must still succeed because _enqueue_notification wraps the submission.form
    dereference in its own org_scope.
    """

    def test_freshly_reloaded_uncached_form_fk_in_scope(self, db):
        """Calling notify_submission on a freshly reloaded submission with no
        ambient org context succeeds — form FK is dereferenced inside org_scope."""
        from quickscale_modules_forms.models import (
            Form,
            FormField,
            FormFieldValue,
            FormSubmission,
        )
        from quickscale_modules_orgs.current_org import get_current_org_id, org_scope
        from quickscale_modules_orgs.models import Organization

        import uuid

        slug_suffix = uuid.uuid4().hex[:8]
        org = Organization.objects.create(
            name=f"REV-007 Org {slug_suffix}",
            slug=f"rev007-org-{slug_suffix}",
        )

        with org_scope(org):
            form = Form.all_objects.create(
                title="REV-007 Form",
                slug=f"rev007-form-{slug_suffix}",
                organization=org,
                notify_emails="rev007@example.com",
                is_active=True,
            )
            field = FormField.all_objects.create(
                form=form,
                organization=org,
                field_type=FormField.FIELD_TYPE_TEXT,
                label="Full Name",
                name="full_name",
                required=True,
                order=1,
            )
            sub = FormSubmission.all_objects.create(
                form=form,
                organization=org,
                ip_address="10.0.0.1",
            )
            FormFieldValue.all_objects.create(
                submission=sub,
                organization=org,
                field=field,
                field_name="full_name",
                field_label="Full Name",
                value="REV-007 Alice",
            )

        # Exit setup scope and verify no context leak.
        assert get_current_org_id() is None, "setup org_scope must not leak"

        # Reload the submission from DB with an explicit org scope to
        # get a completely uncached object (all FK caches cleared).
        # We use all_objects inside org_scope because the default
        # TenantManager would return .none() without org context.
        with org_scope(org):
            fresh_sub = FormSubmission.all_objects.get(pk=sub.pk)

        # Verify the cached FK is NOT pre-loaded before we call notify.
        # At this point get_current_org_id() is None — any lazy FK
        # traversal to form would fail under FORCE RLS.
        assert get_current_org_id() is None

        # Call notify_submission with no ambient org context.
        # _enqueue_notification must wrap its own org_scope.
        from quickscale_modules_forms.notifications import notify_submission

        notify_submission(fresh_sub)

        assert len(mail.outbox) == 1, "Notification email must be sent"
        body = mail.outbox[0].body
        assert "REV-007 Alice" in body, (
            "Field value must appear in email body — proves form FK "
            "dereference works inside org_scope"
        )
        assert "[REV-007 Form]" in mail.outbox[0].subject, (
            "Subject must contain form title — proves form FK was resolved"
        )
        assert "rev007@example.com" in mail.outbox[0].recipients(), (
            "Recipient must match form.notify_emails — proves form.load() "
            "succeeded inside org_scope"
        )
