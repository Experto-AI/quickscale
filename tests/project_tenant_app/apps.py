"""Django application configuration for the project tenant fixture."""

from django.apps import AppConfig

from quickscale_core.runtime import (
    PersonalDataExclusion,
    PersonalDataField,
    PersonalDataTreatment,
)


class ProjectTenantAppConfig(AppConfig):
    """Register a real project-owned app for tenant discovery regressions."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "tests.project_tenant_app"
    label = "project_tenant_app"

    def personal_data_declarations(
        self,
    ) -> tuple[PersonalDataField | PersonalDataExclusion, ...]:
        """Declare the fixture's own rows, as a project app would (rule 49).

        ``ProjectListing.contact_email`` is deliberately left undeclared so the
        W006 control proves an undeclared project-app ``EmailField`` on a
        user-referencing model fails the real walk.
        """
        return (
            PersonalDataField(
                app_label=self.label,
                model_name="ProjectListing",
                field_name="created_by",
                treatment=PersonalDataTreatment.KEEP_LINK,
                note="Fixture row stays attributed to the disabled account.",
            ),
            PersonalDataExclusion(
                app_label=self.label,
                model_name="ProjectListing",
                field_name="description",
                reason="Fixture listing content owned by the organization; retained as-is.",
            ),
            PersonalDataExclusion(
                app_label=self.label,
                model_name="ProjectListing",
                field_name="featured_image",
                reason="Fixture listing image owned by the organization; retained as-is.",
            ),
        )
