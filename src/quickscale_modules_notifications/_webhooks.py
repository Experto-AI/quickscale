"""Provider webhook verification and ingestion for the notifications module.

The HTTP view passes the raw body and signature headers to
``services.ingest_webhook_event`` (Module Conventions rule 26); this module
owns the signing contract, payload parsing, idempotent event recording, and
delivery reconciliation it delegates to (rule 28).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import hmac
import json
import time
from typing import Any

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from quickscale_modules_notifications._delivery import _refresh_message_status
from quickscale_modules_notifications.exceptions import NotificationWebhookError
from quickscale_modules_notifications.models import (
    NotificationDelivery,
    NotificationDeliveryEvent,
)

_EVENT_STATUS_MAP = {
    "sent": NotificationDelivery.Status.SENT,
    "email.sent": NotificationDelivery.Status.SENT,
    "delivered": NotificationDelivery.Status.DELIVERED,
    "email.delivered": NotificationDelivery.Status.DELIVERED,
    "delivery.delivered": NotificationDelivery.Status.DELIVERED,
    "failed": NotificationDelivery.Status.FAILED,
    "delivery.failed": NotificationDelivery.Status.FAILED,
    "rejected": NotificationDelivery.Status.FAILED,
    "bounced": NotificationDelivery.Status.BOUNCED,
    "email.bounced": NotificationDelivery.Status.BOUNCED,
    "complained": NotificationDelivery.Status.COMPLAINED,
    "email.complained": NotificationDelivery.Status.COMPLAINED,
}


@dataclass(frozen=True)
class WebhookIngestionResult:
    """Result returned by webhook ingestion."""

    duplicate: bool
    delivery_id: int
    status: str


@dataclass(frozen=True)
class _WebhookEventFields:
    """Validated provider fields extracted from one webhook payload."""

    event_type: str
    provider_event_id: str
    provider_message_id: str
    recipient_email: str


def build_webhook_signature_headers(
    body: bytes,
    *,
    secret: str,
    timestamp: int | None = None,
) -> dict[str, str]:
    """Build signed webhook headers using the module's shared-secret HMAC contract."""
    resolved_timestamp = timestamp or int(time.time())
    payload = f"{resolved_timestamp}.".encode("utf-8") + body
    digest = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return {
        "X-QuickScale-Notifications-Timestamp": str(resolved_timestamp),
        "X-QuickScale-Notifications-Signature": f"sha256={digest}",
    }


def _parse_webhook_payload(body: bytes) -> dict[str, Any]:
    """Parse a signature-verified webhook body into a JSON object.

    A body that is not UTF-8 JSON, or not a JSON object, is a payload error:
    the rule 9 handler answers it as ``webhook_payload_invalid``.
    """
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NotificationWebhookError("Webhook payload is invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise NotificationWebhookError("Webhook payload must be a JSON object.")
    return payload


def _first_payload_string(payload: Mapping[str, Any], keys: Sequence[str]) -> str:
    """Return the first truthy payload value under *keys*, stripped."""
    for key in keys:
        raw_value = payload.get(key)
        if raw_value:
            return str(raw_value).strip()
    return ""


def _extract_webhook_event_fields(payload: Mapping[str, Any]) -> _WebhookEventFields:
    """Extract and validate the provider fields one signed payload must carry."""
    fields = _WebhookEventFields(
        event_type=_first_payload_string(payload, ("event_type", "type")),
        provider_event_id=_first_payload_string(payload, ("event_id", "id")),
        provider_message_id=_first_payload_string(
            payload, ("provider_message_id", "message_id", "email_id")
        ),
        recipient_email=_first_payload_string(payload, ("recipient", "email")).lower(),
    )
    if not fields.event_type:
        raise NotificationWebhookError("Webhook payload is missing event_type.")
    if not fields.provider_message_id:
        raise NotificationWebhookError(
            "Webhook payload is missing provider_message_id."
        )
    if not fields.recipient_email:
        raise NotificationWebhookError("Webhook payload is missing recipient.")

    try:
        validate_email(fields.recipient_email)
    except ValidationError as exc:
        raise NotificationWebhookError("Webhook payload recipient is invalid.") from exc
    return fields


def _resolve_webhook_delivery(
    fields: _WebhookEventFields,
) -> NotificationDelivery:
    """Return the delivery a verified event refers to, failing loudly when unmatched."""
    delivery = (
        NotificationDelivery.objects.select_related("message")
        .filter(
            provider_message_id=fields.provider_message_id,
            recipient_email__iexact=fields.recipient_email,
        )
        .order_by("-pk")
        .first()
    )
    if delivery is None:
        raise NotificationWebhookError(
            "Webhook payload does not match a known notification delivery."
        )
    return delivery


def _record_delivery_event(
    *,
    delivery: NotificationDelivery,
    fields: _WebhookEventFields,
    normalized_status: str,
    occurred_at: datetime | None,
    idempotency_key: str,
    payload: Mapping[str, Any],
) -> WebhookIngestionResult:
    """Record one provider event idempotently and reconcile its delivery."""
    with transaction.atomic():
        event, created = NotificationDeliveryEvent.objects.get_or_create(
            idempotency_key=idempotency_key,
            defaults={
                "delivery": delivery,
                "provider_event_id": fields.provider_event_id,
                "event_type": fields.event_type,
                "provider_message_id": fields.provider_message_id,
                "status_after": normalized_status,
                "payload_json": dict(payload),
                "occurred_at": occurred_at,
            },
        )
        if not created:
            return WebhookIngestionResult(
                duplicate=True,
                delivery_id=delivery.pk,
                status=delivery.status,
            )

        _apply_delivery_event(
            delivery=delivery,
            event_type=fields.event_type,
            status=normalized_status,
            occurred_at=occurred_at,
        )
        event.status_after = delivery.status
        event.save(update_fields=["status_after"])
        _refresh_message_status(delivery.message)
        return WebhookIngestionResult(
            duplicate=False,
            delivery_id=delivery.pk,
            status=delivery.status,
        )


def _apply_delivery_event(
    *,
    delivery: NotificationDelivery,
    event_type: str,
    status: str,
    occurred_at: datetime | None,
) -> None:
    event_time = occurred_at or timezone.now()
    delivery.status = status
    delivery.last_event_type = event_type
    delivery.last_event_at = event_time
    if (
        status == NotificationDelivery.Status.DELIVERED
        and delivery.delivered_at is None
    ):
        delivery.delivered_at = event_time
    if (
        status
        in {
            NotificationDelivery.Status.FAILED,
            NotificationDelivery.Status.BOUNCED,
            NotificationDelivery.Status.COMPLAINED,
        }
        and delivery.failed_at is None
    ):
        delivery.failed_at = event_time
    delivery.save(
        update_fields=[
            "status",
            "last_event_type",
            "last_event_at",
            "delivered_at",
            "failed_at",
            "updated_at",
        ]
    )


def _build_event_idempotency_key(
    *,
    provider_event_id: str,
    event_type: str,
    provider_message_id: str,
    recipient_email: str,
    payload: Mapping[str, Any],
) -> str:
    if provider_event_id:
        base_value = provider_event_id
    else:
        base_value = json.dumps(
            {
                "event_type": event_type,
                "provider_message_id": provider_message_id,
                "recipient": recipient_email,
                "payload": payload,
            },
            sort_keys=True,
            default=str,
        )
    return hashlib.sha256(base_value.encode("utf-8")).hexdigest()


def _parse_event_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    parsed_value = parse_datetime(str(value))
    if parsed_value is None:
        return None
    if timezone.is_naive(parsed_value):
        return timezone.make_aware(parsed_value, UTC)
    return parsed_value
