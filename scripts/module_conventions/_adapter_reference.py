"""
Bounded callable-reference resolution for the adapter call graph.

The pre-split ``AdapterFlow.reference`` resolver lived in ``adapter_flow``; this
private sibling keeps the mechanics while the facade keeps the ``reference``
method with an unchanged signature and delegates to ``_reference``.
"""

from __future__ import annotations

import ast
from typing import Any

from scripts.module_conventions._adapter_lexical import (
    CallableEnvironment,
    _aliases,
)
from scripts.module_conventions.core import _scope_nodes


def _reference(
    flow: Any,
    node: ast.AST,
    aliases: dict[str, ast.expr],
    seen: frozenset[int] = frozenset(),
    enclosing: tuple[dict[str, ast.expr], ...] = (),
    scope: int | None = None,
    environment: CallableEnvironment | None = None,
) -> str:
    """
    Resolve the same bounded callable references at every call-graph seam.

    Each alias hop resumes in its binding frame, not the original caller.
    Every frame's parameters/imports/definitions are lookup barriers. The
    result is a semantic key: definition identity plus captured static actual
    references, or an imported/builtin identity. ``enclosing`` is retained
    for caller compatibility; authoritative frames come from ``scope``.
    Unknown bindings and AST alias/factory cycles invent no target.
    """
    environment = environment or {}
    if isinstance(node, ast.Name):
        return _name_reference(flow, node, aliases, seen, scope, environment)
    if isinstance(node, ast.Call):
        return _call_reference(flow, node, aliases, seen, enclosing, scope, environment)
    return ""


def _name_reference(
    flow: Any,
    node: ast.Name,
    aliases: dict[str, ast.expr],
    seen: frozenset[int],
    scope: int | None,
    environment: CallableEnvironment,
) -> str:
    """Resolve one ``ast.Name`` hop through alias tables and binding frames."""
    if id(node) in seen:
        return ""
    seen = seen | {id(node)}
    current = scope
    while True:
        table = aliases if current == scope else flow.tables.get(current, {})
        replacement = table.get(node.id)
        if replacement is None and current is None:
            replacement = flow.aliases.get(node.id)
        if replacement is not None:
            return flow.reference(replacement, table, seen, scope=current, environment=environment)
        if current is not None and node.id in environment.get(current, {}):
            return environment[current][node.id]
        defined = flow.definitions.get(current, {}).get(node.id)
        if defined is not None:
            return flow._closure(flow.function_keys[id(defined)], environment)
        imported = flow.imports.get(current, {}).get(node.id)
        if imported is not None:
            return imported
        if node.id in flow._scope_bindings(current):
            return ""
        if current is None:
            return node.id
        current = flow.scope_parents.get(current)


def _call_reference(
    flow: Any,
    node: ast.Call,
    aliases: dict[str, ast.expr],
    seen: frozenset[int],
    enclosing: tuple[dict[str, ast.expr], ...],
    scope: int | None,
    environment: CallableEnvironment,
) -> str:
    """Resolve one call through a single-return factory to its returned hook."""
    called = flow.reference(node.func, aliases, seen, enclosing, scope, environment)
    factory = flow.functions.get(called)
    if factory is not None and id(factory) not in seen:
        nodes = _scope_nodes(factory)
        returns = [n for n in nodes if isinstance(n, ast.Return)]
        if len(returns) == 1 and returns[0].value is not None:
            captured = flow._call_environment(node, called, aliases, scope, environment, seen)
            return flow.reference(
                returns[0].value,
                _aliases(nodes),
                seen | {id(factory)},
                flow.enclosing_scopes(factory),
                id(factory),
                captured,
            )
    return ""
