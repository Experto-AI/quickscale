"""
Statement-flow mechanics: reachable calls, termination, and jumps.

Implementation detail of :mod:`scripts.module_conventions.rules_misc`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast
from enum import Enum

from scripts.module_conventions.core import _static_truth


class _Outcome(Enum):
    """How one statement leaves its enclosing statement sequence."""

    #: Execution continues with the next statement.
    NEXT = "next"
    #: Every executed route returns or raises.
    TERMINATED = "terminated"
    #: Every executed route jumps out of the sequence (break, continue).
    UNREACHABLE = "unreachable"


def _calls_within(node: ast.AST) -> list[ast.Call]:
    """Return calls reachable in a node, skipping statically dead branches."""
    calls: list[ast.Call] = []
    pending = [node]
    while pending:
        current = pending.pop()
        if isinstance(current, ast.Call):
            calls.append(current)
        children = _calls_traversal_children(current)
        pending.extend(ast.iter_child_nodes(current) if children is None else children)
    return calls


def _calls_traversal_children(current: ast.AST) -> list[ast.AST] | None:
    """Return the children a calls traversal visits next; ``None`` means every child."""
    if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return []
    if isinstance(current, ast.Lambda):
        # The body is deferred; only default arguments evaluate at definition.
        return [
            default
            for default in [*current.args.defaults, *current.args.kw_defaults]
            if default is not None
        ]
    if isinstance(current, ast.If):
        return _static_branch_children(current.test, current.body, current.orelse)
    if isinstance(current, ast.While) and _static_truth(current.test) is False:
        return [current.test, *current.orelse]
    if isinstance(current, ast.IfExp):
        return _static_branch_children(current.test, [current.body], [current.orelse])
    if isinstance(current, ast.BoolOp):
        return _bool_operands(current)
    return None


def _static_branch_children(
    test: ast.expr, body: list[ast.AST], orelse: list[ast.AST]
) -> list[ast.AST] | None:
    """Return the test and the statically chosen branch; ``None`` runs both branches."""
    truth = _static_truth(test)
    if truth is True:
        return [test, *body]
    if truth is False:
        return [test, *orelse]
    return None


def _bool_operands(node: ast.BoolOp) -> list[ast.AST]:
    """Return the operands evaluated before one short-circuits the rest."""
    operands: list[ast.AST] = []
    for operand in node.values:
        operands.append(operand)
        truth = _static_truth(operand)
        if (isinstance(node.op, ast.And) and truth is False) or (
            isinstance(node.op, ast.Or) and truth is True
        ):
            break
    return operands


def _direct_calls(node: ast.AST) -> list[ast.Call]:
    """Return calls executed by a function body before it terminates."""
    calls: list[ast.Call] = []
    _collect_direct_calls(list(getattr(node, "body", [])), calls)
    return calls


def _statements_terminate(statements: list[ast.stmt]) -> bool:
    """Return True when every executed route through these statements ends in return/raise."""
    return _collect_direct_calls(statements, [])


def _match_exhaustive(cases: list[ast.match_case]) -> bool:
    """Return True when an unguarded catch-all case matches every value."""
    return any(
        isinstance(case.pattern, ast.MatchAs)
        and case.pattern.pattern is None
        and case.guard is None
        for case in cases
    )


def _effective_cases(cases: list[ast.match_case]) -> list[ast.match_case]:
    """Drop cases whose guard is statically false; their bodies never run."""
    return [case for case in cases if case.guard is None or _static_truth(case.guard) is not False]


def _may_fall_through(statements: list[ast.stmt]) -> bool:
    """Return True when some route through every statement completes normally."""
    return all(_statement_may_fall_through(statement) for statement in statements)


def _statement_may_fall_through(statement: ast.stmt) -> bool:
    """Return True when some route through one statement completes normally."""
    if isinstance(statement, (ast.Raise, ast.Return, ast.Break, ast.Continue)):
        return False
    if isinstance(statement, ast.If):
        return _if_may_fall_through(statement)
    if isinstance(statement, (ast.With, ast.AsyncWith)):
        return _may_fall_through(statement.body)
    if isinstance(statement, ast.While) and _static_truth(statement.test) is True:
        # An endless loop completes only through a break.
        return _contains_jump(statement.body, ast.Break)
    if isinstance(statement, (ast.For, ast.While)):
        # A loop whose condition may be false at once runs zero times.
        return True
    if isinstance(statement, (ast.Try, ast.TryStar)):
        return _try_may_fall_through(statement)
    if isinstance(statement, ast.Match):
        return _match_may_fall_through(statement)
    return True


def _if_may_fall_through(statement: ast.If) -> bool:
    """Return True when the statically chosen branch, or either live branch, falls through."""
    truth = _static_truth(statement.test)
    if truth is True:
        return _may_fall_through(statement.body)
    if truth is False:
        return _may_fall_through(statement.orelse)
    return _may_fall_through(statement.body) or _may_fall_through(statement.orelse)


def _try_may_fall_through(statement: ast.Try | ast.TryStar) -> bool:
    """Return True when a route through the try statement completes normally."""
    if not _may_fall_through(statement.finalbody):
        return False
    normal_falls = _may_fall_through(statement.body) and _may_fall_through(statement.orelse)
    handler_falls = any(_may_fall_through(handler.body) for handler in statement.handlers)
    return normal_falls or handler_falls


def _match_may_fall_through(statement: ast.Match) -> bool:
    """Return True when the match statement may complete without a return/raise."""
    cases = _effective_cases(statement.cases)
    if not _match_exhaustive(cases):
        return True
    return any(_may_fall_through(case.body) for case in cases)


def _contains_jump(statements: list[ast.stmt], kind: type[ast.Break]) -> bool:
    """
    Return True when a reachable break/continue targeting the analyzed loop exists.

    A jump inside a nested loop targets that loop, a jump in a statically dead
    branch never runs, and a jump after an unconditional return/raise or after
    another jump is unreachable, so none of them counts.
    """
    for statement in statements:
        outcome = _jump_outcome(statement, kind)
        if outcome is not None:
            return outcome
    return False


def _jump_outcome(statement: ast.stmt, kind: type[ast.Break]) -> bool | None:
    """Return a jump verdict for one statement, or ``None`` to keep scanning."""
    if isinstance(statement, (ast.Raise, ast.Return)):
        return False
    if isinstance(statement, ast.Break):
        return kind is ast.Break
    if isinstance(statement, ast.Continue):
        return kind is ast.Continue
    if isinstance(statement, (ast.For, ast.While)):
        return _loop_jump_outcome(statement, kind)
    if isinstance(statement, ast.If):
        return _if_jump_outcome(statement, kind)
    if isinstance(statement, (ast.Try, ast.TryStar)):
        return _try_jump_outcome(statement, kind)
    if isinstance(statement, (ast.With, ast.AsyncWith)):
        return _with_jump_outcome(statement, kind)
    if isinstance(statement, ast.Match):
        return _match_jump_outcome(statement, kind)
    return None


def _loop_jump_outcome(statement: ast.For | ast.While, kind: type[ast.Break]) -> bool | None:
    """Return a jump verdict for a loop statement, or ``None`` to keep scanning."""
    # A nested loop's else suite is outside it and can still jump out of
    # the loop being analyzed; the nested loop itself may terminate the
    # enclosing sequence.
    if _contains_jump(statement.orelse, kind):
        return True
    if _statements_terminate([statement]) or not _may_fall_through([statement]):
        return False
    return None


def _if_jump_outcome(statement: ast.If, kind: type[ast.Break]) -> bool | None:
    """Return a jump verdict for an if statement, or ``None`` to keep scanning."""
    truth = _static_truth(statement.test)
    if truth is True:
        if _contains_jump(statement.body, kind):
            return True
        if not _may_fall_through(statement.body):
            return False
        return None
    if truth is False:
        if _contains_jump(statement.orelse, kind):
            return True
        if not _may_fall_through(statement.orelse):
            return False
        return None
    if _contains_jump(statement.body, kind) or _contains_jump(statement.orelse, kind):
        return True
    if not _may_fall_through(statement.body) and not _may_fall_through(statement.orelse):
        return False
    return None


def _try_jump_outcome(statement: ast.Try | ast.TryStar, kind: type[ast.Break]) -> bool | None:
    """Return a jump verdict for a try statement, or ``None`` to keep scanning."""
    if not _may_fall_through(statement.finalbody):
        # A return/raise or jump in ``finally`` overrides the pending jump.
        return _contains_jump(statement.finalbody, kind)
    if (
        _contains_jump(statement.body, kind)
        or any(_contains_jump(handler.body, kind) for handler in statement.handlers)
        or _contains_jump(statement.orelse, kind)
        or _contains_jump(statement.finalbody, kind)
    ):
        return True
    if not _may_fall_through([statement]):
        return False
    return None


def _with_jump_outcome(statement: ast.With | ast.AsyncWith, kind: type[ast.Break]) -> bool | None:
    """Return a jump verdict for a with statement, or ``None`` to keep scanning."""
    if _contains_jump(statement.body, kind):
        return True
    if not _may_fall_through([statement]):
        return False
    return None


def _match_jump_outcome(statement: ast.Match, kind: type[ast.Break]) -> bool | None:
    """Return a jump verdict for a match statement, or ``None`` to keep scanning."""
    if any(_contains_jump(case.body, kind) for case in _effective_cases(statement.cases)):
        return True
    if not _may_fall_through([statement]):
        return False
    return None


def _contains_break(statements: list[ast.stmt]) -> bool:
    """Return True when a reachable break can leave this loop before its else suite."""
    return _contains_jump(statements, ast.Break)


def _contains_continue(statements: list[ast.stmt]) -> bool:
    """Return True when a reachable continue can restart this loop's next iteration."""
    return _contains_jump(statements, ast.Continue)


def _collect_direct_calls(statements: list[ast.stmt], calls: list[ast.Call]) -> bool:
    """Collect executed calls in order; return True when the sequence terminates."""
    for statement in statements:
        outcome = _statement_outcome(statement, calls)
        if outcome is _Outcome.TERMINATED:
            return True
        if outcome is _Outcome.UNREACHABLE:
            return False
    return False


def _statement_outcome(statement: ast.stmt, calls: list[ast.Call]) -> _Outcome:
    """Return how one statement leaves its sequence, collecting its executed calls."""
    if isinstance(statement, ast.Raise):
        return _Outcome.TERMINATED
    if isinstance(statement, ast.Return):
        if statement.value is not None:
            calls.extend(_calls_within(statement.value))
        return _Outcome.TERMINATED
    if isinstance(statement, (ast.Break, ast.Continue)):
        # Control leaves this statement sequence: later calls are unreachable.
        return _Outcome.UNREACHABLE
    if isinstance(statement, ast.If):
        return _if_outcome(statement, calls)
    if isinstance(statement, (ast.With, ast.AsyncWith)):
        return _with_outcome(statement, calls)
    if isinstance(statement, (ast.For, ast.While)):
        return _loop_outcome(statement, calls)
    if isinstance(statement, ast.Match):
        return _match_outcome(statement, calls)
    if isinstance(statement, (ast.Try, ast.TryStar)):
        return _try_outcome(statement, calls)
    calls.extend(_calls_within(statement))
    return _Outcome.NEXT


def _if_outcome(statement: ast.If, calls: list[ast.Call]) -> _Outcome:
    """Return the outcome of an if statement, collecting its executed calls."""
    test = statement.test
    calls.extend(_calls_within(test))
    truth = _static_truth(test)
    if truth is not None:
        branch = statement.body if truth else statement.orelse
        if _collect_direct_calls(branch, calls):
            return _Outcome.TERMINATED
        if not _may_fall_through(branch):
            return _Outcome.UNREACHABLE
        return _Outcome.NEXT
    body_terminates = _collect_direct_calls(statement.body, calls)
    else_terminates = _collect_direct_calls(statement.orelse, calls)
    if body_terminates and else_terminates:
        return _Outcome.TERMINATED
    if not _may_fall_through([statement]):
        return _Outcome.UNREACHABLE
    return _Outcome.NEXT


def _with_outcome(statement: ast.With | ast.AsyncWith, calls: list[ast.Call]) -> _Outcome:
    """Return the outcome of a with statement, collecting its executed calls."""
    for item in statement.items:
        calls.extend(_calls_within(item.context_expr))
    if _collect_direct_calls(statement.body, calls):
        return _Outcome.TERMINATED
    if not _may_fall_through([statement]):
        return _Outcome.UNREACHABLE
    return _Outcome.NEXT


def _loop_outcome(statement: ast.For | ast.While, calls: list[ast.Call]) -> _Outcome:
    """Return the outcome of a for/while statement, collecting its executed calls."""
    iterable = statement.test if isinstance(statement, ast.While) else statement.iter
    calls.extend(_calls_within(iterable))
    if isinstance(statement, ast.While) and _static_truth(statement.test) is False:
        if _collect_direct_calls(statement.orelse, calls):
            return _Outcome.TERMINATED
        if not _may_fall_through([statement]):
            return _Outcome.UNREACHABLE
        return _Outcome.NEXT
    _collect_direct_calls(statement.body, calls)
    else_terminates = _collect_direct_calls(statement.orelse, calls)
    # ``break`` leaves the loop without running ``else``, so a terminating
    # else suite does not terminate the enclosing sequence when the loop
    # body can break out.
    if else_terminates and not _contains_break(statement.body):
        return _Outcome.TERMINATED
    if not _may_fall_through([statement]):
        return _Outcome.UNREACHABLE
    return _Outcome.NEXT


def _match_outcome(statement: ast.Match, calls: list[ast.Call]) -> _Outcome:
    """Return the outcome of a match statement, collecting its executed calls."""
    calls.extend(_calls_within(statement.subject))
    for case in statement.cases:
        if case.guard is not None:
            calls.extend(_calls_within(case.guard))
    cases = _effective_cases(statement.cases)
    case_results = [_collect_direct_calls(case.body, calls) for case in cases]
    if cases and all(case_results) and _match_exhaustive(cases):
        return _Outcome.TERMINATED
    if not _may_fall_through([statement]):
        return _Outcome.UNREACHABLE
    return _Outcome.NEXT


def _try_outcome(statement: ast.Try | ast.TryStar, calls: list[ast.Call]) -> _Outcome:
    """Return the outcome of a try statement, collecting its executed calls."""
    body_terminates = _collect_direct_calls(statement.body, calls)
    handler_results = [_collect_direct_calls(handler.body, calls) for handler in statement.handlers]
    handlers_terminate = bool(handler_results) and all(handler_results)
    else_terminates = False
    if not body_terminates:
        else_terminates = _collect_direct_calls(statement.orelse, calls)
    final_terminates = _collect_direct_calls(statement.finalbody, calls)
    raise_path_terminates = (not statement.handlers) or handlers_terminate
    if final_terminates:
        return _Outcome.TERMINATED
    if body_terminates and raise_path_terminates:
        return _Outcome.TERMINATED
    if else_terminates and raise_path_terminates:
        return _Outcome.TERMINATED
    if not _may_fall_through([statement]):
        return _Outcome.UNREACHABLE
    return _Outcome.NEXT
