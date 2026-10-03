"""Subscription cancellation, resumption, and provider snapshots.

Implementation detail of :mod:`quickscale_modules_billing.services`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from django.apps import apps
from django.conf import settings
from quickscale_modules_orgs.current_org import org_scope

from quickscale_modules_billing._payload import (
    _extract_subscription_period_bounds as _extract_subscription_period_bounds,
)
from quickscale_modules_billing._payload import (
    _map_stripe_subscription_status as _map_stripe_subscription_status,
)
from quickscale_modules_billing._settings import (
    BillingSettingsSnapshot as BillingSettingsSnapshot,
)
from quickscale_modules_billing._settings import (
    SubscriptionCancellationTransition as SubscriptionCancellationTransition,
)
from quickscale_modules_billing._settings import (
    SubscriptionProviderIdentity as SubscriptionProviderIdentity,
)
from quickscale_modules_billing._settings import (
    _ensure_billing_enabled as _ensure_billing_enabled,
)
from quickscale_modules_billing._stripe_client import (
    _translate_stripe_errors as _translate_stripe_errors,
)
from quickscale_modules_billing.exceptions import (
    BillingError,
    BillingSubscriptionAnomalyError,
    BillingValidationError,
    BillingWebhookError,
)
from quickscale_modules_billing.models import (
    Subscription,
)
import quickscale_modules_billing._locks as _locks
import quickscale_modules_billing._stripe_client as _stripe_client

logger = logging.getLogger(__name__)


@_translate_stripe_errors("Stripe subscription cancellation failed.")
def cancel_current_subscription(
    user: Any,
    *,
    organization: Any,
    stripe_client: Any | None = None,
    settings_snapshot: BillingSettingsSnapshot | None = None,
    capture_transition: bool = False,
) -> Subscription | SubscriptionCancellationTransition | None:
    """Schedule the organization's current Stripe-backed subscription to end after the period."""
    with _locks.subscription_provider_mutation_lock(organization):
        _, organization = _require_owner_provider_mutation_authorization(
            user,
            organization,
        )
        if capture_transition:
            return _cancel_current_subscription_with_transition(
                organization=organization,
                stripe_client=stripe_client,
                settings_snapshot=settings_snapshot,
            )
        return _set_current_subscription_cancel_at_period_end(
            organization=organization,
            cancel_at_period_end=True,
            stripe_client=stripe_client,
            settings_snapshot=settings_snapshot,
        )


@_translate_stripe_errors("Stripe subscription resumption failed.")
def resume_current_subscription(
    user: Any,
    *,
    organization: Any,
    stripe_client: Any | None = None,
    settings_snapshot: BillingSettingsSnapshot | None = None,
    transition: SubscriptionCancellationTransition | None = None,
) -> Subscription:
    """Undo a scheduled cancellation when account deletion is rejected."""
    with _locks.subscription_provider_mutation_lock(organization):
        if transition is not None:
            # This is compensation for an already-authorized cancellation, not
            # a new user mutation. Restore only the captured provider identity.
            if transition.organization_id != getattr(
                organization,
                "pk",
                organization,
            ):
                raise BillingValidationError(
                    "The cancellation transition does not belong to this organization."
                )
            return _restore_subscription_cancellation_transition(
                transition,
                stripe_client=stripe_client,
                settings_snapshot=settings_snapshot,
            )
        _, organization = _require_owner_provider_mutation_authorization(
            user,
            organization,
        )
        return _set_current_subscription_cancel_at_period_end(
            organization=organization,
            cancel_at_period_end=False,
            stripe_client=stripe_client,
            settings_snapshot=settings_snapshot,
        )


def _require_owner_provider_mutation_authorization(
    user: Any,
    organization: Any,
) -> tuple[Any, Any]:
    """Revalidate an owner actor after waiting for the provider mutex."""
    user_pk = getattr(user, "pk", None)
    organization_pk = getattr(organization, "pk", organization)
    if user_pk is None or organization_pk is None:
        raise BillingValidationError(
            "Billing authorization changed while the provider mutation was waiting."
        )

    user_model = apps.get_model(settings.AUTH_USER_MODEL)
    organization_model = apps.get_model(
        "quickscale_orgs",
        "Organization",
    )
    membership_model = apps.get_model(
        "quickscale_orgs",
        "OrganizationMembership",
    )
    current_user = user_model._default_manager.filter(pk=user_pk).first()
    current_organization = organization_model._default_manager.filter(
        pk=organization_pk
    ).first()
    if (
        current_user is None
        or current_organization is None
        or not bool(getattr(current_user, "is_active", True))
    ):
        raise BillingValidationError(
            "Billing authorization changed while the provider mutation was waiting."
        )
    if not bool(getattr(current_user, "is_superuser", False)) and not (
        membership_model._default_manager.filter(
            user=current_user,
            organization=current_organization,
            role="owner",
        ).exists()
    ):
        raise BillingValidationError(
            "Billing authorization changed while the provider mutation was waiting."
        )
    return current_user, current_organization


def _cancel_current_subscription_with_transition(
    *,
    organization: Any,
    stripe_client: Any | None,
    settings_snapshot: BillingSettingsSnapshot | None,
) -> SubscriptionCancellationTransition | None:
    """Cancel only after recording the exact provider state to restore."""
    snapshot = settings_snapshot or BillingSettingsSnapshot.from_settings()
    # Imported lazily: _subscription_checkout imports this module at load time.
    import quickscale_modules_billing._subscription_checkout as _subscription_checkout

    with org_scope(organization):
        subscription = (
            _subscription_checkout._resolve_authoritative_subscription_reservation(
                organization=organization,
            )
        )
    if subscription is None:
        return None
    _ensure_billing_enabled(snapshot)

    stripe_subscription_id = str(subscription.stripe_subscription_id or "").strip()
    if not stripe_subscription_id:
        raise BillingSubscriptionAnomalyError(
            "Current recurring subscription is missing a Stripe subscription id."
        )

    resolved_client = stripe_client or _stripe_client.get_stripe_client(
        settings_snapshot=snapshot
    )
    remote_subscription = resolved_client.retrieve_subscription(
        stripe_subscription_id=stripe_subscription_id,
    )
    previous_cancel_state = remote_subscription.get("cancel_at_period_end")
    if not isinstance(previous_cancel_state, bool):
        raise BillingError(
            "Stripe subscription payload is missing its period-end cancellation state."
        )

    transition = SubscriptionCancellationTransition(
        subscription_pk=subscription.pk,
        organization_id=organization.pk,
        stripe_subscription_id=stripe_subscription_id,
        previous_cancel_at_period_end=previous_cancel_state,
    )
    if not transition.changed:
        return transition

    try:
        updated_subscription = resolved_client.cancel_subscription(
            stripe_subscription_id=transition.stripe_subscription_id,
        )
        _persist_subscription_provider_snapshot(
            subscription,
            updated_subscription,
            expected_identity=transition.identity,
        )
    except Exception:
        try:
            _restore_subscription_cancellation_transition(
                transition,
                stripe_client=resolved_client,
                settings_snapshot=snapshot,
            )
        except Exception:
            logger.exception(
                "Failed to restore Stripe subscription %s after an account-delete "
                "cancellation error; manual reconciliation is required.",
                stripe_subscription_id,
            )
        raise
    return transition


def _restore_subscription_cancellation_transition(
    transition: SubscriptionCancellationTransition,
    *,
    stripe_client: Any | None,
    settings_snapshot: BillingSettingsSnapshot | None,
) -> Subscription:
    """Restore the exact subscription changed by a cancellation transition."""
    organization_model = apps.get_model(
        "quickscale_orgs",
        "Organization",
    )
    organization = organization_model._default_manager.filter(
        pk=transition.organization_id
    ).first()
    if organization is None:
        raise BillingError(
            "The captured Stripe subscription cannot be restored because its "
            "organization no longer exists."
        )
    if not transition.changed:
        with org_scope(organization):
            return Subscription.all_objects.get(pk=transition.subscription_pk)

    snapshot = settings_snapshot or BillingSettingsSnapshot.from_settings()
    _ensure_billing_enabled(snapshot)
    resolved_client = stripe_client or _stripe_client.get_stripe_client(
        settings_snapshot=snapshot
    )
    updated_subscription = resolved_client.resume_subscription(
        stripe_subscription_id=transition.stripe_subscription_id,
    )
    with org_scope(organization):
        try:
            subscription = Subscription.all_objects.get(pk=transition.subscription_pk)
        except Subscription.DoesNotExist as exc:
            raise BillingError(
                "The captured Stripe subscription was restored, but its local row no "
                "longer exists; no local provider snapshot was written."
            ) from exc
    return _persist_subscription_provider_snapshot(
        subscription,
        updated_subscription,
        expected_identity=transition.identity,
        skip_stale_identity=True,
    )


def _set_current_subscription_cancel_at_period_end(
    *,
    organization: Any,
    cancel_at_period_end: bool,
    stripe_client: Any | None,
    settings_snapshot: BillingSettingsSnapshot | None,
) -> Subscription:
    """Reconcile one organization's period-end cancellation state."""
    snapshot = settings_snapshot or BillingSettingsSnapshot.from_settings()
    # Imported lazily: _subscription_checkout imports this module at load time.
    import quickscale_modules_billing._subscription_checkout as _subscription_checkout

    with org_scope(organization):
        subscription = (
            _subscription_checkout._resolve_authoritative_subscription_reservation(
                organization=organization,
            )
        )
    if subscription is None:
        raise BillingValidationError(
            "Organization does not have a current recurring subscription."
        )
    _ensure_billing_enabled(snapshot)

    stripe_subscription_id = str(subscription.stripe_subscription_id or "").strip()
    if not stripe_subscription_id:
        raise BillingSubscriptionAnomalyError(
            "Current recurring subscription is missing a Stripe subscription id."
        )

    resolved_client = stripe_client or _stripe_client.get_stripe_client(
        settings_snapshot=snapshot
    )
    expected_identity = SubscriptionProviderIdentity(
        subscription_pk=subscription.pk,
        organization_id=subscription.organization_id,
        stripe_subscription_id=stripe_subscription_id,
    )
    if cancel_at_period_end:
        updated_subscription = resolved_client.cancel_subscription(
            stripe_subscription_id=stripe_subscription_id,
        )
    else:
        updated_subscription = resolved_client.resume_subscription(
            stripe_subscription_id=stripe_subscription_id,
        )

    return _persist_subscription_provider_snapshot(
        subscription,
        updated_subscription,
        expected_identity=expected_identity,
    )


def _persist_subscription_provider_snapshot(
    subscription: Subscription,
    updated_subscription: Mapping[str, Any],
    *,
    expected_identity: SubscriptionProviderIdentity,
    skip_stale_identity: bool = False,
) -> Subscription:
    """Persist one provider subscription response on the exact local row."""
    remote_subscription_id = str(updated_subscription.get("id") or "").strip()
    if (
        remote_subscription_id
        and remote_subscription_id != expected_identity.stripe_subscription_id
    ):
        raise BillingError(
            "Stripe returned a different subscription than the captured transition; "
            "automatic reconciliation was refused."
        )
    remote_status = str(updated_subscription.get("status") or "").strip().lower()
    if remote_status:
        try:
            local_status = _map_stripe_subscription_status(remote_status)
        except BillingWebhookError as exc:
            raise BillingError(str(exc)) from exc
    else:
        local_status = subscription.status

    current_period_start, current_period_end = _extract_subscription_period_bounds(
        updated_subscription
    )

    organization_model = apps.get_model(
        "quickscale_orgs",
        "Organization",
    )
    organization = organization_model._default_manager.filter(
        pk=expected_identity.organization_id
    ).first()
    if organization is None:
        raise BillingError(
            "The captured subscription organization no longer exists; automatic "
            "provider snapshot persistence was refused."
        )

    with org_scope(organization):
        _locks._lock_organization_for_billing_mutation(
            expected_identity.organization_id
        )
        subscription = Subscription.all_objects.select_for_update().get(
            pk=subscription.pk
        )
        identity_is_stale = (
            subscription.pk != expected_identity.subscription_pk
            or subscription.organization_id != expected_identity.organization_id
            or str(subscription.stripe_subscription_id or "").strip()
            != expected_identity.stripe_subscription_id
        )
        if identity_is_stale and skip_stale_identity:
            logger.warning(
                "Restored Stripe subscription %s but skipped its stale local "
                "snapshot because subscription row %s changed identity.",
                expected_identity.stripe_subscription_id,
                expected_identity.subscription_pk,
            )
            return subscription
        if identity_is_stale:
            raise BillingError(
                "The captured subscription changed before provider state could be "
                "persisted; automatic reconciliation was refused."
            )
        subscription.status = local_status
        subscription.stripe_subscription_id = (
            remote_subscription_id or subscription.stripe_subscription_id
        )
        subscription.stripe_customer_id = (
            str(updated_subscription.get("customer") or "").strip()
            or subscription.stripe_customer_id
        )
        subscription.current_period_start = (
            current_period_start or subscription.current_period_start
        )
        subscription.current_period_end = (
            current_period_end or subscription.current_period_end
        )
        subscription.save(
            update_fields=[
                "status",
                "stripe_subscription_id",
                "stripe_customer_id",
                "current_period_start",
                "current_period_end",
            ]
        )
    return subscription
