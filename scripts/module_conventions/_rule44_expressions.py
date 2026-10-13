"""
Rule 44's expression scanner.

Implementation detail of :mod:`scripts.module_conventions.rule_44`; that
module re-exports every name defined here, so existing import paths keep
working.  The pre-split walk is decomposed into per-shape helpers so every
function stays under the harness quality thresholds.
"""

from __future__ import annotations

import ast

from scripts.module_conventions._rule44_names import (
    RULE_44_QUERY_METHODS,
    _Rule44Environment,
    _rule_44_argument_names,
    _rule_44_membership_receiver,
)
from scripts.module_conventions.core import (
    _bound_names,
    _keyword,
)


def _rule_44_call_violation(
    call: ast.Call,
    environment: _Rule44Environment,
    module_name: str,
    rel: str,
) -> str | None:
    """Return the violation for one prohibited call, if it is one."""
    func = call.func
    if not isinstance(func, ast.Attribute) or func.attr not in RULE_44_QUERY_METHODS:
        return None
    role = _keyword(call, "role")
    if not (isinstance(role, ast.Constant) and isinstance(role.value, str)):
        return None
    if not _rule_44_membership_receiver(func.value, environment):
        return None
    return (
        f"rule 44: {module_name}: {rel}:{call.lineno} filters "
        f"OrganizationMembership by string role {role.value!r} outside orgs"
    )


def _rule_44_scan_expression(
    node: ast.expr,
    environment: _Rule44Environment,
    module_name: str,
    rel: str,
    violations: list[str],
    walrus_environment: _Rule44Environment | None = None,
    conditional: bool = False,
    short_circuited: bool = False,
) -> None:
    """
    Scan one expression against the current binding environment.

    Comprehensions and lambdas open their own scope, a walrus binds in the
    enclosing scope, and iteration targets shadow only inside their
    comprehension, so the environment shadows names as Python resolves them.
    A walrus inside a comprehension runs only while the comprehension
    iterates — a later generator only while the earlier ones do — so
    ``conditional`` keeps the pre-state a zero-iteration run retains; a
    walrus on a short-circuit arm (And/Or operand after the first, either
    branch of a conditional expression) may not run at all, so
    ``short_circuited`` keeps the executing scope's alternatives too.
    """
    if walrus_environment is None:
        walrus_environment = environment
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
        _rule_44_scan_comprehension(
            node,
            environment,
            module_name,
            rel,
            violations,
            walrus_environment,
            conditional,
            short_circuited,
        )
        return
    if isinstance(node, ast.Lambda):
        _rule_44_scan_lambda(
            node,
            environment,
            module_name,
            rel,
            violations,
            conditional,
            short_circuited,
        )
        return
    if isinstance(node, ast.BoolOp):
        _rule_44_scan_bool_op(
            node,
            environment,
            module_name,
            rel,
            violations,
            walrus_environment,
            conditional,
            short_circuited,
        )
        return
    if isinstance(node, ast.IfExp):
        _rule_44_scan_if_expression(
            node,
            environment,
            module_name,
            rel,
            violations,
            walrus_environment,
            conditional,
            short_circuited,
        )
        return
    if isinstance(node, ast.NamedExpr):
        _rule_44_scan_walrus(
            node,
            environment,
            module_name,
            rel,
            violations,
            walrus_environment,
            conditional,
            short_circuited,
        )
        return
    if isinstance(node, ast.Call):
        violation = _rule_44_call_violation(node, environment, module_name, rel)
        if violation is not None:
            violations.append(violation)
    _rule_44_scan_expression_children(
        node,
        environment,
        module_name,
        rel,
        violations,
        walrus_environment,
        conditional,
        short_circuited,
    )


def _rule_44_scan_comprehension(
    node: ast.ListComp | ast.SetComp | ast.GeneratorExp | ast.DictComp,
    environment: _Rule44Environment,
    module_name: str,
    rel: str,
    violations: list[str],
    walrus_environment: _Rule44Environment,
    conditional: bool,
    short_circuited: bool,
) -> None:
    """Scan one comprehension's generators, conditions, and element."""
    nested = environment.copy()
    for index, generator in enumerate(node.generators):
        _rule_44_scan_expression(
            generator.iter,
            nested,
            module_name,
            rel,
            violations,
            walrus_environment,
            conditional=conditional or index > 0,
            short_circuited=short_circuited,
        )
        nested.discard_all(_bound_names(generator.target))
        for condition in generator.ifs:
            _rule_44_scan_expression(
                condition,
                nested,
                module_name,
                rel,
                violations,
                walrus_environment,
                conditional=True,
                short_circuited=short_circuited,
            )
    if isinstance(node, ast.DictComp):
        _rule_44_scan_expression(
            node.key,
            nested,
            module_name,
            rel,
            violations,
            walrus_environment,
            conditional=True,
            short_circuited=short_circuited,
        )
        _rule_44_scan_expression(
            node.value,
            nested,
            module_name,
            rel,
            violations,
            walrus_environment,
            conditional=True,
            short_circuited=short_circuited,
        )
        return
    _rule_44_scan_expression(
        node.elt,
        nested,
        module_name,
        rel,
        violations,
        walrus_environment,
        conditional=True,
        short_circuited=short_circuited,
    )


def _rule_44_scan_lambda(
    node: ast.Lambda,
    environment: _Rule44Environment,
    module_name: str,
    rel: str,
    violations: list[str],
    conditional: bool,
    short_circuited: bool,
) -> None:
    """Scan a lambda's default expressions and its own-scope body."""
    for default in [
        *node.args.defaults,
        *(value for value in node.args.kw_defaults if value is not None),
    ]:
        _rule_44_scan_expression(
            default,
            environment,
            module_name,
            rel,
            violations,
            conditional=conditional,
            short_circuited=short_circuited,
        )
    nested = environment.copy()
    nested.discard_all(_rule_44_argument_names(node.args))
    _rule_44_scan_expression(
        node.body,
        nested,
        module_name,
        rel,
        violations,
        conditional=conditional,
        short_circuited=short_circuited,
    )


def _rule_44_scan_bool_op(
    node: ast.BoolOp,
    environment: _Rule44Environment,
    module_name: str,
    rel: str,
    violations: list[str],
    walrus_environment: _Rule44Environment,
    conditional: bool,
    short_circuited: bool,
) -> None:
    """Scan each operand; every operand after the first may be skipped."""
    for index, operand in enumerate(node.values):
        _rule_44_scan_expression(
            operand,
            environment,
            module_name,
            rel,
            violations,
            walrus_environment,
            conditional=conditional,
            short_circuited=short_circuited or index > 0,
        )


def _rule_44_scan_if_expression(
    node: ast.IfExp,
    environment: _Rule44Environment,
    module_name: str,
    rel: str,
    violations: list[str],
    walrus_environment: _Rule44Environment,
    conditional: bool,
    short_circuited: bool,
) -> None:
    """Scan a conditional expression; either branch may be skipped."""
    _rule_44_scan_expression(
        node.test,
        environment,
        module_name,
        rel,
        violations,
        walrus_environment,
        conditional=conditional,
        short_circuited=short_circuited,
    )
    for branch in (node.body, node.orelse):
        _rule_44_scan_expression(
            branch,
            environment,
            module_name,
            rel,
            violations,
            walrus_environment,
            conditional=conditional,
            short_circuited=True,
        )


def _rule_44_scan_walrus(
    node: ast.NamedExpr,
    environment: _Rule44Environment,
    module_name: str,
    rel: str,
    violations: list[str],
    walrus_environment: _Rule44Environment,
    conditional: bool,
    short_circuited: bool,
) -> None:
    """Scan a walrus value and record where its binding may take effect."""
    _rule_44_scan_expression(
        node.value,
        environment,
        module_name,
        rel,
        violations,
        walrus_environment,
        conditional=conditional,
        short_circuited=short_circuited,
    )
    membership = _rule_44_membership_receiver(node.value, environment)
    # The executing scope takes the binding as far as the walrus
    # definitely runs; a short-circuit arm may skip it, so its
    # alternatives stay.  The enclosing scope keeps the binding only
    # when the walrus runs unconditionally overall, because a
    # zero-iteration comprehension leaves the pre-state in place.
    if membership:
        environment.names.add(node.target.id)
        environment.aliases.pop(node.target.id, None)
    elif not short_circuited:
        environment.discard(node.target.id)
    if walrus_environment is not environment:
        if membership:
            walrus_environment.names.add(node.target.id)
            walrus_environment.aliases.pop(node.target.id, None)
        elif not (conditional or short_circuited):
            walrus_environment.discard(node.target.id)


def _rule_44_scan_expression_children(
    node: ast.expr,
    environment: _Rule44Environment,
    module_name: str,
    rel: str,
    violations: list[str],
    walrus_environment: _Rule44Environment,
    conditional: bool,
    short_circuited: bool,
) -> None:
    """Scan a node's expression and keyword children in place."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.expr):
            _rule_44_scan_expression(
                child,
                environment,
                module_name,
                rel,
                violations,
                walrus_environment,
                conditional=conditional,
                short_circuited=short_circuited,
            )
        elif isinstance(child, ast.keyword):
            _rule_44_scan_expression(
                child.value,
                environment,
                module_name,
                rel,
                violations,
                walrus_environment,
                conditional=conditional,
                short_circuited=short_circuited,
            )


def _rule_44_bind(
    targets: list[ast.expr],
    value: ast.expr,
    environment: _Rule44Environment,
) -> None:
    """Bind assignment targets to membership provenance or shadow them."""
    membership = _rule_44_membership_receiver(value, environment)
    for target in targets:
        for name in _bound_names(target):
            environment.bind(name, membership=membership)
