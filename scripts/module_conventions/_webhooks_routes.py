"""
Rule 26's webhook route discovery in module ``urls.py`` files.

Implementation detail of :mod:`scripts.module_conventions.rules_webhooks`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast

from scripts.module_conventions.core import _call_func_name, _keyword, _literal, _parse


def _is_webhook_route(route: object, name: object) -> bool:
    """Return True when a path() call's route or name marks it a webhook."""
    return (isinstance(route, str) and "webhooks/" in route) or (
        isinstance(name, str) and "webhook" in name
    )


def _as_view_target(view: ast.expr) -> tuple[str | None, str | None]:
    """
    Return ``(view_name, error)`` for a route's second ``path()`` argument.

    A resolvable ``as_view()`` mount yields its class name; an ``as_view()``
    call on any other expression, or a callable that is not an ``as_view()``
    mount, yields the matching rule 26 error text.
    """
    if not (
        isinstance(view, ast.Call)
        and isinstance(view.func, ast.Attribute)
        and view.func.attr == "as_view"
    ):
        return None, "does not mount an APIView.as_view() callable"
    target = view.func.value
    if isinstance(target, ast.Name):
        return target.id, None
    if isinstance(target, ast.Attribute):
        return target.attr, None
    return None, "does not resolve to an APIView class"


def _route_entries(module_name: str, urls: str) -> tuple[list[str], list[str]]:
    """Return the webhook view names and route-shape violations of one urls.py."""
    view_names: list[str] = []
    violations: list[str] = []
    for node in ast.walk(_parse(urls)):
        if not isinstance(node, ast.Call) or _call_func_name(node) != "path":
            continue
        route = _literal(node.args[0]) if node.args else None
        name = _literal(_keyword(node, "name"))
        if not _is_webhook_route(route, name):
            continue
        label = route or name
        if len(node.args) < 2:
            violations.append(f"rule 26: {module_name}: webhook route {label!r} has no view")
            continue
        view_name, error = _as_view_target(node.args[1])
        if error is not None:
            violations.append(f"rule 26: {module_name}: webhook route {label!r} {error}")
        elif view_name is not None:
            view_names.append(view_name)
    return view_names, violations
