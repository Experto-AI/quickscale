"""Django app configuration for QuickScale auth module.

Startup configuration is validated by rule 3's generic settings check,
registered through ``quickscale_core.runtime`` from ``ready()``.
"""

from importlib import import_module
from typing import Any

from django.apps import AppConfig

from quickscale_core.runtime import (
    PersonalDataExclusion,
    PersonalDataField,
    PersonalDataTreatment,
    register_module_settings_check,
)
from quickscale_modules_orgs.removal import (
    AUTH_PERSONAL_DATA,
    OrganizationRemovalObligation,
    RemovalAction,
    RemovalBoundary,
)


class QuickscaleAuthConfig(AppConfig):
    """Configuration for QuickScale authentication module"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_auth"
    label = "quickscale_auth"
    verbose_name = "QuickScale Authentication"

    def removal_obligations(
        self,
    ) -> tuple[OrganizationRemovalObligation, ...]:
        """Declare the account's personal data as auth's own obligation.

        The anonymize boundary disables and scrubs the account; the
        ``ANONYMIZE`` action names auth's ``anonymize_account`` executor.  An
        organization purge never touches accounts, so that boundary skips it.
        """
        return (
            OrganizationRemovalObligation(
                name=AUTH_PERSONAL_DATA,
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
        """Scrub the account row as auth's declared ``ANONYMIZE`` executor."""
        from quickscale_modules_auth import _anonymization

        _anonymization.scrub_account(
            user, original_email, original_name, original_username
        )

    def anonymize_handlers(self) -> tuple[Any, ...]:
        """Declare auth's account-anonymization handler (rule 4).

        The anonymize boundary collects every installed app's declared handler
        through the shared core helper and runs them in one transaction; auth
        declares its own app config as its handler.
        """
        return (self,)

    def personal_data_declarations(
        self,
    ) -> tuple[PersonalDataField | PersonalDataExclusion, ...]:
        """Declare the personal-data rows auth owns (rule 49).

        The account is disabled and scrubbed, never deleted, so all six
        identity fields are scrubbed; the auto-created permission through
        tables hold only the FK pair and are excluded.  allauth's
        ``account`` addresses and the person's ``sessions`` rows are declared
        centrally with ``orgs`` because only ``auth``'s scrub deletes them.
        """
        return (
            PersonalDataField(
                app_label=self.label,
                model_name="User",
                field_name="username",
                treatment=PersonalDataTreatment.SCRUB,
                note="Replaced with 'deleted-<id>'.",
            ),
            PersonalDataField(
                app_label=self.label,
                model_name="User",
                field_name="email",
                treatment=PersonalDataTreatment.SCRUB,
                note="Replaced with 'deleted-<id>@invalid' so the address can register again.",
            ),
            PersonalDataField(
                app_label=self.label,
                model_name="User",
                field_name="first_name",
                treatment=PersonalDataTreatment.SCRUB,
                note="Blanked.",
            ),
            PersonalDataField(
                app_label=self.label,
                model_name="User",
                field_name="last_name",
                treatment=PersonalDataTreatment.SCRUB,
                note="Blanked.",
            ),
            PersonalDataField(
                app_label=self.label,
                model_name="User",
                field_name="password",
                treatment=PersonalDataTreatment.SCRUB,
                note="Set unusable; the same handler turns is_active off.",
            ),
            PersonalDataField(
                app_label=self.label,
                model_name="User",
                field_name="last_login",
                treatment=PersonalDataTreatment.SCRUB,
                note="Cleared.",
            ),
            PersonalDataExclusion(
                app_label=self.label,
                model_name="User_groups",
                field_name="user",
                reason="Auto-created M2M through table for User.groups; holds the FK pair only.",
            ),
            PersonalDataExclusion(
                app_label=self.label,
                model_name="User_user_permissions",
                field_name="user",
                reason="Auto-created M2M through table for User.user_permissions; FK pair only.",
            ),
        )

    def removal_boundary_implementations(
        self,
    ) -> dict[RemovalBoundary, tuple[str, str, str]]:
        """Declare auth's anonymize boundary implementation (rule 34).

        Auth owns the anonymize boundary, so it declares where that
        implementation lives instead of orgs' discharge check naming it.
        """
        return {
            RemovalBoundary.ANONYMIZE: (
                self.name,
                "quickscale_modules_auth.views",
                "AccountDeleteView.form_valid",
            ),
        }

    def ready(self) -> None:
        register_module_settings_check(self, "auth")

        # Import signal receivers when app is ready
        import_module("quickscale_modules_auth.receivers")
