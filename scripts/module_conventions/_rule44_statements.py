"""
Rule 44's statement scanner and its function/block orchestration.

Implementation detail of :mod:`scripts.module_conventions.rule_44`; that
module re-exports every name defined here, so existing import paths keep
working.  The pre-split statement walk is decomposed into per-statement
helpers so every function stays under the harness quality thresholds.
"""

from __future__ import annotations

import ast

from scripts.module_conventions._rule44_expressions import (
    _rule_44_bind,
    _rule_44_scan_expression,
)
from scripts.module_conventions._rule44_names import (
    _RULE_44_ALIAS_PATHS,
    RULE_44_MEMBERSHIP_MODEL,
    RULE_44_MEMBERSHIP_SOURCE,
    _Rule44DeferredBodies,
    _Rule44Environment,
    _Rule44Scope,
    _rule_44_argument_names,
    _rule_44_block_bindings,
    _rule_44_bound_names,
    _rule_44_definition_expressions,
    _rule_44_expression_bindings,
    _rule_44_pattern_names,
    _rule_44_scope_declarations,
)
from scripts.module_conventions.core import _bound_names


def _rule_44_scan_function(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    defining_environment: _Rule44Environment,
    module_environment: _Rule44Environment,
    enclosing_functions: tuple[_Rule44Scope, ...],
    module_name: str,
    rel: str,
    violations: list[str],
) -> None:
    """Scan one function body with Python's name resolution."""
    environment = defining_environment.copy()
    environment.discard_all(_rule_44_argument_names(function.args))
    globals_, nonlocals = _rule_44_scope_declarations(function.body)
    for name in globals_:
        environment.bind(
            name,
            membership=name in module_environment.names,
            aliases=module_environment.aliases.get(name),
        )
    for name in nonlocals:
        nearest = next(
            (scope for scope in reversed(enclosing_functions) if name in scope[1]),
            None,
        )
        if nearest is None:
            environment.discard(name)
            continue
        scope_environment, _ = nearest
        environment.bind(
            name,
            membership=name in scope_environment.names,
            aliases=scope_environment.aliases.get(name),
        )
    _rule_44_scan_block(
        function.body,
        environment,
        module_environment,
        (*enclosing_functions, (environment, _rule_44_bound_names(function))),
        environment,
        module_name,
        rel,
        violations,
    )


def _rule_44_scan_block(
    statements: list[ast.stmt],
    environment: _Rule44Environment,
    module_environment: _Rule44Environment,
    enclosing_functions: tuple[_Rule44Scope, ...],
    scope_environment: _Rule44Environment,
    module_name: str,
    rel: str,
    violations: list[str],
    deferred: _Rule44DeferredBodies | None = None,
    intermediates: _Rule44Environment | None = None,
    skip_first_intermediate: bool = False,
) -> None:
    """
    Scan one scope's statements in order and then its deferred bodies.

    Function bodies are deferred until their real defining scope is final,
    because a function resolves module and enclosing names when it runs, not
    when it is defined; definition-time expressions are scanned in place.  A
    compound statement threads the same ``deferred`` list to the scope that
    owns it, so a body defined inside a branch still waits for the whole
    scope; ``scope_environment`` is that owning scope, the one a closure
    resolves.  A branch or loop scans copies and merges them, so a name stays
    membership when any reachable path keeps it; a ``with`` body always runs
    and writes back directly.  When ``intermediates`` is given, the state at
    each statement boundary is unioned into it, so a caller can model an
    exception raised anywhere along the way; ``skip_first_intermediate``
    drops the block's own arrival state, for a ``finally`` whose exceptional
    exits begin only after it has consumed that arrival.
    """
    owns_deferred = deferred is None
    pending: _Rule44DeferredBodies = [] if deferred is None else deferred
    for index, statement in enumerate(statements):
        if intermediates is not None and not (skip_first_intermediate and index == 0):
            intermediates.merge(environment)
        _rule_44_scan_statement(
            statement,
            environment,
            module_environment,
            enclosing_functions,
            scope_environment,
            module_name,
            rel,
            violations,
            pending,
            intermediates,
        )
    if owns_deferred:
        for function, defining_environment, outer_functions in pending:
            _rule_44_scan_function(
                function,
                defining_environment,
                module_environment,
                outer_functions,
                module_name,
                rel,
                violations,
            )


def _rule_44_scan_statement(
    statement: ast.stmt,
    environment: _Rule44Environment,
    module_environment: _Rule44Environment,
    enclosing_functions: tuple[_Rule44Scope, ...],
    scope_environment: _Rule44Environment,
    module_name: str,
    rel: str,
    violations: list[str],
    deferred: _Rule44DeferredBodies,
    intermediates: _Rule44Environment | None,
) -> None:
    """Scan one statement, binding names in source order as Python does."""
    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        _rule_44_scan_definition(
            statement,
            environment,
            module_environment,
            enclosing_functions,
            scope_environment,
            module_name,
            rel,
            violations,
            deferred,
            intermediates,
        )
        return
    if isinstance(statement, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
        _rule_44_scan_assignment(statement, environment, module_name, rel, violations)
        return
    if isinstance(statement, (ast.Import, ast.ImportFrom)):
        _rule_44_scan_import(statement, environment)
        return
    if isinstance(statement, (ast.For, ast.AsyncFor, ast.While)):
        _rule_44_scan_loop(
            statement,
            environment,
            module_environment,
            enclosing_functions,
            scope_environment,
            module_name,
            rel,
            violations,
            deferred,
            intermediates,
        )
        return
    if isinstance(statement, (ast.With, ast.AsyncWith)):
        _rule_44_scan_with(
            statement,
            environment,
            module_environment,
            enclosing_functions,
            scope_environment,
            module_name,
            rel,
            violations,
            deferred,
            intermediates,
        )
        return
    if isinstance(statement, ast.If):
        _rule_44_scan_conditional(
            statement,
            environment,
            module_environment,
            enclosing_functions,
            scope_environment,
            module_name,
            rel,
            violations,
            deferred,
            intermediates,
        )
        return
    if isinstance(statement, (ast.Try, ast.TryStar)):
        _rule_44_scan_try(
            statement,
            environment,
            module_environment,
            enclosing_functions,
            scope_environment,
            module_name,
            rel,
            violations,
            deferred,
            intermediates,
        )
        return
    if isinstance(statement, ast.Match):
        _rule_44_scan_match(
            statement,
            environment,
            module_environment,
            enclosing_functions,
            scope_environment,
            module_name,
            rel,
            violations,
            deferred,
            intermediates,
        )
        return
    if isinstance(statement, ast.Delete):
        for target in statement.targets:
            environment.discard_all(_bound_names(target))
        return
    for child in ast.iter_child_nodes(statement):
        if isinstance(child, ast.expr):
            _rule_44_scan_expression(child, environment, module_name, rel, violations)


def _rule_44_scan_definition(
    statement: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    environment: _Rule44Environment,
    module_environment: _Rule44Environment,
    enclosing_functions: tuple[_Rule44Scope, ...],
    scope_environment: _Rule44Environment,
    module_name: str,
    rel: str,
    violations: list[str],
    deferred: _Rule44DeferredBodies,
    intermediates: _Rule44Environment | None,
) -> None:
    """Scan a function or class definition and defer its body."""
    for piece in _rule_44_definition_expressions(statement):
        _rule_44_scan_expression(piece, environment, module_name, rel, violations)
    environment.discard(statement.name)
    if isinstance(statement, ast.ClassDef):
        class_environment = environment.copy()
        for member in statement.body:
            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for piece in _rule_44_definition_expressions(member):
                    _rule_44_scan_expression(piece, class_environment, module_name, rel, violations)
                # A class body is not an enclosing lexical scope for its
                # methods — through compounds included — so their bodies
                # resolve the scope that owns the class.
                deferred.append((member, scope_environment, enclosing_functions))
            else:
                _rule_44_scan_statement(
                    member,
                    class_environment,
                    module_environment,
                    enclosing_functions,
                    scope_environment,
                    module_name,
                    rel,
                    violations,
                    deferred,
                    intermediates,
                )
        return
    deferred.append((statement, scope_environment, enclosing_functions))


def _rule_44_scan_assignment(
    statement: ast.Assign | ast.AnnAssign | ast.AugAssign,
    environment: _Rule44Environment,
    module_name: str,
    rel: str,
    violations: list[str],
) -> None:
    """Scan an assignment's value and bind (or shadow) its targets."""
    if isinstance(statement, ast.Assign):
        _rule_44_scan_expression(statement.value, environment, module_name, rel, violations)
        _rule_44_bind(statement.targets, statement.value, environment)
        return
    if isinstance(statement, ast.AnnAssign):
        if statement.value is not None:
            _rule_44_scan_expression(statement.value, environment, module_name, rel, violations)
            _rule_44_bind([statement.target], statement.value, environment)
        return
    _rule_44_scan_expression(statement.value, environment, module_name, rel, violations)


def _rule_44_scan_import(
    statement: ast.Import | ast.ImportFrom,
    environment: _Rule44Environment,
) -> None:
    """Bind import names, keeping orgs module aliases for chain resolution."""
    if isinstance(statement, ast.Import):
        for alias in statement.names:
            parts = tuple(alias.name.split("."))
            name = alias.asname or parts[0]
            path = parts if alias.asname else (parts[0],)
            environment.bind(
                name,
                membership=False,
                aliases=frozenset({path}) if path in _RULE_44_ALIAS_PATHS else None,
            )
        return
    source = tuple(statement.module.split(".")) if statement.module and not statement.level else ()
    for alias in statement.names:
        name = alias.asname or alias.name
        membership = (
            not statement.level
            and statement.module == RULE_44_MEMBERSHIP_SOURCE
            and alias.name == RULE_44_MEMBERSHIP_MODEL
        )
        path = (*source, alias.name) if source else ()
        environment.bind(
            name,
            membership=membership,
            aliases=frozenset({path}) if path in _RULE_44_ALIAS_PATHS else None,
        )


def _rule_44_scan_loop(
    statement: ast.For | ast.AsyncFor | ast.While,
    environment: _Rule44Environment,
    module_environment: _Rule44Environment,
    enclosing_functions: tuple[_Rule44Scope, ...],
    scope_environment: _Rule44Environment,
    module_name: str,
    rel: str,
    violations: list[str],
    deferred: _Rule44DeferredBodies,
    intermediates: _Rule44Environment | None,
) -> None:
    """Scan a loop: its header runs once, its body and else merge."""
    if isinstance(statement, (ast.For, ast.AsyncFor)):
        _rule_44_scan_expression(statement.iter, environment, module_name, rel, violations)
        before = environment.copy()
        environment.discard_all(_bound_names(statement.target))
    else:
        _rule_44_scan_expression(statement.test, environment, module_name, rel, violations)
        before = environment.copy()
    body_environment = environment.copy()
    _rule_44_scan_block(
        statement.body,
        body_environment,
        module_environment,
        enclosing_functions,
        scope_environment,
        module_name,
        rel,
        violations,
        deferred,
        intermediates,
    )
    else_environment = environment.copy()
    _rule_44_scan_block(
        statement.orelse,
        else_environment,
        module_environment,
        enclosing_functions,
        scope_environment,
        module_name,
        rel,
        violations,
        deferred,
        intermediates,
    )
    environment.replace(before)
    environment.merge(body_environment)
    environment.merge(else_environment)


def _rule_44_scan_with(
    statement: ast.With | ast.AsyncWith,
    environment: _Rule44Environment,
    module_environment: _Rule44Environment,
    enclosing_functions: tuple[_Rule44Scope, ...],
    scope_environment: _Rule44Environment,
    module_name: str,
    rel: str,
    violations: list[str],
    deferred: _Rule44DeferredBodies,
    intermediates: _Rule44Environment | None,
) -> None:
    """Scan a with statement, whose body always runs and writes back."""
    for item in statement.items:
        _rule_44_scan_expression(item.context_expr, environment, module_name, rel, violations)
        if item.optional_vars is not None:
            environment.discard_all(_bound_names(item.optional_vars))
    _rule_44_scan_block(
        statement.body,
        environment,
        module_environment,
        enclosing_functions,
        scope_environment,
        module_name,
        rel,
        violations,
        deferred,
        intermediates,
    )


def _rule_44_scan_conditional(
    statement: ast.If,
    environment: _Rule44Environment,
    module_environment: _Rule44Environment,
    enclosing_functions: tuple[_Rule44Scope, ...],
    scope_environment: _Rule44Environment,
    module_name: str,
    rel: str,
    violations: list[str],
    deferred: _Rule44DeferredBodies,
    intermediates: _Rule44Environment | None,
) -> None:
    """Scan an if statement; its branches scan copies and merge."""
    _rule_44_scan_expression(statement.test, environment, module_name, rel, violations)
    body_environment = environment.copy()
    _rule_44_scan_block(
        statement.body,
        body_environment,
        module_environment,
        enclosing_functions,
        scope_environment,
        module_name,
        rel,
        violations,
        deferred,
        intermediates,
    )
    else_environment = environment.copy()
    _rule_44_scan_block(
        statement.orelse,
        else_environment,
        module_environment,
        enclosing_functions,
        scope_environment,
        module_name,
        rel,
        violations,
        deferred,
        intermediates,
    )
    environment.merge(body_environment)
    environment.merge(else_environment)


def _rule_44_scan_try(
    statement: ast.Try | ast.TryStar,
    environment: _Rule44Environment,
    module_environment: _Rule44Environment,
    enclosing_functions: tuple[_Rule44Scope, ...],
    scope_environment: _Rule44Environment,
    module_name: str,
    rel: str,
    violations: list[str],
    deferred: _Rule44DeferredBodies,
    intermediates: _Rule44Environment | None,
) -> None:
    """Scan a try: handlers see the body's intermediate states, finally all."""
    before = environment.copy()
    body_environment = environment.copy()
    body_points = _Rule44Environment()
    _rule_44_scan_block(
        statement.body,
        body_environment,
        module_environment,
        enclosing_functions,
        scope_environment,
        module_name,
        rel,
        violations,
        deferred,
        body_points,
    )
    exceptional = environment.copy()
    exceptional.merge(body_points)
    handler_environments: list[_Rule44Environment] = []
    handler_points_all = _Rule44Environment()
    for handler in statement.handlers:
        if handler.type is not None:
            _rule_44_scan_expression(handler.type, environment, module_name, rel, violations)
        handler_environment = exceptional.copy()
        if handler.name:
            handler_environment.discard(handler.name)
        handler_points = _Rule44Environment()
        _rule_44_scan_block(
            handler.body,
            handler_environment,
            module_environment,
            enclosing_functions,
            scope_environment,
            module_name,
            rel,
            violations,
            deferred,
            handler_points,
        )
        handler_environments.append(handler_environment)
        handler_points_all.merge(handler_environment)
        handler_points_all.merge(handler_points)
    else_environment = body_environment.copy()
    else_points = _Rule44Environment()
    _rule_44_scan_block(
        statement.orelse,
        else_environment,
        module_environment,
        enclosing_functions,
        scope_environment,
        module_name,
        rel,
        violations,
        deferred,
        else_points,
    )
    if statement.finalbody:
        # ``finally`` consumes every arrival — the try body, the
        # handlers, the else suite, and their intermediate points — and
        # its output supersedes them all.
        arrivals = before.copy()
        arrivals.merge(body_environment)
        arrivals.merge(body_points)
        arrivals.merge(else_environment)
        arrivals.merge(else_points)
        arrivals.merge(handler_points_all)
        finally_environment = arrivals.copy()
        finally_points = _Rule44Environment()
        _rule_44_scan_block(
            statement.finalbody,
            finally_environment,
            module_environment,
            enclosing_functions,
            scope_environment,
            module_name,
            rel,
            violations,
            deferred,
            finally_points,
            skip_first_intermediate=True,
        )
        environment.replace(finally_environment)
    else:
        arrivals = before.copy()
        arrivals.merge(body_environment)
        arrivals.merge(else_environment)
        for handler_environment in handler_environments:
            arrivals.merge(handler_environment)
        environment.replace(arrivals)
    if intermediates is not None:
        # An enclosing handler or finally observes only what this try's
        # transfer leaves: a nested ``finally``'s output, because it
        # consumes every arrival first, or the raw arrival states when
        # nothing consumes them.
        if statement.finalbody:
            intermediates.merge(finally_environment)
            # Exceptional exits the finally itself can take: its later
            # statement boundaries, never its arrived-at state.
            intermediates.merge(finally_points)
        else:
            intermediates.merge(body_points)
            intermediates.merge(else_points)
            intermediates.merge(handler_points_all)


def _rule_44_scan_match(
    statement: ast.Match,
    environment: _Rule44Environment,
    module_environment: _Rule44Environment,
    enclosing_functions: tuple[_Rule44Scope, ...],
    scope_environment: _Rule44Environment,
    module_name: str,
    rel: str,
    violations: list[str],
    deferred: _Rule44DeferredBodies,
    intermediates: _Rule44Environment | None,
) -> None:
    """Scan a match: captures shadow, and a case body's rebinds survive."""
    _rule_44_scan_expression(statement.subject, environment, module_name, rel, violations)
    merged = environment.copy()
    captures: set[str] = set()
    established: set[str] = set()
    for case in statement.cases:
        case_entry = environment.copy()
        case_captures = _rule_44_pattern_names(case.pattern)
        captures |= case_captures
        case_entry.discard_all(case_captures)
        case_environment = case_entry.copy()
        if case.guard is not None:
            _rule_44_scan_expression(case.guard, case_environment, module_name, rel, violations)
        _rule_44_scan_block(
            case.body,
            case_environment,
            module_environment,
            enclosing_functions,
            scope_environment,
            module_name,
            rel,
            violations,
            deferred,
            intermediates,
        )
        merged.merge(case_environment)
        # A capture shadows the name on its case's path; a name the
        # case's own body or guard rebinds (membership or an alias)
        # keeps its post-match state, while inherited provenance does
        # not survive a capture.
        established |= _rule_44_block_bindings(case.body)
        if case.guard is not None:
            established |= _rule_44_expression_bindings(case.guard)
    for name in captures - established:
        merged.discard(name)
    environment.replace(merged)
