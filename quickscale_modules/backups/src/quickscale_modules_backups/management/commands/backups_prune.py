"""Prune expired backup artifacts according to the active retention policy."""

from django.core.management.base import BaseCommand

from quickscale_modules_backups.services import prune_expired_backups


class Command(BaseCommand):
    """Management command for retention pruning."""

    help = "Delete expired backup files and mark their metadata as deleted"

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        deleted_count = prune_expired_backups()
        self.stdout.write(
            self.style.SUCCESS(f"Pruned {deleted_count} expired backup artifact(s)")
        )
