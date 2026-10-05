"""Stripe webhook dispatch and Checkout event handling.

Implementation detail of :mod:`quickscale_modules_billing.services`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quickscale_modules_billing.models import Plan

from django.db import transaction
from quickscale_modules_orgs.current_org import org_scope

from quickscale_modules_billing._credits import (
    credit_user as credit_user,
)
from quickscale_modules_billing._payload import (
    _extract_checkout_session_expires_at as _extract_checkout_session_expires_at,
)
from quickscale_modules_billing._payload import (
    _extract_event_object as _extract_event_object,
)
from quickscale_modules_billing._payload import (
    _extract_metadata_value as _extract_metadata_value,
)
from quickscale_modules_billing._payload import (
    _purchase_checkout_pk_from_reference as _purchase_checkout_pk_from_reference,
)
from quickscale_modules_billing._payload import (
    _resolve_purchase_checkout_reference as _resolve_purchase_checkout_reference,
)
from quickscale_modules_billing._payload import (
    _resolve_subscription_checkout_reference as _resolve_subscription_checkout_reference,
)
from quickscale_modules_billing._payload import (
    _stripe_object_id as _stripe_object_id,
)
from quickscale_modules_billing._payload import (
    _subscription_checkout_pk_from_reference as _subscription_checkout_pk_from_reference,
)
from quickscale_modules_billing._resolution import (
    _resolve_checkout_session_credit_amount as _resolve_checkout_session_credit_amount,
)
from quickscale_modules_billing._resolution import (
    _resolve_organization_for_checkout_session as _resolve_organization_for_checkout_session,
)
from quickscale_modules_billing._resolution import (
    _resolve_plan_for_checkout_session as _resolve_plan_for_checkout_session,
)
from quickscale_modules_billing._resolution import (
    _resolve_user_for_checkout_session as _resolve_user_for_checkout_session,
)
from quickscale_modules_billing._resolution import (
    _resolve_user_from_metadata_sources as _resolve_user_from_metadata_sources,
)
from quickscale_modules_billing._resolution import (
    _retrieve_checkout_payment_intent_payload as _retrieve_checkout_payment_intent_payload,
)
from quickscale_modules_billing._settings import (
    _PRICE_ID_METADATA_KEY as _PRICE_ID_METADATA_KEY,
)
from quickscale_modules_billing._settings import (
    STRIPE_EVENT_TYPE_CHECKOUT_SESSION_COMPLETED as STRIPE_EVENT_TYPE_CHECKOUT_SESSION_COMPLETED,
)
from quickscale_modules_billing._settings import (
    STRIPE_EVENT_TYPE_CHECKOUT_SESSION_EXPIRED as STRIPE_EVENT_TYPE_CHECKOUT_SESSION_EXPIRED,
)
from quickscale_modules_billing._settings import (
    STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_CREATED as STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_CREATED,
)
from quickscale_modules_billing._settings import (
    STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_DELETED as STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_DELETED,
)
from quickscale_modules_billing._settings import (
    STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_UPDATED as STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_UPDATED,
)
from quickscale_modules_billing._settings import (
    STRIPE_EVENT_TYPE_INVOICE_PAID as STRIPE_EVENT_TYPE_INVOICE_PAID,
)
from quickscale_modules_billing._settings import (
    STRIPE_EVENT_TYPE_INVOICE_PAYMENT_FAILED as STRIPE_EVENT_TYPE_INVOICE_PAYMENT_FAILED,
)
from quickscale_modules_billing._settings import (
    StripeWebhookResult as StripeWebhookResult,
)
import quickscale_modules_billing._subscription_events as _subscription_events
from quickscale_modules_billing._validation import (
    _validate_completed_checkout_provider_identity as _validate_completed_checkout_provider_identity,
)
import quickscale_modules_billing._webhooks_invoice as _webhooks_invoice
from quickscale_modules_billing.exceptions import (
    BillingError,
    BillingWebhookError,
)
from quickscale_modules_billing.models import (
    CreditTransaction,
    PurchaseCheckout,
    Subscription,
    WebhookEvent,
)
import quickscale_modules_billing._locks as _locks


def _process_verified_stripe_event(
    *,
    webhook_event: WebhookEvent,
    event_payload: Mapping[str, Any],
    event_type: str,
    stripe_client: Any,
) -> StripeWebhookResult:
    """Process one verified event while its session-level mutex is held."""
    with transaction.atomic():
        locked_event = WebhookEvent.objects.select_for_update().get(pk=webhook_event.pk)
        if locked_event.processed:
            return StripeWebhookResult(
                duplicate=True,
                event_type=locked_event.event_type,
                status="duplicate",
            )

    # Provider I/O happens outside a database transaction. The session-level
    # advisory mutex remains held so another delivery of this event cannot
    # enter its handler before the final processed state is persisted.
    processing_status = "ignored"
    processing_error_message = ""
    try:
        if event_type == STRIPE_EVENT_TYPE_CHECKOUT_SESSION_COMPLETED:
            _handle_checkout_session_completed_event(
                event_payload,
                stripe_client=stripe_client,
            )
            processing_status = "processed"
        elif event_type == STRIPE_EVENT_TYPE_CHECKOUT_SESSION_EXPIRED:
            _handle_checkout_session_expired_event(event_payload)
            processing_status = "processed"
        elif event_type == STRIPE_EVENT_TYPE_INVOICE_PAID:
            _webhooks_invoice._handle_invoice_paid_event(
                event_payload,
                stripe_client=stripe_client,
            )
            processing_status = "processed"
        elif event_type == STRIPE_EVENT_TYPE_INVOICE_PAYMENT_FAILED:
            _webhooks_invoice._handle_invoice_payment_failed_event(event_payload)
            processing_status = "processed"
        elif event_type in {
            STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_CREATED,
            STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_UPDATED,
            STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_DELETED,
        }:
            _subscription_events._handle_subscription_event(
                event_payload, event_type=event_type
            )
            processing_status = "processed"
        else:
            processing_status = "ignored"
    except BillingError as exc:
        processing_error_message = str(exc)

    # Persist result (short atomic, no Stripe round-trips)
    with transaction.atomic():
        WebhookEvent.objects.filter(pk=webhook_event.pk).update(
            event_type=event_type,
            payload=event_payload,
            processed=(not processing_error_message),
            processing_error=processing_error_message,
        )

    if processing_error_message:
        raise BillingWebhookError(processing_error_message)

    return StripeWebhookResult(
        duplicate=False,
        event_type=event_type,
        status=processing_status,
    )


def _handle_subscription_checkout_mode(
    checkout_session_payload: Mapping[str, Any],
) -> bool:
    """Record a subscription checkout; True when the session was subscription."""
    checkout_mode = str(checkout_session_payload.get("mode") or "").strip()
    if checkout_mode == "subscription":
        _record_subscription_checkout_completion(checkout_session_payload)
        return True
    if checkout_mode and checkout_mode != "payment":
        raise BillingWebhookError(
            "Stripe checkout session is not a one-time payment session."
        )
    payment_status = str(checkout_session_payload.get("payment_status") or "").strip()
    if payment_status and payment_status != "paid":
        raise BillingWebhookError("Stripe checkout session payment is not settled.")
    return False


def _validate_purchase_reservation(
    reservation: PurchaseCheckout,
    *,
    plan: Plan,
    user: Any,
) -> None:
    """Refuse a completed checkout that conflicts with its local reservation."""
    if reservation.status == PurchaseCheckout.Status.EXPIRED:
        raise BillingWebhookError(
            "Completed Stripe checkout conflicts with an expired local "
            "purchase reservation."
        )
    if reservation.plan_id != plan.pk:
        raise BillingWebhookError(
            "Completed Stripe checkout plan conflicts with its local "
            "purchase reservation."
        )
    if reservation.user_id is not None and reservation.user_id != getattr(
        user, "pk", None
    ):
        raise BillingWebhookError(
            "Completed Stripe checkout user conflicts with its local "
            "purchase reservation."
        )


def _complete_purchase_reservation(
    reservation: PurchaseCheckout | None,
    *,
    checkout_session_payload: Mapping[str, Any],
    checkout_session_id: str,
    organization: Any,
) -> None:
    """Mark the matching purchase reservation (or loose row) completed."""
    if reservation is not None:
        reservation.stripe_checkout_session_id = checkout_session_id
        reservation.status = PurchaseCheckout.Status.COMPLETED
        reservation.checkout_expires_at = (
            _extract_checkout_session_expires_at(checkout_session_payload)
            or reservation.checkout_expires_at
        )
        reservation.save(
            update_fields=[
                "stripe_checkout_session_id",
                "status",
                "checkout_expires_at",
            ]
        )
        return
    PurchaseCheckout.all_objects.filter(
        organization=organization,
        stripe_checkout_session_id=checkout_session_id,
        status=PurchaseCheckout.Status.OPEN,
    ).update(status=PurchaseCheckout.Status.COMPLETED)


def _apply_completed_purchase_checkout(
    *,
    checkout_session_payload: Mapping[str, Any],
    organization: Any,
    plan: Plan,
    user: Any,
    credited_amount: Any,
    checkout_session_id: str,
    reference_data: Mapping[str, Any],
    event_payload: Mapping[str, Any],
) -> CreditTransaction | None:
    """Credit a completed purchase checkout under the provider mutex."""
    # Phase 3: each handler owns its provider mutex and org scope so purge,
    # account deletion, and Checkout completion observe one serial history.
    with _locks.subscription_provider_mutation_lock(organization):
        with org_scope(organization):
            _locks._lock_organization_for_billing_mutation(organization)
            reservation = _resolve_purchase_checkout_for_session(
                checkout_session_payload=checkout_session_payload,
                organization=organization,
                for_update=True,
            )
            if reservation is not None:
                _validate_purchase_reservation(reservation, plan=plan, user=user)
            transaction_row = credit_user(
                user,
                organization=organization,
                amount=credited_amount,
                transaction_type=CreditTransaction.TransactionType.PURCHASE,
                description=f"{plan.name} credits from Stripe checkout session {checkout_session_id}",
                stripe_event_id=str(event_payload.get("id") or "").strip(),
                stripe_object_id=checkout_session_id,
                stripe_reference_data=dict(reference_data),
            )
            _complete_purchase_reservation(
                reservation,
                checkout_session_payload=checkout_session_payload,
                checkout_session_id=checkout_session_id,
                organization=organization,
            )
            return transaction_row


def _handle_checkout_session_completed_event(
    event_payload: Mapping[str, Any],
    *,
    stripe_client: Any | None = None,
) -> CreditTransaction | None:
    checkout_session_payload = _extract_event_object(event_payload)
    checkout_session_id = str(checkout_session_payload.get("id") or "").strip()
    if not checkout_session_id:
        raise BillingWebhookError("Stripe checkout session payload is missing an id.")

    if _handle_subscription_checkout_mode(checkout_session_payload):
        return None

    payment_intent_payload = _retrieve_checkout_payment_intent_payload(
        checkout_session_payload=checkout_session_payload,
        stripe_client=stripe_client,
    )
    plan = _resolve_plan_for_checkout_session(
        checkout_session_payload=checkout_session_payload,
        payment_intent_payload=payment_intent_payload,
    )
    credited_amount = _resolve_checkout_session_credit_amount(
        checkout_session_payload=checkout_session_payload,
        payment_intent_payload=payment_intent_payload,
    )
    organization = _resolve_organization_for_checkout_session(
        checkout_session_payload=checkout_session_payload,
        payment_intent_payload=payment_intent_payload,
    )
    user = _resolve_user_for_checkout_session(
        checkout_session_payload=checkout_session_payload,
        payment_intent_payload=payment_intent_payload,
    )
    if user is None:
        raise BillingWebhookError(
            "Could not resolve a local user for the Stripe checkout session."
        )

    payment_intent_id = str(
        checkout_session_payload.get("payment_intent") or ""
    ).strip()
    customer_id = str(checkout_session_payload.get("customer") or "").strip()
    reference_data: dict[str, Any] = {
        "checkout_session_id": checkout_session_id,
        "stripe_customer_id": customer_id,
        "stripe_price_id": plan.stripe_price_id,
    }
    if payment_intent_id:
        reference_data["payment_intent_id"] = payment_intent_id

    return _apply_completed_purchase_checkout(
        checkout_session_payload=checkout_session_payload,
        organization=organization,
        plan=plan,
        user=user,
        credited_amount=credited_amount,
        checkout_session_id=checkout_session_id,
        reference_data=reference_data,
        event_payload=event_payload,
    )


def _record_subscription_checkout_completion(
    checkout_session_payload: Mapping[str, Any],
) -> None:
    """Bind Checkout's subscription identity before later webhooks arrive."""
    organization = _resolve_organization_for_checkout_session(
        checkout_session_payload=checkout_session_payload,
        payment_intent_payload={},
    )
    if organization is None:
        return

    checkout_session_id = str(checkout_session_payload.get("id") or "").strip()
    provider_subscription_id = _stripe_object_id(
        checkout_session_payload.get("subscription")
    )
    if not provider_subscription_id:
        raise BillingWebhookError(
            "Completed subscription checkout is missing its Stripe subscription id."
        )

    with _locks.subscription_provider_mutation_lock(organization):
        with org_scope(organization):
            locked_organization = _locks._lock_organization_for_billing_mutation(
                organization
            )
            reservation = _resolve_subscription_checkout_for_session(
                checkout_session_payload=checkout_session_payload,
                organization=locked_organization,
                for_update=True,
            )
            if reservation is None:
                raise BillingWebhookError(
                    "Completed subscription checkout could not be reconciled to its "
                    "local reservation."
                )
            if reservation.status == Subscription.Status.INCOMPLETE_EXPIRED:
                raise BillingWebhookError(
                    "Completed subscription checkout conflicts with an expired local "
                    "reservation."
                )
            _validate_subscription_checkout_reservation_metadata(
                reservation=reservation,
                checkout_session_payload=checkout_session_payload,
            )
            _validate_completed_checkout_provider_identity(
                reservation=reservation,
                organization=locked_organization,
                checkout_session_payload=checkout_session_payload,
            )
            reservation.stripe_subscription_id = provider_subscription_id
            reservation.stripe_checkout_session_id = checkout_session_id
            reservation.checkout_expires_at = None
            customer_id = str(checkout_session_payload.get("customer") or "").strip()
            update_fields = [
                "stripe_subscription_id",
                "stripe_checkout_session_id",
                "checkout_expires_at",
            ]
            if customer_id and reservation.stripe_customer_id != customer_id:
                reservation.stripe_customer_id = customer_id
                update_fields.append("stripe_customer_id")
            reservation.save(update_fields=update_fields)


def _handle_checkout_session_expired_event(
    event_payload: Mapping[str, Any],
) -> None:
    """Make an exact one-time reservation terminal after Stripe expiry."""
    checkout_session_payload = _extract_event_object(event_payload)
    checkout_session_id = str(checkout_session_payload.get("id") or "").strip()
    if not checkout_session_id:
        raise BillingWebhookError("Stripe checkout session payload is missing an id.")
    checkout_mode = str(checkout_session_payload.get("mode") or "").strip()
    if checkout_mode == "subscription":
        _record_subscription_checkout_expiration(checkout_session_payload)
        return
    if checkout_mode and checkout_mode != "payment":
        return

    organization = _resolve_organization_for_checkout_session(
        checkout_session_payload=checkout_session_payload,
        payment_intent_payload={},
    )
    if organization is None:
        return

    with _locks.subscription_provider_mutation_lock(organization):
        with org_scope(organization):
            _locks._lock_organization_for_billing_mutation(organization)
            reservation = _resolve_purchase_checkout_for_session(
                checkout_session_payload=checkout_session_payload,
                organization=organization,
                for_update=True,
            )
            if reservation is None:
                return
            if reservation.status == PurchaseCheckout.Status.COMPLETED:
                raise BillingWebhookError(
                    "Expired Stripe checkout conflicts with a completed local purchase "
                    "reservation."
                )
            reservation.stripe_checkout_session_id = checkout_session_id
            reservation.status = PurchaseCheckout.Status.EXPIRED
            reservation.checkout_expires_at = (
                _extract_checkout_session_expires_at(checkout_session_payload)
                or reservation.checkout_expires_at
            )
            reservation.save(
                update_fields=[
                    "stripe_checkout_session_id",
                    "status",
                    "checkout_expires_at",
                ]
            )


def _record_subscription_checkout_expiration(
    checkout_session_payload: Mapping[str, Any],
) -> None:
    """Bind and expire an exact subscription reservation after response loss."""
    organization = _resolve_organization_for_checkout_session(
        checkout_session_payload=checkout_session_payload,
        payment_intent_payload={},
    )
    if organization is None:
        return

    checkout_session_id = str(checkout_session_payload.get("id") or "").strip()
    with _locks.subscription_provider_mutation_lock(organization):
        with org_scope(organization):
            locked_organization = _locks._lock_organization_for_billing_mutation(
                organization
            )
            reservation = _resolve_subscription_checkout_for_session(
                checkout_session_payload=checkout_session_payload,
                organization=locked_organization,
                for_update=True,
            )
            if reservation is None:
                raise BillingWebhookError(
                    "Expired subscription checkout could not be reconciled to its "
                    "local reservation."
                )
            if str(reservation.stripe_subscription_id or "").strip():
                raise BillingWebhookError(
                    "Expired subscription checkout conflicts with a locally bound "
                    "Stripe subscription."
                )
            if reservation.status not in {
                Subscription.Status.INCOMPLETE,
                Subscription.Status.INCOMPLETE_EXPIRED,
            }:
                raise BillingWebhookError(
                    "Expired subscription checkout conflicts with the local "
                    "subscription state."
                )
            _validate_subscription_checkout_reservation_metadata(
                reservation=reservation,
                checkout_session_payload=checkout_session_payload,
            )
            _validate_completed_checkout_provider_identity(
                reservation=reservation,
                organization=locked_organization,
                checkout_session_payload=checkout_session_payload,
            )
            reservation.stripe_checkout_session_id = checkout_session_id
            reservation.status = Subscription.Status.INCOMPLETE_EXPIRED
            reservation.checkout_expires_at = (
                _extract_checkout_session_expires_at(checkout_session_payload)
                or reservation.checkout_expires_at
            )
            reservation.save(
                update_fields=[
                    "stripe_checkout_session_id",
                    "status",
                    "checkout_expires_at",
                ]
            )


def _resolve_subscription_checkout_for_session(
    *,
    checkout_session_payload: Mapping[str, Any],
    organization: Any,
    for_update: bool,
) -> Subscription | None:
    """Resolve and validate the exact local subscription Checkout reservation."""
    checkout_session_id = str(checkout_session_payload.get("id") or "").strip()
    reservation_reference = _resolve_subscription_checkout_reference(
        [checkout_session_payload]
    )
    reservation_pk = _subscription_checkout_pk_from_reference(reservation_reference)
    if reservation_reference and reservation_pk is None:
        raise BillingWebhookError(
            "Stripe checkout session has an invalid subscription reservation reference."
        )

    queryset = Subscription.all_objects.filter(organization=organization)
    if for_update:
        queryset = queryset.select_for_update()
    if reservation_pk is not None:
        reservation = queryset.filter(pk=reservation_pk).first()
        if reservation is None:
            raise BillingWebhookError(
                "Stripe checkout session subscription reservation could not be "
                "resolved."
            )
    elif checkout_session_id:
        reservation = queryset.filter(
            stripe_checkout_session_id=checkout_session_id
        ).first()
    else:
        reservation = None
    if reservation is None:
        return None

    persisted_checkout_session_id = str(
        reservation.stripe_checkout_session_id or ""
    ).strip()
    if (
        persisted_checkout_session_id
        and checkout_session_id
        and persisted_checkout_session_id != checkout_session_id
    ):
        raise BillingWebhookError(
            "Stripe checkout session conflicts with its local subscription reservation."
        )
    if (
        checkout_session_id
        and Subscription.all_objects.filter(
            organization=organization,
            stripe_checkout_session_id=checkout_session_id,
        )
        .exclude(pk=reservation.pk)
        .exists()
    ):
        raise BillingWebhookError(
            "Stripe checkout session is already bound to a different subscription "
            "reservation."
        )
    return reservation


def _validate_subscription_checkout_reservation_metadata(
    *,
    reservation: Subscription,
    checkout_session_payload: Mapping[str, Any],
) -> None:
    """Reject immutable Checkout metadata that conflicts with its reservation."""
    metadata_price_id = _extract_metadata_value(
        [checkout_session_payload],
        _PRICE_ID_METADATA_KEY,
    )
    if metadata_price_id and metadata_price_id != reservation.plan.stripe_price_id:
        raise BillingWebhookError(
            "Stripe subscription checkout plan conflicts with its local reservation."
        )
    metadata_user = _resolve_user_from_metadata_sources([checkout_session_payload])
    if (
        metadata_user is not None
        and reservation.user_id is not None
        and reservation.user_id != getattr(metadata_user, "pk", None)
    ):
        raise BillingWebhookError(
            "Stripe subscription checkout user conflicts with its local reservation."
        )


def _resolve_purchase_checkout_for_session(
    *,
    checkout_session_payload: Mapping[str, Any],
    organization: Any,
    for_update: bool,
) -> PurchaseCheckout | None:
    """Resolve and validate the exact local one-time Checkout reservation."""
    checkout_session_id = str(checkout_session_payload.get("id") or "").strip()
    reservation_reference = _resolve_purchase_checkout_reference(
        [checkout_session_payload]
    )
    reservation_pk = _purchase_checkout_pk_from_reference(reservation_reference)
    if reservation_reference and reservation_pk is None:
        raise BillingWebhookError(
            "Stripe checkout session has an invalid purchase reservation reference."
        )

    queryset = PurchaseCheckout.all_objects.filter(organization=organization)
    if for_update:
        queryset = queryset.select_for_update()
    if reservation_pk is not None:
        reservation = queryset.filter(pk=reservation_pk).first()
        if reservation is None:
            raise BillingWebhookError(
                "Stripe checkout session purchase reservation could not be resolved."
            )
    elif checkout_session_id:
        reservation = queryset.filter(
            stripe_checkout_session_id=checkout_session_id
        ).first()
    else:
        reservation = None
    if reservation is None:
        return None

    persisted_checkout_session_id = str(
        reservation.stripe_checkout_session_id or ""
    ).strip()
    if (
        persisted_checkout_session_id
        and checkout_session_id
        and persisted_checkout_session_id != checkout_session_id
    ):
        raise BillingWebhookError(
            "Stripe checkout session conflicts with its local purchase reservation."
        )
    if (
        checkout_session_id
        and PurchaseCheckout.all_objects.filter(
            organization=organization,
            stripe_checkout_session_id=checkout_session_id,
        )
        .exclude(pk=reservation.pk)
        .exists()
    ):
        raise BillingWebhookError(
            "Stripe checkout session is already bound to a different purchase "
            "reservation."
        )
    return reservation
