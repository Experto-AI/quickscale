"""Stripe invoice and subscription event handling.

Implementation detail of :mod:`quickscale_modules_billing.services`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from quickscale_modules_orgs.current_org import org_scope

import quickscale_modules_billing.services as _services
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

    resolved_organization = _services._resolve_organization_for_invoice(
        invoice_payload=invoice_payload,
    )
    if resolved_organization is None:
        return _services._process_invoice_paid_event(
            event_payload=event_payload,
            invoice_payload=invoice_payload,
            invoice_id=invoice_id,
            plan=plan,
            price_id=price_id,
            resolved_organization=None,
            stripe_client=stripe_client,
            provider_lock_held=False,
        )
    with _services.subscription_provider_mutation_lock(resolved_organization):
        return _services._process_invoice_paid_event(
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

    # Phase 1: resolve user + subscription in a short org scope.
    with org_scope(resolved_organization):
        resolved_user = _resolve_user_for_invoice(invoice_payload=invoice_payload)
        subscription_id = _invoice_subscription_id(invoice_payload)
        customer_id = str(invoice_payload.get("customer") or "").strip()
        subscription = _services._resolve_subscription_for_runtime_event(
            stripe_subscription_id=subscription_id,
            customer_id=customer_id,
            organization=resolved_organization,
            user=resolved_user,
            for_update=True,
        )

    # Phase 2: retrieve a missing subscription via Stripe outside every DB
    # transaction. When the invoice could not identify an organization, the
    # retrieved payload supplies it before one continuous provider mutex covers
    # both the local upsert and invoice finalization.
    if subscription is None:
        subscription_payload = _retrieve_subscription_for_paid_invoice(
            invoice_payload=invoice_payload,
            stripe_client=stripe_client,
        )
        payload_organization = _services._resolve_organization_for_subscription(
            subscription_payload=subscription_payload
        )
        mutation_organization = payload_organization or resolved_organization
        if mutation_organization is None:
            raise BillingWebhookError(
                "Could not resolve a local organization for the Stripe subscription."
            )
        if not provider_lock_held:
            with _services.subscription_provider_mutation_lock(mutation_organization):
                subscription = _upsert_subscription_from_payload(
                    subscription_payload,
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
                )
        subscription = _upsert_subscription_from_payload(
            subscription_payload,
            fallback_user=resolved_user,
            fallback_organization=mutation_organization,
            expected_plan=plan,
            provider_lock_held=True,
        )

    if subscription is None:
        raise BillingWebhookError(
            "Could not resolve or backfill a subscription for the invoice."
        )

    # Phase 3: remaining processing + credit_user in a new org scope.
    mutation_organization = resolved_organization or subscription.organization
    expected_identity = _subscription_provider_identity(subscription)
    expected_customer_id = str(subscription.stripe_customer_id or "").strip()
    if not provider_lock_held:
        with _services.subscription_provider_mutation_lock(mutation_organization):
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
    )


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
) -> CreditTransaction:
    """Reload and apply invoice state under the provider and database locks."""
    with org_scope(mutation_organization):
        mutation_organization = _services._lock_organization_for_billing_mutation(
            mutation_organization
        )
        try:
            subscription = (
                Subscription.all_objects.select_for_update()
                .select_related("organization", "plan")
                .get(pk=subscription.pk)
            )
        except Subscription.DoesNotExist as exc:
            raise BillingWebhookError(
                "The resolved invoice subscription disappeared before local "
                "finalization; automatic reconciliation was refused."
            ) from exc
        current_customer_id = str(subscription.stripe_customer_id or "").strip()
        identity_changed = (
            subscription.pk != expected_identity.subscription_pk
            or subscription.organization_id != expected_identity.organization_id
            or str(subscription.stripe_subscription_id or "").strip()
            != expected_identity.stripe_subscription_id
            or current_customer_id != expected_customer_id
        )
        incoming_subscription_id = subscription_id.strip()
        incoming_customer_id = customer_id.strip()
        invoice_conflicts_with_identity = bool(
            incoming_subscription_id
            and expected_identity.stripe_subscription_id
            and incoming_subscription_id != expected_identity.stripe_subscription_id
        ) or bool(
            incoming_customer_id
            and expected_customer_id
            and incoming_customer_id != expected_customer_id
        )
        if identity_changed or invoice_conflicts_with_identity:
            raise BillingWebhookError(
                "The resolved invoice subscription changed provider identity before "
                "local finalization; automatic reconciliation was refused."
            )
        # Re-resolve user if backfill resolved the subscription.
        if resolved_user is None:
            resolved_user = _resolve_user_for_invoice(invoice_payload=invoice_payload)

        if subscription.status in {
            Subscription.Status.INCOMPLETE,
            Subscription.Status.PAST_DUE,
        } or (
            subscription_id
            and not str(subscription.stripe_subscription_id or "").strip()
        ):
            subscription = _activate_subscription_for_paid_invoice(
                subscription=subscription,
                plan=plan,
                organization=mutation_organization,
                user=resolved_user,
                customer_id=customer_id,
                stripe_subscription_id=subscription_id,
            )
        else:
            update_fields: list[str] = []
            if (
                customer_id.strip()
                and subscription.stripe_customer_id != customer_id.strip()
            ):
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
                _sync_organization_customer_id(
                    mutation_organization,
                    customer_id.strip(),
                )

        organization = subscription.organization

        user = resolved_user
        if user is None and subscription is not None:
            user = subscription.user

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
) -> Subscription:
    invoice_payload = _extract_event_object(event_payload)
    invoice_id = str(invoice_payload.get("id") or "").strip()
    if not invoice_id:
        raise BillingWebhookError("Stripe invoice payload is missing an id.")

    resolved_organization = _services._resolve_organization_for_invoice(
        invoice_payload=invoice_payload,
    )
    if resolved_organization is None:
        raise BillingWebhookError(
            "Could not resolve a local organization for the Stripe invoice."
        )
    with _services.subscription_provider_mutation_lock(resolved_organization):
        return _services._apply_invoice_payment_failed_event(
            invoice_payload=invoice_payload,
            resolved_organization=resolved_organization,
        )


def _apply_invoice_payment_failed_event(
    *,
    invoice_payload: Mapping[str, Any],
    resolved_organization: Any,
) -> Subscription:
    """Apply payment failure while the organization's provider mutex is held."""
    # Phase 3: each handler owns its org scope for SET LOCAL support.
    with org_scope(resolved_organization):
        resolved_organization = _services._lock_organization_for_billing_mutation(
            resolved_organization
        )
        resolved_user = _resolve_user_for_invoice(invoice_payload=invoice_payload)
        subscription = _services._resolve_subscription_for_runtime_event(
            stripe_subscription_id=_invoice_subscription_id(invoice_payload),
            customer_id=str(invoice_payload.get("customer") or "").strip(),
            organization=resolved_organization,
            user=resolved_user,
            for_update=True,
        )

        if subscription is None:
            if resolved_user is None and resolved_organization is None:
                raise BillingWebhookError(
                    "Could not resolve a local user for the Stripe invoice."
                )
            price_id = _extract_price_id(invoice_payload)
            plan = Plan.objects.filter(stripe_price_id=price_id).order_by("pk").first()
            if plan is None:
                raise BillingWebhookError(
                    f"No billing plan matches Stripe price {price_id}."
                )
            subscription = Subscription(
                user=resolved_user,
                organization=resolved_organization,
                plan=plan,
            )

        subscription.status = Subscription.Status.PAST_DUE
        update_fields: list[str] = ["status"]
        customer_id = str(invoice_payload.get("customer") or "").strip()
        subscription_id = _invoice_subscription_id(invoice_payload)
        existing_customer_id = str(subscription.stripe_customer_id or "").strip()
        existing_subscription_id = str(
            subscription.stripe_subscription_id or ""
        ).strip()
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


def _activate_subscription_for_paid_invoice(
    *,
    subscription: Subscription,
    plan: Plan,
    organization: Any | None,
    user: Any | None,
    customer_id: str,
    stripe_subscription_id: str,
) -> Subscription:
    update_fields: list[str] = []
    if subscription.plan.pk != plan.pk:
        subscription.plan = plan
        update_fields.append("plan")
    if subscription.status != Subscription.Status.ACTIVE:
        subscription.status = Subscription.Status.ACTIVE
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
