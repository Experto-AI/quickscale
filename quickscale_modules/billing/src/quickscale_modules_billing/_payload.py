"""Stripe payload extraction, normalization, references, and metadata.

Implementation detail of :mod:`quickscale_modules_billing.services`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from datetime import timezone as dt_timezone
from typing import Any, cast

from django.utils import timezone

from quickscale_modules_billing._settings import (
    _CUSTOMER_SEARCH_REFERENCE_UNSAFE_CHARACTERS as _CUSTOMER_SEARCH_REFERENCE_UNSAFE_CHARACTERS,
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
    _PLAN_SLUG_METADATA_KEY as _PLAN_SLUG_METADATA_KEY,
)
from quickscale_modules_billing._settings import (
    _PRICE_ID_METADATA_KEY as _PRICE_ID_METADATA_KEY,
)
from quickscale_modules_billing._settings import (
    _PURCHASE_CHECKOUT_REFERENCE_METADATA_KEY as _PURCHASE_CHECKOUT_REFERENCE_METADATA_KEY,
)
from quickscale_modules_billing._settings import (
    _STRIPE_TO_LOCAL_SUBSCRIPTION_STATUS as _STRIPE_TO_LOCAL_SUBSCRIPTION_STATUS,
)
from quickscale_modules_billing._settings import (
    _SUBSCRIPTION_CHECKOUT_REFERENCE_METADATA_KEY as _SUBSCRIPTION_CHECKOUT_REFERENCE_METADATA_KEY,
)
from quickscale_modules_billing._settings import (
    _USER_METADATA_KEY as _USER_METADATA_KEY,
)
from quickscale_modules_billing.exceptions import (
    BillingValidationError,
    BillingWebhookError,
)
from quickscale_modules_billing.models import (
    Plan,
    PurchaseCheckout,
    Subscription,
)


def _extract_event_object(event_payload: Mapping[str, Any]) -> dict[str, Any]:
    event_data = event_payload.get("data")
    if not isinstance(event_data, Mapping):
        raise BillingWebhookError("Stripe event payload is missing data.object.")
    event_object = event_data.get("object")
    if not isinstance(event_object, Mapping):
        raise BillingWebhookError("Stripe event payload is missing data.object.")
    return _normalize_mapping(event_object)


def _invoice_subscription_details(invoice_payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return the dahlia ``invoice.parent.subscription_details`` mapping.

    Under the pinned API version the invoice's subscription id and its
    metadata snapshot live on the parent, never on the invoice itself.
    """
    parent = _normalize_mapping(invoice_payload.get("parent") or {})
    return _normalize_mapping(parent.get("subscription_details") or {})


def _invoice_subscription_id(invoice_payload: Mapping[str, Any]) -> str:
    """Return the invoice's Stripe subscription id under the pinned version."""
    return _stripe_object_id(
        _invoice_subscription_details(invoice_payload).get("subscription")
    )


def _extract_price_id(invoice_payload: Mapping[str, Any]) -> str:
    line_items = invoice_payload.get("lines")
    line_item_data: list[Mapping[str, Any]] = []
    if isinstance(line_items, Mapping):
        raw_data = line_items.get("data", [])
        if isinstance(raw_data, list):
            line_item_data = [item for item in raw_data if isinstance(item, Mapping)]

    price_ids: set[str] = set()
    for line_item in line_item_data:
        price_id = _dahlia_line_item_price_id(line_item)
        if price_id:
            price_ids.add(price_id)
    if len(price_ids) == 1:
        return next(iter(price_ids))
    if len(price_ids) > 1:
        raise BillingWebhookError(
            "Stripe invoice payload contains multiple billing price ids."
        )

    fallback_price_id = str(
        _normalize_mapping(
            _invoice_subscription_details(invoice_payload).get("metadata") or {}
        ).get(_PRICE_ID_METADATA_KEY, "")
    ).strip()
    if fallback_price_id:
        return fallback_price_id

    raise BillingWebhookError("Stripe invoice payload is missing a billing price id.")


def _dahlia_line_item_price_id(line_item: Mapping[str, Any]) -> str:
    """Return the price id from a dahlia invoice line item's pricing block."""
    pricing = _normalize_mapping(line_item.get("pricing") or {})
    if str(pricing.get("type") or "").strip() != "price_details":
        return ""
    price_details = _normalize_mapping(pricing.get("price_details") or {})
    return _stripe_object_id(price_details.get("price"))


def _extract_subscription_price_id(subscription_payload: Mapping[str, Any]) -> str:
    subscription_items = subscription_payload.get("items")
    line_item_data: list[Mapping[str, Any]] = []
    if isinstance(subscription_items, Mapping):
        raw_data = subscription_items.get("data", [])
        if isinstance(raw_data, list):
            line_item_data = [item for item in raw_data if isinstance(item, Mapping)]

    price_ids = {
        str(price_data.get("id") or "").strip()
        for line_item in line_item_data
        for price_data in [_normalize_mapping(line_item.get("price") or {})]
        if str(price_data.get("id") or "").strip()
    }
    if len(price_ids) == 1:
        return next(iter(price_ids))
    if len(price_ids) > 1:
        raise BillingWebhookError(
            "Stripe subscription payload contains multiple billing price ids."
        )

    fallback_price_id = str(
        _normalize_mapping(subscription_payload.get("metadata") or {}).get(
            _PRICE_ID_METADATA_KEY,
            "",
        )
    ).strip()
    if fallback_price_id:
        return fallback_price_id

    raise BillingWebhookError(
        "Stripe subscription payload is missing a billing price id."
    )


def _extract_subscription_period_bounds(
    subscription_payload: Mapping[str, Any],
) -> tuple[datetime | None, datetime | None]:
    """Return the subscription items' agreed billing-period bounds.

    Under the pinned API version period bounds exist only on subscription
    items. Every item that reports a bound must agree, matching the one-price
    rule the subscription price extraction already enforces.
    """
    subscription_items = subscription_payload.get("items")
    item_data: list[Mapping[str, Any]] = []
    if isinstance(subscription_items, Mapping):
        raw_data = subscription_items.get("data", [])
        if isinstance(raw_data, list):
            item_data = [item for item in raw_data if isinstance(item, Mapping)]

    period_starts: set[int] = set()
    period_ends: set[int] = set()
    for item in item_data:
        period_start = _normalize_integer(item.get("current_period_start"))
        period_end = _normalize_integer(item.get("current_period_end"))
        if period_start is not None and period_start > 0:
            period_starts.add(period_start)
        if period_end is not None and period_end > 0:
            period_ends.add(period_end)
    if len(period_starts) > 1:
        raise BillingWebhookError(
            "Stripe subscription items disagree on current_period_start."
        )
    if len(period_ends) > 1:
        raise BillingWebhookError(
            "Stripe subscription items disagree on current_period_end."
        )
    return (
        _stripe_timestamp_to_datetime(next(iter(period_starts)))
        if period_starts
        else None,
        _stripe_timestamp_to_datetime(next(iter(period_ends))) if period_ends else None,
    )


def _resolve_purchase_checkout_reference(
    metadata_sources: list[Mapping[str, Any]],
) -> str:
    """Return one immutable purchase reservation marker or fail on conflict."""
    references = {
        str(metadata.get(_PURCHASE_CHECKOUT_REFERENCE_METADATA_KEY) or "").strip()
        for metadata_source in metadata_sources
        for metadata in [metadata_source.get("metadata")]
        if isinstance(metadata, Mapping)
        and str(metadata.get(_PURCHASE_CHECKOUT_REFERENCE_METADATA_KEY) or "").strip()
    }
    if len(references) > 1:
        raise BillingWebhookError(
            "Stripe checkout metadata contains conflicting purchase reservation "
            "references."
        )
    return next(iter(references)) if references else ""


def _purchase_checkout_pk_from_reference(reservation_reference: str) -> str | None:
    """Return the local pk encoded in one PurchaseCheckout reference."""
    normalized_reference = reservation_reference.strip()
    if not normalized_reference:
        return None
    model_label, separator, pk_value = normalized_reference.partition(":")
    if (
        not separator
        or model_label != PurchaseCheckout._meta.label_lower
        or not pk_value
    ):
        return None
    return pk_value


def _resolve_subscription_checkout_reference(
    metadata_sources: list[Mapping[str, Any]],
) -> str:
    """Return one immutable subscription reservation marker or fail on conflict."""
    references = {
        str(metadata.get(_SUBSCRIPTION_CHECKOUT_REFERENCE_METADATA_KEY) or "").strip()
        for metadata_source in metadata_sources
        for metadata in [metadata_source.get("metadata")]
        if isinstance(metadata, Mapping)
        and str(
            metadata.get(_SUBSCRIPTION_CHECKOUT_REFERENCE_METADATA_KEY) or ""
        ).strip()
    }
    if len(references) > 1:
        raise BillingWebhookError(
            "Stripe checkout metadata contains conflicting subscription reservation "
            "references."
        )
    return next(iter(references)) if references else ""


def _subscription_checkout_pk_from_reference(
    reservation_reference: str,
) -> str | None:
    """Return the local pk encoded in one Subscription reference."""
    normalized_reference = reservation_reference.strip()
    if not normalized_reference:
        return None
    model_label, separator, pk_value = normalized_reference.partition(":")
    if not separator or model_label != Subscription._meta.label_lower or not pk_value:
        return None
    return pk_value


def _checkout_session_metadata_is_complete(
    checkout_session_payload: Mapping[str, Any],
) -> bool:
    metadata = _normalize_mapping(checkout_session_payload.get("metadata") or {})
    user_reference = str(metadata.get(_USER_METADATA_KEY) or "").strip()
    plan_slug = str(metadata.get(_PLAN_SLUG_METADATA_KEY) or "").strip()
    price_id = str(metadata.get(_PRICE_ID_METADATA_KEY) or "").strip()
    return bool(user_reference and (plan_slug or price_id))


def _extract_metadata_value(
    metadata_sources: list[Mapping[str, Any]],
    key: str,
) -> str:
    for metadata_source in metadata_sources:
        metadata = metadata_source.get("metadata")
        if not isinstance(metadata, Mapping):
            continue
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    return ""


def _build_checkout_session_metadata(
    user: Any,
    plan: Plan,
    *,
    organization: Any,
) -> dict[str, str]:
    metadata = _build_customer_metadata(user, organization=organization)
    metadata.update(
        {
            _PLAN_SLUG_METADATA_KEY: plan.slug,
            _PLAN_CREDITS_METADATA_KEY: str(plan.credits_per_period),
            _PLAN_INTERVAL_METADATA_KEY: plan.billing_interval,
            _PRICE_ID_METADATA_KEY: plan.stripe_price_id,
        }
    )
    return metadata


def _extract_live_checkout_session_url(
    checkout_session_payload: Mapping[str, Any],
) -> str:
    checkout_url = str(checkout_session_payload.get("url") or "").strip()
    if not checkout_url:
        return ""

    session_status = str(checkout_session_payload.get("status") or "").strip().lower()
    if session_status and session_status != "open":
        return ""

    expires_at = _extract_checkout_session_expires_at(checkout_session_payload)
    if expires_at is not None and expires_at <= timezone.now():
        return ""
    return checkout_url


def _extract_checkout_session_expires_at(
    checkout_session_payload: Mapping[str, Any],
) -> datetime | None:
    return _stripe_timestamp_to_datetime(checkout_session_payload.get("expires_at"))


def _stripe_timestamp_to_datetime(value: Any) -> datetime | None:
    normalized_timestamp = _normalize_integer(value)
    if normalized_timestamp is None or normalized_timestamp <= 0:
        return None
    return datetime.fromtimestamp(normalized_timestamp, tz=dt_timezone.utc)


def _stripe_named_release(api_version: str) -> str:
    """Return the named release (the suffix after the date) of an API version."""
    normalized_version = api_version.strip()
    if not normalized_version:
        return ""
    _, separator, named_release = normalized_version.rpartition(".")
    if separator and named_release:
        return named_release
    return normalized_version


def _map_stripe_subscription_status(stripe_status: str) -> str:
    normalized_status = stripe_status.strip().lower()
    if normalized_status in _STRIPE_TO_LOCAL_SUBSCRIPTION_STATUS:
        return _STRIPE_TO_LOCAL_SUBSCRIPTION_STATUS[normalized_status]
    raise BillingWebhookError(
        f"Stripe subscription status {normalized_status or '<blank>'} is not supported."
    )


def _normalize_integer(value: Any) -> int | None:
    try:
        return int(value)
    except TypeError, ValueError:
        return None


def _stripe_object_id(value: Any) -> str:
    """Return an id from a Stripe expandable object or scalar id."""
    if isinstance(value, Mapping):
        return str(value.get("id") or "").strip()
    return str(value or "").strip()


def _build_customer_metadata(
    user: Any,
    *,
    organization: Any,
) -> dict[str, str]:
    metadata: dict[str, str] = {
        _ORG_REFERENCE_METADATA_KEY: _organization_reference(organization),
        "quickscale_org_model": str(organization._meta.label_lower),
        "quickscale_org_pk": str(organization.pk),
    }
    metadata.update(
        {
            _USER_METADATA_KEY: _user_reference(user),
            "quickscale_user_model": str(user._meta.label_lower),
            "quickscale_user_pk": str(user.pk),
        }
    )
    return metadata


def _build_customer_create_idempotency_key(user_reference: str) -> str:
    digest = hashlib.sha256(user_reference.encode("utf-8")).hexdigest()
    return f"quickscale-billing-customer:{digest}"


def _build_purchase_checkout_create_idempotency_key(
    reservation_reference: str,
) -> str:
    digest = hashlib.sha256(reservation_reference.encode("utf-8")).hexdigest()
    return f"quickscale-purchase-checkout:{digest}"


def _purchase_checkout_reference(reservation: PurchaseCheckout) -> str:
    return f"{reservation._meta.label_lower}:{reservation.pk}"


def _build_subscription_checkout_create_idempotency_key(
    reservation_reference: str,
) -> str:
    digest = hashlib.sha256(reservation_reference.encode("utf-8")).hexdigest()
    return f"quickscale-subscription-checkout:{digest}"


def _subscription_checkout_reference(reservation: Subscription) -> str:
    return f"{reservation._meta.label_lower}:{reservation.pk}"


def _organization_reference(organization: Any) -> str:
    return f"{organization._meta.label_lower}:{organization.pk}"


def _user_reference(user: Any) -> str:
    return f"{user._meta.label_lower}:{user.pk}"


def _validate_customer_search_reference(*, field_name: str, reference: str) -> None:
    """Reject a customer-search reference that would break the Stripe query."""
    for character, label in _CUSTOMER_SEARCH_REFERENCE_UNSAFE_CHARACTERS:
        if character in reference:
            raise BillingValidationError(
                f"{field_name} contains an unsupported {label} character "
                f"({character!r}) for a Stripe customer search reference."
            )


def _display_name_for_user(user: Any) -> str:
    get_full_name = getattr(user, "get_full_name", None)
    if callable(get_full_name):
        full_name = str(get_full_name() or "").strip()
        if full_name:
            return full_name
    return _string_field(user, "username") or _string_field(user, "email")


def _string_field(instance: Any, field_name: str) -> str:
    return str(getattr(instance, field_name, "") or "").strip()


def _normalize_mapping(value: Any) -> dict[str, Any]:
    """Return a JSON-safe mapping, converting Stripe SDK objects first.

    Since stripe-python 13 a ``StripeObject`` is neither a ``dict`` subclass
    nor a ``collections.abc.Mapping``, so an SDK response must be converted
    with its own recursive ``to_dict()`` before the mapping check.
    """
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        value = to_dict()
    if not isinstance(value, Mapping):
        return {}
    serialized = json.dumps(dict(value), default=str)
    return cast(dict[str, Any], json.loads(serialized))
