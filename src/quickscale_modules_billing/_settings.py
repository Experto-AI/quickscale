"""Billing settings, dataclasses, and module gating.

Implementation detail of :mod:`quickscale_modules_billing.services`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any, Final, cast

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.urls import NoReverseMatch, reverse

from quickscale_modules_billing.exceptions import (
    BillingConfigurationError,
    BillingDisabledError,
)
from quickscale_modules_billing.models import (
    CREDIT_TRANSACTION_BUSINESS_REFERENCE_KEYS,
    Plan,
    Subscription,
)

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


def _ensure_billing_enabled(settings_snapshot: BillingSettingsSnapshot) -> None:
    if not settings_snapshot.enabled:
        raise BillingDisabledError("Billing module is disabled.")


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


def is_enabled() -> bool:
    """Return whether the module is enabled by ``QUICKSCALE_BILLING_ENABLED``.

    Rule 4: the question a caller asks before using an optional module;
    rule 3: the declared setting is read directly, with no default.
    """
    return bool(settings.QUICKSCALE_BILLING_ENABLED)
