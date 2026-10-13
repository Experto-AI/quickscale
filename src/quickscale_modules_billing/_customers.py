"""Stripe customer resolution, creation, and identity sync.

Implementation detail of :mod:`quickscale_modules_billing.services`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.apps import apps
from django.db import IntegrityError, transaction
from django.utils import timezone
from quickscale_modules_orgs.current_org import org_scope

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
    _STRIPE_SEARCH_INDEX_LAG as _STRIPE_SEARCH_INDEX_LAG,
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
    BillingError,
    BillingWebhookError,
)
from quickscale_modules_billing.models import (
    BillingCustomer,
    PurchaseCheckout,
    Subscription,
)
import quickscale_modules_billing._stripe_client as _stripe_client
import quickscale_modules_billing._locks as _locks


def _organization_customer_id(organization: Any) -> str:
    """Return the Stripe customer id recorded for *organization*, or ``""``."""
    if organization is None:
        return ""
    customer_id = (
        BillingCustomer.objects.filter(organization=organization)
        .values_list("stripe_customer_id", flat=True)
        .first()
    )
    return str(customer_id or "").strip()


def _distinct_customer_ids(remote_customers: list[dict[str, Any]]) -> list[str]:
    """Return the distinct non-empty Stripe customer ids in a search result."""
    return sorted(
        {
            str(customer.get("id") or "").strip()
            for customer in remote_customers
            if str(customer.get("id") or "").strip()
        }
    )


def _stamp_organization_customer_attempt(
    organization: Any,
    *,
    completed: bool,
) -> None:
    """Record a customer-resolution attempt on the organization's reservations.

    Stripe's customer identity is organization-wide, so an attempt made by any
    checkout or portal flow refreshes the Search indexing lag window of every
    unresolved reservation the organization holds. The attempt is stamped in
    flight and again on completion, so an interrupted attempt cannot age into
    a trusted absence.
    """
    attempt_at = timezone.now()
    values: dict[str, Any] = (
        {"customer_lookup_completed_at": attempt_at}
        if completed
        else {
            "customer_lookup_attempted_at": attempt_at,
            "customer_lookup_completed_at": None,
        }
    )
    with org_scope(organization):
        Subscription.all_objects.filter(
            organization=organization,
            status=Subscription.Status.INCOMPLETE,
        ).update(**values)
        PurchaseCheckout.all_objects.filter(
            organization=organization,
            status=PurchaseCheckout.Status.PREPARING,
        ).update(**values)


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
    # Stripe Search is eventually consistent, so reconciliation must be able to
    # tell how recently the organization may have created a customer. The
    # attempt is stamped on every unresolved reservation of the organization
    # before the provider call and again once its outcome is known, so a slow
    # search or a lost response cannot outlast the reconciliation window.
    _stamp_organization_customer_attempt(organization, completed=False)
    try:
        remote_customers = resolved_client.search_customers(
            user_reference=str(customer_metadata.get(_USER_METADATA_KEY) or ""),
            organization_reference=str(
                customer_metadata.get(_ORG_REFERENCE_METADATA_KEY) or ""
            ),
        )
        if len(_distinct_customer_ids(remote_customers)) > 1:
            raise BillingError(
                "Multiple Stripe customers match the billing reference; manual "
                "billing reconciliation is required."
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
            idempotency_key=_build_customer_create_idempotency_key(
                idempotency_reference
            ),
        )
        created_customer_id = str(created_customer.get("id") or "").strip()
        if not created_customer_id:
            raise BillingWebhookError("Stripe customer creation did not return an id.")
        _sync_organization_customer_id(organization, created_customer_id)
        return created_customer_id, True
    finally:
        _stamp_organization_customer_attempt(organization, completed=True)


def _resolve_existing_customer_id_for_reconciliation(
    *,
    organization: Any,
    stripe_client: Any,
    reservation_attempted_at: datetime | None,
    reservation_completed_at: datetime | None,
    reservation_created_at: datetime,
    reservation_customer_id: str = "",
) -> str:
    """Return the organization's Stripe customer id without creating one.

    Reconciliation must not add provider state, so an organization with no
    recorded customer id is looked up by reference. Stripe's customer search
    is eventually consistent, so a miss counts as absence only once the
    reservation's latest recorded customer-resolution attempt is older than
    the documented Search indexing lag, measured from when the search was
    issued; before that, and while an attempt has no recorded outcome, the
    reservation stays open instead of being resolved as absent.
    """
    for candidate in (
        reservation_customer_id,
        _organization_customer_id(organization),
    ):
        normalized_candidate = candidate.strip()
        if normalized_candidate:
            return normalized_candidate
    if reservation_attempted_at is not None and reservation_completed_at is None:
        raise BillingError(
            "A Stripe checkout reservation's customer resolution has no "
            "recorded outcome; the reservation stays open until a resolution "
            "completes. Retry the checkout or reconcile manually."
        )
    lag_anchor = (
        reservation_completed_at or reservation_attempted_at or reservation_created_at
    )
    query_started_at = timezone.now()
    remote_customers = stripe_client.search_customers(
        organization_reference=_organization_reference(organization),
    )
    customer_ids = _distinct_customer_ids(remote_customers)
    if len(customer_ids) > 1:
        raise BillingError(
            "Multiple Stripe customers match the organization for checkout "
            "reconciliation; manual billing reconciliation is required."
        )
    if customer_ids:
        return customer_ids[0]
    if query_started_at - lag_anchor < _STRIPE_SEARCH_INDEX_LAG:
        raise BillingError(
            "A Stripe checkout reservation's creation outcome is unknown and "
            "Stripe's customer search returned no match inside the Search "
            "indexing lag; the reservation stays open until the lag elapses. "
            "Retry after the lag or reconcile manually."
        )
    return ""


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

    existing_customer_id = _organization_customer_id(organization)
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
            existing_customer_id = _organization_customer_id(locked_organization)
            if existing_customer_id == normalized_customer_id:
                return
            if existing_customer_id:
                raise BillingWebhookError(
                    "Stripe customer identity conflicts with the organization's "
                    "current billing customer; automatic replacement was refused."
                )
            if BillingCustomer.objects.filter(
                stripe_customer_id=normalized_customer_id
            ).exists():
                raise BillingWebhookError(
                    "Stripe customer identity is already owned by another "
                    "organization; automatic assignment was refused."
                )
            BillingCustomer.objects.create(
                organization=locked_organization,
                stripe_customer_id=normalized_customer_id,
            )
    except IntegrityError as exc:
        raise BillingWebhookError(
            "Stripe customer identity is already owned by another organization; "
            "automatic assignment was refused."
        ) from exc


def _resolve_organization_by_customer_id(customer_id: str) -> Any | None:
    normalized_customer_id = customer_id.strip()
    if not normalized_customer_id:
        return None

    customer = (
        BillingCustomer.objects.select_related("organization")
        .filter(stripe_customer_id=normalized_customer_id)
        .first()
    )
    if customer is not None:
        return customer.organization

    subscription = (
        Subscription.all_objects.select_related("organization")
        .filter(stripe_customer_id=normalized_customer_id)
        .order_by("-pk")
        .first()
    )
    if subscription is None:
        return None
    return subscription.organization
