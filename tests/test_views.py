"""Tests for billing webhook views."""

from __future__ import annotations

from typing import Any

import pytest
from django.test import Client
from django.urls import reverse

from quickscale_modules_billing.services import (
    BillingConfigurationError,
    BillingDisabledError,
    BillingWebhookError,
    BillingWebhookSignatureError,
    StripeWebhookResult,
)


def test_webhook_view_passes_raw_body_and_signature_header(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_call: dict[str, Any] = {}

    def fake_handle_stripe_event(*, body: bytes, signature: str) -> StripeWebhookResult:
        captured_call["body"] = body
        captured_call["signature"] = signature
        return StripeWebhookResult(
            duplicate=False,
            event_type="invoice.paid",
            status="processed",
        )

    monkeypatch.setattr(
        "quickscale_modules_billing.views.handle_stripe_event",
        fake_handle_stripe_event,
    )
    body = b'{"id":"evt_view"}'

    response = client.post(
        reverse("quickscale_billing:stripe-webhook"),
        data=body,
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="t=1,v1=view-signature",
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "accepted",
        "duplicate": False,
        "event_type": "invoice.paid",
        "processing_status": "processed",
    }
    assert captured_call == {
        "body": body,
        "signature": "t=1,v1=view-signature",
    }


def test_webhook_view_maps_signature_errors_to_403(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "quickscale_modules_billing.views.handle_stripe_event",
        lambda **kwargs: (_ for _ in ()).throw(
            BillingWebhookSignatureError("Webhook signature is invalid.")
        ),
    )

    response = client.post(
        reverse("quickscale_billing:stripe-webhook"),
        data=b"{}",
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="t=1,v1=invalid",
    )

    assert response.status_code == 403
    assert response.json()["error"] == "Webhook signature is invalid."


def test_webhook_view_maps_disabled_runtime_to_403(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "quickscale_modules_billing.views.handle_stripe_event",
        lambda **kwargs: (_ for _ in ()).throw(
            BillingDisabledError("Billing module is disabled.")
        ),
    )

    response = client.post(
        reverse("quickscale_billing:stripe-webhook"),
        data=b"{}",
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="t=1,v1=disabled",
    )

    assert response.status_code == 403
    assert response.json()["error"] == "Billing module is disabled."


def test_webhook_view_maps_processing_errors_to_400(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "quickscale_modules_billing.views.handle_stripe_event",
        lambda **kwargs: (_ for _ in ()).throw(
            BillingWebhookError("Stripe invoice payload is missing an id.")
        ),
    )

    response = client.post(
        reverse("quickscale_billing:stripe-webhook"),
        data=b"{}",
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="t=1,v1=broken",
    )

    assert response.status_code == 400
    assert response.json()["error"] == "Stripe invoice payload is missing an id."


def test_webhook_view_maps_configuration_errors_to_500(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "quickscale_modules_billing.views.handle_stripe_event",
        lambda **kwargs: (_ for _ in ()).throw(
            BillingConfigurationError(
                "Stripe webhook secret is not configured in the runtime environment."
            )
        ),
    )

    response = client.post(
        reverse("quickscale_billing:stripe-webhook"),
        data=b"{}",
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="t=1,v1=config",
    )

    assert response.status_code == 500
    assert response.json()["error"] == (
        "Stripe webhook secret is not configured in the runtime environment."
    )
