"""One-time Checkout and Billing Portal session creation.

Implementation detail of :mod:`quickscale_modules_billing.services`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

from typing import Any

from quickscale_modules_orgs.current_org import org_scope

import quickscale_modules_billing.services as _services
from quickscale_modules_billing._customers import (
    get_or_create_stripe_customer as get_or_create_stripe_customer,
)
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
from quickscale_modules_billing._settings import (
    _ensure_billing_enabled as _ensure_billing_enabled,
)
from quickscale_modules_billing._stripe_client import (
    _stripe_error_classes as _stripe_error_classes,
)
from quickscale_modules_billing._subscription_mutations import (
    _require_owner_provider_mutation_authorization as _require_owner_provider_mutation_authorization,
)
from quickscale_modules_billing._validation import (
    _validate_one_time_purchase_plan as _validate_one_time_purchase_plan,
)
from quickscale_modules_billing._validation import (
    _validate_stripe_price_parity as _validate_stripe_price_parity,
)
from quickscale_modules_billing.exceptions import (
    BillingError,
    BillingValidationError,
)
from quickscale_modules_billing.models import (
    Plan,
    PurchaseCheckout,
)


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
        with _services.subscription_provider_mutation_lock(organization):
            user, organization = _require_owner_provider_mutation_authorization(
                user,
                organization,
            )
            return _services._create_checkout_session(
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
    _ensure_billing_enabled(snapshot)

    normalized_success_url = success_url.strip()
    normalized_cancel_url = cancel_url.strip()
    if not normalized_success_url or not normalized_cancel_url:
        raise BillingValidationError("Checkout success and cancel URLs are required.")

    _validate_one_time_purchase_plan(plan)

    resolved_client = stripe_client or _services.get_stripe_client(
        settings_snapshot=snapshot
    )
    stripe_price = resolved_client.retrieve_price(price_id=plan.stripe_price_id)
    _validate_stripe_price_parity(plan=plan, stripe_price=stripe_price)
    customer_id, _ = get_or_create_stripe_customer(
        user,
        organization=organization,
        stripe_client=resolved_client,
        settings_snapshot=snapshot,
    )
    # Persist the intent immediately before the non-transactional provider
    # create. An exception can mean Stripe created the session but the response
    # was lost, so the PREPARING row must remain as a fail-closed obligation.
    with org_scope(organization):
        _services._lock_organization_for_billing_mutation(organization)
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
        reservation = (
            preparing_reservations[0]
            if preparing_reservations
            else PurchaseCheckout.all_objects.create(
                user=user,
                organization=organization,
                plan=plan,
            )
        )

    reservation_reference = _purchase_checkout_reference(reservation)
    session_metadata = _build_checkout_session_metadata(
        user,
        plan,
        organization=organization,
    )
    session_metadata[_PURCHASE_CHECKOUT_REFERENCE_METADATA_KEY] = reservation_reference

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
    checkout_session_id = str(checkout_session.get("id") or "").strip()
    checkout_url = str(checkout_session.get("url") or "").strip()
    if not checkout_session_id:
        raise BillingError("Stripe checkout session creation did not return an id.")

    with org_scope(organization):
        _services._lock_organization_for_billing_mutation(organization)
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
    _ensure_billing_enabled(snapshot)

    normalized_return_url = return_url.strip()
    if not normalized_return_url:
        raise BillingValidationError("Billing portal return URL is required.")

    resolved_client = stripe_client or _services.get_stripe_client(
        settings_snapshot=snapshot
    )
    try:
        with _services.subscription_provider_mutation_lock(organization):
            user, organization = _require_owner_provider_mutation_authorization(
                user,
                organization,
            )
            customer_id, _ = get_or_create_stripe_customer(
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
