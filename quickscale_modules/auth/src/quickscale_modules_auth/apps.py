"""Django app configuration for QuickScale auth module.

Startup configuration is validated by rule 3's generic settings check,
registered through ``quickscale_core.runtime`` from ``ready()``.
"""

from importlib import import_module
from typing import Any

from django.apps import AppConfig

from quickscale_core.runtime import register_module_settings_check
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

        The account-deletion boundary disables and scrubs the account; the
        ``ANONYMIZE`` action names auth's ``anonymize_account`` executor.  An
        organization purge never touches accounts, so that boundary skips it.
        """
        return (
            OrganizationRemovalObligation(
                name=AUTH_PERSONAL_DATA,
                purge_action=RemovalAction.SKIP,
                account_delete_action=RemovalAction.ANONYMIZE,
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

        The account-deletion boundary collects every installed app's declared
        handler through the shared core helper and runs them in one
        transaction; auth declares its own app config as its handler.
        """
        return (self,)

    def removal_boundary_implementations(
        self,
    ) -> dict[RemovalBoundary, tuple[str, str, str]]:
        """Declare auth's account-deletion boundary implementation (rule 34).

        Auth owns the account-deletion boundary, so it declares where that
        implementation lives instead of orgs' discharge check naming it.
        """
        return {
            RemovalBoundary.ACCOUNT_DELETE: (
                self.name,
                "quickscale_modules_auth.views",
                "AccountDeleteView.form_valid",
            ),
        }

    def ready(self) -> None:
        register_module_settings_check(self, "auth")

        # Import signal receivers when app is ready
        import_module("quickscale_modules_auth.receivers")
