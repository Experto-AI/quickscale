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
        submission.form.notify_emails = "a@example.com, b@example.com"
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
        form.notify_emails = ""
        form.save()
        notify_submission(submission)
        assert len(mail.outbox) == 0

    def test_spam_submission_does_not_send_email(self, submission):
        """Spam submissions are silently ignored — no email sent"""
        submission.is_spam = True
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
        # Create a submission with only a non-name field
        sub = FormSubmission.all_objects.create(
            form=form,
            organization=form.organization,
            ip_address="127.0.0.1",
        )
        from quickscale_modules_forms.models import FormField, FormFieldValue

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
        with org_scope(org):
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

        with org_scope(org):
            notify_submission(sub)

        assert len(mail.outbox) == 1
        # Subject should include "from Alice Tenant" — this proves the
        # submitter_name resolution via FK traversal works within org_scope.
        assert "from Alice Tenant" in mail.outbox[0].subject, (
            "Subject must include the submitter name resolved from child"
            " field values inside org_scope"
        )
