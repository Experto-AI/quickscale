"""Contract tests for the pinned Stripe SDK integration.

These tests exercise the real ``stripe`` SDK: payloads are built from SDK
objects, webhook bodies are signed locally, and ``StripeClient`` verifies them
through the installed SDK. No network access is required, except for the one
test gated on ``STRIPE_TEST_SECRET_KEY``, which creates a real test-mode
subscription Checkout when that key is present.
"""

from __future__ import annotations
import quickscale_modules_billing._payload as _payload
import quickscale_modules_billing._settings as _settings
import quickscale_modules_billing._validation as _validation

from contextlib import suppress
import hashlib
import hmac
import json
import os
from pathlib import Path
from types import SimpleNamespace
import time
from typing import Any

import pytest
from django.conf import settings
import stripe

from quickscale_core.manifest.loader import load_manifest_from_path
from quickscale_modules_billing.models import (
    CreditBalance,
    CreditTransaction,
    Plan,
    Subscription,
    WebhookEvent,
)
from dataclasses import replace

from quickscale_modules_billing._settings import (
    STRIPE_API_VERSION,
    BillingSettingsSnapshot,
)
from quickscale_modules_billing.exceptions import (
    BillingConfigurationError,
    BillingError,
    BillingValidationError,
)
from quickscale_modules_billing._stripe_client import StripeClient
from quickscale_modules_billing._payload import _stripe_named_release
from quickscale_modules_billing.services import (
    handle_stripe_event,
)

from tests._stripe_payloads import (
    TEST_API_KEY,
    invoice_event,
    stripe_event,
    subscription_event,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
WEBHOOK_SECRET = "whsec_contract"  # noqa: S105 - test signing secret, not a credential


def _create_plan(*, price_id: str) -> Plan:
    return Plan.objects.create(
        name="Contract",
        slug=f"contract-{price_id}",
        stripe_price_id=price_id,
        credits_per_period=100,
        price_cents=1900,
        currency="usd",
        billing_interval=Plan.BillingInterval.MONTHLY,
    )


def _organization_reference(organization: Any) -> str:
    return f"{organization._meta.label_lower}:{organization.pk}"


def _user_reference(user: Any) -> str:
    return f"{user._meta.label_lower}:{user.pk}"


def _signed_body(
    payload: dict[str, Any],
    *,
    secret: str = WEBHOOK_SECRET,
) -> tuple[bytes, str]:
    """Sign a webhook body the way Stripe signs a delivery."""
    body = json.dumps(payload).encode("utf-8")
    timestamp = int(time.time())
    signature = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.{body.decode('utf-8')}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return body, f"t={timestamp},v1={signature}"


def _real_stripe_client() -> StripeClient:
    return StripeClient(stripe_module=stripe, api_key=TEST_API_KEY)


_LIVE_TEST_SECRET_KEY = os.environ.get("STRIPE_TEST_SECRET_KEY", "").strip()


def test_every_stripe_metadata_key_fits_the_provider_limit() -> None:
    """Stripe refuses metadata keys longer than 40 characters (its contract)."""
    metadata_key_constants = {
        name: value
        for name, value in vars(_settings).items()
        if name.endswith("_METADATA_KEY") and isinstance(value, str)
    }

    assert metadata_key_constants
    assert {
        name: key for name, key in metadata_key_constants.items() if len(key) > 40
    } == {}


@pytest.mark.django_db
def test_rendered_checkout_metadata_keys_fit_the_provider_limit(
    user,
    organization,
) -> None:
    """The generated Checkout metadata, inline keys included, is provider-valid."""
    plan = _create_plan(price_id="price_metadata_limit")
    metadata = _payload._build_checkout_session_metadata(
        user,
        plan,
        organization=organization,
    )
    metadata[_settings._SUBSCRIPTION_CHECKOUT_REFERENCE_METADATA_KEY] = (
        "quickscale_billing.subscription:1"
    )

    assert {key for key in metadata if len(key) > 40} == set()


@pytest.mark.skipif(
    not _LIVE_TEST_SECRET_KEY.startswith("sk_test_"),
    reason="STRIPE_TEST_SECRET_KEY is not set to a Stripe test-mode key.",
)
def test_subscription_checkout_is_accepted_by_stripe_test_mode() -> None:
    """The provider accepts the subscription Checkout the module builds."""
    stripe.api_key = _LIVE_TEST_SECRET_KEY
    stripe.api_version = STRIPE_API_VERSION
    customer = stripe.Customer.create(
        email="quickscale-contract@example.com",
        metadata={"purpose": "quickscale-subscription-contract"},
    )
    product = stripe.Product.create(name="QuickScale subscription contract")
    price = stripe.Price.create(
        product=product.id,
        unit_amount=1900,
        currency="usd",
        recurring={"interval": "month"},
    )
    metadata = {
        _settings._ORG_REFERENCE_METADATA_KEY: "quickscale_orgs.organization:1",
        _settings._USER_METADATA_KEY: "auth.user:1",
        _settings._PLAN_SLUG_METADATA_KEY: "contract",
        _settings._PLAN_CREDITS_METADATA_KEY: "100",
        _settings._PLAN_INTERVAL_METADATA_KEY: "monthly",
        _settings._PRICE_ID_METADATA_KEY: price.id,
        _settings._SUBSCRIPTION_CHECKOUT_REFERENCE_METADATA_KEY: (
            "quickscale_billing.subscription:1"
        ),
    }
    try:
        client = StripeClient(
            stripe_module=stripe,
            api_key=_LIVE_TEST_SECRET_KEY,
        )
        session = client.create_subscription_checkout_session(
            customer_id=customer.id,
            price_id=price.id,
            success_url="https://example.com/billing/subscription/success",
            cancel_url="https://example.com/billing/subscription/cancel",
            session_metadata=metadata,
            subscription_metadata=metadata,
            client_reference_id="auth.user:1",
        )

        assert session["mode"] == "subscription"
        assert str(session["id"]).startswith("cs_")
        assert session["client_reference_id"] == "auth.user:1"
        assert session["metadata"][
            _settings._SUBSCRIPTION_CHECKOUT_REFERENCE_METADATA_KEY
        ] == ("quickscale_billing.subscription:1")
    finally:
        with suppress(stripe.StripeError):
            stripe.Customer.delete(customer.id)
        with suppress(stripe.StripeError):
            stripe.Price.modify(price.id, active=False)
        with suppress(stripe.StripeError):
            stripe.Product.modify(product.id, active=False)


def test_normalize_mapping_keeps_real_sdk_object_identity() -> None:
    """A real SDK object must not collapse to an empty mapping."""
    session = stripe.checkout.Session.construct_from({"id": "cs_1"}, TEST_API_KEY)
    event = stripe.Event.construct_from(
        {"id": "evt_1", "type": "invoice.paid"},
        TEST_API_KEY,
    )

    assert _payload._normalize_mapping(session)["id"] == "cs_1"
    assert _payload._normalize_mapping(event)["id"] == "evt_1"


def test_construct_event_through_real_sdk_keeps_event_id() -> None:
    """A locally signed body survives SDK verification and normalization."""
    payload = stripe_event(
        event_id="evt_signed",
        event_type="invoice.paid",
        object_type="invoice",
        event_object={"id": "in_signed"},
    )
    body, signature = _signed_body(payload)

    event = _real_stripe_client().construct_event(
        body=body,
        signature=signature,
        webhook_secret=WEBHOOK_SECRET,
    )

    assert event["id"] == "evt_signed"
    assert event["api_version"] == STRIPE_API_VERSION


@pytest.mark.django_db
def test_checkout_validation_uses_the_configured_billing_currency() -> None:
    """The module-wide currency gates every Checkout, not only the plan row."""
    plan = Plan.objects.create(
        name="Euro Contract",
        slug="euro-contract",
        stripe_price_id="price_eur_contract",
        credits_per_period=100,
        price_cents=1900,
        currency="eur",
        billing_interval=Plan.BillingInterval.MONTHLY,
    )
    stripe_price = {
        "unit_amount": 1900,
        "currency": "eur",
        "type": "recurring",
        "recurring": {"interval": "month"},
    }
    with pytest.raises(BillingValidationError, match="configured billing currency"):
        _validation._validate_stripe_price_parity(plan=plan, stripe_price=stripe_price)

    supplied = replace(BillingSettingsSnapshot.from_settings(), billing_currency="eur")
    _validation._validate_stripe_price_parity(
        plan=plan,
        stripe_price=stripe_price,
        settings_snapshot=supplied,
    )

    usd_plan = _create_plan(price_id="price_usd_contract")
    usd_price = {
        "unit_amount": 1900,
        "currency": "usd",
        "type": "recurring",
        "recurring": {"interval": "month"},
    }
    with pytest.raises(BillingValidationError, match="configured billing currency"):
        _validation._validate_stripe_price_parity(
            plan=usd_plan,
            stripe_price=usd_price,
            settings_snapshot=supplied,
        )


def test_pinned_api_version_matches_installed_sdk_named_release() -> None:
    """An SDK bump to a different named release must fail this test."""
    from stripe._api_version import _ApiVersion

    assert _stripe_named_release(STRIPE_API_VERSION) == _stripe_named_release(
        _ApiVersion.CURRENT
    ), (
        "The installed Stripe SDK moved to a different named release; review the "
        "dahlia payload reads and pin the reviewed version in STRIPE_API_VERSION."
    )


def test_activate_api_key_pins_the_api_version_on_the_sdk() -> None:
    """Every SDK call must run at the version this module is written against."""
    stripe_module = SimpleNamespace(api_key="", api_version="")

    StripeClient(stripe_module=stripe_module, api_key=TEST_API_KEY)._activate_api_key()

    assert stripe_module.api_key == TEST_API_KEY
    assert stripe_module.api_version == STRIPE_API_VERSION


def test_stripe_client_refuses_relative_checkout_redirect_urls() -> None:
    """A path-only success or cancel URL never reaches the Stripe SDK."""
    calls: list[dict[str, Any]] = []

    def create(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {"id": "cs_guard", "url": "https://checkout.stripe.test/guard"}

    stripe_module = SimpleNamespace(
        api_key="",
        checkout=SimpleNamespace(Session=SimpleNamespace(create=create)),
    )
    stripe_client = StripeClient(stripe_module=stripe_module, api_key=TEST_API_KEY)

    with pytest.raises(BillingValidationError, match="success_url"):
        stripe_client.create_checkout_session(
            customer_id="cus_guard",
            price_id="price_guard",
            success_url="/billing/purchase/success/",
            cancel_url="https://app.example.com/billing/purchase/cancel",
            session_metadata={"quickscale_user_reference": "auth.user:1"},
            payment_intent_metadata={"quickscale_user_reference": "auth.user:1"},
            client_reference_id="auth.user:1",
        )
    with pytest.raises(BillingValidationError, match="cancel_url"):
        stripe_client.create_checkout_session(
            customer_id="cus_guard",
            price_id="price_guard",
            success_url="https://app.example.com/billing/purchase/success",
            cancel_url="/billing/purchase/cancel/",
            session_metadata={"quickscale_user_reference": "auth.user:1"},
            payment_intent_metadata={"quickscale_user_reference": "auth.user:1"},
            client_reference_id="auth.user:1",
        )

    assert calls == []


def test_stripe_client_refuses_relative_subscription_checkout_urls() -> None:
    """A path-only success or cancel URL never reaches the Stripe SDK."""
    calls: list[dict[str, Any]] = []

    def create(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {"id": "cs_guard", "url": "https://checkout.stripe.test/guard"}

    stripe_module = SimpleNamespace(
        api_key="",
        checkout=SimpleNamespace(Session=SimpleNamespace(create=create)),
    )
    stripe_client = StripeClient(stripe_module=stripe_module, api_key=TEST_API_KEY)

    with pytest.raises(BillingValidationError, match="success_url"):
        stripe_client.create_subscription_checkout_session(
            customer_id="cus_guard",
            price_id="price_guard",
            success_url="/billing/subscription/success/",
            cancel_url="https://app.example.com/billing/subscription/cancel",
            session_metadata={"quickscale_user_reference": "auth.user:1"},
            subscription_metadata={"quickscale_user_reference": "auth.user:1"},
            client_reference_id="auth.user:1",
        )
    with pytest.raises(BillingValidationError, match="cancel_url"):
        stripe_client.create_subscription_checkout_session(
            customer_id="cus_guard",
            price_id="price_guard",
            success_url="https://app.example.com/billing/subscription/success",
            cancel_url="/billing/subscription/cancel/",
            session_metadata={"quickscale_user_reference": "auth.user:1"},
            subscription_metadata={"quickscale_user_reference": "auth.user:1"},
            client_reference_id="auth.user:1",
        )

    assert calls == []


def test_stripe_client_refuses_relative_billing_portal_return_url() -> None:
    """A path-only portal return URL never reaches the Stripe SDK."""
    calls: list[dict[str, Any]] = []

    def create(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {"id": "bps_guard", "url": "https://billing.stripe.test/guard"}

    stripe_module = SimpleNamespace(
        api_key="",
        billing_portal=SimpleNamespace(Session=SimpleNamespace(create=create)),
    )
    stripe_client = StripeClient(stripe_module=stripe_module, api_key=TEST_API_KEY)

    with pytest.raises(BillingValidationError, match="return_url"):
        stripe_client.create_billing_portal_session(
            customer_id="cus_guard",
            return_url="/billing/portal/return/",
        )

    assert calls == []


@pytest.mark.parametrize(
    "bad_url",
    [
        "/billing/purchase/success/",
        "//app.example.com/billing/purchase/success/",
        "https://:443/billing/purchase/success/",
        "https://[::1",
    ],
    ids=["path", "scheme-relative", "port-only-authority", "malformed-host"],
)
def test_stripe_client_refuses_urls_without_a_scheme_and_host(bad_url: str) -> None:
    """Scheme-relative, host-less, and malformed URLs are refused locally."""
    calls: list[dict[str, Any]] = []

    def create(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {"id": "cs_guard", "url": "https://checkout.stripe.test/guard"}

    stripe_module = SimpleNamespace(
        api_key="",
        checkout=SimpleNamespace(Session=SimpleNamespace(create=create)),
    )
    stripe_client = StripeClient(stripe_module=stripe_module, api_key=TEST_API_KEY)

    with pytest.raises(BillingValidationError, match="success_url"):
        stripe_client.create_checkout_session(
            customer_id="cus_guard",
            price_id="price_guard",
            success_url=bad_url,
            cancel_url="https://app.example.com/billing/purchase/cancel",
            session_metadata={"quickscale_user_reference": "auth.user:1"},
            payment_intent_metadata={"quickscale_user_reference": "auth.user:1"},
            client_reference_id="auth.user:1",
        )

    assert calls == []


def _checkout_session_list_client(
    page: dict[str, Any],
) -> tuple[StripeClient, list[dict[str, Any]]]:
    """Return a StripeClient whose Session.list answers the given page."""
    list_calls: list[dict[str, Any]] = []

    def list_sessions(**kwargs: Any) -> dict[str, Any]:
        list_calls.append(kwargs)
        return page

    stripe_module = SimpleNamespace(
        api_key="",
        checkout=SimpleNamespace(Session=SimpleNamespace(list=list_sessions)),
    )
    return StripeClient(stripe_module=stripe_module, api_key=TEST_API_KEY), list_calls


def test_stripe_client_finds_a_checkout_session_by_reservation_reference() -> None:
    """The client lists the customer's sessions and matches on the marker."""
    stripe_client, list_calls = _checkout_session_list_client(
        {
            "data": [
                {
                    "id": "cs_other",
                    "metadata": {
                        "quickscale_purchase_checkout_reference": (
                            "quickscale_billing.purchasecheckout:1"
                        )
                    },
                },
                {
                    "id": "cs_match",
                    "metadata": {
                        "quickscale_purchase_checkout_reference": (
                            "quickscale_billing.purchasecheckout:2"
                        )
                    },
                },
            ]
        }
    )

    session = stripe_client.find_checkout_session_by_reference(
        customer_id="cus_lookup",
        metadata_key="quickscale_purchase_checkout_reference",
        reference="quickscale_billing.purchasecheckout:2",
    )

    assert session is not None
    assert session["id"] == "cs_match"
    assert list_calls == [{"customer": "cus_lookup", "limit": 100}]


def test_stripe_client_reports_no_checkout_session_for_a_missing_reference() -> None:
    """A customer with no matching session resolves to ``None``, not an error."""
    stripe_client, _list_calls = _checkout_session_list_client(
        {
            "data": [
                {
                    "id": "cs_other",
                    "metadata": {
                        "quickscale_purchase_checkout_reference": (
                            "quickscale_billing.purchasecheckout:1"
                        )
                    },
                }
            ]
        }
    )

    session = stripe_client.find_checkout_session_by_reference(
        customer_id="cus_lookup",
        metadata_key="quickscale_purchase_checkout_reference",
        reference="quickscale_billing.purchasecheckout:9",
    )

    assert session is None


def test_stripe_client_refuses_ambiguous_checkout_session_references() -> None:
    """Two sessions for one reservation reference fail closed."""
    reference = "quickscale_billing.purchasecheckout:2"
    stripe_client, _list_calls = _checkout_session_list_client(
        {
            "data": [
                {
                    "id": "cs_first",
                    "metadata": {"quickscale_purchase_checkout_reference": reference},
                },
                {
                    "id": "cs_second",
                    "metadata": {"quickscale_purchase_checkout_reference": reference},
                },
            ]
        }
    )

    with pytest.raises(BillingError, match="multiple checkout sessions"):
        stripe_client.find_checkout_session_by_reference(
            customer_id="cus_lookup",
            metadata_key="quickscale_purchase_checkout_reference",
            reference=reference,
        )


def test_stripe_client_refuses_a_missing_checkout_session_list_support() -> None:
    """A stub SDK without Session.list fails closed instead of guessing."""
    stripe_module = SimpleNamespace(
        api_key="",
        checkout=SimpleNamespace(Session=SimpleNamespace()),
    )
    stripe_client = StripeClient(stripe_module=stripe_module, api_key=TEST_API_KEY)

    with pytest.raises(BillingConfigurationError, match="list support"):
        stripe_client.find_checkout_session_by_reference(
            customer_id="cus_lookup",
            metadata_key="quickscale_purchase_checkout_reference",
            reference="quickscale_billing.purchasecheckout:2",
        )


@pytest.mark.django_db
def test_handle_stripe_event_rejects_a_different_named_release(
    user,
    organization,
    org_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A basil event is refused as configuration drift and creates no credit."""
    plan = _create_plan(price_id="price_contract_basil")
    Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_subscription_id="sub_contract_basil",
        stripe_customer_id="cus_contract_basil",
        status=Subscription.Status.ACTIVE,
    )
    monkeypatch.setattr(settings, "QUICKSCALE_BILLING_WEBHOOK_SECRET", WEBHOOK_SECRET)
    payload = invoice_event(
        event_id="evt_contract_basil",
        event_type="invoice.paid",
        invoice_id="in_contract_basil",
        customer_id="cus_contract_basil",
        price_id=plan.stripe_price_id,
        subscription_id="sub_contract_basil",
        api_version="2025-03-31.basil",
    )
    body, signature = _signed_body(payload)

    with pytest.raises(BillingConfigurationError, match=STRIPE_API_VERSION):
        handle_stripe_event(
            body=body,
            signature=signature,
            stripe_client=_real_stripe_client(),
        )

    assert CreditTransaction.all_objects.count() == 0
    assert WebhookEvent.objects.count() == 0


@pytest.mark.django_db
def test_dahlia_invoice_paid_grants_exactly_one_plan_credit(
    user,
    organization,
    org_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dahlia subscription_cycle invoice credits the plan exactly once."""
    plan = _create_plan(price_id="price_contract_cycle")
    Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_subscription_id="sub_contract_cycle",
        stripe_customer_id="cus_contract_cycle",
        status=Subscription.Status.ACTIVE,
    )
    monkeypatch.setattr(settings, "QUICKSCALE_BILLING_WEBHOOK_SECRET", WEBHOOK_SECRET)
    payload = invoice_event(
        event_id="evt_contract_cycle",
        event_type="invoice.paid",
        invoice_id="in_contract_cycle",
        customer_id="cus_contract_cycle",
        price_id=plan.stripe_price_id,
        subscription_id="sub_contract_cycle",
        billing_reason="subscription_cycle",
    )
    body, signature = _signed_body(payload)

    result = handle_stripe_event(
        body=body,
        signature=signature,
        stripe_client=_real_stripe_client(),
    )

    transactions = list(CreditTransaction.all_objects.filter(organization=organization))
    assert result.status == "processed"
    assert len(transactions) == 1
    assert transactions[0].amount == plan.credits_per_period
    assert transactions[0].stripe_reference_data["stripe_subscription_id"] == (
        "sub_contract_cycle"
    )
    assert (
        CreditBalance.all_objects.get(organization=organization).balance
        == plan.credits_per_period
    )


@pytest.mark.django_db
def test_dahlia_subscription_updated_keeps_item_derived_period_bounds(
    user,
    organization,
    org_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Item bounds are applied, and a bound-less payload never blanks them."""
    plan = _create_plan(price_id="price_contract_bounds")
    subscription = Subscription.all_objects.create(
        user=user,
        organization=organization,
        plan=plan,
        stripe_subscription_id="sub_contract_bounds",
        stripe_customer_id="cus_contract_bounds",
        status=Subscription.Status.ACTIVE,
        current_period_start=_payload._stripe_timestamp_to_datetime(1_600_000_000),
        current_period_end=_payload._stripe_timestamp_to_datetime(1_600_086_400),
    )
    monkeypatch.setattr(settings, "QUICKSCALE_BILLING_WEBHOOK_SECRET", WEBHOOK_SECRET)

    updated_event = subscription_event(
        event_id="evt_contract_bounds",
        event_type="customer.subscription.updated",
        subscription_id="sub_contract_bounds",
        customer_id="cus_contract_bounds",
        price_id=plan.stripe_price_id,
        status="active",
        user_reference=_user_reference(user),
    )
    updated_event["data"]["object"]["metadata"]["quickscale_org_reference"] = (
        _organization_reference(organization)
    )
    body, signature = _signed_body(updated_event)
    stripe_client = _real_stripe_client()
    provider_payload: dict[str, Any] = {"object": updated_event["data"]["object"]}

    def retrieve_subscription(*, stripe_subscription_id: str) -> dict[str, Any]:
        del stripe_subscription_id
        return provider_payload["object"]

    monkeypatch.setattr(stripe_client, "retrieve_subscription", retrieve_subscription)

    result = handle_stripe_event(
        body=body,
        signature=signature,
        stripe_client=stripe_client,
    )
    subscription.refresh_from_db()

    assert result.status == "processed"
    assert subscription.current_period_start == (
        _payload._stripe_timestamp_to_datetime(1_700_000_000)
    )
    assert subscription.current_period_end == (
        _payload._stripe_timestamp_to_datetime(1_700_086_400)
    )

    bound_less_event = subscription_event(
        event_id="evt_contract_bounds_absent",
        event_type="customer.subscription.updated",
        subscription_id="sub_contract_bounds",
        customer_id="cus_contract_bounds",
        price_id=plan.stripe_price_id,
        status="active",
        user_reference=_user_reference(user),
    )
    bound_less_event["data"]["object"]["items"] = {"data": []}
    bound_less_event["data"]["object"]["metadata"]["quickscale_org_reference"] = (
        _organization_reference(organization)
    )
    body, signature = _signed_body(bound_less_event)
    provider_payload["object"] = bound_less_event["data"]["object"]

    handle_stripe_event(
        body=body,
        signature=signature,
        stripe_client=stripe_client,
    )
    subscription.refresh_from_db()

    assert subscription.current_period_start == (
        _payload._stripe_timestamp_to_datetime(1_700_000_000)
    )
    assert subscription.current_period_end == (
        _payload._stripe_timestamp_to_datetime(1_700_086_400)
    )


def test_manifest_adoption_step_reads_the_core_stripe_api_version() -> None:
    """The shipped manifest references the one constant; reading it resolves it."""
    manifest_path = REPO_ROOT / "quickscale_modules" / "billing" / "module.yml"
    raw_text = manifest_path.read_text()
    manifest = load_manifest_from_path(manifest_path)

    assert "{stripe_api_version}" in raw_text, (
        "the manifest must reference the core token, not a copy"
    )
    assert STRIPE_API_VERSION not in raw_text, (
        "the manifest must not hand-copy the Stripe API version"
    )
    vintage = manifest.contract_vintage
    assert vintage is not None
    assert any(STRIPE_API_VERSION in step for step in vintage.manual_adoption_steps), (
        "every operator-facing manifest surface must name the required version"
    )


def test_no_product_station_hand_copies_the_stripe_api_version() -> None:
    """The version is read or rendered at every station, never re-authored."""
    stations = (
        REPO_ROOT
        / "quickscale_modules"
        / "billing"
        / "src"
        / "quickscale_modules_billing"
        / "_settings.py",
        REPO_ROOT / "quickscale_modules" / "billing" / "module.yml",
        REPO_ROOT
        / "quickscale_core"
        / "src"
        / "quickscale_core"
        / "data"
        / "manifests"
        / "billing"
        / "module.yml",
        REPO_ROOT
        / "quickscale_cli"
        / "src"
        / "quickscale_cli"
        / "commands"
        / "_finalize.py",
        REPO_ROOT
        / "quickscale_core"
        / "src"
        / "quickscale_core"
        / "generator"
        / "generator.py",
        REPO_ROOT
        / "quickscale_core"
        / "src"
        / "quickscale_core"
        / "generator"
        / "templates"
        / "OPERATIONS.md.j2",
    )

    for path in stations:
        assert STRIPE_API_VERSION not in path.read_text(), (
            f"{path} re-states the Stripe API version instead of reading the "
            "one authored constant"
        )


def test_generated_operations_guidance_renders_the_billing_version_contract() -> None:
    """The managed operations page states the version only for billing projects."""
    import jinja2

    from quickscale_core.generator.operations_page import render_operations_page

    managed_billing = render_operations_page(["billing"])
    managed_default = render_operations_page(["blog", "forms", "social"])

    assert "## Stripe Billing" in managed_billing
    assert STRIPE_API_VERSION in managed_billing
    assert "## Stripe Billing" not in managed_default

    # The user-owned guide links the managed page and states no module value.
    guide_template = jinja2.Template(
        (
            REPO_ROOT
            / "quickscale_core"
            / "src"
            / "quickscale_core"
            / "generator"
            / "templates"
            / "OPERATIONS.md.j2"
        ).read_text()
    )
    context: dict[str, Any] = {
        "project_name": "testproject",
        "package_name": "testproject",
        "runtime_db_role": "testproject_app",
        "runtime_db_role_attributes": ["NOSUPERUSER", "NOBYPASSRLS"],
        "runtime_db_manual_grant_statements": ["GRANT CONNECT ON DATABASE"],
    }

    guide = guide_template.render({**context, "selected_modules": ["billing"]})

    assert "quickscale-operations.md" in guide
    assert STRIPE_API_VERSION not in guide
    assert "## Stripe Billing" not in guide
