"""Create a backup artifact for the active project database."""

import json

from django.core.management.base import BaseCommand, CommandError

from quickscale_modules_backups.services import (
    BackupError,
    build_backup_snapshot_report,
    create_backup,
)


class Command(BaseCommand):
    """Management command for on-demand backup creation."""

    help = "Create a private database backup artifact"

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument(
            "--scheduled",
            action="store_true",
            help="Mark the created artifact as coming from an external scheduler.",
        )
        parser.add_argument(
            "--resume",
            dest="resume_snapshot_id",
            help="Resume an existing snapshot capture by snapshot id.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            dest="as_json",
            help="Emit structured snapshot capture output for automation.",
        )

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        trigger = "scheduled" if options["scheduled"] else "manual"
        resume_snapshot_id = (
            str(options.get("resume_snapshot_id") or "").strip() or None
        )
        try:
            if resume_snapshot_id is None:
                artifact = create_backup(trigger=trigger)
            else:
                artifact = create_backup(
                    trigger=trigger,
                    resume_snapshot_id=resume_snapshot_id,
                )
        except BackupError as exc:
            raise CommandError(str(exc)) from exc

        snapshot = getattr(artifact, "authoritative_snapshot", None)
        if snapshot is None:
            raise CommandError("Created backup is missing its stored snapshot record.")

        report = build_backup_snapshot_report(snapshot)
        if options["as_json"]:
            self.stdout.write(json.dumps(report, indent=2, sort_keys=True))
            return

        action_label = "Resumed backup" if resume_snapshot_id else "Created backup"
        self.stdout.write(self.style.SUCCESS(f"{action_label} {artifact.filename}"))
        self.stdout.write(f"Artifact id: {artifact.pk}")
        self.stdout.write(f"Snapshot id: {report['snapshot_id']}")
        self.stdout.write(f"Snapshot status: {report['status']}")
        self.stdout.write(f"Snapshot root: {report['local_root_path']}")
        self.stdout.write(f"Local path: {artifact.local_path}")
        if artifact.remote_key:
            self.stdout.write(f"Remote key: {artifact.remote_key}")
        if report["failure_note"]:
            self.stdout.write(
                self.style.WARNING(f"Snapshot warning: {report['failure_note']}")
            )
