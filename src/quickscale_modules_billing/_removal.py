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

from quickscale_modules_billing._payload import (
    _normalize_mapping as _normalize_mapping,
)
from quickscale_modules_billing._settings import (
    BillingSettingsSnapshot as BillingSettingsSnapshot,
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
    organization_model = apps.get_model(
        "quickscale_orgs",
        "Organization",
    )
    organization = organization_model._default_manager.filter(
        pk=organization_id
    ).first()
    if organization is None:
        return ()

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
        reservations = list(queryset.order_by("pk"))
    if not reservations:
        return ()

    snapshot = settings_snapshot or BillingSettingsSnapshot.from_settings()
    _ensure_billing_enabled(snapshot)
    resolved_client = stripe_client or _stripe_client.get_stripe_client(
        settings_snapshot=snapshot
    )
    expired_checkout_ids: list[str] = []
    for reservation in reservations:
        checkout_session_id = str(reservation.stripe_checkout_session_id or "").strip()
        if not checkout_session_id:
            raise BillingError(
                "A Stripe purchase checkout is still being prepared or its creation "
                "outcome is unknown; reconcile provider state before retrying removal."
            )
        checkout_session = _normalize_mapping(
            resolved_client.retrieve_checkout_session(
                checkout_session_id=checkout_session_id,
            )
        )
        provider_status = str(checkout_session.get("status") or "").strip().lower()
        if provider_status == "expired":
            expired_checkout_ids.append(checkout_session_id)
            if persist:
                with org_scope(organization):
                    _locks._lock_organization_for_billing_mutation(organization)
                    PurchaseCheckout.all_objects.filter(
                        pk=reservation.pk,
                        status=PurchaseCheckout.Status.OPEN,
                        stripe_checkout_session_id=checkout_session_id,
                    ).update(status=PurchaseCheckout.Status.EXPIRED)
            continue
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
    return tuple(expired_checkout_ids)


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
