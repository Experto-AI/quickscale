"""Django app configuration for QuickScale billing.

SA17.2 — fail-hard billing enabled-flag setting: requires
``QUICKSCALE_BILLING_ENABLED`` in Django settings at startup
instead of silently defaulting to ``True``.
"""

from collections.abc import Callable
from typing import Any

from django.apps import AppConfig

from quickscale_core.runtime import (
    register_module_checks,
    register_module_settings_check,
)
from quickscale_modules_orgs.removal import (
    BILLING_PERSONAL_DATA,
    BILLING_PROVIDER_STATE,
    BoundaryGuardedHooks,
    ExternalProviderField,
    OrganizationRemovalObligation,
    RemovalAction,
)


class QuickscaleBillingConfig(AppConfig):
    """Configuration for the QuickScale billing module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_billing"
    label = "quickscale_billing"
    verbose_name = "QuickScale Billing"

    def removal_obligations(self) -> tuple[OrganizationRemovalObligation, ...]:
        """Declare billing's organization-removal obligations.

        Billing owns the Stripe identifiers it writes — including the Stripe
        customer id it stores on the organization row — so the declaration
        lives here rather than in vendored ``orgs`` source. Purge refuses
        while provider state is live and account deletion reconciles it.  A
        second obligation owns the stored webhook payloads, whose customer
        email and name the account anonymization redacts in place.
        """
        return (
            OrganizationRemovalObligation(
                name=BILLING_PROVIDER_STATE,
                purge_action=RemovalAction.REFUSE,
                account_delete_action=RemovalAction.RECONCILE,
                # Billing's purge refusal is decided by its own guards in the
                # purge command (live subscription, pending checkout), not by a
                # populated identifier, so every field is declared
                # boundary-guarded rather than value-refused; a stale Stripe
                # identifier must not block a purge.
                external_provider_fields=(
                    ExternalProviderField(
                        "quickscale_billing.credittransaction",
                        "stripe_event_id",
                        boundary_guarded=True,
                    ),
                    ExternalProviderField(
                        "quickscale_billing.credittransaction",
                        "stripe_object_id",
                        boundary_guarded=True,
                    ),
                    ExternalProviderField(
                        "quickscale_billing.credittransaction",
                        "stripe_reference_data",
                        structured_keys=(
                            "charge_id",
                            "checkout_session_id",
                            "credit_grant_id",
                            "invoice_id",
                            "payment_intent_id",
                            "stripe_customer_id",
                            "stripe_price_id",
                            "stripe_subscription_id",
                        ),
                        boundary_guarded=True,
                    ),
                    ExternalProviderField(
                        "quickscale_billing.purchasecheckout",
                        "stripe_checkout_session_id",
                        boundary_guarded=True,
                    ),
                    ExternalProviderField(
                        "quickscale_billing.subscription",
                        "stripe_subscription_id",
                        boundary_guarded=True,
                    ),
                    ExternalProviderField(
                        "quickscale_billing.subscription",
                        "stripe_customer_id",
                        boundary_guarded=True,
                    ),
                    ExternalProviderField(
                        "quickscale_billing.subscription",
                        "stripe_checkout_session_id",
                        boundary_guarded=True,
                    ),
                    ExternalProviderField(
                        "quickscale_orgs.organization",
                        "stripe_customer_id",
                        boundary_guarded=True,
                    ),
                ),
                # Billing ships the hooks its guarded fields name, so the purge
                # boundary runs billing's own provider-state code and names no
                # billing label: a pre-transaction reconciliation, the provider
                # mutex held across it, and the in-transaction refusal guard.
                boundary_guarded_hooks=BoundaryGuardedHooks(
                    guard="guard_organization_removal_provider_state",
                    reconcile="reconcile_organization_removal_provider_state",
                    mutation_lock="organization_removal_provider_mutation_lock",
                ),
            ),
            OrganizationRemovalObligation(
                name=BILLING_PERSONAL_DATA,
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
        """Redact stored provider payloads as billing's declared executor."""
        from quickscale_modules_billing import _anonymization

        _anonymization.anonymize_account(
            user, original_email, original_name, original_username
        )

    def anonymize_handlers(self) -> tuple[Any, ...]:
        """Declare billing's account-anonymization handler (rule 4).

        The account-deletion boundary collects every installed app's declared
        handler through the shared core helper and runs them in one
        transaction; billing declares its own app config as its handler.
        """
        return (self,)

    def reconcile_organization_removal_provider_state(
        self,
        organization_id: Any,
        *,
        persist: bool,
    ) -> str:
        """Inspect checkout state before orgs opens its purge transaction."""
        from quickscale_modules_billing._removal import (
            reconcile_purchase_checkouts_for_removal,
        )
        from quickscale_modules_billing._subscription_checkout import (
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
        from quickscale_modules_billing._subscription_checkout import (
            reconcile_account_deletion_subscription_checkout,
        )

        reconcile_account_deletion_subscription_checkout(organization_id)

    def reconcile_account_deletion_purchase_provider_state(
        self,
        organization_id: Any,
        user_id: Any,
    ) -> None:
        """Require one user's purchase Checkouts to be terminal before deletion."""
        from quickscale_modules_billing._removal import (
            reconcile_purchase_checkouts_for_removal,
        )

        reconcile_purchase_checkouts_for_removal(
            organization_id,
            user_id=user_id,
            persist=True,
        )

    def organization_removal_provider_mutation_lock(self, organization_id: Any) -> Any:
        """Return the billing provider mutex shared with Checkout creation."""
        from quickscale_modules_billing._locks import (
            subscription_provider_mutation_lock,
        )

        return subscription_provider_mutation_lock(organization_id)

    def guard_organization_removal_provider_state(
        self,
        organization: Any,
        *,
        provider_expired_checkout_id: str = "",
    ) -> str:
        """Return billing's purge refusal for live provider state, or an empty string."""
        from quickscale_modules_billing._removal import (
            guard_organization_removal_provider_state as guard,
        )

        return guard(
            organization,
            provider_expired_checkout_id=provider_expired_checkout_id,
        )

    def detach_account_deletion_user_references(
        self,
        user_id: Any,
        organization_ids: list[Any],
    ) -> int:
        """Clear billing provenance before Django deletes the referenced user."""
        from quickscale_modules_billing._removal import (
            detach_account_deletion_user_references,
        )

        return detach_account_deletion_user_references(
            user_id,
            organization_ids=organization_ids,
        )

    def account_deletion_user_reference_organization_ids(
        self,
        user_id: Any,
    ) -> list[Any]:
        """Return orgs that retain billing provenance for account deletion."""
        from quickscale_modules_billing._removal import (
            account_deletion_user_reference_organization_ids,
        )

        return account_deletion_user_reference_organization_ids(user_id)

    def organization_pricing_url_hooks(
        self,
    ) -> tuple[Callable[[Any], str | None], ...]:
        """Declare billing's pricing page for the org-creation handoff (rule 4).

        The orgs create flow collects this capability and uses the first
        declared URL as its post-create handoff, so no consumer names
        billing's route, label, or settings.  A switched-off billing declares
        nothing: its public pages answer as disabled (rule 1), so the
        consumer keeps its own fallback page.
        """
        from django.conf import settings

        if not bool(settings.QUICKSCALE_BILLING_ENABLED):
            return ()
        from quickscale_modules_billing._settings import organization_pricing_page_url

        return (organization_pricing_page_url,)

    def account_deletion_handlers(self) -> tuple[Any, ...]:
        """Declare billing's account-deletion handler (Module Conventions rule 4).

        Account deletion collects every installed app's declared handler and
        drives billing's provider reconciliation, subscription cancellation
        with compensation, and provenance detachment through it, so no consumer
        needs billing's label or service imports.  Billing declares its own app
        config as the handler: the methods below are the handler surface.
        """
        return (self,)

    def account_deletion_handled_app_labels(self) -> tuple[str, ...]:
        """Return the app labels whose account-deletion state this handler owns."""
        return (self.label,)

    def account_deletion_fail_closed_errors(self) -> tuple[type[BaseException], ...]:
        """Return the error types that must fail account deletion closed.

        A handler raises these for provider states that block account
        deletion; any other exception is unexpected and propagates instead of
        being masked as a user-facing block.
        """
        from quickscale_modules_billing.exceptions import BillingError

        return (BillingError,)

    def account_deletion_reconcile_scope(self) -> str:
        """Return the organization scope billing reconciles before deletion.

        ``cancellation``: billing reconciles an organization's subscription
        checkout only where this deletion cancels its subscription, because a
        retained organization's open checkout is not this user's to resolve.
        A handler declaring ``touched`` is reconciled for every organization
        the deletion touches.
        """
        return "cancellation"

    def account_deletion_subscription_mutation_lock(
        self,
        organization_id: Any,
    ) -> Any:
        """Return the provider mutex held while account deletion mutates state."""
        from quickscale_modules_billing._locks import (
            subscription_provider_mutation_lock,
        )

        return subscription_provider_mutation_lock(organization_id)

    def cancel_account_deletion_subscription(
        self,
        user: Any,
        organization: Any,
    ) -> Any:
        """Cancel one organization's subscription, capturing the transition."""
        from quickscale_modules_billing._subscription_mutations import (
            cancel_current_subscription,
        )

        return cancel_current_subscription(
            user,
            organization=organization,
            capture_transition=True,
        )

    def resume_account_deletion_subscription(
        self,
        user: Any,
        organization: Any,
        transition: Any,
    ) -> Any:
        """Restore a captured cancellation when account deletion is rejected."""
        from quickscale_modules_billing._subscription_mutations import (
            resume_current_subscription,
        )

        return resume_current_subscription(
            user,
            organization=organization,
            transition=transition,
        )

    def ready(self) -> None:
        # Late import: checks.py reads the billing settings snapshot, which
        # touches models, so it must load after the app registry is ready.
        from quickscale_modules_billing.checks import check_billing_settings

        # Rule 3 first: a missing or invalid declared setting is reported by
        # the generic check before the runtime check reads it.
        register_module_settings_check(self, "billing")
        register_module_checks(self, [check_billing_settings])
