"""Validate or execute a guarded backup restore."""

from django.core.management.base import BaseCommand, CommandError

from quickscale_modules_backups.models import BackupArtifact
from quickscale_modules_backups.services import BackupError, restore_backup_artifact


class Command(BaseCommand):
    """Management command for guarded restore execution."""

    help = "Validate or execute a guarded restore for a backup artifact"

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument("artifact_id", type=int, help="BackupArtifact primary key")
        parser.add_argument(
            "--confirm",
            required=True,
            help="Must exactly match the backup filename before restore may proceed.",
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
        try:
            artifact = BackupArtifact.objects.get(pk=options["artifact_id"])
        except BackupArtifact.DoesNotExist as exc:
            raise CommandError("Backup artifact not found") from exc

        try:
            result = restore_backup_artifact(
                artifact,
                confirmation=options["confirm"],
                dry_run=bool(options["dry_run"]),
                allow_production=bool(options["allow_production"]),
            )
        except BackupError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(result.message))
