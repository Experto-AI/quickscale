"""Focused tests for CRM management commands (F11.6 backfill)."""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from quickscale_modules_crm.models import (
    Company,
    Contact,
    Deal,
    Stage,
    Tag,
)
from quickscale_modules_orgs.models import Organization


@pytest.mark.django_db
class TestBackfillCrmOrgOwnership:
    """Tests for backfill_crm_org_ownership management command."""

    def test_requires_org_slug(self) -> None:
        """Command requires --org-slug argument."""
        with pytest.raises(CommandError, match="org-slug"):
            call_command(
                "backfill_crm_org_ownership",
                stdout=StringIO(),
                stderr=StringIO(),
            )

    def test_rejects_nonexistent_org_slug(self) -> None:
        """Command rejects an org slug that does not exist."""
        with pytest.raises(CommandError, match="does not exist"):
            call_command(
                "backfill_crm_org_ownership",
                "--org-slug=nonexistent",
                stdout=StringIO(),
                stderr=StringIO(),
            )

    def test_backfills_null_owned_rows_to_target_org(self) -> None:
        """Command assigns NULL-owned rows to the target organization."""
        target_org = Organization.objects.create(name="Target Org", slug="target-org")

        # Create NULL-owned rows.
        tag = Tag.objects.create(name="VIP")
        company = Company.objects.create(name="Acme Corp")
        contact = Contact.objects.create(
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            company=company,
        )
        stage = Stage.objects.create(name="Prospecting", order=1)
        deal = Deal.objects.create(
            title="Big Deal",
            contact=contact,
            stage=stage,
        )

        # Verify all start as NULL-owned.
        assert tag.organization is None
        assert company.organization is None
        assert contact.organization is None
        assert stage.organization is None
        assert deal.organization is None

        stdout = StringIO()
        call_command(
            "backfill_crm_org_ownership",
            "--org-slug=target-org",
            stdout=stdout,
            stderr=StringIO(),
        )

        # Refresh and verify all now point to target_org.
        tag.refresh_from_db()
        company.refresh_from_db()
        contact.refresh_from_db()
        stage.refresh_from_db()
        deal.refresh_from_db()

        assert tag.organization == target_org
        assert company.organization == target_org
        assert contact.organization == target_org
        assert stage.organization == target_org
        assert deal.organization == target_org

        output = stdout.getvalue()
        # Verify the command reported updates for each model (counts may vary due to test data).
        assert "Tag:" in output
        assert "Company:" in output
        assert "Contact:" in output
        assert "Stage:" in output
        assert "Deal:" in output
        assert "Backfill complete" in output

    def test_is_idempotent_on_second_run(self) -> None:
        """Command is idempotent: second run updates 0 rows."""
        target_org = Organization.objects.create(name="Target Org", slug="target-org")

        # Create and backfill NULL-owned rows.
        Tag.objects.create(name="VIP")
        Company.objects.create(name="Acme Corp")

        first_stdout = StringIO()
        call_command(
            "backfill_crm_org_ownership",
            "--org-slug=target-org",
            stdout=first_stdout,
            stderr=StringIO(),
        )

        # Second run should update 0 rows.
        second_stdout = StringIO()
        call_command(
            "backfill_crm_org_ownership",
            "--org-slug=target-org",
            stdout=second_stdout,
            stderr=StringIO(),
        )

        output = second_stdout.getvalue()
        assert "Tag: 0" in output
        assert "Company: 0" in output
        assert "No NULL-owned rows found" in output or "Nothing to backfill" in output
        # Verify target_org still exists (used by slug in command).
        assert target_org.pk is not None

    def test_aborts_on_conflicting_ownership(self) -> None:
        """Command aborts without writes when conflicting ownership exists."""
        target_org = Organization.objects.create(name="Target Org", slug="target-org")
        other_org = Organization.objects.create(name="Other Org", slug="other-org")

        # Create a NULL-owned tag and an other-org-owned company (conflict).
        tag = Tag.objects.create(name="VIP")
        company = Company.objects.create(name="Acme Corp", organization=other_org)

        with pytest.raises(CommandError, match="conflicting organization ownership"):
            call_command(
                "backfill_crm_org_ownership",
                "--org-slug=target-org",
                stdout=StringIO(),
                stderr=StringIO(),
            )

        # Verify no writes occurred: tag remains NULL-owned.
        tag.refresh_from_db()
        company.refresh_from_db()
        assert tag.organization is None
        assert company.organization == other_org
        # Verify target_org still exists (used by slug in command).
        assert target_org.pk is not None

    def test_allows_backfill_when_existing_rows_match_target_org(self) -> None:
        """Command succeeds when existing non-null rows already point to target org."""
        target_org = Organization.objects.create(name="Target Org", slug="target-org")

        # Create some rows already owned by target_org and some NULL-owned.
        Tag.objects.create(name="Existing", organization=target_org)
        null_tag = Tag.objects.create(name="NullTag")

        stdout = StringIO()
        call_command(
            "backfill_crm_org_ownership",
            "--org-slug=target-org",
            stdout=stdout,
            stderr=StringIO(),
        )

        # Null tag should now be owned by target_org.
        null_tag.refresh_from_db()
        assert null_tag.organization == target_org

        output = stdout.getvalue()
        assert "Tag: 1" in output  # Only the NULL tag was updated.

    def test_dry_run_does_not_write(self) -> None:
        """Command with --dry-run shows what would be updated without writing."""
        target_org = Organization.objects.create(name="Target Org", slug="target-org")

        tag = Tag.objects.create(name="VIP")
        company = Company.objects.create(name="Acme Corp")

        stdout = StringIO()
        call_command(
            "backfill_crm_org_ownership",
            "--org-slug=target-org",
            "--dry-run",
            stdout=stdout,
            stderr=StringIO(),
        )

        # Verify no writes occurred.
        tag.refresh_from_db()
        company.refresh_from_db()
        assert tag.organization is None
        assert company.organization is None
        # Verify target_org still exists (used by slug in command).
        assert target_org.pk is not None

        output = stdout.getvalue()
        assert "Dry run" in output
        assert "would update" in output

    def test_reports_zero_null_rows_gracefully(self) -> None:
        """Command reports success when no NULL-owned rows exist."""
        target_org = Organization.objects.create(name="Target Org", slug="target-org")

        # Create rows already owned by target_org for all models.
        Tag.objects.create(name="VIP", organization=target_org)
        Company.objects.create(name="Acme Corp", organization=target_org)
        company = Company.objects.create(name="Test Co", organization=target_org)
        Contact.objects.create(
            first_name="Test",
            last_name="User",
            email="test@example.com",
            company=company,
            organization=target_org,
        )
        Stage.objects.create(name="Stage 1", order=1, organization=target_org)
        contact = Contact.objects.create(
            first_name="Test2",
            last_name="User2",
            email="test2@example.com",
            company=company,
            organization=target_org,
        )
        Deal.objects.create(
            title="Deal 1",
            contact=contact,
            stage=Stage.objects.filter(organization=target_org).first(),
            organization=target_org,
        )

        # Clear any NULL-owned rows from other tests.
        Tag.objects.filter(organization__isnull=True).delete()
        Company.objects.filter(organization__isnull=True).delete()
        Contact.objects.filter(organization__isnull=True).delete()
        Stage.objects.filter(organization__isnull=True).delete()
        Deal.objects.filter(organization__isnull=True).delete()

        stdout = StringIO()
        call_command(
            "backfill_crm_org_ownership",
            "--org-slug=target-org",
            stdout=stdout,
            stderr=StringIO(),
        )

        output = stdout.getvalue()
        assert "No NULL-owned rows found" in output or "Nothing to backfill" in output
