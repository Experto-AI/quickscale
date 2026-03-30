"""Tests for notifications module models and metadata."""

import pytest

import quickscale_modules_notifications
from quickscale_modules_notifications.models import (
    NotificationDelivery,
    NotificationDeliveryEvent,
    NotificationMessage,
)


def test_package_version_is_exposed() -> None:
    assert quickscale_modules_notifications.__version__ == "0.78.0"


@pytest.mark.django_db
def test_model_string_representations(notification_settings_row) -> None:
    message = NotificationMessage.objects.create(
        template_key="notifications.generic",
        subject="Subject",
        from_email="QuickScale <noreply@example.com>",
        reply_to_email="support@example.com",
        rendered_text="Body",
        rendered_html="<p>Body</p>",
        context_json={"headline": "Subject", "body": "Body"},
    )
    delivery = NotificationDelivery.objects.create(
        message=message,
        recipient_email="user@example.com",
    )
    event = NotificationDeliveryEvent.objects.create(
        delivery=delivery,
        provider_event_id="",
        idempotency_key="abc123",
        event_type="delivered",
        provider_message_id="provider-1",
        status_after=NotificationDelivery.STATUS_DELIVERED,
        payload_json={},
    )

    assert "Notification settings" in str(notification_settings_row)
    assert str(message) == "notifications.generic (queued)"
    assert str(delivery) == "user@example.com (queued)"
    assert str(event) == "delivered (abc123)"
