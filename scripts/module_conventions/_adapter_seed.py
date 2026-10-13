"""
Boundary and hook seeding for the adapter call graph.

The pre-split ``AdapterFlow._seed`` pass (with ``_sources`` and
``_seed_defaults``) lived in ``adapter_flow``; this private sibling keeps the
mechanics while the facade keeps every method with an unchanged signature and
delegates here.
"""

from __future__ import annotations

import ast
from typing import Any

from scripts.module_conventions._adapter_lexical import (
    Function,
    _aliases,
    _arguments,
    _defaults,
)
from scripts.module_conventions.core import _scope_nodes


def _seed(flow: Any) -> None:
    """Seed every callable in the flow from its boundary call sites."""
    for name, function in list(flow.functions.items()):
        _seed_function(flow, name, function)


def _seed_function(flow: Any, name: str, function: Function) -> None:
    """Seed one callable's boundary arguments, hook contexts, and adapter entry."""
    nodes = _scope_nodes(function)
    aliases = _aliases(nodes)
    enclosing = flow.enclosing_scopes(function)
    bindings: dict[str, str] = {}
    for node in nodes:
        if not isinstance(node, ast.Call):
            continue
        called = flow.reference(node.func, aliases, enclosing=enclosing, scope=id(function))
        if called in flow.boundaries | flow.normalizers:
            argument = _boundary_argument(node)
            if argument is not None:
                for parameter in _sources(argument, aliases, set(_arguments(function))):
                    bindings[parameter] = "options"
        if called in flow.boundaries:
            _seed_hook(flow, node, aliases, enclosing, function)
    if bindings or name in flow.queries:
        flow.contexts.add((name, tuple(bindings.get(arg, "") for arg in _arguments(function))))
    if function.name == "get_manifest_adapter" and flow.scope_parents[id(function)] is None:
        _seed_manifest_adapter(flow, nodes, aliases, enclosing, function)


def _boundary_argument(node: ast.Call) -> ast.expr | None:
    """Return the ``options`` keyword, else the second positional argument."""
    argument = next((keyword.value for keyword in node.keywords if keyword.arg == "options"), None)
    if argument is None and len(node.args) > 1:
        argument = node.args[1]
    return argument


def _seed_hook(
    flow: Any,
    node: ast.Call,
    aliases: dict[str, ast.expr],
    enclosing: tuple[dict[str, ast.expr], ...],
    function: Function,
) -> None:
    """Seed a boundary call's ``post_hook`` factory context and defaults."""
    hook = next((keyword.value for keyword in node.keywords if keyword.arg == "post_hook"), None)
    hook_name = (
        flow.reference(hook, aliases, enclosing=enclosing, scope=id(function))
        if hook is not None
        else ""
    )
    if hook_name in flow.functions:
        flow.add_context(hook_name, ["spec", "options"])
        _seed_defaults(flow, hook_name, supplied=2)


def _seed_manifest_adapter(
    flow: Any,
    nodes: list[ast.AST],
    aliases: dict[str, ast.expr],
    enclosing: tuple[dict[str, ast.expr], ...],
    function: Function,
) -> None:
    """Seed the adapter returned by a module-level ``get_manifest_adapter``."""
    for node in nodes:
        if isinstance(node, ast.Return) and node.value is not None:
            adapter = flow.reference(node.value, aliases, enclosing=enclosing, scope=id(function))
            if adapter in flow.functions:
                flow.add_context(adapter, ["options"])


def _sources(
    node: ast.AST,
    aliases: dict[str, ast.expr],
    parameters: set[str],
    seen: frozenset[str] = frozenset(),
) -> set[str]:
    """Trace boundary inputs backwards through simple aliases/copies/expressions."""
    if isinstance(node, ast.Name):
        if node.id in parameters:
            return {node.id}
        if node.id in aliases and node.id not in seen:
            return _sources(aliases[node.id], aliases, parameters, seen | {node.id})
        return set()
    return set().union(
        *(_sources(child, aliases, parameters, seen) for child in ast.iter_child_nodes(node))
    )


def _seed_defaults(flow: Any, name: str, supplied: int) -> None:
    """
    Bind a seeded callable's omitted parameter defaults (SA263).

    The implicit post-hook seeds supply the first *supplied* parameters
    with the boundary's spec/options kinds, so later parameters are
    omitted.  Their default expressions resolve in the callable's defining
    frame through its captured environment, exactly as
    ``_call_environment`` resolves an ordinary call's omitted defaults.
    """
    function = flow.functions[name]
    captured = dict(flow.environments.get(name, {}))
    bindings = dict(captured.get(id(function), {}))
    defaults = _defaults(function)
    parent = flow.scope_parents.get(id(function))
    for argument in _arguments(function)[supplied:]:
        if argument in defaults and argument not in bindings:
            bindings[argument] = flow.reference(
                defaults[argument],
                flow.tables.get(parent, {}),
                scope=parent,
                environment=captured,
            )
    if bindings != captured.get(id(function), {}) and any(bindings.values()):
        captured[id(function)] = bindings
        flow.environments[name] = captured
