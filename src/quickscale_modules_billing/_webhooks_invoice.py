"""Stripe invoice and subscription event handling.

Implementation detail of :mod:`quickscale_modules_billing.services`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from quickscale_modules_orgs.current_org import org_scope

from quickscale_modules_billing._credits import (
    credit_user as credit_user,
)
from quickscale_modules_billing._customers import (
    _sync_organization_customer_id as _sync_organization_customer_id,
)
from quickscale_modules_billing._payload import (
    _extract_event_object as _extract_event_object,
)
from quickscale_modules_billing._payload import (
    _extract_price_id as _extract_price_id,
)
from quickscale_modules_billing._payload import (
    _invoice_subscription_id as _invoice_subscription_id,
)
from quickscale_modules_billing._payload import (
    _map_stripe_subscription_status as _map_stripe_subscription_status,
)
from quickscale_modules_billing._payload import (
    _normalize_mapping as _normalize_mapping,
)
from quickscale_modules_billing._resolution import (
    _resolve_user_for_invoice as _resolve_user_for_invoice,
)
from quickscale_modules_billing._settings import (
    _CREDITABLE_INVOICE_BILLING_REASONS as _CREDITABLE_INVOICE_BILLING_REASONS,
)
from quickscale_modules_billing._settings import (
    SubscriptionProviderIdentity as SubscriptionProviderIdentity,
)
from quickscale_modules_billing._subscription_events import (
    _retrieve_authoritative_subscription_payload as _retrieve_authoritative_subscription_payload,
)
from quickscale_modules_billing._subscription_events import (
    _subscription_provider_identity as _subscription_provider_identity,
)
from quickscale_modules_billing._subscription_events import (
    _upsert_subscription_from_payload as _upsert_subscription_from_payload,
)
from quickscale_modules_billing.exceptions import (
    BillingWebhookError,
)
from quickscale_modules_billing.models import (
    CreditTransaction,
    Plan,
    Subscription,
)
import quickscale_modules_billing._resolution as _resolution
import quickscale_modules_billing._locks as _locks


def _handle_invoice_paid_event(
    event_payload: Mapping[str, Any],
    *,
    stripe_client: Any | None = None,
) -> CreditTransaction | None:
    invoice_payload = _extract_event_object(event_payload)
    invoice_id = str(invoice_payload.get("id") or "").strip()
    if not invoice_id:
        raise BillingWebhookError("Stripe invoice payload is missing an id.")

    billing_reason = str(invoice_payload.get("billing_reason") or "").strip().lower()
    if billing_reason not in _CREDITABLE_INVOICE_BILLING_REASONS:
        return None

    price_id = _extract_price_id(invoice_payload)
    plan = Plan.objects.filter(stripe_price_id=price_id).order_by("pk").first()
    if plan is None:
        raise BillingWebhookError(f"No billing plan matches Stripe price {price_id}.")

    resolved_organization = _resolution._resolve_organization_for_invoice(
        invoice_payload=invoice_payload,
    )
    if resolved_organization is None:
        return _process_invoice_paid_event(
            event_payload=event_payload,
            invoice_payload=invoice_payload,
            invoice_id=invoice_id,
            plan=plan,
            price_id=price_id,
            resolved_organization=None,
            stripe_client=stripe_client,
            provider_lock_held=False,
        )
    with _locks.subscription_provider_mutation_lock(resolved_organization):
        return _process_invoice_paid_event(
            event_payload=event_payload,
            invoice_payload=invoice_payload,
            invoice_id=invoice_id,
            plan=plan,
            price_id=price_id,
            resolved_organization=resolved_organization,
            stripe_client=stripe_client,
            provider_lock_held=True,
        )


def _process_invoice_paid_event(
    *,
    event_payload: Mapping[str, Any],
    invoice_payload: Mapping[str, Any],
    invoice_id: str,
    plan: Plan,
    price_id: str,
    resolved_organization: Any | None,
    stripe_client: Any | None,
    provider_lock_held: bool,
) -> CreditTransaction:
    """Resolve an invoice subscription, keeping provider I/O outside atomics."""

    subscription_id = _invoice_subscription_id(invoice_payload)
    customer_id = str(invoice_payload.get("customer") or "").strip()

    # Phase 1: resolve user + subscription in a short org scope.
    with org_scope(resolved_organization):
        resolved_user = _resolve_user_for_invoice(invoice_payload=invoice_payload)
        subscription = _resolution._resolve_subscription_for_runtime_event(
            stripe_subscription_id=subscription_id,
            customer_id=customer_id,
            organization=resolved_organization,
            user=resolved_user,
            for_update=True,
        )
        needs_provider_status = bool(
            subscription is not None
            and subscription_id
            and subscription.status
            in {Subscription.Status.INCOMPLETE, Subscription.Status.PAST_DUE}
        )

    # Phase 2: a paid invoice may activate a subscription, so read the
    # provider's current status first. Stripe does not promise delivery order,
    # and an older paid event must not overwrite a newer provider status. The
    # read stays outside every DB transaction; the caller holds the
    # organization's provider mutex when the organization was resolved.
    provider_subscription: Mapping[str, Any] | None = None
    if needs_provider_status:
        provider_subscription = _retrieve_authoritative_subscription_payload(
            stripe_subscription_id=subscription_id,
            stripe_client=stripe_client,
        )

    # Phase 3: retrieve a missing subscription via Stripe outside every DB
    # transaction. When the invoice could not identify an organization, the
    # retrieved payload supplies it before one continuous provider mutex covers
    # both the local upsert and invoice finalization.
    if subscription is None:
        subscription_payload = _retrieve_subscription_for_paid_invoice(
            invoice_payload=invoice_payload,
            stripe_client=stripe_client,
        )
        payload_organization = _resolution._resolve_organization_for_subscription(
            subscription_payload=subscription_payload
        )
        mutation_organization = payload_organization or resolved_organization
        if mutation_organization is None:
            raise BillingWebhookError(
                "Could not resolve a local organization for the Stripe subscription."
            )
        if not provider_lock_held:
            with _locks.subscription_provider_mutation_lock(mutation_organization):
                # The unlocked read above only discovered the organization.
                # Refresh the provider state under the mutex so a newer delivery
                # that landed before this lock cannot be overwritten by the
                # snapshot fetched before it.
                provider_subscription = _retrieve_authoritative_subscription_payload(
                    stripe_subscription_id=subscription_id,
                    stripe_client=stripe_client,
                )
                subscription = _upsert_subscription_from_payload(
                    provider_subscription,
                    fallback_user=resolved_user,
                    fallback_organization=mutation_organization,
                    expected_plan=plan,
                    provider_lock_held=True,
                )
                expected_identity = _subscription_provider_identity(subscription)
                return _finalize_invoice_paid_event(
                    event_payload=event_payload,
                    invoice_payload=invoice_payload,
                    invoice_id=invoice_id,
                    plan=plan,
                    price_id=price_id,
                    resolved_user=resolved_user,
                    subscription=subscription,
                    subscription_id=subscription_id,
                    customer_id=customer_id,
                    mutation_organization=mutation_organization,
                    expected_identity=expected_identity,
                    expected_customer_id=str(
                        subscription.stripe_customer_id or ""
                    ).strip(),
                    provider_subscription=provider_subscription,
                )
        subscription = _upsert_subscription_from_payload(
            subscription_payload,
            fallback_user=resolved_user,
            fallback_organization=mutation_organization,
            expected_plan=plan,
            provider_lock_held=True,
        )
        # This read happened under the caller's provider mutex; keep it as the
        # authoritative status for finalization instead of defaulting to active.
        provider_subscription = subscription_payload

    if subscription is None:
        raise BillingWebhookError(
            "Could not resolve or backfill a subscription for the invoice."
        )

    # Phase 4: remaining processing + credit_user in a new org scope.
    mutation_organization = resolved_organization or subscription.organization
    expected_identity = _subscription_provider_identity(subscription)
    expected_customer_id = str(subscription.stripe_customer_id or "").strip()
    if not provider_lock_held:
        with _locks.subscription_provider_mutation_lock(mutation_organization):
            return _finalize_invoice_paid_event(
                event_payload=event_payload,
                invoice_payload=invoice_payload,
                invoice_id=invoice_id,
                plan=plan,
                price_id=price_id,
                resolved_user=resolved_user,
                subscription=subscription,
                subscription_id=subscription_id,
                customer_id=customer_id,
                mutation_organization=mutation_organization,
                expected_identity=expected_identity,
                expected_customer_id=expected_customer_id,
                provider_subscription=provider_subscription,
            )
    return _finalize_invoice_paid_event(
        event_payload=event_payload,
        invoice_payload=invoice_payload,
        invoice_id=invoice_id,
        plan=plan,
        price_id=price_id,
        resolved_user=resolved_user,
        subscription=subscription,
        subscription_id=subscription_id,
        customer_id=customer_id,
        mutation_organization=mutation_organization,
        expected_identity=expected_identity,
        expected_customer_id=expected_customer_id,
        provider_subscription=provider_subscription,
    )


def _reload_invoice_subscription(subscription: Subscription) -> Subscription:
    """Reload the subscription for update, or fail closed when it vanished."""
    try:
        return (
            Subscription.all_objects.select_for_update()
            .select_related("organization", "plan")
            .get(pk=subscription.pk)
        )
    except Subscription.DoesNotExist as exc:
        raise BillingWebhookError(
            "The resolved invoice subscription disappeared before local "
            "finalization; automatic reconciliation was refused."
        ) from exc


def _invoice_identity_changed(
    subscription: Subscription,
    expected_identity: SubscriptionProviderIdentity,
    expected_customer_id: str,
) -> bool:
    """Return whether the reloaded subscription no longer matches its identity."""
    current_customer_id = str(subscription.stripe_customer_id or "").strip()
    return (
        subscription.pk != expected_identity.subscription_pk
        or subscription.organization_id != expected_identity.organization_id
        or str(subscription.stripe_subscription_id or "").strip()
        != expected_identity.stripe_subscription_id
        or current_customer_id != expected_customer_id
    )


def _invoice_conflicts_with_identity(
    *,
    subscription_id: str,
    customer_id: str,
    expected_identity: SubscriptionProviderIdentity,
    expected_customer_id: str,
) -> bool:
    """Return whether the invoice's provider identity conflicts with the stored one."""
    incoming_subscription_id = subscription_id.strip()
    incoming_customer_id = customer_id.strip()
    return bool(
        incoming_subscription_id
        and expected_identity.stripe_subscription_id
        and incoming_subscription_id != expected_identity.stripe_subscription_id
    ) or bool(
        incoming_customer_id
        and expected_customer_id
        and incoming_customer_id != expected_customer_id
    )


def _require_unchanged_invoice_identity(
    subscription: Subscription,
    *,
    expected_identity: SubscriptionProviderIdentity,
    expected_customer_id: str,
    subscription_id: str,
    customer_id: str,
) -> None:
    """Refuse a paid invoice whose subscription identity changed underneath it."""
    if _invoice_identity_changed(
        subscription, expected_identity, expected_customer_id
    ) or _invoice_conflicts_with_identity(
        subscription_id=subscription_id,
        customer_id=customer_id,
        expected_identity=expected_identity,
        expected_customer_id=expected_customer_id,
    ):
        raise BillingWebhookError(
            "The resolved invoice subscription changed provider identity before "
            "local finalization; automatic reconciliation was refused."
        )


def _update_existing_invoice_identity(
    subscription: Subscription,
    *,
    organization: Any,
    customer_id: str,
    subscription_id: str,
) -> None:
    """Refresh the existing subscription's provider identity fields."""
    update_fields: list[str] = []
    if customer_id.strip() and subscription.stripe_customer_id != customer_id.strip():
        subscription.stripe_customer_id = customer_id.strip()
        update_fields.append("stripe_customer_id")
    if (
        subscription_id.strip()
        and subscription.stripe_subscription_id != subscription_id.strip()
    ):
        subscription.stripe_subscription_id = subscription_id.strip()
        update_fields.append("stripe_subscription_id")
    if update_fields:
        subscription.save(update_fields=update_fields)
    if customer_id.strip():
        _sync_organization_customer_id(organization, customer_id.strip())


def _update_invoice_subscription_identity(
    subscription: Subscription,
    *,
    plan: Plan,
    organization: Any,
    user: Any,
    customer_id: str,
    subscription_id: str,
    provider_subscription: Mapping[str, Any] | None = None,
) -> Subscription:
    """Activate an incomplete subscription or refresh its identity fields."""
    target_status: str = Subscription.Status.ACTIVE
    if provider_subscription is not None:
        target_status = _map_stripe_subscription_status(
            str(provider_subscription.get("status") or "")
        )
    if subscription.status in {
        Subscription.Status.INCOMPLETE,
        Subscription.Status.PAST_DUE,
    } or (
        subscription_id and not str(subscription.stripe_subscription_id or "").strip()
    ):
        return _activate_subscription_for_paid_invoice(
            subscription=subscription,
            plan=plan,
            organization=organization,
            user=user,
            customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            local_status=target_status,
        )
    _update_existing_invoice_identity(
        subscription,
        organization=organization,
        customer_id=customer_id,
        subscription_id=subscription_id,
    )
    return subscription


def _finalize_invoice_paid_event(
    *,
    event_payload: Mapping[str, Any],
    invoice_payload: Mapping[str, Any],
    invoice_id: str,
    plan: Plan,
    price_id: str,
    resolved_user: Any | None,
    subscription: Subscription,
    subscription_id: str,
    customer_id: str,
    mutation_organization: Any,
    expected_identity: SubscriptionProviderIdentity,
    expected_customer_id: str,
    provider_subscription: Mapping[str, Any] | None = None,
) -> CreditTransaction:
    """Reload and apply invoice state under the provider and database locks."""
    with org_scope(mutation_organization):
        mutation_organization = _locks._lock_organization_for_billing_mutation(
            mutation_organization
        )
        subscription = _reload_invoice_subscription(subscription)
        _require_unchanged_invoice_identity(
            subscription,
            expected_identity=expected_identity,
            expected_customer_id=expected_customer_id,
            subscription_id=subscription_id,
            customer_id=customer_id,
        )
        # Re-resolve user if backfill resolved the subscription.
        if resolved_user is None:
            resolved_user = _resolve_user_for_invoice(invoice_payload=invoice_payload)

        subscription = _update_invoice_subscription_identity(
            subscription,
            plan=plan,
            organization=mutation_organization,
            user=resolved_user,
            customer_id=customer_id,
            subscription_id=subscription_id,
            provider_subscription=provider_subscription,
        )
        organization = subscription.organization
        user = resolved_user if resolved_user is not None else subscription.user

        reference_data: dict[str, Any] = {
            "invoice_id": invoice_id,
            "stripe_customer_id": customer_id,
            "stripe_price_id": price_id,
        }
        if subscription_id:
            reference_data["stripe_subscription_id"] = subscription_id

        return credit_user(
            user,
            organization=organization,
            amount=plan.credits_per_period,
            transaction_type=CreditTransaction.TransactionType.PLAN,
            description=f"{plan.name} credits from Stripe invoice {invoice_id}",
            stripe_event_id=str(event_payload.get("id") or "").strip(),
            stripe_object_id=invoice_id,
            stripe_reference_data=reference_data,
        )


def _handle_invoice_payment_failed_event(
    event_payload: Mapping[str, Any],
    *,
    stripe_client: Any | None = None,
) -> Subscription:
    invoice_payload = _extract_event_object(event_payload)
    invoice_id = str(invoice_payload.get("id") or "").strip()
    if not invoice_id:
        raise BillingWebhookError("Stripe invoice payload is missing an id.")

    resolved_organization = _resolution._resolve_organization_for_invoice(
        invoice_payload=invoice_payload,
    )
    if resolved_organization is None:
        raise BillingWebhookError(
            "Could not resolve a local organization for the Stripe invoice."
        )
    subscription_id = _invoice_subscription_id(invoice_payload)
    with _locks.subscription_provider_mutation_lock(resolved_organization):
        provider_subscription: Mapping[str, Any] | None = None
        if subscription_id:
            provider_subscription = _retrieve_authoritative_subscription_payload(
                stripe_subscription_id=subscription_id,
                stripe_client=stripe_client,
            )
        return _apply_invoice_payment_failed_event(
            invoice_payload=invoice_payload,
            resolved_organization=resolved_organization,
            provider_subscription=provider_subscription,
        )


def _subscription_for_missing_failed_invoice(
    *,
    invoice_payload: Mapping[str, Any],
    resolved_user: Any | None,
    resolved_organization: Any,
) -> Subscription:
    """Build the subscription row a failed invoice implies when none exists."""
    if resolved_user is None and resolved_organization is None:
        raise BillingWebhookError(
            "Could not resolve a local user for the Stripe invoice."
        )
    price_id = _extract_price_id(invoice_payload)
    plan = Plan.objects.filter(stripe_price_id=price_id).order_by("pk").first()
    if plan is None:
        raise BillingWebhookError(f"No billing plan matches Stripe price {price_id}.")
    return Subscription(
        user=resolved_user,
        organization=resolved_organization,
        plan=plan,
    )


def _require_failed_invoice_identity(
    subscription: Subscription, *, customer_id: str, subscription_id: str
) -> None:
    """Refuse a failed invoice that conflicts with the stored provider identity."""
    existing_customer_id = str(subscription.stripe_customer_id or "").strip()
    existing_subscription_id = str(subscription.stripe_subscription_id or "").strip()
    if (
        customer_id and existing_customer_id and customer_id != existing_customer_id
    ) or (
        subscription_id
        and existing_subscription_id
        and subscription_id != existing_subscription_id
    ):
        raise BillingWebhookError(
            "The failed invoice conflicts with the current subscription provider "
            "identity; automatic replacement was refused."
        )


def _apply_failed_subscription_fields(
    subscription: Subscription,
    resolved_user: Any | None,
    resolved_organization: Any,
    *,
    customer_id: str,
    subscription_id: str,
    local_status: str,
) -> Subscription:
    """Apply the provider's current status and refresh identity fields."""
    subscription.status = local_status
    update_fields: list[str] = ["status"]
    if customer_id and subscription.stripe_customer_id != customer_id:
        subscription.stripe_customer_id = customer_id
        update_fields.append("stripe_customer_id")
    if subscription_id and subscription.stripe_subscription_id != subscription_id:
        subscription.stripe_subscription_id = subscription_id
        update_fields.append("stripe_subscription_id")
    if (
        resolved_organization is not None
        and subscription.organization_id != resolved_organization.pk
    ):
        subscription.organization = resolved_organization
        update_fields.append("organization")
    if resolved_user is not None and subscription.user_id != resolved_user.pk:
        subscription.user = resolved_user
        update_fields.append("user")
    subscription.save(update_fields=update_fields)
    return subscription


def _apply_invoice_payment_failed_event(
    *,
    invoice_payload: Mapping[str, Any],
    resolved_organization: Any,
    provider_subscription: Mapping[str, Any] | None = None,
) -> Subscription:
    """Apply payment failure while the organization's provider mutex is held."""
    # Phase 3: each handler owns its org scope for SET LOCAL support.
    with org_scope(resolved_organization):
        resolved_organization = _locks._lock_organization_for_billing_mutation(
            resolved_organization
        )
        resolved_user = _resolve_user_for_invoice(invoice_payload=invoice_payload)
        subscription = _resolution._resolve_subscription_for_runtime_event(
            stripe_subscription_id=_invoice_subscription_id(invoice_payload),
            customer_id=str(invoice_payload.get("customer") or "").strip(),
            organization=resolved_organization,
            user=resolved_user,
            for_update=True,
        )

        if subscription is None:
            subscription = _subscription_for_missing_failed_invoice(
                invoice_payload=invoice_payload,
                resolved_user=resolved_user,
                resolved_organization=resolved_organization,
            )

        customer_id = str(invoice_payload.get("customer") or "").strip()
        subscription_id = _invoice_subscription_id(invoice_payload)
        _require_failed_invoice_identity(
            subscription,
            customer_id=customer_id,
            subscription_id=subscription_id,
        )
        local_status: str = Subscription.Status.PAST_DUE
        if provider_subscription is not None:
            local_status = _map_stripe_subscription_status(
                str(provider_subscription.get("status") or "")
            )
        return _apply_failed_subscription_fields(
            subscription,
            resolved_user,
            resolved_organization,
            customer_id=customer_id,
            subscription_id=subscription_id,
            local_status=local_status,
        )


def _activate_subscription_for_paid_invoice(
    *,
    subscription: Subscription,
    plan: Plan,
    organization: Any | None,
    user: Any | None,
    customer_id: str,
    stripe_subscription_id: str,
    local_status: str = Subscription.Status.ACTIVE,
) -> Subscription:
    update_fields: list[str] = []
    if subscription.plan.pk != plan.pk:
        subscription.plan = plan
        update_fields.append("plan")
    if subscription.status != local_status:
        subscription.status = local_status
        update_fields.append("status")
    normalized_customer_id = customer_id.strip()
    if (
        normalized_customer_id
        and subscription.stripe_customer_id != normalized_customer_id
    ):
        subscription.stripe_customer_id = normalized_customer_id
        update_fields.append("stripe_customer_id")
    normalized_subscription_id = stripe_subscription_id.strip()
    if (
        normalized_subscription_id
        and subscription.stripe_subscription_id != normalized_subscription_id
    ):
        subscription.stripe_subscription_id = normalized_subscription_id
        update_fields.append("stripe_subscription_id")
    if normalized_customer_id:
        _sync_organization_customer_id(organization, normalized_customer_id)
    unique_fields = list(dict.fromkeys(update_fields))
    if subscription.pk is None:
        subscription.save()
    elif unique_fields:
        subscription.save(update_fields=unique_fields)
    return subscription


def _retrieve_subscription_for_paid_invoice(
    *,
    invoice_payload: Mapping[str, Any],
    stripe_client: Any | None,
) -> dict[str, Any]:
    """Retrieve the invoice subscription before local lock/transaction work."""
    stripe_subscription_id = _invoice_subscription_id(invoice_payload)
    if not stripe_subscription_id:
        raise BillingWebhookError(
            "Stripe invoice payload is missing a subscription id for local reconciliation."
        )
    if stripe_client is None or not hasattr(stripe_client, "retrieve_subscription"):
        raise BillingWebhookError(
            "Stripe subscription retrieval is unavailable for invoice reconciliation."
        )

    return _normalize_mapping(
        stripe_client.retrieve_subscription(
            stripe_subscription_id=stripe_subscription_id,
        )
    )
