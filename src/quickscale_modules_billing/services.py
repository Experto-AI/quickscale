"""Runtime billing services for the QuickScale billing module."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
import hashlib
from importlib import import_module
import json
import os
from typing import Any, cast

from django.apps import apps
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

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
STRIPE_EVENT_TYPE_CHECKOUT_SESSION_COMPLETED = "checkout.session.completed"
STRIPE_EVENT_TYPE_INVOICE_PAID = "invoice.paid"
STRIPE_EVENT_TYPE_INVOICE_PAYMENT_FAILED = "invoice.payment_failed"
STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_CREATED = "customer.subscription.created"
STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_UPDATED = "customer.subscription.updated"
STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_DELETED = "customer.subscription.deleted"
_INVOICE_REFERENCE_KEYS = ("invoice_id",)
_BUSINESS_OBJECT_REFERENCE_KEYS = (
    "checkout_session_id",
    "payment_intent_id",
    "charge_id",
    "credit_grant_id",
    "stripe_subscription_id",
)
_USER_METADATA_KEY = "quickscale_user_reference"
_PLAN_SLUG_METADATA_KEY = "quickscale_plan_slug"
_PLAN_CREDITS_METADATA_KEY = "quickscale_plan_credits"
_PLAN_INTERVAL_METADATA_KEY = "quickscale_plan_interval"
_PRICE_ID_METADATA_KEY = "stripe_price_id"
_CREDITABLE_INVOICE_BILLING_REASONS = frozenset(
    {"subscription_create", "subscription_cycle"}
)
_CURRENT_RECURRING_SUBSCRIPTION_ERROR = (
    "User already has a current recurring subscription."
)
_STRIPE_RECURRING_INTERVAL_BY_PLAN_INTERVAL = {
    Plan.BillingInterval.MONTHLY: "month",
    Plan.BillingInterval.YEARLY: "year",
}
_STRIPE_TO_LOCAL_SUBSCRIPTION_STATUS = {
    "incomplete": Subscription.Status.INCOMPLETE,
    "incomplete_expired": Subscription.Status.INCOMPLETE_EXPIRED,
    "trialing": Subscription.Status.TRIALING,
    "active": Subscription.Status.ACTIVE,
    "past_due": Subscription.Status.PAST_DUE,
    "canceled": Subscription.Status.CANCELED,
    "unpaid": Subscription.Status.UNPAID,
    "paused": Subscription.Status.PAUSED,
}


class BillingError(Exception):
    """Base error for billing runtime operations."""


class InsufficientCreditsError(BillingError):
    """Raised when a debit exceeds the available balance."""


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
        publishable_key = os.getenv(self.publishable_key_env_var, "").strip()
        if not publishable_key:
            raise BillingConfigurationError(
                "Stripe publishable key is not configured in the runtime environment."
            )
        return publishable_key

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

    def create_checkout_session(
        self,
        *,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        session_metadata: Mapping[str, str],
        payment_intent_metadata: Mapping[str, str],
        client_reference_id: str,
    ) -> dict[str, Any]:
        """Create a Stripe Checkout Session for a one-time purchase."""
        self._activate_api_key()
        checkout_session_api = self._resolve_checkout_session_api()
        created_session = checkout_session_api.create(
            mode="payment",
            customer=customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=client_reference_id,
            metadata=dict(session_metadata),
            payment_intent_data={"metadata": dict(payment_intent_metadata)},
        )
        return _normalize_mapping(created_session)

    def create_subscription_checkout_session(
        self,
        *,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        session_metadata: Mapping[str, str],
        subscription_metadata: Mapping[str, str],
        client_reference_id: str,
    ) -> dict[str, Any]:
        """Create a Stripe Checkout Session for a recurring subscription."""
        self._activate_api_key()
        checkout_session_api = self._resolve_checkout_session_api()
        created_session = checkout_session_api.create(
            mode="subscription",
            customer=customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=client_reference_id,
            metadata=dict(session_metadata),
            subscription_data={"metadata": dict(subscription_metadata)},
        )
        return _normalize_mapping(created_session)

    def create_billing_portal_session(
        self,
        *,
        customer_id: str,
        return_url: str,
    ) -> dict[str, Any]:
        """Create a Stripe Billing Portal Session for an existing customer."""
        self._activate_api_key()
        billing_portal_session_api = self._resolve_billing_portal_session_api()
        created_session = billing_portal_session_api.create(
            customer=customer_id,
            return_url=return_url,
        )
        return _normalize_mapping(created_session)

    def cancel_subscription(
        self,
        *,
        stripe_subscription_id: str,
    ) -> dict[str, Any]:
        """Schedule a Stripe subscription to cancel at period end."""
        self._activate_api_key()
        subscription_api = getattr(self._stripe_module, "Subscription", None)
        if subscription_api is None:
            raise BillingConfigurationError(
                "Stripe Subscription SDK support is unavailable in this environment."
            )
        if hasattr(subscription_api, "modify"):
            updated_subscription = subscription_api.modify(
                stripe_subscription_id,
                cancel_at_period_end=True,
            )
            return _normalize_mapping(updated_subscription)
        if hasattr(subscription_api, "update"):
            updated_subscription = subscription_api.update(
                stripe_subscription_id,
                cancel_at_period_end=True,
            )
            return _normalize_mapping(updated_subscription)
        raise BillingConfigurationError(
            "Stripe Subscription SDK update support is unavailable in this environment."
        )

    def retrieve_subscription(
        self,
        *,
        stripe_subscription_id: str,
    ) -> dict[str, Any]:
        """Return a normalized Stripe Subscription payload."""
        self._activate_api_key()
        subscription_api = getattr(self._stripe_module, "Subscription", None)
        if subscription_api is None or not hasattr(subscription_api, "retrieve"):
            raise BillingConfigurationError(
                "Stripe Subscription SDK retrieve support is unavailable in this environment."
            )
        subscription = subscription_api.retrieve(stripe_subscription_id)
        return _normalize_mapping(subscription)

    def retrieve_checkout_session(self, *, checkout_session_id: str) -> dict[str, Any]:
        """Return a normalized Stripe Checkout Session payload."""
        self._activate_api_key()
        checkout_session_api = self._resolve_checkout_session_api()
        checkout_session = checkout_session_api.retrieve(checkout_session_id)
        return _normalize_mapping(checkout_session)

    def retrieve_payment_intent(self, *, payment_intent_id: str) -> dict[str, Any]:
        """Return a normalized Stripe PaymentIntent payload."""
        self._activate_api_key()
        payment_intent_api = getattr(self._stripe_module, "PaymentIntent", None)
        if payment_intent_api is None or not hasattr(payment_intent_api, "retrieve"):
            raise BillingConfigurationError(
                "Stripe PaymentIntent SDK support is unavailable in this environment."
            )
        payment_intent = payment_intent_api.retrieve(payment_intent_id)
        return _normalize_mapping(payment_intent)

    def retrieve_price(self, *, price_id: str) -> dict[str, Any]:
        """Return a normalized Stripe Price payload."""
        self._activate_api_key()
        price_api = getattr(self._stripe_module, "Price", None)
        if price_api is None or not hasattr(price_api, "retrieve"):
            raise BillingConfigurationError(
                "Stripe Price SDK support is unavailable in this environment."
            )
        price = price_api.retrieve(price_id)
        return _normalize_mapping(price)

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

    def _resolve_checkout_session_api(self) -> Any:
        checkout_module = getattr(self._stripe_module, "checkout", None)
        checkout_session_api = getattr(checkout_module, "Session", None)
        if checkout_session_api is None:
            raise BillingConfigurationError(
                "Stripe Checkout SDK support is unavailable in this environment."
            )
        return checkout_session_api

    def _resolve_billing_portal_session_api(self) -> Any:
        billing_portal_module = getattr(self._stripe_module, "billing_portal", None)
        billing_portal_session_api = getattr(billing_portal_module, "Session", None)
        if billing_portal_session_api is None:
            raise BillingConfigurationError(
                "Stripe Billing Portal SDK support is unavailable in this environment."
            )
        return billing_portal_session_api


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

    authoritative_subscription = _resolve_authoritative_subscription_reservation(
        user=user,
    )
    if authoritative_subscription is not None:
        existing_customer_id = str(
            authoritative_subscription.stripe_customer_id or ""
        ).strip()
        if existing_customer_id:
            return existing_customer_id, False

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


def create_checkout_session(
    user: Any,
    plan: Plan,
    success_url: str,
    cancel_url: str,
    *,
    stripe_client: Any | None = None,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> str:
    """Create a Stripe Checkout Session for a one-time credit purchase."""
    snapshot = settings_snapshot or BillingSettingsSnapshot.from_settings()
    _ensure_billing_enabled(snapshot)

    normalized_success_url = success_url.strip()
    normalized_cancel_url = cancel_url.strip()
    if not normalized_success_url or not normalized_cancel_url:
        raise BillingValidationError("Checkout success and cancel URLs are required.")

    _validate_one_time_purchase_plan(plan)

    resolved_client = stripe_client or get_stripe_client(settings_snapshot=snapshot)
    stripe_price = resolved_client.retrieve_price(price_id=plan.stripe_price_id)
    _validate_stripe_price_parity(plan=plan, stripe_price=stripe_price)

    customer_id, _ = get_or_create_stripe_customer(
        user,
        stripe_client=resolved_client,
        settings_snapshot=snapshot,
    )
    session_metadata = _build_checkout_session_metadata(user, plan)
    checkout_session = resolved_client.create_checkout_session(
        customer_id=customer_id,
        price_id=plan.stripe_price_id,
        success_url=normalized_success_url,
        cancel_url=normalized_cancel_url,
        session_metadata=session_metadata,
        payment_intent_metadata=session_metadata,
        client_reference_id=_user_reference(user),
    )
    checkout_url = str(checkout_session.get("url") or "").strip()
    if not checkout_url:
        raise BillingError(
            "Stripe checkout session creation did not return a hosted URL."
        )
    return checkout_url


def create_subscription_checkout_session(
    user: Any,
    plan: Plan,
    success_url: str,
    cancel_url: str,
    *,
    stripe_client: Any | None = None,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> str:
    """Create or reuse a Stripe Checkout Session for a recurring subscription."""
    snapshot = settings_snapshot or BillingSettingsSnapshot.from_settings()
    _ensure_billing_enabled(snapshot)

    normalized_success_url = success_url.strip()
    normalized_cancel_url = cancel_url.strip()
    if not normalized_success_url or not normalized_cancel_url:
        raise BillingValidationError("Checkout success and cancel URLs are required.")

    _validate_recurring_subscription_plan(plan)

    resolved_client = stripe_client or get_stripe_client(settings_snapshot=snapshot)
    stripe_price = resolved_client.retrieve_price(price_id=plan.stripe_price_id)
    _validate_stripe_price_parity(plan=plan, stripe_price=stripe_price)

    with transaction.atomic():
        reservation, recovered_from_create_conflict = (
            _prepare_subscription_checkout_reservation(user=user, plan=plan)
        )

    customer_id = str(reservation.stripe_customer_id or "").strip()
    if not customer_id:
        customer_id, _ = get_or_create_stripe_customer(
            user,
            stripe_client=resolved_client,
            settings_snapshot=snapshot,
        )
        with transaction.atomic():
            reservation = Subscription.objects.select_for_update().get(
                pk=reservation.pk
            )
            if not _subscription_reservation_can_be_reused(reservation, plan=plan):
                raise BillingValidationError(_CURRENT_RECURRING_SUBSCRIPTION_ERROR)
            reservation.stripe_customer_id = customer_id
            reservation.save(update_fields=["stripe_customer_id"])

    live_checkout_url = _reuse_live_subscription_checkout_url(
        reservation=reservation,
        stripe_client=resolved_client,
    )
    if live_checkout_url:
        return live_checkout_url
    if recovered_from_create_conflict:
        raise BillingValidationError(_CURRENT_RECURRING_SUBSCRIPTION_ERROR)

    if str(reservation.stripe_checkout_session_id or "").strip():
        recovered_from_replacement_conflict = False
        with transaction.atomic():
            current_reservation = Subscription.objects.select_for_update().get(
                pk=reservation.pk
            )
            if _subscription_reservation_can_be_reused(current_reservation, plan=plan):
                _expire_subscription_reservation(current_reservation)
                reservation, recovered_from_replacement_conflict = (
                    _create_subscription_reservation(
                        user=user,
                        plan=plan,
                        stripe_customer_id=customer_id or None,
                    )
                )
        customer_id = str(reservation.stripe_customer_id or "").strip()
        live_checkout_url = _reuse_live_subscription_checkout_url(
            reservation=reservation,
            stripe_client=resolved_client,
        )
        if live_checkout_url:
            return live_checkout_url
        if recovered_from_replacement_conflict:
            raise BillingValidationError(_CURRENT_RECURRING_SUBSCRIPTION_ERROR)

    try:
        session_metadata = _build_checkout_session_metadata(user, plan)
        checkout_session = resolved_client.create_subscription_checkout_session(
            customer_id=customer_id,
            price_id=plan.stripe_price_id,
            success_url=normalized_success_url,
            cancel_url=normalized_cancel_url,
            session_metadata=session_metadata,
            subscription_metadata=session_metadata,
            client_reference_id=_user_reference(user),
        )
        checkout_session_id = str(checkout_session.get("id") or "").strip()
        checkout_url = str(checkout_session.get("url") or "").strip()
        if not checkout_session_id:
            raise BillingError(
                "Stripe subscription checkout session creation did not return an id."
            )
        if not checkout_url:
            raise BillingError(
                "Stripe subscription checkout session creation did not return a hosted URL."
            )
    except Exception:
        with transaction.atomic():
            failed_reservation = (
                Subscription.objects.select_for_update()
                .filter(pk=reservation.pk)
                .first()
            )
            if (
                failed_reservation is not None
                and _subscription_reservation_can_be_reused(
                    failed_reservation,
                    plan=plan,
                )
            ):
                _expire_subscription_reservation(failed_reservation)
        raise

    with transaction.atomic():
        reservation = Subscription.objects.select_for_update().get(pk=reservation.pk)
        if not _subscription_reservation_can_be_reused(reservation, plan=plan):
            raise BillingValidationError(_CURRENT_RECURRING_SUBSCRIPTION_ERROR)
        reservation.stripe_customer_id = customer_id
        reservation.stripe_checkout_session_id = checkout_session_id
        reservation.checkout_expires_at = _extract_checkout_session_expires_at(
            checkout_session
        )
        reservation.save(
            update_fields=[
                "stripe_customer_id",
                "stripe_checkout_session_id",
                "checkout_expires_at",
            ]
        )
    return checkout_url


def create_billing_portal_session(
    user: Any,
    return_url: str,
    *,
    stripe_client: Any | None = None,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> str:
    """Create a hosted Stripe billing portal session for the given user."""
    snapshot = settings_snapshot or BillingSettingsSnapshot.from_settings()
    _ensure_billing_enabled(snapshot)

    normalized_return_url = return_url.strip()
    if not normalized_return_url:
        raise BillingValidationError("Billing portal return URL is required.")

    resolved_client = stripe_client or get_stripe_client(settings_snapshot=snapshot)
    customer_id, _ = get_or_create_stripe_customer(
        user,
        stripe_client=resolved_client,
        settings_snapshot=snapshot,
    )
    portal_session = resolved_client.create_billing_portal_session(
        customer_id=customer_id,
        return_url=normalized_return_url,
    )
    portal_url = str(portal_session.get("url") or "").strip()
    if not portal_url:
        raise BillingError(
            "Stripe billing portal session creation did not return a hosted URL."
        )
    return portal_url


def cancel_current_subscription(
    user: Any,
    *,
    stripe_client: Any | None = None,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> Subscription:
    """Schedule the user's current Stripe-backed subscription to end after the period."""
    snapshot = settings_snapshot or BillingSettingsSnapshot.from_settings()
    _ensure_billing_enabled(snapshot)

    subscription = _resolve_authoritative_subscription_reservation(user=user)
    if subscription is None:
        raise BillingValidationError(
            "User does not have a current recurring subscription."
        )

    stripe_subscription_id = str(subscription.stripe_subscription_id or "").strip()
    if not stripe_subscription_id:
        raise BillingValidationError(
            "Current recurring subscription is missing a Stripe subscription id."
        )

    resolved_client = stripe_client or get_stripe_client(settings_snapshot=snapshot)
    updated_subscription = resolved_client.cancel_subscription(
        stripe_subscription_id=stripe_subscription_id,
    )

    remote_status = str(updated_subscription.get("status") or "").strip().lower()
    if remote_status:
        try:
            local_status = _map_stripe_subscription_status(remote_status)
        except BillingWebhookError as exc:
            raise BillingError(str(exc)) from exc
    else:
        local_status = subscription.status

    current_period_start = _stripe_timestamp_to_datetime(
        updated_subscription.get("current_period_start")
    )
    current_period_end = _stripe_timestamp_to_datetime(
        updated_subscription.get("current_period_end")
    )

    with transaction.atomic():
        subscription = Subscription.objects.select_for_update().get(pk=subscription.pk)
        subscription.status = local_status
        subscription.stripe_subscription_id = (
            str(updated_subscription.get("id") or "").strip()
            or subscription.stripe_subscription_id
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

        updated_balance = _apply_locked_credit_balance_delta(
            balance=balance,
            delta=amount,
        )
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
        return transaction_row


def debit_user(
    user: Any,
    amount: int,
    description: str = "",
) -> CreditTransaction:
    """Debit credits from a user and record the usage transaction."""
    if amount <= 0:
        raise BillingValidationError("Debit amount must be greater than zero.")

    with transaction.atomic():
        balance = CreditBalance.objects.select_for_update().filter(user=user).first()
        if balance is None or int(balance.balance) < amount:
            raise InsufficientCreditsError("User does not have enough credits.")

        updated_balance = _apply_locked_credit_balance_delta(
            balance=balance,
            delta=-amount,
        )
        return CreditTransaction.objects.create(
            user=user,
            amount=-amount,
            transaction_type=CreditTransaction.TransactionType.USAGE,
            description=description,
            balance_after=updated_balance,
        )


def _apply_locked_credit_balance_delta(*, balance: CreditBalance, delta: int) -> int:
    CreditBalance.objects.filter(pk=balance.pk).update(
        balance=F("balance") + delta,
        updated_at=timezone.now(),
    )
    balance.refresh_from_db(fields=["balance", "updated_at"])
    return int(balance.balance)


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

            if event_type == STRIPE_EVENT_TYPE_CHECKOUT_SESSION_COMPLETED:
                _handle_checkout_session_completed_event(
                    event_payload,
                    stripe_client=resolved_client,
                )
                processing_status = "processed"
            elif event_type == STRIPE_EVENT_TYPE_INVOICE_PAID:
                _handle_invoice_paid_event(
                    event_payload,
                    stripe_client=resolved_client,
                )
                processing_status = "processed"
            elif event_type == STRIPE_EVENT_TYPE_INVOICE_PAYMENT_FAILED:
                _handle_invoice_payment_failed_event(event_payload)
                processing_status = "processed"
            elif event_type in {
                STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_CREATED,
                STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_UPDATED,
                STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_DELETED,
            }:
                _handle_subscription_event(event_payload, event_type=event_type)
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

    resolved_user = _resolve_user_for_invoice(invoice_payload=invoice_payload)
    subscription_id = str(invoice_payload.get("subscription") or "").strip()
    customer_id = str(invoice_payload.get("customer") or "").strip()
    subscription = _resolve_subscription_for_runtime_event(
        stripe_subscription_id=subscription_id,
        customer_id=customer_id,
        user=resolved_user,
        for_update=True,
    )

    if subscription is None:
        subscription = _backfill_missing_subscription_for_paid_invoice(
            invoice_payload=invoice_payload,
            stripe_client=stripe_client,
            fallback_user=resolved_user,
            expected_plan=plan,
        )
    elif subscription.status in {
        Subscription.Status.INCOMPLETE,
        Subscription.Status.PAST_DUE,
    } or (
        subscription_id and not str(subscription.stripe_subscription_id or "").strip()
    ):
        subscription = _activate_subscription_for_paid_invoice(
            subscription=subscription,
            plan=plan,
            customer_id=customer_id,
            stripe_subscription_id=subscription_id,
        )

    user = resolved_user
    if user is None and subscription is not None:
        user = subscription.user
    if user is None:
        raise BillingWebhookError(
            "Could not resolve a local user for the Stripe invoice."
        )

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


def _handle_invoice_payment_failed_event(
    event_payload: Mapping[str, Any],
) -> Subscription:
    invoice_payload = _extract_event_object(event_payload)
    invoice_id = str(invoice_payload.get("id") or "").strip()
    if not invoice_id:
        raise BillingWebhookError("Stripe invoice payload is missing an id.")

    resolved_user = _resolve_user_for_invoice(invoice_payload=invoice_payload)
    subscription = _resolve_subscription_for_runtime_event(
        stripe_subscription_id=str(invoice_payload.get("subscription") or "").strip(),
        customer_id=str(invoice_payload.get("customer") or "").strip(),
        user=resolved_user,
        for_update=True,
    )

    if subscription is None:
        if resolved_user is None:
            raise BillingWebhookError(
                "Could not resolve a local user for the Stripe invoice."
            )
        price_id = _extract_price_id(invoice_payload)
        plan = Plan.objects.filter(stripe_price_id=price_id).order_by("pk").first()
        if plan is None:
            raise BillingWebhookError(
                f"No billing plan matches Stripe price {price_id}."
            )
        subscription = Subscription(user=resolved_user, plan=plan)

    subscription.status = Subscription.Status.PAST_DUE
    subscription.stripe_customer_id = (
        str(invoice_payload.get("customer") or "").strip()
        or subscription.stripe_customer_id
    )
    subscription.stripe_subscription_id = (
        str(invoice_payload.get("subscription") or "").strip()
        or subscription.stripe_subscription_id
    )
    if subscription.pk is None:
        subscription.save()
    else:
        subscription.save(
            update_fields=[
                "status",
                "stripe_customer_id",
                "stripe_subscription_id",
            ]
        )
    return subscription


def _activate_subscription_for_paid_invoice(
    *,
    subscription: Subscription,
    plan: Plan,
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

    if update_fields:
        subscription.save(update_fields=update_fields)
    return subscription


def _backfill_missing_subscription_for_paid_invoice(
    *,
    invoice_payload: Mapping[str, Any],
    stripe_client: Any | None,
    fallback_user: Any | None,
    expected_plan: Plan,
) -> Subscription:
    stripe_subscription_id = str(invoice_payload.get("subscription") or "").strip()
    if not stripe_subscription_id:
        raise BillingWebhookError(
            "Stripe invoice payload is missing a subscription id for local reconciliation."
        )
    if stripe_client is None or not hasattr(stripe_client, "retrieve_subscription"):
        raise BillingWebhookError(
            "Stripe subscription retrieval is unavailable for invoice reconciliation."
        )

    subscription_payload = _normalize_mapping(
        stripe_client.retrieve_subscription(
            stripe_subscription_id=stripe_subscription_id,
        )
    )
    return _upsert_subscription_from_payload(
        subscription_payload,
        fallback_user=fallback_user,
        expected_plan=expected_plan,
    )


def _upsert_subscription_from_payload(
    subscription_payload: Mapping[str, Any],
    *,
    fallback_user: Any | None = None,
    expected_plan: Plan | None = None,
    fallback_status: str = "",
) -> Subscription:
    stripe_subscription_id = str(subscription_payload.get("id") or "").strip()
    if not stripe_subscription_id:
        raise BillingWebhookError("Stripe subscription payload is missing an id.")

    stripe_status = str(subscription_payload.get("status") or "").strip().lower()
    if not stripe_status:
        stripe_status = fallback_status.strip().lower()
    local_status = _map_stripe_subscription_status(stripe_status)

    plan = _resolve_plan_for_subscription_payload(subscription_payload)
    if expected_plan is not None and plan.pk != expected_plan.pk:
        raise BillingWebhookError(
            "Stripe subscription does not match the invoiced billing plan."
        )

    user = _resolve_user_for_subscription(subscription_payload=subscription_payload)
    if user is None:
        user = fallback_user
    if user is None:
        raise BillingWebhookError(
            "Could not resolve a local user for the Stripe subscription."
        )

    subscription = _resolve_subscription_for_runtime_event(
        stripe_subscription_id=stripe_subscription_id,
        customer_id=str(subscription_payload.get("customer") or "").strip(),
        user=user,
        for_update=True,
    )
    if subscription is None:
        subscription = Subscription(user=user, plan=plan)

    subscription.plan = plan
    subscription.status = local_status
    subscription.stripe_subscription_id = stripe_subscription_id
    subscription.stripe_customer_id = (
        str(subscription_payload.get("customer") or "").strip()
        or subscription.stripe_customer_id
    )
    subscription.current_period_start = _stripe_timestamp_to_datetime(
        subscription_payload.get("current_period_start")
    )
    subscription.current_period_end = _stripe_timestamp_to_datetime(
        subscription_payload.get("current_period_end")
    )
    if subscription.pk is None:
        subscription.save()
    else:
        subscription.save(
            update_fields=[
                "plan",
                "status",
                "stripe_subscription_id",
                "stripe_customer_id",
                "current_period_start",
                "current_period_end",
            ]
        )
    return subscription


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


def _handle_checkout_session_completed_event(
    event_payload: Mapping[str, Any],
    *,
    stripe_client: Any | None = None,
) -> CreditTransaction | None:
    checkout_session_payload = _extract_event_object(event_payload)
    checkout_session_id = str(checkout_session_payload.get("id") or "").strip()
    if not checkout_session_id:
        raise BillingWebhookError("Stripe checkout session payload is missing an id.")

    checkout_mode = str(checkout_session_payload.get("mode") or "").strip()
    if checkout_mode == "subscription":
        return None
    if checkout_mode and checkout_mode != "payment":
        raise BillingWebhookError(
            "Stripe checkout session is not a one-time payment session."
        )

    payment_status = str(checkout_session_payload.get("payment_status") or "").strip()
    if payment_status and payment_status != "paid":
        raise BillingWebhookError("Stripe checkout session payment is not settled.")

    payment_intent_payload = _retrieve_checkout_payment_intent_payload(
        checkout_session_payload=checkout_session_payload,
        stripe_client=stripe_client,
    )
    plan = _resolve_plan_for_checkout_session(
        checkout_session_payload=checkout_session_payload,
        payment_intent_payload=payment_intent_payload,
    )
    credited_amount = _resolve_checkout_session_credit_amount(
        checkout_session_payload=checkout_session_payload,
        payment_intent_payload=payment_intent_payload,
    )
    user = _resolve_user_for_checkout_session(
        checkout_session_payload=checkout_session_payload,
        payment_intent_payload=payment_intent_payload,
    )
    if user is None:
        raise BillingWebhookError(
            "Could not resolve a local user for the Stripe checkout session."
        )

    payment_intent_id = str(
        checkout_session_payload.get("payment_intent") or ""
    ).strip()
    customer_id = str(checkout_session_payload.get("customer") or "").strip()
    reference_data: dict[str, Any] = {
        "checkout_session_id": checkout_session_id,
        "stripe_customer_id": customer_id,
        "stripe_price_id": plan.stripe_price_id,
    }
    if payment_intent_id:
        reference_data["payment_intent_id"] = payment_intent_id

    return credit_user(
        user,
        amount=credited_amount,
        transaction_type=CreditTransaction.TransactionType.PURCHASE,
        description=f"{plan.name} credits from Stripe checkout session {checkout_session_id}",
        stripe_event_id=str(event_payload.get("id") or "").strip(),
        stripe_object_id=checkout_session_id,
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
    user: Any | None,
    for_update: bool = False,
) -> Subscription | None:
    normalized_subscription_id = stripe_subscription_id.strip()
    if normalized_subscription_id:
        queryset = Subscription.objects.select_related("user", "plan").filter(
            stripe_subscription_id=normalized_subscription_id
        )
        if for_update:
            queryset = queryset.select_for_update()
        subscription = queryset.order_by("-pk").first()
        if subscription is not None:
            return subscription

    if customer_id.strip():
        subscription = _resolve_authoritative_subscription_reservation(
            customer_id=customer_id,
            for_update=for_update,
        )
        if subscription is not None:
            return subscription

    if user is not None:
        return _resolve_authoritative_subscription_reservation(
            user=user,
            for_update=for_update,
        )

    return None


def _resolve_user_for_invoice(*, invoice_payload: Mapping[str, Any]) -> Any | None:
    customer_id = str(invoice_payload.get("customer") or "").strip()
    if customer_id:
        subscription = _resolve_authoritative_subscription_reservation(
            customer_id=customer_id,
        )
        if subscription is not None:
            return subscription.user

    metadata_sources = [
        invoice_payload,
        _normalize_mapping(invoice_payload.get("subscription_details") or {}),
        _normalize_mapping(invoice_payload.get("parent") or {}),
    ]
    return _resolve_user_from_metadata_sources(metadata_sources)


def _resolve_user_for_subscription(
    *, subscription_payload: Mapping[str, Any]
) -> Any | None:
    customer_id = str(subscription_payload.get("customer") or "").strip()
    if customer_id:
        subscription = _resolve_authoritative_subscription_reservation(
            customer_id=customer_id,
        )
        if subscription is not None:
            return subscription.user

    return _resolve_user_from_metadata_sources([subscription_payload])


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


def _validate_one_time_purchase_plan(plan: Plan) -> None:
    if not plan.is_active:
        raise BillingValidationError("Billing plan is not active.")
    if plan.billing_interval != Plan.BillingInterval.ONE_TIME:
        raise BillingValidationError(
            "Billing plan does not support one-time purchases."
        )
    if not str(plan.stripe_price_id or "").strip():
        raise BillingValidationError("Billing plan is missing a Stripe price id.")


def _validate_recurring_subscription_plan(plan: Plan) -> None:
    if not plan.is_active:
        raise BillingValidationError("Billing plan is not active.")
    if plan.billing_interval not in _STRIPE_RECURRING_INTERVAL_BY_PLAN_INTERVAL:
        raise BillingValidationError(
            "Billing plan does not support recurring subscriptions."
        )
    if not str(plan.stripe_price_id or "").strip():
        raise BillingValidationError("Billing plan is missing a Stripe price id.")


def _validate_completed_checkout_plan(
    plan: Plan,
    *,
    expected_price_id: str,
    expected_interval: str,
) -> None:
    if not str(plan.stripe_price_id or "").strip():
        raise BillingWebhookError("Billing plan is missing a Stripe price id.")
    if plan.stripe_price_id != expected_price_id:
        raise BillingWebhookError(
            "Billing plan no longer matches the immutable checkout price."
        )
    if expected_interval and expected_interval != Plan.BillingInterval.ONE_TIME:
        raise BillingWebhookError(
            "Stripe checkout session metadata does not describe a one-time purchase."
        )


def _build_checkout_session_metadata(user: Any, plan: Plan) -> dict[str, str]:
    metadata = _build_customer_metadata(user)
    metadata.update(
        {
            _PLAN_SLUG_METADATA_KEY: plan.slug,
            _PLAN_CREDITS_METADATA_KEY: str(plan.credits_per_period),
            _PLAN_INTERVAL_METADATA_KEY: plan.billing_interval,
            _PRICE_ID_METADATA_KEY: plan.stripe_price_id,
        }
    )
    return metadata


def _validate_stripe_price_parity(
    *,
    plan: Plan,
    stripe_price: Mapping[str, Any],
) -> None:
    unit_amount = _normalize_integer(stripe_price.get("unit_amount"))
    if unit_amount is None or unit_amount != plan.price_cents:
        raise BillingValidationError(
            "Billing plan price does not match the referenced Stripe price amount."
        )

    currency = str(stripe_price.get("currency") or "").strip().lower()
    if currency != plan.currency.casefold():
        raise BillingValidationError(
            "Billing plan currency does not match the referenced Stripe price."
        )

    price_type = str(stripe_price.get("type") or "").strip().lower()
    if (
        plan.billing_interval == Plan.BillingInterval.ONE_TIME
        and price_type != "one_time"
    ):
        raise BillingValidationError(
            "Billing plan must reference a one-time Stripe price for purchases."
        )
    if (
        plan.billing_interval != Plan.BillingInterval.ONE_TIME
        and price_type != "recurring"
    ):
        raise BillingValidationError(
            "Billing plan must reference a recurring Stripe price for subscriptions."
        )
    if plan.billing_interval == Plan.BillingInterval.ONE_TIME:
        return

    expected_interval = _STRIPE_RECURRING_INTERVAL_BY_PLAN_INTERVAL.get(
        plan.billing_interval,
        "",
    )
    recurring_data = _normalize_mapping(stripe_price.get("recurring") or {})
    actual_interval = str(recurring_data.get("interval") or "").strip().lower()
    if actual_interval != expected_interval:
        raise BillingValidationError(
            "Billing plan billing interval does not match the referenced Stripe price."
        )


def _resolve_authoritative_subscription_reservation(
    *,
    user: Any | None = None,
    customer_id: str = "",
    for_update: bool = False,
) -> Subscription | None:
    normalized_customer_id = customer_id.strip()
    if user is None and not normalized_customer_id:
        return None

    queryset = Subscription.objects.select_related("user", "plan").order_by("-pk")
    if for_update:
        queryset = queryset.select_for_update()
    if user is not None:
        queryset = queryset.filter(user=user)
    if normalized_customer_id:
        queryset = queryset.filter(stripe_customer_id=normalized_customer_id)
    return queryset.filter(Subscription.current_status_q()).first()


def _subscription_reservation_can_be_reused(
    reservation: Subscription,
    *,
    plan: Plan,
) -> bool:
    if reservation.plan.pk != plan.pk:
        return False
    if reservation.status != Subscription.Status.INCOMPLETE:
        return False
    return not str(reservation.stripe_subscription_id or "").strip()


def _subscription_reservation_needs_replacement(
    reservation: Subscription,
) -> bool:
    checkout_session_id = str(reservation.stripe_checkout_session_id or "").strip()
    if not checkout_session_id:
        return True
    if reservation.checkout_expires_at is None:
        return False
    return reservation.checkout_expires_at <= timezone.now()


def _expire_subscription_reservation(reservation: Subscription) -> None:
    reservation.status = Subscription.Status.INCOMPLETE_EXPIRED
    reservation.save(update_fields=["status"])


def _create_subscription_reservation(
    *,
    user: Any,
    plan: Plan,
    stripe_customer_id: str | None = None,
) -> tuple[Subscription, bool]:
    try:
        with transaction.atomic():
            return (
                Subscription.objects.create(
                    user=user,
                    plan=plan,
                    stripe_customer_id=stripe_customer_id,
                    status=Subscription.Status.INCOMPLETE,
                ),
                False,
            )
    except IntegrityError as exc:
        recovered_reservation = _recover_conflicting_subscription_reservation(
            user=user,
            plan=plan,
        )
        if recovered_reservation is not None:
            return recovered_reservation, True
        raise BillingValidationError(_CURRENT_RECURRING_SUBSCRIPTION_ERROR) from exc


def _recover_conflicting_subscription_reservation(
    *,
    user: Any,
    plan: Plan,
) -> Subscription | None:
    with transaction.atomic():
        current_reservation = _resolve_authoritative_subscription_reservation(
            user=user,
            for_update=True,
        )
        if current_reservation is None:
            return None
        if not _subscription_reservation_can_be_reused(current_reservation, plan=plan):
            return None
        if _subscription_reservation_needs_replacement(current_reservation):
            return None
        return current_reservation


def _prepare_subscription_checkout_reservation(
    *,
    user: Any,
    plan: Plan,
) -> tuple[Subscription, bool]:
    current_reservation = _resolve_authoritative_subscription_reservation(
        user=user,
        for_update=True,
    )
    if current_reservation is None:
        return _create_subscription_reservation(user=user, plan=plan)

    if not _subscription_reservation_can_be_reused(current_reservation, plan=plan):
        raise BillingValidationError(_CURRENT_RECURRING_SUBSCRIPTION_ERROR)

    if _subscription_reservation_needs_replacement(current_reservation):
        persisted_customer_id = str(
            current_reservation.stripe_customer_id or ""
        ).strip()
        _expire_subscription_reservation(current_reservation)
        return _create_subscription_reservation(
            user=user,
            plan=plan,
            stripe_customer_id=persisted_customer_id or None,
        )

    return current_reservation, False


def _reuse_live_subscription_checkout_url(
    *,
    reservation: Subscription,
    stripe_client: Any,
) -> str:
    checkout_session_id = str(reservation.stripe_checkout_session_id or "").strip()
    if not checkout_session_id:
        return ""
    if (
        reservation.checkout_expires_at is not None
        and reservation.checkout_expires_at <= timezone.now()
    ):
        return ""
    if not hasattr(stripe_client, "retrieve_checkout_session"):
        return ""

    checkout_session = _normalize_mapping(
        stripe_client.retrieve_checkout_session(
            checkout_session_id=checkout_session_id,
        )
    )
    return _extract_live_checkout_session_url(checkout_session)


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
    except (TypeError, ValueError):
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
    "cancel_current_subscription",
    "BillingConfigurationError",
    "BillingDisabledError",
    "BillingError",
    "BillingSettingsSnapshot",
    "BillingValidationError",
    "BillingWebhookError",
    "BillingWebhookSignatureError",
    "debit_user",
    "StripeClient",
    "StripeWebhookResult",
    "create_billing_portal_session",
    "create_checkout_session",
    "create_subscription_checkout_session",
    "credit_user",
    "get_or_create_stripe_customer",
    "get_stripe_client",
    "handle_stripe_event",
    "InsufficientCreditsError",
]
