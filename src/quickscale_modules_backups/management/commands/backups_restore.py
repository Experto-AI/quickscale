"""Validate or execute a guarded backup restore."""

from django.core.management.base import BaseCommand, CommandError

from quickscale_modules_backups.models import BackupArtifact
from quickscale_modules_backups.services import BackupError, restore_backup_source


class Command(BaseCommand):
    """Management command for guarded restore execution."""

    help = "Validate or execute a guarded restore for a backup artifact or file"

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument(
            "artifact_id",
            nargs="?",
            type=int,
            help="BackupArtifact primary key",
        )
        parser.add_argument(
            "--snapshot-id",
            dest="snapshot_id",
            help="Stored snapshot locator for the authoritative dump artifact.",
        )
        parser.add_argument(
            "--file",
            dest="file_path",
            help=(
                "Operator-supplied restore file path. Use either artifact_id or "
                "--file PATH."
            ),
        )
        parser.add_argument(
            "--confirm",
            required=True,
            help=(
                "Must exactly match the artifact filename or file basename before "
                "restore may proceed."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate the artifact and guardrails without executing restore.",
        )
        parser.add_argument(
            "--allow-production",
            action="store_true",
            help=(
                "Record explicit destructive-restore intent in CLI workflows; "
                "outside DEBUG mode QUICKSCALE_BACKUPS_ALLOW_RESTORE=true is "
                "still required."
            ),
        )

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        artifact_id = options["artifact_id"]
        snapshot_id = options["snapshot_id"]
        file_path = options["file_path"]
        provided_source_count = sum(
            source is not None for source in (artifact_id, snapshot_id, file_path)
        )
        if provided_source_count == 0:
            raise CommandError(
                "Provide either an artifact_id, --snapshot-id, or --file PATH."
            )
        if provided_source_count > 1:
            raise CommandError(
                "Choose exactly one restore source: an artifact id, --snapshot-id, or --file PATH."
            )

        artifact = None
        if artifact_id is not None:
            try:
                artifact = BackupArtifact.objects.get(pk=artifact_id)
            except BackupArtifact.DoesNotExist as exc:
                raise CommandError("Backup artifact not found") from exc

        try:
            result = restore_backup_source(
                artifact=artifact,
                file_path=file_path,
                snapshot_id=snapshot_id,
                confirmation=options["confirm"],
                dry_run=bool(options["dry_run"]),
                allow_production=bool(options["allow_production"]),
            )
        except BackupError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(result.message))
        for warning in result.warnings:
            self.stdout.write(
                self.style.WARNING(f"Warning [{warning.code}]: {warning.message}")
            )
