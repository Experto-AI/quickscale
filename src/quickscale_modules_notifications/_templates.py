"""Canonical notification templates and rendering.

Every notification is rendered from one registry entry keyed by the module's
``notifications.<name>`` template key; the registry validates the caller's
context before rendering.  ``services.py`` re-exports this surface (Module
Conventions rule 28).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from typing import Any, cast

from django.template.loader import render_to_string

from quickscale_modules_notifications.exceptions import NotificationTemplateError


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


_TEMPLATE_REGISTRY = {
    "notifications.generic": NotificationTemplateDefinition(
        subject_template=("quickscale_notifications/email/generic_subject.txt"),
        text_template=("quickscale_notifications/email/generic_body.txt"),
        html_template=("quickscale_notifications/email/generic_body.html"),
        required_context=frozenset({"headline", "body"}),
    ),
    "notifications.forms_submission": NotificationTemplateDefinition(
        subject_template=(
            "quickscale_notifications/email/forms_submission_subject.txt"
        ),
        text_template=("quickscale_notifications/email/forms_submission_body.txt"),
        html_template=("quickscale_notifications/email/forms_submission_body.html"),
        required_context=frozenset(
            {"form_title", "submitted_at", "fields", "ip_address", "status"}
        ),
    ),
    "notifications.org_invitation": NotificationTemplateDefinition(
        subject_template=("quickscale_notifications/email/org_invitation_subject.txt"),
        text_template=("quickscale_notifications/email/org_invitation_body.txt"),
        html_template=("quickscale_notifications/email/org_invitation_body.html"),
        required_context=frozenset(
            {
                "organization_name",
                "invitee_email",
                "inviter_name",
                "role_display",
                "accept_url",
                "expires_at",
            }
        ),
    ),
}


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


def _normalize_context(context: Mapping[str, Any]) -> dict[str, Any]:
    try:
        serialized = json.dumps(dict(context))
    except TypeError as exc:
        raise NotificationTemplateError(
            "Notification context must be JSON-serializable."
        ) from exc
    normalized = json.loads(serialized)
    return cast(dict[str, Any], normalized)
