"""Template tags for VIEW-AS debug mode rendering."""

from __future__ import annotations

from django import template
from django.http import HttpRequest

from ..constants import DEBUG_AS_ORG_SESSION_KEY

register = template.Library()


@register.simple_tag(takes_context=True)
def debug_as_active(context: dict) -> bool:
    """Return ``True`` when a VIEW-AS debug session is active for the user.

    Usage::

        {% load quickscale_orgs_debug %}
        {% debug_as_active as is_debug_active %}
        {% if is_debug_active %}...{% endif %}
    """
    request: HttpRequest | None = context.get("request")
    if request is None:
        return False
    if not getattr(request.user, "is_superuser", False):
        return False
    return DEBUG_AS_ORG_SESSION_KEY in request.session
