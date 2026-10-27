"""Generic admin-shortcut region for module-owned admin templates (SA320).

The generated ``templates/admin/index.html`` and ``app_index.html`` are
user-owned, so they name no module.  Each renders a module's own
``templates/admin/<app_label>/quickscale_shortcut.html`` through this tag when
that module ships one, and nothing otherwise.  The module owns its markup and
URL names; core owns only the generic lookup.

The shortcut template receives the requesting Django context plus
``quickscale_admin_page`` (``"index"`` or ``"app_index"``), so one module
template can distinguish the two admin pages.
"""

from __future__ import annotations

import re
from typing import Any, cast

from django import template
from django.template import TemplateDoesNotExist
from django.template.loader import get_template

__all__ = ["module_admin_shortcut", "register"]

register = template.Library()

#: A Django app label is a safe template-path segment.
_APP_LABEL = re.compile(r"[a-z_][a-z0-9_]*\Z")


@register.simple_tag(takes_context=True)
def module_admin_shortcut(context: template.Context, app_label: str, page: str) -> str:
    """Render a module's admin shortcut block for one app label and page.

    Args:
        context: The requesting template context.
        app_label: The Django app label being rendered in the admin index.
        page: ``"index"`` or ``"app_index"``; passed to the module template as
            ``quickscale_admin_page``.

    Returns:
        The module template's rendered HTML, or an empty string when the app
        ships no shortcut template.
    """
    if not isinstance(app_label, str) or _APP_LABEL.fullmatch(app_label) is None:
        return ""
    template_name = f"admin/{app_label}/quickscale_shortcut.html"
    try:
        module_template = get_template(template_name)
    except TemplateDoesNotExist:
        return ""
    template_context = cast(dict[str, Any], context.flatten())
    rendered = module_template.render(
        {**template_context, "quickscale_admin_page": page},
        request=context.get("request"),
    )
    # Template.render returns a SafeString; the tag preserves it while the
    # template engine, not this function, escaped the module's own output.
    return rendered
