"""The generated React shell's ``window.__QUICKSCALE__`` module seam.

Module Conventions rule 31: the theme's ``index.html`` and its public social
pages report modules from the shipped module inventory, so the seam carries a
key for every shipped module — ``true`` only while the module is installed and
its ``QUICKSCALE_<MODULE>_ENABLED`` setting is on — and a ``modulePaths`` entry
per path-bearing module whose named route resolves at request time, never a
mount literal.  Rule 41: the seam carries each API-bearing module's base in
``moduleApiPaths`` the same way, cut at rule 7's ``<mount>api/`` boundary, so
the theme's API clients never write ``/<mount>/api`` themselves.

This module owns the seam's inventory, its route tables, and resolution.  The
``quickscale_seam`` template-tag library that renders the resolved values into
the templates lives in :mod:`quickscale_core.runtime.seam_tags`; the generated
project's ``settings/base.py`` registers that library through the template
engine's ``libraries`` option, and the theme templates load and call it.  A
generated project therefore holds one tag call per object instead of a
generated line per module in its user-owned files.

The module stays importable without Django: resolution reads a settings-like
object and takes the URL reverser as a callable, so tests and the CLI's
generation path never need a Django process.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from quickscale_core.contracts.module_catalog import MODULE_CATALOG

__all__ = [
    "SeamModule",
    "SeamRoute",
    "render_module_api_paths",
    "render_module_flags",
    "render_module_paths",
    "seam_api_path_names",
    "seam_module_api_paths",
    "seam_module_flags",
    "seam_module_paths",
    "seam_modules",
    "seam_path_names",
]


@dataclass(frozen=True)
class SeamModule:
    """One shipped module as the React seam reports it."""

    name: str
    app_label: str
    enabled_setting: str


#: ``orgs`` carries no ``modules`` flag: the theme reports its deployment mode
#: through ``owner.mode`` instead (rule 31).
_NON_SEAM_MODULES = frozenset({"orgs"})


@dataclass(frozen=True)
class SeamRoute:
    """One candidate named route of a seam ``modulePaths`` entry."""

    route: str
    #: Empty while the route always applies; otherwise the settings name that
    #: selects this route only while it is on.
    enabled_setting: str = ""


#: The theme's server-resolved path table (rule 31): module name -> candidate
#: routes in preference order.  A route with an ``enabled_setting`` applies
#: only while that setting is on; the first applicable route wins, and the
#: first entry is the default when none applies.  crm and analytics resolve
#: one route; social renders the link tree by default and the embeds page
#: while the link tree is off and embeds is on.  These three names are the
#: theme's own module surface, which rule 37 lists as its allowed literal-name
#: exception; the mount a module actually uses stays in its manifest (rule 7).
_SEAM_MODULE_PATHS: tuple[tuple[str, tuple[SeamRoute, ...]], ...] = (
    ("crm", (SeamRoute("quickscale_crm_shell"),)),
    (
        "social",
        (
            SeamRoute("social-link-tree", "QUICKSCALE_SOCIAL_LINK_TREE_ENABLED"),
            SeamRoute("social-embeds", "QUICKSCALE_SOCIAL_EMBEDS_ENABLED"),
        ),
    ),
    ("analytics", (SeamRoute("quickscale_analytics:dashboard"),)),
)


def seam_modules() -> tuple[SeamModule, ...]:
    """Return every shipped module the seam reports, in inventory order.

    The set comes from core's declared release inventory (Module Conventions
    rule 37's allowed exception), which its consistency test keeps equal to
    ``quickscale_modules/*/module.yml`` discovery.  A selected subset must not
    shrink the set: the seam validator requires an own flag for every shipped
    module, present as ``false`` when the module is absent.
    """
    return tuple(
        SeamModule(
            name=entry.name,
            app_label=f"quickscale_modules_{entry.name}",
            enabled_setting=f"QUICKSCALE_{entry.name.upper()}_ENABLED",
        )
        for entry in MODULE_CATALOG
        if entry.name not in _NON_SEAM_MODULES
    )


def seam_path_names() -> tuple[str, ...]:
    """Return the path-bearing module surfaces, in route-table order."""
    return tuple(name for name, _routes in _SEAM_MODULE_PATHS)


def seam_module_flags(settings_obj: Any) -> dict[str, bool]:
    """Resolve ``window.__QUICKSCALE__.modules`` against *settings_obj*.

    Each flag is ``true`` only while the module is installed and its enabled
    setting is truthy; a module that is not installed is ``false``, and a
    module whose enabled setting is absent is ``false`` too.
    """
    installed_apps = getattr(settings_obj, "INSTALLED_APPS", ())
    return {
        module.name: module.app_label in installed_apps
        and bool(getattr(settings_obj, module.enabled_setting, False))
        for module in seam_modules()
    }


def _path_route(name: str, settings_obj: Any) -> str:
    """Return the named route one seam path entry resolves against the settings."""
    routes = dict(_SEAM_MODULE_PATHS)[name]
    for route in routes:
        if not route.enabled_setting or getattr(
            settings_obj, route.enabled_setting, False
        ):
            return route.route
    return routes[0].route


def seam_module_paths(
    settings_obj: Any,
    reverse_func: Callable[[str], str],
) -> dict[str, str]:
    """Resolve ``window.__QUICKSCALE__.modulePaths`` against *settings_obj*.

    A path resolves its module's named route only while the module is
    installed and enabled; otherwise it resolves the project's always-present
    ``home`` route, because the seam validator requires a non-empty string for
    every path field even when the flag above is ``false``.
    """
    flags = seam_module_flags(settings_obj)
    return {
        name: reverse_func(_path_route(name, settings_obj) if flags[name] else "home")
        for name in seam_path_names()
    }


#: The theme's API-base table (rule 41): module name -> the named route of one
#: endpoint inside the module's ``<mount>api/`` subtree (rule 7).  The base the
#: theme receives is the reversed path cut at that ``api/`` boundary, so no
#: theme file writes ``/<mount>/api`` itself.  These names are the theme's own
#: module surface, which rule 37 lists as its allowed literal-name exception;
#: the mount a module actually uses stays in its manifest (rule 7).
_SEAM_MODULE_API_PATHS: tuple[tuple[str, str], ...] = (
    ("orgs", "quickscale_orgs:api_list_create"),
    ("billing", "quickscale_billing:subscription_plans"),
    ("crm", "quickscale_crm:api_root"),
    ("forms", "quickscale_forms:admin_form_list"),
)

#: Rule 7's API boundary inside a module's mount.
_API_BOUNDARY = "/api/"


def seam_api_path_names() -> tuple[str, ...]:
    """Return the API-bearing module surfaces, in route-table order."""
    return tuple(name for name, _route in _SEAM_MODULE_API_PATHS)


def _api_base_from_path(path: str, module: str) -> str:
    """Cut a module's reversed API route at rule 7's ``/api/`` boundary."""
    boundary = path.find(_API_BOUNDARY)
    if boundary == -1:
        raise ValueError(
            f"Seam API path for module '{module}' has no '/api/' boundary: {path!r}. "
            "A module's API lives at '<mount>api/' (rule 7)."
        )
    return path[: boundary + len(_API_BOUNDARY)]


def seam_module_api_paths(
    settings_obj: Any,
    reverse_func: Callable[[str], str],
) -> dict[str, str]:
    """Resolve ``window.__QUICKSCALE__.moduleApiPaths`` against *settings_obj*.

    A base resolves its module's named route only while the module is
    installed and enabled; otherwise it resolves the project's always-present
    ``home`` route, because the seam validator requires a non-empty string for
    every path field even when the module is absent.
    """
    installed_apps = getattr(settings_obj, "INSTALLED_APPS", ())
    resolved: dict[str, str] = {}
    for module, route in _SEAM_MODULE_API_PATHS:
        installed = f"quickscale_modules_{module}" in installed_apps
        enabled = bool(
            getattr(settings_obj, f"QUICKSCALE_{module.upper()}_ENABLED", False)
        )
        if installed and enabled:
            resolved[module] = _api_base_from_path(reverse_func(route), module)
        else:
            resolved[module] = reverse_func("home")
    return resolved


def render_module_flags(flags: Mapping[str, bool], indent: str = "          ") -> str:
    """Render the ``modules`` object's JS body: one flag per shipped module."""
    return "\n".join(
        f"{indent}{name}: {'true' if enabled else 'false'},"
        for name, enabled in flags.items()
    )


def _render_path_object(paths: Mapping[str, str], indent: str) -> str:
    """Render a paths object's JS body: quoted entries, last without a comma."""
    entries = list(paths.items())
    return "\n".join(
        f'{indent}{name}: "{path}"{"," if index < len(entries) - 1 else ""}'
        for index, (name, path) in enumerate(entries)
    )


def render_module_paths(paths: Mapping[str, str], indent: str = "          ") -> str:
    """Render the ``modulePaths`` object's JS body.

    Every entry is a quoted, reversed path; the last line carries no trailing
    comma, so the object body is valid inside the surrounding braces.
    """
    return _render_path_object(paths, indent)


def render_module_api_paths(
    paths: Mapping[str, str], indent: str = "          "
) -> str:
    """Render the ``moduleApiPaths`` object's JS body (rule 41)."""
    return _render_path_object(paths, indent)
