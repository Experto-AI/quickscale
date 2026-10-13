"""
Readiness-query selection pass for the adapter call graph.

The pre-split ``AdapterFlow`` query pass (``_query_functions`` and its purity,
selection, and value walkers) lived in ``adapter_flow``; this private sibling
keeps the mechanics while the facade keeps every method with an unchanged
signature and delegates here.
"""

from __future__ import annotations

import ast
from typing import Any

from scripts.module_conventions._adapter_lexical import Function, _aliases, _arguments
from scripts.module_conventions.core import _scope_nodes


def _query_functions(flow: Any) -> set[str]:
    """Select the readiness queries and publish the flow's query roots."""
    constants = {name for name, value in flow.aliases.items() if isinstance(value, ast.Constant)}
    candidates = _query_candidates(flow, constants)
    flow.query_roots = _query_roots(flow, candidates)
    return _query_selections(flow, candidates)


def _query_candidates(flow: Any, constants: set[str]) -> set[str]:
    """Collect callables whose returns are proven pure selections, to fixpoint."""
    candidates: set[str] = set()
    # Return selection is proven from expressions, never annotations.
    for _ in range(len(flow.functions) + 1):
        for name, function in list(flow.functions.items()):
            nodes = _scope_nodes(function)
            returns = [node.value for node in nodes if isinstance(node, ast.Return)]
            if returns and all(
                _selection(flow, value, constants, candidates, function) for value in returns
            ):
                if _pure(nodes):
                    candidates.add(name)
    return candidates


def _query_roots(flow: Any, candidates: set[str]) -> set[str]:
    """Keep the candidates that consume the normalization API's output."""
    return {
        name
        for name, function in list(flow.functions.items())
        if name in candidates
        and any(
            isinstance(node, ast.Call)
            and flow.reference(
                node.func,
                _aliases(_scope_nodes(function)),
                enclosing=flow.enclosing_scopes(function),
                scope=id(function),
            )
            in flow.normalizers
            for node in _scope_nodes(function)
        )
    }


def _query_selections(flow: Any, candidates: set[str]) -> set[str]:
    """Walk every reachable selection context to a fixed point."""
    queries: set[str] = set()
    contexts: set[tuple[str, tuple[bool, ...]]] = {
        (name, tuple(False for _ in _arguments(flow.functions[name]))) for name in flow.query_roots
    }
    seen: set[tuple[str, tuple[bool, ...]]] = set()
    while contexts - seen:
        for context in list(contexts - seen):
            seen.add(context)
            name, inputs = context
            function = flow.functions[name]
            bindings = dict(zip(_arguments(function), inputs))
            aliases = _aliases(_scope_nodes(function))
            enclosing = flow.enclosing_scopes(function)
            if _query_body(
                flow,
                function.body,
                bindings,
                aliases,
                candidates,
                contexts,
                enclosing,
                id(function),
            ):
                queries.add(name)
            if any(inputs) and name not in flow.query_roots:
                queries.add(name)
    return queries


def _query_value(
    flow: Any,
    node: ast.AST,
    bindings: dict[str, bool],
    aliases: dict[str, ast.expr],
    candidates: set[str],
    contexts: set[tuple[str, tuple[bool, ...]]],
    enclosing: tuple[dict[str, ast.expr], ...],
    scope: int | None,
) -> bool:
    """Follow *outputs* of normalization; an unused API call grants nothing."""
    if isinstance(node, ast.Name):
        return bindings.get(node.id, False)
    if isinstance(node, ast.Call):
        called = flow.reference(node.func, aliases, enclosing=enclosing, scope=scope)
        if called in flow.normalizers:
            return True
        values = [
            _query_value(flow, arg, bindings, aliases, candidates, contexts, enclosing, scope)
            for arg in node.args
        ]
        if called in candidates:
            arguments = _arguments(flow.functions[called])
            values += [False] * max(0, len(arguments) - len(values))
            for keyword in node.keywords:
                if keyword.arg in arguments:
                    values[arguments.index(keyword.arg)] = _query_value(
                        flow,
                        keyword.value,
                        bindings,
                        aliases,
                        candidates,
                        contexts,
                        enclosing,
                        scope,
                    )
            if any(values):
                contexts.add((called, tuple(values[: len(arguments)])))
        return any(values) or _query_value(
            flow, node.func, bindings, aliases, candidates, contexts, enclosing, scope
        )
    return any(
        [
            _query_value(flow, child, bindings, aliases, candidates, contexts, enclosing, scope)
            for child in ast.iter_child_nodes(node)
        ]
    )


def _query_body(
    flow: Any,
    body: list[ast.stmt],
    bindings: dict[str, bool],
    aliases: dict[str, ast.expr],
    candidates: set[str],
    contexts: set[tuple[str, tuple[bool, ...]]],
    enclosing: tuple[dict[str, ast.expr], ...],
    scope: int | None,
) -> bool:
    """Walk one statement body, joining branch bindings union-style."""
    returned = False
    for statement in body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            if statement.value is not None:
                value = _query_value(
                    flow, statement.value, bindings, aliases, candidates, contexts, enclosing, scope
                )
                targets = (
                    statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                )
                for target in targets:
                    if isinstance(target, ast.Name):
                        bindings[target.id] = value
        elif isinstance(statement, ast.If):
            _query_value(
                flow, statement.test, bindings, aliases, candidates, contexts, enclosing, scope
            )
            left, right = dict(bindings), dict(bindings)
            returned |= _query_body(
                flow, statement.body, left, aliases, candidates, contexts, enclosing, scope
            )
            returned |= _query_body(
                flow, statement.orelse, right, aliases, candidates, contexts, enclosing, scope
            )
            bindings.update(
                {
                    key: left.get(key, False) or right.get(key, False)
                    for key in left.keys() | right.keys()
                }
            )
        elif isinstance(statement, ast.Return) and statement.value is not None:
            returned |= _query_value(
                flow, statement.value, bindings, aliases, candidates, contexts, enclosing, scope
            )
        else:
            _query_value(flow, statement, bindings, aliases, candidates, contexts, enclosing, scope)
    return returned


def _pure(nodes: list[ast.AST]) -> bool:
    """Reject returns whose expressions rebind state or read settings."""
    for node in nodes:
        if isinstance(node, (ast.Raise, ast.Assert, ast.AugAssign, ast.Delete)):
            return False
        if isinstance(node, ast.Attribute) and node.attr == "settings":
            return False
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in {"update", "pop", "popitem", "setdefault", "clear"}:
                return False
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(not isinstance(target, ast.Name) for target in targets):
                return False
        if isinstance(node, ast.Expr) and not isinstance(node.value, ast.Constant):
            return False
    return True


def _selection(
    flow: Any,
    node: ast.AST | None,
    constants: set[str],
    queries: set[str],
    function: Function,
) -> bool:
    """Return whether one expression is a proven selection."""
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (bool, str)) or node.value is None
    if isinstance(node, ast.Name):
        return node.id in constants
    if isinstance(node, ast.Compare):
        return True
    if isinstance(node, ast.UnaryOp):
        return isinstance(node.op, ast.Not)
    if isinstance(node, ast.BoolOp):
        return all(_selection(flow, value, constants, queries, function) for value in node.values)
    if isinstance(node, ast.Call):
        called = flow.reference(node.func, flow.tables[id(function)], scope=id(function))
        return called == "bool" or flow.definition_key(called) in queries
    return False
