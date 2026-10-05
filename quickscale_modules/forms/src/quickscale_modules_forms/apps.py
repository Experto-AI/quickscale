"""Django app configuration for QuickScale Forms module.

Startup configuration is validated by rule 3's generic settings check,
registered through ``quickscale_core.runtime`` from ``ready()``.
"""

from django.apps import AppConfig

from quickscale_core.runtime import (
    PersonalDataExclusion,
    PersonalDataField,
    PersonalDataTreatment,
    register_module_settings_check,
)


class QuickscaleFormsConfig(AppConfig):
    """Configuration for QuickScale Forms module"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_forms"
    label = "quickscale_forms"
    verbose_name = "QuickScale Forms"

    def personal_data_declarations(
        self,
    ) -> tuple[PersonalDataField | PersonalDataExclusion, ...]:
        """Declare the personal-data rows forms owns (rule 49).

        The form's creator link stays attributed to the disabled account;
        organization-owned form configuration and submission data about
        non-users is excluded with its reason.
        """
        return (
            PersonalDataField(
                app_label=self.label,
                model_name="Form",
                field_name="created_by",
                treatment=PersonalDataTreatment.KEEP_LINK,
                note="Form stays attributed to the deleted user.",
            ),
            PersonalDataExclusion(
                app_label=self.label,
                model_name="Form",
                field_name="description",
                reason="Form configuration owned by the organization; retained as-is.",
            ),
            PersonalDataExclusion(
                app_label=self.label,
                model_name="Form",
                field_name="success_message",
                reason="Form configuration owned by the organization; retained as-is.",
            ),
            PersonalDataExclusion(
                app_label=self.label,
                model_name="Form",
                field_name="notify_emails",
                reason="Organization recipient addresses, not the user's address.",
            ),
            PersonalDataExclusion(
                app_label=self.label,
                model_name="FormSubmission",
                field_name="ip_address",
                reason="Submission data about a non-user; belongs to the organization.",
            ),
        )

    def ready(self) -> None:
        from quickscale_modules_forms.checks import RETIRED_SETTINGS

        register_module_settings_check(self, "forms", retired_settings=RETIRED_SETTINGS)
