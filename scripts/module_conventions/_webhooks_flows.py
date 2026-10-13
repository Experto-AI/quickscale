"""
Rule 26's return-flow and overwrite mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_webhooks`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast


def _nested_bodies(statement: ast.stmt) -> list[list[ast.stmt]]:
    """Return every statement list directly nested in *statement*."""
    if isinstance(statement, ast.If):
        return [statement.body, statement.orelse]
    if isinstance(statement, (ast.With, ast.AsyncWith)):
        return [statement.body]
    if isinstance(statement, (ast.For, ast.While)):
        return [statement.body, statement.orelse]
    if isinstance(statement, ast.Try):
        return [
            statement.body,
            *(handler.body for handler in statement.handlers),
            statement.orelse,
            statement.finalbody,
        ]
    if isinstance(statement, ast.Match):
        return [case.body for case in statement.cases]
    return []


def _selected_branch(statement: ast.If) -> list[ast.stmt] | None:
    """Return the branch a statically-decided test selects, else None."""
    test = statement.test
    if isinstance(test, ast.Constant) and test.value is True:
        return statement.body
    if isinstance(test, ast.Constant) and test.value is False:
        return statement.orelse
    return None


def _is_rejection_value(value: ast.expr | None) -> bool:
    return value is None or (isinstance(value, ast.Constant) and value.value in {None, False})


def _may_return_non_rejection(statements: list[ast.stmt]) -> bool:
    """Return True when any route through these statements can return a value."""
    for statement in statements:
        if isinstance(statement, ast.Return) and not _is_rejection_value(statement.value):
            return True
        if any(_may_return_non_rejection(body) for body in _nested_bodies(statement)):
            return True
    return False


def _may_return_any(statements: list[ast.stmt]) -> bool:
    """Return True when any route through these statements returns a value."""
    for statement in statements:
        if isinstance(statement, ast.Return):
            return True
        if any(_may_return_any(body) for body in _nested_bodies(statement)):
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
            selected = _selected_branch(statement)
            if selected is not None:
                if _rejects_failure(selected):
                    return True
                if _may_return_non_rejection(selected):
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


def _rejects_by_raising(branch: list[ast.stmt]) -> bool:
    """Rejection must raise so a caller cannot ignore a returned sentinel."""
    for statement in branch:
        if isinstance(statement, ast.Raise):
            return True
        if isinstance(statement, ast.Return):
            return False
        if isinstance(statement, ast.If):
            selected = _selected_branch(statement)
            if selected is not None:
                if _rejects_by_raising(selected):
                    return True
                if _may_return_any(selected):
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
