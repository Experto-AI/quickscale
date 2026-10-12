"""
Rule 46's view discovery and Django/DRF class-resolution mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_routes`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast

from scripts.module_conventions.core import Module, _parse

# Rule 46's discovery roots: a class that subclasses a Django or DRF view
# (directly or through a class the same file defines) is view code, wherever a
# rule 28 split files it under a private name.
VIEW_MODULE_PREFIXES = (
    "django.contrib.auth.views",
    "django.views",
    "rest_framework.views",
    "rest_framework.generics",
    "rest_framework.viewsets",
)

#: Rule 19's view frameworks: DRF permissions are enforced only on DRF views,
#: so a ``permission_classes`` attribute on a plain Django page declares nothing.
DRF_VIEW_MODULE_PREFIXES: tuple[str, ...] = (
    "rest_framework.views",
    "rest_framework.generics",
    "rest_framework.viewsets",
)
DJANGO_VIEW_MODULE_PREFIXES: tuple[str, ...] = (
    "django.views",
    "django.contrib.auth.views",
)


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


def _base_name(node: ast.expr) -> str | None:
    """Return the class name a base expression names, directly or qualified."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _base_view_target(
    node: ast.expr,
    names: set[str],
    namespaces: dict[str, str],
) -> str | None:
    """Resolve a base expression to its dotted view target, when it is one."""
    if isinstance(node, ast.Name):
        return namespaces.get(node.id) if node.id in names else None
    dotted = _dotted_name(node)
    if dotted is None:
        return None
    root, _, rest = dotted.partition(".")
    if not rest:
        return namespaces.get(dotted) if dotted in names else None
    return f"{namespaces.get(root, root)}.{rest}"


def _view_framework(
    name: str,
    classes: dict[str, tuple[ast.ClassDef, str]],
    bindings: dict[str, tuple[set[str], dict[str, str]]],
    seen: set[str],
) -> str | None:
    """Return whether a view class's ancestry is ``"drf"`` or ``"django"``."""
    entry = classes.get(name)
    if entry is None:
        return None
    node, rel = entry
    names, namespaces = bindings[rel]
    for base in node.bases:
        target = _base_view_target(base, names, namespaces)
        if target is not None:
            if target.startswith(DRF_VIEW_MODULE_PREFIXES):
                return "drf"
            if target.startswith(DJANGO_VIEW_MODULE_PREFIXES):
                return "django"
        base_id = _base_name(base)
        if base_id is not None and base_id in classes and base_id not in seen:
            seen.add(base_id)
            found = _view_framework(base_id, classes, bindings, seen)
            if found is not None:
                return found
    return None


def _view_class_index(
    module: Module,
) -> tuple[
    dict[str, tuple[ast.ClassDef, str]],
    set[str],
    dict[str, tuple[set[str], dict[str, str]]],
    dict[str, dict[str, str]],
]:
    """
    Index a module's classes and resolve which of them are view classes.

    Returns the name-to-(class, file) map, the view class names, the per-file
    view bindings, and each file's permission import aliases (``AllowAny as
    X`` resolves to ``AllowAny`` only inside its declaring file).  A class is
    a view class when a base resolves to a Django or DRF view module or to
    another view class the same module defines, wherever a rule 28 split
    files it (rule 46's discovery).
    """
    classes: dict[str, tuple[ast.ClassDef, str]] = {}
    parsed: dict[str, ast.Module] = {}
    aliases_by_rel: dict[str, dict[str, str]] = {}
    for rel, text in module.files.items():
        if not rel.endswith(".py") or rel.startswith("migrations/"):
            continue
        tree = _parse(text)
        parsed[rel] = tree
        file_aliases: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.setdefault(node.name, (node, rel))
            if isinstance(node, ast.ImportFrom) and node.module == "rest_framework.permissions":
                for alias in node.names:
                    if alias.asname:
                        file_aliases[alias.asname] = alias.name
        if file_aliases:
            aliases_by_rel[rel] = file_aliases
    bindings = {rel: _view_bindings(tree) for rel, tree in parsed.items()}
    view_names: set[str] = set()
    changed = True
    while changed:
        changed = False
        for name, (node, rel) in classes.items():
            if name in view_names:
                continue
            names, namespaces = bindings[rel]
            for base in node.bases:
                base_id = _base_name(base)
                if _is_view_base(base, names, namespaces) or (
                    base_id is not None and base_id in classes and base_id in view_names
                ):
                    view_names.add(name)
                    changed = True
                    break
    return classes, view_names, bindings, aliases_by_rel
