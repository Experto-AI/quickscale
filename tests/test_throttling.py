"""Throttling contract tests for the billing module.

The generated settings compose the billing-contributed
``quickscale_billing_checkout`` and ``quickscale_billing_portal`` scopes over
their conservative ``user``/``anon`` defaults.  These tests pin that
contribution and prove a Stripe-calling view throttles past its scope rate
with a 429.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework.throttling import ScopedRateThrottle

import quickscale_modules_billing.views as billing_views
from quickscale_core.module_wiring import ModuleWiringSpec
from quickscale_modules_billing.adapter import _billing_post_hook
from quickscale_modules_billing.views import (
    CancelSubscriptionView,
    CreateBillingPortalSessionView,
    CreateCheckoutSessionView,
    CreateSubscriptionCheckoutView,
)

BILLING_SCOPE_RATES = {
    "quickscale_billing_checkout": "30/hour",
    "quickscale_billing_portal": "30/hour",
}
#: Tight scope rates for the 429 path.  DRF binds the generated settings'
#: ``DEFAULT_THROTTLE_RATES`` onto ``SimpleRateThrottle`` at import time, so a
#: settings override cannot reach it; the test applies both bindings itself.
THROTTLE_RATES = {
    "quickscale_billing_checkout": "2/hour",
    "quickscale_billing_portal": "2/hour",
}


def test_billing_wiring_contributes_tighter_throttle_scopes() -> None:
    """The billing wiring spec ships both Stripe-calling throttle scopes."""
    spec = _billing_post_hook(
        ModuleWiringSpec(
            settings={
                "QUICKSCALE_BILLING_ENABLED": True,
                "QUICKSCALE_BILLING_API_RATE_LIMIT": "30/hour",
            }
        ),
        {},
    )

    rest_framework = spec.settings["REST_FRAMEWORK"]
    assert rest_framework["DEFAULT_THROTTLE_RATES"] == BILLING_SCOPE_RATES


def test_billing_wiring_carries_the_configured_rate() -> None:
    """Both scopes take their rate from the module's api_rate_limit option."""
    spec = _billing_post_hook(
        ModuleWiringSpec(
            settings={
                "QUICKSCALE_BILLING_ENABLED": True,
                "QUICKSCALE_BILLING_API_RATE_LIMIT": " 7/hour ",
            }
        ),
        {},
    )

    rest_framework = spec.settings["REST_FRAMEWORK"]
    assert rest_framework["DEFAULT_THROTTLE_RATES"] == {
        "quickscale_billing_checkout": "7/hour",
        "quickscale_billing_portal": "7/hour",
    }


def test_stripe_calling_views_declare_throttle_scopes() -> None:
    """Every Stripe-calling view carries an explicit throttle scope."""
    assert CreateCheckoutSessionView.throttle_scope == "quickscale_billing_checkout"
    assert (
        CreateSubscriptionCheckoutView.throttle_scope == "quickscale_billing_checkout"
    )
    assert CreateBillingPortalSessionView.throttle_scope == "quickscale_billing_portal"
    assert CancelSubscriptionView.throttle_scope == "quickscale_billing_portal"


@pytest.fixture
def mock_org_resolution(monkeypatch, organization):
    """Resolve the billing organization without middleware.

    Mirrors the fixture the billing view tests use so the request reaches the
    serializer instead of stopping at the missing organization selection.
    """
    monkeypatch.setattr(
        billing_views,
        "_resolve_request_organization",
        lambda request, require_owner=False: (organization, False),
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("url_name", "view_class"),
    [
        ("quickscale_billing:purchase-checkout", CreateCheckoutSessionView),
        ("quickscale_billing:billing-portal-session", CreateBillingPortalSessionView),
    ],
)
def test_billing_views_return_429_past_their_scope_rate(
    client,
    mock_org_resolution,
    url_name: str,
    view_class: type,
    user,
) -> None:
    """Posting past the configured scope rate returns 429."""
    cache.clear()
    client.force_login(user)
    url = reverse(url_name)
    payload = json.dumps({"plan_slug": "not-a-plan"})

    # The generated settings install ScopedRateThrottle as the default DRF
    # throttle class and ship the scope rates; DRF binds both at import time,
    # so this test applies the same bindings to the view and the throttle.
    with (
        override_settings(REST_FRAMEWORK={"DEFAULT_THROTTLE_RATES": THROTTLE_RATES}),
        patch.object(view_class, "throttle_classes", [ScopedRateThrottle]),
        patch.object(ScopedRateThrottle, "THROTTLE_RATES", THROTTLE_RATES),
    ):
        responses = [
            client.post(url, data=payload, content_type="application/json")
            for _ in range(3)
        ]

    assert [response.status_code for response in responses[:2]] == [400, 400]
    assert responses[2].status_code == 429


@pytest.mark.django_db
def test_billing_checkout_refuses_the_thirty_first_request_in_an_hour(
    client,
    mock_org_resolution,
    user,
) -> None:
    """SA207: once SA201's contract is adopted, the 31st checkout is 429.

    The scope rate is the real ``30/hour`` the billing wiring contributes, so
    the first thirty requests reach the serializer (400 for an unknown plan)
    and the thirty-first is refused by the adopted throttle contract.
    """
    cache.clear()
    client.force_login(user)
    url = reverse("quickscale_billing:purchase-checkout")
    payload = json.dumps({"plan_slug": "not-a-plan"})

    with (
        override_settings(
            REST_FRAMEWORK={"DEFAULT_THROTTLE_RATES": BILLING_SCOPE_RATES}
        ),
        patch.object(
            CreateCheckoutSessionView, "throttle_classes", [ScopedRateThrottle]
        ),
        patch.object(ScopedRateThrottle, "THROTTLE_RATES", BILLING_SCOPE_RATES),
    ):
        responses = [
            client.post(url, data=payload, content_type="application/json")
            for _ in range(31)
        ]

    assert [response.status_code for response in responses[:30]] == [400] * 30
    assert responses[30].status_code == 429
