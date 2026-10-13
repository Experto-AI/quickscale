"""
Rule 23's service-surface mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_package`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast

from scripts.module_conventions.core import (
    Module,
    _attribute_chain,
    _cross_module_imports,
    _declared_exports,
    _parse,
    _service_module_bindings,
)


def _service_functions(
    module: Module, tree: ast.Module
) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    """Resolve exported service functions, following intra-package re-exports."""
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    prefix = f"quickscale_modules_{module.name}."
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if node.level:
            source = f"{node.module.replace('.', '/')}.py"
        elif node.module.startswith(prefix):
            source = f"{node.module[len(prefix) :].replace('.', '/')}.py"
        else:
            continue
        if source == "services.py":
            continue
        text = module.files.get(source)
        if text is None:
            continue
        sibling = _parse(text)
        definitions = {
            child.name: child
            for child in sibling.body
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for alias in node.names:
            local = alias.asname or alias.name
            if local not in functions and alias.name in definitions:
                functions[local] = definitions[alias.name]
    return functions


def _module_bindings(tree: ast.Module) -> set[str]:
    """Names bound at module level: definitions, assignments, and imports."""
    bound: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bound.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            bound.add(node.target.id)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bound.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                bound.add(alias.asname or alias.name)
    return bound


def _service_declarations(module: Module) -> tuple[list[str], set[str] | None]:
    """Return one module's declarations findings and its declared exports."""
    services = module.files.get("services.py")
    if services is None:
        return [f"rule 23: {module.name}: services.py is missing"], None
    tree = _parse(services)
    declared = _declared_exports(tree)
    if declared is None:
        return [f"rule 23: {module.name}: services.py declares no __all__"], None
    violations: list[str] = []
    bound = _module_bindings(tree)
    functions = _service_functions(module, tree)
    for name in declared:
        if name not in bound:
            violations.append(f"rule 23: {module.name}: service {name!r} in __all__ is not defined")
            continue
        function = functions.get(name)
        if function is None:
            continue
        positional = len(function.args.posonlyargs) + len(function.args.args)
        if positional > 1 or function.args.vararg is not None:
            violations.append(
                f"rule 23: {module.name}: {name} takes {positional} positional "
                "parameter(s); services take keyword-only parameters after at most "
                "one subject"
            )
    return violations, set(declared)


def _import_export_findings(
    module: Module, rel: str, tree: ast.Module, exports: dict[str, set[str]]
) -> list[str]:
    """Return imports that name a symbol outside a provider's services.__all__."""
    violations: list[str] = []
    for other, path, names, lineno, kind in _cross_module_imports(tree):
        if other == module.name or kind != "from" or path[:1] != ("services",):
            continue
        other_exports = exports.get(other)
        if other_exports is None:
            continue
        for name in names:
            if name not in other_exports:
                violations.append(
                    f"rule 23: {module.name}: {rel}:{lineno} imports {name!r} "
                    f"outside {other}'s services.__all__"
                )
    return violations


def _member_access_findings(
    module: Module, rel: str, tree: ast.Module, exports: dict[str, set[str]]
) -> list[str]:
    """Return module-member reads outside a provider's services.__all__."""
    violations: list[str] = []
    for prefix, provider in _service_module_bindings(tree).items():
        provider_exports = exports.get(provider)
        if provider == module.name or provider_exports is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute):
                continue
            chain = _attribute_chain(node)
            if chain is None or len(chain) != len(prefix) + 1:
                continue
            member = chain[-1]
            if chain[: len(prefix)] != prefix or member in provider_exports:
                continue
            if member.startswith("__"):
                continue
            violations.append(
                f"rule 23: {module.name}: {rel}:{node.lineno} uses "
                f"{provider}.services.{member} outside services.__all__"
            )
    return violations


def _service_usage_findings(
    module: Module, rel: str, tree: ast.Module, exports: dict[str, set[str]]
) -> list[str]:
    """Return one file's cross-module service-usage findings, in report order."""
    violations = _import_export_findings(module, rel, tree, exports)
    violations.extend(_member_access_findings(module, rel, tree, exports))
    return violations
