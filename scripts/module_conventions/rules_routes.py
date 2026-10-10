"""Route, template, API, authorization, theme-seam, and throttle rules."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from scripts.module_conventions.core import (
    ALLOWED_TEMPLATE_DIRS,
    GENERATOR_TEMPLATE_ROOT,
    SNAKE_CASE,
    Corpus,
    Module,
    _call_func_name,
    _declared_mounts,
    _docstring_nodes,
    _keyword,
    _literal,
    _parse,
    _string_assignments,
    _uses_name,
    _wiring_projection,
)

# Rule 31's seam producers, relative to the core package.  The templates render
# the discovered module set at request time through the runtime tag library; the
# theme's TypeScript may still name its own React surfaces (rule 37's allowlist).
THEME_SEAM_TEMPLATE = "generator/templates/themes/showcase_react/templates/index.html.j2"

THEME_SEAM_TEMPLATES: tuple[str, ...] = (
    THEME_SEAM_TEMPLATE,
    "generator/templates/themes/showcase_react/templates/social/link_tree.html.j2",
    "generator/templates/themes/showcase_react/templates/social/embeds.html.j2",
)

#: Rule 31's runtime seam library: every producer loads it, and its tags
#: resolve the flags and paths from the shipped inventory and live settings
#: (``quickscale_core.runtime.seam_tags``).
SEAM_LIBRARY_LOAD = re.compile(r"{%\s*load\b[^%]*\bquickscale_seam\b[^%]*%}")

# Rule 41's stated exceptions: orgs' tenancy-mode shell reservations and
# forms' shallow reservations stay host-rendered, but since SA258 they render
# from the versioned runtime URLconf (quickscale_core.runtime.urls) instead of
# a generator template, so no host template carries their mount.  The 404
# hints test a requested path against the module's mount; they declare no
# route.
RULE_7_ALLOWED_TEMPLATE_MOUNTS: dict[tuple[str, str], str] = {
    ("generator/templates/templates/404.html.j2", "auth"): (
        "the 404 hint tests the requested path against the module's mount; it declares no route"
    ),
    ("generator/templates/templates/404.html.j2", "billing"): (
        "the 404 hint tests the requested path against the module's mount; it declares no route"
    ),
}

# Rule 19's forbidden tokens, the listed operator paths where a superuser check
# is sanctioned (audited cross-tenant operator access), and the listed traffic
# filter.  Rule 46's discovery finds view code by content: a class that
# subclasses a Django or DRF view (directly or through a class the same file
# defines), or any function taking a ``request`` parameter.  View code a split
# files under any private name is therefore scanned, and a token is sanctioned
# only by an explicit mapping entry.
VIEW_MODULE_PREFIXES = (
    "django.contrib.auth.views",
    "django.views",
    "rest_framework.views",
    "rest_framework.generics",
    "rest_framework.viewsets",
)

FORBIDDEN_VIEW_TOKENS = ("is_staff", "is_superuser", "IsAdminUser", "redirect_to_login")

OPERATOR_TOKENS: dict[tuple[str, str], frozenset[str]] = {
    ("forms", "views.py"): frozenset({"is_superuser"}),
    ("orgs", "_api_views.py"): frozenset({"is_superuser"}),
    ("orgs", "_debug.py"): frozenset({"is_superuser"}),
    ("orgs", "_view_context.py"): frozenset({"is_superuser"}),
    ("orgs", "_view_org_management.py"): frozenset({"is_superuser"}),
    ("orgs", "admin.py"): frozenset({"is_superuser"}),
    ("orgs", "debug_views.py"): frozenset({"is_superuser"}),
    ("orgs", "middleware.py"): frozenset({"is_superuser"}),
    ("orgs", "permissions.py"): frozenset({"is_superuser"}),
}

# Rule 19's listed exception for analytics' EXCLUDE_STAFF: the filter reads
# ``is_staff`` to hide analytics from staff requests, not to authorize one.
TRAFFIC_FILTER_TOKENS: dict[tuple[str, str], frozenset[str]] = {
    ("analytics", "services.py"): frozenset({"is_staff"}),
}

RATE_LITERAL = re.compile(r"\d+/(?:second|minute|hour|day)")

#: Rule 9's one session authentication class (SA262), shipped in the
#: ``quickscale_core.runtime`` facade.  A module-defined subclass or a direct
#: DRF spelling fails the closed world.
CORE_SESSION_AUTHENTICATION = "QuickscaleSessionAuthentication"

#: Rule 9's one list paginator (SA262), shipped in the
#: ``quickscale_core.runtime`` facade.  A module paginator subclasses it and
#: declares the ``<THING>_PER_PAGE`` setting it reads; a
#: ``PageNumberPagination`` subclass outside that world and a literal
#: ``page_size`` both fail the closed world.
CORE_LIST_PAGINATION = "PlainListPagination"


def _declares_literal_url_includes(value: ast.expr) -> bool:
    """
    Return True when a non-empty list/tuple literal hard-codes URL wiring.

    Rule 7 makes the manifest the only place that sets a module's mount, so an
    adapter naming literal include pairs violates it.  An *empty* literal
    declares no include at all: it is how a switched-off module mounts none of
    its public URLs (rule 1), so it stays allowed and the check must not flag it.
    """
    return isinstance(value, (ast.List, ast.Tuple)) and bool(value.elts)


def rule_7_urls(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        package = f"quickscale_modules_{module.name}"
        includes = _wiring_projection(module.manifest, "url_includes")
        own = [
            entry
            for entry in includes
            if isinstance(entry, list)
            and len(entry) == 2
            and isinstance(entry[1], str)
            and entry[1] == f"{package}.urls"
        ]
        for entry in includes:
            if not isinstance(entry, list) or len(entry) != 2:
                violations.append(f"rule 7: {module.name}: malformed url_includes entry {entry!r}")
                continue
            mount = entry[0]
            if not isinstance(mount, str) or not mount or mount.startswith("/"):
                violations.append(
                    f"rule 7: {module.name}: url mount {mount!r} must be a non-empty relative path"
                )
        if "urls.py" in module.files and not own:
            violations.append(
                f"rule 7: {module.name}: manifest url_includes does not mount {package}.urls"
            )
        adapter = module.files.get("adapter.py", "")
        if adapter:
            for node in ast.walk(_parse(adapter)):
                if isinstance(node, ast.Call):
                    for keyword in node.keywords:
                        if keyword.arg == "url_includes" and _declares_literal_url_includes(
                            keyword.value
                        ):
                            violations.append(
                                f"rule 7: {module.name}: adapter.py declares a literal url_includes"
                            )
                    continue
                targets: list[ast.expr] = []
                if isinstance(node, ast.Assign) and _declares_literal_url_includes(node.value):
                    targets = list(node.targets)
                elif (
                    isinstance(node, ast.AnnAssign)
                    and node.value is not None
                    and _declares_literal_url_includes(node.value)
                ):
                    targets = [node.target]
                for target in targets:
                    if isinstance(target, ast.Name) and target.id == "url_includes":
                        violations.append(
                            f"rule 7: {module.name}: adapter.py declares a literal url_includes"
                        )
        urls = module.files.get("urls.py")
        if urls is None:
            continue
        tree = _parse(urls)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = _call_func_name(node)
            if func in {"path", "re_path"}:
                name = _literal(_keyword(node, "name"))
                if isinstance(name, str):
                    violations.extend(_route_name_violations(module.name, name, "path name"))
            elif func == "register" and node.args and isinstance(node.args[0], ast.Constant):
                basename = _literal(_keyword(node, "basename"))
                if isinstance(basename, str):
                    violations.extend(
                        _route_name_violations(module.name, basename, "router basename")
                    )
                elif basename is None:
                    violations.append(
                        f"rule 7: {module.name}: router.register without an explicit basename"
                    )
        root_view_name = _string_assignments(tree).get("root_view_name")
        if root_view_name is not None:
            violations.extend(_route_name_violations(module.name, root_view_name, "api root"))
    violations.extend(_template_mount_literal_violations(corpus))
    return violations


def _template_mount_literal_violations(corpus: Corpus) -> list[str]:
    """
    Rule 7 over the generator's Jinja templates (enforcement gap 13).

    A declared module mount written as a host route literal in a ``.j2``
    file shadows the module the same way a copied mount does in Python; the
    rule-41 exceptions are the entries in ``RULE_7_ALLOWED_TEMPLATE_MOUNTS``.
    """
    violations: list[str] = []
    declared = {module.name: _declared_mounts(module) for module in corpus.modules}
    for rel, text in corpus.core_files.items():
        if not (rel.startswith(GENERATOR_TEMPLATE_ROOT) and rel.endswith(".j2")):
            continue
        for module_name, mounts in declared.items():
            if (rel, module_name) in RULE_7_ALLOWED_TEMPLATE_MOUNTS:
                continue
            for mount in mounts:
                if not mount:
                    continue
                anchor = mount.rstrip("/")
                # An anchored route claims the mount only while the mount's
                # segment ends there; ``^blogroll`` and ``^blog-roll`` are not
                # blog's mount.
                route_pattern = re.compile(rf"""[r]?["']\^{re.escape(anchor)}(?![A-Za-z0-9_-])""")
                literals = (
                    f'path("{mount}',
                    f"path('{mount}",
                    f'"/{mount}"',
                    f"'/{mount}'",
                    f'"{mount}"',
                    f"'{mount}'",
                    # A quoted absolute path under the mount (``"/billing/api/"``)
                    # repeats the mount just as the bare mount does.
                    f'"/{anchor}/',
                    f"'/{anchor}/",
                )
                if route_pattern.search(text) or any(literal in text for literal in literals):
                    violations.append(
                        f"rule 7: core {rel}: module '{module_name}' mount "
                        f"'{mount}' is written as a literal"
                    )
    return violations


def _route_name_violations(module: str, name: str, where: str) -> list[str]:
    violations: list[str] = []
    skeleton = name.replace("{basename}", "x").replace("{url_name}", "x").replace("{lookup}", "x")
    if "{" in skeleton or "}" in skeleton:
        violations.append(f"rule 7: {module}: unresolved route template {name!r} in {where}")
        return violations
    if not SNAKE_CASE.match(skeleton):
        violations.append(f"rule 7: {module}: route name {name!r} in {where} is not snake_case")
    if re.search(rf"(^|_){module}(_|$)", skeleton):
        violations.append(f"rule 7: {module}: route name {name!r} in {where} repeats the module")
    return violations


def _is_admin_model_override(value: str) -> bool:
    """Return whether a template path is Django's ``admin/<label>/<model>/``."""
    parts = value.split("/")
    return len(parts) >= 4 and parts[0] == "admin" and all(parts[1:4]) and value.endswith(".html")


def rule_8_templates(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        stem = f"quickscale_{module.name}"
        base_rel = f"templates/{stem}/base.html"
        pages: list[str] = []
        for rel, text in module.files.items():
            if not rel.startswith("templates/") or not rel.endswith(".html"):
                continue
            if Path(rel).name.startswith("_"):
                continue
            parts = rel.split("/")[1:-1]
            if any(part in ALLOWED_TEMPLATE_DIRS for part in parts):
                continue
            if "email" in parts:
                continue
            if parts and parts[0] != stem:
                continue
            pages.append(rel)
        if pages:
            if base_rel not in module.files:
                violations.append(f"rule 8: {module.name}: missing module base {base_rel}")
            else:
                if not re.search(r'\{%\s*extends\s+["\']base\.html["\']', module.files[base_rel]):
                    violations.append(
                        f"rule 8: {module.name}: {base_rel} does not extend base.html"
                    )
                content_block = re.search(
                    rf"\{{%\s*block\s+{re.escape(module.name)}_content\s*%\}}",
                    module.files[base_rel],
                )
                if content_block is None:
                    violations.append(
                        f"rule 8: {module.name}: {base_rel} owns no {module.name}_content block"
                    )
            for rel in pages:
                text = module.files[rel]
                parts = rel.split("/")[1:-1]
                if len(parts) > 1:
                    violations.append(
                        f"rule 8: {module.name}: {rel} is not flat under templates/{stem}/"
                    )
                if re.search(r"<html\b", text, re.IGNORECASE):
                    violations.append(f"rule 8: {module.name}: {rel} emits <html>")
                if rel == base_rel:
                    continue
                if not re.search(rf'\{{%\s*extends\s+["\']{re.escape(stem)}/base\.html["\']', text):
                    violations.append(
                        f"rule 8: {module.name}: {rel} does not extend {stem}/base.html"
                    )
                if not re.search(rf"\{{%\s*block\s+{re.escape(module.name)}_content\s*%\}}", text):
                    violations.append(
                        f"rule 8: {module.name}: {rel} fills no {module.name}_content block"
                    )
        for rel in module.files:
            if not rel.startswith("static/"):
                continue
            parts = rel.split("/")
            if parts[1] != stem:
                violations.append(f"rule 8: {module.name}: static path {rel} lacks the {stem} root")
                continue
            if len(parts) >= 4 and parts[2] not in {"css", "js", "img"}:
                violations.append(f"rule 8: {module.name}: static path {rel} is outside css/js/img")
        for rel in module.files:
            if not rel.startswith("templatetags/") or not rel.endswith(".py"):
                continue
            library = Path(rel).stem
            if library in {"__init__"} or library.startswith("_"):
                continue
            if library != stem and not library.startswith(f"{stem}_"):
                violations.append(
                    f"rule 8: {module.name}: template tag library {library!r} lacks the {stem} stem"
                )
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            for node in ast.walk(_parse(text)):
                if not isinstance(node, ast.Assign):
                    continue
                for target in node.targets:
                    if not isinstance(target, ast.Name) or target.id not in {
                        "change_list_template",
                        "change_form_template",
                    }:
                        continue
                    value = _literal(node.value)
                    if isinstance(value, str) and not _is_admin_model_override(value):
                        violations.append(
                            f"rule 8: {module.name}: {rel} admin override {value!r} is not "
                            "under admin/<label>/<model>/"
                        )
    return violations


def rule_9_http_apis(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        paginator_classes = _paginator_classifications(module)
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            tree = _parse(text)
            if _uses_name(tree, "JsonResponse"):
                violations.append(f"rule 9: {module.name}: {rel} uses JsonResponse")
            violations.extend(_session_authentication_violations(module.name, rel, tree))
            violations.extend(_pagination_violations(module.name, rel, tree, paginator_classes))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and _call_func_name(node) == "HttpResponse":
                    content_type = _literal(_keyword(node, "content_type"))
                    if isinstance(content_type, str) and "json" in content_type:
                        violations.append(
                            f"rule 9: {module.name}: {rel} builds a JSON HttpResponse"
                        )
                if isinstance(node, ast.Dict):
                    error_values = [
                        value
                        for key, value in zip(node.keys, node.values)
                        if isinstance(key, ast.Constant) and key.value == "error"
                    ]
                    if not error_values:
                        continue
                    value = error_values[0]
                    if isinstance(value, ast.Dict):
                        violations.append(
                            f"rule 9: {module.name}: {rel} builds an error body in module code"
                        )
    violations.extend(_rendered_managed_json_violations())
    return violations


def _session_authentication_bindings(
    tree: ast.Module,
) -> tuple[set[str], set[str], dict[str, str]]:
    """
    Resolve a module's DRF and core session-authentication bindings.

    Returns the names bound to DRF's ``SessionAuthentication``, the names
    bound to core's one session authentication class, and the namespace
    aliases bound to ``rest_framework.authentication``, so ``from
    rest_framework.authentication import SessionAuthentication``,
    ``from rest_framework import authentication``, and the fully qualified
    ``rest_framework.authentication.SessionAuthentication`` all resolve.
    """
    drf_names: set[str] = set()
    core_names: set[str] = set()
    namespaces: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                binding = alias.asname or alias.name
                if (
                    node.module == "rest_framework.authentication"
                    and alias.name == "SessionAuthentication"
                ):
                    drf_names.add(binding)
                elif (
                    node.module == "quickscale_core.runtime"
                    or node.module.startswith("quickscale_core.runtime.")
                ) and alias.name == CORE_SESSION_AUTHENTICATION:
                    core_names.add(binding)
                elif node.module == "rest_framework" and alias.name == "authentication":
                    namespaces[binding] = "rest_framework.authentication"
                elif node.module == "quickscale_core" and alias.name == "runtime":
                    namespaces[binding] = "quickscale_core.runtime"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in {
                    "rest_framework",
                    "rest_framework.authentication",
                    "quickscale_core",
                    "quickscale_core.runtime",
                }:
                    root = alias.asname or alias.name.split(".")[0]
                    namespaces[root] = alias.name if alias.asname else root
    return drf_names, core_names, namespaces


def _resolves_to_drf_session_authentication(
    node: ast.expr, drf_names: set[str], namespaces: dict[str, str]
) -> bool:
    """Return whether a base or value resolves to DRF's SessionAuthentication."""
    if isinstance(node, ast.Name):
        return node.id in drf_names
    dotted = _dotted_name(node)
    if dotted is None:
        return False
    root, _, rest = dotted.partition(".")
    if not rest:
        return dotted in drf_names
    resolved = f"{namespaces.get(root, root)}.{rest}"
    return resolved == "rest_framework.authentication.SessionAuthentication"


def _resolves_to_core_session_authentication(
    node: ast.expr, core_names: set[str], namespaces: dict[str, str]
) -> bool:
    """Return whether a value resolves to core's one session authentication class."""
    if isinstance(node, ast.Name):
        return node.id in core_names
    dotted = _dotted_name(node)
    if dotted is None:
        return False
    root, _, rest = dotted.partition(".")
    if not rest:
        return dotted in core_names
    return f"{namespaces.get(root, root)}.{rest}" in {
        "quickscale_core.runtime.QuickscaleSessionAuthentication",
        "quickscale_core.runtime.drf.QuickscaleSessionAuthentication",
    }


def _session_authentication_violations(module_name: str, rel: str, tree: ast.Module) -> list[str]:
    """
    Return rule 9's session-authentication violations for one module file.

    Closed world: a module defines no ``SessionAuthentication`` subclass, and
    an ``authentication_classes`` literal names core's one session
    authentication class or is empty (the webhook and public-read case).
    """
    violations: list[str] = []
    drf_names, core_names, namespaces = _session_authentication_bindings(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if any(
            _resolves_to_drf_session_authentication(base, drf_names, namespaces)
            for base in node.bases
        ):
            violations.append(
                f"rule 9: {module_name}: {rel} defines a SessionAuthentication subclass"
            )
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
            value = node.value
        else:
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "authentication_classes"
            for target in targets
        ):
            continue
        if isinstance(value, (ast.List, ast.Tuple)):
            elements = value.elts
        else:
            violations.append(
                f"rule 9: {module_name}: {rel} sets authentication_classes to a non-literal value"
            )
            continue
        for element in elements:
            if _resolves_to_core_session_authentication(element, core_names, namespaces):
                continue
            if _resolves_to_drf_session_authentication(element, drf_names, namespaces):
                violations.append(
                    f"rule 9: {module_name}: {rel} names DRF's SessionAuthentication directly"
                )
            else:
                violations.append(
                    f"rule 9: {module_name}: {rel} authentication_classes entry is "
                    "not core's session authentication class"
                )
    return violations


def _pagination_bindings(
    tree: ast.Module,
) -> tuple[set[str], set[str], dict[str, str]]:
    """
    Resolve a module's DRF and core list-pagination bindings.

    Returns the names bound to DRF's ``PageNumberPagination``, the names
    bound to core's one list paginator, and the namespace aliases bound to
    ``rest_framework.pagination``, so the direct import, the ``pagination``
    module alias, and the fully qualified spelling all resolve.
    """
    drf_names: set[str] = set()
    core_names: set[str] = set()
    namespaces: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                binding = alias.asname or alias.name
                if (
                    node.module == "rest_framework.pagination"
                    and alias.name == "PageNumberPagination"
                ):
                    drf_names.add(binding)
                elif (
                    node.module == "quickscale_core.runtime"
                    or node.module.startswith("quickscale_core.runtime.")
                ) and alias.name == CORE_LIST_PAGINATION:
                    core_names.add(binding)
                elif node.module == "rest_framework" and alias.name == "pagination":
                    namespaces[binding] = "rest_framework.pagination"
                elif node.module == "quickscale_core" and alias.name == "runtime":
                    namespaces[binding] = "quickscale_core.runtime"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in {
                    "rest_framework",
                    "rest_framework.pagination",
                    "quickscale_core",
                    "quickscale_core.runtime",
                }:
                    root = alias.asname or alias.name.split(".")[0]
                    namespaces[root] = alias.name if alias.asname else root
    return drf_names, core_names, namespaces


def _resolves_to_drf_page_number_pagination(
    node: ast.expr, drf_names: set[str], namespaces: dict[str, str]
) -> bool:
    """Return whether a base resolves to DRF's PageNumberPagination."""
    if isinstance(node, ast.Name):
        return node.id in drf_names
    dotted = _dotted_name(node)
    if dotted is None:
        return False
    root, _, rest = dotted.partition(".")
    if not rest:
        return dotted in drf_names
    return (
        f"{namespaces.get(root, root)}.{rest}" == "rest_framework.pagination.PageNumberPagination"
    )


def _resolves_to_core_list_pagination(
    node: ast.expr, core_names: set[str], namespaces: dict[str, str]
) -> bool:
    """Return whether a base resolves to core's one list paginator."""
    if isinstance(node, ast.Name):
        return node.id in core_names
    dotted = _dotted_name(node)
    if dotted is None:
        return False
    root, _, rest = dotted.partition(".")
    if not rest:
        return dotted in core_names
    return f"{namespaces.get(root, root)}.{rest}" in {
        "quickscale_core.runtime.PlainListPagination",
        "quickscale_core.runtime.drf.PlainListPagination",
    }


def _declares_page_size_setting(class_node: ast.ClassDef) -> bool:
    """Return whether a paginator subclass declares a literal page_size_setting."""
    for statement in class_node.body:
        if isinstance(statement, ast.Assign):
            targets = statement.targets
            value = statement.value
        elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
            targets = [statement.target]
            value = statement.value
        else:
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "page_size_setting" for target in targets
        ):
            continue
        return isinstance(value, ast.Constant) and isinstance(value.value, str)
    return False


def _paginator_classifications(module: Module) -> dict[str, dict[str, str]]:
    """
    Classify the paginator classes each module file defines.

    Maps a package-relative file to ``{class name: "core" | "drf"}`` for every
    class whose direct base resolves to core's one list paginator or to DRF's
    ``PageNumberPagination``.  The map lets another file's ``pagination_class``
    resolve a paginator imported from a sibling module file (rule 28 sanctions
    private sibling modules).
    """
    classifications: dict[str, dict[str, str]] = {}
    for rel, text in module.files.items():
        if not rel.endswith(".py") or rel.startswith("migrations/"):
            continue
        tree = _parse(text)
        drf_names, core_names, namespaces = _pagination_bindings(tree)
        classes: dict[str, str] = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if any(
                _resolves_to_core_list_pagination(base, core_names, namespaces)
                for base in node.bases
            ):
                classes[node.name] = "core"
            elif any(
                _resolves_to_drf_page_number_pagination(base, drf_names, namespaces)
                for base in node.bases
            ):
                classes[node.name] = "drf"
        classifications[rel] = classes
    return classifications


def _sibling_paginator_imports(
    module_name: str,
    tree: ast.Module,
    classifications: dict[str, dict[str, str]],
) -> dict[str, str]:
    """
    Map imported names to the paginator class they resolve to in a sibling file.

    Resolves relative imports (``from ._pagination import DemoPagination``) and
    the module's own absolute package imports
    (``from quickscale_modules_<name>._pagination import ...``) against the
    per-file classifications.
    """
    imports: dict[str, str] = {}
    package_stem = f"quickscale_modules_{module_name}"
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        target_rel: str | None = None
        if node.level == 1 and node.module:
            target_rel = f"{node.module.replace('.', '/')}.py"
        elif node.module and (
            node.module == package_stem or node.module.startswith(f"{package_stem}.")
        ):
            remainder = node.module[len(package_stem) :].lstrip(".")
            if remainder:
                target_rel = f"{remainder.replace('.', '/')}.py"
        if target_rel is None:
            continue
        target_classes = classifications.get(target_rel)
        if not target_classes:
            continue
        for alias in node.names:
            if alias.name in target_classes:
                imports[alias.asname or alias.name] = target_classes[alias.name]
    return imports


def _pagination_violations(
    module_name: str,
    rel: str,
    tree: ast.Module,
    paginator_classes: dict[str, dict[str, str]],
) -> list[str]:
    """
    Return rule 9's list-pagination violations for one module file.

    Closed world: a module defines no ``PageNumberPagination`` subclass
    outside core's one list paginator; a paginator subclass declares the
    ``page_size_setting`` it reads; a ``pagination_class`` names such a
    subclass (defined here or imported from a sibling module file); and no
    code sets a literal ``page_size``.
    """
    violations: list[str] = []
    drf_names, core_names, namespaces = _pagination_bindings(tree)
    sibling_imports = _sibling_paginator_imports(module_name, tree, paginator_classes)
    local_core_paginators: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        core_base = any(
            _resolves_to_core_list_pagination(base, core_names, namespaces) for base in node.bases
        ) or any(
            isinstance(base, ast.Name) and sibling_imports.get(base.id) == "core"
            for base in node.bases
        )
        if core_base:
            local_core_paginators.add(node.name)
            if not _declares_page_size_setting(node):
                violations.append(
                    f"rule 9: {module_name}: {rel} paginator {node.name} must declare "
                    "page_size_setting"
                )
            continue
        drf_base = any(
            _resolves_to_drf_page_number_pagination(base, drf_names, namespaces)
            for base in node.bases
        ) or any(
            isinstance(base, ast.Name) and sibling_imports.get(base.id) == "drf"
            for base in node.bases
        )
        if drf_base:
            violations.append(
                f"rule 9: {module_name}: {rel} defines a PageNumberPagination subclass "
                f"{node.name} outside core"
            )
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
            value = node.value
        else:
            continue
        if not any(isinstance(target, ast.Name) for target in targets):
            continue
        names = {target.id for target in targets if isinstance(target, ast.Name)}
        if "page_size" in names and isinstance(value, ast.Constant):
            if isinstance(value.value, int):
                violations.append(f"rule 9: {module_name}: {rel} sets a literal page_size")
        if "pagination_class" in names:
            resolved = None
            if isinstance(value, ast.Name):
                if value.id in local_core_paginators:
                    resolved = "core"
                else:
                    resolved = sibling_imports.get(value.id)
            if resolved != "core":
                violations.append(
                    f"rule 9: {module_name}: {rel} pagination_class must name a subclass "
                    "of core's PlainListPagination"
                )
    return violations


def _rendered_managed_json_violations() -> list[str]:
    """
    Return rule 9 violations from core's managed-file renderer output.

    The managed files core renders into a generated project are outside the
    module corpus, so the detector renders them once and parses the result
    the same way module source is parsed (rule 9: generated project code that
    serves JSON follows rule 9).
    """
    from quickscale_core.manifest.social_manifest import (  # noqa: PLC0415
        render_social_managed_views_module,
    )

    content = render_social_managed_views_module(
        provider_allowlist=["youtube", "tiktok"],
        embed_provider_allowlist=["youtube", "tiktok"],
        layout_variant="list",
        cache_ttl_seconds=300,
        links_per_page=24,
        embeds_per_page=12,
    )
    tree = _parse(content)
    violations: list[str] = []
    if _uses_name(tree, "JsonResponse"):
        violations.append("rule 9: managed social views (rendered) use JsonResponse")
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        error_values = [
            value
            for key, value in zip(node.keys, node.values)
            if isinstance(key, ast.Constant) and key.value == "error"
        ]
        if error_values and isinstance(error_values[0], ast.Dict):
            violations.append("rule 9: managed social views (rendered) build an error body")
    return violations


def _view_token(node: ast.AST) -> str | None:
    """Return the forbidden authorization token a view node uses, if any."""
    if isinstance(node, ast.Name) and node.id in FORBIDDEN_VIEW_TOKENS:
        return node.id
    if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_VIEW_TOKENS:
        return node.attr
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        if node.value in FORBIDDEN_VIEW_TOKENS:
            return node.value
    return None


def _is_view_module(module: str) -> bool:
    """Return whether ``module`` is a Django or DRF module that defines views."""
    return any(
        module == prefix or module.startswith(f"{prefix}.") for prefix in VIEW_MODULE_PREFIXES
    )


def _view_bindings(tree: ast.Module) -> tuple[set[str], dict[str, str]]:
    """
    Resolve a module's Django and DRF view bindings.

    Returns the names bound to view classes and the namespace aliases bound to
    view modules, mapped to their dotted targets, so ``from rest_framework
    import views``, ``import rest_framework.views as drf_views``, and a fully
    qualified ``rest_framework.views.APIView`` all resolve.  A base imported
    from another project module is not resolved.
    """
    names: set[str] = set()
    namespaces: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                target = f"{node.module}.{alias.name}"
                binding = alias.asname or alias.name
                if _is_view_module(node.module):
                    names.add(binding)
                if _is_view_module(target):
                    namespaces[binding] = target
        elif isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.asname or alias.name.split(".")[0]
                namespaces[root] = alias.name if alias.asname else root
    return names, namespaces


def _dotted_name(node: ast.expr) -> str | None:
    """Return the dotted spelling of a name or attribute chain, if it has one."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        value = _dotted_name(node.value)
        return f"{value}.{node.attr}" if value is not None else None
    return None


def _is_view_base(node: ast.expr, names: set[str], namespaces: dict[str, str]) -> bool:
    """Return whether a class base resolves to a Django or DRF view class."""
    if isinstance(node, ast.Name):
        return node.id in names
    dotted = _dotted_name(node)
    if dotted is None:
        return False
    root, _, rest = dotted.partition(".")
    if not rest:
        return dotted in names
    resolved = f"{namespaces.get(root, root)}.{rest}"
    return any(resolved.startswith(f"{prefix}.") for prefix in VIEW_MODULE_PREFIXES)


def _defines_view_class(tree: ast.Module) -> bool:
    """Return whether a module defines a Django or DRF view subclass."""
    names, namespaces = _view_bindings(tree)
    if not names and not namespaces:
        return False
    classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    view_classes: set[str] = set()
    changed = True
    while changed:
        changed = False
        for node in classes:
            if node.name in view_classes:
                continue
            if any(
                _is_view_base(base, names, namespaces)
                or (isinstance(base, ast.Name) and base.id in view_classes)
                for base in node.bases
            ):
                view_classes.add(node.name)
                changed = True
    return bool(view_classes)


def _takes_request(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return whether a function or method declares a ``request`` parameter."""
    parameters = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
    return any(parameter.arg == "request" for parameter in parameters)


def _defines_view_code(tree: ast.Module) -> bool:
    """
    Rule 46's discovery: return whether a module defines view code.

    View code is a Django or DRF view subclass or a function taking
    ``request``; the scan set no longer follows file names, so a split that
    files view code under any private name stays inside the check.
    """
    if _defines_view_class(tree):
        return True
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _takes_request(node)
        for node in ast.walk(tree)
    )


def rule_19_authorization(corpus: Corpus) -> list[str]:
    """
    Rule 19: module views authorize by org role, not site-wide staff flags.

    The statically checkable clause: ``is_staff``, ``is_superuser``,
    ``IsAdminUser``, and hand-written ``redirect_to_login`` — imported or
    aliased, read as an attribute, or passed as a string — appear only in the
    listed operator paths.  Rule 46 finds the view code to scan by content
    rather than by file name: every file that defines a Django or DRF view
    subclass or a function taking ``request``, wherever a rule 28 split files
    it.  The "logged in is one of the three idioms" and "README lists the
    minimum role" clauses stay review rules: rule 9 sanctions ``AllowAny`` plus
    a view's own authentication, and the README prose is not a code property.
    """
    violations: list[str] = []
    for module in corpus.modules:
        for rel, text in module.files.items():
            if not rel.endswith(".py"):
                continue
            tree = _parse(text)
            if not _defines_view_code(tree):
                continue
            key = (module.name, Path(rel).name)
            allowed = OPERATOR_TOKENS.get(key, frozenset()) | TRAFFIC_FILTER_TOKENS.get(
                key, frozenset()
            )
            docstrings = _docstring_nodes(tree)
            for node in ast.walk(tree):
                token = _view_token(node)
                if token is None or token in allowed:
                    continue
                if isinstance(node, ast.Constant) and id(node) in docstrings:
                    continue
                violations.append(
                    f"rule 19: {module.name}: {rel}:{node.lineno} uses {token} outside "
                    "the listed operator paths"
                )
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    imported = [alias.name for alias in node.names]
                elif isinstance(node, ast.Import):
                    imported = [alias.name.split(".")[-1] for alias in node.names]
                else:
                    continue
                for name in imported:
                    if name in FORBIDDEN_VIEW_TOKENS and name not in allowed:
                        violations.append(
                            f"rule 19: {module.name}: {rel}:{node.lineno} imports {name} "
                            "outside the listed operator paths"
                        )
    return violations


def rule_31_theme_seam(corpus: Corpus) -> list[str]:
    """
    Rule 31: the seam producer renders discovery at request time.

    The statically checkable clauses of the seam's producers, the theme's
    ``index.html.j2`` and its two public social pages: each loads the
    ``quickscale_seam`` runtime tag library and renders the discovered flags
    and paths through its tags instead of literal module lines or mount paths,
    and the index template carries no ``INSTALLED_APPS`` test (the runtime
    library holds it).  A loaded core tree without the template fails; an
    empty synthetic corpus does not.
    """
    violations: list[str] = []
    index_template = corpus.core_files.get(THEME_SEAM_TEMPLATE)
    if index_template is None:
        if corpus.core_files:
            violations.append("rule 31: the core tree carries no theme index.html.j2 seam producer")
        return violations
    for rel in THEME_SEAM_TEMPLATES:
        template = corpus.core_files.get(rel)
        if template is None:
            continue
        for tag in ("{% seam_module_flags %}", "{% seam_module_paths %}"):
            if tag not in template:
                violations.append(f"rule 31: {rel} does not render {tag}")
        if SEAM_LIBRARY_LOAD.search(template) is None:
            violations.append(f"rule 31: {rel} does not load the quickscale_seam tag library")
        for module in corpus.modules:
            name = module.name
            for mount in _declared_mounts(module):
                if not mount:
                    continue
                for literal in (f'"{mount}"', f"'{mount}'", f'"/{mount}"', f"'/{mount}'"):
                    if literal in template:
                        violations.append(
                            f"rule 31: {rel} writes {name}'s mount {mount!r} literally"
                        )
            if rel != THEME_SEAM_TEMPLATE:
                for literal in (f'"{name}":', f"'{name}':"):
                    if literal in template:
                        violations.append(f"rule 31: {rel} writes module {name!r} as a key")
            if re.search(rf"(?m)^\s*{re.escape(name)}\s*:", template):
                violations.append(f"rule 31: {rel} writes module {name!r} as a bare key")
    for module in corpus.modules:
        name = module.name
        literals = (
            f'"{name}"',
            f"'{name}'",
            f'"/{name}/"',
            f"'/{name}/'",
            f'"{name}/"',
            f"'{name}/'",
        )
        for literal in literals:
            if literal in index_template:
                violations.append(
                    f"rule 31: the theme's index.html.j2 names module {name!r} literally"
                )
    if "INSTALLED_APPS" in index_template:
        violations.append("rule 31: the theme's index.html.j2 carries an INSTALLED_APPS test")
    return violations


def _webhook_view_names(module: Module) -> set[str]:
    """Return the view classes the module routes as webhooks (rule 26)."""
    urls = module.files.get("urls.py")
    if urls is None:
        return set()
    names: set[str] = set()
    for node in ast.walk(_parse(urls)):
        if not isinstance(node, ast.Call) or _call_func_name(node) != "path":
            continue
        route = _literal(node.args[0]) if node.args else None
        name = _literal(_keyword(node, "name"))
        if not (
            (isinstance(route, str) and "webhooks/" in route)
            or (isinstance(name, str) and "webhook" in name)
        ):
            continue
        if len(node.args) < 2:
            continue
        view = node.args[1]
        if (
            isinstance(view, ast.Call)
            and isinstance(view.func, ast.Attribute)
            and view.func.attr == "as_view"
        ):
            target = view.func.value
            if isinstance(target, ast.Name):
                names.add(target.id)
            elif isinstance(target, ast.Attribute):
                names.add(target.attr)
    return names


def _throttle_registration_violations(
    module_name: str,
    rel: str,
    tree: ast.Module,
    webhook_views: set[str],
) -> list[str]:
    """
    Rule 32's closed world over ``throttle_classes`` registrations.

    A view attaches a throttle through ``throttle_scope`` only, through
    core's one scoped throttle class.  The single sanctioned literal is the
    empty ``throttle_classes`` rule 26 requires on a webhook view; every
    other registration, empty or not, fails — as a class attribute or
    through an ``as_view(throttle_classes=...)`` mount.
    """
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        else:
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "throttle_classes" for target in targets
        ):
            continue
        owner = parents.get(node)
        while owner is not None and not isinstance(owner, (ast.ClassDef, ast.Module)):
            owner = parents.get(owner)
        class_name = owner.name if isinstance(owner, ast.ClassDef) else None
        empty_literal = isinstance(value, (ast.List, ast.Tuple)) and not value.elts
        if class_name is not None and class_name in webhook_views and empty_literal:
            continue
        if class_name is None:
            violations.append(
                f"rule 32: {module_name}: {rel} assigns throttle_classes outside a view class"
            )
        elif class_name in webhook_views:
            violations.append(
                f"rule 32: {module_name}: {rel}: webhook {class_name} declares a "
                "non-empty throttle_classes"
            )
        else:
            violations.append(
                f"rule 32: {module_name}: {rel}: {class_name} declares "
                "throttle_classes; a throttle attaches through throttle_scope only"
            )
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _call_func_name(node) != "as_view":
            continue
        override = _keyword(node, "throttle_classes")
        if override is None:
            continue
        func = node.func
        target = func.value if isinstance(func, ast.Attribute) else None
        target_name: str | None = None
        if isinstance(target, ast.Name):
            target_name = target.id
        elif isinstance(target, ast.Attribute):
            target_name = target.attr
        empty_literal = isinstance(override, (ast.List, ast.Tuple)) and not override.elts
        if target_name is not None and target_name in webhook_views and empty_literal:
            continue
        if target_name in webhook_views:
            violations.append(
                f"rule 32: {module_name}: {rel}: webhook {target_name}.as_view() "
                "supplies a non-empty throttle_classes"
            )
        else:
            violations.append(
                f"rule 32: {module_name}: {rel}: as_view() supplies throttle_classes; "
                "a throttle attaches through throttle_scope only"
            )
    return violations


def rule_32_throttles(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        stem = f"quickscale_{module.name}"
        webhook_views = _webhook_view_names(module)
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            tree = _parse(text)
            violations.extend(
                _throttle_registration_violations(module.name, rel, tree, webhook_views)
            )
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name.endswith("Throttle"):
                    for stmt in node.body:
                        if not isinstance(stmt, ast.Assign):
                            continue
                        for target in stmt.targets:
                            if not isinstance(target, ast.Name):
                                continue
                            value = _literal(stmt.value)
                            if target.id == "rate":
                                violations.append(
                                    f"rule 32: {module.name}: {node.name} hard-codes a rate"
                                )
                            if target.id == "scope" and isinstance(value, str):
                                if not value.startswith(f"{stem}_"):
                                    violations.append(
                                        f"rule 32: {module.name}: {node.name} scope {value!r} "
                                        f"lacks the {stem}_ stem"
                                    )
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if (
                            isinstance(target, ast.Name)
                            and target.id == "throttle_scope"
                            and isinstance(node.value, ast.Constant)
                            and isinstance(node.value.value, str)
                            and not node.value.value.startswith(f"{stem}_")
                        ):
                            violations.append(
                                f"rule 32: {module.name}: {rel} throttle scope "
                                f"{node.value.value!r} lacks the {stem}_ stem"
                            )
            docstrings = _docstring_nodes(tree)
            for constant in ast.walk(tree):
                if not isinstance(constant, ast.Constant) or not isinstance(constant.value, str):
                    continue
                if id(constant) in docstrings:
                    continue
                match = RATE_LITERAL.search(constant.value)
                if match:
                    violations.append(
                        f"rule 32: {module.name}: {rel} writes a throttle rate literal "
                        f"{match.group()!r}"
                    )
                    break
            if _uses_name(tree, "RunSQL"):
                violations.append(f"rule 32: {module.name}: {rel} creates raw SQL objects")
    return violations
