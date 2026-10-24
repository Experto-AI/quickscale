"""The generated React shell's ``window.__QUICKSCALE__`` module seam.

Module Conventions rule 31: the theme's ``index.html`` and its public social
pages report modules from the shipped module inventory, so the seam carries a
key for every shipped module — ``true`` only while the module is installed and
its ``QUICKSCALE_<MODULE>_ENABLED`` setting is on — a ``modulePaths`` entry per
path-bearing module whose named route resolves at request time, never a mount
literal, and a ``moduleDocumentPaths`` entry per module-owned server-rendered
document the theme's launcher pages link to.  Rule 41: the seam carries each API-bearing module's base in
``moduleApiPaths`` the same way, cut at rule 7's ``<mount>api/`` boundary, so
the theme's API clients never write ``/<mount>/api`` themselves.

This module owns the seam's inventory, its route tables, and resolution.  The
``quickscale_seam`` template-tag library that renders the resolved values into
the templates lives in :mod:`quickscale_core.runtime.seam_tags`; the generated
project's ``settings/base.py`` registers that library through the template
engine's ``libraries`` option, and the theme templates load and call it.  A
generated project therefore holds one tag call per object instead of a
generated line per module in its user-owned files.

The same tables render the theme's managed seam declaration
(:func:`render_seam_declaration` into :data:`SEAM_DECLARATION_RELATIVE_PATH`),
so the theme's module-key types follow the shipped set instead of being typed
per project.

The module stays importable without Django: resolution reads a settings-like
object and takes the URL reverser as a callable, so tests and the CLI's
generation path never need a Django process.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from quickscale_core.contracts.module_catalog import MODULE_CATALOG
from quickscale_core.contracts.module_discovery import (
    get_bundled_manifests_path,
    resolve_manifest_base_path,
)
from quickscale_core.manifest.loader import load_manifest_from_path
from quickscale_core.manifest.schema import FrontendResources, ModuleManifest

__all__ = [
    "SEAM_DECLARATION_RELATIVE_PATH",
    "SEAM_HOOKS_RELATIVE_PATH",
    "SEAM_KEY_MANIFEST_RELATIVE_PATH",
    "SeamModule",
    "SeamRoute",
    "render_module_api_paths",
    "render_module_document_paths",
    "render_module_flags",
    "render_module_paths",
    "render_seam_declaration",
    "render_seam_hooks",
    "render_seam_key_manifest",
    "seam_api_path_names",
    "seam_document_path_names",
    "seam_module_api_paths",
    "seam_module_document_paths",
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
    """One candidate named route of a seam path-table entry."""

    route: str
    #: Empty while the route always applies; otherwise the settings name that
    #: selects this route only while it is on.
    enabled_setting: str = ""


#: The theme's server-resolved path table (rule 31): module name -> candidate
#: routes in preference order.  A route with an ``enabled_setting`` applies
#: only while that setting is on; the first applicable route wins, and the
#: first entry is the default when none applies.  blog, listings, crm, and
#: analytics resolve one route each; social renders the link tree by default
#: and the embeds page while the link tree is off and embeds is on.  These
#: names are the theme's own module surface, which rule 37 lists as its
#: allowed literal-name exception; the mount a module actually uses stays in
#: its manifest (rule 7).
_SEAM_MODULE_PATHS: tuple[tuple[str, tuple[SeamRoute, ...]], ...] = (
    ("blog", (SeamRoute("quickscale_blog_shell"),)),
    ("listings", (SeamRoute("quickscale_listings_shell"),)),
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


def _applicable_route(routes: tuple[SeamRoute, ...], settings_obj: Any) -> str:
    """Return the first applicable route of one seam path entry's candidates.

    The first entry is the default when none applies, so a candidate table
    always names the route the entry falls back to.
    """
    for route in routes:
        if not route.enabled_setting or getattr(
            settings_obj, route.enabled_setting, False
        ):
            return route.route
    return routes[0].route


def _path_route(name: str, settings_obj: Any) -> str:
    """Return the named route one seam path entry resolves against the settings."""
    return _applicable_route(dict(_SEAM_MODULE_PATHS)[name], settings_obj)


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


#: The theme's server-resolved document-path table (rule 31): flat key ->
#: owning module -> candidate named routes in preference order, resolved the
#: way ``modulePaths`` is.  These are the module-owned server-rendered
#: documents the theme's launcher pages link to, so a document link follows
#: the module's URL names instead of a mount written by hand.  The blog feed
#: route exists only while its rss feature setting is on, so the entry falls
#: back to the module's index — the same table shape the social path uses.
_SEAM_DOCUMENT_PATHS: tuple[tuple[str, str, tuple[SeamRoute, ...]], ...] = (
    ("blogIndex", "blog", (SeamRoute("quickscale_blog:post_list"),)),
    (
        "blogFeed",
        "blog",
        (
            SeamRoute("quickscale_blog:feed", "QUICKSCALE_BLOG_RSS_ENABLED"),
            SeamRoute("quickscale_blog:post_list"),
        ),
    ),
    ("listingsIndex", "listings", (SeamRoute("quickscale_listings:listing_list"),)),
    ("crmDashboard", "crm", (SeamRoute("quickscale_crm:dashboard"),)),
)


def seam_document_path_names() -> tuple[str, ...]:
    """Return the theme's document-path keys, in table order."""
    return tuple(name for name, _module, _routes in _SEAM_DOCUMENT_PATHS)


def seam_module_document_paths(
    settings_obj: Any,
    reverse_func: Callable[[str], str],
) -> dict[str, str]:
    """Resolve ``window.__QUICKSCALE__.moduleDocumentPaths`` against *settings_obj*.

    An entry resolves its module's named route only while the module is
    installed and enabled; otherwise it resolves the project's always-present
    ``home`` route, because the seam validator requires a non-empty string for
    every path field even when the module is absent.
    """
    installed_apps = getattr(settings_obj, "INSTALLED_APPS", ())
    resolved: dict[str, str] = {}
    for name, module, routes in _SEAM_DOCUMENT_PATHS:
        installed = f"quickscale_modules_{module}" in installed_apps
        enabled = bool(
            getattr(settings_obj, f"QUICKSCALE_{module.upper()}_ENABLED", False)
        )
        if installed and enabled:
            resolved[name] = reverse_func(_applicable_route(routes, settings_obj))
        else:
            resolved[name] = reverse_func("home")
    return resolved


#: The theme's API-base table (rule 41): module name -> the named route of one
#: endpoint inside the module's ``<mount>api/`` subtree (rule 7).  The base the
#: theme receives is the reversed path cut at that ``api/`` boundary, so no
#: theme file writes ``/<mount>/api`` itself.  These names are the theme's own
#: module surface, which rule 37 lists as its allowed literal-name exception;
#: the mount a module actually uses stays in its manifest (rule 7). Each entry
#: also pins the named endpoint's suffix below the API boundary; checking this
#: suffix fails closed on route drift and preserves any outer ``api/`` segments.
_SEAM_MODULE_API_PATHS: tuple[tuple[str, str, str], ...] = (
    ("orgs", "quickscale_orgs:api_list_create", ""),
    ("billing", "quickscale_billing:subscription_plans", "plans/"),
    ("crm", "quickscale_crm:api_root", ""),
    ("forms", "quickscale_forms:admin_form_list", "admin/forms/"),
)

#: Rule 7's API boundary inside a module's mount.
_API_BOUNDARY = "/api/"


def seam_api_path_names() -> tuple[str, ...]:
    """Return the API-bearing module surfaces, in route-table order."""
    return tuple(name for name, _route, _suffix in _SEAM_MODULE_API_PATHS)


def _api_base_from_path(path: str, module: str, endpoint_suffix: str) -> str:
    """Remove only the named endpoint suffix after the module's API boundary."""
    if not path.endswith(_API_BOUNDARY + endpoint_suffix):
        raise ValueError(
            f"Seam API path for module '{module}' has no '/api/' boundary "
            f"before endpoint suffix {endpoint_suffix!r}: {path!r}. "
            "A module's API lives at '<mount>api/' (rule 7)."
        )
    return path[: -len(endpoint_suffix)] if endpoint_suffix else path


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
    for module, route, endpoint_suffix in _SEAM_MODULE_API_PATHS:
        installed = f"quickscale_modules_{module}" in installed_apps
        enabled = bool(
            getattr(settings_obj, f"QUICKSCALE_{module.upper()}_ENABLED", False)
        )
        if installed and enabled:
            resolved[module] = _api_base_from_path(
                reverse_func(route), module, endpoint_suffix
            )
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


def render_module_document_paths(
    paths: Mapping[str, str], indent: str = "          "
) -> str:
    """Render the ``moduleDocumentPaths`` object's JS body (rule 31)."""
    return _render_path_object(paths, indent)


#: Project-relative path of the theme's managed seam declaration (SA276).
#: Generation emits it from :func:`render_seam_declaration`, and
#: ``quickscale apply``/``quickscale update`` regenerate it under the
#: managed-file hash guard, so a local edit is reported as drift.
SEAM_DECLARATION_RELATIVE_PATH = "frontend/src/quickscaleSeam.d.ts"


def render_seam_declaration() -> str:
    """Render the theme's managed seam declaration from the shipped set.

    One exported interface per seam table — the module flags (rule 31), the
    server-resolved path names, and the API bases (rule 41) — each typed from
    the same tables the runtime seam resolves, so the declaration follows the
    shipped set rather than a hand-typed list.
    """
    module_flags = "\n".join(f"  {module.name}: boolean" for module in seam_modules())
    module_paths = "\n".join(f"  {name}: string" for name in seam_path_names())
    api_paths = "\n".join(f"  {name}: string" for name in seam_api_path_names())
    document_paths = "\n".join(
        f"  {name}: string" for name in seam_document_path_names()
    )
    return (
        "// QuickScale managed seam declaration.\n"
        "//\n"
        "// DO NOT EDIT MANUALLY. This file is regenerated by QuickScale from the\n"
        "// shipped module set (quickscale_modules/*/module.yml), so a module that\n"
        "// joins the set joins the theme's types.\n"
        "\n"
        "export interface QuickScaleModules {\n"
        f"{module_flags}\n"
        "}\n"
        "\n"
        "export interface QuickScaleModulePaths {\n"
        f"{module_paths}\n"
        "}\n"
        "\n"
        "export interface QuickScaleModuleApiPaths {\n"
        f"{api_paths}\n"
        "}\n"
        "\n"
        "export interface QuickScaleModuleDocumentPaths {\n"
        f"{document_paths}\n"
        "}\n"
    )


#: Project-relative path of the theme's managed seam key manifest (SA276).
#: The generated declaration carries the seam's types; this file carries the
#: same tables as runtime arrays, so the theme's seam validator requires every
#: flag, path, and API-base entry without holding its own module list.
#: Generation emits it, and ``quickscale apply``/``quickscale update``
#: regenerate it under the managed-file hash guard beside the declaration.
SEAM_KEY_MANIFEST_RELATIVE_PATH = "frontend/src/quickscaleSeam.keys.ts"


def _render_ts_string_array(names: tuple[str, ...], *, multiline: bool = False) -> str:
    """Render one TypeScript string-array literal from *names*."""
    if not multiline:
        return "[" + ", ".join(f"'{name}'" for name in names) + "]"
    return "[\n" + "".join(f"  '{name}',\n" for name in names) + "]"


def render_seam_key_manifest() -> str:
    """Render the theme's managed seam key manifest from the shipped set.

    The declaration types the seam; this manifest carries the same tables as
    runtime arrays, so the theme's validator can require every entry the
    declaration names without a hand-maintained copy in user-owned code.
    """
    flag_keys = _render_ts_string_array(
        tuple(module.name for module in seam_modules()), multiline=True
    )
    path_keys = _render_ts_string_array(seam_path_names())
    api_keys = _render_ts_string_array(seam_api_path_names())
    document_keys = _render_ts_string_array(seam_document_path_names())
    return (
        "// QuickScale managed seam key manifest.\n"
        "//\n"
        "// DO NOT EDIT MANUALLY. This file is regenerated by QuickScale from the\n"
        "// shipped module set (quickscale_modules/*/module.yml), so a module that\n"
        "// joins the set joins the validator's required entries.\n"
        "\n"
        f"export const SEAM_MODULE_FLAG_KEYS = {flag_keys} as const\n"
        "\n"
        f"export const SEAM_MODULE_PATH_KEYS = {path_keys} as const\n"
        "\n"
        f"export const SEAM_MODULE_API_PATH_KEYS = {api_keys} as const\n"
        "\n"
        f"export const SEAM_MODULE_DOCUMENT_PATH_KEYS = {document_keys} as const\n"
    )


#: Project-relative path of the theme's managed module hooks (SA320).
#: The file carries each shipped module's manifest-declared API resource
#: subpaths and payload types, so a user-owned page imports the module's
#: resource contract instead of restating a subpath or a response type.
#: Generation emits it, and ``quickscale apply``/``quickscale update``/
#: ``quickscale remove`` regenerate it under the managed-file hash guard
#: beside the seam declaration and key manifest.
SEAM_HOOKS_RELATIVE_PATH = "frontend/src/quickscaleSeam.hooks.ts"


def _load_contract_manifest(module_name: str) -> ModuleManifest:
    """Load one module's manifest for the generated frontend contract.

    The active manifest base is read first, so ``apply``/``update``/``remove``
    in a generated project use the installed module's own declaration (the
    frontend contract then matches the backend actually present), and
    generation in the maintainer workspace uses the source manifest.  A
    module the project does not install has no manifest under an embedded
    module base, so it falls back to the release's bundled snapshot: the theme
    emits every module page as a dormant file, and a page for an uninstalled
    module still imports its contract at build time.
    """
    base = resolve_manifest_base_path()
    candidate = base / module_name / "module.yml"
    if not candidate.is_file():
        if (base / module_name).exists():
            # A module directory without a manifest is a broken installation;
            # load_manifest_from_path fails hard instead of masking it.
            return load_manifest_from_path(candidate)
        candidate = get_bundled_manifests_path() / module_name / "module.yml"
    return load_manifest_from_path(candidate)


def _frontend_resources_by_module() -> tuple[tuple[str, FrontendResources], ...]:
    """Return each shipped module's declared frontend resource contract.

    Manifests are read for the whole shipped set, not the project's installed
    set: the theme emits every module page as a dormant file, so a page for an
    uninstalled module still imports its contract at build time.  A payload
    type declared by two modules is refused, because the hook file has one
    TypeScript namespace.
    """
    contracts: list[tuple[str, FrontendResources]] = []
    seen_types: dict[str, str] = {}
    for entry in MODULE_CATALOG:
        manifest = _load_contract_manifest(entry.name)
        contract = manifest.frontend_resources
        if contract is None:
            continue
        for type_name in contract.payload_types:
            other = seen_types.get(type_name)
            if other is not None:
                raise ValueError(
                    f"Frontend payload type {type_name!r} is declared by both "
                    f"{other!r} and {entry.name!r}; the managed hook file has "
                    "one TypeScript namespace, so the type needs one owner."
                )
            seen_types[type_name] = entry.name
        contracts.append((entry.name, contract))
    return tuple(contracts)


def render_seam_hooks() -> str:
    """Render the theme's managed module hooks from the active manifests.

    One ``<MODULE>_RESOURCE_PATHS`` constant per module that declares resource
    paths and one exported interface per declared payload type.  A declaring
    module's resource subpath or response shape therefore lives in this
    generated file; a user-owned page imports it and never restates either, so
    a module release that changes one needs no user-owned diff.  The active
    manifest set is the project's installed modules plus the release's shipped
    snapshots for modules it does not install, so the hook follows the backend
    the project actually runs.
    """
    blocks: list[str] = []
    for module_name, contract in _frontend_resources_by_module():
        if contract.paths:
            entries = "\n".join(
                f"  {resource}: '{path}'," for resource, path in contract.paths.items()
            )
            blocks.append(
                f"export const {module_name.upper()}_RESOURCE_PATHS = {{\n"
                f"{entries}\n"
                "} as const"
            )
        for type_name, fields in contract.payload_types.items():
            members = "\n".join(
                f"  {field_name}: {field_type}"
                for field_name, field_type in fields.items()
            )
            blocks.append(f"export interface {type_name} {{\n{members}\n}}")
    header = (
        "// QuickScale managed module hooks.\n"
        "//\n"
        "// DO NOT EDIT MANUALLY. This file is regenerated by QuickScale from the\n"
        "// active module manifests (quickscale_modules/*/module.yml): the\n"
        "// project's installed modules plus the shipped set for modules it does\n"
        "// not install. A module release that changes a resource subpath or\n"
        "// payload type changes only this file; the theme's pages import these\n"
        "// declarations instead of restating a module resource path or response\n"
        "// type.\n"
    )
    if not blocks:
        return header
    return header + "\n" + "\n\n".join(blocks) + "\n"
