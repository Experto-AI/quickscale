"""Create a backup artifact for the active project database."""

from django.core.management.base import BaseCommand, CommandError

from quickscale_modules_backups.services import BackupError, create_backup


class Command(BaseCommand):
    """Management command for on-demand backup creation."""

    help = "Create a private database backup artifact"

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument(
            "--scheduled",
            action="store_true",
            help="Mark the created artifact as coming from an external scheduler.",
        )

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        trigger = "scheduled" if options["scheduled"] else "manual"
        try:
            artifact = create_backup(trigger=trigger)
        except BackupError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(f"Created backup {artifact.filename}"))
        self.stdout.write(f"Artifact id: {artifact.pk}")
        self.stdout.write(f"Local path: {artifact.local_path}")
        if artifact.remote_key:
            self.stdout.write(f"Remote key: {artifact.remote_key}")
