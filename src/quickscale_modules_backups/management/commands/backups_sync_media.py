"""Dry-run or execute snapshot media sync against target runtime settings."""

import json

from django.core.management.base import BaseCommand, CommandError

from quickscale_modules_backups.services import BackupError, sync_backup_snapshot_media


class Command(BaseCommand):
    """Management command for source-side media sync execution."""

    help = "Dry-run or execute media sync for a stored backup snapshot"

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument("snapshot_id", help="Public stored snapshot locator")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate media sync inputs without copying objects.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            dest="as_json",
            help="Emit structured media sync output for automation.",
        )

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        try:
            result = sync_backup_snapshot_media(
                options["snapshot_id"],
                dry_run=bool(options["dry_run"]),
            )
        except BackupError as exc:
            raise CommandError(str(exc)) from exc

        if options["as_json"]:
            self.stdout.write(json.dumps(result, indent=2, sort_keys=True))
            return

        action = "Validated" if options["dry_run"] else "Synced"
        self.stdout.write(
            self.style.SUCCESS(f"{action} media for snapshot {result['snapshot_id']}")
        )
        self.stdout.write(f"Status: {result['status']}")
        self.stdout.write(f"Strategy: {result['strategy']}")
        self.stdout.write(f"Planned count: {result['planned_count']}")
        self.stdout.write(f"Copied count: {result['copied_count']}")
        self.stdout.write(f"Missing paths: {len(result['missing_paths'])}")
