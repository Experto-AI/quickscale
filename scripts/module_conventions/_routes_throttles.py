"""
Rule 32's throttle registration, scope, and rate mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_routes`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast
import re

from scripts.module_conventions.core import (
    Corpus,
    Module,
    _call_func_name,
    _docstring_nodes,
    _keyword,
    _literal,
    _parse,
    _uses_name,
)

RATE_LITERAL = re.compile(r"\d+/(?:second|minute|hour|day)")


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


def _parent_map(tree: ast.Module) -> dict[ast.AST, ast.AST]:
    """Map every node to its parent (rule 32's enclosing-class resolution)."""
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _enclosing_class_name(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str | None:
    """Return the class an assignment sits in, or None at module level."""
    owner = parents.get(node)
    while owner is not None and not isinstance(owner, (ast.ClassDef, ast.Module)):
        owner = parents.get(owner)
    return owner.name if isinstance(owner, ast.ClassDef) else None


def _class_throttle_registrations(
    module_name: str,
    rel: str,
    tree: ast.Module,
    webhook_views: set[str],
    parents: dict[ast.AST, ast.AST],
) -> list[str]:
    """Return rule 32's violations for ``throttle_classes`` assignments."""
    violations: list[str] = []
    for node in ast.walk(tree):
        targets: list[ast.expr]
        value: ast.expr | None
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
        class_name = _enclosing_class_name(node, parents)
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
    return violations


def _as_view_throttle_registrations(
    module_name: str,
    rel: str,
    tree: ast.Module,
    webhook_views: set[str],
) -> list[str]:
    """Return rule 32's violations for ``as_view(throttle_classes=...)`` mounts."""
    violations: list[str] = []
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
    parents = _parent_map(tree)
    violations = _class_throttle_registrations(module_name, rel, tree, webhook_views, parents)
    violations.extend(_as_view_throttle_registrations(module_name, rel, tree, webhook_views))
    return violations


def _throttle_class_violations(
    module_name: str,
    rel: str,
    tree: ast.Module,
    stem: str,
) -> list[str]:
    """Return rule 32's Throttle-class rate/scope and ``throttle_scope`` violations."""
    violations: list[str] = []
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
                        violations.append(f"rule 32: {module_name}: {node.name} hard-codes a rate")
                    if target.id == "scope" and isinstance(value, str):
                        if not value.startswith(f"{stem}_"):
                            violations.append(
                                f"rule 32: {module_name}: {node.name} scope {value!r} "
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
                        f"rule 32: {module_name}: {rel} throttle scope "
                        f"{node.value.value!r} lacks the {stem}_ stem"
                    )
    return violations


def _rate_literal_violations(module_name: str, rel: str, tree: ast.Module) -> list[str]:
    """Return rule 32's throttle-rate literal violation for one file, if any."""
    violations: list[str] = []
    docstrings = _docstring_nodes(tree)
    for constant in ast.walk(tree):
        if not isinstance(constant, ast.Constant) or not isinstance(constant.value, str):
            continue
        if id(constant) in docstrings:
            continue
        match = RATE_LITERAL.search(constant.value)
        if match:
            violations.append(
                f"rule 32: {module_name}: {rel} writes a throttle rate literal {match.group()!r}"
            )
            break
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
            violations.extend(_throttle_class_violations(module.name, rel, tree, stem))
            violations.extend(_rate_literal_violations(module.name, rel, tree))
            if _uses_name(tree, "RunSQL"):
                violations.append(f"rule 32: {module.name}: {rel} creates raw SQL objects")
    return violations
