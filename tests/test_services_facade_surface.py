"""Public-surface lock for the notifications ``services`` facade.

``services`` keeps its public import path and re-exports public names one way
from the private modules that define them; the delivery dispatch and webhook
entry points stay defined here.  This test pins public names only — no private
name and no incidental import — resolves the delivery seam through the module
that defines it, and checks that explicit re-exports are the defining objects
(decisions.md, Split-Facade Seams).
"""

from __future__ import annotations

import importlib

import pytest

from quickscale_modules_notifications import _delivery, services
from quickscale_modules_notifications.models import NotificationMessage

SERVICE_SURFACE: frozenset[str] = frozenset(
    {
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
    }
)

INCIDENTAL_NAMES = frozenset(
    {"Any", "Mapping", "Sequence", "hmac", "time", "transaction"}
)

FORMER_PRIVATE_REEXPORTS = frozenset(
    {
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
        "_extract_webhook_event_fields",
        "_mark_delivery_failed",
        "_mark_delivery_sent",
        "_normalize_context",
        "_normalize_metadata_key",
        "_normalize_recipients",
        "_normalize_tag",
        "_normalize_tag_sequence",
        "_parse_event_datetime",
        "_parse_webhook_payload",
        "_record_delivery_event",
        "_refresh_message_status",
        "_resolve_webhook_delivery",
        "_sanitize_provider_visible_value",
        "_send_email_message",
        "_validate_dispatch_settings",
    }
)

REEXPORTED_FROM: dict[str, str] = {
    "DeliveryMailer": "quickscale_modules_notifications._delivery",
    "NotificationConfigurationError": "quickscale_modules_notifications.exceptions",
    "NotificationDisabledError": "quickscale_modules_notifications.exceptions",
    "NotificationError": "quickscale_modules_notifications.exceptions",
    "NotificationSettingsSnapshot": "quickscale_modules_notifications._settings",
    "NotificationTemplateDefinition": "quickscale_modules_notifications._templates",
    "NotificationTemplateError": "quickscale_modules_notifications.exceptions",
    "NotificationValidationError": "quickscale_modules_notifications.exceptions",
    "NotificationWebhookError": "quickscale_modules_notifications.exceptions",
    "NotificationWebhookSignatureError": "quickscale_modules_notifications.exceptions",
    "RenderedNotification": "quickscale_modules_notifications._templates",
    "WebhookIngestionResult": "quickscale_modules_notifications._webhooks",
    "build_webhook_signature_headers": "quickscale_modules_notifications._webhooks",
    "ensure_default_settings": "quickscale_modules_notifications._settings",
    "is_enabled": "quickscale_modules_notifications._settings",
    "load_settings_snapshot": "quickscale_modules_notifications._settings",
    "render_notification": "quickscale_modules_notifications._templates",
    "sanitize_provider_metadata": "quickscale_modules_notifications._sanitization",
    "sanitize_provider_tags": "quickscale_modules_notifications._sanitization",
}


def test_public_surface_importable() -> None:
    """Every pinned public name is present on the facade."""
    missing = sorted(SERVICE_SURFACE - set(dir(services)))
    assert not missing, f"services is missing public names: {missing}"


def test_surface_pins_no_private_or_incidental_names() -> None:
    """The expected set names public facade API only."""
    for name in SERVICE_SURFACE:
        assert not name.startswith("_"), f"services pins private {name!r}"
    incidental = SERVICE_SURFACE & INCIDENTAL_NAMES
    assert not incidental, f"services pins incidental names: {sorted(incidental)}"


def test_facade_reexports_no_private_names() -> None:
    """The facade no longer surfaces names that private siblings define."""
    leaked = sorted(
        name for name in FORMER_PRIVATE_REEXPORTS if hasattr(services, name)
    )
    assert not leaked, f"services re-exports private names: {leaked}"


def test_declared_surface_is_public() -> None:
    """``__all__`` stays a subset of the pinned public surface."""
    assert set(services.__all__) <= set(SERVICE_SURFACE)


def test_reexports_are_the_defining_objects() -> None:
    """A re-export is the same object as its defining module's binding."""
    for name, source in REEXPORTED_FROM.items():
        defining = importlib.import_module(source)
        assert getattr(services, name) is getattr(defining, name), (
            f"services.{name} is not {source}.{name}"
        )


@pytest.mark.django_db
def test_defining_module_patch_reaches_delivery_dispatch(
    monkeypatch: pytest.MonkeyPatch,
    queued_message,
) -> None:
    """The dispatch path resolves ``_send_email_message`` from ``_delivery``."""
    dispatched: list[str] = []

    def patched_send(message) -> str:
        dispatched.append(message.to[0])
        return f"patched::{message.to[0]}"

    monkeypatch.setattr(_delivery, "_send_email_message", patched_send)

    services.dispatch_notification_message(queued_message.pk)

    queued_message.refresh_from_db()
    assert dispatched == ["alpha@example.com", "beta@example.com"]
    assert queued_message.status == NotificationMessage.Status.SENT
    assert sorted(
        queued_message.deliveries.values_list("provider_message_id", flat=True)
    ) == ["patched::alpha@example.com", "patched::beta@example.com"]
