"""Set or clear a rollback pin on one stored snapshot."""

import json

from django.core.management.base import BaseCommand, CommandError

from quickscale_modules_backups.services import (
    BackupError,
    clear_backup_snapshot_rollback_pin,
    set_backup_snapshot_rollback_pin,
)


class Command(BaseCommand):
    """Management command for time-bounded rollback pin management."""

    help = "Set or clear a rollback pin on one stored backup snapshot"

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument("snapshot_id", help="Public stored snapshot locator")
        parser.add_argument(
            "--hours",
            type=int,
            help="Pin duration in hours when setting a rollback pin.",
        )
        parser.add_argument(
            "--reason",
            help="Operator reason for the rollback pin.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear any active rollback pin instead of setting one.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            dest="as_json",
            help="Emit structured rollback-pin output for automation.",
        )

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        snapshot_id = options["snapshot_id"]
        should_clear = bool(options["clear"])
        hours = options["hours"]
        reason = options["reason"] or ""

        if should_clear:
            if hours is not None or reason.strip():
                raise CommandError(
                    "--clear cannot be combined with --hours or --reason."
                )
            try:
                report = clear_backup_snapshot_rollback_pin(snapshot_id)
            except BackupError as exc:
                raise CommandError(str(exc)) from exc
            action_label = f"Cleared rollback pin for snapshot {report['snapshot_id']}"
        else:
            if hours is None:
                raise CommandError("--hours is required when setting a rollback pin.")
            if not reason.strip():
                raise CommandError("--reason is required when setting a rollback pin.")
            try:
                report = set_backup_snapshot_rollback_pin(
                    snapshot_id,
                    ttl_hours=hours,
                    reason=reason,
                )
            except BackupError as exc:
                raise CommandError(str(exc)) from exc
            action_label = f"Pinned snapshot {report['snapshot_id']}"

        if options["as_json"]:
            self.stdout.write(json.dumps(report, indent=2, sort_keys=True))
            return

        rollback_pin = report["rollback_pin"]
        self.stdout.write(self.style.SUCCESS(action_label))
        self.stdout.write(f"Rollback pin active: {str(rollback_pin['active']).lower()}")
        self.stdout.write(
            f"Rollback pin expires at: {rollback_pin['expires_at'] or 'none'}"
        )
        self.stdout.write(f"Rollback pin reason: {rollback_pin['reason'] or 'none'}")
