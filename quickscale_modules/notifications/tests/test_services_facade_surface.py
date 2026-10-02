"""Conformance gate: the split notifications service surface keeps its imports.

The delivery, webhook, settings, template, and sanitization helpers live in
private sibling modules; every name the former
``quickscale_modules_notifications.services`` module defined stays importable
from the same path, with identical defining objects, and the delivery mailer
stays patchable at the services module.
"""

from __future__ import annotations

import pytest

from quickscale_modules_notifications import (
    _delivery,
    _sanitization,
    _settings,
    _templates,
    _webhooks,
    services,
)
from quickscale_modules_notifications.models import NotificationMessage

EXPECTED_DEFINED_SURFACE = frozenset(
    {
        "DeliveryMailer",
        "NotificationSettingsSnapshot",
        "NotificationTemplateDefinition",
        "RenderedNotification",
        "WebhookIngestionResult",
        "_ALLOWED_METADATA_KEYS",
        "_DEFAULT_ALLOWED_TAGS",
        "_DEFAULT_DEFAULT_TAGS",
        "_EVENT_STATUS_MAP",
        "_LIVE_RESEND_BACKEND",
        "_PLACEHOLDER_SENDER_EMAIL",
        "_TEMPLATE_REGISTRY",
        "_apply_delivery_event",
        "_bounded_subject",
        "_build_event_idempotency_key",
        "_dispatch_single_delivery",
        "_ensure_notifications_enabled",
        "_extract_provider_message_id",
        "_mark_delivery_failed",
        "_mark_delivery_sent",
        "_normalize_context",
        "_normalize_metadata_key",
        "_normalize_recipients",
        "_normalize_tag",
        "_normalize_tag_sequence",
        "_parse_event_datetime",
        "_parse_webhook_payload",
        "_refresh_message_status",
        "_sanitize_provider_visible_value",
        "_send_email_message",
        "_validate_dispatch_settings",
        "_verify_webhook_signature",
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
    }
)


def test_facade_preserves_former_defined_surface() -> None:
    """Every defined name the former module exposed stays importable from services."""
    missing = sorted(EXPECTED_DEFINED_SURFACE - set(dir(services)))
    assert not missing, f"facade dropped former module names: {missing}"


def test_facade_reexports_the_original_objects() -> None:
    """Re-exported names stay identical to their defining objects."""
    assert (
        services.NotificationSettingsSnapshot is _settings.NotificationSettingsSnapshot
    )
    assert services.ensure_default_settings is _settings.ensure_default_settings
    assert services.is_enabled is _settings.is_enabled
    assert services.render_notification is _templates.render_notification
    assert services.sanitize_provider_tags is _sanitization.sanitize_provider_tags
    assert (
        services.sanitize_provider_metadata is _sanitization.sanitize_provider_metadata
    )
    assert services._send_email_message is _delivery._send_email_message
    assert services._bounded_subject is _delivery._bounded_subject
    assert services._refresh_message_status is _delivery._refresh_message_status
    assert (
        services.build_webhook_signature_headers
        is _webhooks.build_webhook_signature_headers
    )
    assert callable(services._verify_webhook_signature)


@pytest.mark.django_db
def test_delivery_mailer_seam_stays_patchable_from_the_facade(
    monkeypatch: pytest.MonkeyPatch,
    queued_message,
) -> None:
    """The dispatch path resolves ``_send_email_message`` from the facade namespace."""
    dispatched: list[str] = []

    def patched_send(message) -> str:
        dispatched.append(message.to[0])
        return f"patched::{message.to[0]}"

    monkeypatch.setattr(services, "_send_email_message", patched_send)

    services.dispatch_notification_message(queued_message.pk)

    queued_message.refresh_from_db()
    assert dispatched == ["alpha@example.com", "beta@example.com"]
    assert queued_message.status == NotificationMessage.Status.SENT
    assert sorted(
        queued_message.deliveries.values_list("provider_message_id", flat=True)
    ) == ["patched::alpha@example.com", "patched::beta@example.com"]
