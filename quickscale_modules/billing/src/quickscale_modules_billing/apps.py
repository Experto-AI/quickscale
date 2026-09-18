"""Django app configuration for QuickScale billing.

SA17.2 — fail-hard billing enabled-flag setting: requires
``QUICKSCALE_BILLING_ENABLED`` in Django settings at startup
instead of silently defaulting to ``True``.
"""

from typing import Any

from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class QuickscaleBillingConfig(AppConfig):
    """Configuration for the QuickScale billing module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_billing"
    label = "quickscale_modules_billing"
    verbose_name = "QuickScale Billing"

    def reconcile_organization_removal_provider_state(
        self,
        organization_id: Any,
        *,
        persist: bool,
    ) -> str:
        """Inspect checkout state before orgs opens its purge transaction."""
        from quickscale_modules_billing.services import (
            reconcile_purchase_checkouts_for_removal,
            reconcile_organization_removal_subscription_checkout,
        )

        reconcile_purchase_checkouts_for_removal(
            organization_id,
            persist=persist,
        )
        result = reconcile_organization_removal_subscription_checkout(
            organization_id,
            persist=persist,
        )
        if result.provider_status == "expired":
            return result.checkout_session_id
        return ""

    def reconcile_account_deletion_provider_state(
        self,
        organization_id: Any,
    ) -> None:
        """Require hosted checkout state to be terminal before owner deletion."""
        from quickscale_modules_billing.services import (
            reconcile_account_deletion_subscription_checkout,
        )

        reconcile_account_deletion_subscription_checkout(organization_id)

    def reconcile_account_deletion_purchase_provider_state(
        self,
        organization_id: Any,
        user_id: Any,
    ) -> None:
        """Require one user's purchase Checkouts to be terminal before deletion."""
        from quickscale_modules_billing.services import (
            reconcile_purchase_checkouts_for_removal,
        )

        reconcile_purchase_checkouts_for_removal(
            organization_id,
            user_id=user_id,
            persist=True,
        )

    def organization_removal_provider_mutation_lock(self, organization_id: Any) -> Any:
        """Return the billing provider mutex shared with Checkout creation."""
        from quickscale_modules_billing.services import (
            subscription_provider_mutation_lock,
        )

        return subscription_provider_mutation_lock(organization_id)

    def detach_account_deletion_user_references(
        self,
        user_id: Any,
        organization_ids: list[Any],
    ) -> int:
        """Clear billing provenance before Django deletes the referenced user."""
        from quickscale_modules_billing.services import (
            detach_account_deletion_user_references,
        )

        return detach_account_deletion_user_references(user_id, organization_ids)

    def account_deletion_user_reference_organization_ids(
        self,
        user_id: Any,
    ) -> list[Any]:
        """Return orgs that retain billing provenance for account deletion."""
        from quickscale_modules_billing.services import (
            account_deletion_user_reference_organization_ids,
        )

        return account_deletion_user_reference_organization_ids(user_id)

    def ready(self) -> None:
        # ---- SA17.2 — fail-hard billing enabled-flag setting -------------
        # Every generated project must explicitly set this; no silent
        # fallback that enables billing when the setting is absent.
        if not hasattr(settings, "QUICKSCALE_BILLING_ENABLED"):
            raise ImproperlyConfigured(
                "The QUICKSCALE_BILLING_ENABLED setting is required. "
                "Set it to True or False in your Django settings."
            )
