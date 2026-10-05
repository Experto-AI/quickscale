"""Runtime billing services for the QuickScale billing module.

The implementation lives in private sibling modules grouped by concern
(``_settings``, ``_checkout``, ``_webhooks``, ...); this module owns the public
service surface and the Stripe webhook entry point, re-exports public names for
unchanged import paths, and resolves collaborators through the sibling modules
that define them (decisions.md, Split-Facade Seams).
"""

from __future__ import annotations

import logging
from typing import Any

import quickscale_modules_billing._locks as _locks
import quickscale_modules_billing.models as _models
import quickscale_modules_billing._payload as _payload
import quickscale_modules_billing._settings as _settings
import quickscale_modules_billing._stripe_client as _stripe_client
import quickscale_modules_billing._webhooks as _webhooks
import quickscale_modules_billing.exceptions as _exceptions

from quickscale_modules_billing._checkout import (
    create_billing_portal_session as create_billing_portal_session,
    create_checkout_session as create_checkout_session,
)
from quickscale_modules_billing._credits import (
    credit_user as credit_user,
    debit_user as debit_user,
)
from quickscale_modules_billing._customers import (
    get_or_create_stripe_customer as get_or_create_stripe_customer,
)
from quickscale_modules_billing._locks import (
    subscription_provider_mutation_lock as subscription_provider_mutation_lock,
)
from quickscale_modules_billing._removal import (
    account_deletion_user_reference_organization_ids as account_deletion_user_reference_organization_ids,
    guard_organization_removal_provider_state as guard_organization_removal_provider_state,
    reconcile_purchase_checkouts_for_removal as reconcile_purchase_checkouts_for_removal,
)
from quickscale_modules_billing._settings import (
    BillingSettingsSnapshot as BillingSettingsSnapshot,
    STRIPE_API_VERSION as STRIPE_API_VERSION,
    STRIPE_EVENT_TYPE_CHECKOUT_SESSION_COMPLETED as STRIPE_EVENT_TYPE_CHECKOUT_SESSION_COMPLETED,
    STRIPE_EVENT_TYPE_CHECKOUT_SESSION_EXPIRED as STRIPE_EVENT_TYPE_CHECKOUT_SESSION_EXPIRED,
    STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_CREATED as STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_CREATED,
    STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_DELETED as STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_DELETED,
    STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_UPDATED as STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_UPDATED,
    STRIPE_EVENT_TYPE_INVOICE_PAID as STRIPE_EVENT_TYPE_INVOICE_PAID,
    STRIPE_EVENT_TYPE_INVOICE_PAYMENT_FAILED as STRIPE_EVENT_TYPE_INVOICE_PAYMENT_FAILED,
    StripeWebhookResult as StripeWebhookResult,
    SubscriptionCancellationTransition as SubscriptionCancellationTransition,
    SubscriptionCheckoutReconciliation as SubscriptionCheckoutReconciliation,
    SubscriptionProviderIdentity as SubscriptionProviderIdentity,
    is_enabled as is_enabled,
    organization_pricing_page_url as organization_pricing_page_url,
    require_org_feature as require_org_feature,
)
from quickscale_modules_billing._stripe_client import (
    StripeClient as StripeClient,
    get_stripe_client as get_stripe_client,
)
from quickscale_modules_billing._subscription_checkout import (
    create_subscription_checkout_session as create_subscription_checkout_session,
    reconcile_account_deletion_subscription_checkout as reconcile_account_deletion_subscription_checkout,
    reconcile_elapsed_subscription_checkout as reconcile_elapsed_subscription_checkout,
    reconcile_organization_removal_subscription_checkout as reconcile_organization_removal_subscription_checkout,
)
from quickscale_modules_billing._subscription_mutations import (
    cancel_current_subscription as cancel_current_subscription,
    resume_current_subscription as resume_current_subscription,
)
from quickscale_modules_billing.exceptions import (
    BillingConfigurationError as BillingConfigurationError,
    BillingDisabledError as BillingDisabledError,
    BillingError as BillingError,
    BillingSubscriptionAnomalyError as BillingSubscriptionAnomalyError,
    BillingValidationError as BillingValidationError,
    BillingWebhookError as BillingWebhookError,
    BillingWebhookSignatureError as BillingWebhookSignatureError,
    InsufficientCreditsError as InsufficientCreditsError,
    OrgSelectionRequiredError as OrgSelectionRequiredError,
)


logger = logging.getLogger(__name__)


@_stripe_client._translate_stripe_errors("Stripe webhook handling failed.")
def handle_stripe_event(
    *,
    body: bytes,
    signature: str,
    stripe_client: Any | None = None,
    settings_snapshot: _settings.BillingSettingsSnapshot | None = None,
) -> _settings.StripeWebhookResult:
    """Verify, record, and handle a Stripe webhook event idempotently."""
    snapshot = settings_snapshot or _settings.BillingSettingsSnapshot.from_settings()
    _settings._ensure_billing_enabled(snapshot)

    webhook_secret = snapshot.resolve_webhook_secret()
    if not webhook_secret:
        raise _exceptions.BillingConfigurationError(
            "Stripe webhook secret is not configured in the runtime settings."
        )

    resolved_client = stripe_client or _stripe_client.get_stripe_client(
        settings_snapshot=snapshot
    )
    event_payload = resolved_client.construct_event(
        body=body,
        signature=signature,
        webhook_secret=webhook_secret,
    )
    event_id = str(event_payload.get("id") or "").strip()
    event_type = str(event_payload.get("type") or "").strip()
    if not event_id:
        raise _exceptions.BillingWebhookError("Stripe event payload is missing an id.")
    if not event_type:
        raise _exceptions.BillingWebhookError("Stripe event payload is missing a type.")

    event_api_version = str(event_payload.get("api_version") or "").strip()
    logger.info(
        "Stripe webhook event %s reports API version %s.",
        event_id,
        event_api_version or "<blank>",
    )
    if _payload._stripe_named_release(
        event_api_version
    ) != _payload._stripe_named_release(_settings.STRIPE_API_VERSION):
        raise _exceptions.BillingConfigurationError(
            f"Stripe webhook event API version {event_api_version or '<blank>'} does "
            f"not match the required Stripe API version {_settings.STRIPE_API_VERSION}; "
            f"recreate the webhook endpoint at {_settings.STRIPE_API_VERSION}."
        )

    with _locks._webhook_event_processing_lock(event_id):
        webhook_event, _ = _models.WebhookEvent.objects.get_or_create(
            stripe_event_id=event_id,
            defaults={
                "event_type": event_type,
                "payload": event_payload,
            },
        )
        return _webhooks._process_verified_stripe_event(
            webhook_event=webhook_event,
            event_payload=event_payload,
            event_type=event_type,
            stripe_client=resolved_client,
        )


__all__ = [
    "account_deletion_user_reference_organization_ids",
    "cancel_current_subscription",
    "BillingConfigurationError",
    "BillingDisabledError",
    "BillingError",
    "BillingSubscriptionAnomalyError",
    "BillingValidationError",
    "BillingWebhookError",
    "BillingWebhookSignatureError",
    "debit_user",
    "StripeClient",
    "StripeWebhookResult",
    "SubscriptionCancellationTransition",
    "create_billing_portal_session",
    "create_checkout_session",
    "create_subscription_checkout_session",
    "credit_user",
    "get_or_create_stripe_customer",
    "get_stripe_client",
    "guard_organization_removal_provider_state",
    "handle_stripe_event",
    "InsufficientCreditsError",
    "is_enabled",
    "organization_pricing_page_url",
    "OrgSelectionRequiredError",
    "resume_current_subscription",
    "reconcile_account_deletion_subscription_checkout",
    "reconcile_organization_removal_subscription_checkout",
    "reconcile_purchase_checkouts_for_removal",
    "require_org_feature",
    "subscription_provider_mutation_lock",
]
