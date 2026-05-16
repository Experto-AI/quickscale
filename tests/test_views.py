"""Tests for billing checkout and webhook views."""

from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from quickscale_modules_billing.models import CreditBalance, CreditTransaction, Plan
from quickscale_modules_billing.services import (
    BillingConfigurationError,
    BillingDisabledError,
    BillingWebhookError,
    BillingWebhookSignatureError,
    StripeWebhookResult,
)


def _create_one_time_plan(
    *,
    slug: str = "credits-pack",
    price_id: str = "price_credits_pack",
    credits: int = 250,
    price_cents: int = 4900,
) -> Plan:
    return Plan.objects.create(
        name="Credits Pack",
        slug=slug,
        stripe_price_id=price_id,
        credits_per_period=credits,
        price_cents=price_cents,
        currency="usd",
        billing_interval=Plan.BillingInterval.ONE_TIME,
        is_active=True,
    )


def _create_credit_transaction(
    *,
    user: Any,
    amount: int,
    balance_after: int,
    description: str,
) -> CreditTransaction:
    return CreditTransaction.objects.create(
        user=user,
        amount=amount,
        transaction_type=CreditTransaction.TransactionType.PURCHASE,
        description=description,
        balance_after=balance_after,
    )


def test_checkout_view_returns_json_401_for_anonymous_requests() -> None:
    csrf_client = Client(enforce_csrf_checks=True)

    response = csrf_client.post(
        reverse("quickscale_billing:purchase-checkout"),
        data=json.dumps({"plan_slug": "credits-pack"}),
        content_type="application/json",
    )

    assert response.status_code == 401
    assert response.json() == {"error": "Authentication required"}


@pytest.mark.parametrize(
    "route_name",
    ["credit-balance", "credit-transactions"],
)
def test_billing_read_views_return_json_401_for_anonymous_requests(
    client: Client,
    route_name: str,
) -> None:
    response = client.get(reverse(f"quickscale_billing:{route_name}"))

    assert response.status_code == 401
    assert response.json() == {"error": "Authentication required"}


def test_checkout_view_missing_csrf_returns_403(user) -> None:
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(user)

    response = csrf_client.post(
        reverse("quickscale_billing:purchase-checkout"),
        data=json.dumps({"plan_slug": "credits-pack"}),
        content_type="application/json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_credit_balance_view_creates_zero_balance_on_first_use(
    client: Client,
    user,
) -> None:
    client.force_login(user)

    response = client.get(reverse("quickscale_billing:credit-balance"))

    assert response.status_code == 200
    assert response.json()["balance"] == 0
    assert response.json()["updated_at"] is not None
    balance = CreditBalance.objects.get(user=user)
    assert balance.balance == 0


@pytest.mark.django_db
def test_credit_balance_view_returns_only_authenticated_users_balance(
    client: Client,
    user,
    django_user_model,
) -> None:
    other_user = django_user_model.objects.create_user(
        username="other-balance-user",
        email="other-balance@example.com",
        password="password123",
    )
    CreditBalance.objects.create(user=user, balance=125)
    CreditBalance.objects.create(user=other_user, balance=900)
    client.force_login(user)

    response = client.get(reverse("quickscale_billing:credit-balance"))

    assert response.status_code == 200
    assert response.json()["balance"] == 125


@pytest.mark.django_db
def test_checkout_view_rejects_caller_supplied_redirect_fields(
    client: Client,
    user,
) -> None:
    plan = _create_one_time_plan(slug="credits-redirect-view")
    client.force_login(user)

    response = client.post(
        reverse("quickscale_billing:purchase-checkout"),
        data=json.dumps(
            {
                "plan_slug": plan.slug,
                "success_url": "https://app.example.com/custom/success",
                "cancel_url": "https://app.example.com/custom/cancel",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json() == {
        "errors": {
            "cancel_url": ["This field is not allowed."],
            "success_url": ["This field is not allowed."],
        }
    }


@pytest.mark.django_db
def test_credit_transactions_view_returns_only_authenticated_users_transactions(
    client: Client,
    user,
    django_user_model,
) -> None:
    other_user = django_user_model.objects.create_user(
        username="other-transactions-user",
        email="other-transactions@example.com",
        password="password123",
    )
    user_transaction = _create_credit_transaction(
        user=user,
        amount=125,
        balance_after=125,
        description="Current user purchase",
    )
    _create_credit_transaction(
        user=other_user,
        amount=900,
        balance_after=900,
        description="Other user purchase",
    )
    client.force_login(user)

    response = client.get(reverse("quickscale_billing:credit-transactions"))

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": user_transaction.pk,
            "amount": 125,
            "transaction_type": CreditTransaction.TransactionType.PURCHASE,
            "description": "Current user purchase",
            "balance_after": 125,
            "created_at": user_transaction.created_at.isoformat().replace(
                "+00:00", "Z"
            ),
        }
    ]


@pytest.mark.django_db
def test_credit_transactions_view_uses_fixed_page_size_without_client_override(
    client: Client,
    user,
) -> None:
    for index in range(30):
        _create_credit_transaction(
            user=user,
            amount=index + 1,
            balance_after=index + 1,
            description=f"Purchase {index + 1}",
        )
    client.force_login(user)

    first_page_response = client.get(
        reverse("quickscale_billing:credit-transactions"),
        {"page_size": 5},
    )
    second_page_response = client.get(
        reverse("quickscale_billing:credit-transactions"),
        {"page": 2, "page_size": 5},
    )

    assert first_page_response.status_code == 200
    assert isinstance(first_page_response.json(), list)
    assert len(first_page_response.json()) == 25
    assert second_page_response.status_code == 200
    assert len(second_page_response.json()) == 5


@pytest.mark.django_db
def test_credit_transactions_view_breaks_same_timestamp_ties_by_descending_id(
    client: Client,
    user,
) -> None:
    created_transactions = [
        _create_credit_transaction(
            user=user,
            amount=index + 1,
            balance_after=index + 1,
            description=f"Purchase {index + 1}",
        )
        for index in range(26)
    ]
    shared_timestamp = timezone.now()
    CreditTransaction.objects.filter(
        pk__in=[transaction_row.pk for transaction_row in created_transactions]
    ).update(created_at=shared_timestamp)
    expected_ids = sorted(
        (transaction_row.pk for transaction_row in created_transactions),
        reverse=True,
    )
    client.force_login(user)

    first_page_response = client.get(reverse("quickscale_billing:credit-transactions"))
    second_page_response = client.get(
        reverse("quickscale_billing:credit-transactions"),
        {"page": 2},
    )

    assert first_page_response.status_code == 200
    assert second_page_response.status_code == 200
    assert [item["id"] for item in first_page_response.json()] == expected_ids[:25]
    assert [item["id"] for item in second_page_response.json()] == expected_ids[25:]


@pytest.mark.django_db
def test_checkout_view_creates_session_with_server_owned_redirect_urls(
    client: Client,
    user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_one_time_plan(slug="credits-checkout-view")
    captured_call: dict[str, Any] = {}

    def fake_create_checkout_session(
        auth_user,
        auth_plan,
        success_url: str,
        cancel_url: str,
    ) -> str:
        captured_call["user"] = auth_user
        captured_call["plan"] = auth_plan
        captured_call["success_url"] = success_url
        captured_call["cancel_url"] = cancel_url
        return "https://checkout.stripe.test/session/view"

    monkeypatch.setattr(
        "quickscale_modules_billing.views.create_checkout_session",
        fake_create_checkout_session,
    )
    client.force_login(user)

    response = client.post(
        reverse("quickscale_billing:purchase-checkout"),
        data=json.dumps({"plan_slug": plan.slug}),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {
        "checkout_url": "https://checkout.stripe.test/session/view"
    }
    assert captured_call == {
        "user": user,
        "plan": plan,
        "success_url": "http://testserver/billing/purchase/success/",
        "cancel_url": "http://testserver/billing/purchase/cancel/",
    }


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


@pytest.mark.parametrize(
    ("route_name", "expected_text", "expected_purchase_status"),
    [
        ("purchase-success", "Purchase complete", "success"),
        ("purchase-cancel", "Purchase canceled", "cancel"),
    ],
)
def test_purchase_return_views_are_public_and_render(
    client: Client,
    route_name: str,
    expected_text: str,
    expected_purchase_status: str,
) -> None:
    response = client.get(reverse(f"quickscale_billing:{route_name}"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert expected_text in content
    assert 'id="billing-purchase-root"' in content
    assert f'data-purchase-status="{expected_purchase_status}"' in content


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
