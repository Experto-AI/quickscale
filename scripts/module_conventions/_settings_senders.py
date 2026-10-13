"""
Rule 43's optional-sender mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_settings`;
that module owns rule 43's orchestration and re-exports this module's names.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping

from scripts.module_conventions.core import (
    MODULE_LAYERS,
    Module,
    _attribute_chain,
    _body_nodes,
    _call_func_name,
    _keyword,
    _module_target,
    _scope_nodes,
)

_RULE_43_SETTINGS_ATTRIBUTE = re.compile(r"(?:Settings|Snapshot)")


def _import_module_service_bindings(tree: ast.Module) -> dict[str, str]:
    """Map locals assigned from ``import_module("<module>.services")`` to that module."""
    bindings: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        value = node.value
        if not isinstance(target, ast.Name) or not isinstance(value, ast.Call):
            continue
        func = value.func
        if not isinstance(func, ast.Name) or func.id != "import_module":
            continue
        if len(value.args) != 1 or not isinstance(value.args[0], ast.Constant):
            continue
        path = value.args[0].value
        if not isinstance(path, str):
            continue
        target_module = _module_target(tuple(path.split(".")))
        if target_module is not None and target_module[1] == ("services",):
            bindings[target.id] = target_module[0]
    return bindings


def _other_module_service_imports(tree: ast.Module, module_name: str) -> dict[str, str]:
    """Map names imported from another module's ``services`` to that module."""
    names: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module or node.level:
            continue
        target = _module_target(tuple(node.module.split(".")))
        if target is None or target[0] == module_name or target[1] != ("services",):
            continue
        for alias in node.names:
            names[alias.asname or alias.name] = target[0]
    return names


def _attribute_binding_module(
    chain: tuple[str, ...],
    service_bindings: dict[tuple[str, ...], str],
    import_module_bindings: dict[str, str],
) -> str | None:
    """Resolve the module an attribute chain is rooted in, if it is another module."""
    direct = _module_target(chain)
    if direct is not None:
        return direct[0]
    if (chain[0],) in service_bindings:
        return service_bindings[(chain[0],)]
    return import_module_bindings.get(chain[0])


def _call_other_module_service(
    call: ast.Call,
    service_names: dict[str, str],
    service_bindings: dict[tuple[str, ...], str],
    import_module_bindings: dict[str, str],
) -> tuple[str, str] | None:
    """Return the module and name a call targets through its ``services`` surface."""
    func = call.func
    if isinstance(func, ast.Name):
        owner = service_names.get(func.id)
        return (owner, func.id) if owner is not None else None
    if isinstance(func, ast.Attribute):
        chain = _attribute_chain(func)
        if chain is None:
            return None
        for prefix, binding_owner in sorted(
            service_bindings.items(), key=lambda item: len(item[0]), reverse=True
        ):
            if len(prefix) < len(chain) and chain[: len(prefix)] == prefix:
                return (binding_owner, func.attr)
        owner = import_module_bindings.get(chain[0])
        if owner is not None:
            return (owner, func.attr)
    return None


def _reference_module_name(value: str) -> str | None:
    """Resolve a package stem or app label to a module name."""
    target = _module_target(tuple(value.split(".")))
    if target is not None:
        return target[0]
    for name in MODULE_LAYERS:
        if value == f"quickscale_{name}":
            return name
    return None


def _guarded_module_name(node: ast.expr | None, constants: Mapping[str, str]) -> str | None:
    """Resolve the module an ``apps.is_installed`` argument names."""
    value: str | None = None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        value = node.value
    elif isinstance(node, ast.Name):
        value = constants.get(node.id)
    if value is None:
        return None
    return _reference_module_name(value)


def _getattr_service_owner(
    target: ast.expr,
    service_names: Mapping[str, str],
    service_bindings: Mapping[tuple[str, ...], str],
    import_module_bindings: Mapping[str, str],
) -> str | None:
    """Resolve the module whose services a ``getattr`` target is rooted in."""
    if isinstance(target, ast.Name):
        return (
            service_names.get(target.id)
            or service_bindings.get((target.id,))
            or import_module_bindings.get(target.id)
        )
    if isinstance(target, ast.Attribute):
        chain = _attribute_chain(target)
        if chain is None:
            return None
        return _attribute_binding_module(chain, service_bindings, import_module_bindings)
    return None


def _guard_call_violations(
    module: Module,
    rel: str,
    tree: ast.Module,
    required: set[str] | frozenset[str],
    service_names: Mapping[str, str],
    service_bindings: Mapping[tuple[str, ...], str],
    import_module_bindings: Mapping[str, str],
    constants: Mapping[str, str],
) -> list[str]:
    """Rule 43's call clauses: required guards and getattr-with-default service reads."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _call_func_name(node) == "is_installed":
            argument = node.args[0] if node.args else _keyword(node, "app_name")
            guarded = _guarded_module_name(argument, constants)
            if guarded is not None and guarded in required:
                violations.append(
                    f"rule 43: {module.name}: {rel}:{node.lineno} guards "
                    f"required module {guarded} with apps.is_installed"
                )
        elif _call_func_name(node) == "getattr" and len(node.args) >= 3:
            owner = _getattr_service_owner(
                node.args[0],
                service_names,
                service_bindings,
                import_module_bindings,
            )
            if owner is not None and owner != module.name:
                violations.append(
                    f"rule 43: {module.name}: {rel}:{node.lineno} reads "
                    f"{owner}'s service through getattr with a default"
                )
    return violations


def _cross_attribute_violations(
    module: Module,
    rel: str,
    tree: ast.Module,
    service_bindings: Mapping[tuple[str, ...], str],
    import_module_bindings: Mapping[str, str],
) -> list[str]:
    """Rule 43: another module's settings read through a cross-module attribute."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Attribute) and _RULE_43_SETTINGS_ATTRIBUTE.search(node.attr)):
            continue
        chain = _attribute_chain(node)
        if chain is None:
            continue
        owner = _attribute_binding_module(chain, service_bindings, import_module_bindings)
        if owner is not None and owner != module.name:
            violations.append(
                f"rule 43: {module.name}: {rel}:{node.lineno} reads {owner}'s "
                f"settings through {node.attr}"
            )
    return violations


def _broad_except_violations(
    module: Module,
    rel: str,
    tree: ast.Module,
    service_names: Mapping[str, str],
    service_bindings: Mapping[tuple[str, ...], str],
    import_module_bindings: Mapping[str, str],
    best_effort: frozenset[str],
) -> list[str]:
    """Rule 43: a broad ``except`` around another module's service call."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for item in _scope_nodes(node):
            if not isinstance(item, ast.Try):
                continue
            owner = next(
                (
                    found
                    for found in (
                        _call_other_module_service(
                            child,
                            service_names,
                            service_bindings,
                            import_module_bindings,
                        )
                        for child in _body_nodes(item.body)
                        if isinstance(child, ast.Call)
                    )
                    if found is not None and found[0] != module.name and found[0] not in best_effort
                ),
                None,
            )
            if owner is None:
                continue
            for handler in item.handlers:
                catches_everything = handler.type is None or (
                    isinstance(handler.type, ast.Name) and handler.type.id == "Exception"
                )
                if catches_everything:
                    violations.append(
                        f"rule 43: {module.name}: {rel}:{handler.lineno} catches "
                        f"Exception around {owner[0]}'s service call"
                    )
    return violations
