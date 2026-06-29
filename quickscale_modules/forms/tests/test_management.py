"""Tests for Forms module management commands"""

import logging
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from quickscale_modules_forms.models import Form, FormField, FormSubmission
from quickscale_modules_orgs.models import Organization, OrganizationTombstone


@pytest.mark.django_db
class TestFormsSeedPresets:
    """Tests for the forms_seed_presets management command"""

    def test_seed_presets_creates_four_forms(self):
        """Command creates all four preset forms"""
        call_command("forms_seed_presets", verbosity=0)
        slugs = list(Form.all_objects.values_list("slug", flat=True))
        assert "contact" in slugs
        assert "newsletter" in slugs
        assert "feedback" in slugs
        assert "support" in slugs

    def test_contact_preset_has_correct_fields(self):
        """Contact preset has the five standard fields"""
        from quickscale_modules_orgs.current_org import set_current_org_id

        call_command("forms_seed_presets", verbosity=0)
        form = Form.all_objects.get(slug="contact")
        # Set the org context so that scoped form.fields works.
        set_current_org_id(form.organization_id)
        field_names = list(form.fields.values_list("name", flat=True))
        assert "full_name" in field_names
        assert "email" in field_names
        assert "company" in field_names
        assert "subject" in field_names
        assert "project_context" in field_names

    def test_newsletter_preset_has_two_fields(self):
        """Newsletter preset has exactly two fields"""
        from quickscale_modules_orgs.current_org import set_current_org_id

        call_command("forms_seed_presets", verbosity=0)
        form = Form.all_objects.get(slug="newsletter")
        # Set the org context so that scoped form.fields works.
        set_current_org_id(form.organization_id)
        assert form.fields.count() == 2

    def test_seed_presets_is_idempotent(self):
        """Running the command twice does not create duplicate forms"""
        call_command("forms_seed_presets", verbosity=0)
        call_command("forms_seed_presets", verbosity=0)
        assert Form.all_objects.filter(slug="contact").count() == 1

    @override_settings(FORMS_DATA_RETENTION_DAYS=730)
    def test_seed_presets_use_settings_backed_data_retention_default(self):
        """Preset-created forms should inherit the configured retention default."""
        Form.all_objects.all().delete()

        call_command("forms_seed_presets", verbosity=0)

        assert set(Form.all_objects.values_list("data_retention_days", flat=True)) == {
            730
        }

    @override_settings(FORMS_DATA_RETENTION_DAYS=730)
    def test_seed_presets_preserve_existing_form_data_retention_days(self):
        """Existing forms should keep their stored retention days when presets rerun."""
        call_command("forms_seed_presets", verbosity=0)
        form = Form.all_objects.get(slug="contact")
        form.data_retention_days = 14
        form.save(update_fields=["data_retention_days"])

        call_command("forms_seed_presets", verbosity=0)

        assert Form.all_objects.get(slug="contact").data_retention_days == 14

    def test_feedback_preset_has_select_field(self):
        """Feedback preset has a select field named 'rating'"""
        from quickscale_modules_orgs.current_org import set_current_org_id

        call_command("forms_seed_presets", verbosity=0)
        form = Form.all_objects.get(slug="feedback")
        # Set the org context so that scoped form.fields works.
        set_current_org_id(form.organization_id)
        assert form.fields.filter(field_type=FormField.FIELD_TYPE_SELECT).exists()

    def test_support_preset_has_priority_select(self):
        """Support preset has a priority select field with three options"""
        call_command("forms_seed_presets", verbosity=0)
        priority_field = FormField.all_objects.get(
            form__slug="support", name="priority"
        )
        assert priority_field.field_type == FormField.FIELD_TYPE_SELECT
        assert len(priority_field.options) == 3

    def test_seed_scoped_to_system_org_under_per_org_slug_uniqueness(self):
        """Seed command must not reuse tenant-owned rows with the same slug.

        CR-T17-002: With per-org slug uniqueness, a tenant may have a form
        with the same slug as a preset. The seed command must scope its
        lookup to the System org and create the preset there.
        """
        from quickscale_modules_orgs.models import Organization

        system_org = Organization.objects.get_system_org()
        tenant_org = Organization.objects.create(
            name="Tenant", slug="tenant-org", is_personal=False
        )

        # Tenant creates a form with slug="contact" (conflicts with preset).
        tenant_form = Form.objects.create(
            title="Tenant Contact",
            slug="contact",
            organization=tenant_org,
        )

        # Run seed — should NOT reuse the tenant row.
        call_command("forms_seed_presets", verbosity=0)

        # The System org should now have a "contact" preset.
        system_contact = Form.all_objects.get(slug="contact", organization=system_org)
        assert system_contact.title == "Contact"
        assert system_contact.pk != tenant_form.pk

        # The tenant's form must remain unchanged.
        tenant_form.refresh_from_db()
        assert tenant_form.title == "Tenant Contact"

    def test_seed_idempotent_with_conflicting_tenant_slug(self):
        """Seed must stay idempotent after a tenant-owned same-slug row exists."""
        from quickscale_modules_orgs.models import Organization

        system_org = Organization.objects.get_system_org()
        tenant_org = Organization.objects.create(
            name="Tenant", slug="tenant-org-2", is_personal=False
        )

        Form.objects.create(
            title="Tenant Contact",
            slug="contact",
            organization=tenant_org,
        )

        # Run seed twice.
        call_command("forms_seed_presets", verbosity=0)
        call_command("forms_seed_presets", verbosity=0)

        # System-org presets must exist exactly once.
        assert (
            Form.all_objects.filter(slug="contact", organization=system_org).count()
            == 1
        )
        # Tenant's form still exists independently.
        assert (
            Form.all_objects.filter(slug="contact", organization=tenant_org).count()
            == 1
        )


@pytest.mark.django_db
class TestFormsAnonymizeSubmissions:
    """Tests for the forms_anonymize_submissions management command"""

    def test_anonymize_does_not_touch_recent_submissions(self, form):
        """Submissions newer than data_retention_days are not anonymized"""
        sub = FormSubmission.all_objects.create(
            form=form,
            organization=form.organization,
            ip_address="192.168.1.1",
        )
        call_command("forms_anonymize_submissions", verbosity=0)
        sub.refresh_from_db()
        assert sub.ip_address == "192.168.1.1"

    def test_anonymize_clears_ip_of_old_submissions(self, form):
        """Submissions older than data_retention_days have ip_address set to None"""
        from datetime import timedelta

        sub = FormSubmission.all_objects.create(
            form=form,
            organization=form.organization,
            ip_address="10.0.0.1",
            user_agent="OldBrowser/1.0",
        )
        # Force submitted_at to be past the retention window
        cutoff = timezone.now() - timedelta(days=form.data_retention_days + 1)
        FormSubmission.all_objects.filter(pk=sub.pk).update(submitted_at=cutoff)

        call_command("forms_anonymize_submissions", verbosity=0)
        sub.refresh_from_db()
        assert sub.ip_address is None
        assert sub.user_agent == ""

    def test_anonymize_skips_forms_with_zero_retention_days(self):
        """Forms with data_retention_days=0 (keep forever) are skipped"""
        from quickscale_modules_orgs.models import Organization

        system_org = Organization.objects.get_system_org()
        form = Form.objects.create(
            title="Zero Retention",
            slug="zero-retention",
            data_retention_days=0,
            organization=system_org,
        )
        sub = FormSubmission.all_objects.create(
            form=form,
            organization=form.organization,
            ip_address="1.2.3.4",
        )
        # Force the submission to be very old
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(days=9999)
        FormSubmission.all_objects.filter(pk=sub.pk).update(submitted_at=cutoff)
        call_command("forms_anonymize_submissions", verbosity=0)
        sub.refresh_from_db()
        # ip_address must NOT be nulled because retention_days=0 means keep forever
        assert sub.ip_address == "1.2.3.4"

    def test_anonymize_skips_already_anonymized_submissions(self, form):
        """Submissions already anonymized (ip=None) are not double-processed"""
        from datetime import timedelta

        sub = FormSubmission.all_objects.create(
            form=form, organization=form.organization, ip_address=None
        )
        cutoff = timezone.now() - timedelta(days=form.data_retention_days + 1)
        FormSubmission.all_objects.filter(pk=sub.pk).update(submitted_at=cutoff)
        # Should not raise
        call_command("forms_anonymize_submissions", verbosity=0)
        sub.refresh_from_db()
        assert sub.ip_address is None


@pytest.mark.django_db
class TestFormsAnonymizeSubmissionsOperatorPath:
    """AF3: verify management command iterates via org-scoped operator seam."""

    def test_command_iterates_all_forms_including_system_org(self):
        """Command visits all forms via org-scoped iteration including System-org."""
        from datetime import timedelta

        system_org = Organization.objects.get_system_org()

        form = Form.objects.create(
            title="System Org Form",
            slug="system-org-form",
            data_retention_days=30,
            organization=system_org,
        )
        sub = FormSubmission.all_objects.create(
            form=form,
            organization=form.organization,
            ip_address="10.0.0.1",
            user_agent="OldBrowser/1.0",
        )
        cutoff = timezone.now() - timedelta(days=31)
        FormSubmission.all_objects.filter(pk=sub.pk).update(submitted_at=cutoff)

        call_command("forms_anonymize_submissions", verbosity=0)
        sub.refresh_from_db()
        assert sub.ip_address is None
        assert sub.user_agent == ""

    def test_command_iterates_via_organization_iteration(self):
        """Command iterates Organization.objects (org-scoped), not all_objects."""
        with patch.object(Organization.objects, "iterator") as mock_iter:
            mock_iter.return_value = Organization.objects.none()
            call_command("forms_anonymize_submissions", verbosity=0)
            mock_iter.assert_called_once()

    def test_command_operator_access_success(self, caplog):
        """Command produces a succeeded operator_access audit log."""
        caplog.set_level(logging.INFO)

        system_org = Organization.objects.get_system_org()

        Form.objects.create(
            title="Audit Anonymize Form",
            slug="audit-anonymize",
            data_retention_days=30,
            organization=system_org,
        )

        call_command("forms_anonymize_submissions", verbosity=0)

        msgs = [r.getMessage() for r in caplog.records]
        matching = [
            m
            for m in msgs
            if "operator_access:" in m and "command=forms_anonymize_submissions" in m
        ]
        assert len(matching) >= 1, f"No audit log found in: {msgs}"
        msg = matching[-1]
        assert "status=succeeded" in msg
        assert "scope=all_orgs" in msg
        assert "error_class=" in msg

    def test_command_operator_access_failure(self, caplog):
        """When anonymize body raises, audit log must have status='failed',
        error_class, and the pre-populated target_org_ids."""
        caplog.set_level(logging.INFO)

        system_org = Organization.objects.get_system_org()

        Form.objects.create(
            title="Fail Anonymize Form",
            slug="fail-anonymize",
            data_retention_days=30,
            organization=system_org,
        )

        # Patch Organization.objects.iterator to raise mid-way.
        original_iterator = Organization.objects.iterator

        def failing_iterator():
            yield from original_iterator()
            raise RuntimeError("Simulated anonymize failure")

        with patch.object(
            Organization.objects, "iterator", side_effect=failing_iterator
        ):
            with pytest.raises(RuntimeError, match="Simulated anonymize failure"):
                call_command("forms_anonymize_submissions", verbosity=0)

        msgs = [r.getMessage() for r in caplog.records]
        matching = [
            m
            for m in msgs
            if "operator_access:" in m and "command=forms_anonymize_submissions" in m
        ]
        assert len(matching) >= 1, f"No audit log found in: {msgs}"
        msg = matching[-1]
        assert "status=failed" in msg
        assert "error_class=RuntimeError" in msg
        # target_org_ids is pre-populated before iteration so must appear
        # even on failure.  touched_org_ids may be partial or empty.
        assert "target_orgs=" in msg
        assert str(system_org.pk) in msg


# ---------------------------------------------------------------------------
# AF3 — forms_seed_presets operator-access seam tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFormsSeedPresetsOperatorSeam:
    """AF3: forms_seed_presets must produce an operator_access audit log."""

    def test_seed_presets_operator_access_success(self, caplog):
        """forms_seed_presets produces a succeeded audit log."""
        caplog.set_level(logging.INFO)

        call_command("forms_seed_presets", verbosity=0)

        msgs = [r.getMessage() for r in caplog.records]
        matching = [
            m
            for m in msgs
            if "operator_access:" in m and "command=forms_seed_presets" in m
        ]
        assert len(matching) >= 1, f"No audit log found in: {msgs}"
        msg = matching[-1]
        assert "status=succeeded" in msg
        assert "scope=system_org" in msg
        assert "error_class=" in msg

    def test_seed_presets_operator_access_target_org(self, caplog):
        """forms_seed_presets must log the System org in target_orgs and touched_orgs."""
        caplog.set_level(logging.INFO)

        system_org = Organization.objects.get_system_org()

        call_command("forms_seed_presets", verbosity=0)

        msgs = [r.getMessage() for r in caplog.records]
        matching = [
            m
            for m in msgs
            if "operator_access:" in m and "command=forms_seed_presets" in m
        ]
        assert len(matching) >= 1
        msg = matching[-1]
        assert str(system_org.pk) in msg
        # Both target_orgs and touched_orgs should contain the system org pk.
        assert "target_orgs" in msg
        assert "touched_orgs" in msg

    def test_seed_presets_operator_access_failure(self, caplog):
        """When seed body raises, audit log must have status='failed',
        error_class, and target/touched org IDs (set before the risky work)."""
        caplog.set_level(logging.INFO)

        system_org = Organization.objects.get_system_org()

        # Patch Form.objects.get_or_create to raise midway — the core
        # audit fields (including target_org_ids/touched_org_ids) are set
        # before get_or_create is called.
        with patch.object(
            Form.objects,
            "get_or_create",
            side_effect=RuntimeError("Simulated seed failure"),
        ):
            with pytest.raises(RuntimeError, match="Simulated seed failure"):
                call_command("forms_seed_presets", verbosity=0)

        msgs = [r.getMessage() for r in caplog.records]
        matching = [
            m
            for m in msgs
            if "operator_access:" in m and "command=forms_seed_presets" in m
        ]
        assert len(matching) >= 1, f"No audit log found in: {msgs}"
        msg = matching[-1]
        assert "status=failed" in msg
        assert "error_class=RuntimeError" in msg
        # Extract exact field-delimited values so that extra IDs or suffixes
        # after the expected value cause a failure.
        target_orgs_value = msg.split("target_orgs=")[1].split(" ")[0]
        assert target_orgs_value == str(system_org.pk), (
            f"Expected target_orgs={system_org.pk}, "
            f"got target_orgs={target_orgs_value!r} in: {msg}"
        )
        touched_orgs_value = msg.split("touched_orgs=")[1].split(" ")[0]
        assert touched_orgs_value == str(system_org.pk), (
            f"Expected touched_orgs={system_org.pk}, "
            f"got touched_orgs={touched_orgs_value!r} in: {msg}"
        )

    def test_seed_presets_operator_access_early_failure(self, caplog):
        """When get_system_org fails, command actor/scope are still logged,
        and target_orgs/touched_orgs show the expected empty-field shape."""
        caplog.set_level(logging.INFO)

        with patch.object(
            Organization.objects,
            "get_system_org",
            side_effect=RuntimeError("Seed early failure"),
        ):
            with pytest.raises(RuntimeError, match="Seed early failure"):
                call_command("forms_seed_presets", verbosity=0)

        msgs = [r.getMessage() for r in caplog.records]
        matching = [
            m
            for m in msgs
            if "operator_access:" in m and "command=forms_seed_presets" in m
        ]
        assert len(matching) >= 1, f"No audit log found in: {msgs}"
        msg = matching[-1]
        assert "status=failed" in msg
        assert "error_class=RuntimeError" in msg
        # Static audit fields set before get_system_org must appear.
        assert "command=forms_seed_presets" in msg
        assert "scope=system_org" in msg
        assert "actor=cli:forms_seed_presets" in msg
        # target_org_ids/touched_org_ids depend on get_system_org result
        # and will be empty defaults — show the exact empty-field shape.
        assert "target_orgs= touched_orgs=" in msg, (
            f"Expected empty target_orgs/touched_orgs in: {msg}"
        )


# ---------------------------------------------------------------------------
# T1.17 — purge_organization integration test for forms delete branch
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPurgeOrganization:
    """purge_organization must delete form rows owned by the purged org."""

    def test_purge_deletes_org_forms(self):
        """Form and FormSubmission rows are deleted by purge_organization."""
        from io import StringIO

        org = Organization.objects.create(name="Purgeable Org", slug="purgeable")
        Form.objects.create(organization=org, title="Purge Me", slug="purge-me")
        org_id = org.pk

        call_command(
            "purge_organization",
            organization_id=str(org_id),
            stdout=StringIO(),
            stderr=StringIO(),
            verbosity=0,
        )

        assert not Organization.objects.filter(pk=org_id).exists()
        assert Form.all_objects.filter(organization_id=org_id).count() == 0
        assert OrganizationTombstone.objects.filter(organization_id=org_id).exists()
