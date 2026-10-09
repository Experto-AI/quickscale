"""The generated project's managed URLconf and template URL resolution.

This module is the single declaration of the URL-facing seam between the
shipped modules and a generated project.  The user-owned
``<package>/urls.py`` holds one ``include()`` line pointing at the managed
``<package>/urls_modules.py`` file that ``apply`` regenerates; that file
carries the module-derived URL includes and calls
:func:`compose_managed_urlpatterns`, so the theme's host route table for
module surfaces (Module Conventions rule 41) and the rule's ordering ship
through the versioned ``quickscale-core`` lockstep pin instead of living in
user-owned generated files.

The theme's shell block is fixed data: the home route, orgs' ``/orgs*``
React shell reservations (the tenancy mode decides which side owns the path,
so the module's own include sits on either side of this block), the
profile/settings and forms shallow reservations (forms' module entrypoint
renders only a mount-point div, so the shell must win until it hydrates),
and the public social pages (flat route names ``social-link-tree`` and
``social-embeds``).  ``compose_managed_urlpatterns`` fixes the order the
generated URLconf has always used: shell routes, pre-home module includes,
public social pages, post-home module includes, then the manifest-declared
React shell routes (``SPA_MODULE_URLPATTERNS``).

:func:`installed_module_context` is the Django-template half of the same
seam: it resolves the template-visible URL of each route-table module from
the live settings and the URL resolver, so the generated
``<package>/context_processors.py`` names no module and no module route.

The module is Django-side runtime code: a process that never loads a URLconf
never imports it.  Its import path ``quickscale_core.runtime.urls`` is public
API; existing projects adopt the managed URLconf through a declared contract
step.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.http import HttpRequest
from django.urls import (
    URLPattern,
    URLResolver,
    NoReverseMatch,
    path,
    re_path,
    reverse,
)
from django.views.generic import TemplateView

__all__ = [
    "ManagedURLPattern",
    "compose_managed_urlpatterns",
    "installed_module_context",
]

ManagedURLPattern = URLPattern | URLResolver


def _shell_urlpatterns(
    *,
    react_shell_view: Any,
    orgs_shell_view: Any,
) -> list[ManagedURLPattern]:
    """Return the theme's host-rendered shell routes for module surfaces.

    Every route here serves the React shell for a path a module owns
    (Module Conventions rule 41's stated exceptions): orgs' ``/orgs*``
    reservations are host-rendered because the tenancy mode decides which
    side owns the path, forms' shallow reservations stay host-rendered until
    the module's entrypoint hydrates, and the profile/settings pages are the
    theme's own routes.  The orgs regexes exclude ``/orgs/api/`` so the
    module's JSON API reaches Django instead of the shell.
    """
    return [
        path("", react_shell_view, name="home"),
        re_path(r"^orgs/?$", orgs_shell_view),
        re_path(r"^orgs/new/?$", orgs_shell_view),
        # The module's JSON API lives under /orgs/api/ and must reach Django.
        re_path(r"^orgs/(?!api(?:/|$))[^/]+/?$", orgs_shell_view),
        re_path(
            r"^orgs/(?!api(?:/|$))[^/]+/(blog|listings|members|settings)/?$",
            orgs_shell_view,
        ),
        re_path(r"^(profile|settings)/?$", react_shell_view),
        # Forms' module entrypoint template renders only a mount-point div
        # with no bundle or seam, so the host shell keeps its shallow paths
        # working until the module page hydrates (rule 41 exception).
        re_path(r"^forms/?$", react_shell_view),
        re_path(r"^forms/[^/]+/?$", react_shell_view),
    ]


def _social_urlpatterns() -> list[ManagedURLPattern]:
    """Return the theme's public social pages (rule 41's stated exception).

    The flat route names ``social-link-tree`` and ``social-embeds`` are the
    theme seam's ``modulePaths`` targets for social (rule 31); they are not a
    module mount, which stays the manifest-declared ``_quickscale/social/``
    transport include.
    """
    return [
        re_path(
            r"^social/?$",
            TemplateView.as_view(template_name="social/link_tree.html"),
            name="social-link-tree",
        ),
        re_path(
            r"^social/embeds/?$",
            TemplateView.as_view(template_name="social/embeds.html"),
            name="social-embeds",
        ),
    ]


def compose_managed_urlpatterns(
    *,
    pre_home: list[ManagedURLPattern],
    post_home: list[ManagedURLPattern],
    spa: list[ManagedURLPattern],
    react_shell_view: Any,
    orgs_shell_view: Any,
) -> list[ManagedURLPattern]:
    """Compose the managed URLconf in the generated project's fixed order.

    The order is the actual specification of URL ownership (rule 41): the
    theme shell wins over a module's post-home includes so a module's
    server-rendered index keeps its path while its React shell route covers
    the bare path, and the manifest-declared ``spa`` routes render after
    every module include.  ``pre_home`` carries the modules whose manifest
    says Django owns their path ahead of the shell (orgs in solo mode).
    """
    return [
        *_shell_urlpatterns(
            react_shell_view=react_shell_view,
            orgs_shell_view=orgs_shell_view,
        ),
        *pre_home,
        *_social_urlpatterns(),
        *post_home,
        *spa,
    ]


#: The template-visible URL table: one entry per module whose named routes
#: the Django-rendered shell links, as ``(module, anonymous route,
#: authenticated route)``.  The module's enabled setting
#: (``QUICKSCALE_<MODULE>_ENABLED``) gates the value exactly the way the
#: React seam gates its module flags, so a module that is absent or switched
#: off yields ``None``.  The routes are named, never literal paths: the
#: module owns its URLs (rule 41).  This is the theme seam's server-side
#: route knowledge (rule 37's listed exception), the sibling of
#: ``runtime/seam._SEAM_MODULE_PATHS``.
_TEMPLATE_MODULE_URLS: tuple[tuple[str, str, str], ...] = (
    ("billing", "quickscale_billing:pricing_page", "quickscale_billing:dashboard"),
)


def _template_module_url(
    module: str,
    *,
    anonymous_route: str,
    authenticated_route: str,
    request: HttpRequest,
) -> str | None:
    """Resolve one module's template URL for the request's authentication."""
    if not getattr(settings, f"QUICKSCALE_{module.upper()}_ENABLED", False):
        return None
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        route_name = anonymous_route
    else:
        route_name = authenticated_route
    try:
        return reverse(route_name)
    except NoReverseMatch:
        return None


def installed_module_context(
    request: HttpRequest,
) -> dict[str, dict[str, str | None]]:
    """Return the Django-template ``modules`` context for the installed set.

    Every route-table module is present, with its URL resolved for the
    request (anonymous visitors reach the pricing page, authenticated users
    the dashboard) or ``None`` while the module is absent, switched off, or
    its namespace does not resolve.  The generated
    ``<package>/context_processors.py`` returns ``{"modules": ...}`` from
    this helper.
    """
    return {
        module: {
            "url": _template_module_url(
                module,
                anonymous_route=anonymous_route,
                authenticated_route=authenticated_route,
                request=request,
            )
        }
        for module, anonymous_route, authenticated_route in _TEMPLATE_MODULE_URLS
    }
