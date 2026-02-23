"""Tests for Forms module management commands"""

import pytest
from django.core.management import call_command
from django.utils import timezone

from quickscale_modules_forms.models import Form, FormField, FormSubmission


@pytest.mark.django_db
class TestFormsSeedPresets:
    """Tests for the forms_seed_presets management command"""

    def test_seed_presets_creates_four_forms(self):
        """Command creates all four preset forms"""
        call_command("forms_seed_presets", verbosity=0)
        slugs = list(Form.objects.values_list("slug", flat=True))
        assert "contact" in slugs
        assert "newsletter" in slugs
        assert "feedback" in slugs
        assert "support" in slugs

    def test_contact_preset_has_correct_fields(self):
        """Contact preset has the five standard fields"""
        call_command("forms_seed_presets", verbosity=0)
        form = Form.objects.get(slug="contact")
        field_names = list(form.fields.values_list("name", flat=True))
        assert "full_name" in field_names
        assert "email" in field_names
        assert "company" in field_names
        assert "subject" in field_names
        assert "project_context" in field_names

    def test_newsletter_preset_has_two_fields(self):
        """Newsletter preset has exactly two fields"""
        call_command("forms_seed_presets", verbosity=0)
        form = Form.objects.get(slug="newsletter")
        assert form.fields.count() == 2

    def test_seed_presets_is_idempotent(self):
        """Running the command twice does not create duplicate forms"""
        call_command("forms_seed_presets", verbosity=0)
        call_command("forms_seed_presets", verbosity=0)
        assert Form.objects.filter(slug="contact").count() == 1

    def test_feedback_preset_has_select_field(self):
        """Feedback preset includes a select (rating) field"""
        call_command("forms_seed_presets", verbosity=0)
        form = Form.objects.get(slug="feedback")
        assert form.fields.filter(field_type=FormField.FIELD_TYPE_SELECT).exists()

    def test_support_preset_has_priority_select(self):
        """Support preset has a priority select field with three options"""
        call_command("forms_seed_presets", verbosity=0)
        priority_field = FormField.objects.get(form__slug="support", name="priority")
        assert priority_field.field_type == FormField.FIELD_TYPE_SELECT
        assert len(priority_field.options) == 3


@pytest.mark.django_db
class TestFormsAnonymizeSubmissions:
    """Tests for the forms_anonymize_submissions management command"""

    def test_anonymize_does_not_touch_recent_submissions(self, form):
        """Submissions newer than data_retention_days are not anonymized"""
        sub = FormSubmission.objects.create(
            form=form,
            ip_address="192.168.1.1",
        )
        call_command("forms_anonymize_submissions", verbosity=0)
        sub.refresh_from_db()
        assert sub.ip_address == "192.168.1.1"

    def test_anonymize_clears_ip_of_old_submissions(self, form):
        """Submissions older than data_retention_days have ip_address set to None"""
        from datetime import timedelta

        sub = FormSubmission.objects.create(
            form=form,
            ip_address="10.0.0.1",
            user_agent="OldBrowser/1.0",
        )
        # Force submitted_at to be past the retention window
        cutoff = timezone.now() - timedelta(days=form.data_retention_days + 1)
        FormSubmission.objects.filter(pk=sub.pk).update(submitted_at=cutoff)

        call_command("forms_anonymize_submissions", verbosity=0)
        sub.refresh_from_db()
        assert sub.ip_address is None
        assert sub.user_agent == ""

    def test_anonymize_skips_forms_with_zero_retention_days(self):
        """Forms with data_retention_days=0 (keep forever) are skipped"""
        form = Form.objects.create(
            title="Zero Retention",
            slug="zero-retention",
            data_retention_days=0,
        )
        sub = FormSubmission.objects.create(
            form=form,
            ip_address="1.2.3.4",
        )
        # Force the submission to be very old
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(days=9999)
        FormSubmission.objects.filter(pk=sub.pk).update(submitted_at=cutoff)
        call_command("forms_anonymize_submissions", verbosity=0)
        sub.refresh_from_db()
        # ip_address must NOT be nulled because retention_days=0 means keep forever
        assert sub.ip_address == "1.2.3.4"

    def test_anonymize_skips_already_anonymized_submissions(self, form):
        """Submissions already anonymized (ip=None) are not double-processed"""
        from datetime import timedelta

        sub = FormSubmission.objects.create(form=form, ip_address=None)
        cutoff = timezone.now() - timedelta(days=form.data_retention_days + 1)
        FormSubmission.objects.filter(pk=sub.pk).update(submitted_at=cutoff)
        # Should not raise
        call_command("forms_anonymize_submissions", verbosity=0)
        sub.refresh_from_db()
        assert sub.ip_address is None
