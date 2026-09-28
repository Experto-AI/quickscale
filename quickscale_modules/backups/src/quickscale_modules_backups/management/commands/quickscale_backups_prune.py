"""Prune expired backup artifacts according to the active retention policy."""

from django.core.management.base import BaseCommand, CommandError

from quickscale_core.runtime import ADAPTER_FUNCTIONS, BackupError


class Command(BaseCommand):
    """Management command for retention pruning."""

    help = "Delete expired backup files and mark their metadata as deleted"

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Report expired artifacts without deleting them.",
        )

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        dry_run = bool(options["dry_run"])
        try:
            result = ADAPTER_FUNCTIONS["prune_backups"](dry_run=dry_run)
        except BackupError as exc:
            raise CommandError(str(exc)) from exc
        verb = "Would prune" if dry_run else "Pruned"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {result['deleted_count']} expired backup artifact(s)"
            )
        )
