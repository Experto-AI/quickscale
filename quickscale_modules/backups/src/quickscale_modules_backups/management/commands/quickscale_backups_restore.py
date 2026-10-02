"""
Validate or execute a guarded backup restore.

SA20: When an artifact carries Status.RESTORING, the command persists
restore_started_at on entry and transitions to Status.FAILED + restore_error
on failure. Admin-triggered background restores are observable through
the artifact's status and error fields.

CR-SA20-006: The ``--local-only`` flag forces
``RestoreSourceResolutionMode.LOCAL_ONLY`` so the child never falls
back to remote materialization even when the local file disappears
after enqueue.

CR-SA20-007: The admin parent now persists Status.RESTORING before
Popen (not after), so a fast child terminal update is never missed or
overwritten.  The failure handler here catches all ``Exception``
subclasses (not just ``BackupError``) so that fast failures and
non-BackupError crashes record ``Status.FAILED`` instead of
stranding ``Status.RESTORING``.  The handler refreshes DB state
unconditionally before writing to handle concurrent state changes.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone as django_timezone
from quickscale_core.runtime import ADAPTER_FUNCTIONS


def _require_single_restore_source(options: dict[str, Any]) -> None:
    """Refuse a restore invocation without exactly one source."""
    provided_source_count = sum(
        source is not None
        for source in (
            options["artifact_id"],
            options["snapshot_id"],
            options["file_path"],
        )
    )
    if provided_source_count == 0:
        raise CommandError(
            "Provide either an artifact_id, --snapshot-id, or --file PATH."
        )
    if provided_source_count > 1:
        raise CommandError(
            "Choose exactly one restore source: an artifact id, --snapshot-id, or --file PATH."
        )


def _mark_restore_started(artifact_id: int | None) -> Any:
    """Load the target artifact and stamp a RESTORING row's start time.

    SA20: if this artifact was marked Status.RESTORING by the admin
    dispatch, track the lifecycle.
    """
    if artifact_id is None:
        return None

    from quickscale_modules_backups.models import BackupArtifact

    try:
        artifact = BackupArtifact.objects.get(pk=artifact_id)
    except BackupArtifact.DoesNotExist:
        return None
    if (
        artifact.status == BackupArtifact.Status.RESTORING
        and artifact.restore_started_at is None
    ):
        artifact.restore_started_at = django_timezone.now()
        artifact.save(update_fields=["restore_started_at", "updated_at"])
    return artifact


def _record_restore_failure(artifact: Any, exc: Exception) -> None:
    """Record a failed restore on a RESTORING artifact.

    SA20 / CR-SA20-007: Record failure for Status.RESTORING artifacts on
    any exception (BackupError, fast failures, generic crashes) so the
    status is never stranded.  Refresh DB state unconditionally before
    writing to handle concurrent status changes.
    """
    if artifact is None:
        return

    from quickscale_modules_backups.models import BackupArtifact

    try:
        artifact.refresh_from_db()
        if artifact.status != BackupArtifact.Status.RESTORING:
            return
        artifact.status = BackupArtifact.Status.FAILED
        artifact.restore_error = str(exc)
        artifact.save(
            update_fields=[
                "status",
                "restore_error",
                "updated_at",
            ]
        )
    except BackupArtifact.DoesNotExist:
        pass


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
            "--local-only",
            action="store_true",
            help=(
                "Forbid remote materialization — fail the restore if the "
                "local file is missing.  Used by the admin async dispatch "
                "to enforce the admin restore contract."
            ),
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
        _require_single_restore_source(options)
        artifact = _mark_restore_started(options["artifact_id"])

        # CR-SA20-006: Map --local-only to LOCAL_ONLY resolution mode so
        # the child never falls back to remote materialization.
        resolution_mode = "local_only" if options["local_only"] else None

        try:
            result = ADAPTER_FUNCTIONS["restore_backup"](
                artifact_id=options["artifact_id"],
                snapshot_id=options["snapshot_id"],
                file_path=options["file_path"],
                confirmation=options["confirm"],
                dry_run=bool(options["dry_run"]),
                allow_production=bool(options["allow_production"]),
                resolution_mode=resolution_mode,
            )
        except Exception as exc:
            _record_restore_failure(artifact, exc)
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(result["message"]))
        for warning in result.get("warnings", []):
            self.stdout.write(
                self.style.WARNING(f"Warning [{warning['code']}]: {warning['message']}")
            )
