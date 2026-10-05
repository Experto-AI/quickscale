"""Subscription Checkout creation, reconciliation, and reservations.

Implementation detail of :mod:`quickscale_modules_billing.services`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

from typing import Any

from django.apps import apps
from django.db import IntegrityError, transaction
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
    _extract_live_checkout_session_url as _extract_live_checkout_session_url,
)
from quickscale_modules_billing._payload import (
    _normalize_mapping as _normalize_mapping,
)
from quickscale_modules_billing._payload import (
    _stripe_object_id as _stripe_object_id,
)
from quickscale_modules_billing._payload import (
    _subscription_checkout_reference as _subscription_checkout_reference,
)
from quickscale_modules_billing._payload import (
    _user_reference as _user_reference,
)
from quickscale_modules_billing._settings import (
    _CURRENT_RECURRING_SUBSCRIPTION_ERROR as _CURRENT_RECURRING_SUBSCRIPTION_ERROR,
)
from quickscale_modules_billing._settings import (
    _SUBSCRIPTION_CHECKOUT_REFERENCE_METADATA_KEY as _SUBSCRIPTION_CHECKOUT_REFERENCE_METADATA_KEY,
)
from quickscale_modules_billing._settings import (
    BillingSettingsSnapshot as BillingSettingsSnapshot,
)
from quickscale_modules_billing._settings import (
    SubscriptionCheckoutReconciliation as SubscriptionCheckoutReconciliation,
)
from quickscale_modules_billing._settings import (
    _ensure_billing_enabled as _ensure_billing_enabled,
)
from quickscale_modules_billing._stripe_client import (
    _stripe_error_classes as _stripe_error_classes,
)
from quickscale_modules_billing._stripe_client import (
    _translate_stripe_errors as _translate_stripe_errors,
)
from quickscale_modules_billing._subscription_mutations import (
    _require_owner_provider_mutation_authorization as _require_owner_provider_mutation_authorization,
)
from quickscale_modules_billing._validation import (
    _validate_completed_checkout_provider_identity as _validate_completed_checkout_provider_identity,
)
from quickscale_modules_billing._validation import (
    _validate_recurring_subscription_plan as _validate_recurring_subscription_plan,
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
    Subscription,
)
import quickscale_modules_billing._locks as _locks
import quickscale_modules_billing._stripe_client as _stripe_client


from quickscale_modules_billing._subscription_checkout_steps import (
    _create_and_persist_checkout_session as _create_and_persist_checkout_session,
)
from quickscale_modules_billing._subscription_checkout_steps import (
    _expire_provider_expired_reservation as _expire_provider_expired_reservation,
)
from quickscale_modules_billing._subscription_checkout_steps import (
    _find_checkout_reservation as _find_checkout_reservation,
)
from quickscale_modules_billing._subscription_checkout_steps import (
    _initial_subscription_checkout_reservation as _initial_subscription_checkout_reservation,
)
from quickscale_modules_billing._subscription_checkout_steps import (
    _persist_completed_checkout_reservation as _persist_completed_checkout_reservation,
)
from quickscale_modules_billing._subscription_checkout_steps import (
    _replace_stale_checkout_reservation as _replace_stale_checkout_reservation,
)
from quickscale_modules_billing._subscription_checkout_steps import (
    _reservation_customer_id as _reservation_customer_id,
)
from quickscale_modules_billing._subscription_checkout_steps import (
    _resolve_checkout_reconciliation_client as _resolve_checkout_reconciliation_client,
)


def create_subscription_checkout_session(
    user: Any,
    *,
    plan: Plan,
    success_url: str,
    cancel_url: str,
    organization: Any,
    stripe_client: Any | None = None,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> str:
    """Serialize recurring Checkout creation with account deletion mutations."""
    try:
        with _locks.subscription_provider_mutation_lock(organization):
            user, organization = _require_owner_provider_mutation_authorization(
                user,
                organization,
            )
            return _create_subscription_checkout_session(
                user,
                plan,
                success_url,
                cancel_url,
                organization=organization,
                stripe_client=stripe_client,
                settings_snapshot=settings_snapshot,
            )
    except _stripe_error_classes() as exc:
        raise BillingError(
            "Stripe subscription checkout session creation failed."
        ) from exc


def _create_subscription_checkout_session(
    user: Any,
    plan: Plan,
    success_url: str,
    cancel_url: str,
    *,
    organization: Any,
    stripe_client: Any | None = None,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> str:
    """Create or reuse one recurring Checkout Session while its mutex is held."""
    snapshot = settings_snapshot or BillingSettingsSnapshot.from_settings()
    _ensure_billing_enabled(snapshot)

    normalized_success_url = success_url.strip()
    normalized_cancel_url = cancel_url.strip()
    if not normalized_success_url or not normalized_cancel_url:
        raise BillingValidationError("Checkout success and cancel URLs are required.")

    _validate_recurring_subscription_plan(plan)

    resolved_client = stripe_client or _stripe_client.get_stripe_client(
        settings_snapshot=snapshot
    )
    stripe_price = resolved_client.retrieve_price(price_id=plan.stripe_price_id)
    _validate_stripe_price_parity(plan=plan, stripe_price=stripe_price)
    reconciled_customer_id = reconcile_elapsed_subscription_checkout(
        organization.pk,
        stripe_client=resolved_client,
        settings_snapshot=snapshot,
    )

    reservation = _initial_subscription_checkout_reservation(
        user=user,
        organization=organization,
        plan=plan,
        stripe_customer_id=reconciled_customer_id or None,
    )
    reservation, customer_id = _reservation_customer_id(
        reservation,
        user=user,
        organization=organization,
        plan=plan,
        resolved_client=resolved_client,
        snapshot=snapshot,
    )
    live_checkout_url = _reuse_live_subscription_checkout_url(
        reservation=reservation,
        stripe_client=resolved_client,
    )
    if live_checkout_url:
        return live_checkout_url

    reservation, live_checkout_url = _replace_stale_checkout_reservation(
        reservation,
        user=user,
        organization=organization,
        plan=plan,
        customer_id=customer_id,
        resolved_client=resolved_client,
    )
    # A replacement reservation carries its own provider customer id.
    customer_id = str(reservation.stripe_customer_id or "").strip()
    if live_checkout_url:
        return live_checkout_url

    return _create_and_persist_checkout_session(
        user=user,
        plan=plan,
        organization=organization,
        reservation=reservation,
        customer_id=customer_id,
        resolved_client=resolved_client,
        success_url=normalized_success_url,
        cancel_url=normalized_cancel_url,
    )


@_translate_stripe_errors("Stripe subscription checkout reconciliation failed.")
def reconcile_elapsed_subscription_checkout(
    organization_id: Any,
    *,
    stripe_client: Any | None = None,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> str:
    """Normalize an elapsed checkout only after Stripe confirms it is terminal."""
    result = _reconcile_subscription_checkout(
        organization_id,
        elapsed_only=True,
        persist=True,
        stripe_client=stripe_client,
        settings_snapshot=settings_snapshot,
    )
    return result.stripe_customer_id


@_translate_stripe_errors("Stripe subscription checkout reconciliation failed.")
def reconcile_organization_removal_subscription_checkout(
    organization_id: Any,
    *,
    persist: bool,
    stripe_client: Any | None = None,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> SubscriptionCheckoutReconciliation:
    """Inspect an elapsed checkout and optionally persist terminal provider state."""
    return _reconcile_subscription_checkout(
        organization_id,
        elapsed_only=True,
        persist=persist,
        stripe_client=stripe_client,
        settings_snapshot=settings_snapshot,
    )


@_translate_stripe_errors("Stripe subscription checkout reconciliation failed.")
def reconcile_account_deletion_subscription_checkout(
    organization_id: Any,
    *,
    stripe_client: Any | None = None,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> SubscriptionCheckoutReconciliation:
    """Require a hosted checkout to be provider-terminal before account deletion."""
    return _reconcile_subscription_checkout(
        organization_id,
        elapsed_only=False,
        persist=True,
        stripe_client=stripe_client,
        settings_snapshot=settings_snapshot,
    )


def _reconcile_subscription_checkout(
    organization_id: Any,
    *,
    elapsed_only: bool,
    persist: bool,
    stripe_client: Any | None,
    settings_snapshot: BillingSettingsSnapshot | None,
) -> SubscriptionCheckoutReconciliation:
    """Read one checkout from Stripe and persist it only when requested."""
    organization_model = apps.get_model(
        "quickscale_orgs",
        "Organization",
    )
    organization = organization_model._default_manager.filter(
        pk=organization_id
    ).first()
    if organization is None:
        return SubscriptionCheckoutReconciliation()

    reservation = _find_checkout_reservation(organization, elapsed_only=elapsed_only)
    if reservation is None:
        return SubscriptionCheckoutReconciliation()

    resolved_client = _resolve_checkout_reconciliation_client(
        stripe_client, settings_snapshot
    )
    checkout_session_id = str(reservation.stripe_checkout_session_id or "").strip()
    checkout_session = _normalize_mapping(
        resolved_client.retrieve_checkout_session(
            checkout_session_id=checkout_session_id,
        )
    )
    provider_status = str(checkout_session.get("status") or "").strip().lower()
    if provider_status == "expired":
        persisted_customer_id = _expire_provider_expired_reservation(
            organization,
            reservation,
            checkout_session_id=checkout_session_id,
            persist=persist,
        )
        return SubscriptionCheckoutReconciliation(
            provider_status=provider_status,
            checkout_session_id=checkout_session_id,
            stripe_customer_id=persisted_customer_id,
        )

    provider_subscription_id = _stripe_object_id(checkout_session.get("subscription"))
    if provider_status == "complete":
        _validate_completed_checkout_provider_identity(
            reservation=reservation,
            organization=organization,
            checkout_session_payload=checkout_session,
        )
        _persist_completed_checkout_reservation(
            organization,
            reservation,
            checkout_session_payload=checkout_session,
            checkout_session_id=checkout_session_id,
            provider_subscription_id=provider_subscription_id,
            persist=persist,
        )
        provider_label = provider_subscription_id or checkout_session_id
        raise BillingValidationError(
            "Stripe checkout completed and may have created a live subscription "
            f"({provider_label}); wait for subscription synchronization or "
            "reconcile it before changing billing or organization state."
        )

    if provider_status == "open":
        raise BillingValidationError(
            f"Stripe checkout session {checkout_session_id} is still open."
        )
    raise BillingError(
        "Stripe checkout session reconciliation returned an unsupported or blank "
        f"status for {checkout_session_id}."
    )


def _resolve_authoritative_subscription_reservation(
    *,
    organization: Any | None = None,
    customer_id: str = "",
    for_update: bool = False,
) -> Subscription | None:
    normalized_customer_id = customer_id.strip()
    if organization is None and not normalized_customer_id:
        return None

    queryset = Subscription.all_objects.order_by("-pk")
    if not for_update:
        queryset = queryset.select_related("user", "plan")
    if for_update:
        queryset = queryset.select_for_update()
    if organization is not None:
        queryset = queryset.filter(organization=organization)
    if normalized_customer_id:
        queryset = queryset.filter(
            Q(stripe_customer_id=normalized_customer_id)
            | Q(organization__stripe_customer_id=normalized_customer_id)
        )
    return queryset.filter(Subscription.current_status_q()).first()


def _subscription_reservation_can_be_reused(
    reservation: Subscription,
    *,
    plan: Plan,
) -> bool:
    if reservation.plan.pk != plan.pk:
        return False
    if reservation.status != Subscription.Status.INCOMPLETE:
        return False
    return not str(reservation.stripe_subscription_id or "").strip()


def _subscription_reservation_needs_replacement(
    reservation: Subscription,
) -> bool:
    checkout_session_id = str(reservation.stripe_checkout_session_id or "").strip()
    if not checkout_session_id:
        return False
    if reservation.checkout_expires_at is None:
        return False
    return reservation.checkout_expires_at <= timezone.now()


def _expire_subscription_reservation(reservation: Subscription) -> None:
    reservation.status = Subscription.Status.INCOMPLETE_EXPIRED
    reservation.save(update_fields=["status"])


def _create_subscription_reservation(
    *,
    user: Any,
    organization: Any,
    plan: Plan,
    stripe_customer_id: str | None = None,
) -> tuple[Subscription, bool]:
    try:
        with transaction.atomic():
            return (
                Subscription.all_objects.create(
                    user=user,
                    organization=organization,
                    plan=plan,
                    stripe_customer_id=stripe_customer_id,
                    status=Subscription.Status.INCOMPLETE,
                ),
                False,
            )
    except IntegrityError as exc:
        recovered_reservation = _recover_conflicting_subscription_reservation(
            user=user,
            organization=organization,
            plan=plan,
        )
        if recovered_reservation is not None:
            return recovered_reservation, True
        raise BillingValidationError(_CURRENT_RECURRING_SUBSCRIPTION_ERROR) from exc


def _recover_conflicting_subscription_reservation(
    *,
    user: Any,
    organization: Any | None,
    plan: Plan,
) -> Subscription | None:
    with transaction.atomic():
        _locks._lock_organization_for_billing_mutation(organization)
        current_reservation = _resolve_authoritative_subscription_reservation(
            organization=organization,
            for_update=True,
        )
        if current_reservation is None:
            return None
        if not _subscription_reservation_can_be_reused(current_reservation, plan=plan):
            return None
        if _subscription_reservation_needs_replacement(current_reservation):
            return None
        return current_reservation


def _prepare_subscription_checkout_reservation(
    *,
    user: Any,
    organization: Any,
    plan: Plan,
    stripe_customer_id: str | None = None,
) -> tuple[Subscription, bool]:
    _locks._lock_organization_for_billing_mutation(organization)
    current_reservation = _resolve_authoritative_subscription_reservation(
        organization=organization,
        for_update=True,
    )
    if current_reservation is None:
        return _create_subscription_reservation(
            user=user,
            organization=organization,
            plan=plan,
            stripe_customer_id=stripe_customer_id,
        )

    if not _subscription_reservation_can_be_reused(current_reservation, plan=plan):
        raise BillingValidationError(_CURRENT_RECURRING_SUBSCRIPTION_ERROR)

    if _subscription_reservation_needs_replacement(current_reservation):
        persisted_customer_id = str(
            current_reservation.stripe_customer_id or ""
        ).strip()
        _expire_subscription_reservation(current_reservation)
        return _create_subscription_reservation(
            user=user,
            organization=organization,
            plan=plan,
            stripe_customer_id=persisted_customer_id or None,
        )

    return current_reservation, not bool(
        str(current_reservation.stripe_checkout_session_id or "").strip()
    )


def _reuse_live_subscription_checkout_url(
    *,
    reservation: Subscription,
    stripe_client: Any,
) -> str:
    checkout_session_id = str(reservation.stripe_checkout_session_id or "").strip()
    if not checkout_session_id:
        return ""
    if not hasattr(stripe_client, "retrieve_checkout_session"):
        raise BillingError(
            "Stripe checkout retrieval is unavailable; the existing subscription "
            "checkout cannot be replaced safely."
        )

    checkout_session = _normalize_mapping(
        stripe_client.retrieve_checkout_session(
            checkout_session_id=checkout_session_id,
        )
    )
    provider_status = str(checkout_session.get("status") or "").strip().lower()
    if provider_status == "expired":
        return ""
    if provider_status == "complete":
        provider_subscription_id = _stripe_object_id(
            checkout_session.get("subscription")
        )
        with org_scope(reservation.organization):
            locked_organization = _locks._lock_organization_for_billing_mutation(
                reservation.organization
            )
            current_reservation = (
                Subscription.all_objects.select_for_update()
                .filter(
                    pk=reservation.pk,
                    stripe_checkout_session_id=checkout_session_id,
                )
                .first()
            )
            if current_reservation is None:
                raise BillingValidationError(_CURRENT_RECURRING_SUBSCRIPTION_ERROR)
            _validate_completed_checkout_provider_identity(
                reservation=current_reservation,
                organization=locked_organization,
                checkout_session_payload=checkout_session,
            )
            existing_subscription_id = str(
                current_reservation.stripe_subscription_id or ""
            ).strip()
            update_fields: list[str] = []
            if provider_subscription_id and not existing_subscription_id:
                current_reservation.stripe_subscription_id = provider_subscription_id
                update_fields.append("stripe_subscription_id")
            if current_reservation.checkout_expires_at is not None:
                current_reservation.checkout_expires_at = None
                update_fields.append("checkout_expires_at")
            if update_fields:
                current_reservation.save(update_fields=update_fields)
        provider_label = provider_subscription_id or checkout_session_id
        raise BillingValidationError(
            "Stripe checkout completed and may have created a live subscription "
            f"({provider_label}); wait for subscription synchronization or "
            "reconcile it before creating another checkout."
        )
    if provider_status != "open":
        raise BillingError(
            "Stripe checkout session reconciliation returned an unsupported or "
            f"blank status for {checkout_session_id}."
        )

    checkout_url = _extract_live_checkout_session_url(checkout_session)
    if not checkout_url:
        raise BillingError(
            "Stripe reports the existing subscription checkout as open but did not "
            "return a reusable hosted URL; automatic replacement was refused."
        )
    return checkout_url
