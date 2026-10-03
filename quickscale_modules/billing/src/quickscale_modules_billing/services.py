"""Runtime billing services for the QuickScale billing module.

The implementation lives in private sibling modules grouped by concern
(``_settings``, ``_checkout``, ``_webhooks``, ...); this module owns the
public service surface, the Stripe webhook entry point, and
``get_stripe_client``, and re-exports every name that previously lived
here (Module Conventions rule 28), so existing
``quickscale_modules_billing.services`` imports and test patch targets keep
working unchanged.
"""

from __future__ import annotations

from importlib import import_module
import logging
from typing import Any

from quickscale_modules_billing._checkout import (
    _create_checkout_session as _create_checkout_session,
    create_billing_portal_session as create_billing_portal_session,
    create_checkout_session as create_checkout_session,
)
from quickscale_modules_billing._credits import (
    _apply_locked_credit_balance_delta as _apply_locked_credit_balance_delta,
    _find_existing_credit_transaction as _find_existing_credit_transaction,
    _get_locked_credit_balance as _get_locked_credit_balance,
    _get_or_create_credit_balance as _get_or_create_credit_balance,
    _has_matching_business_reference as _has_matching_business_reference,
    credit_user as credit_user,
    debit_user as debit_user,
)
from quickscale_modules_billing._customers import (
    _resolve_authoritative_organization_customer_id as _resolve_authoritative_organization_customer_id,
    _resolve_organization_by_customer_id as _resolve_organization_by_customer_id,
    _resolve_organization_from_reference as _resolve_organization_from_reference,
    _resolve_user_from_reference as _resolve_user_from_reference,
    _sync_organization_customer_id as _sync_organization_customer_id,
    get_or_create_stripe_customer as get_or_create_stripe_customer,
)
from quickscale_modules_billing._locks import (
    _lock_organization_for_billing_mutation as _lock_organization_for_billing_mutation,
    _subscription_provider_mutation_lock_key as _subscription_provider_mutation_lock_key,
    _webhook_event_processing_lock as _webhook_event_processing_lock,
    _webhook_event_processing_lock_key as _webhook_event_processing_lock_key,
    subscription_provider_mutation_lock as subscription_provider_mutation_lock,
)
from quickscale_modules_billing._payload import (
    _build_checkout_session_metadata as _build_checkout_session_metadata,
    _build_customer_create_idempotency_key as _build_customer_create_idempotency_key,
    _build_customer_metadata as _build_customer_metadata,
    _build_purchase_checkout_create_idempotency_key as _build_purchase_checkout_create_idempotency_key,
    _build_subscription_checkout_create_idempotency_key as _build_subscription_checkout_create_idempotency_key,
    _checkout_session_metadata_is_complete as _checkout_session_metadata_is_complete,
    _dahlia_line_item_price_id as _dahlia_line_item_price_id,
    _display_name_for_user as _display_name_for_user,
    _extract_checkout_session_expires_at as _extract_checkout_session_expires_at,
    _extract_event_object as _extract_event_object,
    _extract_live_checkout_session_url as _extract_live_checkout_session_url,
    _extract_metadata_value as _extract_metadata_value,
    _extract_price_id as _extract_price_id,
    _extract_subscription_period_bounds as _extract_subscription_period_bounds,
    _extract_subscription_price_id as _extract_subscription_price_id,
    _invoice_subscription_details as _invoice_subscription_details,
    _invoice_subscription_id as _invoice_subscription_id,
    _map_stripe_subscription_status as _map_stripe_subscription_status,
    _normalize_integer as _normalize_integer,
    _normalize_mapping as _normalize_mapping,
    _organization_reference as _organization_reference,
    _purchase_checkout_pk_from_reference as _purchase_checkout_pk_from_reference,
    _purchase_checkout_reference as _purchase_checkout_reference,
    _resolve_purchase_checkout_reference as _resolve_purchase_checkout_reference,
    _resolve_subscription_checkout_reference as _resolve_subscription_checkout_reference,
    _string_field as _string_field,
    _stripe_named_release as _stripe_named_release,
    _stripe_object_id as _stripe_object_id,
    _stripe_timestamp_to_datetime as _stripe_timestamp_to_datetime,
    _subscription_checkout_pk_from_reference as _subscription_checkout_pk_from_reference,
    _subscription_checkout_reference as _subscription_checkout_reference,
    _user_reference as _user_reference,
    _validate_customer_search_reference as _validate_customer_search_reference,
)
from quickscale_modules_billing._removal import (
    account_deletion_user_reference_organization_ids as account_deletion_user_reference_organization_ids,
    detach_account_deletion_user_references as detach_account_deletion_user_references,
    guard_organization_removal_provider_state as guard_organization_removal_provider_state,
    reconcile_purchase_checkouts_for_removal as reconcile_purchase_checkouts_for_removal,
)
from quickscale_modules_billing._resolution import (
    _resolve_checkout_metadata_organizations as _resolve_checkout_metadata_organizations,
    _resolve_checkout_reservation_organization as _resolve_checkout_reservation_organization,
    _resolve_checkout_session_credit_amount as _resolve_checkout_session_credit_amount,
    _resolve_organization_for_checkout_session as _resolve_organization_for_checkout_session,
    _resolve_organization_for_invoice as _resolve_organization_for_invoice,
    _resolve_organization_for_subscription as _resolve_organization_for_subscription,
    _resolve_organization_from_metadata_sources as _resolve_organization_from_metadata_sources,
    _resolve_plan_for_checkout_session as _resolve_plan_for_checkout_session,
    _resolve_plan_for_subscription_payload as _resolve_plan_for_subscription_payload,
    _resolve_subscription_for_runtime_event as _resolve_subscription_for_runtime_event,
    _resolve_user_for_checkout_session as _resolve_user_for_checkout_session,
    _resolve_user_for_invoice as _resolve_user_for_invoice,
    _resolve_user_for_subscription as _resolve_user_for_subscription,
    _resolve_user_from_metadata_sources as _resolve_user_from_metadata_sources,
    _retrieve_checkout_payment_intent_payload as _retrieve_checkout_payment_intent_payload,
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
    _BUSINESS_OBJECT_REFERENCE_KEYS as _BUSINESS_OBJECT_REFERENCE_KEYS,
    _CREDITABLE_INVOICE_BILLING_REASONS as _CREDITABLE_INVOICE_BILLING_REASONS,
    _CURRENT_RECURRING_SUBSCRIPTION_ERROR as _CURRENT_RECURRING_SUBSCRIPTION_ERROR,
    _CUSTOMER_SEARCH_REFERENCE_UNSAFE_CHARACTERS as _CUSTOMER_SEARCH_REFERENCE_UNSAFE_CHARACTERS,
    _INVOICE_REFERENCE_KEYS as _INVOICE_REFERENCE_KEYS,
    _ORG_REFERENCE_METADATA_KEY as _ORG_REFERENCE_METADATA_KEY,
    _PLAN_CREDITS_METADATA_KEY as _PLAN_CREDITS_METADATA_KEY,
    _PLAN_INTERVAL_METADATA_KEY as _PLAN_INTERVAL_METADATA_KEY,
    _PLAN_SLUG_METADATA_KEY as _PLAN_SLUG_METADATA_KEY,
    _PRICE_ID_METADATA_KEY as _PRICE_ID_METADATA_KEY,
    _PURCHASE_CHECKOUT_REFERENCE_METADATA_KEY as _PURCHASE_CHECKOUT_REFERENCE_METADATA_KEY,
    _STRIPE_RECURRING_INTERVAL_BY_PLAN_INTERVAL as _STRIPE_RECURRING_INTERVAL_BY_PLAN_INTERVAL,
    _STRIPE_TO_LOCAL_SUBSCRIPTION_STATUS as _STRIPE_TO_LOCAL_SUBSCRIPTION_STATUS,
    _SUBSCRIPTION_CHECKOUT_REFERENCE_METADATA_KEY as _SUBSCRIPTION_CHECKOUT_REFERENCE_METADATA_KEY,
    _USER_METADATA_KEY as _USER_METADATA_KEY,
    _ensure_billing_enabled as _ensure_billing_enabled,
    _get_active_org_subscription as _get_active_org_subscription,
    is_enabled as is_enabled,
    organization_pricing_page_url as organization_pricing_page_url,
    require_org_feature as require_org_feature,
)
from quickscale_modules_billing._stripe_client import (
    P as P,
    R as R,
    StripeClient as StripeClient,
    _stripe_error_classes as _stripe_error_classes,
    _translate_stripe_errors as _translate_stripe_errors,
)
from quickscale_modules_billing._subscription_checkout import (
    _create_subscription_checkout_session as _create_subscription_checkout_session,
    _create_subscription_reservation as _create_subscription_reservation,
    _expire_subscription_reservation as _expire_subscription_reservation,
    _prepare_subscription_checkout_reservation as _prepare_subscription_checkout_reservation,
    _reconcile_subscription_checkout as _reconcile_subscription_checkout,
    _recover_conflicting_subscription_reservation as _recover_conflicting_subscription_reservation,
    _resolve_authoritative_subscription_reservation as _resolve_authoritative_subscription_reservation,
    _reuse_live_subscription_checkout_url as _reuse_live_subscription_checkout_url,
    _subscription_reservation_can_be_reused as _subscription_reservation_can_be_reused,
    _subscription_reservation_needs_replacement as _subscription_reservation_needs_replacement,
    create_subscription_checkout_session as create_subscription_checkout_session,
    reconcile_account_deletion_subscription_checkout as reconcile_account_deletion_subscription_checkout,
    reconcile_elapsed_subscription_checkout as reconcile_elapsed_subscription_checkout,
    reconcile_organization_removal_subscription_checkout as reconcile_organization_removal_subscription_checkout,
)
from quickscale_modules_billing._subscription_events import (
    _apply_subscription_payload as _apply_subscription_payload,
    _handle_subscription_event as _handle_subscription_event,
    _subscription_provider_identity as _subscription_provider_identity,
    _upsert_subscription_from_payload as _upsert_subscription_from_payload,
)
from quickscale_modules_billing._subscription_mutations import (
    _cancel_current_subscription_with_transition as _cancel_current_subscription_with_transition,
    _persist_subscription_provider_snapshot as _persist_subscription_provider_snapshot,
    _require_owner_provider_mutation_authorization as _require_owner_provider_mutation_authorization,
    _restore_subscription_cancellation_transition as _restore_subscription_cancellation_transition,
    _set_current_subscription_cancel_at_period_end as _set_current_subscription_cancel_at_period_end,
    cancel_current_subscription as cancel_current_subscription,
    resume_current_subscription as resume_current_subscription,
)
from quickscale_modules_billing._validation import (
    _validate_completed_checkout_plan as _validate_completed_checkout_plan,
    _validate_completed_checkout_provider_identity as _validate_completed_checkout_provider_identity,
    _validate_one_time_purchase_plan as _validate_one_time_purchase_plan,
    _validate_recurring_subscription_plan as _validate_recurring_subscription_plan,
    _validate_stripe_price_parity as _validate_stripe_price_parity,
)
from quickscale_modules_billing._webhooks import (
    _handle_checkout_session_completed_event as _handle_checkout_session_completed_event,
    _handle_checkout_session_expired_event as _handle_checkout_session_expired_event,
    _process_verified_stripe_event as _process_verified_stripe_event,
    _record_subscription_checkout_completion as _record_subscription_checkout_completion,
    _record_subscription_checkout_expiration as _record_subscription_checkout_expiration,
    _resolve_purchase_checkout_for_session as _resolve_purchase_checkout_for_session,
    _resolve_subscription_checkout_for_session as _resolve_subscription_checkout_for_session,
    _validate_subscription_checkout_reservation_metadata as _validate_subscription_checkout_reservation_metadata,
)
from quickscale_modules_billing._webhooks_invoice import (
    _activate_subscription_for_paid_invoice as _activate_subscription_for_paid_invoice,
    _apply_invoice_payment_failed_event as _apply_invoice_payment_failed_event,
    _finalize_invoice_paid_event as _finalize_invoice_paid_event,
    _handle_invoice_paid_event as _handle_invoice_paid_event,
    _handle_invoice_payment_failed_event as _handle_invoice_payment_failed_event,
    _process_invoice_paid_event as _process_invoice_paid_event,
    _retrieve_subscription_for_paid_invoice as _retrieve_subscription_for_paid_invoice,
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

from quickscale_modules_billing.models import WebhookEvent

logger = logging.getLogger(__name__)


def get_stripe_client(
    *,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> StripeClient:
    """Return a configured Stripe client for the current runtime settings."""
    snapshot = settings_snapshot or BillingSettingsSnapshot.from_settings()
    secret_key = snapshot.resolve_secret_key()
    if not secret_key:
        raise BillingConfigurationError(
            "Stripe secret key is not configured in the runtime settings."
        )
    try:
        stripe_module = import_module("stripe")
    except ImportError as exc:
        raise BillingConfigurationError(
            "Stripe SDK is not installed in this environment."
        ) from exc
    return StripeClient(stripe_module=stripe_module, api_key=secret_key)


@_translate_stripe_errors("Stripe webhook handling failed.")
def handle_stripe_event(
    *,
    body: bytes,
    signature: str,
    stripe_client: Any | None = None,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> StripeWebhookResult:
    """Verify, record, and handle a Stripe webhook event idempotently."""
    snapshot = settings_snapshot or BillingSettingsSnapshot.from_settings()
    _ensure_billing_enabled(snapshot)

    webhook_secret = snapshot.resolve_webhook_secret()
    if not webhook_secret:
        raise BillingConfigurationError(
            "Stripe webhook secret is not configured in the runtime settings."
        )

    resolved_client = stripe_client or get_stripe_client(settings_snapshot=snapshot)
    event_payload = resolved_client.construct_event(
        body=body,
        signature=signature,
        webhook_secret=webhook_secret,
    )
    event_id = str(event_payload.get("id") or "").strip()
    event_type = str(event_payload.get("type") or "").strip()
    if not event_id:
        raise BillingWebhookError("Stripe event payload is missing an id.")
    if not event_type:
        raise BillingWebhookError("Stripe event payload is missing a type.")

    event_api_version = str(event_payload.get("api_version") or "").strip()
    logger.info(
        "Stripe webhook event %s reports API version %s.",
        event_id,
        event_api_version or "<blank>",
    )
    if _stripe_named_release(event_api_version) != _stripe_named_release(
        STRIPE_API_VERSION
    ):
        raise BillingConfigurationError(
            f"Stripe webhook event API version {event_api_version or '<blank>'} does "
            f"not match the required Stripe API version {STRIPE_API_VERSION}; "
            f"recreate the webhook endpoint at {STRIPE_API_VERSION}."
        )

    with _webhook_event_processing_lock(event_id):
        webhook_event, _ = WebhookEvent.objects.get_or_create(
            stripe_event_id=event_id,
            defaults={
                "event_type": event_type,
                "payload": event_payload,
            },
        )
        return _process_verified_stripe_event(
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
    "detach_account_deletion_user_references",
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
