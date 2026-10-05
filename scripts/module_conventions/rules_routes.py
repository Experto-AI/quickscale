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
# the discovered module set; the theme's TypeScript may still name its own
# React surfaces (rule 37's allowlist).
THEME_SEAM_TEMPLATE = "generator/templates/themes/showcase_react/templates/index.html.j2"

THEME_SEAM_TEMPLATES: tuple[str, ...] = (
    THEME_SEAM_TEMPLATE,
    "generator/templates/themes/showcase_react/templates/social/link_tree.html.j2",
    "generator/templates/themes/showcase_react/templates/social/embeds.html.j2",
)

# Rule 41's stated exception: the tenancy mode decides which side owns /orgs*
# (solo mounts orgs before home, saas after), so orgs' React shell
# reservations in the host URL template stay host-rendered.
RULE_7_ALLOWED_TEMPLATE_MOUNTS: dict[tuple[str, str], str] = {
    ("generator/templates/project_name/urls.py.j2", "orgs"): (
        "rule 41 exception: tenancy-mode shell reservations stay host-rendered"
    ),
    ("generator/templates/project_name/urls.py.j2", "forms"): (
        "rule 41 exception: forms' module entrypoint renders only a mount-point div, "
        "so the host shell keeps its shallow paths working until it hydrates"
    ),
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
    return violations


def rule_9_http_apis(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            tree = _parse(text)
            if _uses_name(tree, "JsonResponse"):
                violations.append(f"rule 9: {module.name}: {rel} uses JsonResponse")
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
    Rule 31: the seam producer renders discovery, not hand-written lines.

    The statically checkable clauses of the seam's producer, the theme's
    ``index.html.j2``: it emits the discovered flags and paths through the
    seam placeholders instead of literal module lines or mount paths, and it
    carries no ``INSTALLED_APPS`` test.  A loaded core tree without the
    template fails; an empty synthetic corpus does not.
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
        for placeholder in ("{{ seam_module_flags }}", "{{ seam_module_paths }}"):
            if placeholder not in template:
                violations.append(f"rule 31: {rel} does not render {placeholder}")
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


def rule_32_throttles(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        stem = f"quickscale_{module.name}"
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            tree = _parse(text)
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
