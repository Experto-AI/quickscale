"""
Rule 26's incoming-signature derivation and verification mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_webhooks`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast

from scripts.module_conventions._webhooks_flows import (
    _may_return_any,
    _overwritten_names,
    _rejects_by_raising,
    _selected_branch,
)
from scripts.module_conventions.core import _call_func_name, _static_truth

# Rule 26: method calls whose value preserves signature dependence.  A method
# outside this list could discard its receiver (``signature.join([...])``), so
# it earns no verification credit.
SIGNATURE_METHOD_DERIVATIONS = frozenset(
    {"casefold", "decode", "encode", "lower", "lstrip", "rstrip", "strip", "upper"}
)

# Rule 26: the split methods a vendor advertises one or more signatures with,
# and the value-preserving methods a candidate passes through to reach its
# comparison (Svix sends ``v1,<base64>`` entries in ``svix-signature``).
CANDIDATE_SPLIT_METHODS = frozenset({"split", "rsplit"})
CANDIDATE_SELECTION_METHODS = frozenset(
    {"partition", "removeprefix", "removesuffix", "replace", "rsplit", "split"}
)


def _distinct_arguments(call: ast.Call) -> bool:
    if len(call.args) < 2:
        return False
    return ast.dump(call.args[0]) != ast.dump(call.args[1])


def _is_falsy_constant(node: ast.expr) -> bool:
    """Return True when *node* is a literal falsy value."""
    return isinstance(node, ast.Constant) and not node.value


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
        return _evaluated_ifexp(expr, names)
    if isinstance(expr, ast.BoolOp):
        return _evaluated_boolop(expr, names)
    if isinstance(expr, ast.Call):
        return _evaluated_call(expr, names)
    return False


def _evaluated_ifexp(expr: ast.IfExp, names: set[str]) -> bool:
    """Return True when the conditional's selected value derives from the signature."""
    truth = _static_truth(expr.test)
    if truth is True:
        return _evaluated_signature_value(expr.body, names)
    if truth is False:
        return _evaluated_signature_value(expr.orelse, names)
    return _evaluated_signature_value(expr.body, names) and _evaluated_signature_value(
        expr.orelse, names
    )


def _evaluated_boolop(expr: ast.BoolOp, names: set[str]) -> bool:
    """Return True when every value the boolean operator can supply derives from the signature."""
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
        _is_falsy_constant(operand) or _evaluated_signature_value(operand, names)
        for operand in operands[1:]
    )


def _evaluated_call(expr: ast.Call, names: set[str]) -> bool:
    """Return True when the call's evaluated value derives from the signature."""
    func = expr.func
    if isinstance(func, ast.Attribute):
        # Only a known value-preserving method, on a trusted receiver.
        return func.attr in SIGNATURE_METHOD_DERIVATIONS and _evaluated_signature_value(
            func.value, names
        )
    if isinstance(func, ast.Name) and func.id in {"bytes", "str"} and expr.args:
        return any(_evaluated_signature_value(argument, names) for argument in expr.args) and all(
            isinstance(argument, ast.Constant) or _evaluated_signature_value(argument, names)
            for argument in expr.args
        )
    return False


def _consumes_names(call: ast.Call, names: set[str]) -> bool:
    """Return True when a comparison argument's evaluated value derives from the signature."""
    if not names:
        return False
    return any(
        _evaluated_signature_value(argument, names)
        for argument in [*call.args, *(keyword.value for keyword in call.keywords)]
    )


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


def _loop_verifies_before_raise(
    statement: ast.For, trusted: set[str], pending: list[ast.stmt]
) -> bool:
    """Return True when a candidate loop verifies and the path rejects right after."""
    return (
        _signature_candidate_loop_verifies(statement, trusted)
        and bool(pending)
        and isinstance(pending[0], ast.Raise)
    )


def _assignment_verifies(statement: ast.Assign | ast.AnnAssign, trusted: set[str]) -> bool:
    """Drop the trusted names the assignment overwrites, then credit construct_event."""
    targets: list[ast.expr] = []
    if isinstance(statement, ast.Assign):
        targets = list(statement.targets)
    else:
        targets = [statement.target]
    for target in targets:
        if isinstance(target, ast.Name) and target.id in trusted:
            trusted.discard(target.id)
    return _calls_construct_event(statement.value, trusted)


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
            selected = _selected_branch(statement)
            if selected is not None:
                pending = list(selected) + pending
                continue
            branch = _failure_branch(statement, trusted)
            if branch is not None and _rejects_by_raising(branch):
                return True
            if _may_return_any(statement.body) or _may_return_any(statement.orelse):
                return False
            continue
        if isinstance(statement, ast.For):
            if _loop_verifies_before_raise(statement, trusted, pending):
                return True
            if _may_return_any([statement]):
                return False
            continue
        if isinstance(statement, (ast.With, ast.AsyncWith, ast.While, ast.Try, ast.Match)):
            if _may_return_any([statement]):
                return False
            continue
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            if _assignment_verifies(statement, trusted):
                return True
    return False


def _signature_candidate_loop_verifies(statement: ast.For, trusted: set[str]) -> bool:
    """
    Return True when a loop scans signature candidates for a match.

    Vendor signature headers advertise one or more candidates (Svix sends a
    space-separated ``v1,<base64>`` list); the canonical verification loops
    over ``signature.split(...)``, compares a candidate-derived value in
    constant time, and returns only on a match.  Credit only loops that iterate
    over the incoming signature, guard an accepting Return with a
    ``compare_digest`` call on a candidate-derived value, and reach no other
    Return; the caller requires the loop to reject afterwards with a raise.
    """
    if statement.orelse:
        return False
    target = statement.target
    if not isinstance(target, ast.Name):
        return False
    iterable = statement.iter
    if not (
        isinstance(iterable, ast.Call)
        and isinstance(iterable.func, ast.Attribute)
        and iterable.func.attr in CANDIDATE_SPLIT_METHODS
        and _evaluated_signature_value(iterable.func.value, trusted)
    ):
        return False
    derived = {target.id}
    guard = False
    for inner in statement.body:
        if isinstance(inner, ast.If) and _candidate_guard_returns(inner, derived):
            guard = True
            continue
        if _may_return_any([inner]):
            return False
        _update_candidate_derivation(inner, derived)
    return guard


def _candidate_guard_returns(statement: ast.If, derived: set[str]) -> bool:
    """Return True when *statement* accepts only on a candidate comparison."""
    calls = _and_evaluated_compares(statement.test)
    if not any(_distinct_arguments(call) and _consumes_names(call, derived) for call in calls):
        return False
    if _may_return_any(statement.orelse):
        return False
    return any(_may_return_any([inner]) for inner in statement.body)


def _and_evaluated_compares(node: ast.expr) -> list[ast.Call]:
    """
    Return ``compare_digest`` calls the accepting path must pass through.

    Only a bare call or a chain of ``and`` operands guarantees the call was
    evaluated and held: an ``or`` or a conditional expression can reach the
    guarded body without evaluating it.
    """
    if isinstance(node, ast.Call) and _call_func_name(node) == "compare_digest":
        return [node]
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
        calls: list[ast.Call] = []
        for operand in node.values:
            calls.extend(_and_evaluated_compares(operand))
        return calls
    return []


def _update_candidate_derivation(statement: ast.stmt, derived: set[str]) -> None:
    """Track which loop-local names still derive from the looped candidate."""
    if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
        names = _single_target_names(statement.targets[0])
        if names is not None:
            if _candidate_value(statement.value, derived):
                derived.update(names)
            else:
                derived.difference_update(names)
            return
    derived.difference_update(_overwritten_names([statement]))


def _single_target_names(target: ast.expr) -> set[str] | None:
    """Return the names a simple assignment target binds, else None."""
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        names: set[str] = set()
        for element in target.elts:
            if not isinstance(element, ast.Name):
                return None
            names.add(element.id)
        return names
    return None


def _candidate_value(node: ast.expr, derived: set[str]) -> bool:
    """Return True when *node* derives from the looped candidate values."""
    if _evaluated_signature_value(node, derived):
        return True
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in CANDIDATE_SELECTION_METHODS
        and _candidate_value(node.func.value, derived)
    ):
        return True
    if isinstance(node, ast.Subscript):
        return _candidate_value(node.value, derived)
    if isinstance(node, (ast.Tuple, ast.List)):
        return bool(node.elts) and all(_candidate_value(element, derived) for element in node.elts)
    return False
