"""Tests for Forms module management commands"""

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
        from quickscale_modules_orgs.current_org import operator_access

        call_command("forms_seed_presets", verbosity=0)
        with operator_access(reason="test: verify all four presets created"):
            slugs = list(Form.all_objects.values_list("slug", flat=True))
        assert "contact" in slugs
        assert "newsletter" in slugs
        assert "feedback" in slugs
        assert "support" in slugs

    def test_contact_preset_has_correct_fields(self):
        """Contact preset has the five standard fields"""
        from quickscale_modules_orgs.current_org import (
            operator_access,
            org_scope,
        )

        call_command("forms_seed_presets", verbosity=0)
        with operator_access(reason="test: lookup preset form"):
            form = Form.all_objects.get(slug="contact")
        # Enter org scope so that form.fields (via all_objects base
        # manager) sees the correct app.current_org_id GUC.
        with org_scope(form.organization):
            field_names = list(form.fields.values_list("name", flat=True))
        assert "full_name" in field_names
        assert "email" in field_names
        assert "company" in field_names
        assert "subject" in field_names
        assert "project_context" in field_names

    def test_newsletter_preset_has_two_fields(self):
        """Newsletter preset has exactly two fields"""
        from quickscale_modules_orgs.current_org import (
            operator_access,
            org_scope,
        )

        call_command("forms_seed_presets", verbosity=0)
        with operator_access(reason="test: lookup preset form"):
            form = Form.all_objects.get(slug="newsletter")
        # Enter org scope so that form.fields (via all_objects base
        # manager) sees the correct app.current_org_id GUC.
        with org_scope(form.organization):
            assert form.fields.count() == 2

    def test_seed_presets_is_idempotent(self):
        """Running the command twice does not create duplicate forms"""
        from quickscale_modules_orgs.current_org import operator_access

        call_command("forms_seed_presets", verbosity=0)
        call_command("forms_seed_presets", verbosity=0)
        with operator_access(reason="test: verify idempotent count"):
            assert Form.all_objects.filter(slug="contact").count() == 1

    @override_settings(FORMS_DATA_RETENTION_DAYS=730)
    def test_seed_presets_use_settings_backed_data_retention_default(self):
        """Preset-created forms should inherit the configured retention default."""
        from quickscale_modules_orgs.current_org import (
            operator_access,
            org_scope,
        )
        from quickscale_modules_orgs.models import Organization

        system_org = Organization.objects.get_system_org()
        with org_scope(system_org):
            Form.objects.all().delete()

        call_command("forms_seed_presets", verbosity=0)

        # Scope the assertion to System org — pre-existing forms in other
        # orgs (e.g. from other test modules) must not affect the check.
        with operator_access(reason="test: verify retention days default"):
            assert set(
                Form.all_objects.filter(organization=system_org).values_list(
                    "data_retention_days", flat=True
                )
            ) == {730}

    @override_settings(FORMS_DATA_RETENTION_DAYS=730)
    def test_seed_presets_preserve_existing_form_data_retention_days(self):
        """Existing forms should keep their stored retention days when presets rerun."""
        from quickscale_modules_orgs.current_org import (
            operator_access,
            org_scope,
        )

        call_command("forms_seed_presets", verbosity=0)
        with operator_access(reason="test: lookup form to customise retention"):
            form = Form.all_objects.get(slug="contact")
        form.data_retention_days = 14
        with org_scope(form.organization):
            form.save(update_fields=["data_retention_days"])

        call_command("forms_seed_presets", verbosity=0)

        with operator_access(reason="test: verify retention days preserved"):
            assert Form.all_objects.get(slug="contact").data_retention_days == 14

    def test_feedback_preset_has_select_field(self):
        """Feedback preset has a select field named 'rating'"""
        from quickscale_modules_orgs.current_org import (
            operator_access,
            org_scope,
        )

        call_command("forms_seed_presets", verbosity=0)
        with operator_access(reason="test: lookup feedback form"):
            form = Form.all_objects.get(slug="feedback")
        # Enter org scope so that form.fields (via all_objects base
        # manager) sees the correct app.current_org_id GUC.
        with org_scope(form.organization):
            assert form.fields.filter(field_type=FormField.FIELD_TYPE_SELECT).exists()

    def test_support_preset_has_priority_select(self):
        """Support preset has a priority select field with three options"""
        from quickscale_modules_orgs.current_org import operator_access

        call_command("forms_seed_presets", verbosity=0)
        with operator_access(reason="test: lookup priority field"):
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
        from quickscale_modules_orgs.current_org import (
            operator_access,
            org_scope,
        )
        from quickscale_modules_orgs.models import Organization

        system_org = Organization.objects.get_system_org()
        tenant_org = Organization.objects.create(
            name="Tenant", slug="tenant-org", is_personal=False
        )

        # Tenant creates a form with slug="contact" (conflicts with preset).
        with org_scope(tenant_org):
            tenant_form = Form.objects.create(
                title="Tenant Contact",
                slug="contact",
                organization=tenant_org,
            )

        # Run seed — should NOT reuse the tenant row.
        call_command("forms_seed_presets", verbosity=0)

        # The System org should now have a "contact" preset.
        with operator_access(reason="test: lookup system contact"):
            system_contact = Form.all_objects.get(
                slug="contact", organization=system_org
            )
        assert system_contact.title == "Contact"
        assert system_contact.pk != tenant_form.pk

        # The tenant's form must remain unchanged.
        with org_scope(tenant_org):
            tenant_form.refresh_from_db()
        assert tenant_form.title == "Tenant Contact"

    def test_seed_idempotent_with_conflicting_tenant_slug(self):
        """Seed must stay idempotent after a tenant-owned same-slug row exists."""
        from quickscale_modules_orgs.current_org import (
            operator_access,
            org_scope,
        )
        from quickscale_modules_orgs.models import Organization

        system_org = Organization.objects.get_system_org()
        tenant_org = Organization.objects.create(
            name="Tenant", slug="tenant-org-2", is_personal=False
        )

        with org_scope(tenant_org):
            Form.objects.create(
                title="Tenant Contact",
                slug="contact",
                organization=tenant_org,
            )

        # Run seed twice.
        call_command("forms_seed_presets", verbosity=0)
        call_command("forms_seed_presets", verbosity=0)

        # System-org presets must exist exactly once.
        with operator_access(reason="test: verify system contact count"):
            assert (
                Form.all_objects.filter(slug="contact", organization=system_org).count()
                == 1
            )
        # Tenant's form still exists independently.
        with operator_access(reason="test: verify tenant contact count"):
            assert (
                Form.all_objects.filter(slug="contact", organization=tenant_org).count()
                == 1
            )


@pytest.mark.django_db
class TestFormsAnonymizeSubmissions:
    """Tests for the forms_anonymize_submissions management command"""

    def test_anonymize_does_not_touch_recent_submissions(self, form):
        """Submissions newer than data_retention_days are not anonymized"""
        from quickscale_modules_orgs.current_org import org_scope

        with org_scope(form.organization):
            sub = FormSubmission.objects.create(
                form=form,
                organization=form.organization,
                ip_address="192.168.1.1",
            )
        call_command("forms_anonymize_submissions", verbosity=0)
        with org_scope(form.organization):
            sub.refresh_from_db()
        assert sub.ip_address == "192.168.1.1"

    def test_anonymize_clears_ip_of_old_submissions(self, form):
        """Submissions older than data_retention_days have ip_address set to None"""
        from datetime import timedelta

        from quickscale_modules_orgs.current_org import org_scope

        with org_scope(form.organization):
            sub = FormSubmission.objects.create(
                form=form,
                organization=form.organization,
                ip_address="10.0.0.1",
                user_agent="OldBrowser/1.0",
            )
        # Force submitted_at to be past the retention window
        cutoff = timezone.now() - timedelta(days=form.data_retention_days + 1)
        with org_scope(form.organization):
            FormSubmission.objects.filter(pk=sub.pk).update(submitted_at=cutoff)

        call_command("forms_anonymize_submissions", verbosity=0)
        with org_scope(form.organization):
            sub.refresh_from_db()
        assert sub.ip_address is None
        assert sub.user_agent == ""

    def test_anonymize_skips_forms_with_zero_retention_days(self):
        """Forms with data_retention_days=0 (keep forever) are skipped"""
        from datetime import timedelta

        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import Organization

        system_org = Organization.objects.get_system_org()
        with org_scope(system_org):
            form = Form.objects.create(
                title="Zero Retention",
                slug="zero-retention",
                data_retention_days=0,
                organization=system_org,
            )
            sub = FormSubmission.objects.create(
                form=form,
                organization=form.organization,
                ip_address="1.2.3.4",
            )
        # Force the submission to be very old
        cutoff = timezone.now() - timedelta(days=9999)
        with org_scope(system_org):
            FormSubmission.objects.filter(pk=sub.pk).update(submitted_at=cutoff)
        call_command("forms_anonymize_submissions", verbosity=0)
        with org_scope(system_org):
            sub.refresh_from_db()
        # ip_address must NOT be nulled because retention_days=0 means keep forever
        assert sub.ip_address == "1.2.3.4"

    def test_anonymize_skips_already_anonymized_submissions(self, form):
        """Submissions already anonymized (ip=None) are not double-processed"""
        from datetime import timedelta

        from quickscale_modules_orgs.current_org import org_scope

        with org_scope(form.organization):
            sub = FormSubmission.objects.create(
                form=form, organization=form.organization, ip_address=None
            )
            cutoff = timezone.now() - timedelta(days=form.data_retention_days + 1)
            FormSubmission.objects.filter(pk=sub.pk).update(submitted_at=cutoff)
        # Should not raise
        call_command("forms_anonymize_submissions", verbosity=0)
        with org_scope(form.organization):
            sub.refresh_from_db()
        assert sub.ip_address is None


@pytest.mark.django_db
class TestFormsAnonymizeSubmissionsOperatorPath:
    """Phase F11.12a: verify management command uses the operator manager."""

    def test_command_iterates_all_forms_including_system_org(self):
        """Command uses all_objects so it visits all forms including System-org."""
        from datetime import timedelta

        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import Organization

        system_org = Organization.objects.get_system_org()

        with org_scope(system_org):
            form = Form.objects.create(
                title="System Org Form",
                slug="system-org-form",
                data_retention_days=30,
                organization=system_org,
            )
            sub = FormSubmission.objects.create(
                form=form,
                organization=form.organization,
                ip_address="10.0.0.1",
                user_agent="OldBrowser/1.0",
            )
            cutoff = timezone.now() - timedelta(days=31)
            FormSubmission.objects.filter(pk=sub.pk).update(submitted_at=cutoff)

        call_command("forms_anonymize_submissions", verbosity=0)
        with org_scope(system_org):
            sub.refresh_from_db()
        assert sub.ip_address is None
        assert sub.user_agent == ""

    def test_command_iterates_via_all_objects(self):
        """Command iterates Form.all_objects.all() (operator manager)."""
        with patch.object(Form, "all_objects") as mock_mgr:
            mock_mgr.all.return_value = Form.objects.none()
            call_command("forms_anonymize_submissions", verbosity=0)
            mock_mgr.all.assert_called_once()

    # CR-SA85-REV-006: two-org repeated anonymization test.
    def test_two_org_repeated_anonymization(self):
        """Repeated anonymization across two orgs is idempotent and
        correctly clears IP/user_agent for both orgs' old submissions
        while preserving recent ones.

        Creates old submissions under org_a and org_b, runs anonymize
        twice, and verifies both orgs' old submissions are anonymized
        while recent ones are preserved.
        """
        from datetime import timedelta

        from quickscale_modules_orgs.current_org import (
            get_current_org_id,
            org_scope,
        )
        from quickscale_modules_orgs.models import Organization

        org_a = Organization.objects.create(
            name="Anon Two-Org A", slug="anon-two-org-a"
        )
        org_b = Organization.objects.create(
            name="Anon Two-Org B", slug="anon-two-org-b"
        )

        # Create old submissions under both orgs (past retention window).
        with org_scope(org_a):
            old_a = FormSubmission.objects.create(
                form=Form.objects.create(
                    title="Anon Form A",
                    slug="anon-form-a",
                    organization=org_a,
                    data_retention_days=30,
                ),
                organization=org_a,
                ip_address="10.0.0.1",
                user_agent="OldAgentA/1.0",
            )
            cutoff = timezone.now() - timedelta(days=31)
            FormSubmission.objects.filter(pk=old_a.pk).update(submitted_at=cutoff)

        with org_scope(org_b):
            old_b = FormSubmission.objects.create(
                form=Form.objects.create(
                    title="Anon Form B",
                    slug="anon-form-b",
                    organization=org_b,
                    data_retention_days=30,
                ),
                organization=org_b,
                ip_address="10.0.0.2",
                user_agent="OldAgentB/1.0",
            )
            cutoff = timezone.now() - timedelta(days=31)
            FormSubmission.objects.filter(pk=old_b.pk).update(submitted_at=cutoff)

        # Recent submission (within retention window).
        with org_scope(org_a):
            recent = FormSubmission.objects.create(
                form=Form.all_objects.get(slug="anon-form-a"),
                organization=org_a,
                ip_address="10.0.0.3",
                user_agent="RecentAgent/1.0",
            )

        # Run anonymize twice.
        call_command("forms_anonymize_submissions", verbosity=0)
        call_command("forms_anonymize_submissions", verbosity=0)

        # Verify old submissions are anonymized in both orgs.
        with org_scope(org_a):
            old_a.refresh_from_db()
        assert old_a.ip_address is None, "Org A old submission must be anonymized"
        assert old_a.user_agent == "", "Org A old submission user_agent must be cleared"

        with org_scope(org_b):
            old_b.refresh_from_db()
        assert old_b.ip_address is None, "Org B old submission must be anonymized"
        assert old_b.user_agent == "", "Org B old submission user_agent must be cleared"

        # Recent submission must be preserved.
        with org_scope(org_a):
            recent.refresh_from_db()
        assert recent.ip_address == "10.0.0.3", "Recent submission must keep its IP"
        assert recent.user_agent == "RecentAgent/1.0", (
            "Recent submission must keep its user_agent"
        )

        # Verify no context leak.
        assert get_current_org_id() is None, "anonymize must not leak org context"


# ---------------------------------------------------------------------------
# T1.17 — purge_organization integration test for forms delete branch
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPurgeOrganization:
    """purge_organization must delete form rows owned by the purged org."""

    def test_purge_deletes_org_forms(self):
        """Form and FormSubmission rows are deleted by purge_organization."""
        from io import StringIO

        from quickscale_modules_orgs.current_org import (
            operator_access,
            org_scope,
        )

        org = Organization.objects.create(name="Purgeable Org", slug="purgeable")
        with org_scope(org):
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
        with operator_access(reason="test: verify forms purged"):
            assert Form.all_objects.filter(organization_id=org_id).count() == 0
        assert OrganizationTombstone.objects.filter(organization_id=org_id).exists()
