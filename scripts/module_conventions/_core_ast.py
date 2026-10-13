"""
Shared AST helpers for the module-convention detectors.

Implementation detail of :mod:`scripts.module_conventions.core`; that module
re-exports every name defined here, so existing import paths (``registry``,
``check_module_conventions``, the rule modules, and the control cases) keep
working.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from typing import Any

from scripts.module_conventions._core_corpus import Module

# Rule 40's "one test-owned mapping" keeps its module-name tables in the
# rule-37-exempt :mod:`scripts.module_conventions.core` facade.  The two
# entries below are the vocabulary these AST helpers need: the model base
# names class resolution starts from and the first-party import prefix.
MODULE_ABSTRACT_BASES = ("TenantModel", "AbstractListing", "BaseSocialItem")

MODULE_IMPORT_PREFIX = "quickscale_modules_"


# ---------------------------------------------------------------------------
# Shared parsing helpers
# ---------------------------------------------------------------------------


def _parse(source: str) -> ast.Module:
    return ast.parse(source)


def _docstring_nodes(tree: ast.Module) -> set[int]:
    """Return the ids of string constants that are docstrings."""
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", [])
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            docstrings.add(id(body[0].value))
    return docstrings


def _string_assignments(tree: ast.Module) -> dict[str, str]:
    """Collect ``NAME = "literal"`` assignments, annotated ones included."""
    values: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        values[target.id] = node.value.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str) and isinstance(node.target, ast.Name):
                values[node.target.id] = node.value.value
    return values


def _class_names(node: ast.ClassDef) -> list[str]:
    names: list[str] = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            names.append(base.id)
        elif isinstance(base, ast.Attribute):
            names.append(base.attr)
    return names


def _string_list(tree: ast.Module) -> dict[str, list[str]]:
    """Collect ``NAME = ["literal", ...]`` assignments."""
    values: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.List):
            items = [
                item.value
                for item in node.value.elts
                if isinstance(item, ast.Constant) and isinstance(item.value, str)
            ]
            if len(items) == len(node.value.elts):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        values[target.id] = items
    return values


def _call_func_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _uses_name(tree: ast.Module, name: str) -> bool:
    """Return True when executable code calls or imports *name*."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_func_name(node) == name:
            return True
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name.split(".")[-1] == name:
                    return True
    return False


def _keyword(node: ast.Call, name: str) -> ast.expr | None:
    for keyword in node.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _literal(node: ast.expr | None) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    return None


def _model_classes(tree: ast.Module) -> list[ast.ClassDef]:
    """Resolve classes that model bases reach within one models.py module."""
    known: set[str] = {"Model", "TenantModel", *MODULE_ABSTRACT_BASES}
    models: list[ast.ClassDef] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = _class_names(node)
        if any(base in known for base in bases):
            models.append(node)
            known.add(node.name)
    return models


def _meta_class(node: ast.ClassDef) -> ast.ClassDef | None:
    for stmt in node.body:
        if isinstance(stmt, ast.ClassDef) and stmt.name == "Meta":
            return stmt
    return None


def _module_target(parts: tuple[str, ...]) -> tuple[str, tuple[str, ...]] | None:
    """Resolve a dotted import path to (module name, path after the package)."""
    for index, part in enumerate(parts):
        if part.startswith(MODULE_IMPORT_PREFIX) and len(part) > len(MODULE_IMPORT_PREFIX):
            return part[len(MODULE_IMPORT_PREFIX) :], parts[index + 1 :]
        if part == "quickscale_modules" and index + 1 < len(parts) and parts[index + 1]:
            return parts[index + 1], parts[index + 2 :]
    return None


def _cross_module_imports(
    tree: ast.Module,
) -> list[tuple[str, tuple[str, ...], tuple[str, ...], int, str]]:
    """Collect every import of a first-party module, nested scopes included."""
    found: list[tuple[str, tuple[str, ...], tuple[str, ...], int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            target = _module_target(tuple(node.module.split(".")))
            if target is not None:
                found.append(
                    (
                        target[0],
                        target[1],
                        tuple(alias.name for alias in node.names),
                        node.lineno,
                        "from",
                    )
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                target = _module_target(tuple(alias.name.split(".")))
                if target is not None:
                    found.append(
                        (target[0], target[1], (alias.name.split(".")[-1],), node.lineno, "import")
                    )
    return found


def _settings_bindings(tree: ast.Module) -> tuple[set[str], set[tuple[str, ...]]]:
    """Return settings bindings and module paths ending at ``django.conf``."""
    names = {"settings"}
    modules: set[tuple[str, ...]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "django.conf":
            for alias in node.names:
                if alias.name == "settings":
                    names.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "django":
            for alias in node.names:
                if alias.name == "conf":
                    modules.add((alias.asname or alias.name,))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "django.conf":
                    modules.add((alias.asname,) if alias.asname else ("django", "conf"))
    return names, modules


def _is_settings_receiver(node: ast.expr, names: set[str], modules: set[tuple[str, ...]]) -> bool:
    """Resolve ``settings``, an import alias, or a qualified Django conf path."""
    if isinstance(node, ast.Name):
        return node.id in names or node.id.endswith("settings")
    if isinstance(node, ast.Attribute) and node.attr == "settings":
        chain = _attribute_chain(node.value)
        return chain is not None and chain in modules
    return False


def _settings_attribute_reads(tree: ast.Module) -> list[tuple[str, int]]:
    """Collect ``settings.QUICKSCALE_*`` attribute reads from executable code."""
    found: list[tuple[str, int]] = []
    names, modules = _settings_bindings(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or not node.attr.startswith("QUICKSCALE_"):
            continue
        if _is_settings_receiver(node.value, names, modules):
            found.append((node.attr, node.lineno))
    return found


def _declared_exports(tree: ast.Module) -> list[str] | None:
    """Return ``__all__``'s literal names, annotated declarations included."""
    for node in tree.body:
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        if not any(isinstance(target, ast.Name) and target.id == "__all__" for target in targets):
            continue
        if not isinstance(value, ast.List):
            return None
        names = [
            element.value
            for element in value.elts
            if isinstance(element, ast.Constant) and isinstance(element.value, str)
        ]
        if len(names) != len(value.elts):
            return None
        return names
    return None


def _service_module_bindings(tree: ast.Module) -> dict[tuple[str, ...], str]:
    """Map dotted local names bound to another module's services to that module."""
    bindings: dict[tuple[str, ...], str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            target = _module_target(tuple(node.module.split(".")))
            if target is None or target[1]:
                continue
            for alias in node.names:
                if alias.name == "services":
                    bindings[(alias.asname or alias.name,)] = target[0]
        elif isinstance(node, ast.Import):
            for alias in node.names:
                target = _module_target(tuple(alias.name.split(".")))
                if target is None or target[1] != ("services",):
                    continue
                if alias.asname:
                    bindings[(alias.asname,)] = target[0]
                else:
                    bindings[tuple(alias.name.split("."))] = target[0]
    return bindings


def _attribute_chain(node: ast.expr) -> tuple[str, ...] | None:
    """Flatten ``a.b.c`` into ("a", "b", "c")."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return tuple(reversed(parts))
    return None


def _same_layer_cycles(edges: Mapping[str, set[str]]) -> list[list[str]]:
    """Return one representative cycle per cyclic same-layer component."""
    cycles: list[list[str]] = []
    reported: set[frozenset[str]] = set()
    state: dict[str, int] = {}
    path: list[str] = []

    def visit(node: str) -> None:
        state[node] = 1
        path.append(node)
        for neighbour in sorted(edges.get(node, ())):
            if state.get(neighbour, 0) == 1:
                cycle = path[path.index(neighbour) :] + [neighbour]
                key = frozenset(cycle)
                if key not in reported:
                    reported.add(key)
                    cycles.append(cycle)
            elif state.get(neighbour, 0) == 0:
                visit(neighbour)
        path.pop()
        state[node] = 2

    for node in sorted(edges):
        if state.get(node, 0) == 0:
            visit(node)
    return cycles


def _bound_names(target: ast.expr) -> set[str]:
    """Return the names an assignment target binds, destructuring included."""
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        names: set[str] = set()
        for element in target.elts:
            names |= _bound_names(element)
        return names
    if isinstance(target, ast.Starred):
        return _bound_names(target.value)
    return set()


def _wiring_projection(manifest: Mapping[str, Any], field: str) -> list[Any]:
    derivation = manifest.get("derivation")
    if not isinstance(derivation, Mapping):
        return []
    projections = derivation.get("wiring_projections")
    if not isinstance(projections, list):
        return []
    entries: list[Any] = []
    for projection in projections:
        if isinstance(projection, Mapping) and projection.get("wiring_field") == field:
            entries.extend(_projection_values(projection.get("expression")))
    return entries


def _projection_values(expression: Any) -> list[Any]:
    """Flatten a static value or every conditional branch's value."""
    if not isinstance(expression, Mapping):
        return []
    entries: list[Any] = []
    value = expression.get("value")
    if isinstance(value, list):
        entries.extend(value)
    branches = expression.get("branches")
    if isinstance(branches, Mapping):
        for branch in branches.values():
            if isinstance(branch, list):
                entries.extend(branch)
    return entries


def _static_truth(node: ast.expr) -> bool | None:
    """Return the statically known truth of an expression, or None when unknown."""
    if isinstance(node, ast.Constant):
        return bool(node.value)
    if isinstance(node, ast.IfExp):
        test = _static_truth(node.test)
        if test is True:
            return _static_truth(node.body)
        if test is False:
            return _static_truth(node.orelse)
        return None
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.Or):
            result: bool | None = False
            for operand in node.values:
                truth = _static_truth(operand)
                if truth is True:
                    return True
                if truth is None:
                    result = None
            return result
        result = True
        for operand in node.values:
            truth = _static_truth(operand)
            if truth is False:
                return False
            if truth is None:
                result = None
        return result
    return None


def _import_package_parts(node: ast.ImportFrom, module_name: str) -> tuple[str, ...] | None:
    """
    Map an own-package ``ImportFrom`` target to its package path (SA239).

    Both the level-1 relative form (``from ._uploads import …``) and the
    absolute form (``from quickscale_modules_<module>._uploads import …``)
    resolve to the same package path; a deeper relative level leaves the
    package and is ignored.
    """
    package = f"quickscale_modules_{module_name}"
    base = (package,)
    if node.module:
        if node.level:
            if node.level != 1:
                return None
            return base + tuple(node.module.split("."))
        parts = tuple(node.module.split("."))
        if parts[:1] != base:
            return None
        return parts
    if node.level != 1:
        return None
    return base


def _ancestors(node: ast.ClassDef, classes: Mapping[str, ast.ClassDef]) -> list[ast.ClassDef]:
    """Return every base class defined in the same module, transitively."""
    found: list[ast.ClassDef] = []
    seen: set[str] = set()
    pending = list(_class_names(node))
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        ancestor = classes.get(name)
        if ancestor is None:
            continue
        found.append(ancestor)
        pending.extend(_class_names(ancestor))
    return found


def _declared_mounts(module: Module) -> list[str]:
    """Rule 31: the URL mounts the module's manifest declares (rule 7)."""
    mounts: list[str] = []
    for entry in _wiring_projection(module.manifest, "url_includes"):
        if (
            isinstance(entry, (list, tuple))
            and entry
            and isinstance(entry[0], str)
            and entry[0] not in mounts
        ):
            mounts.append(entry[0])
    return mounts


def _declared_url_mounts(module: Module) -> list[str]:
    """
    Rule 41: the mounts of both include buckets, pre-home and post-home.

    The two buckets render into one URLconf, so a prefix belongs to one
    module across both projections.
    """
    mounts: list[str] = []
    for field in ("pre_home_url_includes", "url_includes"):
        for entry in _wiring_projection(module.manifest, field):
            if (
                isinstance(entry, (list, tuple))
                and entry
                and isinstance(entry[0], str)
                and entry[0] not in mounts
            ):
                mounts.append(entry[0])
    return mounts


def _body_nodes(body: list[ast.stmt]) -> list[ast.AST]:
    """Return nodes in *body* without descending into nested functions."""
    found: list[ast.AST] = []
    stack: list[ast.AST] = list(body)
    while stack:
        current = stack.pop()
        found.append(current)
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        stack.extend(ast.iter_child_nodes(current))
    return found


def _scope_nodes(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.AST]:
    """Return *node*'s own body without descending into nested functions."""
    return _body_nodes(node.body)
