"""Public-surface lock for the billing ``services`` facade.

``services`` keeps its public import path and re-exports public names one way
from the private modules that define them; the Stripe webhook entry point
stays defined here.  This test pins public names only — no private name and no
incidental import — and checks that explicit re-exports are the defining
objects (decisions.md, Split-Facade Seams).
"""

from __future__ import annotations
import quickscale_modules_billing._stripe_client as _stripe_client

import importlib

import pytest

from quickscale_modules_billing import services

SERVICE_SURFACE: frozenset[str] = frozenset(
    {
        "BillingConfigurationError",
        "BillingDisabledError",
        "BillingError",
        "BillingSettingsSnapshot",
        "BillingSubscriptionAnomalyError",
        "BillingValidationError",
        "BillingWebhookError",
        "BillingWebhookSignatureError",
        "InsufficientCreditsError",
        "OrgSelectionRequiredError",
        "STRIPE_API_VERSION",
        "STRIPE_EVENT_TYPE_CHECKOUT_SESSION_COMPLETED",
        "STRIPE_EVENT_TYPE_CHECKOUT_SESSION_EXPIRED",
        "STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_CREATED",
        "STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_DELETED",
        "STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_UPDATED",
        "STRIPE_EVENT_TYPE_INVOICE_PAID",
        "STRIPE_EVENT_TYPE_INVOICE_PAYMENT_FAILED",
        "StripeClient",
        "StripeWebhookResult",
        "SubscriptionCancellationTransition",
        "SubscriptionCheckoutReconciliation",
        "SubscriptionProviderIdentity",
        "account_deletion_user_reference_organization_ids",
        "cancel_current_subscription",
        "create_billing_portal_session",
        "create_checkout_session",
        "create_subscription_checkout_session",
        "credit_user",
        "debit_user",
        "detach_account_deletion_user_references",
        "get_or_create_stripe_customer",
        "get_stripe_client",
        "guard_organization_removal_provider_state",
        "handle_stripe_event",
        "is_enabled",
        "logger",
        "organization_pricing_page_url",
        "reconcile_account_deletion_subscription_checkout",
        "reconcile_elapsed_subscription_checkout",
        "reconcile_organization_removal_subscription_checkout",
        "reconcile_purchase_checkouts_for_removal",
        "require_org_feature",
        "resume_current_subscription",
        "subscription_provider_mutation_lock",
    }
)

INCIDENTAL_NAMES = frozenset(
    {"P", "R", "T", "Any", "TypeVar", "ParamSpec", "annotations", "re", "json", "cast"}
)

REEXPORTED_FROM: dict[str, str] = {
    "BillingConfigurationError": "quickscale_modules_billing.exceptions",
    "BillingDisabledError": "quickscale_modules_billing.exceptions",
    "BillingError": "quickscale_modules_billing.exceptions",
    "BillingSettingsSnapshot": "quickscale_modules_billing._settings",
    "BillingSubscriptionAnomalyError": "quickscale_modules_billing.exceptions",
    "BillingValidationError": "quickscale_modules_billing.exceptions",
    "BillingWebhookError": "quickscale_modules_billing.exceptions",
    "BillingWebhookSignatureError": "quickscale_modules_billing.exceptions",
    "InsufficientCreditsError": "quickscale_modules_billing.exceptions",
    "OrgSelectionRequiredError": "quickscale_modules_billing.exceptions",
    "STRIPE_API_VERSION": "quickscale_modules_billing._settings",
    "STRIPE_EVENT_TYPE_CHECKOUT_SESSION_COMPLETED": "quickscale_modules_billing._settings",
    "STRIPE_EVENT_TYPE_CHECKOUT_SESSION_EXPIRED": "quickscale_modules_billing._settings",
    "STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_CREATED": "quickscale_modules_billing._settings",
    "STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_DELETED": "quickscale_modules_billing._settings",
    "STRIPE_EVENT_TYPE_CUSTOMER_SUBSCRIPTION_UPDATED": "quickscale_modules_billing._settings",
    "STRIPE_EVENT_TYPE_INVOICE_PAID": "quickscale_modules_billing._settings",
    "STRIPE_EVENT_TYPE_INVOICE_PAYMENT_FAILED": "quickscale_modules_billing._settings",
    "StripeClient": "quickscale_modules_billing._stripe_client",
    "StripeWebhookResult": "quickscale_modules_billing._settings",
    "SubscriptionCancellationTransition": "quickscale_modules_billing._settings",
    "SubscriptionCheckoutReconciliation": "quickscale_modules_billing._settings",
    "SubscriptionProviderIdentity": "quickscale_modules_billing._settings",
    "account_deletion_user_reference_organization_ids": "quickscale_modules_billing._removal",
    "cancel_current_subscription": "quickscale_modules_billing._subscription_mutations",
    "create_billing_portal_session": "quickscale_modules_billing._checkout",
    "create_checkout_session": "quickscale_modules_billing._checkout",
    "create_subscription_checkout_session": "quickscale_modules_billing._subscription_checkout",
    "credit_user": "quickscale_modules_billing._credits",
    "debit_user": "quickscale_modules_billing._credits",
    "detach_account_deletion_user_references": "quickscale_modules_billing._removal",
    "get_or_create_stripe_customer": "quickscale_modules_billing._customers",
    "get_stripe_client": "quickscale_modules_billing._stripe_client",
    "guard_organization_removal_provider_state": "quickscale_modules_billing._removal",
    "is_enabled": "quickscale_modules_billing._settings",
    "organization_pricing_page_url": "quickscale_modules_billing._settings",
    "reconcile_account_deletion_subscription_checkout": "quickscale_modules_billing._subscription_checkout",
    "reconcile_elapsed_subscription_checkout": "quickscale_modules_billing._subscription_checkout",
    "reconcile_organization_removal_subscription_checkout": "quickscale_modules_billing._subscription_checkout",
    "reconcile_purchase_checkouts_for_removal": "quickscale_modules_billing._removal",
    "require_org_feature": "quickscale_modules_billing._settings",
    "resume_current_subscription": "quickscale_modules_billing._subscription_mutations",
    "subscription_provider_mutation_lock": "quickscale_modules_billing._locks",
}


def test_public_surface_importable() -> None:
    """Every pinned public name is present on the facade."""
    missing = sorted(SERVICE_SURFACE - set(dir(services)))
    assert not missing, f"services is missing public names: {missing}"


def test_surface_pins_no_private_or_incidental_names() -> None:
    """The expected set names public facade API only."""
    for name in SERVICE_SURFACE:
        assert not name.startswith("_"), f"services pins private {name!r}"
    incidental = SERVICE_SURFACE & INCIDENTAL_NAMES
    assert not incidental, f"services pins incidental names: {sorted(incidental)}"


def test_declared_surface_is_public() -> None:
    """``__all__`` stays a subset of the pinned public surface."""
    assert set(services.__all__) <= set(SERVICE_SURFACE)


def test_reexports_are_the_defining_objects() -> None:
    """A re-export is the same object as its defining module's binding."""
    for name, source in REEXPORTED_FROM.items():
        defining = importlib.import_module(source)
        value = getattr(defining, name)
        if isinstance(value, (dict, list, set)):
            continue
        assert getattr(services, name) is value, (
            f"services.{name} is not {source}.{name}"
        )


def test_get_stripe_client_lives_in_the_stripe_client_module() -> None:
    """The moved helper is owned by ``_stripe_client`` and re-exported."""
    assert _stripe_client.get_stripe_client.__module__ == (
        "quickscale_modules_billing._stripe_client"
    )


def test_defining_module_patch_reaches_checkout_collaborator() -> None:
    """A replacement bound on ``_customers`` reaches ``_checkout`` at call time."""
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch

    from quickscale_modules_billing import _checkout, _customers, _settings, _validation

    plan = SimpleNamespace(stripe_price_id="price_1")
    organization = SimpleNamespace(pk=1, name="org")
    user = SimpleNamespace(pk=2)
    client = MagicMock()
    client.retrieve_price.return_value = {"id": "price_1"}

    with (
        patch.object(_settings, "_ensure_billing_enabled"),
        patch.object(_validation, "_validate_one_time_purchase_plan"),
        patch.object(_validation, "_validate_stripe_price_parity"),
        patch.object(
            _customers,
            "get_or_create_stripe_customer",
            side_effect=AssertionError("defining-module replacement reached"),
        ) as customer,
    ):
        with pytest.raises(AssertionError, match="defining-module replacement"):
            _checkout._create_checkout_session(
                user,
                plan,
                "https://ok",
                "https://cancel",
                organization=organization,
                stripe_client=client,
                settings_snapshot=MagicMock(),
            )

    customer.assert_called_once()
