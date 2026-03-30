"""Tests for notifications module services."""

from __future__ import annotations

import json
import os
import time

import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from quickscale_modules_forms.models import (
    Form,
    FormField,
    FormFieldValue,
    FormSubmission,
)
from quickscale_modules_forms.notifications import notify_submission

from quickscale_modules_notifications.models import (
    NotificationDelivery,
    NotificationDeliveryEvent,
    NotificationMessage,
)
from quickscale_modules_notifications.services import (
    NotificationDisabledError,
    NotificationTemplateError,
    NotificationWebhookSignatureError,
    build_webhook_signature_headers,
    dispatch_notification_message,
    ensure_default_settings,
    ingest_webhook_event,
    render_notification,
    send_notification,
)


def _create_contact_form(*, slug: str, notify_emails: str) -> Form:
    form = Form.objects.create(
        title="Tracked Contact",
        slug=slug,
        description="Get in touch.",
        success_message="Thank you, we will be in touch.",
        notify_emails=notify_emails,
        spam_protection_enabled=True,
    )
    FormField.objects.create(
        form=form,
        field_type=FormField.FIELD_TYPE_TEXT,
        label="Name",
        name="full_name",
        required=True,
        order=1,
    )
    FormField.objects.create(
        form=form,
        field_type=FormField.FIELD_TYPE_EMAIL,
        label="Email",
        name="email",
        required=True,
        order=2,
    )
    return form


def _create_submission(form: Form) -> FormSubmission:
    submission = FormSubmission.objects.create(
        form=form,
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    full_name_field = form.fields.get(name="full_name")
    email_field = form.fields.get(name="email")
    FormFieldValue.objects.create(
        submission=submission,
        field=full_name_field,
        field_name="full_name",
        field_label=full_name_field.label,
        value="Alice",
    )
    FormFieldValue.objects.create(
        submission=submission,
        field=email_field,
        field_name="email",
        field_label=email_field.label,
        value="alice@example.com",
    )
    return submission


@pytest.mark.django_db
def test_ensure_default_settings_prevents_snapshot_drift(
    notification_settings_row,
) -> None:
    notification_settings_row.sender_email = "stale@example.com"
    notification_settings_row.save(update_fields=["sender_email", "updated_at"])

    with override_settings(
        QUICKSCALE_NOTIFICATIONS_SENDER_EMAIL="fresh@example.com",
        EMAIL_BACKEND="anymail.backends.resend.EmailBackend",
    ):
        refreshed = ensure_default_settings()

    notification_settings_row.refresh_from_db()
    assert refreshed.sender_email == "fresh@example.com"
    assert refreshed.email_backend == "anymail.backends.resend.EmailBackend"
    assert notification_settings_row.sender_email == "fresh@example.com"


def test_render_notification_requires_declared_context_keys() -> None:
    with pytest.raises(NotificationTemplateError, match="Missing required"):
        render_notification(
            template_key="notifications.generic",
            context={"headline": "Missing body"},
        )


@pytest.mark.django_db
def test_send_notification_tracks_each_recipient_and_sanitizes_provider_metadata(
    notification_settings_row,
    django_capture_on_commit_callbacks,
) -> None:
    del notification_settings_row
    captured_messages: list[tuple[str, list[str], dict[str, str]]] = []

    def fake_mailer(message) -> str:
        captured_messages.append(
            (
                message.to[0],
                list(getattr(message, "tags", [])),
                dict(getattr(message, "metadata", {})),
            )
        )
        return f"provider::{message.to[0]}"

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        message = send_notification(
            template_key="notifications.generic",
            recipients=["Alpha@example.com", "beta@example.com"],
            context={
                "headline": "Welcome aboard",
                "body": "Your account is ready.",
                "secondary_text": "Thanks for trying QuickScale.",
            },
            tags=["auth", "internal-id"],
            metadata={
                "project": "Client Alpha",
                "workflow": "Password Reset",
                "internal_id": "12345",
            },
            mailer=fake_mailer,
        )

    message.refresh_from_db()
    deliveries = list(message.deliveries.order_by("recipient_email"))

    assert len(callbacks) == 1
    assert message.status == NotificationMessage.STATUS_SENT
    assert [delivery.recipient_email for delivery in deliveries] == [
        "alpha@example.com",
        "beta@example.com",
    ]
    assert [delivery.provider_message_id for delivery in deliveries] == [
        "provider::alpha@example.com",
        "provider::beta@example.com",
    ]
    assert captured_messages[0][1] == ["quickscale", "transactional", "auth"]
    assert captured_messages[0][2] == {
        "project": "client-alpha",
        "workflow": "password-reset",
        "template": "notifications-generic",
    }


@pytest.mark.django_db
def test_send_notification_persists_partial_failures_per_recipient(
    notification_settings_row,
    django_capture_on_commit_callbacks,
) -> None:
    del notification_settings_row

    def fake_mailer(message) -> str:
        if message.to[0] == "broken@example.com":
            raise RuntimeError("provider exploded")
        return "provider::ok@example.com"

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        message = send_notification(
            template_key="notifications.generic",
            recipients=["ok@example.com", "broken@example.com"],
            context={"headline": "Partial send", "body": "Test body"},
            mailer=fake_mailer,
        )

    message.refresh_from_db()
    successful = message.deliveries.get(recipient_email="ok@example.com")
    failed = message.deliveries.get(recipient_email="broken@example.com")

    assert len(callbacks) == 1
    assert successful.status == NotificationDelivery.STATUS_SENT
    assert successful.provider_message_id == "provider::ok@example.com"
    assert failed.status == NotificationDelivery.STATUS_FAILED
    assert failed.retry_count == 1
    assert "provider exploded" in failed.failure_reason
    assert message.status == NotificationMessage.STATUS_PARTIAL
    assert "provider exploded" in message.last_error


@pytest.mark.django_db
def test_send_notification_can_dispatch_inline_when_requested(
    notification_settings_row,
) -> None:
    del notification_settings_row

    message = send_notification(
        template_key="notifications.generic",
        recipients=["inline@example.com"],
        context={"headline": "Inline dispatch", "body": "Immediate body"},
        dispatch_after_commit=False,
        mailer=lambda mail: f"inline::{mail.to[0]}",
    )

    message.refresh_from_db()
    delivery = message.deliveries.get()

    assert message.status == NotificationMessage.STATUS_SENT
    assert delivery.status == NotificationDelivery.STATUS_SENT
    assert delivery.provider_message_id == "inline::inline@example.com"


@pytest.mark.django_db
def test_send_notification_rejects_tracking_when_runtime_disabled(
    notification_settings_row,
) -> None:
    del notification_settings_row

    with override_settings(QUICKSCALE_NOTIFICATIONS_ENABLED=False):
        with pytest.raises(NotificationDisabledError, match="disabled"):
            send_notification(
                template_key="notifications.generic",
                recipients=["disabled@example.com"],
                context={"headline": "Disabled", "body": "Do not track this."},
            )

    assert NotificationMessage.objects.count() == 0
    assert NotificationDelivery.objects.count() == 0


@pytest.mark.django_db
def test_forms_notify_submission_tracks_each_recipient_through_notifications(
    notification_settings_row,
    django_capture_on_commit_callbacks,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del notification_settings_row
    form = _create_contact_form(
        slug="tracked-fanout",
        notify_emails="Alpha@example.com, beta@example.com",
    )
    submission = _create_submission(form)
    dispatched_recipients: list[str] = []

    def fake_send(message) -> str:
        recipient = message.to[0]
        dispatched_recipients.append(recipient)
        return f"provider::{recipient}"

    monkeypatch.setattr(
        "quickscale_modules_notifications.services._send_email_message",
        fake_send,
    )

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        notify_submission(submission)

    message = NotificationMessage.objects.get(
        template_key="notifications.forms_submission"
    )
    deliveries = list(message.deliveries.order_by("recipient_email"))

    assert len(callbacks) == 1
    assert dispatched_recipients == ["alpha@example.com", "beta@example.com"]
    assert message.subject == "[Tracked Contact] New submission from Alice"
    assert message.status == NotificationMessage.STATUS_SENT
    assert message.tags_json == ["quickscale", "transactional", "forms"]
    assert message.metadata_json == {
        "template": "notifications-forms-submission",
        "workflow": "form-submission",
    }
    assert [delivery.recipient_email for delivery in deliveries] == [
        "alpha@example.com",
        "beta@example.com",
    ]
    assert [delivery.provider_message_id for delivery in deliveries] == [
        "provider::alpha@example.com",
        "provider::beta@example.com",
    ]
    assert "Name: Alice" in message.rendered_text


@pytest.mark.django_db
def test_forms_submit_keeps_saved_submission_when_tracked_delivery_fails(
    notification_settings_row,
    django_capture_on_commit_callbacks,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del notification_settings_row
    form = _create_contact_form(
        slug="tracked-failure",
        notify_emails="alpha@example.com, broken@example.com",
    )
    client = APIClient()

    def failing_send(message) -> str:
        raise RuntimeError(f"provider exploded for {message.to[0]}")

    monkeypatch.setattr(
        "quickscale_modules_notifications.services._send_email_message",
        failing_send,
    )

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        response = client.post(
            reverse("quickscale_forms:form-submit", kwargs={"slug": form.slug}),
            {"full_name": "Alice", "email": "alice@example.com"},
            format="json",
        )

    submission = FormSubmission.objects.get(form=form)
    message = NotificationMessage.objects.get(
        template_key="notifications.forms_submission"
    )
    deliveries = list(message.deliveries.order_by("recipient_email"))

    assert response.status_code == 201
    assert len(callbacks) == 1
    assert submission.values.filter(field_name="full_name", value="Alice").exists()
    assert message.status == NotificationMessage.STATUS_FAILED
    assert [delivery.recipient_email for delivery in deliveries] == [
        "alpha@example.com",
        "broken@example.com",
    ]
    assert all(
        delivery.status == NotificationDelivery.STATUS_FAILED for delivery in deliveries
    )
    assert all(
        "provider exploded" in delivery.failure_reason for delivery in deliveries
    )


def test_render_notification_rejects_unknown_template_key() -> None:
    with pytest.raises(
        NotificationTemplateError, match="Unknown notification template"
    ):
        render_notification(
            template_key="notifications.unknown",
            context={"headline": "Unknown", "body": "Body"},
        )


@pytest.mark.django_db
def test_dispatch_notification_message_fails_loudly_for_live_backend_without_api_key(
    queued_message,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RESEND_API_KEY", raising=False)

    with override_settings(EMAIL_BACKEND="anymail.backends.resend.EmailBackend"):
        dispatch_notification_message(queued_message.pk)

    queued_message.refresh_from_db()
    assert queued_message.status == NotificationMessage.STATUS_FAILED
    assert "API key environment variable" in queued_message.last_error
    assert (
        queued_message.deliveries.filter(
            status=NotificationDelivery.STATUS_FAILED
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_dispatch_notification_message_rejects_when_runtime_disabled(
    queued_message,
) -> None:
    with override_settings(QUICKSCALE_NOTIFICATIONS_ENABLED=False):
        with pytest.raises(NotificationDisabledError, match="disabled"):
            dispatch_notification_message(queued_message.pk)

    queued_message.refresh_from_db()

    assert queued_message.status == NotificationMessage.STATUS_QUEUED
    assert (
        queued_message.deliveries.filter(
            status=NotificationDelivery.STATUS_QUEUED
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_webhook_ingestion_rejects_when_runtime_disabled(delivery_for_webhook) -> None:
    payload = {
        "id": "evt-disabled",
        "type": "email.delivered",
        "provider_message_id": delivery_for_webhook.provider_message_id,
        "recipient": delivery_for_webhook.recipient_email,
    }
    body = json.dumps(payload).encode("utf-8")
    headers = build_webhook_signature_headers(
        body,
        secret=os.environ["QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET"],
        timestamp=int(time.time()),
    )

    with override_settings(QUICKSCALE_NOTIFICATIONS_ENABLED=False):
        with pytest.raises(NotificationDisabledError, match="disabled"):
            ingest_webhook_event(
                body=body,
                payload=payload,
                signature=headers["X-QuickScale-Notifications-Signature"],
                timestamp=headers["X-QuickScale-Notifications-Timestamp"],
            )

    delivery_for_webhook.refresh_from_db()

    assert delivery_for_webhook.status == NotificationDelivery.STATUS_SENT
    assert (
        NotificationDeliveryEvent.objects.filter(delivery=delivery_for_webhook).count()
        == 0
    )


@pytest.mark.django_db
def test_webhook_signature_rejection_is_explicit(delivery_for_webhook) -> None:
    payload = {
        "id": "evt-1",
        "type": "email.delivered",
        "provider_message_id": delivery_for_webhook.provider_message_id,
        "recipient": delivery_for_webhook.recipient_email,
    }
    body = json.dumps(payload).encode("utf-8")

    with pytest.raises(NotificationWebhookSignatureError, match="invalid"):
        ingest_webhook_event(
            body=body,
            payload=payload,
            signature="sha256=invalid",
            timestamp=str(int(time.time())),
        )


@pytest.mark.django_db
def test_webhook_signature_rejects_expired_timestamps(delivery_for_webhook) -> None:
    payload = {
        "id": "evt-expired",
        "type": "email.delivered",
        "provider_message_id": delivery_for_webhook.provider_message_id,
        "recipient": delivery_for_webhook.recipient_email,
    }
    body = json.dumps(payload).encode("utf-8")
    headers = build_webhook_signature_headers(
        body,
        secret=os.environ["QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET"],
        timestamp=int(time.time()) - 1_000,
    )

    with pytest.raises(NotificationWebhookSignatureError, match="expired"):
        ingest_webhook_event(
            body=body,
            payload=payload,
            signature=headers["X-QuickScale-Notifications-Signature"],
            timestamp=headers["X-QuickScale-Notifications-Timestamp"],
        )


@pytest.mark.django_db
def test_webhook_ingestion_requires_provider_message_id(delivery_for_webhook) -> None:
    payload = {
        "id": "evt-missing-id",
        "type": "email.delivered",
        "recipient": delivery_for_webhook.recipient_email,
    }
    body = json.dumps(payload).encode("utf-8")
    headers = build_webhook_signature_headers(
        body,
        secret=os.environ["QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET"],
        timestamp=int(time.time()),
    )

    with pytest.raises(Exception, match="provider_message_id"):
        ingest_webhook_event(
            body=body,
            payload=payload,
            signature=headers["X-QuickScale-Notifications-Signature"],
            timestamp=headers["X-QuickScale-Notifications-Timestamp"],
        )


@pytest.mark.django_db
def test_webhook_ingestion_is_replay_safe_and_updates_delivery_status(
    delivery_for_webhook,
) -> None:
    payload = {
        "id": "evt-delivered-1",
        "type": "email.delivered",
        "provider_message_id": delivery_for_webhook.provider_message_id,
        "recipient": delivery_for_webhook.recipient_email,
    }
    body = json.dumps(payload).encode("utf-8")
    headers = build_webhook_signature_headers(
        body,
        secret=os.environ["QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET"],
        timestamp=int(time.time()),
    )

    first_result = ingest_webhook_event(
        body=body,
        payload=payload,
        signature=headers["X-QuickScale-Notifications-Signature"],
        timestamp=headers["X-QuickScale-Notifications-Timestamp"],
    )
    second_result = ingest_webhook_event(
        body=body,
        payload=payload,
        signature=headers["X-QuickScale-Notifications-Signature"],
        timestamp=headers["X-QuickScale-Notifications-Timestamp"],
    )

    delivery_for_webhook.refresh_from_db()
    delivery_for_webhook.message.refresh_from_db()

    assert first_result.duplicate is False
    assert second_result.duplicate is True
    assert delivery_for_webhook.status == NotificationDelivery.STATUS_DELIVERED
    assert delivery_for_webhook.message.status == NotificationMessage.STATUS_SENT
    assert (
        NotificationDeliveryEvent.objects.filter(delivery=delivery_for_webhook).count()
        == 1
    )
