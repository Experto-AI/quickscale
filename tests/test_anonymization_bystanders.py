"""Bystander conformance: every registered template links its person.

Account anonymization must select a message through the person link the
sender declares, and must leave a bystander's message untouched.  Rendering
every registered template key with a sentinel user exercises the whole
registry, so a new template cannot ship without a linkable person (tech audit
§ Tooling gaps).
"""

from __future__ import annotations

from typing import Any

import pytest
from django.contrib.auth import get_user_model

from quickscale_modules_notifications._anonymization import anonymize_account
from quickscale_modules_notifications._templates import (
    NotificationTemplateDefinition,
    _TEMPLATE_REGISTRY,
)
from quickscale_modules_notifications.services import send_notification

pytestmark = pytest.mark.django_db


def _renderable_context(
    definition: NotificationTemplateDefinition,
) -> dict[str, Any]:
    """Return a context that renders every required key of the template."""
    context: dict[str, Any] = {
        key: f"sentinel {key}" for key in definition.required_context
    }
    if "fields" in context:
        context["fields"] = [["Field", "Value"]]
    return context


def _stored_snapshot(message) -> tuple[Any, ...]:
    """Return every stored field the scrub could touch."""
    return (
        message.subject,
        message.rendered_text,
        message.rendered_html,
        message.context_json,
        message.last_error,
        message.about_user_ids_json,
    )


@pytest.mark.parametrize("template_key", sorted(_TEMPLATE_REGISTRY))
def test_each_registered_template_links_its_person(
    template_key: str,
    notification_settings_row,
    django_capture_on_commit_callbacks,
) -> None:
    """The anonymizer selects the linked message and leaves the bystander's."""
    del notification_settings_row
    user_model = get_user_model()
    sentinel = user_model.objects.create_user(
        username="sentinel-user",
        email="sentinel-user@example.com",
        password="SentinelPass1!",
    )
    bystander = user_model.objects.create_user(
        username="bystander-user",
        email="bystander-user@example.com",
        password="BystanderPass1!",
    )
    context = _renderable_context(_TEMPLATE_REGISTRY[template_key])

    with django_capture_on_commit_callbacks(execute=True):
        linked = send_notification(
            template_key=template_key,
            recipients=["archive@example.com"],
            context=context,
            about_users=[sentinel],
            mailer=lambda mail: f"provider::{mail.to[0]}",
        )
        bystander_message = send_notification(
            template_key=template_key,
            recipients=["archive@example.com"],
            context=context,
            about_users=[bystander],
            mailer=lambda mail: f"provider::{mail.to[0]}",
        )

    linked.refresh_from_db()
    bystander_message.refresh_from_db()
    bystander_snapshot = _stored_snapshot(bystander_message)
    assert linked.about_user_ids_json == [str(sentinel.pk)]
    assert bystander_message.about_user_ids_json == [str(bystander.pk)]

    anonymize_account(
        sentinel,
        sentinel.email,
        "Sentinel Person",
        sentinel.get_username(),
    )

    linked.refresh_from_db()
    bystander_message.refresh_from_db()
    assert str(sentinel.pk) not in linked.about_user_ids_json, (
        "the anonymizer must select the message through its stored link"
    )
    assert _stored_snapshot(bystander_message) == bystander_snapshot, (
        "the bystander's stored message must stay byte-identical"
    )
