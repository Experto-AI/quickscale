"""Tests for notifications module services."""

from __future__ import annotations

import inspect
import json
import time
from typing import Any, cast

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from quickscale_modules_forms.models import (
    Form,
    FormField,
    FormFieldValue,
    FormSubmission,
)
from quickscale_modules_orgs.current_org import set_current_org_id
from quickscale_modules_orgs.models import Organization

from quickscale_modules_forms._email import notify_submission

from quickscale_modules_notifications import services
from quickscale_modules_notifications.models import (
    NotificationDelivery,
    NotificationDeliveryEvent,
    NotificationMessage,
)
from quickscale_modules_notifications.services import (
    NotificationDisabledError,
    NotificationError,
    NotificationSettingsSnapshot,
    NotificationTemplateError,
    NotificationValidationError,
    NotificationWebhookSignatureError,
    build_webhook_signature_headers,
    dispatch_notification_message,
    ensure_default_settings,
    ingest_webhook_event,
    render_notification,
    sanitize_provider_tags,
    send_notification,
)


def _create_contact_form(*, slug: str, notify_emails: str) -> Form:
    system_org = Organization.objects.get_system_org()
    set_current_org_id(system_org.pk)
    form = Form.objects.create(
        title="Tracked Contact",
        slug=slug,
        description="Get in touch.",
        success_message="Thank you, we will be in touch.",
        notify_emails=notify_emails,
        spam_protection_enabled=True,
        organization=system_org,
    )
    FormField.all_objects.create(
        form=form,
        organization=form.organization,
        field_type=FormField.FieldType.TEXT,
        label="Name",
        name="full_name",
        required=True,
        order=1,
    )
    FormField.all_objects.create(
        form=form,
        organization=form.organization,
        field_type=FormField.FieldType.EMAIL,
        label="Email",
        name="email",
        required=True,
        order=2,
    )
    return form


def _create_submission(form: Form) -> FormSubmission:
    submission = FormSubmission.all_objects.create(
        form=form,
        organization=form.organization,
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    full_name_field = FormField.all_objects.get(form=form, name="full_name")
    email_field = FormField.all_objects.get(form=form, name="email")
    FormFieldValue.all_objects.create(
        submission=submission,
        organization=submission.organization,
        field=full_name_field,
        field_name="full_name",
        field_label=full_name_field.label,
        value="Alice",
    )
    FormFieldValue.all_objects.create(
        submission=submission,
        organization=submission.organization,
        field=email_field,
        field_name="email",
        field_label=email_field.label,
        value="alice@example.com",
    )
    return submission


def _org_invitation_context() -> dict[str, str]:
    return {
        "organization_name": "Acme Labs",
        "invitee_email": "invitee@example.com",
        "inviter_name": "Helios Admin",
        "role_display": "Admin",
        "accept_url": (
            "https://example.com/orgs/invitations/"
            "00000000-0000-0000-0000-000000000000/accept/"
        ),
        "expires_at": "2026-05-26T12:00:00+00:00",
    }


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


def test_render_notification_renders_org_invitation_template() -> None:
    context = _org_invitation_context()

    rendered = render_notification(
        template_key="notifications.org_invitation",
        context=context,
    )

    assert rendered.subject == "You're invited to join Acme Labs"
    assert (
        "Helios Admin invited invitee@example.com to join Acme Labs as Admin."
        in rendered.text_body
    )
    assert context["accept_url"] in rendered.text_body
    assert context["expires_at"] in rendered.text_body
    assert "Accept invitation" in rendered.html_body
    assert context["accept_url"] in rendered.html_body


def test_sanitize_provider_tags_matches_noncanonical_allowlist_entries() -> None:
    """An accepted but noncanonical allowlist entry still matches its tag.

    ``apply`` normalizes tag lists, but a value that reached settings by
    another route passes the generic check unaltered; the comparison set must
    canonicalize the same way each candidate does, or the tag is silently
    dropped.
    """
    with override_settings(
        QUICKSCALE_NOTIFICATIONS_DEFAULT_TAGS=["VIP"],
        QUICKSCALE_NOTIFICATIONS_ALLOWED_TAGS=["VIP"],
    ):
        snapshot = NotificationSettingsSnapshot.from_settings()
        assert sanitize_provider_tags(["VIP"], settings_snapshot=snapshot) == ["vip"]


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
            about_users=[],
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
    assert message.status == NotificationMessage.Status.SENT
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
def test_send_notification_supports_org_invitation_template(
    notification_settings_row,
    django_capture_on_commit_callbacks,
) -> None:
    del notification_settings_row
    context = _org_invitation_context()

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        message = send_notification(
            template_key="notifications.org_invitation",
            recipients=["Invitee@Example.com"],
            context=context,
            about_users=[],
            tags=["auth"],
            metadata={"workflow": "org-invitation"},
            mailer=lambda mail: f"provider::{mail.to[0]}",
        )

    message.refresh_from_db()
    delivery = message.deliveries.get()

    assert len(callbacks) == 1
    assert message.subject == "You're invited to join Acme Labs"
    assert message.status == NotificationMessage.Status.SENT
    assert message.tags_json == ["quickscale", "transactional", "auth"]
    assert message.metadata_json == {
        "template": "notifications-org-invitation",
        "workflow": "org-invitation",
    }
    assert delivery.recipient_email == "invitee@example.com"
    assert delivery.status == NotificationDelivery.Status.SENT
    assert delivery.provider_message_id == "provider::invitee@example.com"
    assert "Accept invitation" in message.rendered_html


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
            about_users=[],
            mailer=fake_mailer,
        )

    message.refresh_from_db()
    successful = message.deliveries.get(recipient_email="ok@example.com")
    failed = message.deliveries.get(recipient_email="broken@example.com")

    assert len(callbacks) == 1
    assert successful.status == NotificationDelivery.Status.SENT
    assert successful.provider_message_id == "provider::ok@example.com"
    assert failed.status == NotificationDelivery.Status.FAILED
    assert failed.retry_count == 1
    assert "provider exploded" in failed.failure_reason
    assert message.status == NotificationMessage.Status.PARTIAL
    assert "provider exploded" in message.last_error


@pytest.mark.django_db
def test_rolled_back_send_notification_dispatches_nothing(
    notification_settings_row,
    django_capture_on_commit_callbacks,
) -> None:
    """Rule 21: a rolled-back write dispatches no delivery; a commit does."""
    from django.db import transaction

    del notification_settings_row
    dispatched: list[str] = []

    def fake_mailer(mail) -> str:
        dispatched.append(mail.to[0])
        return f"provider::{mail.to[0]}"

    class _Rollback(Exception):
        pass

    with pytest.raises(_Rollback):
        with transaction.atomic():
            send_notification(
                template_key="notifications.generic",
                recipients=["rollback@example.com"],
                context={"headline": "Rollback", "body": "Discard me."},
                about_users=[],
                mailer=fake_mailer,
            )
            raise _Rollback

    assert dispatched == [], "a rolled-back write dispatches no delivery"
    assert not NotificationMessage.objects.exists(), (
        "a rolled-back write records no tracked notification"
    )

    # Positive control: the same write without a rollback dispatches, so the
    # negative assertion is not vacuous.
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        send_notification(
            template_key="notifications.generic",
            recipients=["rollback@example.com"],
            context={"headline": "Commit", "body": "Send me."},
            about_users=[],
            mailer=fake_mailer,
        )

    assert len(callbacks) == 1
    assert dispatched == ["rollback@example.com"]


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
                about_users=[],
            )

    assert NotificationMessage.objects.count() == 0
    assert NotificationDelivery.objects.count() == 0


@pytest.mark.django_db
def test_send_notification_bounds_an_overlong_rendered_subject(
    notification_settings_row,
    django_capture_on_commit_callbacks,
) -> None:
    """A valid long context renders a subject the message row can still store."""
    del notification_settings_row

    with django_capture_on_commit_callbacks(execute=True):
        message = send_notification(
            template_key="notifications.generic",
            recipients=["long@example.com"],
            context={"headline": "H" * 300, "body": "Body"},
            about_users=[],
            mailer=lambda mail: f"provider::{mail.to[0]}",
        )

    message.refresh_from_db()

    assert message.subject == "H" * 255
    assert message.deliveries.get().status == NotificationDelivery.Status.SENT


def test_send_notification_requires_the_about_users_keyword() -> None:
    """Rule 50: the persons link is a required keyword with no default."""
    parameter = inspect.signature(send_notification).parameters["about_users"]

    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inspect.Parameter.empty


@pytest.mark.django_db
def test_send_notification_stores_the_person_link(
    notification_settings_row,
    django_capture_on_commit_callbacks,
) -> None:
    """Rule 50: notifications stores the ids where anonymization reads them."""
    del notification_settings_row
    user_model = get_user_model()
    first = user_model.objects.create_user(
        username="link-first",
        email="link-first@example.com",
        password="LinkFirst1!",
    )
    second = user_model.objects.create_user(
        username="link-second",
        email="link-second@example.com",
        password="LinkSecond1!",
    )

    with django_capture_on_commit_callbacks(execute=True):
        message = send_notification(
            template_key="notifications.generic",
            recipients=["archive@example.com"],
            context={"headline": "Linked", "body": "Body"},
            about_users=[first, second, first],
            mailer=lambda mail: f"provider::{mail.to[0]}",
        )

    message.refresh_from_db()
    assert message.about_user_ids_json == [str(first.pk), str(second.pk)]


@pytest.mark.django_db
def test_send_notification_accepts_an_explicit_empty_about_users(
    notification_settings_row,
    django_capture_on_commit_callbacks,
) -> None:
    """A message about no platform user stores an empty link list."""
    del notification_settings_row

    with django_capture_on_commit_callbacks(execute=True):
        message = send_notification(
            template_key="notifications.generic",
            recipients=["archive@example.com"],
            context={"headline": "Unlinked", "body": "Body"},
            about_users=[],
            mailer=lambda mail: f"provider::{mail.to[0]}",
        )

    message.refresh_from_db()
    assert message.about_user_ids_json == []


@pytest.mark.django_db
def test_send_notification_rejects_an_unsaved_about_user(
    notification_settings_row,
) -> None:
    """Rule 50: the link needs a saved person, not an unsaved model."""
    del notification_settings_row
    user_model = get_user_model()

    with pytest.raises(NotificationValidationError, match="saved user"):
        send_notification(
            template_key="notifications.generic",
            recipients=["archive@example.com"],
            context={"headline": "Hi", "body": "Body"},
            about_users=[user_model(username="unsaved-link")],
        )


def test_send_notification_rejects_a_non_sequence_about_users() -> None:
    """Rule 50: about_users is a sequence, not a single user or None."""
    with pytest.raises(NotificationValidationError, match="sequence"):
        services.send_notification(
            template_key="notifications.generic",
            recipients=["archive@example.com"],
            context={"headline": "Hi", "body": "Body"},
            about_users=cast(Any, None),
        )


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
        "quickscale_modules_notifications._delivery._send_email_message",
        fake_send,
    )

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        notify_submission(submission)

    message = NotificationMessage.objects.get(
        template_key="notifications.forms_submission"
    )
    deliveries = list(message.deliveries.order_by("recipient_email"))

    # Forms schedules the send on commit; notifications schedules the delivery
    # of the message that send creates — two captured callbacks in the chain.
    assert len(callbacks) >= 1
    assert dispatched_recipients == ["alpha@example.com", "beta@example.com"]
    assert message.subject == "[Tracked Contact] New submission from Alice"
    assert message.status == NotificationMessage.Status.SENT
    assert message.tags_json == ["quickscale", "transactional", "forms"]
    assert message.metadata_json == {
        "template": "notifications-forms-submission",
        "workflow": "form-submission",
    }
    # Rule 50: forms states explicitly that the message is about no user.
    assert message.about_user_ids_json == []
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
        "quickscale_modules_notifications._delivery._send_email_message",
        failing_send,
    )

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        response = client.post(
            reverse("quickscale_forms:form_submit", kwargs={"slug": form.slug}),
            {"full_name": "Alice", "email": "alice@example.com"},
            format="json",
        )

    submission = FormSubmission.all_objects.get(form=form)
    message = NotificationMessage.objects.get(
        template_key="notifications.forms_submission"
    )
    deliveries = list(message.deliveries.order_by("recipient_email"))

    assert response.status_code == 201
    # Forms schedules the send on commit; notifications schedules the delivery
    # of the message that send creates — two captured callbacks in the chain.
    assert len(callbacks) >= 1
    assert submission.values.filter(field_name="full_name", value="Alice").exists()
    assert message.status == NotificationMessage.Status.FAILED
    assert [delivery.recipient_email for delivery in deliveries] == [
        "alpha@example.com",
        "broken@example.com",
    ]
    assert all(
        delivery.status == NotificationDelivery.Status.FAILED for delivery in deliveries
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
) -> None:
    with override_settings(
        EMAIL_BACKEND="anymail.backends.resend.EmailBackend",
        QUICKSCALE_NOTIFICATIONS_SENDER_EMAIL="noreply@example.com",
        QUICKSCALE_NOTIFICATIONS_RESEND_API_KEY="",
    ):
        dispatch_notification_message(queued_message.pk)

    queued_message.refresh_from_db()
    assert queued_message.status == NotificationMessage.Status.FAILED
    assert "API key environment variable" in queued_message.last_error
    assert (
        queued_message.deliveries.filter(
            status=NotificationDelivery.Status.FAILED
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_dispatch_notification_message_fails_loudly_for_live_backend_with_placeholder_sender(
    queued_message,
) -> None:
    with override_settings(
        EMAIL_BACKEND="anymail.backends.resend.EmailBackend",
        QUICKSCALE_NOTIFICATIONS_SENDER_EMAIL="noreply@example.com",
        QUICKSCALE_NOTIFICATIONS_RESEND_API_KEY="configured-live-key",
    ):
        dispatch_notification_message(queued_message.pk)

    queued_message.refresh_from_db()
    assert queued_message.status == NotificationMessage.Status.FAILED
    assert "placeholder sender email noreply@example.com" in queued_message.last_error
    assert (
        queued_message.deliveries.filter(
            status=NotificationDelivery.Status.FAILED
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_dispatch_notification_message_allows_placeholder_sender_on_console_backend(
    queued_message,
) -> None:
    dispatch_notification_message(
        queued_message.pk,
        mailer=lambda message: f"console::{message.to[0]}",
    )

    queued_message.refresh_from_db()
    deliveries = list(queued_message.deliveries.order_by("recipient_email"))

    assert queued_message.status == NotificationMessage.Status.SENT
    assert [delivery.provider_message_id for delivery in deliveries] == [
        "console::alpha@example.com",
        "console::beta@example.com",
    ]


@pytest.mark.django_db
def test_dispatch_notification_message_rejects_when_runtime_disabled(
    queued_message,
) -> None:
    with override_settings(QUICKSCALE_NOTIFICATIONS_ENABLED=False):
        with pytest.raises(NotificationDisabledError, match="disabled"):
            dispatch_notification_message(queued_message.pk)

    queued_message.refresh_from_db()

    assert queued_message.status == NotificationMessage.Status.QUEUED
    assert (
        queued_message.deliveries.filter(
            status=NotificationDelivery.Status.QUEUED
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
        secret=settings.QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET,
        timestamp=int(time.time()),
    )

    with override_settings(QUICKSCALE_NOTIFICATIONS_ENABLED=False):
        with pytest.raises(NotificationDisabledError, match="disabled"):
            ingest_webhook_event(
                body=body,
                signature=headers["X-QuickScale-Notifications-Signature"],
                timestamp=headers["X-QuickScale-Notifications-Timestamp"],
            )

    delivery_for_webhook.refresh_from_db()

    assert delivery_for_webhook.status == NotificationDelivery.Status.SENT
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
        secret=settings.QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET,
        timestamp=int(time.time()) - 1_000,
    )

    with pytest.raises(NotificationWebhookSignatureError, match="expired"):
        ingest_webhook_event(
            body=body,
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
        secret=settings.QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET,
        timestamp=int(time.time()),
    )

    with pytest.raises(Exception, match="provider_message_id"):
        ingest_webhook_event(
            body=body,
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
        secret=settings.QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET,
        timestamp=int(time.time()),
    )

    first_result = ingest_webhook_event(
        body=body,
        signature=headers["X-QuickScale-Notifications-Signature"],
        timestamp=headers["X-QuickScale-Notifications-Timestamp"],
    )
    second_result = ingest_webhook_event(
        body=body,
        signature=headers["X-QuickScale-Notifications-Signature"],
        timestamp=headers["X-QuickScale-Notifications-Timestamp"],
    )

    delivery_for_webhook.refresh_from_db()
    delivery_for_webhook.message.refresh_from_db()

    assert first_result.duplicate is False
    assert second_result.duplicate is True
    assert delivery_for_webhook.status == NotificationDelivery.Status.DELIVERED
    assert delivery_for_webhook.message.status == NotificationMessage.Status.SENT
    assert (
        NotificationDeliveryEvent.objects.filter(delivery=delivery_for_webhook).count()
        == 1
    )


def test_services_publishes_exactly_the_declared_surface() -> None:
    """Rule 23: ``__all__`` is the module's declared public service surface."""
    assert services.__all__ == [
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
    for name in services.__all__:
        assert hasattr(services, name)


def test_send_notification_rejects_invalid_recipients_with_module_error() -> None:
    """Rule 23: invalid input answers through the module's NotificationError base."""
    with pytest.raises(NotificationValidationError, match="Invalid recipient"):
        services.send_notification(
            template_key="notifications.generic",
            recipients=["not-an-email"],
            context={"headline": "Hi", "body": "Body"},
            about_users=[],
        )


@pytest.mark.django_db
def test_dispatch_notification_message_translates_missing_message() -> None:
    """Rule 23: a stale message id answers through the module's error base."""
    with pytest.raises(NotificationError, match="does not exist"):
        services.dispatch_notification_message(999999)


def test_is_enabled_reads_the_module_enabled_setting() -> None:
    """Rule 1: ``is_enabled()`` reports ``QUICKSCALE_NOTIFICATIONS_ENABLED`` both ways."""
    with override_settings(QUICKSCALE_NOTIFICATIONS_ENABLED=True):
        assert services.is_enabled() is True
    with override_settings(QUICKSCALE_NOTIFICATIONS_ENABLED=False):
        assert services.is_enabled() is False
