"""
Rule 26's service-call discovery and verification walk.

Implementation detail of :mod:`scripts.module_conventions.rules_webhooks`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Mapping

from scripts.module_conventions._webhooks_flows import (
    _may_return_any,
    _may_return_non_rejection,
    _overwritten_names,
    _rejects_by_raising,
)
from scripts.module_conventions._webhooks_signature import (
    _evaluated_signature_value,
    _verification_on_accepting_path,
)
from scripts.module_conventions.core import _call_func_name, _parse


def _service_call_target(
    call: ast.Call,
    bindings: Mapping[str, str],
    module_names: set[str],
) -> str | None:
    """Resolve a call to its original services.py function name, alias-aware."""
    if isinstance(call.func, ast.Name) and call.func.id in bindings:
        return bindings[call.func.id]
    if (
        isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id in module_names
    ):
        return call.func.attr
    return None


def _request_header_argument(node: ast.expr) -> bool:
    """Return True when an argument reads request headers."""
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in {"get", "getlist"}:
            return _mentions_headers(func.value)
    if isinstance(node, ast.Subscript):
        return _mentions_headers(node.value)
    return False


def _mentions_headers(node: ast.expr) -> bool:
    return any(
        (isinstance(child, ast.Attribute) and child.attr == "headers")
        or (isinstance(child, ast.Name) and child.id == "headers")
        for child in ast.walk(node)
    )


def _direct_call_node(
    node: ast.expr | None, functions: Mapping[str, ast.FunctionDef]
) -> ast.Call | None:
    if isinstance(node, ast.Call) and _call_func_name(node) in functions:
        return node
    return None


def _executed_if_step(
    statement: ast.If, is_service: Callable[[ast.Call], bool]
) -> tuple[str, list[ast.Call]]:
    """
    Return the outcome (``continue``, ``break``, or ``empty``) and calls of one If.

    A statically-decided test evaluates the selected branch and stops the walk
    when that branch can return; a dynamic test credits the calls both
    branches make, and reports ``empty`` when the walk must fail closed with no
    calls at all.
    """
    test = statement.test
    if isinstance(test, ast.Constant) and test.value is True:
        calls = _executed_service_calls(statement.body, is_service)
        return ("break" if _may_return_any(statement.body) else "continue"), calls
    if isinstance(test, ast.Constant) and test.value is False:
        calls = _executed_service_calls(statement.orelse, is_service)
        return ("break" if _may_return_any(statement.orelse) else "continue"), calls
    if _may_return_non_rejection(statement.body) or _may_return_non_rejection(statement.orelse):
        return "empty", []
    body_calls = _executed_service_calls(statement.body, is_service)
    else_calls = _executed_service_calls(statement.orelse, is_service)
    body_terminates = _may_return_any(statement.body) or _rejects_by_raising(statement.body)
    else_terminates = _may_return_any(statement.orelse) or _rejects_by_raising(statement.orelse)
    if body_terminates and else_terminates:
        return "continue", []
    if body_terminates or else_terminates:
        return "continue", body_calls if body_terminates else else_calls
    if not (body_calls and else_calls):
        return "empty", []
    return "continue", body_calls


def _executed_service_calls(
    statements: list[ast.stmt], is_service: Callable[[ast.Call], bool]
) -> list[ast.Call]:
    """Collect service calls executed on the accepting path (fail-closed)."""
    calls: list[ast.Call] = []
    for statement in statements:
        if isinstance(statement, ast.Raise):
            break
        if isinstance(statement, ast.Return):
            value = statement.value
            if isinstance(value, ast.Call) and is_service(value):
                calls.append(value)
            break
        if isinstance(statement, ast.If):
            outcome, if_calls = _executed_if_step(statement, is_service)
            if outcome == "empty":
                return []
            calls.extend(if_calls)
            if outcome == "break":
                break
            continue
        if isinstance(statement, (ast.With, ast.AsyncWith, ast.For, ast.While, ast.Try, ast.Match)):
            if _may_return_any([statement]):
                break
            continue
        if isinstance(statement, (ast.Assign, ast.AnnAssign, ast.Expr)):
            value = statement.value
            if isinstance(value, ast.Call) and is_service(value):
                calls.append(value)
    return calls


def _local_if_step(
    statement: ast.If,
    functions: Mapping[str, ast.FunctionDef],
    trusted: set[str],
) -> tuple[str, list[tuple[ast.Call, set[str]]]]:
    """Return the outcome (``continue`` or ``break``) and calls of one If."""
    test = statement.test
    if isinstance(test, ast.Constant) and test.value is True:
        calls = _executed_local_calls(statement.body, functions, trusted)
        return ("break" if _may_return_any(statement.body) else "continue"), calls
    if isinstance(test, ast.Constant) and test.value is False:
        calls = _executed_local_calls(statement.orelse, functions, trusted)
        return ("break" if _may_return_any(statement.orelse) else "continue"), calls
    if _may_return_any(statement.body) or _may_return_any(statement.orelse):
        return "break", []
    return "continue", []


def _assignment_call_and_drop(
    statement: ast.Assign | ast.AnnAssign,
    functions: Mapping[str, ast.FunctionDef],
    trusted: set[str],
) -> ast.Call | None:
    """Return the assignment's direct local call and drop overwritten trusted names."""
    call = _direct_call_node(statement.value, functions)
    if isinstance(statement, ast.Assign):
        targets = list(statement.targets)
    else:
        targets = [statement.target]
    for target in targets:
        if isinstance(target, ast.Name) and target.id in trusted:
            trusted.discard(target.id)
    return call


def _executed_local_calls(
    statements: list[ast.stmt],
    functions: Mapping[str, ast.FunctionDef],
    trusted: set[str],
) -> list[tuple[ast.Call, set[str]]]:
    """Collect local calls with the signature trust in effect at each call."""
    trusted = set(trusted) - _overwritten_names(statements)
    calls: list[tuple[ast.Call, set[str]]] = []
    for statement in statements:
        if isinstance(statement, ast.Raise):
            break
        if isinstance(statement, ast.Return):
            call = _direct_call_node(statement.value, functions)
            if call is not None:
                calls.append((call, set(trusted)))
            break
        if isinstance(statement, ast.If):
            outcome, if_calls = _local_if_step(statement, functions, trusted)
            calls.extend(if_calls)
            if outcome == "break":
                break
            continue
        if isinstance(statement, (ast.With, ast.AsyncWith, ast.For, ast.While, ast.Try, ast.Match)):
            if _may_return_any([statement]):
                break
            continue
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            call = _assignment_call_and_drop(statement, functions, trusted)
            if call is not None:
                calls.append((call, set(trusted)))
            continue
        if isinstance(statement, ast.Expr):
            call = _direct_call_node(statement.value, functions)
            if call is not None:
                calls.append((call, set(trusted)))
    return calls


def _callee_signature_binding(
    call: ast.Call, caller_names: set[str], callee: ast.FunctionDef
) -> set[str]:
    """Map the caller's incoming signature to the callee's signature parameter."""
    parameters = [*callee.args.args, *callee.args.kwonlyargs]
    parameter_names = [parameter.arg for parameter in parameters]
    mapping: dict[str, ast.expr] = {}
    for index, argument in enumerate(call.args):
        if index < len(parameter_names):
            mapping[parameter_names[index]] = argument
    for keyword in call.keywords:
        if keyword.arg is not None:
            mapping[keyword.arg] = keyword.value
    return {
        name
        for name, value in mapping.items()
        if "signature" in name.lower() and _evaluated_signature_value(value, caller_names)
    }


def _entry_signature_binding(view_call: ast.Call, entry: ast.FunctionDef) -> set[str]:
    """Bind the entry parameter that receives the view's header-derived signature."""
    parameters = [*entry.args.args, *entry.args.kwonlyargs]
    parameter_names = [parameter.arg for parameter in parameters]
    mapping: dict[str, ast.expr] = {}
    for index, argument in enumerate(view_call.args):
        if index < len(parameter_names):
            mapping[parameter_names[index]] = argument
    for keyword in view_call.keywords:
        if keyword.arg is not None:
            mapping[keyword.arg] = keyword.value
    return {
        name
        for name, value in mapping.items()
        if "signature" in name.lower() and _request_header_argument(value)
    }


def _meaningful_verification(node: ast.AST, signature_names: set[str]) -> bool:
    """Return True when a failed verification actually rejects the request."""
    return _verification_on_accepting_path(list(getattr(node, "body", [])), signature_names)


def _service_verifies_signature(
    services_source: str, function_name: str, view_call: ast.Call
) -> bool:
    """Walk local calls, requiring the incoming signature to reach verification."""
    if not services_source:
        return False
    tree = _parse(services_source)
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    entry = functions.get(function_name)
    if entry is None:
        return False
    bound = _entry_signature_binding(view_call, entry)
    if not bound:
        return False
    seen: set[str] = set()
    pending: list[tuple[str, set[str]]] = [(function_name, bound)]
    while pending:
        name, signature_names = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        node = functions.get(name)
        if node is None:
            continue
        if _meaningful_verification(node, signature_names):
            return True
        for call, call_trust in _executed_local_calls(
            list(node.body), functions, set(signature_names)
        ):
            callee = _call_func_name(call)
            callee_node = functions.get(callee)
            if callee_node is None:
                continue
            bound = _callee_signature_binding(call, call_trust, callee_node)
            if bound:
                pending.append((callee, bound))
    return False
