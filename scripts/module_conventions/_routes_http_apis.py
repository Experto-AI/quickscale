"""
Rule 9's JSON-response, session-authentication, pagination, and content-policy mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_routes`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast

from scripts.module_conventions._routes_view_index import _dotted_name
from scripts.module_conventions._webhooks_routes import _as_view_target, _route_entries
from scripts.module_conventions.core import (
    Corpus,
    Module,
    _call_func_name,
    _keyword,
    _literal,
    _parse,
    _uses_name,
)

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

#: Rule 9's JSON-only content contract: the generated ``REST_FRAMEWORK``
#: composes the JSON renderer and parser defaults through
#: ``quickscale_core.runtime.settings.compose_rest_framework``, so a module
#: view pins neither class.  A webhook reads its raw body and a file upload
#: declares the multipart parser it needs; those two keep their local policy.
JSON_RENDERER_CLASS = "rest_framework.renderers.JSONRenderer"
JSON_PARSER_CLASS = "rest_framework.parsers.JSONParser"
MULTIPART_PARSER_CLASSES = frozenset(
    {
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FileUploadParser",
    }
)
UPLOAD_MULTIPART_PARSERS = frozenset(
    {
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FileUploadParser",
    }
)
#: The two DRF view attributes rule 9's content contract claims.
CONTENT_POLICY_ATTRIBUTES = ("renderer_classes", "parser_classes")


def rule_9_http_apis(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        webhook_view_names = _webhook_view_names(module)
        paginator_classes = _paginator_classifications(module)
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            tree = _parse(text)
            if _uses_name(tree, "JsonResponse"):
                violations.append(f"rule 9: {module.name}: {rel} uses JsonResponse")
            violations.extend(_session_authentication_violations(module.name, rel, tree))
            violations.extend(_pagination_violations(module.name, rel, tree, paginator_classes))
            violations.extend(
                _content_policy_pin_violations(f"{module.name}: {rel}", tree, webhook_view_names)
            )
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
    violations.extend(_composed_json_default_violations())
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


def _paginator_class_violations(
    module_name: str,
    rel: str,
    tree: ast.Module,
    drf_names: set[str],
    core_names: set[str],
    namespaces: dict[str, str],
    sibling_imports: dict[str, str],
) -> tuple[list[str], set[str]]:
    """Return rule 9's paginator-class violations and the local core subclasses."""
    violations: list[str] = []
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
    return violations, local_core_paginators


def _pagination_attribute_violations(
    module_name: str,
    rel: str,
    tree: ast.Module,
    sibling_imports: dict[str, str],
    local_core_paginators: set[str],
) -> list[str]:
    """Return rule 9's literal-``page_size`` and ``pagination_class`` violations."""
    violations: list[str] = []
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
    drf_names, core_names, namespaces = _pagination_bindings(tree)
    sibling_imports = _sibling_paginator_imports(module_name, tree, paginator_classes)
    violations, local_core_paginators = _paginator_class_violations(
        module_name, rel, tree, drf_names, core_names, namespaces, sibling_imports
    )
    violations.extend(
        _pagination_attribute_violations(
            module_name, rel, tree, sibling_imports, local_core_paginators
        )
    )
    return violations


def _webhook_view_names(module: Module) -> frozenset[str]:
    """
    Return the view names the module mounts on its webhook routes (rule 26).

    The webhook route definition is rule 26's (a ``webhooks/`` path or a
    ``*webhook*`` name); a view rule 26 discovers as a webhook keeps its local
    parser policy, so the pin ban reads the same set.
    """
    urls = module.files.get("urls.py")
    if urls is None:
        return frozenset()
    view_names, _route_violations = _route_entries(module.name, urls)
    return frozenset(view_names)


def _parser_class_bindings(tree: ast.Module) -> tuple[dict[str, str], dict[str, str]]:
    """
    Resolve the DRF parser classes and namespaces a module file binds.

    Returns the names bound to ``rest_framework.parsers`` classes and the
    namespace aliases bound to ``rest_framework`` or ``rest_framework.parsers``,
    so the direct import, the ``parsers`` module alias, and the fully qualified
    spelling all resolve.
    """
    imported: dict[str, str] = {}
    namespaces: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                binding = alias.asname or alias.name
                if node.module == "rest_framework.parsers":
                    imported[binding] = f"rest_framework.parsers.{alias.name}"
                elif node.module == "rest_framework" and alias.name == "parsers":
                    namespaces[binding] = "rest_framework.parsers"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "rest_framework":
                    namespaces[alias.asname or "rest_framework"] = "rest_framework"
                elif alias.name == "rest_framework.parsers":
                    if alias.asname:
                        namespaces[alias.asname] = "rest_framework.parsers"
                    else:
                        namespaces.setdefault("rest_framework", "rest_framework")
    return imported, namespaces


def _resolve_parser_class(
    node: ast.expr, imported: dict[str, str], namespaces: dict[str, str]
) -> str | None:
    """Resolve one parser-class expression to its dotted DRF parser name."""
    if isinstance(node, ast.Name):
        return imported.get(node.id)
    dotted = _dotted_name(node)
    if dotted is None:
        return None
    root, _, rest = dotted.partition(".")
    if not rest:
        return imported.get(dotted)
    resolved = f"{namespaces.get(root, root)}.{rest}"
    return resolved if resolved.startswith("rest_framework.parsers.") else None


def _is_multipart_upload_parser_list(
    value: ast.expr, imported: dict[str, str], namespaces: dict[str, str]
) -> bool:
    """
    Return whether a ``parser_classes`` value is a file upload's multipart policy.

    Closed world: the value is a literal list or tuple of DRF multipart parser
    classes and names at least one parser that reads an uploaded file, so a
    form-encoded-only pin (``[FormParser]``) and a mixed pin are not exempt.
    """
    if not isinstance(value, (ast.List, ast.Tuple)) or not value.elts:
        return False
    resolved = [_resolve_parser_class(element, imported, namespaces) for element in value.elts]
    if any(item is None for item in resolved):
        return False
    return all(item in MULTIPART_PARSER_CLASSES for item in resolved) and any(
        item in UPLOAD_MULTIPART_PARSERS for item in resolved
    )


def _content_policy_pin_violations(
    label: str, tree: ast.Module, webhook_view_names: frozenset[str]
) -> list[str]:
    """
    Return rule 9's per-view renderer/parser pin violations for one source.

    ``label`` names the source in the finding (``"demo: views.py"`` or the
    rendered managed views).  Closed world: no view pins ``renderer_classes``
    or ``parser_classes`` — as a class attribute or as an ``as_view()``
    keyword override, which DRF applies to the instance — except a webhook
    view (its raw body is the input) and a file upload's multipart parser
    policy.
    """
    imported, namespaces = _parser_class_bindings(tree)
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name in webhook_view_names:
            continue
        for statement in node.body:
            if isinstance(statement, ast.Assign):
                targets = statement.targets
                value = statement.value
            elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
                targets = [statement.target]
                value = statement.value
            else:
                continue
            names = {target.id for target in targets if isinstance(target, ast.Name)}
            for attribute in CONTENT_POLICY_ATTRIBUTES:
                if attribute not in names:
                    continue
                if attribute == "parser_classes" and _is_multipart_upload_parser_list(
                    value, imported, namespaces
                ):
                    continue
                violations.append(
                    f"rule 9: {label} pins {attribute} on {node.name}; the composed "
                    "REST_FRAMEWORK defaults carry the JSON content contract"
                )
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "as_view":
            continue
        view_name, _target_error = _as_view_target(node)
        if view_name in webhook_view_names:
            continue
        for keyword in node.keywords:
            if keyword.arg not in CONTENT_POLICY_ATTRIBUTES:
                continue
            if keyword.arg == "parser_classes" and _is_multipart_upload_parser_list(
                keyword.value, imported, namespaces
            ):
                continue
            violations.append(
                f"rule 9: {label} pins {keyword.arg} in an as_view() override on "
                f"{view_name or 'an unresolved view'}; the composed REST_FRAMEWORK "
                "defaults carry the JSON content contract"
            )
    return violations


def _composed_json_default_violations() -> list[str]:
    """
    Return rule 9 violations when the composed REST_FRAMEWORK is not JSON-only.

    The generated ``settings/base.py`` delegates its ``REST_FRAMEWORK`` to
    ``quickscale_core.runtime.settings.compose_rest_framework``; the composed
    defaults install DRF's JSON renderer and parser.  The helper is imported at
    call time so a control can substitute it.
    """
    from quickscale_core.runtime.settings import compose_rest_framework  # noqa: PLC0415

    composed = compose_rest_framework(use_x_forwarded_for=False, trusted_proxy_count=0)
    violations: list[str] = []
    if composed.get("DEFAULT_RENDERER_CLASSES") != [JSON_RENDERER_CLASS]:
        violations.append(
            "rule 9: the composed REST_FRAMEWORK does not install the JSON renderer default"
        )
    if composed.get("DEFAULT_PARSER_CLASSES") != [JSON_PARSER_CLASS]:
        violations.append(
            "rule 9: the composed REST_FRAMEWORK does not install the JSON parser default"
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
    violations.extend(
        _content_policy_pin_violations("managed social views (rendered)", tree, frozenset())
    )
    return violations
