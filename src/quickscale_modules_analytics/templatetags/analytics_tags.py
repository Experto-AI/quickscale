"""Template tags for manual analytics adoption in server-rendered templates."""

from __future__ import annotations

import json

from django import template
from django.http import HttpRequest
from django.utils.safestring import mark_safe

from quickscale_modules_analytics.services import get_template_analytics_context

register = template.Library()


def _resolve_request(context: template.Context) -> HttpRequest | None:
    request = context.get("request")
    if isinstance(request, HttpRequest):
        return request
    return None


@register.simple_tag(takes_context=True)
def analytics_public_config(context: template.Context) -> dict[str, object]:
    """Return the resolved analytics config for the current request."""
    return get_template_analytics_context(_resolve_request(context))


@register.simple_tag(takes_context=True)
def analytics_public_config_json(context: template.Context) -> str:
    """Return the resolved analytics config as JSON."""
    payload = get_template_analytics_context(_resolve_request(context))
    return mark_safe(json.dumps(payload, sort_keys=True))
