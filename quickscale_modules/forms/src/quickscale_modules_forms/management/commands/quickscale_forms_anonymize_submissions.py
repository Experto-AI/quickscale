"""Management command to anonymize old form submissions for GDPR compliance"""

from typing import Any

from django.core.management.base import BaseCommand

from quickscale_core.runtime import require_scheduled_module_enabled
from quickscale_modules_forms.management.commands._retention import (
    anonymize_expired_submissions,
)


class Command(BaseCommand):
    """Anonymizes IP address and user agent for submissions older than each form's data_retention_days"""

    help = (
        "Anonymize submission data older than each form's data_retention_days setting"
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--trigger",
            choices=["manual", "scheduled"],
            default="manual",
            help=(
                "Invocation provenance (default: manual). A scheduled run is "
                "refused while the module is off; a manual run stays."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Report submissions that would be anonymized without changing them.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        trigger = str(options.get("trigger") or "manual")
        require_scheduled_module_enabled(trigger, module_name="forms")

        dry_run = bool(options.get("dry_run", False))
        per_form = anonymize_expired_submissions(dry_run=dry_run)

        for slug, count in per_form:
            if dry_run:
                self.stdout.write(
                    f"  Would anonymize {count} submissions for form: {slug}"
                )
            else:
                self.stdout.write(f"  Anonymized {count} submissions for form: {slug}")

        total_anonymized = sum(count for _, count in per_form)
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Dry run. Submissions that would be anonymized: {total_anonymized}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Done. Total submissions anonymized: {total_anonymized}"
                )
            )
