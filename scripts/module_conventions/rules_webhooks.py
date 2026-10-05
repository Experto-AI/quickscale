"""Webhook rule and its verification helpers."""

from __future__ import annotations

import ast
from collections.abc import Callable, Mapping

from scripts.module_conventions.core import (
    Corpus,
    _call_func_name,
    _class_names,
    _keyword,
    _literal,
    _parse,
    _static_truth,
)

# Rule 26: method calls whose value preserves signature dependence.  A method
# outside this list could discard its receiver (``signature.join([...])``), so
# it earns no verification credit.
SIGNATURE_METHOD_DERIVATIONS = frozenset(
    {"casefold", "decode", "encode", "lower", "lstrip", "rstrip", "strip", "upper"}
)


def rule_26_webhooks(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        urls = module.files.get("urls.py")
        if urls is None:
            continue
        view_names: list[str] = []
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
                violations.append(
                    f"rule 26: {module.name}: webhook route {route or name!r} has no view"
                )
                continue
            view = node.args[1]
            if (
                isinstance(view, ast.Call)
                and isinstance(view.func, ast.Attribute)
                and view.func.attr == "as_view"
            ):
                target = view.func.value
                if isinstance(target, ast.Name):
                    view_names.append(target.id)
                elif isinstance(target, ast.Attribute):
                    view_names.append(target.attr)
                else:
                    violations.append(
                        f"rule 26: {module.name}: webhook route {route or name!r} "
                        "does not resolve to an APIView class"
                    )
            else:
                violations.append(
                    f"rule 26: {module.name}: webhook route {route or name!r} does not "
                    "mount an APIView.as_view() callable"
                )
        for view_name in view_names:
            views = module.files.get("views.py", "")
            if not views:
                violations.append(f"rule 26: {module.name}: webhook view {view_name} not found")
                continue
            tree = _parse(views)
            node = next(
                (
                    candidate
                    for candidate in tree.body
                    if isinstance(candidate, ast.ClassDef) and candidate.name == view_name
                ),
                None,
            )
            if node is None:
                violations.append(f"rule 26: {module.name}: webhook view {view_name} not found")
                continue
            if not any(
                base == "APIView" or base.endswith("APIView") for base in _class_names(node)
            ):
                violations.append(f"rule 26: {module.name}: {view_name} is not a DRF APIView")
            service_bindings: dict[str, str] = {}
            services_module_names: set[str] = set()
            for statement in tree.body:
                if not isinstance(statement, ast.ImportFrom):
                    continue
                if (statement.module or "").endswith(".services"):
                    for alias in statement.names:
                        service_bindings[alias.asname or alias.name] = alias.name
                for alias in statement.names:
                    if alias.name == "services":
                        services_module_names.add(alias.asname or alias.name)
            for attribute in (
                "authentication_classes",
                "permission_classes",
                "throttle_classes",
            ):
                found = False
                for stmt in node.body:
                    if isinstance(stmt, ast.Assign):
                        for target in stmt.targets:
                            if (
                                isinstance(target, ast.Name)
                                and target.id == attribute
                                and isinstance(stmt.value, ast.List)
                                and not stmt.value.elts
                            ):
                                found = True
                if not found:
                    violations.append(
                        f"rule 26: {module.name}: {view_name} does not declare empty {attribute}"
                    )
            post = next(
                (
                    method
                    for method in node.body
                    if isinstance(method, ast.FunctionDef) and method.name == "post"
                ),
                None,
            )
            if post is None:
                violations.append(f"rule 26: {module.name}: {view_name} defines no post()")
                continue
            service_calls = _executed_service_calls(
                list(post.body),
                lambda call: (
                    _service_call_target(call, service_bindings, services_module_names) is not None
                ),
            )
            if not service_calls:
                violations.append(
                    f"rule 26: {module.name}: {view_name} does not call a services.py function"
                )
            services_source = module.files.get("services.py", "")
            for call in service_calls:
                body = _keyword(call, "body")
                if not (isinstance(body, ast.Attribute) and body.attr == "body"):
                    violations.append(
                        f"rule 26: {module.name}: {view_name} does not pass request.body "
                        "to a service"
                    )
                signature_argument = next(
                    (
                        keyword.value
                        for keyword in call.keywords
                        if keyword.arg and "signature" in keyword.arg
                    ),
                    None,
                )
                if signature_argument is None or not _request_header_argument(signature_argument):
                    violations.append(
                        f"rule 26: {module.name}: {view_name} does not take the signature "
                        "from request headers"
                    )
                target = _service_call_target(call, service_bindings, services_module_names)
                if target is not None and not _service_verifies_signature(
                    services_source, target, call
                ):
                    violations.append(
                        f"rule 26: {module.name}: {view_name} calls {target}, which does "
                        "not verify a signature"
                    )
    return violations


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


def _distinct_arguments(call: ast.Call) -> bool:
    if len(call.args) < 2:
        return False
    return ast.dump(call.args[0]) != ast.dump(call.args[1])


def _is_rejection_value(value: ast.expr | None) -> bool:
    return value is None or (isinstance(value, ast.Constant) and value.value in {None, False})


def _may_return_non_rejection(statements: list[ast.stmt]) -> bool:
    """Return True when any route through these statements can return a value."""
    for statement in statements:
        if isinstance(statement, ast.Return) and not _is_rejection_value(statement.value):
            return True
        if isinstance(statement, ast.If):
            if _may_return_non_rejection(statement.body) or _may_return_non_rejection(
                statement.orelse
            ):
                return True
        elif isinstance(statement, (ast.With, ast.AsyncWith)):
            if _may_return_non_rejection(statement.body):
                return True
        elif isinstance(statement, (ast.For, ast.While)):
            if _may_return_non_rejection(statement.body) or _may_return_non_rejection(
                statement.orelse
            ):
                return True
        elif isinstance(statement, ast.Try):
            if (
                _may_return_non_rejection(statement.body)
                or any(_may_return_non_rejection(handler.body) for handler in statement.handlers)
                or _may_return_non_rejection(statement.orelse)
                or _may_return_non_rejection(statement.finalbody)
            ):
                return True
        elif isinstance(statement, ast.Match):
            if any(_may_return_non_rejection(case.body) for case in statement.cases):
                return True
    return False


def _rejects_failure(branch: list[ast.stmt]) -> bool:
    """Return True when every executed route through the failure path rejects."""
    for statement in branch:
        if isinstance(statement, ast.Raise):
            return True
        if isinstance(statement, ast.Return):
            return _is_rejection_value(statement.value)
        if isinstance(statement, ast.If):
            test = statement.test
            if isinstance(test, ast.Constant) and test.value is True:
                if _rejects_failure(statement.body):
                    return True
                if _may_return_non_rejection(statement.body):
                    return False
                continue
            if isinstance(test, ast.Constant) and test.value is False:
                if _rejects_failure(statement.orelse):
                    return True
                if _may_return_non_rejection(statement.orelse):
                    return False
                continue
            if _may_return_non_rejection(statement.body) or _may_return_non_rejection(
                statement.orelse
            ):
                return False
            continue
        if isinstance(statement, (ast.With, ast.AsyncWith, ast.For, ast.While, ast.Try, ast.Match)):
            if _may_return_non_rejection([statement]):
                return False
            continue
    return False


def _evaluated_signature_value(expr: ast.expr, names: set[str]) -> bool:
    """
    Return True when the expression's evaluated value derives from the incoming signature.

    Statically selected branches are followed, so a dead branch cannot launder
    trust: ``signature if False else "fixed"`` evaluates to a constant and is
    rejected, while ``signature`` and derived values such as
    ``(signature or "").encode("utf-8")`` are accepted.
    """
    if isinstance(expr, ast.Name):
        return expr.id in names
    if isinstance(expr, ast.Attribute):
        return _evaluated_signature_value(expr.value, names)
    if isinstance(expr, ast.IfExp):
        truth = _static_truth(expr.test)
        if truth is True:
            return _evaluated_signature_value(expr.body, names)
        if truth is False:
            return _evaluated_signature_value(expr.orelse, names)
        return _evaluated_signature_value(expr.body, names) and _evaluated_signature_value(
            expr.orelse, names
        )
    if isinstance(expr, ast.BoolOp):
        operands = expr.values
        if not operands:
            return False
        if isinstance(expr.op, ast.And):
            # Any operand can supply the value (the first falsy one, else the
            # last), so every operand must itself derive from the signature.
            return all(_evaluated_signature_value(operand, names) for operand in operands)
        # Or: the first operand supplies the value while it is truthy; later
        # operands are reached only when it is falsy, so only falsy constants
        # may stand in for it.
        if not _evaluated_signature_value(operands[0], names):
            return False
        return all(
            (isinstance(operand, ast.Constant) and not operand.value)
            or _evaluated_signature_value(operand, names)
            for operand in operands[1:]
        )
    if isinstance(expr, ast.Call):
        func = expr.func
        if isinstance(func, ast.Attribute):
            # Only a known value-preserving method, on a trusted receiver.
            return func.attr in SIGNATURE_METHOD_DERIVATIONS and _evaluated_signature_value(
                func.value, names
            )
        if isinstance(func, ast.Name) and func.id in {"bytes", "str"} and expr.args:
            return any(
                _evaluated_signature_value(argument, names) for argument in expr.args
            ) and all(
                isinstance(argument, ast.Constant) or _evaluated_signature_value(argument, names)
                for argument in expr.args
            )
        return False
    return False


def _consumes_names(call: ast.Call, names: set[str]) -> bool:
    """Return True when a comparison argument's evaluated value derives from the signature."""
    if not names:
        return False
    return any(
        _evaluated_signature_value(argument, names)
        for argument in [*call.args, *(keyword.value for keyword in call.keywords)]
    )


def _failure_branch(statement: ast.If, signature_names: set[str]) -> list[ast.stmt] | None:
    """Return the branch taken when a supported comparison does not hold."""
    test = statement.test
    if (
        isinstance(test, ast.UnaryOp)
        and isinstance(test.op, ast.Not)
        and isinstance(test.operand, ast.Call)
        and _call_func_name(test.operand) == "compare_digest"
        and _distinct_arguments(test.operand)
        and _consumes_names(test.operand, signature_names)
    ):
        return statement.body
    if (
        isinstance(test, ast.Call)
        and _call_func_name(test) == "compare_digest"
        and _distinct_arguments(test)
        and _consumes_names(test, signature_names)
    ):
        return statement.orelse
    return None


def _calls_construct_event(value: ast.expr | None, signature_names: set[str]) -> bool:
    """
    Credit an SDK verification call only when its signature slot reads the incoming signature.

    The slot is the SDK's second positional argument (`sig_header`) or an
    explicit `sig_header`/`signature` keyword, as the Stripe SDK and the
    billing wrapper use.  A trusted name anywhere else (say, as the payload)
    does not prove the incoming signature was verified.
    """
    if not isinstance(value, ast.Call) or _call_func_name(value) != "construct_event":
        return False
    if not signature_names:
        return False
    for keyword in value.keywords:
        if keyword.arg in {"sig_header", "signature"} and _evaluated_signature_value(
            keyword.value, signature_names
        ):
            return True
    return len(value.args) >= 2 and _evaluated_signature_value(value.args[1], signature_names)


def _may_return_any(statements: list[ast.stmt]) -> bool:
    """Return True when any route through these statements returns a value."""
    for statement in statements:
        if isinstance(statement, ast.Return):
            return True
        if isinstance(statement, ast.If):
            if _may_return_any(statement.body) or _may_return_any(statement.orelse):
                return True
        elif isinstance(statement, (ast.With, ast.AsyncWith)):
            if _may_return_any(statement.body):
                return True
        elif isinstance(statement, (ast.For, ast.While)):
            if _may_return_any(statement.body) or _may_return_any(statement.orelse):
                return True
        elif isinstance(statement, ast.Try):
            if (
                _may_return_any(statement.body)
                or any(_may_return_any(handler.body) for handler in statement.handlers)
                or _may_return_any(statement.orelse)
                or _may_return_any(statement.finalbody)
            ):
                return True
        elif isinstance(statement, ast.Match):
            if any(_may_return_any(case.body) for case in statement.cases):
                return True
    return False


def _rejects_by_raising(branch: list[ast.stmt]) -> bool:
    """Rejection must raise so a caller cannot ignore a returned sentinel."""
    for statement in branch:
        if isinstance(statement, ast.Raise):
            return True
        if isinstance(statement, ast.Return):
            return False
        if isinstance(statement, ast.If):
            test = statement.test
            if isinstance(test, ast.Constant) and test.value is True:
                if _rejects_by_raising(statement.body):
                    return True
                if _may_return_any(statement.body):
                    return False
                continue
            if isinstance(test, ast.Constant) and test.value is False:
                if _rejects_by_raising(statement.orelse):
                    return True
                if _may_return_any(statement.orelse):
                    return False
                continue
            if _may_return_any(statement.body) or _may_return_any(statement.orelse):
                return False
            continue
        if isinstance(statement, (ast.With, ast.AsyncWith, ast.For, ast.While, ast.Try, ast.Match)):
            if _may_return_any([statement]):
                return False
            continue
    return False


def _overwritten_names(statements: list[ast.stmt]) -> set[str]:
    """Return every name stored or deleted anywhere in these statements."""
    names: set[str] = set()
    pending: list[ast.AST] = list(statements)
    while pending:
        current = pending.pop()
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(current, ast.Name) and isinstance(current.ctx, (ast.Store, ast.Del)):
            names.add(current.id)
        pending.extend(ast.iter_child_nodes(current))
    return names


def _verification_on_accepting_path(statements: list[ast.stmt], signature_names: set[str]) -> bool:
    """Credit only a supported guard shape executed on the top-level path."""
    trusted = set(signature_names) - _overwritten_names(statements)
    pending = list(statements)
    while pending:
        statement = pending.pop(0)
        if isinstance(statement, ast.Raise):
            return False
        if isinstance(statement, ast.Return):
            return _calls_construct_event(statement.value, trusted)
        if isinstance(statement, ast.If):
            test = statement.test
            if isinstance(test, ast.Constant) and test.value is False:
                pending = list(statement.orelse) + pending
                continue
            if isinstance(test, ast.Constant) and test.value is True:
                pending = list(statement.body) + pending
                continue
            branch = _failure_branch(statement, trusted)
            if branch is not None and _rejects_by_raising(branch):
                return True
            if _may_return_any(statement.body) or _may_return_any(statement.orelse):
                return False
            continue
        if isinstance(statement, (ast.With, ast.AsyncWith, ast.For, ast.While, ast.Try, ast.Match)):
            if _may_return_any([statement]):
                return False
            continue
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            targets: list[ast.expr] = []
            if isinstance(statement, ast.Assign):
                targets = list(statement.targets)
            elif isinstance(statement, ast.AnnAssign):
                targets = [statement.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id in trusted:
                    trusted.discard(target.id)
            if _calls_construct_event(statement.value, trusted):
                return True
    return False


def _meaningful_verification(node: ast.AST, signature_names: set[str]) -> bool:
    """Return True when a failed verification actually rejects the request."""
    return _verification_on_accepting_path(list(getattr(node, "body", [])), signature_names)


def _direct_call_node(
    node: ast.expr | None, functions: Mapping[str, ast.FunctionDef]
) -> ast.Call | None:
    if isinstance(node, ast.Call) and _call_func_name(node) in functions:
        return node
    return None


def _executed_service_calls(
    statements: list[ast.stmt], is_service: Callable[[ast.Call], bool]
) -> list[ast.Call]:
    """Collect service calls executed on the accepting path (fail-closed)."""
    calls: list[ast.Call] = []
    for statement in statements:
        if isinstance(statement, ast.Raise):
            break
        if isinstance(statement, ast.Return):
            if isinstance(statement.value, ast.Call) and is_service(statement.value):
                calls.append(statement.value)
            break
        if isinstance(statement, ast.If):
            test = statement.test
            if isinstance(test, ast.Constant) and test.value is True:
                calls.extend(_executed_service_calls(statement.body, is_service))
                if _may_return_any(statement.body):
                    break
                continue
            if isinstance(test, ast.Constant) and test.value is False:
                calls.extend(_executed_service_calls(statement.orelse, is_service))
                if _may_return_any(statement.orelse):
                    break
                continue
            if _may_return_non_rejection(statement.body) or _may_return_non_rejection(
                statement.orelse
            ):
                return []
            body_calls = _executed_service_calls(statement.body, is_service)
            else_calls = _executed_service_calls(statement.orelse, is_service)
            body_terminates = _may_return_any(statement.body) or _rejects_by_raising(statement.body)
            else_terminates = _may_return_any(statement.orelse) or _rejects_by_raising(
                statement.orelse
            )
            if body_terminates and else_terminates:
                continue
            if body_terminates or else_terminates:
                calls.extend(body_calls if body_terminates else else_calls)
                continue
            if not (body_calls and else_calls):
                return []
            calls.extend(body_calls)
            continue
        if isinstance(statement, (ast.With, ast.AsyncWith, ast.For, ast.While, ast.Try, ast.Match)):
            if _may_return_any([statement]):
                break
            continue
        if isinstance(statement, (ast.Assign, ast.AnnAssign, ast.Expr)):
            if isinstance(statement.value, ast.Call) and is_service(statement.value):
                calls.append(statement.value)
    return calls


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
            test = statement.test
            if isinstance(test, ast.Constant) and test.value is True:
                calls.extend(_executed_local_calls(statement.body, functions, trusted))
                if _may_return_any(statement.body):
                    break
            elif isinstance(test, ast.Constant) and test.value is False:
                calls.extend(_executed_local_calls(statement.orelse, functions, trusted))
                if _may_return_any(statement.orelse):
                    break
            elif _may_return_any(statement.body) or _may_return_any(statement.orelse):
                break
            continue
        if isinstance(statement, (ast.With, ast.AsyncWith, ast.For, ast.While, ast.Try, ast.Match)):
            if _may_return_any([statement]):
                break
            continue
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            call = _direct_call_node(statement.value, functions)
            if call is not None:
                calls.append((call, set(trusted)))
            targets: list[ast.expr] = []
            if isinstance(statement, ast.Assign):
                targets = list(statement.targets)
            elif isinstance(statement, ast.AnnAssign):
                targets = [statement.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id in trusted:
                    trusted.discard(target.id)
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
