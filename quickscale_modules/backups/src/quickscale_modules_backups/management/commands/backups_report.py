"""Report the stored-snapshot state for one backup snapshot id."""

import json

from django.core.management.base import BaseCommand, CommandError

from quickscale_modules_backups.services import BackupError, report_backup_snapshot


class Command(BaseCommand):
    """Management command for snapshot inspection/reporting."""

    help = "Report one stored backup snapshot by snapshot_id"

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument("snapshot_id", help="Public stored snapshot locator")
        parser.add_argument(
            "--sidecar-payload",
            action="append",
            dest="sidecar_payloads",
            default=[],
            help=(
                "Include one parsed sidecar payload in --json output. "
                "May be supplied multiple times."
            ),
        )
        parser.add_argument(
            "--json",
            action="store_true",
            dest="as_json",
            help="Emit structured snapshot report output for automation.",
        )

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        try:
            sidecar_payloads = options["sidecar_payloads"]
            if sidecar_payloads:
                report = report_backup_snapshot(
                    options["snapshot_id"],
                    sidecar_payloads=sidecar_payloads,
                )
            else:
                report = report_backup_snapshot(options["snapshot_id"])
        except BackupError as exc:
            raise CommandError(str(exc)) from exc

        if options["as_json"]:
            self.stdout.write(json.dumps(report, indent=2, sort_keys=True))
            return

        authoritative_dump = report["authoritative_dump"] or {}
        rollback_pin = report["rollback_pin"]
        self.stdout.write(self.style.SUCCESS(f"Snapshot id: {report['snapshot_id']}"))
        self.stdout.write(f"Status: {report['status']}")
        self.stdout.write(f"Source environment: {report['source_environment']}")
        self.stdout.write(f"Artifact id: {authoritative_dump.get('artifact_id', '')}")
        self.stdout.write(f"Filename: {authoritative_dump.get('filename', '')}")
        self.stdout.write(f"Confirmation value: {report['confirmation_value']}")
        self.stdout.write(f"Local root: {report['local_root_path']}")
        self.stdout.write(f"Remote root: {report['remote_root_key']}")
        self.stdout.write(f"Rollback pin active: {str(rollback_pin['active']).lower()}")
        self.stdout.write(
            f"Rollback pin expires at: {rollback_pin['expires_at'] or 'none'}"
        )
        self.stdout.write(f"Rollback pin reason: {rollback_pin['reason'] or 'none'}")
        if report["failure_note"]:
            self.stdout.write(f"Failure note: {report['failure_note']}")
        for filename, summary in report["sidecar_summary"].items():
            manifest_status = summary["manifest_status"] or "n/a"
            self.stdout.write(
                f"Sidecar {filename}: {summary['status']} ({manifest_status})"
            )
