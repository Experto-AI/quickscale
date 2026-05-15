"""Runtime billing services for the QuickScale billing module."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
from importlib import import_module
import json
import os
from typing import Any, cast

from django.apps import apps
from django.conf import settings
from django.db import transaction

from quickscale_modules_billing.models import (
    CreditBalance,
    CreditTransaction,
    Plan,
    Subscription,
    WebhookEvent,
)

DEFAULT_BILLING_CURRENCY = "usd"
DEFAULT_BILLING_PUBLISHABLE_KEY_ENV_VAR = "STRIPE_PUBLISHABLE_KEY"
DEFAULT_BILLING_SECRET_KEY_ENV_VAR = "STRIPE_SECRET_KEY"
DEFAULT_BILLING_WEBHOOK_SECRET_ENV_VAR = "QUICKSCALE_BILLING_WEBHOOK_SECRET"
STRIPE_EVENT_TYPE_INVOICE_PAID = "invoice.paid"
_INVOICE_REFERENCE_KEYS = ("invoice_id",)
_BUSINESS_OBJECT_REFERENCE_KEYS = (
    "checkout_session_id",
    "payment_intent_id",
    "charge_id",
    "credit_grant_id",
    "stripe_subscription_id",
)
_USER_METADATA_KEY = "quickscale_user_reference"


class BillingError(Exception):
    """Base error for billing runtime operations."""


class BillingConfigurationError(BillingError):
    """Raised when runtime billing configuration is invalid."""


class BillingDisabledError(BillingError):
    """Raised when the billing runtime is disabled."""


class BillingValidationError(BillingError):
    """Raised when a billing request is structurally invalid."""


class BillingWebhookError(BillingError):
    """Raised when Stripe webhook handling fails."""


class BillingWebhookSignatureError(BillingWebhookError):
    """Raised when Stripe webhook signature validation fails."""


@dataclass(frozen=True)
class BillingSettingsSnapshot:
    """Immutable runtime view of the authoritative billing settings."""

    enabled: bool
    publishable_key_env_var: str
    secret_key_env_var: str
    webhook_secret_env_var: str
    billing_currency: str

    @classmethod
    def from_settings(cls) -> BillingSettingsSnapshot:
        """Create a billing runtime snapshot from Django settings."""
        return cls(
            enabled=bool(getattr(settings, "QUICKSCALE_BILLING_ENABLED", True)),
            publishable_key_env_var=str(
                getattr(
                    settings,
                    "QUICKSCALE_BILLING_PUBLISHABLE_KEY_ENV_VAR",
                    DEFAULT_BILLING_PUBLISHABLE_KEY_ENV_VAR,
                )
            ).strip()
            or DEFAULT_BILLING_PUBLISHABLE_KEY_ENV_VAR,
            secret_key_env_var=str(
                getattr(
                    settings,
                    "QUICKSCALE_BILLING_SECRET_KEY_ENV_VAR",
                    DEFAULT_BILLING_SECRET_KEY_ENV_VAR,
                )
            ).strip()
            or DEFAULT_BILLING_SECRET_KEY_ENV_VAR,
            webhook_secret_env_var=str(
                getattr(
                    settings,
                    "QUICKSCALE_BILLING_WEBHOOK_SECRET_ENV_VAR",
                    DEFAULT_BILLING_WEBHOOK_SECRET_ENV_VAR,
                )
            ).strip()
            or DEFAULT_BILLING_WEBHOOK_SECRET_ENV_VAR,
            billing_currency=str(
                getattr(
                    settings,
                    "QUICKSCALE_BILLING_CURRENCY",
                    DEFAULT_BILLING_CURRENCY,
                )
            ).strip()
            or DEFAULT_BILLING_CURRENCY,
        )

    def resolve_publishable_key(self) -> str:
        """Resolve the Stripe publishable key from the configured env var."""
        return os.getenv(self.publishable_key_env_var, "").strip()

    def resolve_secret_key(self) -> str:
        """Resolve the Stripe secret key from the configured env var."""
        return os.getenv(self.secret_key_env_var, "").strip()

    def resolve_webhook_secret(self) -> str:
        """Resolve the Stripe webhook secret from the configured env var."""
        return os.getenv(self.webhook_secret_env_var, "").strip()


@dataclass(frozen=True)
class StripeWebhookResult:
    """Result returned after Stripe webhook handling."""

    duplicate: bool
    event_type: str
    status: str


class StripeClient:
    """Thin Stripe SDK wrapper used by the billing runtime and tests."""

    def __init__(self, *, stripe_module: Any, api_key: str) -> None:
        self._stripe_module = stripe_module
        self._api_key = api_key

    def search_customers(self, *, user_reference: str) -> list[dict[str, Any]]:
        """Search Stripe customers by the schema-neutral user metadata key."""
        self._activate_api_key()
        query = f"metadata['{_USER_METADATA_KEY}']:'{user_reference}'"
        search_result = self._stripe_module.Customer.search(query=query, limit=1)
        data = getattr(search_result, "data", None)
        if data is None and isinstance(search_result, Mapping):
            data = search_result.get("data", [])
        return [_normalize_mapping(item) for item in data or []]

    def create_customer(
        self,
        *,
        email: str,
        name: str,
        metadata: Mapping[str, str],
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Create a Stripe customer with schema-neutral local metadata."""
        self._activate_api_key()
        create_kwargs: dict[str, Any] = {"metadata": dict(metadata)}
        if email:
            create_kwargs["email"] = email
        if name:
            create_kwargs["name"] = name
        if idempotency_key:
            create_kwargs["idempotency_key"] = idempotency_key
        created_customer = self._stripe_module.Customer.create(**create_kwargs)
        return _normalize_mapping(created_customer)

    def construct_event(
        self,
        *,
        body: bytes,
        signature: str,
        webhook_secret: str,
    ) -> dict[str, Any]:
        """Verify and deserialize a Stripe webhook event."""
        if not signature.strip():
            raise BillingWebhookSignatureError("Webhook signature is invalid.")
        try:
            event = self._stripe_module.Webhook.construct_event(
                payload=body,
                sig_header=signature,
                secret=webhook_secret,
            )
        except ValueError as exc:
            raise BillingWebhookError("Webhook payload is invalid.") from exc
        except Exception as exc:  # pragma: no cover - SDK exception types vary
            message = str(exc).strip()
            if exc.__class__.__name__ == "SignatureVerificationError":
                raise BillingWebhookSignatureError(
                    "Webhook signature is invalid."
                ) from exc
            if "signature" in message.casefold():
                raise BillingWebhookSignatureError(
                    "Webhook signature is invalid."
                ) from exc
            raise BillingWebhookError(
                message or "Stripe webhook verification failed."
            ) from exc
        return _normalize_mapping(event)

    def _activate_api_key(self) -> None:
        if hasattr(self._stripe_module, "api_key"):
            setattr(self._stripe_module, "api_key", self._api_key)


def get_stripe_client(
    *,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> StripeClient:
    """Return a configured Stripe client for the current runtime settings."""
    snapshot = settings_snapshot or BillingSettingsSnapshot.from_settings()
    secret_key = snapshot.resolve_secret_key()
    if not secret_key:
        raise BillingConfigurationError(
            "Stripe secret key is not configured in the runtime environment."
        )
    try:
        stripe_module = import_module("stripe")
    except ImportError as exc:
        raise BillingConfigurationError(
            "Stripe SDK is not installed in this environment."
        ) from exc
    return StripeClient(stripe_module=stripe_module, api_key=secret_key)


def get_or_create_stripe_customer(
    user: Any,
    *,
    stripe_client: Any | None = None,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> tuple[str, bool]:
    """Resolve or create a Stripe customer for the given local user."""
    snapshot = settings_snapshot or BillingSettingsSnapshot.from_settings()
    _ensure_billing_enabled(snapshot)

    existing_customer_id = (
        Subscription.objects.filter(user=user)
        .exclude(stripe_customer_id="")
        .order_by("-pk")
        .values_list("stripe_customer_id", flat=True)
        .first()
    )
    if existing_customer_id:
        return str(existing_customer_id), False

    resolved_client = stripe_client or get_stripe_client(settings_snapshot=snapshot)
    customer_metadata = _build_customer_metadata(user)
    remote_customers = resolved_client.search_customers(
        user_reference=customer_metadata[_USER_METADATA_KEY]
    )
    if remote_customers:
        remote_customer_id = str(remote_customers[0].get("id") or "").strip()
        if not remote_customer_id:
            raise BillingWebhookError(
                "Stripe customer search returned a customer without an id."
            )
        return remote_customer_id, False

    created_customer = resolved_client.create_customer(
        email="",
        name="",
        metadata=customer_metadata,
        idempotency_key=_build_customer_create_idempotency_key(
            customer_metadata[_USER_METADATA_KEY]
        ),
    )
    created_customer_id = str(created_customer.get("id") or "").strip()
    if not created_customer_id:
        raise BillingWebhookError("Stripe customer creation did not return an id.")
    return created_customer_id, True


def credit_user(
    user: Any,
    *,
    amount: int,
    transaction_type: str,
    description: str = "",
    stripe_event_id: str = "",
    stripe_object_id: str = "",
    stripe_reference_data: Mapping[str, Any] | None = None,
) -> CreditTransaction:
    """Credit a user once for a Stripe-backed business object."""
    if amount <= 0:
        raise BillingValidationError("Credit amount must be greater than zero.")

    normalized_reference_data = _normalize_mapping(stripe_reference_data or {})
    with transaction.atomic():
        balance, _ = CreditBalance.get_or_create_for_user(user)
        existing_transaction = _find_existing_credit_transaction(
            user=user,
            transaction_type=transaction_type,
            stripe_event_id=stripe_event_id,
            stripe_object_id=stripe_object_id,
            stripe_reference_data=normalized_reference_data,
        )
        if existing_transaction is not None:
            return existing_transaction

        updated_balance = balance.balance + amount
        transaction_row = CreditTransaction.objects.create(
            user=user,
            amount=amount,
            transaction_type=transaction_type,
            stripe_event_id=stripe_event_id,
            stripe_object_id=stripe_object_id,
            stripe_reference_data=normalized_reference_data,
            description=description,
            balance_after=updated_balance,
        )
        balance.balance = updated_balance
        balance.save(update_fields=["balance", "updated_at"])
        return transaction_row


def handle_stripe_event(
    *,
    body: bytes,
    signature: str,
    stripe_client: Any | None = None,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> StripeWebhookResult:
    """Verify, record, and handle a Stripe webhook event idempotently."""
    snapshot = settings_snapshot or BillingSettingsSnapshot.from_settings()
    _ensure_billing_enabled(snapshot)

    webhook_secret = snapshot.resolve_webhook_secret()
    if not webhook_secret:
        raise BillingConfigurationError(
            "Stripe webhook secret is not configured in the runtime environment."
        )

    resolved_client = stripe_client or get_stripe_client(settings_snapshot=snapshot)
    event_payload = resolved_client.construct_event(
        body=body,
        signature=signature,
        webhook_secret=webhook_secret,
    )
    event_id = str(event_payload.get("id") or "").strip()
    event_type = str(event_payload.get("type") or "").strip()
    if not event_id:
        raise BillingWebhookError("Stripe event payload is missing an id.")
    if not event_type:
        raise BillingWebhookError("Stripe event payload is missing a type.")

    webhook_event, _ = WebhookEvent.objects.get_or_create(
        stripe_event_id=event_id,
        defaults={
            "event_type": event_type,
            "payload": event_payload,
        },
    )

    try:
        with transaction.atomic():
            locked_event = WebhookEvent.objects.select_for_update().get(
                pk=webhook_event.pk
            )
            if locked_event.processed:
                return StripeWebhookResult(
                    duplicate=True,
                    event_type=locked_event.event_type,
                    status="duplicate",
                )

            locked_event.event_type = event_type
            locked_event.payload = event_payload
            locked_event.processing_error = ""
            locked_event.save(
                update_fields=["event_type", "payload", "processing_error"]
            )

            if event_type == STRIPE_EVENT_TYPE_INVOICE_PAID:
                _handle_invoice_paid_event(event_payload)
                processing_status = "processed"
            else:
                processing_status = "ignored"
            locked_event.processed = True
            locked_event.processing_error = ""
            locked_event.save(update_fields=["processed", "processing_error"])
            return StripeWebhookResult(
                duplicate=False,
                event_type=event_type,
                status=processing_status,
            )
    except BillingError as exc:
        WebhookEvent.objects.filter(pk=webhook_event.pk).update(
            event_type=event_type,
            payload=event_payload,
            processed=False,
            processing_error=str(exc),
        )
        raise


def _ensure_billing_enabled(settings_snapshot: BillingSettingsSnapshot) -> None:
    if not settings_snapshot.enabled:
        raise BillingDisabledError("Billing module is disabled.")


def _handle_invoice_paid_event(event_payload: Mapping[str, Any]) -> CreditTransaction:
    invoice_payload = _extract_event_object(event_payload)
    invoice_id = str(invoice_payload.get("id") or "").strip()
    if not invoice_id:
        raise BillingWebhookError("Stripe invoice payload is missing an id.")

    price_id = _extract_price_id(invoice_payload)
    plan = Plan.objects.filter(stripe_price_id=price_id).order_by("pk").first()
    if plan is None:
        raise BillingWebhookError(f"No billing plan matches Stripe price {price_id}.")

    user = _resolve_user_for_invoice(invoice_payload=invoice_payload)
    if user is None:
        raise BillingWebhookError(
            "Could not resolve a local user for the Stripe invoice."
        )

    subscription_id = str(invoice_payload.get("subscription") or "").strip()
    customer_id = str(invoice_payload.get("customer") or "").strip()
    reference_data: dict[str, Any] = {
        "invoice_id": invoice_id,
        "stripe_customer_id": customer_id,
        "stripe_price_id": price_id,
    }
    if subscription_id:
        reference_data["stripe_subscription_id"] = subscription_id

    return credit_user(
        user,
        amount=plan.credits_per_period,
        transaction_type=CreditTransaction.TransactionType.PLAN,
        description=f"{plan.name} credits from Stripe invoice {invoice_id}",
        stripe_event_id=str(event_payload.get("id") or "").strip(),
        stripe_object_id=invoice_id,
        stripe_reference_data=reference_data,
    )


def _extract_event_object(event_payload: Mapping[str, Any]) -> dict[str, Any]:
    event_data = event_payload.get("data")
    if not isinstance(event_data, Mapping):
        raise BillingWebhookError("Stripe event payload is missing data.object.")
    event_object = event_data.get("object")
    if not isinstance(event_object, Mapping):
        raise BillingWebhookError("Stripe event payload is missing data.object.")
    return _normalize_mapping(event_object)


def _extract_price_id(invoice_payload: Mapping[str, Any]) -> str:
    line_items = invoice_payload.get("lines")
    line_item_data: list[Mapping[str, Any]] = []
    if isinstance(line_items, Mapping):
        raw_data = line_items.get("data", [])
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
            "Stripe invoice payload contains multiple billing price ids."
        )

    fallback_price_id = str(
        _normalize_mapping(invoice_payload.get("metadata") or {}).get(
            "stripe_price_id",
            "",
        )
    ).strip()
    if fallback_price_id:
        return fallback_price_id

    raise BillingWebhookError("Stripe invoice payload is missing a billing price id.")


def _resolve_user_for_invoice(*, invoice_payload: Mapping[str, Any]) -> Any | None:
    customer_id = str(invoice_payload.get("customer") or "").strip()
    if customer_id:
        subscription = (
            Subscription.objects.select_related("user")
            .filter(stripe_customer_id=customer_id)
            .order_by("-pk")
            .first()
        )
        if subscription is not None:
            return subscription.user

    metadata_sources = [
        invoice_payload,
        _normalize_mapping(invoice_payload.get("subscription_details") or {}),
        _normalize_mapping(invoice_payload.get("parent") or {}),
    ]
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


def _build_customer_metadata(user: Any) -> dict[str, str]:
    return {
        _USER_METADATA_KEY: _user_reference(user),
        "quickscale_user_model": str(user._meta.label_lower),
        "quickscale_user_pk": str(user.pk),
    }


def _build_customer_create_idempotency_key(user_reference: str) -> str:
    digest = hashlib.sha256(user_reference.encode("utf-8")).hexdigest()
    return f"quickscale-billing-customer:{digest}"


def _user_reference(user: Any) -> str:
    return f"{user._meta.label_lower}:{user.pk}"


def _display_name_for_user(user: Any) -> str:
    get_full_name = getattr(user, "get_full_name", None)
    if callable(get_full_name):
        full_name = str(get_full_name() or "").strip()
        if full_name:
            return full_name
    return _string_field(user, "username") or _string_field(user, "email")


def _string_field(instance: Any, field_name: str) -> str:
    return str(getattr(instance, field_name, "") or "").strip()


def _find_existing_credit_transaction(
    *,
    user: Any,
    transaction_type: str,
    stripe_event_id: str,
    stripe_object_id: str,
    stripe_reference_data: Mapping[str, Any],
) -> CreditTransaction | None:
    candidate_queryset = CreditTransaction.objects.select_for_update().filter(
        user=user,
        transaction_type=transaction_type,
    )
    if stripe_object_id:
        existing = candidate_queryset.filter(stripe_object_id=stripe_object_id).first()
        if existing is not None:
            return existing
    if stripe_event_id:
        existing = candidate_queryset.filter(stripe_event_id=stripe_event_id).first()
        if existing is not None:
            return existing
    if not stripe_reference_data:
        return None

    for candidate in candidate_queryset.order_by("-pk"):
        if _has_matching_business_reference(
            candidate.stripe_reference_data,
            stripe_reference_data,
        ):
            return candidate
    return None


def _has_matching_business_reference(
    existing_reference_data: Mapping[str, Any],
    incoming_reference_data: Mapping[str, Any],
) -> bool:
    existing_data = _normalize_mapping(existing_reference_data)
    incoming_data = _normalize_mapping(incoming_reference_data)
    reference_keys: tuple[str, ...] = _BUSINESS_OBJECT_REFERENCE_KEYS
    if (
        str(existing_data.get("invoice_id") or "").strip()
        or str(incoming_data.get("invoice_id") or "").strip()
    ):
        reference_keys = _INVOICE_REFERENCE_KEYS

    for key in reference_keys:
        existing_value = str(existing_data.get(key) or "").strip()
        incoming_value = str(incoming_data.get(key) or "").strip()
        if existing_value and incoming_value and existing_value == incoming_value:
            return True
    return False


def _normalize_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    serialized = json.dumps(dict(value), default=str)
    return cast(dict[str, Any], json.loads(serialized))


__all__ = [
    "BillingConfigurationError",
    "BillingDisabledError",
    "BillingError",
    "BillingSettingsSnapshot",
    "BillingValidationError",
    "BillingWebhookError",
    "BillingWebhookSignatureError",
    "StripeClient",
    "StripeWebhookResult",
    "credit_user",
    "get_or_create_stripe_customer",
    "get_stripe_client",
    "handle_stripe_event",
]
