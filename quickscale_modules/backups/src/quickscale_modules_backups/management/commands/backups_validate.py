"""Validate a recorded backup artifact."""

from django.core.management.base import BaseCommand, CommandError

from quickscale_modules_backups.models import BackupArtifact
from quickscale_modules_backups.services import validate_backup_artifact


class Command(BaseCommand):
    """Management command for validating a backup artifact."""

    help = "Validate checksum and local availability for a backup artifact"

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument("artifact_id", type=int, help="BackupArtifact primary key")

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        try:
            artifact = BackupArtifact.objects.get(pk=options["artifact_id"])
        except BackupArtifact.DoesNotExist as exc:
            raise CommandError("Backup artifact not found") from exc

        issues = validate_backup_artifact(artifact)
        if issues:
            raise CommandError("; ".join(issues))

        self.stdout.write(self.style.SUCCESS(f"Validated {artifact.filename}"))
