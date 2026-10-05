"""Django app configuration for QuickScale blog module"""

from typing import Any

from django.apps import AppConfig

from quickscale_core.runtime import (
    PersonalDataExclusion,
    PersonalDataField,
    PersonalDataTreatment,
    register_module_checks,
    register_module_settings_check,
)
from quickscale_modules_orgs.removal import (
    BLOG_PERSONAL_DATA,
    OrganizationRemovalObligation,
    RemovalAction,
)


class QuickscaleBlogConfig(AppConfig):
    """Configuration for QuickScale blog module"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_blog"
    label = "quickscale_blog"
    verbose_name = "QuickScale Blog"

    #: Display prefix for the module's models in organization-removal summaries.
    removal_label_prefix = "Blog"

    def removal_obligations(self) -> tuple[OrganizationRemovalObligation, ...]:
        """Declare the author profile's personal data as blog's own obligation.

        The person's posts and uploaded media belong to the organization and
        stay attributed to the disabled account, so only the profile fields are
        scrubbed.  An organization purge does not touch a user profile.
        """
        return (
            OrganizationRemovalObligation(
                name=BLOG_PERSONAL_DATA,
                purge_action=RemovalAction.SKIP,
                anonymize_action=RemovalAction.ANONYMIZE,
            ),
        )

    def anonymize_account(
        self,
        user: Any,
        original_email: str,
        original_name: str,
        original_username: str,
    ) -> None:
        """Clear the author profile as blog's declared ``ANONYMIZE`` executor."""
        from quickscale_modules_blog import _anonymization

        _anonymization.anonymize_account(
            user, original_email, original_name, original_username
        )

    def anonymize_handlers(self) -> tuple[Any, ...]:
        """Declare blog's account-anonymization handler (rule 4).

        The anonymize boundary collects every installed app's declared handler
        through the shared core helper and runs them in one transaction; blog
        declares its own app config as its handler.
        """
        return (self,)

    def personal_data_declarations(
        self,
    ) -> tuple[PersonalDataField | PersonalDataExclusion, ...]:
        """Declare the personal-data rows blog owns (rule 49).

        The profile's user link is retained while its bio and stored avatar are
        cleared; posts and uploaded media belong to the organization and stay
        attributed to the disabled account.  Organization editorial content and
        organization-owned media files are excluded with their reasons.
        """
        return (
            PersonalDataField(
                app_label=self.label,
                model_name="AuthorProfile",
                field_name="user",
                treatment=PersonalDataTreatment.KEEP_LINK,
                note="Profile row stays; its bio and avatar are cleared.",
            ),
            PersonalDataField(
                app_label=self.label,
                model_name="AuthorProfile",
                field_name="bio",
                treatment=PersonalDataTreatment.SCRUB,
                note="Blanked.",
            ),
            PersonalDataField(
                app_label=self.label,
                model_name="AuthorProfile",
                field_name="avatar",
                treatment=PersonalDataTreatment.DELETE_FILE,
                note="Stored file deleted on commit and the field cleared.",
            ),
            PersonalDataField(
                app_label=self.label,
                model_name="Post",
                field_name="author",
                treatment=PersonalDataTreatment.KEEP_LINK,
                note="Post stays attributed to the deleted user.",
            ),
            PersonalDataField(
                app_label=self.label,
                model_name="BlogMediaAsset",
                field_name="uploaded_by",
                treatment=PersonalDataTreatment.KEEP_LINK,
                note="Media stays attributed to the deleted user.",
            ),
            PersonalDataExclusion(
                app_label=self.label,
                model_name="Post",
                field_name="content",
                reason="Organization editorial content authored by the user; retained as-is.",
            ),
            PersonalDataExclusion(
                app_label=self.label,
                model_name="Post",
                field_name="excerpt",
                reason="Organization editorial content authored by the user; retained as-is.",
            ),
            PersonalDataExclusion(
                app_label=self.label,
                model_name="Post",
                field_name="featured_image",
                reason="Organization-owned post image; retained as-is.",
            ),
            PersonalDataExclusion(
                app_label=self.label,
                model_name="BlogMediaAsset",
                field_name="file",
                reason="Organization-owned media file; retained as-is.",
            ),
        )

    def ready(self) -> None:
        """Run the blog startup checks through the shared helpers."""
        # Late import: keep the app config importable while Django is still
        # populating the app registry.
        from quickscale_modules_blog.checks import RETIRED_SETTINGS, check_media_url

        register_module_checks(self, [check_media_url])
        register_module_settings_check(self, "blog", retired_settings=RETIRED_SETTINGS)
