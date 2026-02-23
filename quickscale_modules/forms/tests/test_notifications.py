"""Tests for Forms module email notification helper"""

import pytest
from django.core import mail

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
        sub = FormSubmission.objects.create(
            form=form,
            ip_address="127.0.0.1",
        )
        from quickscale_modules_forms.models import FormField, FormFieldValue

        # A message field (no 'name' in its label)
        field = FormField.objects.create(
            form=form,
            field_type=FormField.FIELD_TYPE_TEXTAREA,
            label="Message",
            name="message",
            order=10,
        )
        FormFieldValue.objects.create(
            submission=sub,
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
