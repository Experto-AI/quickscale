"""Contract tests for the pinned Stripe SDK integration.

These tests exercise the real ``stripe`` SDK: payloads are built from SDK
objects, webhook bodies are signed locally, and ``StripeClient`` verifies them
through the installed SDK. No network access is required.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from types import SimpleNamespace
import time
from typing import Any

import pytest
from django.conf import settings
import stripe

from quickscale_modules_billing import services as billing_services
from quickscale_modules_billing.models import (
    CreditBalance,
    CreditTransaction,
    Plan,
    Subscription,
    WebhookEvent,
)
from quickscale_modules_billing.services import (
    STRIPE_API_VERSION,
    BillingConfigurationError,
    StripeClient,
    _stripe_named_release,
    handle_stripe_event,
)

from tests.stripe_payloads import (
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


def test_normalize_mapping_keeps_real_sdk_object_identity() -> None:
    """A real SDK object must not collapse to an empty mapping."""
    session = stripe.checkout.Session.construct_from({"id": "cs_1"}, TEST_API_KEY)
    event = stripe.Event.construct_from(
        {"id": "evt_1", "type": "invoice.paid"},
        TEST_API_KEY,
    )

    assert billing_services._normalize_mapping(session)["id"] == "cs_1"
    assert billing_services._normalize_mapping(event)["id"] == "evt_1"


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
        current_period_start=billing_services._stripe_timestamp_to_datetime(
            1_600_000_000
        ),
        current_period_end=billing_services._stripe_timestamp_to_datetime(
            1_600_086_400
        ),
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

    result = handle_stripe_event(
        body=body,
        signature=signature,
        stripe_client=_real_stripe_client(),
    )
    subscription.refresh_from_db()

    assert result.status == "processed"
    assert subscription.current_period_start == (
        billing_services._stripe_timestamp_to_datetime(1_700_000_000)
    )
    assert subscription.current_period_end == (
        billing_services._stripe_timestamp_to_datetime(1_700_086_400)
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

    handle_stripe_event(
        body=body,
        signature=signature,
        stripe_client=_real_stripe_client(),
    )
    subscription.refresh_from_db()

    assert subscription.current_period_start == (
        billing_services._stripe_timestamp_to_datetime(1_700_000_000)
    )
    assert subscription.current_period_end == (
        billing_services._stripe_timestamp_to_datetime(1_700_086_400)
    )


def test_operator_guidance_states_the_pinned_stripe_api_version() -> None:
    """Every operator-facing surface names the required endpoint version."""
    guidance_paths = (
        REPO_ROOT / "quickscale_modules" / "billing" / "README.md",
        REPO_ROOT / "quickscale_modules" / "billing" / "module.yml",
        REPO_ROOT
        / "quickscale_core"
        / "src"
        / "quickscale_core"
        / "generator"
        / "templates"
        / "OPERATIONS.md.j2",
        REPO_ROOT
        / "quickscale_cli"
        / "src"
        / "quickscale_cli"
        / "commands"
        / "_finalize.py",
    )

    for path in guidance_paths:
        assert STRIPE_API_VERSION in path.read_text(), (
            f"{path} must state the required Stripe API version"
        )


def test_generated_operations_guidance_renders_the_billing_version_contract() -> None:
    """The generated operations guide states the version only for billing projects."""
    import jinja2

    template = jinja2.Template(
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

    billing_render = template.render({**context, "selected_modules": ["billing"]})
    default_render = template.render({**context, "selected_modules": ["blog"]})

    assert "## Stripe Billing" in billing_render
    assert STRIPE_API_VERSION in billing_render
    assert "## Stripe Billing" not in default_render
