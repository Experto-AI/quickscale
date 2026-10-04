"""Django app configuration for QuickScale notifications."""

from typing import Any

from django.apps import AppConfig

from quickscale_core.runtime import (
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
        stay importable without ``orgs``, so the account-deletion boundary
        collects this handler through the shared core capability helper.
        """
        from quickscale_modules_notifications import _anonymization

        _anonymization.anonymize_account(
            user, original_email, original_name, original_username
        )

    def anonymize_handlers(self) -> tuple[Any, ...]:
        """Declare notifications' account-anonymization handler (rule 4).

        The declaration uses no other module: the account-deletion boundary
        collects it through ``quickscale_core.runtime``, so notifications
        stays independent of ``orgs``.
        """
        return (self,)

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
