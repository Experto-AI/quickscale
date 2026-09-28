"""Prune expired backup artifacts according to the active retention policy."""

from django.core.management.base import BaseCommand, CommandError

from quickscale_core.runtime import ADAPTER_FUNCTIONS, BackupError


class Command(BaseCommand):
    """Management command for retention pruning."""

    help = "Delete expired backup files and mark their metadata as deleted"

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        try:
            result = ADAPTER_FUNCTIONS["prune_backups"]()
        except BackupError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"Pruned {result['deleted_count']} expired backup artifact(s)"
            )
        )
