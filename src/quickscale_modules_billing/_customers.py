"""Stripe customer resolution, creation, and identity sync.

Implementation detail of :mod:`quickscale_modules_billing.services`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

from typing import Any

from django.apps import apps
from django.db import IntegrityError, transaction

from quickscale_modules_billing._payload import (
    _build_customer_create_idempotency_key as _build_customer_create_idempotency_key,
)
from quickscale_modules_billing._payload import (
    _build_customer_metadata as _build_customer_metadata,
)
from quickscale_modules_billing._payload import (
    _organization_reference as _organization_reference,
)
from quickscale_modules_billing._settings import (
    _ORG_REFERENCE_METADATA_KEY as _ORG_REFERENCE_METADATA_KEY,
)
from quickscale_modules_billing._settings import (
    _USER_METADATA_KEY as _USER_METADATA_KEY,
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
    BillingWebhookError,
)
from quickscale_modules_billing.models import (
    Subscription,
)
import quickscale_modules_billing._stripe_client as _stripe_client
import quickscale_modules_billing._locks as _locks


@_translate_stripe_errors("Stripe customer resolution failed.")
def get_or_create_stripe_customer(
    user: Any,
    *,
    organization: Any,
    stripe_client: Any | None = None,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> tuple[str, bool]:
    """Resolve or create a Stripe customer for the given organization."""
    snapshot = settings_snapshot or BillingSettingsSnapshot.from_settings()
    _ensure_billing_enabled(snapshot)

    existing_customer_id = _resolve_authoritative_organization_customer_id(
        organization=organization,
    )
    if existing_customer_id:
        return existing_customer_id, False

    resolved_client = stripe_client or _stripe_client.get_stripe_client(
        settings_snapshot=snapshot
    )
    customer_metadata = _build_customer_metadata(user, organization=organization)
    remote_customers = resolved_client.search_customers(
        user_reference=str(customer_metadata.get(_USER_METADATA_KEY) or ""),
        organization_reference=str(
            customer_metadata.get(_ORG_REFERENCE_METADATA_KEY) or ""
        ),
    )
    if remote_customers:
        remote_customer_id = str(remote_customers[0].get("id") or "").strip()
        if not remote_customer_id:
            raise BillingWebhookError(
                "Stripe customer search returned a customer without an id."
            )
        _sync_organization_customer_id(organization, remote_customer_id)
        return remote_customer_id, False

    idempotency_reference = _organization_reference(organization)
    created_customer = resolved_client.create_customer(
        email="",
        name="",
        metadata=customer_metadata,
        idempotency_key=_build_customer_create_idempotency_key(idempotency_reference),
    )
    created_customer_id = str(created_customer.get("id") or "").strip()
    if not created_customer_id:
        raise BillingWebhookError("Stripe customer creation did not return an id.")
    _sync_organization_customer_id(organization, created_customer_id)
    return created_customer_id, True


def _resolve_user_from_reference(user_reference: str) -> Any | None:
    model_label, separator, pk_value = user_reference.partition(":")
    if not separator or "." not in model_label or not pk_value:
        return None
    app_label, _, model_name = model_label.partition(".")
    try:
        model_class = apps.get_model(app_label, model_name)
    except LookupError:
        return None
    return model_class._default_manager.filter(pk=pk_value).first()


def _resolve_organization_from_reference(organization_reference: str) -> Any | None:
    model_label, separator, pk_value = organization_reference.partition(":")
    if not separator or "." not in model_label or not pk_value:
        return None
    app_label, _, model_name = model_label.partition(".")
    try:
        model_class = apps.get_model(app_label, model_name)
    except LookupError:
        return None
    return model_class._default_manager.filter(pk=pk_value).first()


def _resolve_authoritative_organization_customer_id(*, organization: Any) -> str:
    # Imported lazily: _subscription_checkout imports this module at load time.
    import quickscale_modules_billing._subscription_checkout as _subscription_checkout

    existing_customer_id = str(
        getattr(organization, "stripe_customer_id", "") or ""
    ).strip()
    if existing_customer_id:
        return existing_customer_id

    authoritative_subscription = (
        _subscription_checkout._resolve_authoritative_subscription_reservation(
            organization=organization,
        )
    )
    existing_customer_id = ""
    if authoritative_subscription is not None:
        existing_customer_id = str(
            authoritative_subscription.stripe_customer_id or ""
        ).strip()
    if not existing_customer_id:
        historical_customer_ids = {
            str(customer_id).strip()
            for customer_id in (
                Subscription.all_objects.filter(organization=organization)
                .exclude(stripe_customer_id__isnull=True)
                .exclude(stripe_customer_id="")
                .values_list("stripe_customer_id", flat=True)
            )
            if str(customer_id).strip()
        }
        if len(historical_customer_ids) > 1:
            raise BillingWebhookError(
                "Historical subscriptions reference multiple Stripe customers; "
                "manual billing reconciliation is required."
            )
        if historical_customer_ids:
            existing_customer_id = next(iter(historical_customer_ids))
    if existing_customer_id:
        _sync_organization_customer_id(organization, existing_customer_id)
    return existing_customer_id


def _sync_organization_customer_id(organization: Any, customer_id: str) -> None:
    normalized_customer_id = customer_id.strip()
    if organization is None or not normalized_customer_id:
        return

    try:
        with transaction.atomic():
            locked_organization = _locks._lock_organization_for_billing_mutation(
                organization
            )
            existing_customer_id = str(
                getattr(locked_organization, "stripe_customer_id", "") or ""
            ).strip()
            if existing_customer_id == normalized_customer_id:
                organization.stripe_customer_id = normalized_customer_id
                return
            if existing_customer_id:
                raise BillingWebhookError(
                    "Stripe customer identity conflicts with the organization's "
                    "current billing customer; automatic replacement was refused."
                )
            if (
                type(organization)
                .objects.filter(stripe_customer_id=normalized_customer_id)
                .exclude(pk=locked_organization.pk)
                .exists()
            ):
                raise BillingWebhookError(
                    "Stripe customer identity is already owned by another "
                    "organization; automatic assignment was refused."
                )
            type(organization).objects.filter(pk=locked_organization.pk).update(
                stripe_customer_id=normalized_customer_id
            )
    except IntegrityError as exc:
        raise BillingWebhookError(
            "Stripe customer identity is already owned by another organization; "
            "automatic assignment was refused."
        ) from exc
    organization.stripe_customer_id = normalized_customer_id


def _resolve_organization_by_customer_id(customer_id: str) -> Any | None:
    normalized_customer_id = customer_id.strip()
    if not normalized_customer_id:
        return None

    organization_model = apps.get_model(
        "quickscale_orgs",
        "Organization",
    )
    matches = list(
        organization_model._default_manager.filter(
            stripe_customer_id=normalized_customer_id,
        ).order_by("pk")[:2]
    )
    if len(matches) > 1:
        raise BillingWebhookError(
            "Multiple organizations match the Stripe customer id on this billing event."
        )
    if matches:
        return matches[0]

    subscription = (
        Subscription.all_objects.select_related("organization")
        .filter(stripe_customer_id=normalized_customer_id)
        .order_by("-pk")
        .first()
    )
    if subscription is None:
        return None
    return subscription.organization
