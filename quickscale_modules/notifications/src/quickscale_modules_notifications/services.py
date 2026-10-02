"""Runtime notifications services for the QuickScale notifications module.

The implementation lives in private sibling modules grouped by concern
(``_settings``, ``_templates``, ``_sanitization``, ``_delivery``,
``_webhooks``); this module owns the public service surface, the delivery
dispatch and webhook entry points, and re-exports every name that previously
lived here (Module Conventions rule 28).  Existing
``quickscale_modules_notifications.services`` imports, the public ``__all__``,
and the retained delivery and webhook patch seams keep working unchanged;
helpers called from inside the private modules resolve there, not through
this facade.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hmac
import time
from typing import Any

from django.db import transaction

from quickscale_modules_notifications._delivery import (
    DeliveryMailer as DeliveryMailer,
    _bounded_subject as _bounded_subject,
    _dispatch_single_delivery as _dispatch_single_delivery,
    _extract_provider_message_id as _extract_provider_message_id,
    _mark_delivery_failed as _mark_delivery_failed,
    _mark_delivery_sent as _mark_delivery_sent,
    _normalize_recipients as _normalize_recipients,
    _refresh_message_status as _refresh_message_status,
    _send_email_message as _send_email_message,
    _validate_dispatch_settings as _validate_dispatch_settings,
)
from quickscale_modules_notifications._sanitization import (
    _ALLOWED_METADATA_KEYS as _ALLOWED_METADATA_KEYS,
    _DEFAULT_ALLOWED_TAGS as _DEFAULT_ALLOWED_TAGS,
    _DEFAULT_DEFAULT_TAGS as _DEFAULT_DEFAULT_TAGS,
    _normalize_metadata_key as _normalize_metadata_key,
    _normalize_tag as _normalize_tag,
    _normalize_tag_sequence as _normalize_tag_sequence,
    _sanitize_provider_visible_value as _sanitize_provider_visible_value,
    sanitize_provider_metadata as sanitize_provider_metadata,
    sanitize_provider_tags as sanitize_provider_tags,
)
from quickscale_modules_notifications._settings import (
    NotificationSettingsSnapshot as NotificationSettingsSnapshot,
    _ensure_notifications_enabled as _ensure_notifications_enabled,
    _LIVE_RESEND_BACKEND as _LIVE_RESEND_BACKEND,
    _PLACEHOLDER_SENDER_EMAIL as _PLACEHOLDER_SENDER_EMAIL,
    ensure_default_settings as ensure_default_settings,
    is_enabled as is_enabled,
    load_settings_snapshot as load_settings_snapshot,
)
from quickscale_modules_notifications._templates import (
    NotificationTemplateDefinition as NotificationTemplateDefinition,
    RenderedNotification as RenderedNotification,
    _normalize_context as _normalize_context,
    _TEMPLATE_REGISTRY as _TEMPLATE_REGISTRY,
    render_notification as render_notification,
)
from quickscale_modules_notifications._webhooks import (
    WebhookIngestionResult as WebhookIngestionResult,
    _apply_delivery_event as _apply_delivery_event,
    _build_event_idempotency_key as _build_event_idempotency_key,
    _EVENT_STATUS_MAP as _EVENT_STATUS_MAP,
    _extract_webhook_event_fields as _extract_webhook_event_fields,
    _parse_event_datetime as _parse_event_datetime,
    _parse_webhook_payload as _parse_webhook_payload,
    _record_delivery_event as _record_delivery_event,
    _resolve_webhook_delivery as _resolve_webhook_delivery,
    build_webhook_signature_headers as build_webhook_signature_headers,
)
from quickscale_modules_notifications.exceptions import (
    NotificationConfigurationError as NotificationConfigurationError,
    NotificationDisabledError as NotificationDisabledError,
    NotificationError as NotificationError,
    NotificationTemplateError as NotificationTemplateError,
    NotificationValidationError as NotificationValidationError,
    NotificationWebhookError as NotificationWebhookError,
    NotificationWebhookSignatureError as NotificationWebhookSignatureError,
)
from quickscale_modules_notifications.models import (
    NotificationDelivery,
    NotificationMessage,
)

__all__ = [
    "DeliveryMailer",
    "NotificationConfigurationError",
    "NotificationDisabledError",
    "NotificationError",
    "NotificationSettingsSnapshot",
    "NotificationTemplateDefinition",
    "NotificationTemplateError",
    "NotificationValidationError",
    "NotificationWebhookError",
    "NotificationWebhookSignatureError",
    "RenderedNotification",
    "WebhookIngestionResult",
    "build_webhook_signature_headers",
    "dispatch_notification_message",
    "ensure_default_settings",
    "ingest_webhook_event",
    "is_enabled",
    "load_settings_snapshot",
    "render_notification",
    "sanitize_provider_metadata",
    "sanitize_provider_tags",
    "send_notification",
]


def send_notification(
    *,
    template_key: str,
    recipients: Sequence[str],
    context: Mapping[str, Any],
    tags: Sequence[str] | None = None,
    metadata: Mapping[str, Any] | None = None,
    dispatch_after_commit: bool = True,
    mailer: DeliveryMailer | None = None,
) -> NotificationMessage:
    """Create a logical notification message and dispatch it after commit by default."""
    normalized_recipients = _normalize_recipients(recipients)
    if not normalized_recipients:
        raise NotificationValidationError("At least one recipient is required.")

    settings_snapshot = load_settings_snapshot()
    _ensure_notifications_enabled(settings_snapshot)
    normalized_context = _normalize_context(context)
    rendered = render_notification(
        template_key=template_key, context=normalized_context
    )
    provider_tags = sanitize_provider_tags(tags, settings_snapshot=settings_snapshot)
    provider_metadata = sanitize_provider_metadata(
        metadata,
        template_key=template_key,
    )

    with transaction.atomic():
        message = NotificationMessage.objects.create(
            template_key=template_key,
            subject=_bounded_subject(rendered.subject),
            from_email=settings_snapshot.formatted_from_email(),
            reply_to_email=settings_snapshot.reply_to_email,
            rendered_text=rendered.text_body,
            rendered_html=rendered.html_body,
            context_json=normalized_context,
            provider_name=settings_snapshot.provider_name,
            tags_json=provider_tags,
            metadata_json=provider_metadata,
        )
        NotificationDelivery.objects.bulk_create(
            [
                NotificationDelivery(
                    message=message,
                    recipient_email=recipient,
                )
                for recipient in normalized_recipients
            ]
        )
        if dispatch_after_commit:
            transaction.on_commit(
                lambda: dispatch_notification_message(message.pk, mailer=mailer)
            )
        else:
            dispatch_notification_message(message.pk, mailer=mailer)
    return message


def dispatch_notification_message(
    message_id: int,
    *,
    mailer: DeliveryMailer | None = None,
) -> NotificationMessage:
    """Dispatch queued recipient deliveries for a logical notification message."""
    with transaction.atomic():
        try:
            message = NotificationMessage.objects.select_for_update().get(pk=message_id)
        except NotificationMessage.DoesNotExist as exc:
            raise NotificationError(
                f"Notification message {message_id} does not exist."
            ) from exc
        deliveries = list(message.deliveries.select_for_update().order_by("pk"))
        settings_snapshot = load_settings_snapshot()
        _ensure_notifications_enabled(settings_snapshot)

        configuration_issues = _validate_dispatch_settings(settings_snapshot)
        if configuration_issues:
            error_message = "; ".join(configuration_issues)
            for delivery in deliveries:
                if delivery.status != NotificationDelivery.Status.QUEUED:
                    continue
                _mark_delivery_failed(delivery, error_message)
            _refresh_message_status(message)
            return message

        resolved_mailer = mailer or _send_email_message
        for delivery in deliveries:
            if delivery.status not in {
                NotificationDelivery.Status.QUEUED,
                NotificationDelivery.Status.FAILED,
            }:
                continue
            try:
                provider_message_id = _dispatch_single_delivery(
                    message=message,
                    delivery=delivery,
                    settings_snapshot=settings_snapshot,
                    mailer=resolved_mailer,
                )
            except (
                Exception
            ) as exc:  # pragma: no cover - exception type intentionally broad
                _mark_delivery_failed(delivery, str(exc))
                continue
            _mark_delivery_sent(
                delivery,
                provider_message_id=provider_message_id,
            )

        _refresh_message_status(message)
        return message


def _verify_webhook_signature(
    *,
    body: bytes,
    signature: str,
    timestamp: str,
    settings_snapshot: NotificationSettingsSnapshot,
) -> None:
    """Verify the shared-secret HMAC before the body is parsed (rule 26)."""
    secret = settings_snapshot.resolve_webhook_secret()
    if not secret:
        raise NotificationWebhookSignatureError(
            "Webhook secret is not configured in the runtime environment."
        )

    try:
        timestamp_value = int(timestamp)
    except (TypeError, ValueError) as exc:
        raise NotificationWebhookSignatureError(
            "Webhook timestamp header is invalid."
        ) from exc

    age_seconds = abs(int(time.time()) - timestamp_value)
    if age_seconds > settings_snapshot.webhook_ttl_seconds:
        raise NotificationWebhookSignatureError("Webhook signature has expired.")

    expected_headers = build_webhook_signature_headers(
        body,
        secret=secret,
        timestamp=timestamp_value,
    )
    expected_signature = expected_headers["X-QuickScale-Notifications-Signature"]
    if not hmac.compare_digest(
        (signature or "").encode("utf-8"), expected_signature.encode("utf-8")
    ):
        raise NotificationWebhookSignatureError("Webhook signature is invalid.")


def ingest_webhook_event(
    *,
    body: bytes,
    signature: str,
    timestamp: str,
) -> WebhookIngestionResult:
    """Verify and ingest a signed provider delivery event idempotently.

    The signature is verified before the body is parsed (Module Conventions
    rule 26), so an unsigned or mis-signed request never reaches JSON
    parsing.
    """
    settings_snapshot = load_settings_snapshot()
    _ensure_notifications_enabled(settings_snapshot)
    _verify_webhook_signature(
        body=body,
        signature=signature,
        timestamp=timestamp,
        settings_snapshot=settings_snapshot,
    )
    payload = _parse_webhook_payload(body)
    fields = _extract_webhook_event_fields(payload)
    delivery = _resolve_webhook_delivery(fields)

    occurred_at = _parse_event_datetime(
        payload.get("occurred_at")
        or payload.get("created_at")
        or payload.get("timestamp")
    )
    normalized_status = _EVENT_STATUS_MAP.get(
        fields.event_type.strip().lower(),
        delivery.status,
    )
    idempotency_key = _build_event_idempotency_key(
        provider_event_id=fields.provider_event_id,
        event_type=fields.event_type,
        provider_message_id=fields.provider_message_id,
        recipient_email=fields.recipient_email,
        payload=payload,
    )
    return _record_delivery_event(
        delivery=delivery,
        fields=fields,
        normalized_status=normalized_status,
        occurred_at=occurred_at,
        idempotency_key=idempotency_key,
        payload=payload,
    )
