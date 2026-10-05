"""Tests for notifications' account-anonymization executor."""

from __future__ import annotations

from typing import Any

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model

from quickscale_modules_notifications._anonymization import anonymize_account
from quickscale_modules_notifications.models import (
    NotificationDelivery,
    NotificationDeliveryEvent,
    NotificationMessage,
)


def _user(email: str) -> Any:
    return get_user_model().objects.create_user(
        username="qs-anon-user",
        email=email,
        password="PersonPass123!",
    )


def _message(**overrides: Any) -> NotificationMessage:
    fields: dict[str, Any] = {
        "template_key": "notifications.generic",
        "subject": "Hello alpha@example.com",
        "from_email": "QuickScale <noreply@example.com>",
        "reply_to_email": "",
        "rendered_text": "Body for alpha@example.com",
        "rendered_html": "<p>Body for alpha@example.com</p>",
        "context_json": {"email": "alpha@example.com"},
        "last_error": "alpha@example.com bounced",
        "status": NotificationMessage.Status.FAILED,
    }
    fields.update(overrides)
    return NotificationMessage.objects.create(**fields)


@pytest.mark.django_db
def test_anonymize_scrubs_a_sole_recipient_message_delivery_and_event() -> None:
    """A message sent only to the person is redacted with its tracking rows."""
    user = _user("alpha@example.com")
    message = _message()
    delivery = NotificationDelivery.objects.create(
        message=message,
        recipient_email="alpha@example.com",
        failure_reason="alpha@example.com mailbox full",
    )
    event = NotificationDeliveryEvent.objects.create(
        delivery=delivery,
        idempotency_key="abc123",
        event_type="bounced",
        status_after="bounced",
        payload_json={
            "to": "alpha@example.com",
            "detail": {"contact": "Reach alpha@example.com now"},
        },
    )

    anonymize_account(user, "Alpha@Example.com", "Alpha Person", user.get_username())

    deleted_address = f"deleted-{user.pk}@invalid"
    delivery.refresh_from_db()
    event.refresh_from_db()
    message.refresh_from_db()
    assert delivery.recipient_email == deleted_address
    assert delivery.failure_reason == "[redacted]"
    assert event.payload_json == {
        "to": deleted_address,
        "detail": {"contact": f"Reach {deleted_address} now"},
    }
    assert message.subject == "[redacted]"
    assert message.rendered_text == "[redacted]"
    assert message.rendered_html == "[redacted]"
    assert message.context_json == {}
    assert message.last_error == "[redacted]"


@pytest.mark.django_db
def test_anonymize_keeps_a_shared_message_and_other_recipients(queued_message) -> None:
    """Shared content is not one person's record; only their delivery is scrubbed."""
    user = _user("alpha@example.com")
    alpha = queued_message.deliveries.get(recipient_email="alpha@example.com")
    beta = queued_message.deliveries.get(recipient_email="beta@example.com")

    anonymize_account(user, "alpha@example.com", "Alpha Person", user.get_username())

    queued_message.refresh_from_db()
    alpha.refresh_from_db()
    beta.refresh_from_db()
    assert queued_message.subject == "Queued message"
    assert queued_message.rendered_text == "Plain text body"
    assert alpha.recipient_email == f"deleted-{user.pk}@invalid"
    assert beta.recipient_email == "beta@example.com"


@pytest.mark.django_db
def test_anonymize_redacts_identity_from_a_shared_message() -> None:
    """A shared message keeps its content but loses the person's identity."""
    user = _user("alpha@example.com")
    message = _message(
        subject="Update for Alpha Person",
        rendered_text="Hi Alpha Person (alpha@example.com)",
        rendered_html="<p>Alpha Person alpha@example.com</p>",
        context_json={
            "name": "Alpha Person",
            "email": "alpha@example.com",
            "body": "shared body",
        },
        last_error="alpha@example.com bounced",
    )
    NotificationDelivery.objects.create(
        message=message, recipient_email="alpha@example.com"
    )
    beta = NotificationDelivery.objects.create(
        message=message, recipient_email="beta@example.com"
    )

    anonymize_account(user, "alpha@example.com", "Alpha Person", user.get_username())

    message.refresh_from_db()
    beta.refresh_from_db()
    deleted_address = f"deleted-{user.pk}@invalid"
    assert message.subject == "Update for [redacted]"
    assert message.rendered_text == f"Hi [redacted] ({deleted_address})"
    assert message.rendered_html == f"<p>[redacted] {deleted_address}</p>"
    assert message.context_json == {
        "name": "[redacted]",
        "email": deleted_address,
        "body": "shared body",
    }
    assert message.last_error == f"{deleted_address} bounced"
    assert beta.recipient_email == "beta@example.com"


@pytest.mark.django_db
def test_anonymize_redacts_an_html_escaped_name_in_a_shared_message() -> None:
    """A rendered escaped spelling is the same identity as the raw name."""
    user = _user("alpha@example.com")
    message = _message(
        subject="Hi Anne O&#x27;Connor",
        rendered_text="Anne O&#x27;Connor replied",
        rendered_html="<p>Anne O&#x27;Connor replied</p>",
        context_json={"author": "Anne O&#x27;Connor", "body": "shared"},
        last_error="",
    )
    NotificationDelivery.objects.create(
        message=message, recipient_email="alpha@example.com"
    )
    NotificationDelivery.objects.create(
        message=message, recipient_email="beta@example.com"
    )

    anonymize_account(user, "alpha@example.com", "Anne O'Connor", user.get_username())

    message.refresh_from_db()
    assert message.subject == "Hi [redacted]"
    assert message.rendered_text == "[redacted] replied"
    assert message.rendered_html == "<p>[redacted] replied</p>"
    assert message.context_json == {"author": "[redacted]", "body": "shared"}


@pytest.mark.django_db
def test_anonymize_redacts_identity_bearing_context_keys() -> None:
    """A JSON key holding the person's address is redacted too."""
    user = _user("alpha@example.com")
    message = _message(
        subject="Shared",
        rendered_text="Body",
        context_json={"alpha@example.com": "delivery info", "body": "shared"},
        last_error="",
    )
    NotificationDelivery.objects.create(
        message=message, recipient_email="alpha@example.com"
    )
    NotificationDelivery.objects.create(
        message=message, recipient_email="beta@example.com"
    )

    anonymize_account(user, "alpha@example.com", "Alpha Person", user.get_username())

    message.refresh_from_db()
    assert message.context_json == {
        f"deleted-{user.pk}@invalid": "delivery info",
        "body": "shared",
    }
    assert message.subject == "Shared"


@pytest.mark.django_db
def test_anonymize_leaves_an_overlapping_address_untouched() -> None:
    """An address merely containing the person's address is not theirs."""
    user = _user("test@example.com")
    message = _message(
        subject="Protest",
        rendered_text="Contact protest@example.com",
        context_json={"protest@example.com": "other person"},
        last_error="protest@example.com bounced",
    )
    NotificationDelivery.objects.create(
        message=message, recipient_email="test@example.com"
    )
    NotificationDelivery.objects.create(
        message=message, recipient_email="beta@example.com"
    )

    anonymize_account(user, "test@example.com", "", user.get_username())

    message.refresh_from_db()
    assert message.rendered_text == "Contact protest@example.com"
    assert message.context_json == {"protest@example.com": "other person"}
    assert message.last_error == "protest@example.com bounced"


@pytest.mark.django_db
def test_anonymize_redacts_an_invitation_message_sent_to_someone_else(
    notification_settings_row, django_capture_on_commit_callbacks
) -> None:
    """The shipped invitation path: the inviter's name goes, the invitee stays."""
    del notification_settings_row
    from quickscale_modules_notifications.services import send_notification

    inviter = get_user_model().objects.create_user(
        username="helios",
        email="helios@example.com",
        password="HeliosPass123!",
        first_name="Helios",
        last_name="Admin",
    )
    context = {
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
    with django_capture_on_commit_callbacks(execute=True):
        message = send_notification(
            template_key="notifications.org_invitation",
            recipients=["invitee@example.com"],
            context=context,
            tags=["auth"],
            metadata={"workflow": "org-invitation"},
            mailer=lambda mail: f"provider::{mail.to[0]}",
        )

    anonymize_account(
        inviter, "helios@example.com", "Helios Admin", inviter.get_username()
    )

    message.refresh_from_db()
    delivery = message.deliveries.get()
    assert delivery.recipient_email == "invitee@example.com"
    assert "Helios Admin" not in message.rendered_text
    assert "Helios Admin" not in message.rendered_html
    assert message.context_json["inviter_name"] == "[redacted]"
    assert message.context_json["invitee_email"] == "invitee@example.com"


@pytest.mark.django_db
def test_anonymize_redacts_an_html_escaped_address() -> None:
    """A rendered escaped address is the same identity as the raw address."""
    from quickscale_modules_notifications.services import render_notification

    user = _user("o'connor@example.com")
    rendered = render_notification(
        template_key="notifications.generic",
        context={"headline": "Statement", "body": "o'connor@example.com"},
    )
    message = _message(
        subject=rendered.subject,
        rendered_text=rendered.text_body,
        rendered_html=rendered.html_body,
        context_json={"email": "o'connor@example.com"},
        last_error="",
    )
    NotificationDelivery.objects.create(
        message=message, recipient_email="o'connor@example.com"
    )
    NotificationDelivery.objects.create(
        message=message, recipient_email="beta@example.com"
    )

    anonymize_account(user, "o'connor@example.com", "", user.get_username())

    message.refresh_from_db()
    deleted_address = f"deleted-{user.pk}@invalid"
    assert deleted_address in message.rendered_text
    assert "&#x27;" not in message.rendered_html
    assert deleted_address in message.rendered_html
    assert message.context_json == {"email": deleted_address}


@pytest.mark.django_db
def test_anonymize_preserves_an_overlapping_escaped_address() -> None:
    """A rendered escaped address inside another address is not rewritten."""
    from quickscale_modules_notifications.services import render_notification

    user = _user("o'connor@example.com")
    rendered = render_notification(
        template_key="notifications.generic",
        context={"headline": "Other", "body": "proo'connor@example.com"},
    )
    message = _message(
        subject=rendered.subject,
        rendered_text=rendered.text_body,
        rendered_html=rendered.html_body,
        context_json={"body": "proo'connor@example.com"},
        last_error="",
    )
    NotificationDelivery.objects.create(
        message=message, recipient_email="o'connor@example.com"
    )
    NotificationDelivery.objects.create(
        message=message, recipient_email="beta@example.com"
    )

    anonymize_account(user, "o'connor@example.com", "", user.get_username())

    message.refresh_from_db()
    assert "proo&#x27;connor@example.com" in message.rendered_html
    assert "proo&#x27;connor@example.com" in message.rendered_text
    assert message.context_json == {"body": "proo'connor@example.com"}


@pytest.mark.django_db
def test_anonymize_redacts_an_address_whose_local_part_starts_with_a_quote() -> None:
    """A quote that belongs to the address is not treated as surrounding text."""
    user = _user("ann@example.com")
    address = "'testuser@example.com"
    message = _message(
        subject="Address",
        rendered_text=f"Contact {address} now",
        rendered_html="",
        context_json={"note": address},
        last_error="",
    )
    NotificationDelivery.objects.create(message=message, recipient_email=address)
    NotificationDelivery.objects.create(
        message=message, recipient_email="beta@example.com"
    )

    anonymize_account(user, address, "", "ann")

    message.refresh_from_db()
    deleted_address = f"deleted-{user.pk}@invalid"
    assert message.rendered_text == f"Contact {deleted_address} now"
    assert message.context_json == {"note": deleted_address}


@pytest.mark.django_db
def test_anonymize_leaves_unrelated_text_with_a_short_name_untouched() -> None:
    """A short full name does not rewrite unrelated words or addresses."""
    user = _user("ann@example.com")
    message = _message(
        subject="Annual announcement for Joanne",
        rendered_text="Annual announcement for Joanne (joanne@example.com)",
        rendered_html="",
        context_json={"body": "Annual announcement for Joanne"},
        last_error="",
    )
    NotificationDelivery.objects.create(
        message=message, recipient_email="joanne@example.com"
    )

    anonymize_account(user, "ann@example.com", "Ann", "qs-anon-user")

    message.refresh_from_db()
    assert message.subject == "Annual announcement for Joanne"
    assert (
        message.rendered_text == "Annual announcement for Joanne (joanne@example.com)"
    )
    assert message.context_json == {"body": "Annual announcement for Joanne"}


@pytest.mark.django_db
def test_anonymize_redacts_a_username_only_inviters_message() -> None:
    """A user with no full name is matched by the username the display falls to."""
    inviter = get_user_model().objects.create_user(
        username="helios",
        email="helios@example.com",
        password="HeliosPass123!",
    )
    message = _message(
        subject="You're invited to join Acme Labs",
        rendered_text="helios invited invitee@example.com to join Acme Labs as Admin.",
        rendered_html="<p>helios invited invitee@example.com to join Acme Labs.</p>",
        context_json={"inviter_name": "helios", "invitee_email": "invitee@example.com"},
        last_error="",
    )
    NotificationDelivery.objects.create(
        message=message, recipient_email="invitee@example.com"
    )

    anonymize_account(inviter, "helios@example.com", "", "helios")

    message.refresh_from_db()
    assert "helios" not in message.rendered_text
    assert "helios" not in message.rendered_html
    assert message.context_json["inviter_name"] == "[redacted]"
    assert message.context_json["invitee_email"] == "invitee@example.com"


@pytest.mark.django_db
def test_anonymize_preserves_an_entity_continued_escaped_address() -> None:
    """An escaped entity continuing another address's local part is preserved."""
    from quickscale_modules_notifications.services import render_notification

    user = _user("o'connor@example.com")
    other_address = "x&o'connor@example.com"
    rendered = render_notification(
        template_key="notifications.generic",
        context={"headline": "Other", "body": other_address},
    )
    message = _message(
        subject=rendered.subject,
        rendered_text=rendered.text_body,
        rendered_html=rendered.html_body,
        context_json={"body": other_address},
        last_error="",
    )
    NotificationDelivery.objects.create(
        message=message, recipient_email="o'connor@example.com"
    )
    NotificationDelivery.objects.create(
        message=message, recipient_email="beta@example.com"
    )

    anonymize_account(user, "o'connor@example.com", "", user.get_username())

    message.refresh_from_db()
    assert "x&amp;o&#x27;connor@example.com" in message.rendered_html
    assert message.context_json == {"body": other_address}


@pytest.mark.django_db
def test_anonymize_preserves_other_addresses_when_redacting_names() -> None:
    """A name or username is never replaced inside another complete address."""
    user = _user("ann@example.com")
    message = _message(
        subject="Names",
        rendered_text=("Ann and helios: ann.smith@example.com / helios@example.net"),
        rendered_html="",
        context_json={
            "body": "Ann and helios: ann.smith@example.com / helios@example.net"
        },
        last_error="",
    )
    NotificationDelivery.objects.create(
        message=message, recipient_email="joanne@example.com"
    )

    anonymize_account(user, "ann@example.com", "Ann", "helios")

    message.refresh_from_db()
    assert message.rendered_text == (
        "[redacted] and [redacted]: ann.smith@example.com / helios@example.net"
    )
    assert message.context_json == {
        "body": (
            "[redacted] and [redacted]: ann.smith@example.com / helios@example.net"
        )
    }


@pytest.mark.django_db
def test_anonymize_redacts_a_quoted_apostrophe_address() -> None:
    """Ordinary quoting around an address that starts with a quote still matches."""
    user = _user("ann@example.com")
    address = "'testuser@example.com"
    message = _message(
        subject="Quoted",
        rendered_text=f"Contact '{address}' now",
        rendered_html="",
        context_json={"note": f"'{address}'"},
        last_error="",
    )
    NotificationDelivery.objects.create(message=message, recipient_email=address)
    NotificationDelivery.objects.create(
        message=message, recipient_email="beta@example.com"
    )

    anonymize_account(user, address, "", "ann")

    message.refresh_from_db()
    deleted_address = f"deleted-{user.pk}@invalid"
    assert message.rendered_text == f"Contact '{deleted_address}' now"
    assert message.context_json == {"note": f"'{deleted_address}'"}


@pytest.mark.django_db
def test_anonymize_preserves_an_escaped_unrelated_address_when_redacting_names() -> (
    None
):
    """An escaped unrelated address keeps its local part when a name goes."""
    from quickscale_modules_notifications.services import render_notification

    user = _user("ann@example.com")
    other_address = "ann&smith@example.com"
    rendered = render_notification(
        template_key="notifications.generic",
        context={"headline": "Other", "body": f"Ann wrote to {other_address}"},
    )
    message = _message(
        subject=rendered.subject,
        rendered_text=rendered.text_body,
        rendered_html=rendered.html_body,
        context_json={"body": f"Ann wrote to {other_address}"},
        last_error="",
    )
    NotificationDelivery.objects.create(
        message=message, recipient_email="joanne@example.com"
    )

    anonymize_account(user, "ann@example.com", "Ann", "qs-anon-user")

    message.refresh_from_db()
    assert "ann&amp;smith@example.com" in message.rendered_html
    assert "ann&amp;smith@example.com" in message.rendered_text
    assert message.context_json == {"body": f"[redacted] wrote to {other_address}"}


@pytest.mark.django_db
def test_anonymize_preserves_an_ampersand_leading_unrelated_address() -> None:
    """An address starting with a rendered ampersand is not truncated."""
    from quickscale_modules_notifications.services import render_notification

    user = _user("o'connor@example.com")
    other_address = "&o'connor@example.com"
    rendered = render_notification(
        template_key="notifications.generic",
        context={"headline": "Other", "body": f"Contact {other_address} now"},
    )
    message = _message(
        subject=rendered.subject,
        rendered_text=rendered.text_body,
        rendered_html=rendered.html_body,
        context_json={"body": f"Contact {other_address} now"},
        last_error="",
    )
    NotificationDelivery.objects.create(
        message=message, recipient_email="o'connor@example.com"
    )
    NotificationDelivery.objects.create(
        message=message, recipient_email="beta@example.com"
    )

    anonymize_account(user, "o'connor@example.com", "", user.get_username())

    message.refresh_from_db()
    assert "&amp;o&#x27;connor@example.com" in message.rendered_html
    assert message.context_json == {"body": f"Contact {other_address} now"}


@pytest.mark.django_db
def test_anonymize_preserves_an_ampersand_behind_quote_entities() -> None:
    """The whole entity chain is walked, so a deep ampersand still continues."""
    from quickscale_modules_notifications.services import render_notification

    user = _user("o'connor@example.com")
    other_address = "&''''o'connor@example.com"
    rendered = render_notification(
        template_key="notifications.generic",
        context={"headline": "Other", "body": f"Contact {other_address} now"},
    )
    message = _message(
        subject=rendered.subject,
        rendered_text=rendered.text_body,
        rendered_html=rendered.html_body,
        context_json={"body": f"Contact {other_address} now"},
        last_error="",
    )
    NotificationDelivery.objects.create(
        message=message, recipient_email="o'connor@example.com"
    )
    NotificationDelivery.objects.create(
        message=message, recipient_email="beta@example.com"
    )

    anonymize_account(user, "o'connor@example.com", "", user.get_username())

    message.refresh_from_db()
    assert "&amp;&#x27;&#x27;&#x27;&#x27;o&#x27;connor@example.com" in (
        message.rendered_html
    )
    assert message.context_json == {"body": f"Contact {other_address} now"}


@pytest.mark.django_db
def test_anonymize_redacts_a_quoted_escaped_apostrophe_address() -> None:
    """A rendered quotation delimiter is not mistaken for a local part."""
    from quickscale_modules_notifications.services import render_notification

    user = _user("o'connor@example.com")
    rendered = render_notification(
        template_key="notifications.generic",
        context={"headline": "Quoted", "body": "Contact 'o'connor@example.com' now"},
    )
    message = _message(
        subject=rendered.subject,
        rendered_text=rendered.text_body,
        rendered_html=rendered.html_body,
        context_json={"body": "Contact 'o'connor@example.com' now"},
        last_error="",
    )
    NotificationDelivery.objects.create(
        message=message, recipient_email="o'connor@example.com"
    )
    NotificationDelivery.objects.create(
        message=message, recipient_email="beta@example.com"
    )

    anonymize_account(user, "o'connor@example.com", "", user.get_username())

    message.refresh_from_db()
    deleted_address = f"deleted-{user.pk}@invalid"
    assert "o&#x27;connor" not in message.rendered_html
    assert deleted_address in message.rendered_html


@pytest.mark.django_db
def test_anonymize_redacts_a_quoted_escaped_leading_apostrophe_address() -> None:
    """Quoting around an escaped leading-apostrophe address still matches."""
    from quickscale_modules_notifications.services import render_notification

    user = _user("ann@example.com")
    address = "'testuser@example.com"
    rendered = render_notification(
        template_key="notifications.generic",
        context={"headline": "Quoted", "body": f"Contact '{address}' now"},
    )
    message = _message(
        subject=rendered.subject,
        rendered_text=rendered.text_body,
        rendered_html=rendered.html_body,
        context_json={"body": f"Contact '{address}' now"},
        last_error="",
    )
    NotificationDelivery.objects.create(message=message, recipient_email=address)
    NotificationDelivery.objects.create(
        message=message, recipient_email="beta@example.com"
    )

    anonymize_account(user, address, "", "ann")

    message.refresh_from_db()
    deleted_address = f"deleted-{user.pk}@invalid"
    assert "testuser@example.com" not in message.rendered_html
    assert deleted_address in message.rendered_html


@pytest.mark.django_db
def test_anonymize_redacts_a_quoted_address_in_free_text() -> None:
    """Quoting in free text does not hide the person's address."""
    user = _user("test@example.com")
    message = _message(
        subject="Quoted",
        rendered_text="Reach 'test@example.com' now",
        rendered_html="",
        context_json={"note": 'contact "test@example.com"'},
        last_error="",
    )
    NotificationDelivery.objects.create(
        message=message, recipient_email="test@example.com"
    )
    NotificationDelivery.objects.create(
        message=message, recipient_email="beta@example.com"
    )

    anonymize_account(user, "test@example.com", "", user.get_username())

    message.refresh_from_db()
    deleted_address = f"deleted-{user.pk}@invalid"
    assert message.rendered_text == f"Reach '{deleted_address}' now"
    assert message.context_json == {"note": f'contact "{deleted_address}"'}


@pytest.mark.django_db
def test_anonymize_without_a_matching_delivery_changes_nothing(queued_message) -> None:
    """A person with no deliveries leaves every stored record untouched."""
    user = _user("nobody@example.com")

    anonymize_account(user, "nobody@example.com", "Nobody", user.get_username())

    queued_message.refresh_from_db()
    assert queued_message.subject == "Queued message"


@pytest.mark.django_db
def test_anonymize_keeps_an_empty_render_field_empty() -> None:
    """A field that stored nothing keeps storing nothing after the scrub."""
    user = _user("alpha@example.com")
    message = _message(rendered_html="", last_error="")
    NotificationDelivery.objects.create(
        message=message,
        recipient_email="alpha@example.com",
    )

    anonymize_account(user, "alpha@example.com", "Alpha Person", user.get_username())

    message.refresh_from_db()
    assert message.rendered_html == ""
    assert message.last_error == ""
    assert message.subject == "[redacted]"


def test_app_config_declares_the_anonymize_handlers_capability() -> None:
    """Notifications declares its handler without importing orgs."""
    config = apps.get_app_config("quickscale_notifications")

    assert config.anonymize_handlers() == (config,)


@pytest.mark.django_db
def test_declared_treatments_hold_on_a_populated_user() -> None:
    """Every declared treatment matches what the executor does to populated rows."""
    from quickscale_core.runtime import PersonalDataField, PersonalDataTreatment

    config = apps.get_app_config("quickscale_notifications")
    declared = {
        (entry.model_name, entry.field_name): entry.treatment
        for entry in config.personal_data_declarations()
        if isinstance(entry, PersonalDataField)
    }
    assert declared == {
        ("NotificationMessage", "subject"): PersonalDataTreatment.SCRUB,
        ("NotificationMessage", "rendered_text"): PersonalDataTreatment.SCRUB,
        ("NotificationMessage", "rendered_html"): PersonalDataTreatment.SCRUB,
        ("NotificationMessage", "context_json"): PersonalDataTreatment.SCRUB,
        ("NotificationMessage", "last_error"): PersonalDataTreatment.SCRUB,
        ("NotificationDelivery", "failure_reason"): PersonalDataTreatment.SCRUB,
        ("NotificationDelivery", "recipient_email"): PersonalDataTreatment.SCRUB,
        ("NotificationDeliveryEvent", "payload_json"): PersonalDataTreatment.SCRUB,
    }

    user = _user("alpha@example.com")
    message = _message()
    delivery = NotificationDelivery.objects.create(
        message=message,
        recipient_email="alpha@example.com",
        failure_reason="alpha@example.com mailbox full",
    )
    event = NotificationDeliveryEvent.objects.create(
        delivery=delivery,
        idempotency_key="declared-treatments",
        event_type="bounced",
        status_after="bounced",
        payload_json={
            "to": "alpha@example.com",
            "detail": {"contact": "Reach alpha@example.com now"},
        },
    )

    anonymize_account(user, "Alpha@Example.com", "Alpha Person", user.get_username())

    deleted_address = f"deleted-{user.pk}@invalid"
    message.refresh_from_db()
    delivery.refresh_from_db()
    event.refresh_from_db()
    outcomes = {
        ("NotificationMessage", "subject"): message.subject == "[redacted]",
        ("NotificationMessage", "rendered_text"): message.rendered_text == "[redacted]",
        ("NotificationMessage", "rendered_html"): message.rendered_html == "[redacted]",
        ("NotificationMessage", "context_json"): message.context_json == {},
        ("NotificationMessage", "last_error"): message.last_error == "[redacted]",
        ("NotificationDelivery", "failure_reason"): delivery.failure_reason
        == "[redacted]",
        ("NotificationDelivery", "recipient_email"): delivery.recipient_email
        == deleted_address,
        ("NotificationDeliveryEvent", "payload_json"): event.payload_json
        == {
            "to": deleted_address,
            "detail": {"contact": f"Reach {deleted_address} now"},
        },
    }
    assert set(outcomes) == set(declared)
    assert all(outcomes.values()), outcomes
