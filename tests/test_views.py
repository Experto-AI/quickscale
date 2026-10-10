"""Tests for notifications webhook views."""

from __future__ import annotations

import json
import time

import pytest
from django.conf import settings
from django.test import Client
from django.test import override_settings
from django.urls import reverse

from quickscale_modules_notifications.models import (
    NotificationDelivery,
    NotificationDeliveryEvent,
)
from quickscale_modules_notifications.services import build_webhook_signature_headers

_WEBHOOK_URL_NAME = "quickscale_notifications:resend_webhook"


def _resend_delivered_payload(*, email_id: str, recipient: str) -> dict[str, object]:
    """Return a Resend-shaped delivery event payload for one delivery."""
    return {
        "type": "email.delivered",
        "created_at": "2026-02-22T23:41:12.126Z",
        "data": {"email_id": email_id, "to": [recipient]},
    }


def _signed_browser_headers(body: bytes, *, svix_id: str) -> dict[str, str]:
    """Return Django test-client header kwargs signed for *body*."""
    headers = build_webhook_signature_headers(
        body,
        secret=settings.QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET,
        svix_id=svix_id,
        timestamp=int(time.time()),
    )
    return {
        "HTTP_SVIX_ID": headers["svix-id"],
        "HTTP_SVIX_TIMESTAMP": headers["svix-timestamp"],
        "HTTP_SVIX_SIGNATURE": headers["svix-signature"],
    }


@pytest.mark.django_db
def test_webhook_view_rejects_unsigned_invalid_json_payload(client: Client) -> None:
    """The signature is verified before the body is parsed."""
    response = client.post(
        reverse(_WEBHOOK_URL_NAME),
        data="{bad-json",
        content_type="application/json",
        HTTP_SVIX_ID="msg_unsigned",
        HTTP_SVIX_TIMESTAMP=str(int(time.time())),
        HTTP_SVIX_SIGNATURE="v1,invalid",
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "webhook_signature_invalid",
            "message": "Webhook signature is invalid.",
        }
    }


@pytest.mark.django_db
def test_webhook_view_rejects_signed_invalid_json_payload(client: Client) -> None:
    body = b"{bad-json"

    response = client.post(
        reverse(_WEBHOOK_URL_NAME),
        data=body,
        content_type="application/json",
        **_signed_browser_headers(body, svix_id="msg_signed_bad_json"),
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "webhook_payload_invalid",
            "message": "Webhook payload is invalid JSON.",
        }
    }


@pytest.mark.django_db
def test_webhook_view_rejects_invalid_recipient_email(client: Client) -> None:
    payload = _resend_delivered_payload(
        email_id="pm-invalid-recipient", recipient="not-an-email"
    )
    body = json.dumps(payload).encode("utf-8")

    response = client.post(
        reverse(_WEBHOOK_URL_NAME),
        data=body,
        content_type="application/json",
        **_signed_browser_headers(body, svix_id="msg_invalid_recipient"),
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "webhook_payload_invalid",
            "message": "Webhook payload recipient is invalid.",
        }
    }


@pytest.mark.django_db
def test_webhook_view_rejects_invalid_signature(
    client: Client,
    delivery_for_webhook,
) -> None:
    payload = _resend_delivered_payload(
        email_id=delivery_for_webhook.provider_message_id,
        recipient=delivery_for_webhook.recipient_email,
    )

    response = client.post(
        reverse(_WEBHOOK_URL_NAME),
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_SVIX_ID="msg_invalid_signature",
        HTTP_SVIX_TIMESTAMP=str(int(time.time())),
        HTTP_SVIX_SIGNATURE="v1,invalid",
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "webhook_signature_invalid",
            "message": "Webhook signature is invalid.",
        }
    }


@pytest.mark.django_db
def test_webhook_view_rejects_non_ascii_signature(
    client: Client,
    delivery_for_webhook,
) -> None:
    payload = _resend_delivered_payload(
        email_id=delivery_for_webhook.provider_message_id,
        recipient=delivery_for_webhook.recipient_email,
    )

    response = client.post(
        reverse(_WEBHOOK_URL_NAME),
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_SVIX_ID="msg_non_ascii_signature",
        HTTP_SVIX_TIMESTAMP=str(int(time.time())),
        HTTP_SVIX_SIGNATURE="v1,inválid",
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "webhook_signature_invalid",
            "message": "Webhook signature is invalid.",
        }
    }


@pytest.mark.django_db
def test_webhook_view_rejects_when_runtime_disabled(
    client: Client,
    delivery_for_webhook,
) -> None:
    payload = _resend_delivered_payload(
        email_id=delivery_for_webhook.provider_message_id,
        recipient=delivery_for_webhook.recipient_email,
    )
    body = json.dumps(payload).encode("utf-8")

    with override_settings(QUICKSCALE_NOTIFICATIONS_ENABLED=False):
        response = client.post(
            reverse(_WEBHOOK_URL_NAME),
            data=body,
            content_type="application/json",
            **_signed_browser_headers(body, svix_id="msg_disabled_view"),
        )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Notifications module is disabled.",
        }
    }
    assert (
        NotificationDeliveryEvent.objects.filter(delivery=delivery_for_webhook).count()
        == 0
    )


@pytest.mark.django_db
def test_webhook_view_accepts_valid_signed_event(
    client: Client,
    delivery_for_webhook,
) -> None:
    payload = _resend_delivered_payload(
        email_id=delivery_for_webhook.provider_message_id,
        recipient=delivery_for_webhook.recipient_email,
    )
    body = json.dumps(payload).encode("utf-8")

    response = client.post(
        reverse(_WEBHOOK_URL_NAME),
        data=body,
        content_type="application/json",
        **_signed_browser_headers(body, svix_id="msg_view_accepted"),
    )

    delivery_for_webhook.refresh_from_db()

    assert response.status_code == 200
    assert response.json() == {"status": "accepted", "duplicate": False}
    assert delivery_for_webhook.status == NotificationDelivery.Status.DELIVERED
    assert (
        NotificationDeliveryEvent.objects.filter(delivery=delivery_for_webhook).count()
        == 1
    )
