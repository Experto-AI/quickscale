"""Django app configuration for QuickScale backups module."""

from django.apps import AppConfig

from quickscale_core.runtime import (
    PersonalDataExclusion,
    PersonalDataField,
    PersonalDataTreatment,
    register_module_checks,
    register_module_settings_check,
)


class QuickscaleBackupsConfig(AppConfig):
    """Configuration for the QuickScale backups module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_backups"
    label = "quickscale_backups"
    verbose_name = "QuickScale Backups"

    def personal_data_declarations(
        self,
    ) -> tuple[PersonalDataField | PersonalDataExclusion, ...]:
        """Declare the personal-data rows backups owns (rule 49).

        The initiator link stays attributed to the disabled account; the
        artifact's operational validation and restore diagnostics are about
        the backup, not the operator, and are excluded with their reason.
        """
        return (
            PersonalDataField(
                app_label=self.label,
                model_name="BackupArtifact",
                field_name="initiated_by",
                treatment=PersonalDataTreatment.KEEP_LINK,
                note="Backup record stays attributed to the deleted user.",
            ),
            PersonalDataExclusion(
                app_label=self.label,
                model_name="BackupArtifact",
                field_name="validation_notes",
                reason="Operational backup notes, not personal data about the initiator.",
            ),
            PersonalDataExclusion(
                app_label=self.label,
                model_name="BackupArtifact",
                field_name="restore_error",
                reason="Operational restore diagnostics, not personal data about the initiator.",
            ),
        )

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
