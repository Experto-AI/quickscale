"""The ``quickscale_seam`` template-tag library (Module Conventions rule 31).

The generated project's ``settings/base.py`` registers this library through the
template engine's ``libraries`` option::

    "libraries": {
        "quickscale_seam": "quickscale_core.runtime.seam_tags",
    },

The theme's ``templates/index.html`` and public social pages load it and render
the seam with ``{% seam_module_flags %}`` and ``{% seam_module_paths %}``, so
the module flags and paths resolve at request time from the live settings and
shipped inventory instead of being baked into the user-owned file at
generation.  :mod:`quickscale_core.runtime.seam` owns the resolution.
"""

from __future__ import annotations

from django import template
from django.conf import settings as django_settings
from django.urls import reverse
from django.utils.safestring import mark_safe

from quickscale_core.runtime import seam

register = template.Library()

__all__ = ["seam_module_api_paths", "seam_module_flags", "seam_module_paths"]


@register.simple_tag
def seam_module_flags() -> str:
    """Render the ``window.__QUICKSCALE__.modules`` object body."""
    # The body is JavaScript source: module names from the shipped inventory
    # and boolean literals only, so the escaping a ``simple_tag`` would apply
    # to the surrounding punctuation must not run.
    return mark_safe(seam.render_module_flags(seam.seam_module_flags(django_settings)))  # noqa: S308


@register.simple_tag
def seam_module_paths() -> str:
    """Render the ``window.__QUICKSCALE__.modulePaths`` object body."""
    # The body is JavaScript source: quoted paths produced by ``reverse()``,
    # which the retired ``{% url %}`` tag also emitted unescaped here.
    return mark_safe(  # noqa: S308
        seam.render_module_paths(seam.seam_module_paths(django_settings, reverse))
    )


@register.simple_tag
def seam_module_api_paths() -> str:
    """Render the ``window.__QUICKSCALE__.moduleApiPaths`` object body."""
    # The body is JavaScript source: quoted paths produced by ``reverse()``,
    # which the retired ``{% url %}`` tag also emitted unescaped here.
    return mark_safe(  # noqa: S308
        seam.render_module_api_paths(
            seam.seam_module_api_paths(django_settings, reverse)
        )
    )
