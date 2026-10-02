"""Delivery dispatch and delivery-row bookkeeping for the notifications module.

``services.py`` keeps the public ``send_notification`` and
``dispatch_notification_message`` entry points so their call sites and test
patch targets stay put; the per-delivery work they delegate to lives here
(Module Conventions rule 28).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Protocol

from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.utils import timezone

from quickscale_modules_notifications._settings import (
    NotificationSettingsSnapshot,
    _PLACEHOLDER_SENDER_EMAIL,
)
from quickscale_modules_notifications.exceptions import NotificationValidationError
from quickscale_modules_notifications.models import (
    NotificationDelivery,
    NotificationMessage,
)

logger = logging.getLogger(__name__)


class DeliveryMailer(Protocol):
    """Protocol for delivery backends used by dispatch tests and runtime."""

    def __call__(self, message: EmailMultiAlternatives) -> str | None: ...


def _normalize_recipients(recipients: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in recipients:
        candidate = str(raw_value).strip().lower()
        if not candidate:
            continue
        try:
            validate_email(candidate)
        except ValidationError as exc:
            raise NotificationValidationError(
                f"Invalid recipient email address: {candidate}"
            ) from exc
        if candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return normalized


def _bounded_subject(subject: str) -> str:
    """Clamp a rendered subject to the storage field's length contract.

    Each context value is stored on its own row, but the rendered subject
    composes them, so a valid long title or name can exceed
    ``NotificationMessage.subject``'s length.  A rejected insert would drop a
    valid notification silently, so the subject is truncated at the
    persistence boundary; the full content stays in the rendered body.
    """
    max_length = getattr(
        NotificationMessage._meta.get_field("subject"), "max_length", None
    )
    if isinstance(max_length, int) and len(subject) > max_length:
        logger.warning(
            "Notification subject exceeded %s characters and was truncated.",
            max_length,
        )
        return subject[:max_length]
    return subject


def _dispatch_single_delivery(
    *,
    message: NotificationMessage,
    delivery: NotificationDelivery,
    settings_snapshot: NotificationSettingsSnapshot,
    mailer: DeliveryMailer,
) -> str:
    email_message = EmailMultiAlternatives(
        subject=message.subject,
        body=message.rendered_text,
        from_email=settings_snapshot.formatted_from_email(),
        to=[delivery.recipient_email],
        reply_to=[message.reply_to_email] if message.reply_to_email else None,
    )
    if message.rendered_html:
        email_message.attach_alternative(message.rendered_html, "text/html")
    setattr(email_message, "tags", list(message.tags_json))
    setattr(email_message, "metadata", dict(message.metadata_json))
    provider_message_id = mailer(email_message)
    if provider_message_id:
        return provider_message_id
    return _extract_provider_message_id(email_message)


def _send_email_message(message: EmailMultiAlternatives) -> str:
    message.send(fail_silently=False)
    return _extract_provider_message_id(message)


def _extract_provider_message_id(message: EmailMultiAlternatives) -> str:
    status = getattr(message, "anymail_status", None)
    provider_message_id = getattr(status, "message_id", None)
    if provider_message_id:
        return str(provider_message_id)
    extra_headers = getattr(message, "extra_headers", None) or {}
    header_message_id = extra_headers.get("Message-ID")
    if header_message_id:
        return str(header_message_id)
    return ""


def _validate_dispatch_settings(
    settings_snapshot: NotificationSettingsSnapshot,
) -> list[str]:
    issues: list[str] = []
    if not settings_snapshot.sender_email.strip():
        issues.append("sender_email is required for notification delivery")
    if settings_snapshot.live_delivery_enabled():
        if (
            settings_snapshot.sender_email.strip().casefold()
            == _PLACEHOLDER_SENDER_EMAIL.casefold()
        ):
            issues.append(
                "live Resend delivery cannot use the default placeholder sender "
                "email noreply@example.com"
            )
        if not settings_snapshot.resolve_resend_api_key():
            issues.append(
                "live Resend delivery requires the configured API key environment variable"
            )
    return issues


def _mark_delivery_sent(
    delivery: NotificationDelivery,
    *,
    provider_message_id: str,
) -> None:
    now = timezone.now()
    delivery.status = NotificationDelivery.Status.SENT
    if provider_message_id:
        delivery.provider_message_id = provider_message_id
    delivery.failure_reason = ""
    delivery.last_event_type = "sent"
    delivery.dispatched_at = now
    delivery.last_event_at = now
    delivery.save(
        update_fields=[
            "status",
            "provider_message_id",
            "failure_reason",
            "last_event_type",
            "dispatched_at",
            "last_event_at",
            "updated_at",
        ]
    )


def _mark_delivery_failed(delivery: NotificationDelivery, error_message: str) -> None:
    now = timezone.now()
    delivery.status = NotificationDelivery.Status.FAILED
    delivery.failure_reason = error_message
    delivery.retry_count += 1
    delivery.last_event_type = "failed"
    delivery.last_event_at = now
    delivery.failed_at = now
    delivery.save(
        update_fields=[
            "status",
            "failure_reason",
            "retry_count",
            "last_event_type",
            "last_event_at",
            "failed_at",
            "updated_at",
        ]
    )


def _resolve_message_status(statuses: set[str]) -> str:
    """Resolve the parent message status from its deliveries' statuses."""
    success_statuses = {
        NotificationDelivery.Status.SENT,
        NotificationDelivery.Status.DELIVERED,
    }
    failure_statuses = {
        NotificationDelivery.Status.FAILED,
        NotificationDelivery.Status.BOUNCED,
        NotificationDelivery.Status.COMPLAINED,
    }
    if statuses.issubset(success_statuses):
        return NotificationMessage.Status.SENT
    if statuses.issubset(failure_statuses):
        return NotificationMessage.Status.FAILED
    if statuses == {NotificationDelivery.Status.QUEUED}:
        return NotificationMessage.Status.QUEUED
    return NotificationMessage.Status.PARTIAL


@dataclass(frozen=True)
class _DeliverySummary:
    """Aggregated delivery state used to refresh a message's status."""

    statuses: set[str]
    dispatched_at_values: list[datetime]
    last_event_at_values: list[datetime]
    error_messages: list[str]


def _summarize_deliveries(
    deliveries: Sequence[NotificationDelivery],
) -> _DeliverySummary:
    """Collect the per-delivery values a message status is derived from."""
    statuses: set[str] = set()
    dispatched_at_values: list[datetime] = []
    last_event_at_values: list[datetime] = []
    error_messages: list[str] = []
    for delivery in deliveries:
        statuses.add(delivery.status)
        if delivery.dispatched_at is not None:
            dispatched_at_values.append(delivery.dispatched_at)
        if delivery.last_event_at is not None:
            last_event_at_values.append(delivery.last_event_at)
        failure_reason = delivery.failure_reason.strip()
        if failure_reason:
            error_messages.append(failure_reason)
    return _DeliverySummary(
        statuses=statuses,
        dispatched_at_values=dispatched_at_values,
        last_event_at_values=last_event_at_values,
        error_messages=error_messages,
    )


def _refresh_message_status(message: NotificationMessage) -> None:
    deliveries = list(message.deliveries.order_by("pk"))
    if not deliveries:
        return

    summary = _summarize_deliveries(deliveries)
    message.status = _resolve_message_status(summary.statuses)
    message.dispatched_at = (
        min(summary.dispatched_at_values) if summary.dispatched_at_values else None
    )
    message.last_event_at = (
        max(summary.last_event_at_values) if summary.last_event_at_values else None
    )
    message.last_error = summary.error_messages[-1] if summary.error_messages else ""
    message.save(
        update_fields=[
            "status",
            "dispatched_at",
            "last_event_at",
            "last_error",
            "updated_at",
        ]
    )
