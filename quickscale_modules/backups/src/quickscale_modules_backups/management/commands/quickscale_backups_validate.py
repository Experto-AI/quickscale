"""Validate a recorded backup artifact."""

from django.core.management.base import BaseCommand, CommandError

from quickscale_core.runtime import ADAPTER_FUNCTIONS, BackupError


class Command(BaseCommand):
    """Management command for validating a backup artifact."""

    help = "Validate checksum and local availability for a backup artifact"

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument("artifact_id", type=int, help="BackupArtifact primary key")

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        try:
            result = ADAPTER_FUNCTIONS["validate_artifact"](
                artifact_id=options["artifact_id"],
            )
        except BackupError as exc:
            raise CommandError(str(exc)) from exc

        if not result["valid"]:
            raise CommandError("; ".join(result["issues"]))

        self.stdout.write(
            self.style.SUCCESS(f"Validated artifact {result['artifact_id']}")
        )
