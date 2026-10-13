"""Provider webhook verification and ingestion for the notifications module.

The HTTP view passes the raw body and signature headers to
``services.ingest_webhook_event`` (Module Conventions rule 26); this module
owns the signing contract, payload parsing, idempotent event recording, and
delivery reconciliation it delegates to (rule 28).
"""

from __future__ import annotations

from base64 import b64decode, b64encode
import binascii
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
from quickscale_modules_notifications.exceptions import (
    NotificationWebhookError,
    NotificationWebhookSignatureError,
)
from quickscale_modules_notifications.models import (
    NotificationDelivery,
    NotificationDeliveryEvent,
)

_EVENT_STATUS_MAP = {
    "email.sent": NotificationDelivery.Status.SENT,
    "email.delivered": NotificationDelivery.Status.DELIVERED,
    "email.bounced": NotificationDelivery.Status.BOUNCED,
    "email.complained": NotificationDelivery.Status.COMPLAINED,
    "email.failed": NotificationDelivery.Status.FAILED,
}

#: Svix advertises each candidate signature as ``<version>,<base64 digest>``.
_SVIX_SIGNATURE_VERSION = "v1"
_WH_SEC_PREFIX = "whsec_"

#: Delivery statuses ranked by lifecycle progress and outcome finality.  A
#: webhook event advances a delivery's status only when its target status
#: outranks the recorded one, so a late or retried provider event (Svix may
#: redeliver after a failure) never regresses a delivery that already reached
#: a later state.
_STATUS_RANK: dict[str, int] = {
    NotificationDelivery.Status.QUEUED: 0,
    NotificationDelivery.Status.SENT: 1,
    NotificationDelivery.Status.DELIVERED: 2,
    NotificationDelivery.Status.FAILED: 3,
    NotificationDelivery.Status.BOUNCED: 4,
    NotificationDelivery.Status.COMPLAINED: 5,
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


def _decode_svix_secret(secret: str) -> bytes:
    """Decode the base64 key of a Svix signing secret (with its ``whsec_`` prefix).

    A secret that decodes to an empty key (an incomplete ``whsec_`` value) is
    refused: an empty HMAC key is public, so accepting it would let anyone
    forge webhook events.
    """
    encoded = secret.removeprefix(_WH_SEC_PREFIX)
    try:
        key = b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise NotificationWebhookSignatureError(
            "Webhook secret is not a valid Svix signing secret."
        ) from exc
    if not key:
        raise NotificationWebhookSignatureError(
            "Webhook secret is not a valid Svix signing secret."
        )
    return key


def _build_svix_signature(
    secret: str,
    *,
    svix_id: str,
    timestamp: str | int,
    body: bytes,
) -> str:
    """Return the base64 ``v1`` signature Resend sends over ``{id}.{timestamp}.{body}``."""
    signed_content = f"{svix_id}.{timestamp}.".encode("utf-8") + body
    return b64encode(
        hmac.new(_decode_svix_secret(secret), signed_content, hashlib.sha256).digest()
    ).decode("ascii")


def build_webhook_signature_headers(
    body: bytes,
    *,
    secret: str,
    svix_id: str,
    timestamp: int | None = None,
) -> dict[str, str]:
    """Build the Svix signature headers Resend sends, for tests that sign requests."""
    resolved_timestamp = str(timestamp if timestamp is not None else int(time.time()))
    signature = _build_svix_signature(
        secret,
        svix_id=svix_id,
        timestamp=resolved_timestamp,
        body=body,
    )
    return {
        "svix-id": svix_id,
        "svix-timestamp": resolved_timestamp,
        "svix-signature": f"{_SVIX_SIGNATURE_VERSION},{signature}",
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


def _first_recipient_email(data: Mapping[str, Any]) -> str:
    """Return Resend's first ``data.to`` recipient address, lowercased."""
    recipients = data.get("to")
    entries = recipients if isinstance(recipients, (list, tuple)) else (recipients,)
    for entry in entries:
        if entry:
            return str(entry).strip().lower()
    return ""


def _extract_webhook_event_fields(
    payload: Mapping[str, Any],
    *,
    provider_event_id: str,
) -> _WebhookEventFields:
    """Extract and validate the Resend fields one signed payload must carry."""
    data_value = payload.get("data")
    data: Mapping[str, Any] = data_value if isinstance(data_value, Mapping) else {}
    fields = _WebhookEventFields(
        event_type=_first_payload_string(payload, ("type",)),
        provider_event_id=provider_event_id.strip(),
        provider_message_id=_first_payload_string(data, ("email_id",)),
        recipient_email=_first_recipient_email(data),
    )
    if not fields.event_type:
        raise NotificationWebhookError("Webhook payload is missing type.")
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
    """Record one provider event idempotently and reconcile its delivery.

    The delivery row is re-read under ``select_for_update`` inside the
    transaction: its recorded status is the one the event is reconciled
    against, so concurrent or redelivered events apply in a serialized order.
    """
    with transaction.atomic():
        locked_delivery = NotificationDelivery.objects.select_for_update().get(
            pk=delivery.pk
        )
        event, created = NotificationDeliveryEvent.objects.get_or_create(
            idempotency_key=idempotency_key,
            defaults={
                "delivery": locked_delivery,
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
                delivery_id=locked_delivery.pk,
                status=locked_delivery.status,
            )

        _apply_delivery_event(
            delivery=locked_delivery,
            event_type=fields.event_type,
            status=normalized_status,
            occurred_at=occurred_at,
        )
        event.status_after = locked_delivery.status
        event.save(update_fields=["status_after"])
        _refresh_message_status(locked_delivery.message)
        return WebhookIngestionResult(
            duplicate=False,
            delivery_id=locked_delivery.pk,
            status=locked_delivery.status,
        )


def _apply_delivery_event(
    *,
    delivery: NotificationDelivery,
    event_type: str,
    status: str,
    occurred_at: datetime | None,
) -> None:
    """Apply one event to *delivery*, advancing its status only forward.

    ``delivery`` must be the row locked by the caller's
    ``select_for_update``.  An event whose target status does not outrank the
    recorded one is ignored here — the event row itself still records the
    receipt — so an out-of-order ``email.sent`` never regresses a delivered
    or bounced delivery.
    """
    if _STATUS_RANK.get(status, -1) <= _STATUS_RANK.get(delivery.status, -1):
        return
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
