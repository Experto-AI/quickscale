"""Runtime billing services for the QuickScale billing module."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from functools import wraps
import hashlib
from importlib import import_module
import json
import logging
from typing import Any, Final, ParamSpec, TypeVar, cast

from django.apps import apps
from django.conf import settings
from django.db import IntegrityError, connection, transaction
from django.db.models import F, Q
from django.http import HttpRequest, HttpResponse
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from quickscale_modules_orgs.current_org import org_scope
from quickscale_modules_billing.exceptions import (
    BillingConfigurationError,
    BillingDisabledError,
    BillingError,
    BillingSubscriptionAnomalyError,
    BillingValidationError,
    BillingWebhookError,
    BillingWebhookSignatureError,
    InsufficientCreditsError,
    OrgSelectionRequiredError,
)
from quickscale_modules_billing.models import (
    CREDIT_TRANSACTION_BUSINESS_REFERENCE_KEYS,
    CreditBalance,
    CreditTransaction,
    Plan,
    PurchaseCheckout,
    Subscription,
    WebhookEvent,
)

logger = logging.getLogger(__name__)

# The Stripe API version this module is written against: the version
# stripe-python 15.x ships pinned. It is set on the SDK before every call and
# every webhook event must report the same named release.
STRIPE_API_VERSION: Final[str] = "2026-06-24.dahlia"
STRIPE_EVENT_TYPE_CHECKOUT_SESSION_COMPLETED = "checkout.session.completed"
STRIPE_EVENT_TYPE_CHECKOUT_SESSION_EXPIRED = "checkout.session.expired"
STRIPE_EVENT_TYPE_INVOICE_PAID = "invoice.paid"
STRIPE_EVENT_TYPE_INVOICE_PAYMENT_FAILED = "invoice.payment_failed"
STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_CREATED = "customer.subscription.created"
STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_UPDATED = "customer.subscription.updated"
STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_DELETED = "customer.subscription.deleted"
_INVOICE_REFERENCE_KEYS = ("invoice_id",)
_BUSINESS_OBJECT_REFERENCE_KEYS = CREDIT_TRANSACTION_BUSINESS_REFERENCE_KEYS
_ORG_REFERENCE_METADATA_KEY = "quickscale_org_reference"
_USER_METADATA_KEY = "quickscale_user_reference"
_PLAN_SLUG_METADATA_KEY = "quickscale_plan_slug"
_PLAN_CREDITS_METADATA_KEY = "quickscale_plan_credits"
_PLAN_INTERVAL_METADATA_KEY = "quickscale_plan_interval"
_PRICE_ID_METADATA_KEY = "stripe_price_id"
_PURCHASE_CHECKOUT_REFERENCE_METADATA_KEY = "quickscale_purchase_checkout_reference"
_SUBSCRIPTION_CHECKOUT_REFERENCE_METADATA_KEY = (
    "quickscale_subscription_checkout_reference"
)
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
_CUSTOMER_SEARCH_REFERENCE_UNSAFE_CHARACTERS: tuple[tuple[str, str], ...] = (
    ("'", "apostrophe"),
    ("\\", "backslash"),
    ("\n", "newline"),
)


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
        """Create a billing runtime snapshot from Django settings.

        Rule 3: every value is read directly; apply wrote the canonical
        values and the module's startup check has validated them, so the
        snapshot neither defaults nor coerces.
        """
        return cls(
            enabled=bool(settings.QUICKSCALE_BILLING_ENABLED),
            publishable_key_env_var=str(
                settings.QUICKSCALE_BILLING_PUBLISHABLE_KEY_ENV_VAR
            ),
            secret_key_env_var=str(settings.QUICKSCALE_BILLING_SECRET_KEY_ENV_VAR),
            webhook_secret_env_var=str(
                settings.QUICKSCALE_BILLING_WEBHOOK_SECRET_ENV_VAR
            ),
            billing_currency=str(settings.QUICKSCALE_BILLING_CURRENCY),
        )

    def resolve_publishable_key(self) -> str:
        """Resolve the Stripe publishable key from the applied secret setting (rule 35).

        Rule 3: the applied setting is the only source.  An empty setting
        resolves to no key and is refused here, because the key is served to
        the checkout client rather than gatekeeping startup.
        """
        publishable_key = str(settings.QUICKSCALE_BILLING_PUBLISHABLE_KEY).strip()
        if not publishable_key:
            raise BillingConfigurationError(
                "Stripe publishable key is not configured in the runtime settings."
            )
        return publishable_key

    def resolve_secret_key(self) -> str:
        """Resolve the Stripe secret key from the applied secret setting (rule 35).

        Rule 3: the applied setting is the only source.  An empty setting
        resolves to no key, and the startup check refuses the enabled module
        rather than this method substituting a runtime fallback.
        """
        return str(settings.QUICKSCALE_BILLING_SECRET_KEY).strip()

    def resolve_webhook_secret(self) -> str:
        """Resolve the Stripe webhook signing secret from the applied setting (rule 35).

        Rule 3: the applied setting is the only source.  An empty setting
        resolves to no secret, and the startup check refuses the enabled
        module rather than this method substituting a runtime fallback.
        """
        return str(settings.QUICKSCALE_BILLING_WEBHOOK_SECRET).strip()


@dataclass(frozen=True)
class StripeWebhookResult:
    """Result returned after Stripe webhook handling."""

    duplicate: bool
    event_type: str
    status: str


@dataclass(frozen=True)
class SubscriptionProviderIdentity:
    """Immutable local/provider identity captured before a Stripe mutation."""

    subscription_pk: Any
    organization_id: Any
    stripe_subscription_id: str


@dataclass(frozen=True)
class SubscriptionCheckoutReconciliation:
    """Provider state observed for one local checkout reservation."""

    provider_status: str = ""
    checkout_session_id: str = ""
    stripe_customer_id: str = ""


@dataclass(frozen=True)
class SubscriptionCancellationTransition:
    """Remote state captured before an account-deletion cancellation."""

    subscription_pk: Any
    organization_id: Any
    stripe_subscription_id: str
    previous_cancel_at_period_end: bool

    @property
    def changed(self) -> bool:
        """Return whether this transition changed the provider cancellation flag."""
        return not self.previous_cancel_at_period_end

    @property
    def identity(self) -> SubscriptionProviderIdentity:
        """Return the immutable row/provider identity for persistence checks."""
        return SubscriptionProviderIdentity(
            subscription_pk=self.subscription_pk,
            organization_id=self.organization_id,
            stripe_subscription_id=self.stripe_subscription_id,
        )


class StripeClient:
    """Thin Stripe SDK wrapper used by the billing runtime and tests."""

    def __init__(self, *, stripe_module: Any, api_key: str) -> None:
        self._stripe_module = stripe_module
        self._api_key = api_key

    def search_customers(
        self,
        *,
        user_reference: str = "",
        organization_reference: str = "",
    ) -> list[dict[str, Any]]:
        """Search Stripe customers by the authoritative local metadata reference."""
        _validate_customer_search_reference(
            field_name="user_reference",
            reference=user_reference,
        )
        _validate_customer_search_reference(
            field_name="organization_reference",
            reference=organization_reference,
        )
        self._activate_api_key()
        if organization_reference:
            query = (
                f"metadata['{_ORG_REFERENCE_METADATA_KEY}']:'{organization_reference}'"
            )
        else:
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
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Create a Stripe Checkout Session for a one-time purchase."""
        self._activate_api_key()
        checkout_session_api = self._resolve_checkout_session_api()
        create_kwargs: dict[str, Any] = {
            "mode": "payment",
            "customer": customer_id,
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "client_reference_id": client_reference_id,
            "metadata": dict(session_metadata),
            "payment_intent_data": {"metadata": dict(payment_intent_metadata)},
        }
        if idempotency_key:
            create_kwargs["idempotency_key"] = idempotency_key
        created_session = checkout_session_api.create(
            **create_kwargs,
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
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Create a Stripe Checkout Session for a recurring subscription."""
        self._activate_api_key()
        checkout_session_api = self._resolve_checkout_session_api()
        create_kwargs: dict[str, Any] = {
            "mode": "subscription",
            "customer": customer_id,
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "client_reference_id": client_reference_id,
            "metadata": dict(session_metadata),
            "subscription_data": {"metadata": dict(subscription_metadata)},
        }
        if idempotency_key:
            create_kwargs["idempotency_key"] = idempotency_key
        created_session = checkout_session_api.create(**create_kwargs)
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
        return self._set_subscription_cancel_at_period_end(
            stripe_subscription_id=stripe_subscription_id,
            cancel_at_period_end=True,
        )

    def resume_subscription(
        self,
        *,
        stripe_subscription_id: str,
    ) -> dict[str, Any]:
        """Undo a scheduled period-end cancellation."""
        return self._set_subscription_cancel_at_period_end(
            stripe_subscription_id=stripe_subscription_id,
            cancel_at_period_end=False,
        )

    def _set_subscription_cancel_at_period_end(
        self,
        *,
        stripe_subscription_id: str,
        cancel_at_period_end: bool,
    ) -> dict[str, Any]:
        """Set Stripe's period-end cancellation flag."""
        self._activate_api_key()
        subscription_api = getattr(self._stripe_module, "Subscription", None)
        if subscription_api is None:
            raise BillingConfigurationError(
                "Stripe Subscription SDK support is unavailable in this environment."
            )
        if hasattr(subscription_api, "modify"):
            updated_subscription = subscription_api.modify(
                stripe_subscription_id,
                cancel_at_period_end=cancel_at_period_end,
            )
            return _normalize_mapping(updated_subscription)
        if hasattr(subscription_api, "update"):
            updated_subscription = subscription_api.update(
                stripe_subscription_id,
                cancel_at_period_end=cancel_at_period_end,
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
        if hasattr(self._stripe_module, "api_version"):
            setattr(self._stripe_module, "api_version", STRIPE_API_VERSION)

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
            "Stripe secret key is not configured in the runtime settings."
        )
    try:
        stripe_module = import_module("stripe")
    except ImportError as exc:
        raise BillingConfigurationError(
            "Stripe SDK is not installed in this environment."
        ) from exc
    return StripeClient(stripe_module=stripe_module, api_key=secret_key)


def _stripe_error_classes() -> tuple[type[BaseException], ...]:
    """The Stripe SDK's error base, or ``()`` when the SDK is not importable.

    The SDK is an optional runtime dependency, so the class is resolved at
    the service boundary; an empty tuple simply matches nothing.
    """
    try:
        stripe_module = import_module("stripe")
    except ImportError:
        return ()
    error_class = getattr(stripe_module, "StripeError", None)
    if not isinstance(error_class, type) or not issubclass(error_class, BaseException):
        return ()
    return (error_class,)


P = ParamSpec("P")
R = TypeVar("R")


def _translate_stripe_errors(
    message: str,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Translate Stripe SDK failures into the module's error surface (rule 23)."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return func(*args, **kwargs)
            except _stripe_error_classes() as exc:
                raise BillingError(message) from exc

        return wrapper

    return decorator


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

    resolved_client = stripe_client or get_stripe_client(settings_snapshot=snapshot)
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


def create_checkout_session(
    user: Any,
    *,
    plan: Plan,
    success_url: str,
    cancel_url: str,
    organization: Any,
    stripe_client: Any | None = None,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> str:
    """Serialize one-time Checkout creation with destructive org boundaries."""
    try:
        with subscription_provider_mutation_lock(organization):
            user, organization = _require_owner_provider_mutation_authorization(
                user,
                organization,
            )
            return _create_checkout_session(
                user,
                plan,
                success_url,
                cancel_url,
                organization=organization,
                stripe_client=stripe_client,
                settings_snapshot=settings_snapshot,
            )
    except _stripe_error_classes() as exc:
        raise BillingError("Stripe checkout session creation failed.") from exc


def _create_checkout_session(
    user: Any,
    plan: Plan,
    success_url: str,
    cancel_url: str,
    *,
    organization: Any,
    stripe_client: Any | None = None,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> str:
    """Create one Stripe purchase session while its organization mutex is held."""
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
        organization=organization,
        stripe_client=resolved_client,
        settings_snapshot=snapshot,
    )
    # Persist the intent immediately before the non-transactional provider
    # create. An exception can mean Stripe created the session but the response
    # was lost, so the PREPARING row must remain as a fail-closed obligation.
    with org_scope(organization):
        _lock_organization_for_billing_mutation(organization)
        preparing_reservations = list(
            PurchaseCheckout.all_objects.select_for_update()
            .filter(
                user=user,
                organization=organization,
                plan=plan,
                status=PurchaseCheckout.Status.PREPARING,
            )
            .order_by("pk")[:2]
        )
        if len(preparing_reservations) > 1:
            raise BillingError(
                "Multiple purchase checkouts have unknown creation outcomes; "
                "manual provider reconciliation is required."
            )
        reservation = (
            preparing_reservations[0]
            if preparing_reservations
            else PurchaseCheckout.all_objects.create(
                user=user,
                organization=organization,
                plan=plan,
            )
        )

    reservation_reference = _purchase_checkout_reference(reservation)
    session_metadata = _build_checkout_session_metadata(
        user,
        plan,
        organization=organization,
    )
    session_metadata[_PURCHASE_CHECKOUT_REFERENCE_METADATA_KEY] = reservation_reference

    checkout_session = resolved_client.create_checkout_session(
        customer_id=customer_id,
        price_id=plan.stripe_price_id,
        success_url=normalized_success_url,
        cancel_url=normalized_cancel_url,
        session_metadata=session_metadata,
        payment_intent_metadata=session_metadata,
        client_reference_id=_user_reference(user),
        idempotency_key=_build_purchase_checkout_create_idempotency_key(
            reservation_reference
        ),
    )
    checkout_session_id = str(checkout_session.get("id") or "").strip()
    checkout_url = str(checkout_session.get("url") or "").strip()
    if not checkout_session_id:
        raise BillingError("Stripe checkout session creation did not return an id.")

    with org_scope(organization):
        _lock_organization_for_billing_mutation(organization)
        reservation = PurchaseCheckout.all_objects.select_for_update().get(
            pk=reservation.pk
        )
        reservation.stripe_checkout_session_id = checkout_session_id
        reservation.status = PurchaseCheckout.Status.OPEN
        reservation.checkout_expires_at = _extract_checkout_session_expires_at(
            checkout_session
        )
        reservation.save(
            update_fields=[
                "stripe_checkout_session_id",
                "status",
                "checkout_expires_at",
            ]
        )
    if not checkout_url:
        raise BillingError(
            "Stripe checkout session creation did not return a hosted URL."
        )
    return checkout_url


def create_subscription_checkout_session(
    user: Any,
    *,
    plan: Plan,
    success_url: str,
    cancel_url: str,
    organization: Any,
    stripe_client: Any | None = None,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> str:
    """Serialize recurring Checkout creation with account deletion mutations."""
    try:
        with subscription_provider_mutation_lock(organization):
            user, organization = _require_owner_provider_mutation_authorization(
                user,
                organization,
            )
            return _create_subscription_checkout_session(
                user,
                plan,
                success_url,
                cancel_url,
                organization=organization,
                stripe_client=stripe_client,
                settings_snapshot=settings_snapshot,
            )
    except _stripe_error_classes() as exc:
        raise BillingError(
            "Stripe subscription checkout session creation failed."
        ) from exc


def _create_subscription_checkout_session(
    user: Any,
    plan: Plan,
    success_url: str,
    cancel_url: str,
    *,
    organization: Any,
    stripe_client: Any | None = None,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> str:
    """Create or reuse one recurring Checkout Session while its mutex is held."""
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
    reconciled_customer_id = reconcile_elapsed_subscription_checkout(
        organization.pk,
        stripe_client=resolved_client,
        settings_snapshot=snapshot,
    )

    with transaction.atomic():
        _lock_organization_for_billing_mutation(organization)
        reservation, _ = _prepare_subscription_checkout_reservation(
            user=user,
            organization=organization,
            plan=plan,
            stripe_customer_id=reconciled_customer_id or None,
        )
        if reservation.user_id != getattr(user, "pk", None):
            raise BillingValidationError(_CURRENT_RECURRING_SUBSCRIPTION_ERROR)

    customer_id = str(reservation.stripe_customer_id or "").strip()
    if not customer_id:
        customer_id, _ = get_or_create_stripe_customer(
            user,
            organization=organization,
            stripe_client=resolved_client,
            settings_snapshot=snapshot,
        )
        with transaction.atomic():
            _lock_organization_for_billing_mutation(organization)
            reservation = Subscription.all_objects.select_for_update().get(
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

    if str(reservation.stripe_checkout_session_id or "").strip():
        with transaction.atomic():
            _lock_organization_for_billing_mutation(organization)
            current_reservation = Subscription.all_objects.select_for_update().get(
                pk=reservation.pk
            )
            if _subscription_reservation_can_be_reused(current_reservation, plan=plan):
                _expire_subscription_reservation(current_reservation)
                reservation, _ = _create_subscription_reservation(
                    user=user,
                    organization=organization,
                    plan=plan,
                    stripe_customer_id=customer_id or None,
                )
        customer_id = str(reservation.stripe_customer_id or "").strip()
        live_checkout_url = _reuse_live_subscription_checkout_url(
            reservation=reservation,
            stripe_client=resolved_client,
        )
        if live_checkout_url:
            return live_checkout_url

    session_metadata = _build_checkout_session_metadata(
        user,
        plan,
        organization=organization,
    )
    reservation_reference = _subscription_checkout_reference(reservation)
    session_metadata[_SUBSCRIPTION_CHECKOUT_REFERENCE_METADATA_KEY] = (
        reservation_reference
    )
    # A blank-session reservation can survive customer or Checkout provider
    # failure. Reusing its reference and idempotency key makes a retry safe even
    # when the first provider response was lost.
    checkout_session = resolved_client.create_subscription_checkout_session(
        customer_id=customer_id,
        price_id=plan.stripe_price_id,
        success_url=normalized_success_url,
        cancel_url=normalized_cancel_url,
        session_metadata=session_metadata,
        subscription_metadata=session_metadata,
        client_reference_id=_user_reference(user),
        idempotency_key=_build_subscription_checkout_create_idempotency_key(
            reservation_reference
        ),
    )
    checkout_session_id = str(checkout_session.get("id") or "").strip()
    checkout_url = str(checkout_session.get("url") or "").strip()
    if not checkout_session_id:
        raise BillingError(
            "Stripe subscription checkout session creation did not return an id."
        )

    with transaction.atomic():
        _lock_organization_for_billing_mutation(organization)
        reservation = Subscription.all_objects.select_for_update().get(
            pk=reservation.pk
        )
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
    if not checkout_url:
        raise BillingError(
            "Stripe subscription checkout session creation did not return a hosted URL."
        )
    return checkout_url


@_translate_stripe_errors("Stripe subscription checkout reconciliation failed.")
def reconcile_elapsed_subscription_checkout(
    organization_id: Any,
    *,
    stripe_client: Any | None = None,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> str:
    """Normalize an elapsed checkout only after Stripe confirms it is terminal."""
    result = _reconcile_subscription_checkout(
        organization_id,
        elapsed_only=True,
        persist=True,
        stripe_client=stripe_client,
        settings_snapshot=settings_snapshot,
    )
    return result.stripe_customer_id


@_translate_stripe_errors("Stripe subscription checkout reconciliation failed.")
def reconcile_organization_removal_subscription_checkout(
    organization_id: Any,
    *,
    persist: bool,
    stripe_client: Any | None = None,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> SubscriptionCheckoutReconciliation:
    """Inspect an elapsed checkout and optionally persist terminal provider state."""
    return _reconcile_subscription_checkout(
        organization_id,
        elapsed_only=True,
        persist=persist,
        stripe_client=stripe_client,
        settings_snapshot=settings_snapshot,
    )


@_translate_stripe_errors("Stripe subscription checkout reconciliation failed.")
def reconcile_account_deletion_subscription_checkout(
    organization_id: Any,
    *,
    stripe_client: Any | None = None,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> SubscriptionCheckoutReconciliation:
    """Require a hosted checkout to be provider-terminal before account deletion."""
    return _reconcile_subscription_checkout(
        organization_id,
        elapsed_only=False,
        persist=True,
        stripe_client=stripe_client,
        settings_snapshot=settings_snapshot,
    )


@_translate_stripe_errors("Stripe purchase checkout reconciliation failed.")
def reconcile_purchase_checkouts_for_removal(
    organization_id: Any,
    *,
    user_id: Any | None = None,
    persist: bool,
    stripe_client: Any | None = None,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> tuple[str, ...]:
    """Require one-time Checkout sessions to be provider-terminal before removal."""
    organization_model = apps.get_model(
        "quickscale_orgs",
        "Organization",
    )
    organization = organization_model._default_manager.filter(
        pk=organization_id
    ).first()
    if organization is None:
        return ()

    with org_scope(organization):
        queryset = PurchaseCheckout.all_objects.filter(
            organization=organization,
            status__in=(
                PurchaseCheckout.Status.PREPARING,
                PurchaseCheckout.Status.OPEN,
            ),
        )
        if user_id is not None:
            queryset = queryset.filter(user_id=user_id)
        reservations = list(queryset.order_by("pk"))
    if not reservations:
        return ()

    snapshot = settings_snapshot or BillingSettingsSnapshot.from_settings()
    _ensure_billing_enabled(snapshot)
    resolved_client = stripe_client or get_stripe_client(settings_snapshot=snapshot)
    expired_checkout_ids: list[str] = []
    for reservation in reservations:
        checkout_session_id = str(reservation.stripe_checkout_session_id or "").strip()
        if not checkout_session_id:
            raise BillingError(
                "A Stripe purchase checkout is still being prepared or its creation "
                "outcome is unknown; reconcile provider state before retrying removal."
            )
        checkout_session = _normalize_mapping(
            resolved_client.retrieve_checkout_session(
                checkout_session_id=checkout_session_id,
            )
        )
        provider_status = str(checkout_session.get("status") or "").strip().lower()
        if provider_status == "expired":
            expired_checkout_ids.append(checkout_session_id)
            if persist:
                with org_scope(organization):
                    _lock_organization_for_billing_mutation(organization)
                    PurchaseCheckout.all_objects.filter(
                        pk=reservation.pk,
                        status=PurchaseCheckout.Status.OPEN,
                        stripe_checkout_session_id=checkout_session_id,
                    ).update(status=PurchaseCheckout.Status.EXPIRED)
            continue
        if provider_status == "open":
            raise BillingValidationError(
                f"Stripe purchase checkout session {checkout_session_id} is still open."
            )
        if provider_status == "complete":
            raise BillingValidationError(
                "Stripe purchase checkout completed and may require credit "
                f"synchronization ({checkout_session_id}); retry removal after its "
                "webhook is processed."
            )
        raise BillingError(
            "Stripe purchase checkout reconciliation returned an unsupported or "
            f"blank status for {checkout_session_id}."
        )
    return tuple(expired_checkout_ids)


def guard_organization_removal_provider_state(
    organization: Any,
    *,
    provider_expired_checkout_id: str = "",
) -> str:
    """Return the reason an organization purge must refuse, or an empty string.

    The purge boundary declares this hook on billing's obligation
    ``boundary_guarded_hooks`` and calls it while the organization row lock and
    the RLS context are held.  Billing's provider state is live while a current
    subscription carries no provider id to reconcile, while a current
    subscription has not reached a provider-terminal state, or while an
    incomplete subscription checkout Stripe has not confirmed expired is
    pending.  A checkout id the caller reconciled to a provider-confirmed
    expiry is excluded from the pending check.  An empty string means the purge
    may proceed; a non-empty string is the operator-facing refusal.
    """
    current_statuses = Subscription.current_statuses()
    queryset = Subscription.all_objects.filter(organization=organization)
    stripe_subscription_ids = sorted(
        str(subscription_id)
        for subscription_id in queryset.filter(
            status__in=current_statuses,
            stripe_subscription_id__isnull=False,
        )
        .exclude(stripe_subscription_id="")
        .values_list("stripe_subscription_id", flat=True)
    )
    ambiguous_current_subscription = (
        queryset.filter(status__in=current_statuses)
        .exclude(status=Subscription.Status.INCOMPLETE)
        .filter(Q(stripe_subscription_id__isnull=True) | Q(stripe_subscription_id=""))
        .exists()
    )
    pending_checkout_queryset = queryset.filter(
        status=Subscription.Status.INCOMPLETE,
    ).filter(Q(stripe_subscription_id__isnull=True) | Q(stripe_subscription_id=""))
    if provider_expired_checkout_id:
        pending_checkout_queryset = pending_checkout_queryset.exclude(
            stripe_checkout_session_id=provider_expired_checkout_id
        )

    if ambiguous_current_subscription:
        return (
            f"Cannot purge organization {organization.pk} while it has a current "
            "Stripe subscription with no provider id. Reconcile the subscription "
            "before retrying."
        )
    if stripe_subscription_ids:
        joined_ids = ", ".join(stripe_subscription_ids)
        return (
            f"Cannot purge organization {organization.pk} while it has current "
            f"Stripe subscriptions: {joined_ids}. Cancel these subscriptions in "
            "Stripe before retrying."
        )
    if pending_checkout_queryset.exists():
        return (
            f"Cannot purge organization {organization.pk} while a Stripe "
            "subscription checkout is pending. Complete or expire the checkout "
            "before retrying."
        )
    return ""


def detach_account_deletion_user_references(
    user_id: Any,
    *,
    organization_ids: list[Any],
) -> int:
    """Null billing provenance under each organization's FORCE-RLS context."""
    organization_model = apps.get_model(
        "quickscale_orgs",
        "Organization",
    )
    detached_count = 0
    with transaction.atomic():
        organizations = list(
            organization_model._default_manager.select_for_update()
            .filter(pk__in=organization_ids)
            .order_by("pk")
        )
        if len(organizations) != len(set(organization_ids)):
            raise BillingError(
                "A billing organization disappeared during account deletion."
            )
        for organization in organizations:
            with org_scope(organization):
                detached_count += CreditBalance.all_objects.filter(
                    organization=organization,
                    user_id=user_id,
                ).update(user=None)
                detached_count += CreditTransaction.all_objects.filter(
                    organization=organization,
                    user_id=user_id,
                ).update(user=None)
                detached_count += PurchaseCheckout.all_objects.filter(
                    organization=organization,
                    user_id=user_id,
                ).update(user=None)
                detached_count += Subscription.all_objects.filter(
                    organization=organization,
                    user_id=user_id,
                ).update(user=None)
    return detached_count


def account_deletion_user_reference_organization_ids(user_id: Any) -> list[Any]:
    """Discover every organization retaining billing provenance for one user."""
    from quickscale_modules_orgs.current_org import (
        account_deletion_user_reference_organization_ids as discover_organization_ids,
    )

    organization_ids = discover_organization_ids(
        user_id,
        included_app_labels=frozenset({"quickscale_billing"}),
    )
    return sorted(organization_ids, key=str)


def _reconcile_subscription_checkout(
    organization_id: Any,
    *,
    elapsed_only: bool,
    persist: bool,
    stripe_client: Any | None,
    settings_snapshot: BillingSettingsSnapshot | None,
) -> SubscriptionCheckoutReconciliation:
    """Read one checkout from Stripe and persist it only when requested."""
    organization_model = apps.get_model(
        "quickscale_orgs",
        "Organization",
    )
    organization = organization_model._default_manager.filter(
        pk=organization_id
    ).first()
    if organization is None:
        return SubscriptionCheckoutReconciliation()

    with org_scope(organization):
        reservation_queryset = Subscription.all_objects.filter(
            organization=organization,
            status=Subscription.Status.INCOMPLETE,
        )
        if elapsed_only:
            reservation_queryset = reservation_queryset.filter(
                checkout_expires_at__lte=timezone.now()
            )
        reservation = (
            reservation_queryset.filter(
                Q(stripe_subscription_id__isnull=True) | Q(stripe_subscription_id="")
            )
            .exclude(stripe_checkout_session_id__isnull=True)
            .exclude(stripe_checkout_session_id="")
            .first()
        )
    if reservation is None:
        return SubscriptionCheckoutReconciliation()

    snapshot = settings_snapshot or BillingSettingsSnapshot.from_settings()
    _ensure_billing_enabled(snapshot)
    resolved_client = stripe_client or get_stripe_client(settings_snapshot=snapshot)
    checkout_session_id = str(reservation.stripe_checkout_session_id or "").strip()
    checkout_session = _normalize_mapping(
        resolved_client.retrieve_checkout_session(
            checkout_session_id=checkout_session_id,
        )
    )
    provider_status = str(checkout_session.get("status") or "").strip().lower()
    if provider_status == "expired":
        persisted_customer_id = str(reservation.stripe_customer_id or "").strip()
        if persist:
            with org_scope(organization):
                _lock_organization_for_billing_mutation(organization)
                current_reservation = (
                    Subscription.all_objects.select_for_update()
                    .filter(pk=reservation.pk)
                    .first()
                )
                if (
                    current_reservation is not None
                    and current_reservation.status == Subscription.Status.INCOMPLETE
                    and not str(
                        current_reservation.stripe_subscription_id or ""
                    ).strip()
                    and str(
                        current_reservation.stripe_checkout_session_id or ""
                    ).strip()
                    == checkout_session_id
                ):
                    _expire_subscription_reservation(current_reservation)
        return SubscriptionCheckoutReconciliation(
            provider_status=provider_status,
            checkout_session_id=checkout_session_id,
            stripe_customer_id=persisted_customer_id,
        )

    provider_subscription_id = _stripe_object_id(checkout_session.get("subscription"))
    if provider_status == "complete":
        _validate_completed_checkout_provider_identity(
            reservation=reservation,
            organization=organization,
            checkout_session_payload=checkout_session,
        )
        if persist:
            with org_scope(organization):
                locked_organization = _lock_organization_for_billing_mutation(
                    organization
                )
                current_reservation = (
                    Subscription.all_objects.select_for_update()
                    .filter(pk=reservation.pk)
                    .first()
                )
                if (
                    current_reservation is not None
                    and current_reservation.status == Subscription.Status.INCOMPLETE
                    and not str(
                        current_reservation.stripe_subscription_id or ""
                    ).strip()
                    and str(
                        current_reservation.stripe_checkout_session_id or ""
                    ).strip()
                    == checkout_session_id
                ):
                    _validate_completed_checkout_provider_identity(
                        reservation=current_reservation,
                        organization=locked_organization,
                        checkout_session_payload=checkout_session,
                    )
                    current_reservation.checkout_expires_at = None
                    update_fields = ["checkout_expires_at"]
                    if provider_subscription_id:
                        current_reservation.stripe_subscription_id = (
                            provider_subscription_id
                        )
                        update_fields.append("stripe_subscription_id")
                    current_reservation.save(update_fields=update_fields)
        provider_label = provider_subscription_id or checkout_session_id
        raise BillingValidationError(
            "Stripe checkout completed and may have created a live subscription "
            f"({provider_label}); wait for subscription synchronization or "
            "reconcile it before changing billing or organization state."
        )

    if provider_status == "open":
        raise BillingValidationError(
            f"Stripe checkout session {checkout_session_id} is still open."
        )
    raise BillingError(
        "Stripe checkout session reconciliation returned an unsupported or blank "
        f"status for {checkout_session_id}."
    )


def create_billing_portal_session(
    user: Any,
    *,
    return_url: str,
    organization: Any,
    stripe_client: Any | None = None,
    settings_snapshot: BillingSettingsSnapshot | None = None,
) -> str:
    """Create a hosted Stripe billing portal session for the given organization."""
    snapshot = settings_snapshot or BillingSettingsSnapshot.from_settings()
    _ensure_billing_enabled(snapshot)

    normalized_return_url = return_url.strip()
    if not normalized_return_url:
        raise BillingValidationError("Billing portal return URL is required.")

    resolved_client = stripe_client or get_stripe_client(settings_snapshot=snapshot)
    try:
        with subscription_provider_mutation_lock(organization):
            user, organization = _require_owner_provider_mutation_authorization(
                user,
                organization,
            )
            customer_id, _ = get_or_create_stripe_customer(
                user,
                organization=organization,
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
    except _stripe_error_classes() as exc:
        raise BillingError("Stripe billing portal session creation failed.") from exc
    return portal_url


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
    with subscription_provider_mutation_lock(organization):
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
    with subscription_provider_mutation_lock(organization):
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


def _subscription_provider_mutation_lock_key(organization: Any) -> int:
    organization_pk = getattr(organization, "pk", organization)
    digest = hashlib.sha256(
        f"quickscale_billing:subscription:{organization_pk}".encode()
    ).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


@contextmanager
def subscription_provider_mutation_lock(organization: Any) -> Iterator[None]:
    """Serialize app-owned Stripe subscription mutations without a DB transaction."""
    if connection.vendor != "postgresql":
        yield
        return

    lock_key = _subscription_provider_mutation_lock_key(organization)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_lock(%s)", [lock_key])
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [lock_key])
            (released,) = cursor.fetchone()
        if not released:
            raise BillingError(
                "The Stripe subscription mutation lock was not held at release."
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
    with org_scope(organization):
        subscription = _resolve_authoritative_subscription_reservation(
            organization=organization,
        )
    if subscription is None:
        return None
    _ensure_billing_enabled(snapshot)

    stripe_subscription_id = str(subscription.stripe_subscription_id or "").strip()
    if not stripe_subscription_id:
        raise BillingSubscriptionAnomalyError(
            "Current recurring subscription is missing a Stripe subscription id."
        )

    resolved_client = stripe_client or get_stripe_client(settings_snapshot=snapshot)
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
    resolved_client = stripe_client or get_stripe_client(settings_snapshot=snapshot)
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
    with org_scope(organization):
        subscription = _resolve_authoritative_subscription_reservation(
            organization=organization,
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

    resolved_client = stripe_client or get_stripe_client(settings_snapshot=snapshot)
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
        _lock_organization_for_billing_mutation(expected_identity.organization_id)
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


def credit_user(
    user: Any,
    *,
    amount: int,
    transaction_type: str,
    description: str = "",
    stripe_event_id: str = "",
    stripe_object_id: str = "",
    stripe_reference_data: Mapping[str, Any] | None = None,
    organization: Any,
) -> CreditTransaction:
    """Credit an organization's balance for a Stripe-backed business object."""
    if amount <= 0:
        raise BillingValidationError("Credit amount must be greater than zero.")

    normalized_reference_data = _normalize_mapping(stripe_reference_data or {})
    try:
        with transaction.atomic():
            _lock_organization_for_billing_mutation(organization)
            balance, _ = _get_or_create_credit_balance(organization=organization)
            existing_transaction = _find_existing_credit_transaction(
                user=user,
                organization=organization,
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
            transaction_row = CreditTransaction.all_objects.create(
                user=user,
                organization=organization,
                amount=amount,
                transaction_type=transaction_type,
                stripe_event_id=stripe_event_id,
                stripe_object_id=stripe_object_id,
                stripe_reference_data=normalized_reference_data,
                description=description,
                balance_after=updated_balance,
            )
            return transaction_row
    except IntegrityError:
        # A concurrent request beat us to inserting this transaction.
        # The DB constraint prevents duplicates; the savepoint has been
        # rolled back (including the balance delta), so re-fetch the row
        # that was committed by the other request.
        with transaction.atomic():
            _lock_organization_for_billing_mutation(organization)
            existing = CreditTransaction.all_objects.filter(
                transaction_type=transaction_type,
                stripe_event_id=stripe_event_id,
                organization=organization,
            ).first()
        if existing is not None:
            return existing
        raise


def debit_user(
    user: Any,
    *,
    amount: int,
    description: str = "",
    organization: Any,
) -> CreditTransaction:
    """Debit credits from an organization and record the usage transaction."""
    if amount <= 0:
        raise BillingValidationError("Debit amount must be greater than zero.")

    with transaction.atomic():
        _lock_organization_for_billing_mutation(organization)
        balance = _get_locked_credit_balance(organization=organization)
        if balance is None or int(balance.balance) < amount:
            raise InsufficientCreditsError("Organization does not have enough credits.")

        updated_balance = _apply_locked_credit_balance_delta(
            balance=balance,
            delta=-amount,
        )
        return CreditTransaction.all_objects.create(
            user=user,
            organization=organization,
            amount=-amount,
            transaction_type=CreditTransaction.TransactionType.USAGE,
            description=description,
            balance_after=updated_balance,
        )


def _get_or_create_credit_balance(
    *,
    organization: Any,
) -> tuple[CreditBalance, bool]:
    balance, created = CreditBalance.all_objects.get_or_create(
        organization=organization,
        defaults={"balance": 0},
    )
    return CreditBalance.all_objects.select_for_update().get(pk=balance.pk), created


def _get_locked_credit_balance(
    *,
    organization: Any,
) -> CreditBalance | None:
    return (
        CreditBalance.all_objects.select_for_update()
        .filter(organization=organization)
        .first()
    )


def _apply_locked_credit_balance_delta(*, balance: CreditBalance, delta: int) -> int:
    CreditBalance.all_objects.filter(pk=balance.pk).update(
        balance=F("balance") + delta,
        updated_at=timezone.now(),
    )
    balance.refresh_from_db(fields=["balance", "updated_at"])
    return int(balance.balance)


@_translate_stripe_errors("Stripe webhook handling failed.")
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
            "Stripe webhook secret is not configured in the runtime settings."
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

    event_api_version = str(event_payload.get("api_version") or "").strip()
    logger.info(
        "Stripe webhook event %s reports API version %s.",
        event_id,
        event_api_version or "<blank>",
    )
    if _stripe_named_release(event_api_version) != _stripe_named_release(
        STRIPE_API_VERSION
    ):
        raise BillingConfigurationError(
            f"Stripe webhook event API version {event_api_version or '<blank>'} does "
            f"not match the required Stripe API version {STRIPE_API_VERSION}; "
            f"recreate the webhook endpoint at {STRIPE_API_VERSION}."
        )

    with _webhook_event_processing_lock(event_id):
        webhook_event, _ = WebhookEvent.objects.get_or_create(
            stripe_event_id=event_id,
            defaults={
                "event_type": event_type,
                "payload": event_payload,
            },
        )
        return _process_verified_stripe_event(
            webhook_event=webhook_event,
            event_payload=event_payload,
            event_type=event_type,
            stripe_client=resolved_client,
        )


def _process_verified_stripe_event(
    *,
    webhook_event: WebhookEvent,
    event_payload: Mapping[str, Any],
    event_type: str,
    stripe_client: Any,
) -> StripeWebhookResult:
    """Process one verified event while its session-level mutex is held."""
    with transaction.atomic():
        locked_event = WebhookEvent.objects.select_for_update().get(pk=webhook_event.pk)
        if locked_event.processed:
            return StripeWebhookResult(
                duplicate=True,
                event_type=locked_event.event_type,
                status="duplicate",
            )

    # Provider I/O happens outside a database transaction. The session-level
    # advisory mutex remains held so another delivery of this event cannot
    # enter its handler before the final processed state is persisted.
    processing_status = "ignored"
    processing_error_message = ""
    try:
        if event_type == STRIPE_EVENT_TYPE_CHECKOUT_SESSION_COMPLETED:
            _handle_checkout_session_completed_event(
                event_payload,
                stripe_client=stripe_client,
            )
            processing_status = "processed"
        elif event_type == STRIPE_EVENT_TYPE_CHECKOUT_SESSION_EXPIRED:
            _handle_checkout_session_expired_event(event_payload)
            processing_status = "processed"
        elif event_type == STRIPE_EVENT_TYPE_INVOICE_PAID:
            _handle_invoice_paid_event(
                event_payload,
                stripe_client=stripe_client,
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
    except BillingError as exc:
        processing_error_message = str(exc)

    # Persist result (short atomic, no Stripe round-trips)
    with transaction.atomic():
        WebhookEvent.objects.filter(pk=webhook_event.pk).update(
            event_type=event_type,
            payload=event_payload,
            processed=(not processing_error_message),
            processing_error=processing_error_message,
        )

    if processing_error_message:
        raise BillingWebhookError(processing_error_message)

    return StripeWebhookResult(
        duplicate=False,
        event_type=event_type,
        status=processing_status,
    )


def _webhook_event_processing_lock_key(event_id: str) -> int:
    digest = hashlib.sha256(
        f"quickscale_billing:webhook-event:{event_id}".encode()
    ).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


@contextmanager
def _webhook_event_processing_lock(event_id: str) -> Iterator[None]:
    """Serialize one Stripe event without spanning provider I/O in an atomic."""
    if connection.vendor != "postgresql":
        yield
        return

    lock_key = _webhook_event_processing_lock_key(event_id)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_lock(%s)", [lock_key])
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [lock_key])
            (released,) = cursor.fetchone()
        if not released:
            raise BillingWebhookError(
                "The Stripe webhook event processing lock was not held at release."
            )


def _ensure_billing_enabled(settings_snapshot: BillingSettingsSnapshot) -> None:
    if not settings_snapshot.enabled:
        raise BillingDisabledError("Billing module is disabled.")


def _lock_organization_for_billing_mutation(organization: Any) -> Any:
    """Lock the organization row that serializes billing writes with purge."""
    organization_pk = getattr(organization, "pk", organization)
    if organization_pk is None:
        raise BillingWebhookError(
            "Could not resolve an organization for the billing mutation."
        )
    organization_model = apps.get_model(
        "quickscale_orgs",
        "Organization",
    )
    locked_organization = (
        organization_model._default_manager.select_for_update()
        .filter(pk=organization_pk)
        .first()
    )
    if locked_organization is None:
        raise BillingWebhookError(
            "The billing organization no longer exists; the mutation was refused."
        )
    return locked_organization


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

    resolved_organization = _resolve_organization_for_invoice(
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
    with subscription_provider_mutation_lock(resolved_organization):
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

    # Phase 1: resolve user + subscription in a short org scope.
    with org_scope(resolved_organization):
        resolved_user = _resolve_user_for_invoice(invoice_payload=invoice_payload)
        subscription_id = _invoice_subscription_id(invoice_payload)
        customer_id = str(invoice_payload.get("customer") or "").strip()
        subscription = _resolve_subscription_for_runtime_event(
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
        payload_organization = _resolve_organization_for_subscription(
            subscription_payload=subscription_payload
        )
        mutation_organization = payload_organization or resolved_organization
        if mutation_organization is None:
            raise BillingWebhookError(
                "Could not resolve a local organization for the Stripe subscription."
            )
        if not provider_lock_held:
            with subscription_provider_mutation_lock(mutation_organization):
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
        with subscription_provider_mutation_lock(mutation_organization):
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
        mutation_organization = _lock_organization_for_billing_mutation(
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

    resolved_organization = _resolve_organization_for_invoice(
        invoice_payload=invoice_payload,
    )
    if resolved_organization is None:
        raise BillingWebhookError(
            "Could not resolve a local organization for the Stripe invoice."
        )
    with subscription_provider_mutation_lock(resolved_organization):
        return _apply_invoice_payment_failed_event(
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
        resolved_organization = _lock_organization_for_billing_mutation(
            resolved_organization
        )
        resolved_user = _resolve_user_for_invoice(invoice_payload=invoice_payload)
        subscription = _resolve_subscription_for_runtime_event(
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

    plan = _resolve_plan_for_subscription_payload(subscription_payload)
    if expected_plan is not None and plan.pk != expected_plan.pk:
        raise BillingWebhookError(
            "Stripe subscription does not match the invoiced billing plan."
        )

    organization = _resolve_organization_for_subscription(
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
    with subscription_provider_mutation_lock(organization):
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
        organization = _lock_organization_for_billing_mutation(organization)
        user = _resolve_user_for_subscription(subscription_payload=subscription_payload)
        if user is None:
            user = fallback_user
        if user is None and organization is None:
            raise BillingWebhookError(
                "Could not resolve a local user for the Stripe subscription."
            )

        subscription = _resolve_subscription_for_runtime_event(
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
        _record_subscription_checkout_completion(checkout_session_payload)
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
    organization = _resolve_organization_for_checkout_session(
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

    # Phase 3: each handler owns its provider mutex and org scope so purge,
    # account deletion, and Checkout completion observe one serial history.
    with subscription_provider_mutation_lock(organization):
        with org_scope(organization):
            _lock_organization_for_billing_mutation(organization)
            reservation = _resolve_purchase_checkout_for_session(
                checkout_session_payload=checkout_session_payload,
                organization=organization,
                for_update=True,
            )
            if reservation is not None:
                if reservation.status == PurchaseCheckout.Status.EXPIRED:
                    raise BillingWebhookError(
                        "Completed Stripe checkout conflicts with an expired local "
                        "purchase reservation."
                    )
                if reservation.plan_id != plan.pk:
                    raise BillingWebhookError(
                        "Completed Stripe checkout plan conflicts with its local "
                        "purchase reservation."
                    )
                if reservation.user_id is not None and reservation.user_id != getattr(
                    user, "pk", None
                ):
                    raise BillingWebhookError(
                        "Completed Stripe checkout user conflicts with its local "
                        "purchase reservation."
                    )
            transaction_row = credit_user(
                user,
                organization=organization,
                amount=credited_amount,
                transaction_type=CreditTransaction.TransactionType.PURCHASE,
                description=f"{plan.name} credits from Stripe checkout session {checkout_session_id}",
                stripe_event_id=str(event_payload.get("id") or "").strip(),
                stripe_object_id=checkout_session_id,
                stripe_reference_data=reference_data,
            )
            if reservation is not None:
                reservation.stripe_checkout_session_id = checkout_session_id
                reservation.status = PurchaseCheckout.Status.COMPLETED
                reservation.checkout_expires_at = (
                    _extract_checkout_session_expires_at(checkout_session_payload)
                    or reservation.checkout_expires_at
                )
                reservation.save(
                    update_fields=[
                        "stripe_checkout_session_id",
                        "status",
                        "checkout_expires_at",
                    ]
                )
            else:
                PurchaseCheckout.all_objects.filter(
                    organization=organization,
                    stripe_checkout_session_id=checkout_session_id,
                    status=PurchaseCheckout.Status.OPEN,
                ).update(status=PurchaseCheckout.Status.COMPLETED)
            return transaction_row


def _record_subscription_checkout_completion(
    checkout_session_payload: Mapping[str, Any],
) -> None:
    """Bind Checkout's subscription identity before later webhooks arrive."""
    organization = _resolve_organization_for_checkout_session(
        checkout_session_payload=checkout_session_payload,
        payment_intent_payload={},
    )
    if organization is None:
        return

    checkout_session_id = str(checkout_session_payload.get("id") or "").strip()
    provider_subscription_id = _stripe_object_id(
        checkout_session_payload.get("subscription")
    )
    if not provider_subscription_id:
        raise BillingWebhookError(
            "Completed subscription checkout is missing its Stripe subscription id."
        )

    with subscription_provider_mutation_lock(organization):
        with org_scope(organization):
            locked_organization = _lock_organization_for_billing_mutation(organization)
            reservation = _resolve_subscription_checkout_for_session(
                checkout_session_payload=checkout_session_payload,
                organization=locked_organization,
                for_update=True,
            )
            if reservation is None:
                raise BillingWebhookError(
                    "Completed subscription checkout could not be reconciled to its "
                    "local reservation."
                )
            if reservation.status == Subscription.Status.INCOMPLETE_EXPIRED:
                raise BillingWebhookError(
                    "Completed subscription checkout conflicts with an expired local "
                    "reservation."
                )
            _validate_subscription_checkout_reservation_metadata(
                reservation=reservation,
                checkout_session_payload=checkout_session_payload,
            )
            _validate_completed_checkout_provider_identity(
                reservation=reservation,
                organization=locked_organization,
                checkout_session_payload=checkout_session_payload,
            )
            reservation.stripe_subscription_id = provider_subscription_id
            reservation.stripe_checkout_session_id = checkout_session_id
            reservation.checkout_expires_at = None
            customer_id = str(checkout_session_payload.get("customer") or "").strip()
            update_fields = [
                "stripe_subscription_id",
                "stripe_checkout_session_id",
                "checkout_expires_at",
            ]
            if customer_id and reservation.stripe_customer_id != customer_id:
                reservation.stripe_customer_id = customer_id
                update_fields.append("stripe_customer_id")
            reservation.save(update_fields=update_fields)


def _handle_checkout_session_expired_event(
    event_payload: Mapping[str, Any],
) -> None:
    """Make an exact one-time reservation terminal after Stripe expiry."""
    checkout_session_payload = _extract_event_object(event_payload)
    checkout_session_id = str(checkout_session_payload.get("id") or "").strip()
    if not checkout_session_id:
        raise BillingWebhookError("Stripe checkout session payload is missing an id.")
    checkout_mode = str(checkout_session_payload.get("mode") or "").strip()
    if checkout_mode == "subscription":
        _record_subscription_checkout_expiration(checkout_session_payload)
        return
    if checkout_mode and checkout_mode != "payment":
        return

    organization = _resolve_organization_for_checkout_session(
        checkout_session_payload=checkout_session_payload,
        payment_intent_payload={},
    )
    if organization is None:
        return

    with subscription_provider_mutation_lock(organization):
        with org_scope(organization):
            _lock_organization_for_billing_mutation(organization)
            reservation = _resolve_purchase_checkout_for_session(
                checkout_session_payload=checkout_session_payload,
                organization=organization,
                for_update=True,
            )
            if reservation is None:
                return
            if reservation.status == PurchaseCheckout.Status.COMPLETED:
                raise BillingWebhookError(
                    "Expired Stripe checkout conflicts with a completed local purchase "
                    "reservation."
                )
            reservation.stripe_checkout_session_id = checkout_session_id
            reservation.status = PurchaseCheckout.Status.EXPIRED
            reservation.checkout_expires_at = (
                _extract_checkout_session_expires_at(checkout_session_payload)
                or reservation.checkout_expires_at
            )
            reservation.save(
                update_fields=[
                    "stripe_checkout_session_id",
                    "status",
                    "checkout_expires_at",
                ]
            )


def _record_subscription_checkout_expiration(
    checkout_session_payload: Mapping[str, Any],
) -> None:
    """Bind and expire an exact subscription reservation after response loss."""
    organization = _resolve_organization_for_checkout_session(
        checkout_session_payload=checkout_session_payload,
        payment_intent_payload={},
    )
    if organization is None:
        return

    checkout_session_id = str(checkout_session_payload.get("id") or "").strip()
    with subscription_provider_mutation_lock(organization):
        with org_scope(organization):
            locked_organization = _lock_organization_for_billing_mutation(organization)
            reservation = _resolve_subscription_checkout_for_session(
                checkout_session_payload=checkout_session_payload,
                organization=locked_organization,
                for_update=True,
            )
            if reservation is None:
                raise BillingWebhookError(
                    "Expired subscription checkout could not be reconciled to its "
                    "local reservation."
                )
            if str(reservation.stripe_subscription_id or "").strip():
                raise BillingWebhookError(
                    "Expired subscription checkout conflicts with a locally bound "
                    "Stripe subscription."
                )
            if reservation.status not in {
                Subscription.Status.INCOMPLETE,
                Subscription.Status.INCOMPLETE_EXPIRED,
            }:
                raise BillingWebhookError(
                    "Expired subscription checkout conflicts with the local "
                    "subscription state."
                )
            _validate_subscription_checkout_reservation_metadata(
                reservation=reservation,
                checkout_session_payload=checkout_session_payload,
            )
            _validate_completed_checkout_provider_identity(
                reservation=reservation,
                organization=locked_organization,
                checkout_session_payload=checkout_session_payload,
            )
            reservation.stripe_checkout_session_id = checkout_session_id
            reservation.status = Subscription.Status.INCOMPLETE_EXPIRED
            reservation.checkout_expires_at = (
                _extract_checkout_session_expires_at(checkout_session_payload)
                or reservation.checkout_expires_at
            )
            reservation.save(
                update_fields=[
                    "stripe_checkout_session_id",
                    "status",
                    "checkout_expires_at",
                ]
            )


def _resolve_subscription_checkout_for_session(
    *,
    checkout_session_payload: Mapping[str, Any],
    organization: Any,
    for_update: bool,
) -> Subscription | None:
    """Resolve and validate the exact local subscription Checkout reservation."""
    checkout_session_id = str(checkout_session_payload.get("id") or "").strip()
    reservation_reference = _resolve_subscription_checkout_reference(
        [checkout_session_payload]
    )
    reservation_pk = _subscription_checkout_pk_from_reference(reservation_reference)
    if reservation_reference and reservation_pk is None:
        raise BillingWebhookError(
            "Stripe checkout session has an invalid subscription reservation reference."
        )

    queryset = Subscription.all_objects.filter(organization=organization)
    if for_update:
        queryset = queryset.select_for_update()
    if reservation_pk is not None:
        reservation = queryset.filter(pk=reservation_pk).first()
        if reservation is None:
            raise BillingWebhookError(
                "Stripe checkout session subscription reservation could not be "
                "resolved."
            )
    elif checkout_session_id:
        reservation = queryset.filter(
            stripe_checkout_session_id=checkout_session_id
        ).first()
    else:
        reservation = None
    if reservation is None:
        return None

    persisted_checkout_session_id = str(
        reservation.stripe_checkout_session_id or ""
    ).strip()
    if (
        persisted_checkout_session_id
        and checkout_session_id
        and persisted_checkout_session_id != checkout_session_id
    ):
        raise BillingWebhookError(
            "Stripe checkout session conflicts with its local subscription reservation."
        )
    if (
        checkout_session_id
        and Subscription.all_objects.filter(
            organization=organization,
            stripe_checkout_session_id=checkout_session_id,
        )
        .exclude(pk=reservation.pk)
        .exists()
    ):
        raise BillingWebhookError(
            "Stripe checkout session is already bound to a different subscription "
            "reservation."
        )
    return reservation


def _validate_subscription_checkout_reservation_metadata(
    *,
    reservation: Subscription,
    checkout_session_payload: Mapping[str, Any],
) -> None:
    """Reject immutable Checkout metadata that conflicts with its reservation."""
    metadata_price_id = _extract_metadata_value(
        [checkout_session_payload],
        _PRICE_ID_METADATA_KEY,
    )
    if metadata_price_id and metadata_price_id != reservation.plan.stripe_price_id:
        raise BillingWebhookError(
            "Stripe subscription checkout plan conflicts with its local reservation."
        )
    metadata_user = _resolve_user_from_metadata_sources([checkout_session_payload])
    if (
        metadata_user is not None
        and reservation.user_id is not None
        and reservation.user_id != getattr(metadata_user, "pk", None)
    ):
        raise BillingWebhookError(
            "Stripe subscription checkout user conflicts with its local reservation."
        )


def _resolve_purchase_checkout_for_session(
    *,
    checkout_session_payload: Mapping[str, Any],
    organization: Any,
    for_update: bool,
) -> PurchaseCheckout | None:
    """Resolve and validate the exact local one-time Checkout reservation."""
    checkout_session_id = str(checkout_session_payload.get("id") or "").strip()
    reservation_reference = _resolve_purchase_checkout_reference(
        [checkout_session_payload]
    )
    reservation_pk = _purchase_checkout_pk_from_reference(reservation_reference)
    if reservation_reference and reservation_pk is None:
        raise BillingWebhookError(
            "Stripe checkout session has an invalid purchase reservation reference."
        )

    queryset = PurchaseCheckout.all_objects.filter(organization=organization)
    if for_update:
        queryset = queryset.select_for_update()
    if reservation_pk is not None:
        reservation = queryset.filter(pk=reservation_pk).first()
        if reservation is None:
            raise BillingWebhookError(
                "Stripe checkout session purchase reservation could not be resolved."
            )
    elif checkout_session_id:
        reservation = queryset.filter(
            stripe_checkout_session_id=checkout_session_id
        ).first()
    else:
        reservation = None
    if reservation is None:
        return None

    persisted_checkout_session_id = str(
        reservation.stripe_checkout_session_id or ""
    ).strip()
    if (
        persisted_checkout_session_id
        and checkout_session_id
        and persisted_checkout_session_id != checkout_session_id
    ):
        raise BillingWebhookError(
            "Stripe checkout session conflicts with its local purchase reservation."
        )
    if (
        checkout_session_id
        and PurchaseCheckout.all_objects.filter(
            organization=organization,
            stripe_checkout_session_id=checkout_session_id,
        )
        .exclude(pk=reservation.pk)
        .exists()
    ):
        raise BillingWebhookError(
            "Stripe checkout session is already bound to a different purchase "
            "reservation."
        )
    return reservation


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
        subscription = _resolve_authoritative_subscription_reservation(
            organization=organization,
            customer_id=customer_id,
            for_update=for_update,
        )
        if subscription is not None:
            return subscription

    if organization is not None:
        return _resolve_authoritative_subscription_reservation(
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
        subscription = _resolve_authoritative_subscription_reservation(
            customer_id=customer_id,
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
        subscription = _resolve_authoritative_subscription_reservation(
            customer_id=customer_id,
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
    organization: Any | None = None,
    customer_id: str = "",
    for_update: bool = False,
) -> Subscription | None:
    normalized_customer_id = customer_id.strip()
    if organization is None and not normalized_customer_id:
        return None

    queryset = Subscription.all_objects.order_by("-pk")
    if not for_update:
        queryset = queryset.select_related("user", "plan")
    if for_update:
        queryset = queryset.select_for_update()
    if organization is not None:
        queryset = queryset.filter(organization=organization)
    if normalized_customer_id:
        queryset = queryset.filter(
            Q(stripe_customer_id=normalized_customer_id)
            | Q(organization__stripe_customer_id=normalized_customer_id)
        )
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
        return False
    if reservation.checkout_expires_at is None:
        return False
    return reservation.checkout_expires_at <= timezone.now()


def _expire_subscription_reservation(reservation: Subscription) -> None:
    reservation.status = Subscription.Status.INCOMPLETE_EXPIRED
    reservation.save(update_fields=["status"])


def _create_subscription_reservation(
    *,
    user: Any,
    organization: Any,
    plan: Plan,
    stripe_customer_id: str | None = None,
) -> tuple[Subscription, bool]:
    try:
        with transaction.atomic():
            return (
                Subscription.all_objects.create(
                    user=user,
                    organization=organization,
                    plan=plan,
                    stripe_customer_id=stripe_customer_id,
                    status=Subscription.Status.INCOMPLETE,
                ),
                False,
            )
    except IntegrityError as exc:
        recovered_reservation = _recover_conflicting_subscription_reservation(
            user=user,
            organization=organization,
            plan=plan,
        )
        if recovered_reservation is not None:
            return recovered_reservation, True
        raise BillingValidationError(_CURRENT_RECURRING_SUBSCRIPTION_ERROR) from exc


def _recover_conflicting_subscription_reservation(
    *,
    user: Any,
    organization: Any | None,
    plan: Plan,
) -> Subscription | None:
    with transaction.atomic():
        _lock_organization_for_billing_mutation(organization)
        current_reservation = _resolve_authoritative_subscription_reservation(
            organization=organization,
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
    organization: Any,
    plan: Plan,
    stripe_customer_id: str | None = None,
) -> tuple[Subscription, bool]:
    _lock_organization_for_billing_mutation(organization)
    current_reservation = _resolve_authoritative_subscription_reservation(
        organization=organization,
        for_update=True,
    )
    if current_reservation is None:
        return _create_subscription_reservation(
            user=user,
            organization=organization,
            plan=plan,
            stripe_customer_id=stripe_customer_id,
        )

    if not _subscription_reservation_can_be_reused(current_reservation, plan=plan):
        raise BillingValidationError(_CURRENT_RECURRING_SUBSCRIPTION_ERROR)

    if _subscription_reservation_needs_replacement(current_reservation):
        persisted_customer_id = str(
            current_reservation.stripe_customer_id or ""
        ).strip()
        _expire_subscription_reservation(current_reservation)
        return _create_subscription_reservation(
            user=user,
            organization=organization,
            plan=plan,
            stripe_customer_id=persisted_customer_id or None,
        )

    return current_reservation, not bool(
        str(current_reservation.stripe_checkout_session_id or "").strip()
    )


def _reuse_live_subscription_checkout_url(
    *,
    reservation: Subscription,
    stripe_client: Any,
) -> str:
    checkout_session_id = str(reservation.stripe_checkout_session_id or "").strip()
    if not checkout_session_id:
        return ""
    if not hasattr(stripe_client, "retrieve_checkout_session"):
        raise BillingError(
            "Stripe checkout retrieval is unavailable; the existing subscription "
            "checkout cannot be replaced safely."
        )

    checkout_session = _normalize_mapping(
        stripe_client.retrieve_checkout_session(
            checkout_session_id=checkout_session_id,
        )
    )
    provider_status = str(checkout_session.get("status") or "").strip().lower()
    if provider_status == "expired":
        return ""
    if provider_status == "complete":
        provider_subscription_id = _stripe_object_id(
            checkout_session.get("subscription")
        )
        with org_scope(reservation.organization):
            locked_organization = _lock_organization_for_billing_mutation(
                reservation.organization
            )
            current_reservation = (
                Subscription.all_objects.select_for_update()
                .filter(
                    pk=reservation.pk,
                    stripe_checkout_session_id=checkout_session_id,
                )
                .first()
            )
            if current_reservation is None:
                raise BillingValidationError(_CURRENT_RECURRING_SUBSCRIPTION_ERROR)
            _validate_completed_checkout_provider_identity(
                reservation=current_reservation,
                organization=locked_organization,
                checkout_session_payload=checkout_session,
            )
            existing_subscription_id = str(
                current_reservation.stripe_subscription_id or ""
            ).strip()
            update_fields: list[str] = []
            if provider_subscription_id and not existing_subscription_id:
                current_reservation.stripe_subscription_id = provider_subscription_id
                update_fields.append("stripe_subscription_id")
            if current_reservation.checkout_expires_at is not None:
                current_reservation.checkout_expires_at = None
                update_fields.append("checkout_expires_at")
            if update_fields:
                current_reservation.save(update_fields=update_fields)
        provider_label = provider_subscription_id or checkout_session_id
        raise BillingValidationError(
            "Stripe checkout completed and may have created a live subscription "
            f"({provider_label}); wait for subscription synchronization or "
            "reconcile it before creating another checkout."
        )
    if provider_status != "open":
        raise BillingError(
            "Stripe checkout session reconciliation returned an unsupported or "
            f"blank status for {checkout_session_id}."
        )

    checkout_url = _extract_live_checkout_session_url(checkout_session)
    if not checkout_url:
        raise BillingError(
            "Stripe reports the existing subscription checkout as open but did not "
            "return a reusable hosted URL; automatic replacement was refused."
        )
    return checkout_url


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


def _validate_completed_checkout_provider_identity(
    *,
    reservation: Subscription,
    organization: Any,
    checkout_session_payload: Mapping[str, Any],
) -> tuple[str, str]:
    """Reject a completed Checkout that conflicts with locked local identity."""
    provider_subscription_id = _stripe_object_id(
        checkout_session_payload.get("subscription")
    )
    provider_customer_id = _stripe_object_id(checkout_session_payload.get("customer"))
    reservation_subscription_id = str(reservation.stripe_subscription_id or "").strip()
    reservation_customer_id = str(reservation.stripe_customer_id or "").strip()
    organization_customer_id = str(
        getattr(organization, "stripe_customer_id", "") or ""
    ).strip()
    if (
        (
            provider_subscription_id
            and reservation_subscription_id
            and provider_subscription_id != reservation_subscription_id
        )
        or (
            provider_customer_id
            and reservation_customer_id
            and provider_customer_id != reservation_customer_id
        )
        or (
            provider_customer_id
            and organization_customer_id
            and provider_customer_id != organization_customer_id
        )
    ):
        raise BillingWebhookError(
            "Completed checkout provider identity conflicts with the locked "
            "subscription reservation or organization."
        )
    return provider_subscription_id, provider_customer_id


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


def _find_existing_credit_transaction(
    *,
    user: Any,
    organization: Any | None,
    transaction_type: str,
    stripe_event_id: str,
    stripe_object_id: str,
    stripe_reference_data: Mapping[str, Any],
) -> CreditTransaction | None:
    candidate_queryset = CreditTransaction.all_objects.select_for_update().filter(
        transaction_type=transaction_type,
    )
    if organization is not None:
        candidate_queryset = candidate_queryset.filter(organization=organization)
    else:
        candidate_queryset = candidate_queryset.filter(user=user)
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


def _resolve_authoritative_organization_customer_id(*, organization: Any) -> str:
    existing_customer_id = str(
        getattr(organization, "stripe_customer_id", "") or ""
    ).strip()
    if existing_customer_id:
        return existing_customer_id

    authoritative_subscription = _resolve_authoritative_subscription_reservation(
        organization=organization,
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
            locked_organization = _lock_organization_for_billing_mutation(organization)
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


def require_org_feature(feature_key: str) -> Callable:
    """Return a view decorator answering 402 when the org's plan lacks the feature.

    Module Conventions rule 34 publishes the plan-feature gate here: the
    request's organization is resolved through orgs' published
    ``resolve_request_org`` and the entitlement is read from billing's own
    active subscription, so no lower-layer module names billing.
    """
    from quickscale_modules_orgs.current_org import (
        CurrentOrgError,
        require_current_org,
    )
    from quickscale_modules_orgs.permissions import resolve_request_org

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapped(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            user = getattr(request, "user", None)
            if not bool(user is not None and getattr(user, "is_authenticated", False)):
                return HttpResponse(status=402)

            resolve_request_org(request, kwargs)
            try:
                organization = require_current_org(request)
            except CurrentOrgError:
                return HttpResponse(status=402)

            subscription = _get_active_org_subscription(organization)
            plan = getattr(subscription, "plan", None)
            features = getattr(plan, "features", None)
            if subscription is None or plan is None:
                return HttpResponse(status=402)
            if (
                not isinstance(features, (list, tuple, set))
                or feature_key not in features
            ):
                return HttpResponse(status=402)
            return cast(HttpResponse, view_func(request, *args, **kwargs))

        return wrapped

    return decorator


def _get_active_org_subscription(organization: Any) -> Subscription | None:
    """Return the organization's active subscription, if any.

    ``all_objects`` bypasses the tenant manager's contextvar filter because
    the query already filters by the explicit organization; the contextvar
    scoping breaks for slug-resolved views that do not run full middleware.
    """
    return (
        Subscription.all_objects.select_related("plan")
        .filter(
            organization=organization,
            status=Subscription.Status.ACTIVE,
        )
        .first()
    )


def organization_pricing_page_url(organization: Any) -> str:
    """Return billing's pricing-page URL for the organization-creation handoff.

    Module Conventions rule 4: billing declares this function on its
    ``AppConfig`` as the ``organization_pricing_url_hooks`` capability and
    the orgs create flow collects it, so no lower-layer module names
    billing's route, label, or settings.  ``organization`` is the hook
    contract's context argument; billing's pricing page is module-wide.
    An enabled billing whose URLconf does not mount the pricing route is
    misconfigured, so the reversal failure raises ``BillingConfigurationError``
    (rule 23) instead of answering a false negative.
    """
    try:
        return reverse("quickscale_billing:pricing_page")
    except NoReverseMatch as exc:
        raise BillingConfigurationError(
            "Billing is enabled but its pricing route is not mounted; "
            "run `quickscale apply` to restore the module's URL wiring."
        ) from exc


__all__ = [
    "account_deletion_user_reference_organization_ids",
    "cancel_current_subscription",
    "BillingConfigurationError",
    "BillingDisabledError",
    "BillingError",
    "BillingSettingsSnapshot",
    "BillingSubscriptionAnomalyError",
    "BillingValidationError",
    "BillingWebhookError",
    "BillingWebhookSignatureError",
    "debit_user",
    "detach_account_deletion_user_references",
    "StripeClient",
    "StripeWebhookResult",
    "SubscriptionCancellationTransition",
    "create_billing_portal_session",
    "create_checkout_session",
    "create_subscription_checkout_session",
    "credit_user",
    "get_or_create_stripe_customer",
    "get_stripe_client",
    "guard_organization_removal_provider_state",
    "handle_stripe_event",
    "InsufficientCreditsError",
    "organization_pricing_page_url",
    "OrgSelectionRequiredError",
    "resume_current_subscription",
    "reconcile_account_deletion_subscription_checkout",
    "reconcile_organization_removal_subscription_checkout",
    "reconcile_purchase_checkouts_for_removal",
    "require_org_feature",
    "subscription_provider_mutation_lock",
]
