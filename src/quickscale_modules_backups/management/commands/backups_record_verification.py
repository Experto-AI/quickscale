"""Record one plan or execute verification report for a stored snapshot."""

import json

from django.core.management.base import BaseCommand, CommandError

from quickscale_modules_backups.services import (
    BackupError,
    record_backup_snapshot_verification,
)


class Command(BaseCommand):
    """Management command for route-specific verification persistence."""

    help = "Record one plan or execute verification report for a backup snapshot"

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument("snapshot_id", help="Public stored snapshot locator")
        parser.add_argument("--route", required=True, help="Roadmap route label")
        parser.add_argument(
            "--phase",
            required=True,
            choices=["plan", "execute"],
            help="Verification phase to record.",
        )
        parser.add_argument(
            "--status",
            required=True,
            help="Route-specific verification status to persist.",
        )
        parser.add_argument(
            "--payload-json",
            required=True,
            help="JSON object payload describing the route result.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            dest="as_json",
            help="Emit the updated snapshot report as JSON.",
        )

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        try:
            payload = json.loads(options["payload_json"])
        except json.JSONDecodeError as exc:
            raise CommandError("--payload-json must be a JSON object.") from exc
        if not isinstance(payload, dict):
            raise CommandError("--payload-json must be a JSON object.")

        try:
            report = record_backup_snapshot_verification(
                options["snapshot_id"],
                route=options["route"],
                phase=options["phase"],
                status=options["status"],
                payload=payload,
            )
        except BackupError as exc:
            raise CommandError(str(exc)) from exc

        if options["as_json"]:
            self.stdout.write(json.dumps(report, indent=2, sort_keys=True))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Recorded {options['phase']} verification for snapshot {report['snapshot_id']}"
            )
        )
        self.stdout.write(f"Status: {options['status']}")
        self.stdout.write(f"Route: {options['route']}")
