"""One-time Checkout and Billing Portal session creation.

Implementation detail of :mod:`quickscale_modules_billing.services`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

from typing import Any

from quickscale_modules_orgs.current_org import org_scope

import quickscale_modules_billing._customers as _customers
from quickscale_modules_billing._payload import (
    _build_checkout_session_metadata as _build_checkout_session_metadata,
)
from quickscale_modules_billing._payload import (
    _build_purchase_checkout_create_idempotency_key as _build_purchase_checkout_create_idempotency_key,
)
from quickscale_modules_billing._payload import (
    _extract_checkout_session_expires_at as _extract_checkout_session_expires_at,
)
from quickscale_modules_billing._payload import (
    _extract_live_checkout_session_url as _extract_live_checkout_session_url,
)
from quickscale_modules_billing._payload import (
    _normalize_mapping as _normalize_mapping,
)
from quickscale_modules_billing._payload import (
    _purchase_checkout_reference as _purchase_checkout_reference,
)
from quickscale_modules_billing._payload import (
    _user_reference as _user_reference,
)
from quickscale_modules_billing._settings import (
    _PURCHASE_CHECKOUT_REFERENCE_METADATA_KEY as _PURCHASE_CHECKOUT_REFERENCE_METADATA_KEY,
)
from quickscale_modules_billing._settings import (
    BillingSettingsSnapshot as BillingSettingsSnapshot,
)
import quickscale_modules_billing._settings as _settings
from quickscale_modules_billing._stripe_client import (
    _stripe_error_classes as _stripe_error_classes,
)
from quickscale_modules_billing._subscription_mutations import (
    _require_owner_provider_mutation_authorization as _require_owner_provider_mutation_authorization,
)
import quickscale_modules_billing._validation as _validation
from quickscale_modules_billing.exceptions import (
    BillingError,
    BillingValidationError,
)
from quickscale_modules_billing.models import (
    Plan,
    PurchaseCheckout,
)
import quickscale_modules_billing._locks as _locks
import quickscale_modules_billing._removal as _removal
import quickscale_modules_billing._stripe_client as _stripe_client


def create_checkout_session(
    user: Any,
    *,
    plan: Plan,
    success_url: str,
    cancel_url: str,
    organization: Any,
    stripe_client: Any | None = None,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> str:
    """Serialize one-time Checkout creation with destructive org boundaries."""
    try:
        with _locks.subscription_provider_mutation_lock(organization):
            user, organization = _require_owner_provider_mutation_authorization(
                user,
                organization,
            )
            return _create_checkout_session(
                user,
                plan,
                success_url,
                cancel_url,
                organization=organization,
                stripe_client=stripe_client,
                settings_snapshot=settings_snapshot,
            )
    except _stripe_error_classes() as exc:
        raise BillingError("Stripe checkout session creation failed.") from exc


def _create_checkout_session(
    user: Any,
    plan: Plan,
    success_url: str,
    cancel_url: str,
    *,
    organization: Any,
    stripe_client: Any | None = None,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> str:
    """Create one Stripe purchase session while its organization mutex is held."""
    snapshot = settings_snapshot or BillingSettingsSnapshot.from_settings()
    _settings._ensure_billing_enabled(snapshot)

    normalized_success_url = success_url.strip()
    normalized_cancel_url = cancel_url.strip()
    if not normalized_success_url or not normalized_cancel_url:
        raise BillingValidationError("Checkout success and cancel URLs are required.")

    _validation._validate_one_time_purchase_plan(plan)

    resolved_client = stripe_client or _stripe_client.get_stripe_client(
        settings_snapshot=snapshot
    )
    stripe_price = resolved_client.retrieve_price(price_id=plan.stripe_price_id)
    _validation._validate_stripe_price_parity(
        plan=plan,
        stripe_price=stripe_price,
        settings_snapshot=snapshot,
    )
    customer_id, _ = _customers.get_or_create_stripe_customer(
        user,
        organization=organization,
        stripe_client=resolved_client,
        settings_snapshot=snapshot,
    )
    # Persist the intent immediately before the non-transactional provider
    # create. An exception can mean Stripe created the session but the response
    # was lost, so the PREPARING row must remain as a fail-closed obligation.
    with org_scope(organization):
        _locks._lock_organization_for_billing_mutation(organization)
        preparing_reservations = list(
            PurchaseCheckout.all_objects.select_for_update()
            .filter(
                user=user,
                organization=organization,
                plan=plan,
                status=PurchaseCheckout.Status.PREPARING,
            )
            .order_by("pk")[:2]
        )
        if len(preparing_reservations) > 1:
            raise BillingError(
                "Multiple purchase checkouts have unknown creation outcomes; "
                "manual provider reconciliation is required."
            )
        open_reservations: list[PurchaseCheckout] = []
        if preparing_reservations:
            reservation = preparing_reservations[0]
        else:
            # A repeated POST while a reservation is open must not create a
            # second payable provider session. Resolve the open reservations
            # against Stripe and reuse the one whose session is still payable.
            open_reservations = list(
                PurchaseCheckout.all_objects.select_for_update()
                .filter(
                    user=user,
                    organization=organization,
                    plan=plan,
                    status=PurchaseCheckout.Status.OPEN,
                )
                .order_by("-pk")
            )
            reservation = (
                open_reservations[0]
                if open_reservations
                else PurchaseCheckout.all_objects.create(
                    user=user,
                    organization=organization,
                    plan=plan,
                )
            )

    if open_reservations:
        live_checkout_url = _reuse_open_purchase_checkout_url(
            open_reservations,
            stripe_client=resolved_client,
        )
        if live_checkout_url:
            return live_checkout_url
        # Every open reservation resolved to a terminal provider session, so a
        # fresh reservation carries the replacement session.
        with org_scope(organization):
            _locks._lock_organization_for_billing_mutation(organization)
            reservation = PurchaseCheckout.all_objects.create(
                user=user,
                organization=organization,
                plan=plan,
            )

    reservation_reference = _purchase_checkout_reference(reservation)
    session_metadata = _build_checkout_session_metadata(
        user,
        plan,
        organization=organization,
    )
    session_metadata[_PURCHASE_CHECKOUT_REFERENCE_METADATA_KEY] = reservation_reference

    try:
        checkout_session = resolved_client.create_checkout_session(
            customer_id=customer_id,
            price_id=plan.stripe_price_id,
            success_url=normalized_success_url,
            cancel_url=normalized_cancel_url,
            session_metadata=session_metadata,
            payment_intent_metadata=session_metadata,
            client_reference_id=_user_reference(user),
            idempotency_key=_build_purchase_checkout_create_idempotency_key(
                reservation_reference
            ),
        )
    except _stripe_client._stripe_definitive_error_classes():
        _removal._resolve_definitively_failed_purchase_checkout(
            organization,
            reservation,
            customer_id=customer_id,
            stripe_client=resolved_client,
        )
        raise
    checkout_session_id = str(checkout_session.get("id") or "").strip()
    checkout_url = str(checkout_session.get("url") or "").strip()
    if not checkout_session_id:
        raise BillingError("Stripe checkout session creation did not return an id.")

    with org_scope(organization):
        _locks._lock_organization_for_billing_mutation(organization)
        reservation = PurchaseCheckout.all_objects.select_for_update().get(
            pk=reservation.pk
        )
        reservation.stripe_checkout_session_id = checkout_session_id
        reservation.status = PurchaseCheckout.Status.OPEN
        reservation.checkout_expires_at = _extract_checkout_session_expires_at(
            checkout_session
        )
        reservation.save(
            update_fields=[
                "stripe_checkout_session_id",
                "status",
                "checkout_expires_at",
            ]
        )
    if not checkout_url:
        raise BillingError(
            "Stripe checkout session creation did not return a hosted URL."
        )
    return checkout_url


def _reuse_open_purchase_checkout_url(
    reservations: list[PurchaseCheckout],
    *,
    stripe_client: Any,
) -> str:
    """Return a still-payable hosted URL from the organization's open reservations.

    A repeated POST reuses the reservation whose provider session is still
    payable instead of creating a second payable session.  Each inspected
    reservation is resolved against Stripe: an open session returns its hosted
    URL, an expired session is closed locally so the caller can create a
    replacement, and a completed session refuses replacement because its
    credit may still arrive through a webhook.  A provider answer the module
    cannot classify fails closed.
    """
    retrieve = getattr(stripe_client, "retrieve_checkout_session", None)
    if not callable(retrieve):
        raise BillingError(
            "Stripe checkout retrieval is unavailable; the existing purchase "
            "checkout cannot be reused or replaced safely."
        )
    for reservation in reservations:
        checkout_session_id = str(reservation.stripe_checkout_session_id or "").strip()
        if not checkout_session_id:
            # An open reservation without a session id cannot be payable, so
            # it is closed and the caller creates a replacement.
            _close_open_purchase_checkout(reservation)
            continue
        checkout_session = _normalize_mapping(
            retrieve(checkout_session_id=checkout_session_id)
        )
        provider_status = str(checkout_session.get("status") or "").strip().lower()
        if provider_status == "expired":
            _close_open_purchase_checkout(
                reservation,
                checkout_session_id=checkout_session_id,
            )
            continue
        if provider_status == "complete":
            raise BillingValidationError(
                "Stripe purchase checkout completed and may require credit "
                f"synchronization ({checkout_session_id}); wait for its webhook "
                "before creating another checkout."
            )
        if provider_status != "open":
            raise BillingError(
                "Stripe purchase checkout reconciliation returned an unsupported "
                f"or blank status for {checkout_session_id}."
            )
        checkout_url = _extract_live_checkout_session_url(checkout_session)
        if not checkout_url:
            raise BillingError(
                "Stripe reports the existing purchase checkout as open but did "
                "not return a reusable hosted URL; automatic replacement was "
                "refused."
            )
        return checkout_url
    return ""


def _close_open_purchase_checkout(
    reservation: PurchaseCheckout,
    *,
    checkout_session_id: str = "",
) -> None:
    """Mark one open reservation expired without overwriting a newer provider state."""
    filters: dict[str, Any] = {
        "pk": reservation.pk,
        "status": PurchaseCheckout.Status.OPEN,
    }
    if checkout_session_id:
        filters["stripe_checkout_session_id"] = checkout_session_id
    with org_scope(reservation.organization):
        _locks._lock_organization_for_billing_mutation(reservation.organization)
        PurchaseCheckout.all_objects.filter(**filters).update(
            status=PurchaseCheckout.Status.EXPIRED
        )


def create_billing_portal_session(
    user: Any,
    *,
    return_url: str,
    organization: Any,
    stripe_client: Any | None = None,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> str:
    """Create a hosted Stripe billing portal session for the given organization."""
    snapshot = settings_snapshot or BillingSettingsSnapshot.from_settings()
    _settings._ensure_billing_enabled(snapshot)

    normalized_return_url = return_url.strip()
    if not normalized_return_url:
        raise BillingValidationError("Billing portal return URL is required.")

    resolved_client = stripe_client or _stripe_client.get_stripe_client(
        settings_snapshot=snapshot
    )
    try:
        with _locks.subscription_provider_mutation_lock(organization):
            user, organization = _require_owner_provider_mutation_authorization(
                user,
                organization,
            )
            customer_id, _ = _customers.get_or_create_stripe_customer(
                user,
                organization=organization,
                stripe_client=resolved_client,
                settings_snapshot=snapshot,
            )
            portal_session = resolved_client.create_billing_portal_session(
                customer_id=customer_id,
                return_url=normalized_return_url,
            )
            portal_url = str(portal_session.get("url") or "").strip()
            if not portal_url:
                raise BillingError(
                    "Stripe billing portal session creation did not return a hosted URL."
                )
    except _stripe_error_classes() as exc:
        raise BillingError("Stripe billing portal session creation failed.") from exc
    return portal_url
