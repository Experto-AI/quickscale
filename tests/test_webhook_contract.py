"""Vendor-contract tests for Resend's Svix webhook signature.

The signature vector is the example Svix documents for verifying payloads
(https://docs.svix.com/receiving/verifying-payloads/how-manual), which is the
contract Resend's webhooks follow; the event payload is Resend's documented
``email.delivered`` example.
"""

from __future__ import annotations

from base64 import b64encode
import hashlib
import hmac
import json
import time

import pytest
from django.conf import settings
from django.test import override_settings

from quickscale_modules_notifications.models import (
    NotificationDelivery,
    NotificationDeliveryEvent,
)
from quickscale_modules_notifications.services import (
    NotificationWebhookError,
    NotificationWebhookSignatureError,
    build_webhook_signature_headers,
    ingest_webhook_event,
)

SVIX_DOCUMENTED_SECRET = "whsec_MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw"
SVIX_DOCUMENTED_ID = "msg_p5jXN8AQM9LWM0D4loKWxJek"
SVIX_DOCUMENTED_TIMESTAMP = "1614265330"
SVIX_DOCUMENTED_BODY = b'{"test": 2432232314}'
SVIX_DOCUMENTED_SIGNATURE = (
    "v1,g0hM9SsE+OTPJTGt/tmIKtSyZlE3uFJELVlNIOLJ1OE= "
    "v1,bm9ldHUjKzFob2VudXRob2VodWUzMjRvdWVvdWU3"
)
# The documented header lists the valid signature first; Resend advertises
# every live signature while an endpoint secret rotates.
SVIX_ROTATED_SIGNATURE = (
    "v1,bm9ldHUjKzFob2VudXRob2VodWUzMjRvdWVvdWU3 "
    "v1,g0hM9SsE+OTPJTGt/tmIKtSyZlE3uFJELVlNIOLJ1OE="
)

RESEND_DOCUMENTED_PAYLOAD: dict[str, object] = {
    "type": "email.delivered",
    "created_at": "2026-02-22T23:41:12.126Z",
    "data": {
        "created_at": "2026-02-22T23:41:11.894Z",
        "email_id": "56761188-7520-42d8-8898-ff6fc54ce618",
        "message_id": "<111-222-333@email.example.com>",
        "from": "Acme <onboarding@resend.dev>",
        "to": ["delivered@resend.dev"],
        "subject": "Sending this example",
        "tags": {"category": "confirm_email"},
    },
}


def _empty_key_signature(body: bytes, *, svix_id: str, timestamp: str) -> str:
    """Return the signature anyone can compute with an empty HMAC key."""
    signed_content = f"{svix_id}.{timestamp}.".encode("utf-8") + body
    digest = hmac.new(b"", signed_content, hashlib.sha256).digest()
    return f"v1,{b64encode(digest).decode('ascii')}"


@pytest.mark.django_db
def test_whsec_prefix_only_secret_rejects_empty_key(monkeypatch) -> None:
    """A secret that decodes to an empty key never authenticates a request."""
    monkeypatch.setattr(
        "quickscale_modules_notifications.services.time.time",
        lambda: float(SVIX_DOCUMENTED_TIMESTAMP),
    )

    with override_settings(QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET="whsec_"):
        with pytest.raises(
            NotificationWebhookSignatureError, match="not a valid Svix signing secret"
        ):
            ingest_webhook_event(
                body=SVIX_DOCUMENTED_BODY,
                svix_id=SVIX_DOCUMENTED_ID,
                svix_timestamp=SVIX_DOCUMENTED_TIMESTAMP,
                svix_signature=_empty_key_signature(
                    SVIX_DOCUMENTED_BODY,
                    svix_id=SVIX_DOCUMENTED_ID,
                    timestamp=SVIX_DOCUMENTED_TIMESTAMP,
                ),
            )


@pytest.mark.django_db
def test_svix_documented_vector_passes_verification(monkeypatch) -> None:
    """Svix's documented payload and signature pass the signature check.

    The documented body carries no Resend event fields, so acceptance is
    proven by the verification stage passing and payload parsing failing.
    """
    monkeypatch.setattr(
        "quickscale_modules_notifications.services.time.time",
        lambda: float(SVIX_DOCUMENTED_TIMESTAMP),
    )

    with override_settings(
        QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET=SVIX_DOCUMENTED_SECRET
    ):
        with pytest.raises(NotificationWebhookError, match="missing type"):
            ingest_webhook_event(
                body=SVIX_DOCUMENTED_BODY,
                svix_id=SVIX_DOCUMENTED_ID,
                svix_timestamp=SVIX_DOCUMENTED_TIMESTAMP,
                svix_signature=SVIX_DOCUMENTED_SIGNATURE,
            )


@pytest.mark.django_db
def test_svix_rotated_vector_passes_verification(monkeypatch) -> None:
    """Any advertised ``v1`` candidate may verify, not just the first."""
    monkeypatch.setattr(
        "quickscale_modules_notifications.services.time.time",
        lambda: float(SVIX_DOCUMENTED_TIMESTAMP),
    )

    with override_settings(
        QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET=SVIX_DOCUMENTED_SECRET
    ):
        with pytest.raises(NotificationWebhookError, match="missing type"):
            ingest_webhook_event(
                body=SVIX_DOCUMENTED_BODY,
                svix_id=SVIX_DOCUMENTED_ID,
                svix_timestamp=SVIX_DOCUMENTED_TIMESTAMP,
                svix_signature=SVIX_ROTATED_SIGNATURE,
            )


@pytest.mark.django_db
def test_svix_documented_vector_rejects_tampered_body(monkeypatch) -> None:
    """A byte outside the documented payload no longer verifies."""
    monkeypatch.setattr(
        "quickscale_modules_notifications.services.time.time",
        lambda: float(SVIX_DOCUMENTED_TIMESTAMP),
    )

    with override_settings(
        QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET=SVIX_DOCUMENTED_SECRET
    ):
        with pytest.raises(NotificationWebhookSignatureError, match="invalid"):
            ingest_webhook_event(
                body=SVIX_DOCUMENTED_BODY + b" ",
                svix_id=SVIX_DOCUMENTED_ID,
                svix_timestamp=SVIX_DOCUMENTED_TIMESTAMP,
                svix_signature=SVIX_DOCUMENTED_SIGNATURE,
            )


@pytest.mark.django_db
def test_svix_documented_vector_rejects_stale_timestamp() -> None:
    """The documented vector is outside the TTL window at the real clock."""
    with override_settings(
        QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET=SVIX_DOCUMENTED_SECRET
    ):
        with pytest.raises(NotificationWebhookSignatureError, match="expired"):
            ingest_webhook_event(
                body=SVIX_DOCUMENTED_BODY,
                svix_id=SVIX_DOCUMENTED_ID,
                svix_timestamp=SVIX_DOCUMENTED_TIMESTAMP,
                svix_signature=SVIX_DOCUMENTED_SIGNATURE,
            )


@pytest.mark.django_db
def test_svix_documented_vector_rejects_non_v1_candidate(monkeypatch) -> None:
    """A candidate outside the ``v1`` scheme earns no verification credit."""
    monkeypatch.setattr(
        "quickscale_modules_notifications.services.time.time",
        lambda: float(SVIX_DOCUMENTED_TIMESTAMP),
    )

    with override_settings(
        QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET=SVIX_DOCUMENTED_SECRET
    ):
        with pytest.raises(NotificationWebhookSignatureError, match="invalid"):
            ingest_webhook_event(
                body=SVIX_DOCUMENTED_BODY,
                svix_id=SVIX_DOCUMENTED_ID,
                svix_timestamp=SVIX_DOCUMENTED_TIMESTAMP,
                svix_signature=SVIX_DOCUMENTED_SIGNATURE.replace("v1,", "v2,", 1),
            )


@pytest.mark.django_db
def test_resend_documented_delivery_event_reconciles(delivery_for_webhook) -> None:
    """Resend's documented ``email.delivered`` event is accepted end to end."""
    delivery_for_webhook.provider_message_id = "56761188-7520-42d8-8898-ff6fc54ce618"
    delivery_for_webhook.recipient_email = "delivered@resend.dev"
    delivery_for_webhook.save(update_fields=["provider_message_id", "recipient_email"])
    body = json.dumps(RESEND_DOCUMENTED_PAYLOAD).encode("utf-8")
    headers = build_webhook_signature_headers(
        body,
        secret=settings.QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET,
        svix_id="msg_resend_delivered_1",
        timestamp=int(time.time()),
    )

    result = ingest_webhook_event(
        body=body,
        svix_id=headers["svix-id"],
        svix_timestamp=headers["svix-timestamp"],
        svix_signature=headers["svix-signature"],
    )

    delivery_for_webhook.refresh_from_db()
    event = NotificationDeliveryEvent.objects.get(delivery=delivery_for_webhook)

    assert result.duplicate is False
    assert delivery_for_webhook.status == NotificationDelivery.Status.DELIVERED
    assert event.provider_event_id == "msg_resend_delivered_1"
    assert event.event_type == "email.delivered"
    assert event.provider_message_id == "56761188-7520-42d8-8898-ff6fc54ce618"
    assert event.occurred_at is not None
