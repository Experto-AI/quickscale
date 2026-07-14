"""Django app configuration for QuickScale backups module."""

from __future__ import annotations

from django.apps import AppConfig


class QuickscaleBackupsConfig(AppConfig):
    """Configuration for the QuickScale backups module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_backups"
    label = "quickscale_modules_backups"
    verbose_name = "QuickScale Backups"

    def ready(self) -> None:
        """Register persistence providers at Django startup.

        Registers module-level singleton persistence provider instances with
        the core DR persistence seam.  Registration is identity-idempotent
        (re-registering the same object is a no-op) and fail-hard on
        conflict.  Performs no database I/O.
        """
        # Late import ensures Django is fully loaded before we touch the
        # persistence seam's registration function.
        from quickscale_core.runtime import register_backup_persistence
        from quickscale_modules_backups.persistence import (
            artifact_persistence,
            policy_persistence,
        )

        register_backup_persistence(artifact_persistence, policy_persistence)
