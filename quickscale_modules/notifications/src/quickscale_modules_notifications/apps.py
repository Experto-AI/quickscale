"""Django app configuration for QuickScale notifications."""

from typing import Any

from django.apps import AppConfig

from quickscale_core.runtime import (
    PersonalDataExclusion,
    PersonalDataField,
    PersonalDataTreatment,
    register_module_checks,
    register_module_settings_check,
)


class QuickscaleNotificationsConfig(AppConfig):
    """Configuration for the QuickScale notifications module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_notifications"
    label = "quickscale_notifications"
    verbose_name = "QuickScale Notifications"

    def anonymize_account(
        self,
        user: Any,
        original_email: str,
        original_name: str,
        original_username: str,
    ) -> None:
        """Scrub the person's notification records as the declared executor.

        Notifications declares no organization-removal obligation: it must
        stay importable without ``orgs``, so the anonymize boundary
        collects this handler through the shared core capability helper.
        """
        from quickscale_modules_notifications import _anonymization

        _anonymization.anonymize_account(
            user, original_email, original_name, original_username
        )

    def anonymize_handlers(self) -> tuple[Any, ...]:
        """Declare notifications' account-anonymization handler (rule 4).

        The declaration uses no other module: the anonymize boundary
        collects it through ``quickscale_core.runtime``, so notifications
        stays independent of ``orgs``.
        """
        return (self,)

    def personal_data_declarations(
        self,
    ) -> tuple[PersonalDataField | PersonalDataExclusion, ...]:
        """Declare the personal-data rows notifications owns (rule 49).

        Rendered messages, delivery records, and stored provider payloads can
        echo the recipient or an actor identity, so they are scrubbed; the
        organization's sender and reply-to configuration is excluded.  The
        records live in core, so notifications declares them without importing
        ``orgs``.
        """
        return (
            PersonalDataField(
                app_label=self.label,
                model_name="NotificationMessage",
                field_name="subject",
                treatment=PersonalDataTreatment.SCRUB,
                note="Rendered subject replaced with a redacted placeholder.",
            ),
            PersonalDataField(
                app_label=self.label,
                model_name="NotificationMessage",
                field_name="rendered_text",
                treatment=PersonalDataTreatment.SCRUB,
                note="Rendered body replaced with a redacted placeholder.",
            ),
            PersonalDataField(
                app_label=self.label,
                model_name="NotificationMessage",
                field_name="rendered_html",
                treatment=PersonalDataTreatment.SCRUB,
                note="Rendered body replaced with a redacted placeholder.",
            ),
            PersonalDataField(
                app_label=self.label,
                model_name="NotificationMessage",
                field_name="context_json",
                treatment=PersonalDataTreatment.SCRUB,
                note="Rendered context replaced with a redacted placeholder.",
            ),
            PersonalDataField(
                app_label=self.label,
                model_name="NotificationMessage",
                field_name="last_error",
                treatment=PersonalDataTreatment.SCRUB,
                note="Provider error text can echo the address; redacted.",
            ),
            PersonalDataField(
                app_label=self.label,
                model_name="NotificationDelivery",
                field_name="failure_reason",
                treatment=PersonalDataTreatment.SCRUB,
                note="Provider error text can echo the address; redacted.",
            ),
            PersonalDataField(
                app_label=self.label,
                model_name="NotificationDelivery",
                field_name="recipient_email",
                treatment=PersonalDataTreatment.SCRUB,
                note="Address scrubbed; status is kept for delivery statistics.",
            ),
            PersonalDataField(
                app_label=self.label,
                model_name="NotificationDeliveryEvent",
                field_name="payload_json",
                treatment=PersonalDataTreatment.SCRUB,
                note="Stored provider payload carries the recipient; the address is redacted.",
            ),
            PersonalDataExclusion(
                app_label=self.label,
                model_name="NotificationSettings",
                field_name="sender_email",
                reason="Organization sender configuration, not the user's address.",
            ),
            PersonalDataExclusion(
                app_label=self.label,
                model_name="NotificationSettings",
                field_name="reply_to_email",
                reason="Organization reply-to configuration, not the user's address.",
            ),
        )

    def ready(self) -> None:
        # Late import: checks.py reads the notifications settings snapshot,
        # which touches models, so it must load after the app registry is ready.
        from quickscale_modules_notifications.checks import check_vendor_secrets

        # Rule 3 first: a missing or invalid declared setting is reported by
        # the generic check before the runtime checks read it.
        register_module_settings_check(self, "notifications")
        register_module_checks(
            self,
            [check_vendor_secrets],
        )
