"""Canonical notification templates and rendering.

Every notification is rendered from a definition its sender owns: a module
declares its templates under a ``quickscale_<module>.<purpose>`` key through
the rule 4 ``notification_templates`` capability, and this module collects
every installed sender's definitions with the shared core helper.  The
definition validates the caller's context before rendering.  ``services.py``
re-exports this surface (Module Conventions rule 28).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from typing import Any, cast

from django.template.loader import render_to_string

from quickscale_core.runtime import collect_capabilities
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


def registered_notification_templates() -> dict[str, NotificationTemplateDefinition]:
    """Return every installed sender's declared notification templates.

    The declarations arrive through the shared core capability helper in
    app-label order; the same key declared by two senders is refused there.
    Keys are the sender-owned ``quickscale_<module>.<purpose>`` strings.
    """
    templates: dict[str, NotificationTemplateDefinition] = {}
    for entry in collect_capabilities("notification_templates"):
        key, definition = cast("tuple[object, object]", entry)
        if not isinstance(definition, NotificationTemplateDefinition):
            raise NotificationTemplateError(
                f"Sender declared notification template {key!r} as "
                f"{definition!r}; expected a NotificationTemplateDefinition."
            )
        templates[str(key)] = definition
    return templates


def render_notification(
    *,
    template_key: str,
    context: Mapping[str, Any],
) -> RenderedNotification:
    """Render a canonical notification template after validating its context."""
    definition = registered_notification_templates().get(template_key)
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
