"""Operational services for the QuickScale notifications module."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
import hashlib
import hmac
import json
import os
import time
from email.utils import formataddr
from typing import Any, Protocol, cast

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.text import slugify

from quickscale_modules_notifications.models import (
    NotificationDelivery,
    NotificationDeliveryEvent,
    NotificationMessage,
    NotificationSettings,
)

_DEFAULT_ALLOWED_TAGS = (
    "quickscale",
    "transactional",
    "notifications",
    "auth",
    "forms",
    "ops",
    "testing",
)
_DEFAULT_DEFAULT_TAGS = ("quickscale", "transactional")
_ALLOWED_METADATA_KEYS = {"template", "project", "workflow"}
_LIVE_RESEND_BACKEND = "anymail.backends.resend.EmailBackend"
_PLACEHOLDER_SENDER_EMAIL = "noreply@example.com"
_EVENT_STATUS_MAP = {
    "sent": NotificationDelivery.STATUS_SENT,
    "email.sent": NotificationDelivery.STATUS_SENT,
    "delivered": NotificationDelivery.STATUS_DELIVERED,
    "email.delivered": NotificationDelivery.STATUS_DELIVERED,
    "delivery.delivered": NotificationDelivery.STATUS_DELIVERED,
    "failed": NotificationDelivery.STATUS_FAILED,
    "delivery.failed": NotificationDelivery.STATUS_FAILED,
    "rejected": NotificationDelivery.STATUS_FAILED,
    "bounced": NotificationDelivery.STATUS_BOUNCED,
    "email.bounced": NotificationDelivery.STATUS_BOUNCED,
    "complained": NotificationDelivery.STATUS_COMPLAINED,
    "email.complained": NotificationDelivery.STATUS_COMPLAINED,
}


class NotificationError(Exception):
    """Base error for notification operations."""


class NotificationConfigurationError(NotificationError):
    """Raised when runtime notification configuration is invalid."""


class NotificationDisabledError(NotificationError):
    """Raised when the notifications runtime is disabled."""


class NotificationValidationError(NotificationError):
    """Raised when the requested notification payload is invalid."""


class NotificationTemplateError(NotificationValidationError):
    """Raised when a notification template cannot be rendered safely."""


class NotificationWebhookError(NotificationError):
    """Raised when webhook payload ingestion fails."""


class NotificationWebhookSignatureError(NotificationWebhookError):
    """Raised when webhook signature validation fails."""


class DeliveryMailer(Protocol):
    """Protocol for delivery backends used by dispatch tests and runtime."""

    def __call__(self, message: EmailMultiAlternatives) -> str | None: ...


@dataclass(frozen=True)
class NotificationTemplateDefinition:
    """Template registry entry for a canonical notification template."""

    subject_template: str
    text_template: str
    html_template: str
    required_context: frozenset[str]


@dataclass(frozen=True)
class RenderedNotification:
    """Rendered subject and body content for a canonical notification."""

    subject: str
    text_body: str
    html_body: str


@dataclass(frozen=True)
class NotificationSettingsSnapshot:
    """Immutable runtime view of the authoritative notification settings."""

    enabled: bool
    provider_name: str
    email_backend: str
    sender_name: str
    sender_email: str
    reply_to_email: str
    resend_domain: str
    resend_api_key_env_var: str
    webhook_secret_env_var: str
    default_tags: tuple[str, ...]
    allowed_tags: tuple[str, ...]
    webhook_ttl_seconds: int

    @classmethod
    def from_model(
        cls, settings_row: NotificationSettings
    ) -> NotificationSettingsSnapshot:
        """Create a snapshot from a database row."""
        return cls(
            enabled=settings_row.enabled,
            provider_name=settings_row.provider_name,
            email_backend=settings_row.email_backend,
            sender_name=settings_row.sender_name,
            sender_email=settings_row.sender_email,
            reply_to_email=settings_row.reply_to_email,
            resend_domain=settings_row.resend_domain,
            resend_api_key_env_var=settings_row.resend_api_key_env_var,
            webhook_secret_env_var=settings_row.webhook_secret_env_var,
            default_tags=_normalize_tag_sequence(settings_row.default_tags),
            allowed_tags=_normalize_tag_sequence(settings_row.allowed_tags),
            webhook_ttl_seconds=settings_row.webhook_ttl_seconds,
        )

    @classmethod
    def from_settings(cls) -> NotificationSettingsSnapshot:
        """Create a snapshot from Django settings defaults."""
        return cls(
            enabled=bool(getattr(settings, "QUICKSCALE_NOTIFICATIONS_ENABLED", True)),
            provider_name=str(
                getattr(settings, "QUICKSCALE_NOTIFICATIONS_PROVIDER", "resend")
            ),
            email_backend=str(getattr(settings, "EMAIL_BACKEND", "")),
            sender_name=str(
                getattr(settings, "QUICKSCALE_NOTIFICATIONS_SENDER_NAME", "QuickScale")
            ),
            sender_email=str(
                getattr(
                    settings,
                    "QUICKSCALE_NOTIFICATIONS_SENDER_EMAIL",
                    getattr(settings, "DEFAULT_FROM_EMAIL", ""),
                )
            ),
            reply_to_email=str(
                getattr(settings, "QUICKSCALE_NOTIFICATIONS_REPLY_TO_EMAIL", "")
            ),
            resend_domain=str(
                getattr(settings, "QUICKSCALE_NOTIFICATIONS_RESEND_DOMAIN", "")
            ),
            resend_api_key_env_var=str(
                getattr(
                    settings,
                    "QUICKSCALE_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR",
                    "RESEND_API_KEY",
                )
            ),
            webhook_secret_env_var=str(
                getattr(
                    settings,
                    "QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR",
                    "QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET",
                )
            ),
            default_tags=_normalize_tag_sequence(
                getattr(
                    settings,
                    "QUICKSCALE_NOTIFICATIONS_DEFAULT_TAGS",
                    _DEFAULT_DEFAULT_TAGS,
                )
            ),
            allowed_tags=_normalize_tag_sequence(
                getattr(
                    settings,
                    "QUICKSCALE_NOTIFICATIONS_ALLOWED_TAGS",
                    _DEFAULT_ALLOWED_TAGS,
                )
            ),
            webhook_ttl_seconds=int(
                getattr(settings, "QUICKSCALE_NOTIFICATIONS_WEBHOOK_TTL_SECONDS", 300)
            ),
        )

    def as_model_defaults(self) -> dict[str, Any]:
        """Convert the immutable snapshot into model-compatible defaults."""
        return {
            "enabled": self.enabled,
            "provider_name": self.provider_name,
            "email_backend": self.email_backend,
            "sender_name": self.sender_name,
            "sender_email": self.sender_email,
            "reply_to_email": self.reply_to_email,
            "resend_domain": self.resend_domain,
            "resend_api_key_env_var": self.resend_api_key_env_var,
            "webhook_secret_env_var": self.webhook_secret_env_var,
            "default_tags": list(self.default_tags),
            "allowed_tags": list(self.allowed_tags),
            "webhook_ttl_seconds": self.webhook_ttl_seconds,
        }

    def resolve_resend_api_key(self) -> str:
        """Resolve the live Resend API key from the configured environment variable."""
        env_var_name = self.resend_api_key_env_var.strip() or "RESEND_API_KEY"
        return os.getenv(env_var_name, "").strip()

    def resolve_webhook_secret(self) -> str:
        """Resolve the shared webhook signing secret from the configured environment variable."""
        env_var_name = (
            self.webhook_secret_env_var.strip()
            or "QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET"
        )
        return os.getenv(env_var_name, "").strip()

    def live_delivery_enabled(self) -> bool:
        """Return whether the active email backend is the Anymail Resend backend."""
        return self.email_backend.strip() == _LIVE_RESEND_BACKEND

    def formatted_from_email(self) -> str:
        """Return a user-friendly from email value for Django email sending."""
        if self.sender_name.strip():
            return formataddr((self.sender_name.strip(), self.sender_email.strip()))
        return self.sender_email.strip()


@dataclass(frozen=True)
class WebhookIngestionResult:
    """Result returned by webhook ingestion."""

    duplicate: bool
    delivery_id: int
    status: str


_TEMPLATE_REGISTRY = {
    "notifications.generic": NotificationTemplateDefinition(
        subject_template=(
            "quickscale_modules_notifications/notifications/generic_subject.txt"
        ),
        text_template=(
            "quickscale_modules_notifications/notifications/generic_body.txt"
        ),
        html_template=(
            "quickscale_modules_notifications/notifications/generic_body.html"
        ),
        required_context=frozenset({"headline", "body"}),
    ),
    "notifications.forms_submission": NotificationTemplateDefinition(
        subject_template=(
            "quickscale_modules_notifications/notifications/forms_submission_subject.txt"
        ),
        text_template=(
            "quickscale_modules_notifications/notifications/forms_submission_body.txt"
        ),
        html_template=(
            "quickscale_modules_notifications/notifications/forms_submission_body.html"
        ),
        required_context=frozenset(
            {"form_title", "submitted_at", "fields", "ip_address", "status"}
        ),
    ),
}


def ensure_default_settings() -> NotificationSettings:
    """Ensure the read-only settings snapshot row exists and matches settings."""
    snapshot = NotificationSettingsSnapshot.from_settings()
    defaults = snapshot.as_model_defaults()
    settings_row, _ = NotificationSettings.objects.get_or_create(
        key="default",
        defaults=defaults,
    )
    updated_fields = [
        field_name
        for field_name, value in defaults.items()
        if getattr(settings_row, field_name) != value
    ]
    if updated_fields:
        for field_name in updated_fields:
            setattr(settings_row, field_name, defaults[field_name])
        settings_row.save(update_fields=[*updated_fields, "updated_at"])
    return settings_row


def load_settings_snapshot() -> NotificationSettingsSnapshot:
    """Load the authoritative settings snapshot, keeping the admin row in sync."""
    if NotificationSettings.objects.exists():
        ensure_default_settings()
    return NotificationSettingsSnapshot.from_settings()


def _ensure_notifications_enabled(
    settings_snapshot: NotificationSettingsSnapshot,
) -> None:
    if not settings_snapshot.enabled:
        raise NotificationDisabledError("Notifications module is disabled.")


def render_notification(
    *,
    template_key: str,
    context: Mapping[str, Any],
) -> RenderedNotification:
    """Render a canonical notification template after validating its context."""
    definition = _TEMPLATE_REGISTRY.get(template_key)
    if definition is None:
        raise NotificationTemplateError(
            f"Unknown notification template: {template_key}"
        )

    normalized_context = _normalize_context(context)
    missing_keys = sorted(definition.required_context.difference(normalized_context))
    if missing_keys:
        raise NotificationTemplateError(
            "Missing required notification context keys: " + ", ".join(missing_keys)
        )

    template_context = {**normalized_context, "template_key": template_key}
    subject = " ".join(
        render_to_string(definition.subject_template, template_context).splitlines()
    ).strip()
    text_body = render_to_string(definition.text_template, template_context).strip()
    html_body = render_to_string(definition.html_template, template_context).strip()

    if not subject:
        raise NotificationTemplateError(
            f"Template {template_key} rendered an empty subject."
        )
    if not text_body:
        raise NotificationTemplateError(
            f"Template {template_key} rendered an empty text body."
        )

    return RenderedNotification(
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )


def sanitize_provider_tags(
    tags: Sequence[str] | None,
    *,
    settings_snapshot: NotificationSettingsSnapshot,
) -> list[str]:
    """Return provider-visible tags limited to the approved non-sensitive allowlist."""
    allowed_tags = set(settings_snapshot.allowed_tags)
    seen: set[str] = set()
    sanitized: list[str] = []
    for raw_value in [*settings_snapshot.default_tags, *(tags or ())]:
        normalized_tag = _normalize_tag(raw_value)
        if not normalized_tag or normalized_tag not in allowed_tags:
            continue
        if normalized_tag in seen:
            continue
        sanitized.append(normalized_tag)
        seen.add(normalized_tag)
    return sanitized


def sanitize_provider_metadata(
    metadata: Mapping[str, Any] | None,
    *,
    template_key: str,
) -> dict[str, str]:
    """Return provider-visible metadata constrained to non-sensitive keys and values."""
    sanitized: dict[str, str] = {}
    for key, value in (metadata or {}).items():
        normalized_key = _normalize_metadata_key(key)
        if normalized_key not in _ALLOWED_METADATA_KEYS:
            continue
        normalized_value = _sanitize_provider_visible_value(value)
        if normalized_value:
            sanitized[normalized_key] = normalized_value
    sanitized["template"] = _sanitize_provider_visible_value(template_key)
    return sanitized


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
            subject=rendered.subject,
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
        message = NotificationMessage.objects.select_for_update().get(pk=message_id)
        deliveries = list(message.deliveries.select_for_update().order_by("pk"))
        settings_snapshot = load_settings_snapshot()
        _ensure_notifications_enabled(settings_snapshot)

        configuration_issues = _validate_dispatch_settings(settings_snapshot)
        if configuration_issues:
            error_message = "; ".join(configuration_issues)
            for delivery in deliveries:
                if delivery.status != NotificationDelivery.STATUS_QUEUED:
                    continue
                _mark_delivery_failed(delivery, error_message)
            _refresh_message_status(message)
            return message

        resolved_mailer = mailer or _send_email_message
        for delivery in deliveries:
            if delivery.status not in {
                NotificationDelivery.STATUS_QUEUED,
                NotificationDelivery.STATUS_FAILED,
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


def ingest_webhook_event(
    *,
    body: bytes,
    payload: Mapping[str, Any],
    signature: str,
    timestamp: str,
) -> WebhookIngestionResult:
    """Verify and ingest a signed provider delivery event idempotently."""
    settings_snapshot = load_settings_snapshot()
    _ensure_notifications_enabled(settings_snapshot)
    _verify_webhook_signature(
        body=body,
        signature=signature,
        timestamp=timestamp,
        settings_snapshot=settings_snapshot,
    )

    event_type = str(payload.get("event_type") or payload.get("type") or "").strip()
    provider_event_id = str(payload.get("event_id") or payload.get("id") or "").strip()
    provider_message_id = str(
        payload.get("provider_message_id")
        or payload.get("message_id")
        or payload.get("email_id")
        or ""
    ).strip()
    recipient_email = (
        str(payload.get("recipient") or payload.get("email") or "").strip().lower()
    )

    if not event_type:
        raise NotificationWebhookError("Webhook payload is missing event_type.")
    if not provider_message_id:
        raise NotificationWebhookError(
            "Webhook payload is missing provider_message_id."
        )
    if not recipient_email:
        raise NotificationWebhookError("Webhook payload is missing recipient.")

    validate_email(recipient_email)
    delivery = (
        NotificationDelivery.objects.select_related("message")
        .filter(
            provider_message_id=provider_message_id,
            recipient_email__iexact=recipient_email,
        )
        .order_by("-pk")
        .first()
    )
    if delivery is None:
        raise NotificationWebhookError(
            "Webhook payload does not match a known notification delivery."
        )

    occurred_at = _parse_event_datetime(
        payload.get("occurred_at")
        or payload.get("created_at")
        or payload.get("timestamp")
    )
    normalized_status = _EVENT_STATUS_MAP.get(
        event_type.strip().lower(),
        delivery.status,
    )
    idempotency_key = _build_event_idempotency_key(
        provider_event_id=provider_event_id,
        event_type=event_type,
        provider_message_id=provider_message_id,
        recipient_email=recipient_email,
        payload=payload,
    )

    with transaction.atomic():
        event, created = NotificationDeliveryEvent.objects.get_or_create(
            idempotency_key=idempotency_key,
            defaults={
                "delivery": delivery,
                "provider_event_id": provider_event_id,
                "event_type": event_type,
                "provider_message_id": provider_message_id,
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
            event_type=event_type,
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


def _verify_webhook_signature(
    *,
    body: bytes,
    signature: str,
    timestamp: str,
    settings_snapshot: NotificationSettingsSnapshot,
) -> None:
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
    if not hmac.compare_digest(signature or "", expected_signature):
        raise NotificationWebhookSignatureError("Webhook signature is invalid.")


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
        status == NotificationDelivery.STATUS_DELIVERED
        and delivery.delivered_at is None
    ):
        delivery.delivered_at = event_time
    if (
        status
        in {
            NotificationDelivery.STATUS_FAILED,
            NotificationDelivery.STATUS_BOUNCED,
            NotificationDelivery.STATUS_COMPLAINED,
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


def _mark_delivery_sent(
    delivery: NotificationDelivery,
    *,
    provider_message_id: str,
) -> None:
    now = timezone.now()
    delivery.status = NotificationDelivery.STATUS_SENT
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
    delivery.status = NotificationDelivery.STATUS_FAILED
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


def _refresh_message_status(message: NotificationMessage) -> None:
    deliveries = list(message.deliveries.order_by("pk"))
    if not deliveries:
        return

    statuses = {delivery.status for delivery in deliveries}
    last_event_at_values = [
        delivery.last_event_at
        for delivery in deliveries
        if delivery.last_event_at is not None
    ]
    dispatched_at_values = [
        delivery.dispatched_at
        for delivery in deliveries
        if delivery.dispatched_at is not None
    ]
    error_messages = [
        delivery.failure_reason.strip()
        for delivery in deliveries
        if delivery.failure_reason.strip()
    ]

    success_statuses = {
        NotificationDelivery.STATUS_SENT,
        NotificationDelivery.STATUS_DELIVERED,
    }
    failure_statuses = {
        NotificationDelivery.STATUS_FAILED,
        NotificationDelivery.STATUS_BOUNCED,
        NotificationDelivery.STATUS_COMPLAINED,
    }

    if statuses.issubset(success_statuses):
        message.status = NotificationMessage.STATUS_SENT
    elif statuses.issubset(failure_statuses):
        message.status = NotificationMessage.STATUS_FAILED
    elif statuses == {NotificationDelivery.STATUS_QUEUED}:
        message.status = NotificationMessage.STATUS_QUEUED
    else:
        message.status = NotificationMessage.STATUS_PARTIAL

    message.dispatched_at = min(dispatched_at_values) if dispatched_at_values else None
    message.last_event_at = max(last_event_at_values) if last_event_at_values else None
    message.last_error = error_messages[-1] if error_messages else ""
    message.save(
        update_fields=[
            "status",
            "dispatched_at",
            "last_event_at",
            "last_error",
            "updated_at",
        ]
    )


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


def _normalize_context(context: Mapping[str, Any]) -> dict[str, Any]:
    try:
        serialized = json.dumps(dict(context))
    except TypeError as exc:
        raise NotificationTemplateError(
            "Notification context must be JSON-serializable."
        ) from exc
    normalized = json.loads(serialized)
    return cast(dict[str, Any], normalized)


def _normalize_recipients(recipients: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in recipients:
        candidate = str(raw_value).strip().lower()
        if not candidate:
            continue
        validate_email(candidate)
        if candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return normalized


def _normalize_tag_sequence(values: Sequence[Any]) -> tuple[str, ...]:
    normalized_values: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized_value = _normalize_tag(value)
        if not normalized_value or normalized_value in seen:
            continue
        seen.add(normalized_value)
        normalized_values.append(normalized_value)
    return tuple(normalized_values)


def _normalize_tag(value: Any) -> str:
    normalized = slugify(str(value).strip())
    return normalized[:50]


def _normalize_metadata_key(value: Any) -> str:
    return slugify(str(value).strip()).replace("-", "_")


def _sanitize_provider_visible_value(value: Any) -> str:
    normalized = slugify(str(value).strip().replace(".", "-").replace("_", "-"))
    return normalized[:64]


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
        return timezone.datetime.fromtimestamp(value, tz=timezone.utc)
    parsed_value = parse_datetime(str(value))
    if parsed_value is None:
        return None
    if timezone.is_naive(parsed_value):
        return timezone.make_aware(parsed_value, timezone.utc)
    return parsed_value
