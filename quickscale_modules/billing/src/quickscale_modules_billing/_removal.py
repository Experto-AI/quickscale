"""Organization purge and account-deletion provider obligations.

Implementation detail of :mod:`quickscale_modules_billing.services`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

from typing import Any

from django.apps import apps
from django.db.models import Q
from quickscale_modules_orgs.current_org import org_scope

from quickscale_modules_billing._customers import (
    _resolve_existing_customer_id_for_reconciliation as _resolve_existing_customer_id_for_reconciliation,
)
from quickscale_modules_billing._payload import (
    _extract_checkout_session_expires_at as _extract_checkout_session_expires_at,
)
from quickscale_modules_billing._payload import (
    _normalize_mapping as _normalize_mapping,
)
from quickscale_modules_billing._payload import (
    _purchase_checkout_reference as _purchase_checkout_reference,
)
from quickscale_modules_billing._settings import (
    BillingSettingsSnapshot as BillingSettingsSnapshot,
)
from quickscale_modules_billing._settings import (
    _PURCHASE_CHECKOUT_REFERENCE_METADATA_KEY as _PURCHASE_CHECKOUT_REFERENCE_METADATA_KEY,
)
from quickscale_modules_billing._settings import (
    _ensure_billing_enabled as _ensure_billing_enabled,
)
from quickscale_modules_billing._stripe_client import (
    _translate_stripe_errors as _translate_stripe_errors,
)
from quickscale_modules_billing.exceptions import (
    BillingError,
    BillingValidationError,
)
from quickscale_modules_billing.models import (
    PurchaseCheckout,
    Subscription,
)
import quickscale_modules_billing._stripe_client as _stripe_client
import quickscale_modules_billing._locks as _locks


@_translate_stripe_errors("Stripe purchase checkout reconciliation failed.")
def reconcile_purchase_checkouts_for_removal(
    organization_id: Any,
    *,
    user_id: Any | None = None,
    persist: bool,
    stripe_client: Any | None = None,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> tuple[str, ...]:
    """Require one-time Checkout sessions to be provider-terminal before removal."""
    organization = _organization_for_reconciliation(organization_id)
    if organization is None:
        return ()
    reservations = _pending_purchase_checkouts(organization, user_id=user_id)
    if not reservations:
        return ()
    resolved_client = _resolve_reconciliation_client(stripe_client, settings_snapshot)
    expired_checkout_ids: list[str] = []
    for reservation in reservations:
        expired_checkout_ids.extend(
            _reconcile_purchase_checkout(
                organization,
                reservation,
                persist=persist,
                stripe_client=resolved_client,
            )
        )
    return tuple(expired_checkout_ids)


@_translate_stripe_errors("Stripe purchase checkout reconciliation failed.")
def _reconcile_all_purchase_checkouts(
    organization_id: Any,
    *,
    persist: bool,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Resolve every pending purchase row and collect its refusals.

    The operator pass continues past a reservation that must stay live so a
    later resolvable row is not left behind; removal keeps the fail-fast
    ``reconcile_purchase_checkouts_for_removal`` contract.
    """
    organization = _organization_for_reconciliation(organization_id)
    if organization is None:
        return (), ()
    reservations = _pending_purchase_checkouts(organization)
    if not reservations:
        return (), ()
    resolved_client = _resolve_reconciliation_client(None, settings_snapshot)
    expired_checkout_ids: list[str] = []
    refusals: list[str] = []
    for reservation in reservations:
        try:
            expired_checkout_ids.extend(
                _reconcile_purchase_checkout(
                    organization,
                    reservation,
                    persist=persist,
                    stripe_client=resolved_client,
                )
            )
        except BillingError as exc:
            refusals.append(_refusal_text(exc))
        except _stripe_client._stripe_error_classes() as exc:
            # A provider failure on one reservation must not hide a later
            # resolvable one; the row is left untouched and reported.
            refusals.append(
                "Stripe purchase checkout reconciliation failed for reservation "
                f"{reservation.pk}: {exc}"
            )
    return tuple(expired_checkout_ids), tuple(refusals)


def _organization_for_reconciliation(organization_id: Any) -> Any | None:
    organization_model = apps.get_model(
        "quickscale_orgs",
        "Organization",
    )
    return organization_model._default_manager.filter(pk=organization_id).first()


def _pending_purchase_checkouts(
    organization: Any,
    *,
    user_id: Any | None = None,
) -> list[PurchaseCheckout]:
    with org_scope(organization):
        queryset = PurchaseCheckout.all_objects.filter(
            organization=organization,
            status__in=(
                PurchaseCheckout.Status.PREPARING,
                PurchaseCheckout.Status.OPEN,
            ),
        )
        if user_id is not None:
            queryset = queryset.filter(user_id=user_id)
        return list(queryset.order_by("pk"))


def _resolve_reconciliation_client(
    stripe_client: Any | None,
    settings_snapshot: BillingSettingsSnapshot | None,
) -> Any:
    snapshot = settings_snapshot or BillingSettingsSnapshot.from_settings()
    _ensure_billing_enabled(snapshot)
    return stripe_client or _stripe_client.get_stripe_client(settings_snapshot=snapshot)


def _refusal_text(exc: BillingError) -> str:
    return str(getattr(exc, "detail", "") or exc).strip()


def _reconcile_purchase_checkout(
    organization: Any,
    reservation: PurchaseCheckout,
    *,
    persist: bool,
    stripe_client: Any,
) -> tuple[str, ...]:
    """Resolve one purchase reservation; raise when it must stay blocking."""
    checkout_session_id = str(reservation.stripe_checkout_session_id or "").strip()
    checkout_session: dict[str, Any] | None
    if checkout_session_id:
        checkout_session = _normalize_mapping(
            stripe_client.retrieve_checkout_session(
                checkout_session_id=checkout_session_id,
            )
        )
    else:
        checkout_session = _find_unknown_outcome_checkout_session(
            organization=organization,
            reservation=reservation,
            stripe_client=stripe_client,
        )
        if checkout_session is None:
            # The provider holds no session for this reservation: a definitive
            # rejection or a request that never reached Stripe created nothing,
            # so the unknown-outcome row is closed.
            _void_unknown_outcome_purchase_checkout(
                organization,
                reservation,
                persist=persist,
            )
            return ()
        checkout_session_id = str(checkout_session.get("id") or "").strip()
        if not checkout_session_id:
            raise BillingError(
                "Stripe checkout reconciliation returned a session without an id."
            )
        if persist:
            _adopt_unknown_outcome_purchase_checkout(
                organization,
                reservation,
                checkout_session_id=checkout_session_id,
                checkout_expires_at=_extract_checkout_session_expires_at(
                    checkout_session
                ),
            )
    provider_status = str(checkout_session.get("status") or "").strip().lower()
    if provider_status == "expired":
        if persist:
            with org_scope(organization):
                _locks._lock_organization_for_billing_mutation(organization)
                PurchaseCheckout.all_objects.filter(
                    pk=reservation.pk,
                    status__in=(
                        PurchaseCheckout.Status.PREPARING,
                        PurchaseCheckout.Status.OPEN,
                    ),
                    stripe_checkout_session_id=checkout_session_id,
                ).update(status=PurchaseCheckout.Status.EXPIRED)
        return (checkout_session_id,)
    if provider_status == "open":
        raise BillingValidationError(
            f"Stripe purchase checkout session {checkout_session_id} is still open."
        )
    if provider_status == "complete":
        raise BillingValidationError(
            "Stripe purchase checkout completed and may require credit "
            f"synchronization ({checkout_session_id}); retry removal after its "
            "webhook is processed."
        )
    raise BillingError(
        "Stripe purchase checkout reconciliation returned an unsupported or "
        f"blank status for {checkout_session_id}."
    )


def _find_unknown_outcome_checkout_session(
    *,
    organization: Any,
    reservation: PurchaseCheckout,
    stripe_client: Any,
) -> dict[str, Any] | None:
    """Look a purchase reservation's provider session up by its reference."""
    customer_id = _resolve_existing_customer_id_for_reconciliation(
        organization=organization,
        stripe_client=stripe_client,
    )
    if not customer_id:
        return None
    return stripe_client.find_checkout_session_by_reference(
        customer_id=customer_id,
        metadata_key=_PURCHASE_CHECKOUT_REFERENCE_METADATA_KEY,
        reference=_purchase_checkout_reference(reservation),
    )


def _resolve_definitively_failed_purchase_checkout(
    organization: Any,
    reservation: PurchaseCheckout,
    *,
    customer_id: str,
    stripe_client: Any,
) -> None:
    """Resolve a definitive create rejection against the provider first.

    The rejection proves this attempt created no session; a reused reservation
    may still carry one from an earlier lost response, so the provider is
    checked before the row is closed.  A failed check leaves the unknown
    outcome obligation in place.
    """
    try:
        checkout_session = stripe_client.find_checkout_session_by_reference(
            customer_id=customer_id,
            metadata_key=_PURCHASE_CHECKOUT_REFERENCE_METADATA_KEY,
            reference=_purchase_checkout_reference(reservation),
        )
    except _stripe_client._stripe_error_classes():
        return
    if checkout_session is None:
        _close_definitively_failed_purchase_checkout(organization, reservation)
        return
    checkout_session_id = str(checkout_session.get("id") or "").strip()
    if not checkout_session_id:
        return
    _adopt_unknown_outcome_purchase_checkout(
        organization,
        reservation,
        checkout_session_id=checkout_session_id,
        checkout_expires_at=_extract_checkout_session_expires_at(checkout_session),
    )


def _close_definitively_failed_purchase_checkout(
    organization: Any,
    reservation: PurchaseCheckout,
) -> None:
    """Close a reservation whose provider create the provider itself refused.

    A definitive 4xx answer proves Stripe created no session, so the
    unknown-outcome obligation is cleared instead of blocking later account
    removal; an unknown transport failure keeps the reservation for the
    provider-side reconciliation lookup.
    """
    with org_scope(organization):
        _locks._lock_organization_for_billing_mutation(organization)
        PurchaseCheckout.all_objects.filter(
            pk=reservation.pk,
            status=PurchaseCheckout.Status.PREPARING,
        ).update(status=PurchaseCheckout.Status.EXPIRED)


def _adopt_unknown_outcome_purchase_checkout(
    organization: Any,
    reservation: PurchaseCheckout,
    *,
    checkout_session_id: str,
    checkout_expires_at: Any,
) -> None:
    """Bind the provider session an unknown outcome turned out to be."""
    with org_scope(organization):
        _locks._lock_organization_for_billing_mutation(organization)
        update_fields: dict[str, Any] = {
            "stripe_checkout_session_id": checkout_session_id,
        }
        if checkout_expires_at is not None:
            update_fields["checkout_expires_at"] = checkout_expires_at
        PurchaseCheckout.all_objects.filter(
            pk=reservation.pk,
            status=PurchaseCheckout.Status.PREPARING,
        ).filter(
            Q(stripe_checkout_session_id__isnull=True)
            | Q(stripe_checkout_session_id="")
        ).update(**update_fields)


def _void_unknown_outcome_purchase_checkout(
    organization: Any,
    reservation: PurchaseCheckout,
    *,
    persist: bool,
) -> None:
    """Close a reservation the provider lookup proved created nothing."""
    if not persist:
        return
    with org_scope(organization):
        _locks._lock_organization_for_billing_mutation(organization)
        PurchaseCheckout.all_objects.filter(
            pk=reservation.pk,
            status=PurchaseCheckout.Status.PREPARING,
        ).filter(
            Q(stripe_checkout_session_id__isnull=True)
            | Q(stripe_checkout_session_id="")
        ).update(status=PurchaseCheckout.Status.EXPIRED)


def guard_organization_removal_provider_state(
    organization: Any,
    *,
    provider_expired_checkout_id: str = "",
) -> str:
    """Return the reason an organization purge must refuse, or an empty string.

    The purge boundary declares this hook on billing's obligation
    ``boundary_guarded_hooks`` and calls it while the organization row lock and
    the RLS context are held.  Billing's provider state is live while a current
    subscription carries no provider id to reconcile, while a current
    subscription has not reached a provider-terminal state, or while an
    incomplete subscription checkout Stripe has not confirmed expired is
    pending.  A checkout id the caller reconciled to a provider-confirmed
    expiry is excluded from the pending check.  An empty string means the purge
    may proceed; a non-empty string is the operator-facing refusal.
    """
    current_statuses = Subscription.current_statuses()
    queryset = Subscription.all_objects.filter(organization=organization)
    stripe_subscription_ids = sorted(
        str(subscription_id)
        for subscription_id in queryset.filter(
            status__in=current_statuses,
            stripe_subscription_id__isnull=False,
        )
        .exclude(stripe_subscription_id="")
        .values_list("stripe_subscription_id", flat=True)
    )
    ambiguous_current_subscription = (
        queryset.filter(status__in=current_statuses)
        .exclude(status=Subscription.Status.INCOMPLETE)
        .filter(Q(stripe_subscription_id__isnull=True) | Q(stripe_subscription_id=""))
        .exists()
    )
    pending_checkout_queryset = queryset.filter(
        status=Subscription.Status.INCOMPLETE,
    ).filter(Q(stripe_subscription_id__isnull=True) | Q(stripe_subscription_id=""))
    if provider_expired_checkout_id:
        pending_checkout_queryset = pending_checkout_queryset.exclude(
            stripe_checkout_session_id=provider_expired_checkout_id
        )

    if ambiguous_current_subscription:
        return (
            f"Cannot purge organization {organization.pk} while it has a current "
            "Stripe subscription with no provider id. Reconcile the subscription "
            "before retrying."
        )
    if stripe_subscription_ids:
        joined_ids = ", ".join(stripe_subscription_ids)
        return (
            f"Cannot purge organization {organization.pk} while it has current "
            f"Stripe subscriptions: {joined_ids}. Cancel these subscriptions in "
            "Stripe before retrying."
        )
    if pending_checkout_queryset.exists():
        return (
            f"Cannot purge organization {organization.pk} while a Stripe "
            "subscription checkout is pending. Complete or expire the checkout "
            "before retrying."
        )
    return ""


def account_deletion_user_reference_organization_ids(user_id: Any) -> list[Any]:
    """Discover every organization retaining billing provenance for one user.

    Account removal reconciles the one-time purchase state that stays
    attributed to the person in organizations they have left, so it discovers
    the organizations through orgs' narrow read-only seam and then locks and
    reconciles each one.  Nothing is detached: the account row is retained.
    """
    from quickscale_modules_orgs.current_org import (
        account_deletion_user_reference_organization_ids as discover_organization_ids,
    )

    organization_ids = discover_organization_ids(
        user_id,
        included_app_labels=frozenset({"quickscale_billing"}),
    )
    return sorted(organization_ids, key=str)
