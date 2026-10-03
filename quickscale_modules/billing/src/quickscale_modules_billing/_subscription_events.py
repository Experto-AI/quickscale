"""Subscription payload upsert from webhook events.

Implementation detail of :mod:`quickscale_modules_billing.services`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from quickscale_modules_orgs.current_org import org_scope

from quickscale_modules_billing._customers import (
    _sync_organization_customer_id as _sync_organization_customer_id,
)
from quickscale_modules_billing._payload import (
    _extract_event_object as _extract_event_object,
)
from quickscale_modules_billing._payload import (
    _extract_subscription_period_bounds as _extract_subscription_period_bounds,
)
from quickscale_modules_billing._payload import (
    _map_stripe_subscription_status as _map_stripe_subscription_status,
)
from quickscale_modules_billing._resolution import (
    _resolve_user_for_subscription as _resolve_user_for_subscription,
)
from quickscale_modules_billing._settings import (
    STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_DELETED as STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_DELETED,
)
from quickscale_modules_billing._settings import (
    SubscriptionProviderIdentity as SubscriptionProviderIdentity,
)
from quickscale_modules_billing.exceptions import (
    BillingWebhookError,
)
from quickscale_modules_billing.models import (
    Plan,
    Subscription,
)
import quickscale_modules_billing._resolution as _resolution
import quickscale_modules_billing._locks as _locks


def _upsert_subscription_from_payload(
    subscription_payload: Mapping[str, Any],
    *,
    fallback_user: Any | None = None,
    fallback_organization: Any | None = None,
    expected_plan: Plan | None = None,
    fallback_status: str = "",
    provider_lock_held: bool = False,
) -> Subscription:
    stripe_subscription_id = str(subscription_payload.get("id") or "").strip()
    if not stripe_subscription_id:
        raise BillingWebhookError("Stripe subscription payload is missing an id.")

    stripe_status = str(subscription_payload.get("status") or "").strip().lower()
    if not stripe_status:
        stripe_status = fallback_status.strip().lower()
    local_status = _map_stripe_subscription_status(stripe_status)

    plan = _resolution._resolve_plan_for_subscription_payload(subscription_payload)
    if expected_plan is not None and plan.pk != expected_plan.pk:
        raise BillingWebhookError(
            "Stripe subscription does not match the invoiced billing plan."
        )

    organization = _resolution._resolve_organization_for_subscription(
        subscription_payload=subscription_payload
    )
    if (
        organization is not None
        and fallback_organization is not None
        and organization.pk != fallback_organization.pk
    ):
        raise BillingWebhookError(
            "Stripe subscription organization conflicts with the locked billing "
            "organization."
        )
    if organization is None:
        organization = fallback_organization
    if organization is None:
        raise BillingWebhookError(
            "Could not resolve a local organization for the Stripe subscription."
        )
    if provider_lock_held:
        return _apply_subscription_payload(
            subscription_payload=subscription_payload,
            stripe_subscription_id=stripe_subscription_id,
            local_status=local_status,
            plan=plan,
            organization=organization,
            fallback_user=fallback_user,
        )
    with _locks.subscription_provider_mutation_lock(organization):
        return _apply_subscription_payload(
            subscription_payload=subscription_payload,
            stripe_subscription_id=stripe_subscription_id,
            local_status=local_status,
            plan=plan,
            organization=organization,
            fallback_user=fallback_user,
        )


def _apply_subscription_payload(
    *,
    subscription_payload: Mapping[str, Any],
    stripe_subscription_id: str,
    local_status: str,
    plan: Plan,
    organization: Any,
    fallback_user: Any | None,
) -> Subscription:
    """Apply a subscription payload while its provider mutex is held."""

    # Phase 3: each handler owns its org scope for SET LOCAL support.
    with org_scope(organization):
        organization = _locks._lock_organization_for_billing_mutation(organization)
        user = _resolve_user_for_subscription(subscription_payload=subscription_payload)
        if user is None:
            user = fallback_user
        if user is None and organization is None:
            raise BillingWebhookError(
                "Could not resolve a local user for the Stripe subscription."
            )

        subscription = _resolution._resolve_subscription_for_runtime_event(
            stripe_subscription_id=stripe_subscription_id,
            customer_id=str(subscription_payload.get("customer") or "").strip(),
            organization=organization,
            user=user,
            for_update=True,
        )
        if subscription is None:
            subscription = Subscription(user=user, organization=organization, plan=plan)

        customer_id = str(subscription_payload.get("customer") or "").strip()
        existing_subscription_id = str(
            subscription.stripe_subscription_id or ""
        ).strip()
        existing_customer_id = str(subscription.stripe_customer_id or "").strip()
        if (
            existing_subscription_id
            and existing_subscription_id != stripe_subscription_id
        ):
            raise BillingWebhookError(
                "Stripe subscription identity conflicts with the current local "
                "subscription; automatic replacement was refused."
            )
        if customer_id and existing_customer_id and existing_customer_id != customer_id:
            raise BillingWebhookError(
                "Stripe customer identity conflicts with the current local "
                "subscription; automatic replacement was refused."
            )

        subscription.plan = plan
        subscription.status = local_status
        update_fields: list[str] = ["plan", "status"]
        if customer_id and subscription.stripe_customer_id != customer_id:
            subscription.stripe_customer_id = customer_id
            update_fields.append("stripe_customer_id")
        if (
            stripe_subscription_id
            and subscription.stripe_subscription_id != stripe_subscription_id
        ):
            subscription.stripe_subscription_id = stripe_subscription_id
            update_fields.append("stripe_subscription_id")
        if organization is not None and subscription.organization_id != organization.pk:
            subscription.organization = organization
            update_fields.append("organization")
        if user is not None and subscription.user_id is None:
            subscription.user = user
            update_fields.append("user")
        unique_fields = list(dict.fromkeys(update_fields))
        if subscription.pk is None:
            subscription.save()
        elif unique_fields:
            subscription.save(update_fields=unique_fields)
        if organization is not None and customer_id:
            _sync_organization_customer_id(organization, customer_id)
        # Under the pinned API version period bounds exist only on subscription
        # items. Known bounds are never overwritten with a missing value.
        period_start, period_end = _extract_subscription_period_bounds(
            subscription_payload
        )
        period_update_fields: list[str] = []
        if (
            period_start is not None
            and subscription.current_period_start != period_start
        ):
            subscription.current_period_start = period_start
            period_update_fields.append("current_period_start")
        if period_end is not None and subscription.current_period_end != period_end:
            subscription.current_period_end = period_end
            period_update_fields.append("current_period_end")
        if period_update_fields:
            subscription.save(update_fields=period_update_fields)
        return subscription


def _subscription_provider_identity(
    subscription: Subscription,
) -> SubscriptionProviderIdentity:
    """Capture the local row/provider identity that finalization may mutate."""
    return SubscriptionProviderIdentity(
        subscription_pk=subscription.pk,
        organization_id=subscription.organization_id,
        stripe_subscription_id=str(subscription.stripe_subscription_id or "").strip(),
    )


def _handle_subscription_event(
    event_payload: Mapping[str, Any],
    *,
    event_type: str,
) -> Subscription:
    subscription_payload = _extract_event_object(event_payload)
    fallback_status = ""
    if event_type == STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_DELETED:
        fallback_status = Subscription.Status.CANCELED
    return _upsert_subscription_from_payload(
        subscription_payload,
        fallback_status=fallback_status,
    )
