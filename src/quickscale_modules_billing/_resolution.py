"""Webhook payload resolution to local rows and plans.

Implementation detail of :mod:`quickscale_modules_billing.services`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.apps import apps
from quickscale_modules_orgs.current_org import org_scope

from quickscale_modules_billing._customers import (
    _resolve_organization_by_customer_id as _resolve_organization_by_customer_id,
)
from quickscale_modules_billing._customers import (
    _resolve_organization_from_reference as _resolve_organization_from_reference,
)
from quickscale_modules_billing._customers import (
    _resolve_user_from_reference as _resolve_user_from_reference,
)
from quickscale_modules_billing._payload import (
    _checkout_session_metadata_is_complete as _checkout_session_metadata_is_complete,
)
from quickscale_modules_billing._payload import (
    _extract_metadata_value as _extract_metadata_value,
)
from quickscale_modules_billing._payload import (
    _extract_subscription_price_id as _extract_subscription_price_id,
)
from quickscale_modules_billing._payload import (
    _invoice_subscription_details as _invoice_subscription_details,
)
from quickscale_modules_billing._payload import (
    _normalize_integer as _normalize_integer,
)
from quickscale_modules_billing._payload import (
    _normalize_mapping as _normalize_mapping,
)
from quickscale_modules_billing._payload import (
    _purchase_checkout_pk_from_reference as _purchase_checkout_pk_from_reference,
)
from quickscale_modules_billing._payload import (
    _resolve_purchase_checkout_reference as _resolve_purchase_checkout_reference,
)
from quickscale_modules_billing._payload import (
    _resolve_subscription_checkout_reference as _resolve_subscription_checkout_reference,
)
from quickscale_modules_billing._payload import (
    _subscription_checkout_pk_from_reference as _subscription_checkout_pk_from_reference,
)
from quickscale_modules_billing._settings import (
    _ORG_REFERENCE_METADATA_KEY as _ORG_REFERENCE_METADATA_KEY,
)
from quickscale_modules_billing._settings import (
    _PLAN_CREDITS_METADATA_KEY as _PLAN_CREDITS_METADATA_KEY,
)
from quickscale_modules_billing._settings import (
    _PLAN_INTERVAL_METADATA_KEY as _PLAN_INTERVAL_METADATA_KEY,
)
from quickscale_modules_billing._settings import (
    _PRICE_ID_METADATA_KEY as _PRICE_ID_METADATA_KEY,
)
from quickscale_modules_billing._settings import (
    _USER_METADATA_KEY as _USER_METADATA_KEY,
)
from quickscale_modules_billing._validation import (
    _validate_completed_checkout_plan as _validate_completed_checkout_plan,
)
from quickscale_modules_billing.exceptions import (
    BillingWebhookError,
)
from quickscale_modules_billing.models import (
    Plan,
    PurchaseCheckout,
    Subscription,
)
import quickscale_modules_billing._subscription_checkout as _subscription_checkout


def _resolve_plan_for_subscription_payload(
    subscription_payload: Mapping[str, Any],
) -> Plan:
    price_id = _extract_subscription_price_id(subscription_payload)
    plan = Plan.objects.filter(stripe_price_id=price_id).order_by("pk").first()
    if plan is None:
        raise BillingWebhookError(f"No billing plan matches Stripe price {price_id}.")
    return plan


def _resolve_subscription_for_runtime_event(
    *,
    stripe_subscription_id: str,
    customer_id: str,
    organization: Any | None,
    user: Any | None,
    for_update: bool = False,
) -> Subscription | None:
    normalized_subscription_id = stripe_subscription_id.strip()
    if normalized_subscription_id:
        queryset = Subscription.all_objects.filter(
            stripe_subscription_id=normalized_subscription_id
        )
        if not for_update:
            queryset = queryset.select_related("user", "plan")
        if for_update:
            queryset = queryset.select_for_update()
        subscription = queryset.order_by("-pk").first()
        if subscription is not None:
            return subscription

    if customer_id.strip():
        subscription = (
            _subscription_checkout._resolve_authoritative_subscription_reservation(
                organization=organization,
                customer_id=customer_id,
                for_update=for_update,
            )
        )
        if subscription is not None:
            return subscription

    if organization is not None:
        return _subscription_checkout._resolve_authoritative_subscription_reservation(
            organization=organization,
            for_update=for_update,
        )

    return None


def _resolve_organization_for_invoice(
    *,
    invoice_payload: Mapping[str, Any],
) -> Any | None:
    customer_id = str(invoice_payload.get("customer") or "").strip()
    if customer_id:
        organization = _resolve_organization_by_customer_id(customer_id)
        if organization is not None:
            return organization

    metadata_sources = [
        invoice_payload,
        _invoice_subscription_details(invoice_payload),
    ]
    return _resolve_organization_from_metadata_sources(metadata_sources)


def _resolve_user_for_invoice(*, invoice_payload: Mapping[str, Any]) -> Any | None:
    customer_id = str(invoice_payload.get("customer") or "").strip()
    if customer_id:
        subscription = (
            _subscription_checkout._resolve_authoritative_subscription_reservation(
                customer_id=customer_id,
            )
        )
        if subscription is not None:
            return subscription.user

    metadata_sources = [
        invoice_payload,
        _invoice_subscription_details(invoice_payload),
    ]
    return _resolve_user_from_metadata_sources(metadata_sources)


def _resolve_user_for_subscription(
    *, subscription_payload: Mapping[str, Any]
) -> Any | None:
    customer_id = str(subscription_payload.get("customer") or "").strip()
    if customer_id:
        subscription = (
            _subscription_checkout._resolve_authoritative_subscription_reservation(
                customer_id=customer_id,
            )
        )
        if subscription is not None:
            return subscription.user

    return _resolve_user_from_metadata_sources([subscription_payload])


def _resolve_organization_for_subscription(
    *, subscription_payload: Mapping[str, Any]
) -> Any | None:
    customer_id = str(subscription_payload.get("customer") or "").strip()
    if customer_id:
        organization = _resolve_organization_by_customer_id(customer_id)
        if organization is not None:
            return organization

    return _resolve_organization_from_metadata_sources([subscription_payload])


def _resolve_user_for_checkout_session(
    *,
    checkout_session_payload: Mapping[str, Any],
    payment_intent_payload: Mapping[str, Any],
) -> Any | None:
    client_reference_id = str(
        checkout_session_payload.get("client_reference_id") or ""
    ).strip()
    if client_reference_id:
        user = _resolve_user_from_reference(client_reference_id)
        if user is not None:
            return user

    return _resolve_user_from_metadata_sources(
        [checkout_session_payload, payment_intent_payload]
    )


def _resolve_organization_for_checkout_session(
    *,
    checkout_session_payload: Mapping[str, Any],
    payment_intent_payload: Mapping[str, Any],
) -> Any | None:
    customer_id = str(checkout_session_payload.get("customer") or "").strip()
    customer_organization = (
        _resolve_organization_by_customer_id(customer_id) if customer_id else None
    )
    metadata_organizations = _resolve_checkout_metadata_organizations(
        [checkout_session_payload, payment_intent_payload]
    )
    purchase_checkout_reference = _resolve_purchase_checkout_reference(
        [checkout_session_payload, payment_intent_payload]
    )
    subscription_checkout_reference = _resolve_subscription_checkout_reference(
        [checkout_session_payload, payment_intent_payload]
    )
    checkout_session_id = str(checkout_session_payload.get("id") or "").strip()
    reservation_organization = _resolve_checkout_reservation_organization(
        checkout_session_id,
        purchase_checkout_reference=purchase_checkout_reference,
        subscription_checkout_reference=subscription_checkout_reference,
    )
    organizations_by_id = {
        organization.pk: organization
        for organization in (
            customer_organization,
            *metadata_organizations,
            reservation_organization,
        )
        if organization is not None
    }
    if len(organizations_by_id) > 1:
        raise BillingWebhookError(
            "Stripe checkout customer, metadata, and local reservation resolve to "
            "conflicting organizations."
        )
    if not organizations_by_id:
        return None
    return next(iter(organizations_by_id.values()))


def _resolve_checkout_metadata_organizations(
    metadata_sources: list[Mapping[str, Any]],
) -> list[Any]:
    """Resolve every Checkout organization marker so disagreement is visible."""
    organizations_by_id: dict[Any, Any] = {}
    for metadata_source in metadata_sources:
        metadata = metadata_source.get("metadata")
        if not isinstance(metadata, Mapping):
            continue
        organization_reference = str(
            metadata.get(_ORG_REFERENCE_METADATA_KEY) or ""
        ).strip()
        if not organization_reference:
            continue
        organization = _resolve_organization_from_reference(organization_reference)
        if organization is not None:
            organizations_by_id[organization.pk] = organization
    return list(organizations_by_id.values())


def _resolve_checkout_reservation_organization(
    checkout_session_id: str,
    *,
    purchase_checkout_reference: str = "",
    subscription_checkout_reference: str = "",
) -> Any | None:
    """Resolve one globally unique Checkout reservation under FORCE RLS."""
    normalized_checkout_session_id = checkout_session_id.strip()
    purchase_checkout_pk = _purchase_checkout_pk_from_reference(
        purchase_checkout_reference
    )
    if purchase_checkout_reference and purchase_checkout_pk is None:
        raise BillingWebhookError(
            "Stripe checkout session has an invalid purchase reservation reference."
        )
    subscription_checkout_pk = _subscription_checkout_pk_from_reference(
        subscription_checkout_reference
    )
    if subscription_checkout_reference and subscription_checkout_pk is None:
        raise BillingWebhookError(
            "Stripe checkout session has an invalid subscription reservation reference."
        )
    if (
        not normalized_checkout_session_id
        and purchase_checkout_pk is None
        and subscription_checkout_pk is None
    ):
        return None

    organization_model = apps.get_model(
        "quickscale_orgs",
        "Organization",
    )
    matches: list[Any] = []
    for organization in organization_model._default_manager.order_by("pk").iterator():
        with org_scope(organization):
            has_purchase_reservation = bool(
                normalized_checkout_session_id
                and PurchaseCheckout.all_objects.filter(
                    organization=organization,
                    stripe_checkout_session_id=normalized_checkout_session_id,
                ).exists()
            ) or bool(
                purchase_checkout_pk
                and PurchaseCheckout.all_objects.filter(
                    organization=organization,
                    pk=purchase_checkout_pk,
                ).exists()
            )
            has_subscription_reservation = bool(
                normalized_checkout_session_id
                and Subscription.all_objects.filter(
                    organization=organization,
                    stripe_checkout_session_id=normalized_checkout_session_id,
                ).exists()
            ) or bool(
                subscription_checkout_pk
                and Subscription.all_objects.filter(
                    organization=organization,
                    pk=subscription_checkout_pk,
                ).exists()
            )
            has_reservation = has_purchase_reservation or has_subscription_reservation
        if has_reservation:
            matches.append(organization)
            if len(matches) > 1:
                raise BillingWebhookError(
                    "Multiple organizations retain the same Stripe checkout session "
                    "reservation."
                )
    return matches[0] if matches else None


def _resolve_user_from_metadata_sources(
    metadata_sources: list[Mapping[str, Any]],
) -> Any | None:
    for metadata_source in metadata_sources:
        metadata = metadata_source.get("metadata")
        if not isinstance(metadata, Mapping):
            continue
        user_reference = str(metadata.get(_USER_METADATA_KEY) or "").strip()
        if not user_reference:
            continue
        user = _resolve_user_from_reference(user_reference)
        if user is not None:
            return user
    return None


def _resolve_organization_from_metadata_sources(
    metadata_sources: list[Mapping[str, Any]],
) -> Any | None:
    for metadata_source in metadata_sources:
        metadata = metadata_source.get("metadata")
        if not isinstance(metadata, Mapping):
            continue
        organization_reference = str(
            metadata.get(_ORG_REFERENCE_METADATA_KEY) or ""
        ).strip()
        if not organization_reference:
            continue
        organization = _resolve_organization_from_reference(organization_reference)
        if organization is not None:
            return organization
    return None


def _resolve_plan_for_checkout_session(
    *,
    checkout_session_payload: Mapping[str, Any],
    payment_intent_payload: Mapping[str, Any],
) -> Plan:
    metadata_sources = [checkout_session_payload, payment_intent_payload]
    price_id = _extract_metadata_value(metadata_sources, _PRICE_ID_METADATA_KEY)
    if not price_id:
        raise BillingWebhookError(
            "Stripe checkout session is missing immutable Stripe price metadata."
        )

    plan = Plan.objects.filter(stripe_price_id=price_id).order_by("pk").first()
    if plan is None:
        raise BillingWebhookError(f"No billing plan matches Stripe price {price_id}.")

    _validate_completed_checkout_plan(
        plan,
        expected_price_id=price_id,
        expected_interval=_extract_metadata_value(
            metadata_sources,
            _PLAN_INTERVAL_METADATA_KEY,
        ),
    )
    return plan


def _resolve_checkout_session_credit_amount(
    *,
    checkout_session_payload: Mapping[str, Any],
    payment_intent_payload: Mapping[str, Any],
) -> int:
    metadata_sources = [checkout_session_payload, payment_intent_payload]
    stored_credits = _extract_metadata_value(
        metadata_sources,
        _PLAN_CREDITS_METADATA_KEY,
    )
    credited_amount = _normalize_integer(stored_credits)
    if credited_amount is None or credited_amount <= 0:
        raise BillingWebhookError(
            "Stripe checkout session is missing immutable credit metadata."
        )
    return credited_amount


def _retrieve_checkout_payment_intent_payload(
    *,
    checkout_session_payload: Mapping[str, Any],
    stripe_client: Any | None,
) -> dict[str, Any]:
    payment_intent_id = str(
        checkout_session_payload.get("payment_intent") or ""
    ).strip()
    if not payment_intent_id:
        return {}
    if _checkout_session_metadata_is_complete(checkout_session_payload):
        return {}
    if stripe_client is None or not hasattr(stripe_client, "retrieve_payment_intent"):
        return {}
    return _normalize_mapping(
        stripe_client.retrieve_payment_intent(payment_intent_id=payment_intent_id)
    )
