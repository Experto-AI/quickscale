"""Tests for notifications webhook views."""

from __future__ import annotations

import json
import os
import time

import pytest
from django.test import Client
from django.test import override_settings
from django.urls import reverse

from quickscale_modules_notifications.models import (
    NotificationDelivery,
    NotificationDeliveryEvent,
)
from quickscale_modules_notifications.services import build_webhook_signature_headers


def test_webhook_view_rejects_invalid_json_payload(client: Client) -> None:
    response = client.post(
        reverse("quickscale_notifications:resend-webhook"),
        data="{bad-json",
        content_type="application/json",
        HTTP_X_QUICKSCALE_NOTIFICATIONS_SIGNATURE="sha256=invalid",
        HTTP_X_QUICKSCALE_NOTIFICATIONS_TIMESTAMP=str(int(time.time())),
    )

    assert response.status_code == 400
    assert response.json()["error"] == "Invalid JSON payload."


@pytest.mark.django_db
def test_webhook_view_rejects_invalid_signature(
    client: Client,
    delivery_for_webhook,
) -> None:
    payload = {
        "id": "evt-invalid",
        "type": "email.delivered",
        "provider_message_id": delivery_for_webhook.provider_message_id,
        "recipient": delivery_for_webhook.recipient_email,
    }

    response = client.post(
        reverse("quickscale_notifications:resend-webhook"),
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_X_QUICKSCALE_NOTIFICATIONS_SIGNATURE="sha256=invalid",
        HTTP_X_QUICKSCALE_NOTIFICATIONS_TIMESTAMP=str(int(time.time())),
    )

    assert response.status_code == 403
    assert response.json()["error"] == "Webhook signature is invalid."


@pytest.mark.django_db
def test_webhook_view_rejects_when_runtime_disabled(
    client: Client,
    delivery_for_webhook,
) -> None:
    payload = {
        "id": "evt-disabled-view",
        "type": "email.delivered",
        "provider_message_id": delivery_for_webhook.provider_message_id,
        "recipient": delivery_for_webhook.recipient_email,
    }
    body = json.dumps(payload).encode("utf-8")
    headers = build_webhook_signature_headers(
        body,
        secret=os.environ["QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET"],
        timestamp=int(time.time()),
    )

    with override_settings(QUICKSCALE_NOTIFICATIONS_ENABLED=False):
        response = client.post(
            reverse("quickscale_notifications:resend-webhook"),
            data=body,
            content_type="application/json",
            HTTP_X_QUICKSCALE_NOTIFICATIONS_SIGNATURE=headers[
                "X-QuickScale-Notifications-Signature"
            ],
            HTTP_X_QUICKSCALE_NOTIFICATIONS_TIMESTAMP=headers[
                "X-QuickScale-Notifications-Timestamp"
            ],
        )

    assert response.status_code == 403
    assert response.json()["error"] == "Notifications module is disabled."
    assert (
        NotificationDeliveryEvent.objects.filter(delivery=delivery_for_webhook).count()
        == 0
    )


@pytest.mark.django_db
def test_webhook_view_accepts_valid_signed_event(
    client: Client,
    delivery_for_webhook,
) -> None:
    payload = {
        "id": "evt-view-accepted",
        "type": "email.delivered",
        "provider_message_id": delivery_for_webhook.provider_message_id,
        "recipient": delivery_for_webhook.recipient_email,
    }
    body = json.dumps(payload).encode("utf-8")
    headers = build_webhook_signature_headers(
        body,
        secret=os.environ["QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET"],
        timestamp=int(time.time()),
    )

    response = client.post(
        reverse("quickscale_notifications:resend-webhook"),
        data=body,
        content_type="application/json",
        HTTP_X_QUICKSCALE_NOTIFICATIONS_SIGNATURE=headers[
            "X-QuickScale-Notifications-Signature"
        ],
        HTTP_X_QUICKSCALE_NOTIFICATIONS_TIMESTAMP=headers[
            "X-QuickScale-Notifications-Timestamp"
        ],
    )

    delivery_for_webhook.refresh_from_db()

    assert response.status_code == 200
    assert response.json() == {
        "status": "accepted",
        "duplicate": False,
        "delivery_status": NotificationDelivery.STATUS_DELIVERED,
    }
    assert (
        NotificationDeliveryEvent.objects.filter(delivery=delivery_for_webhook).count()
        == 1
    )
