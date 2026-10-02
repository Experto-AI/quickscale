"""Stripe SDK client wrapper and error translation.

Implementation detail of :mod:`quickscale_modules_billing.services`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from functools import wraps
from importlib import import_module
from typing import Any, ParamSpec, TypeVar

from quickscale_modules_billing._payload import (
    _normalize_mapping as _normalize_mapping,
)
from quickscale_modules_billing._payload import (
    _validate_customer_search_reference as _validate_customer_search_reference,
)
from quickscale_modules_billing._settings import (
    _ORG_REFERENCE_METADATA_KEY as _ORG_REFERENCE_METADATA_KEY,
)
from quickscale_modules_billing._settings import (
    _USER_METADATA_KEY as _USER_METADATA_KEY,
)
from quickscale_modules_billing._settings import (
    STRIPE_API_VERSION as STRIPE_API_VERSION,
)
from quickscale_modules_billing.exceptions import (
    BillingConfigurationError,
    BillingError,
    BillingWebhookError,
    BillingWebhookSignatureError,
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
