"""
Rule 26's per-view webhook checks.

Implementation detail of :mod:`scripts.module_conventions.rules_webhooks`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping

from scripts.module_conventions._webhooks_services import (
    _executed_service_calls,
    _request_header_argument,
    _service_call_target,
    _service_verifies_signature,
)
from scripts.module_conventions.core import (
    Module,
    _class_names,
    _keyword,
    _parse,
)


def _view_class(tree: ast.Module, view_name: str) -> ast.ClassDef | None:
    """Return the top-level class *view_name* defines, else None."""
    return next(
        (
            candidate
            for candidate in tree.body
            if isinstance(candidate, ast.ClassDef) and candidate.name == view_name
        ),
        None,
    )


def _service_imports(tree: ast.Module) -> tuple[dict[str, str], set[str]]:
    """Return the services.py function bindings and ``services`` module aliases."""
    bindings: dict[str, str] = {}
    module_names: set[str] = set()
    for statement in tree.body:
        if not isinstance(statement, ast.ImportFrom):
            continue
        if (statement.module or "").endswith(".services"):
            for alias in statement.names:
                bindings[alias.asname or alias.name] = alias.name
        for alias in statement.names:
            if alias.name == "services":
                module_names.add(alias.asname or alias.name)
    return bindings, module_names


def _declares_empty_list(node: ast.ClassDef, attribute: str) -> bool:
    """Return True when the class assigns an empty list literal to *attribute*."""
    for statement in node.body:
        if not isinstance(statement, ast.Assign):
            continue
        for target in statement.targets:
            if (
                isinstance(target, ast.Name)
                and target.id == attribute
                and isinstance(statement.value, ast.List)
                and not statement.value.elts
            ):
                return True
    return False


def _empty_guard_violations(module_name: str, view_name: str, node: ast.ClassDef) -> list[str]:
    """Return rule 26's missing empty guard-list violations, in attribute order."""
    return [
        f"rule 26: {module_name}: {view_name} does not declare empty {attribute}"
        for attribute in ("authentication_classes", "permission_classes", "throttle_classes")
        if not _declares_empty_list(node, attribute)
    ]


def _post_method(node: ast.ClassDef) -> ast.FunctionDef | None:
    """Return the class's top-level post() method, else None."""
    return next(
        (
            method
            for method in node.body
            if isinstance(method, ast.FunctionDef) and method.name == "post"
        ),
        None,
    )


def _service_call_flow_violations(
    module_name: str,
    view_name: str,
    post: ast.FunctionDef,
    service_bindings: Mapping[str, str],
    services_module_names: set[str],
    services_source: str,
) -> list[str]:
    """Return rule 26's body, signature, and verification violations for post()."""
    violations: list[str] = []
    service_calls = _executed_service_calls(
        list(post.body),
        lambda call: (
            _service_call_target(call, service_bindings, services_module_names) is not None
        ),
    )
    if not service_calls:
        return [f"rule 26: {module_name}: {view_name} does not call a services.py function"]
    for call in service_calls:
        body = _keyword(call, "body")
        if not (isinstance(body, ast.Attribute) and body.attr == "body"):
            violations.append(
                f"rule 26: {module_name}: {view_name} does not pass request.body to a service"
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
                f"rule 26: {module_name}: {view_name} does not take the signature "
                "from request headers"
            )
        target = _service_call_target(call, service_bindings, services_module_names)
        if target is not None and not _service_verifies_signature(services_source, target, call):
            violations.append(
                f"rule 26: {module_name}: {view_name} calls {target}, which does not "
                "verify a signature"
            )
    return violations


def _view_violations(module: Module, view_name: str) -> list[str]:
    """Return rule 26's violations for one webhook view name, in finding order."""
    views = module.files.get("views.py", "")
    if not views:
        return [f"rule 26: {module.name}: webhook view {view_name} not found"]
    tree = _parse(views)
    node = _view_class(tree, view_name)
    if node is None:
        return [f"rule 26: {module.name}: webhook view {view_name} not found"]
    violations: list[str] = []
    if not any(base == "APIView" or base.endswith("APIView") for base in _class_names(node)):
        violations.append(f"rule 26: {module.name}: {view_name} is not a DRF APIView")
    service_bindings, services_module_names = _service_imports(tree)
    violations.extend(_empty_guard_violations(module.name, view_name, node))
    post = _post_method(node)
    if post is None:
        violations.append(f"rule 26: {module.name}: {view_name} defines no post()")
        return violations
    services_source = module.files.get("services.py", "")
    violations.extend(
        _service_call_flow_violations(
            module.name, view_name, post, service_bindings, services_module_names, services_source
        )
    )
    return violations
