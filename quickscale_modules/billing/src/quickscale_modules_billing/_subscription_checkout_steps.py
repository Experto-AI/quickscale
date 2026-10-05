"""Reservation and checkout-session steps for subscription Checkout.

Implementation detail of
:mod:`quickscale_modules_billing._subscription_checkout`: these helpers keep
the orchestration modules below the repository file-length gate (SA242).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from quickscale_modules_orgs.current_org import org_scope

from quickscale_modules_billing._customers import (
    get_or_create_stripe_customer as get_or_create_stripe_customer,
)
from quickscale_modules_billing._payload import (
    _build_checkout_session_metadata as _build_checkout_session_metadata,
)
from quickscale_modules_billing._payload import (
    _build_subscription_checkout_create_idempotency_key as _build_subscription_checkout_create_idempotency_key,
)
from quickscale_modules_billing._payload import (
    _extract_checkout_session_expires_at as _extract_checkout_session_expires_at,
)
from quickscale_modules_billing._payload import (
    _subscription_checkout_reference as _subscription_checkout_reference,
)
from quickscale_modules_billing._payload import (
    _user_reference as _user_reference,
)
from quickscale_modules_billing._settings import (
    BillingSettingsSnapshot as BillingSettingsSnapshot,
)
from quickscale_modules_billing._settings import (
    _CURRENT_RECURRING_SUBSCRIPTION_ERROR as _CURRENT_RECURRING_SUBSCRIPTION_ERROR,
)
from quickscale_modules_billing._settings import (
    _SUBSCRIPTION_CHECKOUT_REFERENCE_METADATA_KEY as _SUBSCRIPTION_CHECKOUT_REFERENCE_METADATA_KEY,
)
from quickscale_modules_billing._settings import (
    _ensure_billing_enabled as _ensure_billing_enabled,
)
from quickscale_modules_billing._validation import (
    _validate_completed_checkout_provider_identity as _validate_completed_checkout_provider_identity,
)
from quickscale_modules_billing.exceptions import (
    BillingError,
    BillingValidationError,
)
from quickscale_modules_billing.models import (
    Plan,
    Subscription,
)
import quickscale_modules_billing._locks as _locks
import quickscale_modules_billing._stripe_client as _stripe_client


def _initial_subscription_checkout_reservation(
    *,
    user: Any,
    organization: Any,
    plan: Plan,
    stripe_customer_id: str | None,
) -> Subscription:
    """Create the initial checkout reservation and prove it belongs to the user."""

    from quickscale_modules_billing._subscription_checkout import (
        _prepare_subscription_checkout_reservation,
    )

    with transaction.atomic():
        _locks._lock_organization_for_billing_mutation(organization)
        reservation, _ = _prepare_subscription_checkout_reservation(
            user=user,
            organization=organization,
            plan=plan,
            stripe_customer_id=stripe_customer_id,
        )
        if reservation.user_id != getattr(user, "pk", None):
            raise BillingValidationError(_CURRENT_RECURRING_SUBSCRIPTION_ERROR)
        return reservation


def _reservation_customer_id(
    reservation: Subscription,
    *,
    user: Any,
    organization: Any,
    plan: Plan,
    resolved_client: Any,
    snapshot: BillingSettingsSnapshot,
) -> tuple[Subscription, str]:
    """Return the reservation with a provider customer id attached."""

    from quickscale_modules_billing._subscription_checkout import (
        _subscription_reservation_can_be_reused,
    )

    customer_id = str(reservation.stripe_customer_id or "").strip()
    if customer_id:
        return reservation, customer_id
    customer_id, _ = get_or_create_stripe_customer(
        user,
        organization=organization,
        stripe_client=resolved_client,
        settings_snapshot=snapshot,
    )
    with transaction.atomic():
        _locks._lock_organization_for_billing_mutation(organization)
        reservation = Subscription.all_objects.select_for_update().get(
            pk=reservation.pk
        )
        if not _subscription_reservation_can_be_reused(reservation, plan=plan):
            raise BillingValidationError(_CURRENT_RECURRING_SUBSCRIPTION_ERROR)
        reservation.stripe_customer_id = customer_id
        reservation.save(update_fields=["stripe_customer_id"])
    return reservation, customer_id


def _replace_stale_checkout_reservation(
    reservation: Subscription,
    *,
    user: Any,
    organization: Any,
    plan: Plan,
    customer_id: str,
    resolved_client: Any,
) -> tuple[Subscription, str]:
    """Replace a reservation with a stale session id; return (reservation, url)."""

    from quickscale_modules_billing._subscription_checkout import (
        _create_subscription_reservation,
        _expire_subscription_reservation,
        _reuse_live_subscription_checkout_url,
        _subscription_reservation_can_be_reused,
    )

    if not str(reservation.stripe_checkout_session_id or "").strip():
        return reservation, ""
    with transaction.atomic():
        _locks._lock_organization_for_billing_mutation(organization)
        current_reservation = Subscription.all_objects.select_for_update().get(
            pk=reservation.pk
        )
        if _subscription_reservation_can_be_reused(current_reservation, plan=plan):
            _expire_subscription_reservation(current_reservation)
            reservation, _ = _create_subscription_reservation(
                user=user,
                organization=organization,
                plan=plan,
                stripe_customer_id=customer_id or None,
            )
    live_checkout_url = _reuse_live_subscription_checkout_url(
        reservation=reservation,
        stripe_client=resolved_client,
    )
    return reservation, live_checkout_url


def _create_and_persist_checkout_session(
    *,
    user: Any,
    plan: Plan,
    organization: Any,
    reservation: Subscription,
    customer_id: str,
    resolved_client: Any,
    success_url: str,
    cancel_url: str,
) -> str:
    """Create the provider checkout session and persist it on the reservation."""

    from quickscale_modules_billing._subscription_checkout import (
        _subscription_reservation_can_be_reused,
    )

    session_metadata = _build_checkout_session_metadata(
        user,
        plan,
        organization=organization,
    )
    reservation_reference = _subscription_checkout_reference(reservation)
    session_metadata[_SUBSCRIPTION_CHECKOUT_REFERENCE_METADATA_KEY] = (
        reservation_reference
    )
    # A blank-session reservation can survive customer or Checkout provider
    # failure. Reusing its reference and idempotency key makes a retry safe even
    # when the first provider response was lost.
    checkout_session = resolved_client.create_subscription_checkout_session(
        customer_id=customer_id,
        price_id=plan.stripe_price_id,
        success_url=success_url,
        cancel_url=cancel_url,
        session_metadata=session_metadata,
        subscription_metadata=session_metadata,
        client_reference_id=_user_reference(user),
        idempotency_key=_build_subscription_checkout_create_idempotency_key(
            reservation_reference
        ),
    )
    checkout_session_id = str(checkout_session.get("id") or "").strip()
    checkout_url = str(checkout_session.get("url") or "").strip()
    if not checkout_session_id:
        raise BillingError(
            "Stripe subscription checkout session creation did not return an id."
        )

    with transaction.atomic():
        _locks._lock_organization_for_billing_mutation(organization)
        reservation = Subscription.all_objects.select_for_update().get(
            pk=reservation.pk
        )
        if not _subscription_reservation_can_be_reused(reservation, plan=plan):
            raise BillingValidationError(_CURRENT_RECURRING_SUBSCRIPTION_ERROR)
        reservation.stripe_customer_id = customer_id
        reservation.stripe_checkout_session_id = checkout_session_id
        reservation.checkout_expires_at = _extract_checkout_session_expires_at(
            checkout_session
        )
        reservation.save(
            update_fields=[
                "stripe_customer_id",
                "stripe_checkout_session_id",
                "checkout_expires_at",
            ]
        )
    if not checkout_url:
        raise BillingError(
            "Stripe subscription checkout session creation did not return a hosted URL."
        )
    return checkout_url


def _find_checkout_reservation(
    organization: Any, *, elapsed_only: bool
) -> Subscription | None:
    """Return the organization's open incomplete checkout reservation, if any."""
    with org_scope(organization):
        reservation_queryset = Subscription.all_objects.filter(
            organization=organization,
            status=Subscription.Status.INCOMPLETE,
        )
        if elapsed_only:
            reservation_queryset = reservation_queryset.filter(
                checkout_expires_at__lte=timezone.now()
            )
        return (
            reservation_queryset.filter(
                Q(stripe_subscription_id__isnull=True) | Q(stripe_subscription_id="")
            )
            .exclude(stripe_checkout_session_id__isnull=True)
            .exclude(stripe_checkout_session_id="")
            .first()
        )


def _expire_provider_expired_reservation(
    organization: Any,
    reservation: Subscription,
    *,
    checkout_session_id: str,
    persist: bool,
) -> str:
    """Expire the matching local reservation when persisting; return customer id."""

    from quickscale_modules_billing._subscription_checkout import (
        _expire_subscription_reservation,
    )

    persisted_customer_id = str(reservation.stripe_customer_id or "").strip()
    if not persist:
        return persisted_customer_id
    with org_scope(organization):
        _locks._lock_organization_for_billing_mutation(organization)
        current_reservation = (
            Subscription.all_objects.select_for_update()
            .filter(pk=reservation.pk)
            .first()
        )
        if (
            current_reservation is not None
            and current_reservation.status == Subscription.Status.INCOMPLETE
            and not str(current_reservation.stripe_subscription_id or "").strip()
            and str(current_reservation.stripe_checkout_session_id or "").strip()
            == checkout_session_id
        ):
            _expire_subscription_reservation(current_reservation)
    return persisted_customer_id


def _persist_completed_checkout_reservation(
    organization: Any,
    reservation: Subscription,
    *,
    checkout_session_payload: Mapping[str, Any],
    checkout_session_id: str,
    provider_subscription_id: str,
    persist: bool,
) -> None:
    """Persist a completed provider checkout onto its local reservation."""
    if not persist:
        return
    with org_scope(organization):
        locked_organization = _locks._lock_organization_for_billing_mutation(
            organization
        )
        current_reservation = (
            Subscription.all_objects.select_for_update()
            .filter(pk=reservation.pk)
            .first()
        )
        if (
            current_reservation is not None
            and current_reservation.status == Subscription.Status.INCOMPLETE
            and not str(current_reservation.stripe_subscription_id or "").strip()
            and str(current_reservation.stripe_checkout_session_id or "").strip()
            == checkout_session_id
        ):
            _validate_completed_checkout_provider_identity(
                reservation=current_reservation,
                organization=locked_organization,
                checkout_session_payload=checkout_session_payload,
            )
            current_reservation.checkout_expires_at = None
            update_fields = ["checkout_expires_at"]
            if provider_subscription_id:
                current_reservation.stripe_subscription_id = provider_subscription_id
                update_fields.append("stripe_subscription_id")
            current_reservation.save(update_fields=update_fields)


def _resolve_checkout_reconciliation_client(
    stripe_client: Any | None,
    settings_snapshot: BillingSettingsSnapshot | None,
) -> Any:
    """Return the settings-validated Stripe client for a checkout read."""
    snapshot = settings_snapshot or BillingSettingsSnapshot.from_settings()
    _ensure_billing_enabled(snapshot)
    return stripe_client or _stripe_client.get_stripe_client(settings_snapshot=snapshot)
