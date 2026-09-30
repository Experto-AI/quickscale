"""Django app configuration for QuickScale backups module."""

from django.apps import AppConfig

from quickscale_core.runtime import (
    register_module_checks,
    register_module_settings_check,
)


class QuickscaleBackupsConfig(AppConfig):
    """Configuration for the QuickScale backups module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_backups"
    label = "quickscale_backups"
    verbose_name = "QuickScale Backups"

    def ready(self) -> None:
        """Register persistence providers and run startup checks.

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

        # Late import: keep the app config importable while Django is still
        # populating the app registry.
        from quickscale_modules_backups.checks import check_private_remote_credentials

        # Rule 3 first: a missing or invalid declared setting is reported by
        # the generic check before the runtime check reads it.
        register_module_settings_check(self, "backups")
        register_module_checks(self, [check_private_remote_credentials])
