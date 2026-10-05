"""Django app configuration for QuickScale CRM module.

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


class QuickscaleCrmConfig(AppConfig):
    """Configuration for QuickScale CRM module"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_crm"
    label = "quickscale_crm"
    verbose_name = "QuickScale CRM"

    #: Display prefix for the module's models in organization-removal summaries.
    removal_label_prefix = "CRM"

    def personal_data_declarations(
        self,
    ) -> tuple[PersonalDataField | PersonalDataExclusion, ...]:
        """Declare the personal-data rows CRM owns (rule 49).

        Notes and deals stay attributed to the disabled account (no handler
        executes for them); data about contacts, who are not users, and their
        organization content is excluded with its reason.
        """
        return (
            PersonalDataField(
                app_label=self.label,
                model_name="ContactNote",
                field_name="created_by",
                treatment=PersonalDataTreatment.KEEP_LINK,
                note="Note stays attributed to the deleted user.",
            ),
            PersonalDataField(
                app_label=self.label,
                model_name="DealNote",
                field_name="created_by",
                treatment=PersonalDataTreatment.KEEP_LINK,
                note="Note stays attributed to the deleted user.",
            ),
            PersonalDataField(
                app_label=self.label,
                model_name="Deal",
                field_name="owner",
                treatment=PersonalDataTreatment.KEEP_LINK,
                note="Deal stays attributed to the deleted user.",
            ),
            PersonalDataExclusion(
                app_label=self.label,
                model_name="Contact",
                field_name="email",
                reason="Contact is not a user; the address belongs to the organization.",
            ),
            PersonalDataExclusion(
                app_label=self.label,
                model_name="ContactNote",
                field_name="text",
                reason="Organization content about a contact, not about the user.",
            ),
            PersonalDataExclusion(
                app_label=self.label,
                model_name="DealNote",
                field_name="text",
                reason="Organization content about a deal, not about the user.",
            ),
        )

    def ready(self) -> None:
        # ---- SA7.1 — organization_created signal receiver -----------------
        # Import receivers to connect the seed_crm_default_stages_on_org_created
        # receiver.  The @receiver decorator runs at import time, so importing
        # the module is sufficient.
        import quickscale_modules_crm.receivers  # noqa: F401

        from quickscale_modules_crm.checks import RETIRED_SETTINGS

        register_module_settings_check(self, "crm", retired_settings=RETIRED_SETTINGS)
