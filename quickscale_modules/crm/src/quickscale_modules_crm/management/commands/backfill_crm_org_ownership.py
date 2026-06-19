"""Backfill legacy NULL organization ownership to a selected organization."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from quickscale_modules_crm.models import (
    Company,
    Contact,
    Deal,
    Stage,
    Tag,
)
from quickscale_modules_orgs.models import Organization


# Models with organization FK that participate in backfill.
# Order is informational; each model is independent.
_BACKFILL_MODELS = (
    ("Tag", Tag),
    ("Company", Company),
    ("Contact", Contact),
    ("Stage", Stage),
    ("Deal", Deal),
)


class Command(BaseCommand):
    help = (
        "Backfill legacy CRM rows with NULL organization ownership to a "
        "selected organization. Updates only rows where organization_id IS NULL. "
        "Aborts without partial writes if conflicting ownership is detected."
    )

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument(
            "--org-slug",
            required=True,
            help="Slug of the target organization to receive NULL-owned rows.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without making changes.",
        )

    def handle(self, *args: object, **options: object) -> None:
        del args
        org_slug = str(options["org_slug"])
        dry_run = bool(options["dry_run"])

        # Resolve target organization.
        try:
            target_org = Organization.objects.get(slug=org_slug)
        except Organization.DoesNotExist:
            raise CommandError(
                f"Organization with slug '{org_slug}' does not exist. "
                "Use --org-slug to specify a valid organization slug."
            )

        self.stdout.write(
            f"Target organization: {target_org.name} (slug={target_org.slug})"
        )

        # Pre-flight: check for conflicts and count NULL rows.
        conflicts: list[str] = []
        null_counts: dict[str, int] = {}

        for model_name, model_class in _BACKFILL_MODELS:
            null_qs = model_class.objects.filter(organization__isnull=True)
            null_count = null_qs.count()
            null_counts[model_name] = null_count

            # Check for rows that already have a different organization.
            # This is a conflict: we cannot safely assign NULL rows if some
            # rows already point to a different org (mixed ownership).
            non_null_qs = model_class.objects.filter(organization__isnull=False)
            non_null_org_ids = set(
                non_null_qs.values_list("organization_id", flat=True).distinct()
            )
            if non_null_org_ids and target_org.pk not in non_null_org_ids:
                # All non-null rows point to a different org — this is a conflict.
                conflicts.append(
                    f"{model_name}: {len(non_null_org_ids)} existing organization(s) "
                    f"found, none matching target {target_org.slug}"
                )

        # Report pre-flight findings.
        if null_counts:
            self.stdout.write("NULL-owned rows by model:")
            for model_name, count in null_counts.items():
                self.stdout.write(f"  {model_name}: {count}")

        if conflicts:
            self.stdout.write(self.style.WARNING("Conflicting ownership detected:"))
            for conflict_msg in conflicts:
                self.stdout.write(f"  {conflict_msg}")
            raise CommandError(
                "Cannot backfill: conflicting organization ownership detected. "
                "Resolve conflicts manually before running backfill."
            )

        total_null = sum(null_counts.values())
        if total_null == 0:
            self.stdout.write(
                self.style.SUCCESS("No NULL-owned rows found. Nothing to backfill.")
            )
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run: would update {total_null} rows to organization {target_org.slug}"
                )
            )
            return

        # Perform the backfill in a transaction.
        with transaction.atomic():
            updated_counts: dict[str, int] = {}
            for model_name, model_class in _BACKFILL_MODELS:
                updated = model_class.objects.filter(organization__isnull=True).update(
                    organization=target_org
                )
                updated_counts[model_name] = updated

        # Report results.
        self.stdout.write(self.style.SUCCESS("Backfill complete. Updated rows:"))
        for model_name, count in updated_counts.items():
            self.stdout.write(f"  {model_name}: {count}")

        # Verify idempotency: check remaining NULL counts.
        remaining_null: dict[str, int] = {}
        for model_name, model_class in _BACKFILL_MODELS:
            remaining = model_class.objects.filter(organization__isnull=True).count()
            remaining_null[model_name] = remaining

        total_remaining = sum(remaining_null.values())
        if total_remaining > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"Warning: {total_remaining} NULL-owned rows remain after backfill"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("All CRM rows now have organization ownership.")
            )
