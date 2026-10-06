"""Runtime notifications services for the QuickScale notifications module.

The implementation lives in private sibling modules grouped by concern
(``_settings``, ``_templates``, ``_sanitization``, ``_delivery``,
``_webhooks``); this module owns the public service surface, the delivery
dispatch and webhook entry points, and re-exports public names only.  Private
helpers stay on the module that defines them; callers and tests resolve them
there, never through this facade (decisions.md, Split-Facade Seams).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hmac
import time
from typing import Any

from django.db import transaction

import quickscale_modules_notifications._delivery as _delivery
import quickscale_modules_notifications._settings as _settings
import quickscale_modules_notifications._templates as _templates
import quickscale_modules_notifications._webhooks as _webhooks

from quickscale_modules_notifications._delivery import (
    DeliveryMailer as DeliveryMailer,
)
from quickscale_modules_notifications._sanitization import (
    sanitize_provider_metadata as sanitize_provider_metadata,
    sanitize_provider_tags as sanitize_provider_tags,
)
from quickscale_modules_notifications._settings import (
    NotificationSettingsSnapshot as NotificationSettingsSnapshot,
    ensure_default_settings as ensure_default_settings,
    is_enabled as is_enabled,
    load_settings_snapshot as load_settings_snapshot,
)
from quickscale_modules_notifications._templates import (
    NotificationTemplateDefinition as NotificationTemplateDefinition,
    RenderedNotification as RenderedNotification,
    render_notification as render_notification,
)
from quickscale_modules_notifications._webhooks import (
    WebhookIngestionResult as WebhookIngestionResult,
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
    about_users: Sequence[Any],
    tags: Sequence[str] | None = None,
    metadata: Mapping[str, Any] | None = None,
    mailer: DeliveryMailer | None = None,
) -> NotificationMessage:
    """Create a logical notification message and dispatch it after commit.

    ``about_users`` is required: every sender states the persons the message is
    about (an explicit empty sequence when it is about no platform user), and
    notifications stores the link on the message so account anonymization can
    select it (rule 50).
    """
    normalized_recipients = _delivery._normalize_recipients(recipients)
    if not normalized_recipients:
        raise NotificationValidationError("At least one recipient is required.")
    normalized_about_user_ids = _normalize_about_users(about_users)

    settings_snapshot = load_settings_snapshot()
    _settings._ensure_notifications_enabled(settings_snapshot)
    normalized_context = _templates._normalize_context(context)
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
            subject=_delivery._bounded_subject(rendered.subject),
            from_email=settings_snapshot.formatted_from_email(),
            reply_to_email=settings_snapshot.reply_to_email,
            rendered_text=rendered.text_body,
            rendered_html=rendered.html_body,
            context_json=normalized_context,
            provider_name=settings_snapshot.provider_name,
            tags_json=provider_tags,
            metadata_json=provider_metadata,
            about_user_ids_json=normalized_about_user_ids,
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
        transaction.on_commit(
            lambda: dispatch_notification_message(message.pk, mailer=mailer)
        )
    return message


def _normalize_about_users(about_users: Sequence[Any]) -> list[str]:
    """Return canonical, de-duplicated ids of the persons a message is about.

    Rule 50: the persons travel as the required ``about_users`` sequence, an
    explicit empty sequence included; notifications stores the link itself so
    a sender cannot omit it silently and account anonymization can select the
    message.
    """
    if isinstance(about_users, (str, bytes)):
        raise NotificationValidationError(
            "about_users must be a sequence of saved users, not a string."
        )
    try:
        entries = list(about_users)
    except TypeError as exc:
        raise NotificationValidationError(
            "about_users must be a sequence of saved users."
        ) from exc

    normalized: list[str] = []
    for user in entries:
        pk = getattr(user, "pk", None)
        if pk is None:
            raise NotificationValidationError(
                "Every entry in about_users must be a saved user."
            )
        identifier = str(pk)
        if identifier not in normalized:
            normalized.append(identifier)
    return normalized


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
        _settings._ensure_notifications_enabled(settings_snapshot)

        configuration_issues = _delivery._validate_dispatch_settings(settings_snapshot)
        if configuration_issues:
            error_message = "; ".join(configuration_issues)
            for delivery in deliveries:
                if delivery.status != NotificationDelivery.Status.QUEUED:
                    continue
                _delivery._mark_delivery_failed(delivery, error_message)
            _delivery._refresh_message_status(message)
            return message

        resolved_mailer = mailer or _delivery._send_email_message
        for delivery in deliveries:
            if delivery.status not in {
                NotificationDelivery.Status.QUEUED,
                NotificationDelivery.Status.FAILED,
            }:
                continue
            try:
                provider_message_id = _delivery._dispatch_single_delivery(
                    message=message,
                    delivery=delivery,
                    settings_snapshot=settings_snapshot,
                    mailer=resolved_mailer,
                )
            except (
                Exception
            ) as exc:  # pragma: no cover - exception type intentionally broad
                _delivery._mark_delivery_failed(delivery, str(exc))
                continue
            _delivery._mark_delivery_sent(
                delivery,
                provider_message_id=provider_message_id,
            )

        _delivery._refresh_message_status(message)
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
    _settings._ensure_notifications_enabled(settings_snapshot)
    _verify_webhook_signature(
        body=body,
        signature=signature,
        timestamp=timestamp,
        settings_snapshot=settings_snapshot,
    )
    payload = _webhooks._parse_webhook_payload(body)
    fields = _webhooks._extract_webhook_event_fields(payload)
    delivery = _webhooks._resolve_webhook_delivery(fields)

    occurred_at = _webhooks._parse_event_datetime(
        payload.get("occurred_at")
        or payload.get("created_at")
        or payload.get("timestamp")
    )
    normalized_status = _webhooks._EVENT_STATUS_MAP.get(
        fields.event_type.strip().lower(),
        delivery.status,
    )
    idempotency_key = _webhooks._build_event_idempotency_key(
        provider_event_id=fields.provider_event_id,
        event_type=fields.event_type,
        provider_message_id=fields.provider_message_id,
        recipient_email=fields.recipient_email,
        payload=payload,
    )
    return _webhooks._record_delivery_event(
        delivery=delivery,
        fields=fields,
        normalized_status=normalized_status,
        occurred_at=occurred_at,
        idempotency_key=idempotency_key,
        payload=payload,
    )
