"""Validate or execute a guarded backup restore.

SA20: When an artifact carries STATUS_RESTORING, the command persists
restore_started_at on entry and transitions to STATUS_FAILED + restore_error
on BackupError. Admin-triggered background restores are observable through
the artifact's status and error fields.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone as django_timezone

from quickscale_core.runtime import ADAPTER_FUNCTIONS, BackupError


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
        from quickscale_modules_backups.models import BackupArtifact

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

        # SA20: If this artifact was marked STATUS_RESTORING by the admin
        # dispatch, track the lifecycle.
        artifact = None
        if artifact_id is not None:
            try:
                artifact = BackupArtifact.objects.get(pk=artifact_id)
                if artifact.status == BackupArtifact.STATUS_RESTORING:
                    if artifact.restore_started_at is None:
                        artifact.restore_started_at = django_timezone.now()
                        artifact.save(
                            update_fields=["restore_started_at", "updated_at"]
                        )
            except BackupArtifact.DoesNotExist:
                pass

        try:
            result = ADAPTER_FUNCTIONS["restore_backup"](
                artifact_id=artifact_id,
                snapshot_id=snapshot_id,
                file_path=file_path,
                confirmation=options["confirm"],
                dry_run=bool(options["dry_run"]),
                allow_production=bool(options["allow_production"]),
            )
        except BackupError as exc:
            # SA20: Persist failure status when a STATUS_RESTORING artifact
            # fails to restore. The adapter sets STATUS_RESTORED on success.
            if (
                artifact is not None
                and artifact.status == BackupArtifact.STATUS_RESTORING
            ):
                artifact.refresh_from_db()
                if artifact.status == BackupArtifact.STATUS_RESTORING:
                    artifact.status = BackupArtifact.STATUS_FAILED
                    artifact.restore_error = str(exc)
                    artifact.save(
                        update_fields=["status", "restore_error", "updated_at"]
                    )
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(result["message"]))
        for warning in result.get("warnings", []):
            self.stdout.write(
                self.style.WARNING(f"Warning [{warning['code']}]: {warning['message']}")
            )
