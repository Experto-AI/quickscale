"""
``AppConfig.ready()`` registration-reachability mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_misc`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast

from scripts.module_conventions._misc_flow import _direct_calls
from scripts.module_conventions.core import _class_names


def _ready_scope_signature_calls(tree: ast.Module) -> tuple[bool, list[str]]:
    """
    Return whether registration is reachable and the calls' execution order.

    Registration must run from the AppConfig's own ``ready()`` scope; the
    same traversal follows one level of ``self.<method>`` and module-level
    functions, expanding each helper at the position its call executes so the
    returned call names match Python's execution order.
    """
    app_config = next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
            and any(
                base == "AppConfig" or base.endswith("AppConfig") for base in _class_names(node)
            )
        ),
        None,
    )
    if app_config is None:
        return False, []
    ready = next(
        (
            statement
            for statement in app_config.body
            if isinstance(statement, ast.FunctionDef) and statement.name == "ready"
        ),
        None,
    )
    if ready is None:
        return False, []
    methods: dict[str, ast.FunctionDef] = {
        statement.name: statement
        for statement in app_config.body
        if isinstance(statement, ast.FunctionDef)
    }
    module_functions: dict[str, ast.FunctionDef] = {
        statement.name: statement
        for statement in tree.body
        if isinstance(statement, ast.FunctionDef)
    }
    seen: set[int] = set()
    order: list[str] = []

    def expand(node: ast.FunctionDef) -> None:
        if id(node) in seen:
            return
        seen.add(id(node))
        for call in _direct_calls(node):
            if isinstance(call.func, ast.Name):
                called = call.func.id
                if called in {"register_module_checks", "register_module_settings_check"}:
                    order.append(called)
                if called in module_functions:
                    expand(module_functions[called])
            elif (
                isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "self"
                and call.func.attr in methods
            ):
                expand(methods[call.func.attr])

    expand(ready)
    return bool(order), order


def _registration_reachable(tree: ast.Module) -> bool:
    """Registration must run from the AppConfig's own ready() scope."""
    reachable, _order = _ready_scope_signature_calls(tree)
    return reachable


def _ready_registration_order(tree: ast.Module) -> list[str]:
    """Return the registration helper calls reachable from ready(), in order."""
    _reachable, order = _ready_scope_signature_calls(tree)
    return order
