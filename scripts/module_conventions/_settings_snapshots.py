"""
Rule 42's settings-snapshot mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_settings`;
that module owns rule 42's orchestration and re-exports this module's names.
"""

from __future__ import annotations

import ast
import re

from scripts.module_conventions.core import (
    MODULE_IMPORT_PREFIX,
    Module,
    _declared_exports,
    _is_settings_receiver,
    _parse,
    _scope_nodes,
    _settings_bindings,
)


def _class_defines_from_settings(node: ast.ClassDef) -> bool:
    """Return whether a class declares the rule 42 ``from_settings()`` factory."""
    return any(
        isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "from_settings"
        for item in node.body
    )


_RULE_42_EXPORTED_SNAPSHOT = re.compile(r"SettingsSnapshot$")

_COERCION_BUILTINS = frozenset({"bool", "float", "int", "list", "str", "tuple"})


def _is_direct_setting_read(
    node: ast.expr,
    names: set[str],
    modules: set[tuple[str, ...]],
) -> bool:
    """Return whether an expression is a setting read, wrapped coercions included."""
    if isinstance(node, ast.Attribute):
        return _is_settings_receiver(node.value, names, modules)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _COERCION_BUILTINS
        and len(node.args) == 1
        and not node.keywords
    ):
        return _is_direct_setting_read(node.args[0], names, modules)
    return False


def _call_builds_settings_snapshot(
    call: ast.Call,
    names: set[str],
    modules: set[tuple[str, ...]],
) -> bool:
    """Return whether a call is a ``from_settings()`` factory or an all-settings constructor."""
    if isinstance(call.func, ast.Attribute) and call.func.attr == "from_settings":
        return True
    if isinstance(call.func, ast.Name) and call.func.id in _COERCION_BUILTINS:
        return False
    arguments = [*call.args, *(keyword.value for keyword in call.keywords)]
    return bool(arguments) and all(
        _is_direct_setting_read(argument, names, modules) for argument in arguments
    )


def _intra_module_import_names(tree: ast.Module, module: Module) -> dict[str, str]:
    """Map own-package import aliases to their original names (rule 42 resolution)."""
    names: dict[str, str] = {}
    prefix = f"{MODULE_IMPORT_PREFIX}{module.name}"
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        same_package = bool(node.level) or (
            node.module is not None
            and (node.module == prefix or node.module.startswith(f"{prefix}."))
        )
        if not same_package:
            continue
        for alias in node.names:
            names[alias.asname or alias.name] = alias.name
    return names


def _settings_snapshot_names(module: Module) -> set[str]:
    """Collect the snapshot names the module's private ``_settings.py`` builds."""
    text = module.files.get("_settings.py")
    if text is None:
        return set()
    tree = _parse(text)
    names, modules = _settings_bindings(tree)
    aliases = _intra_module_import_names(tree, module)
    found = {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef) and _class_defines_from_settings(node)
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _call_builds_settings_snapshot(
            node, names, modules
        ):
            continue
        if isinstance(node.func, ast.Name):
            found.add(aliases.get(node.func.id, node.func.id))
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr == "from_settings":
                if isinstance(node.func.value, ast.Name):
                    found.add(aliases.get(node.func.value.id, node.func.value.id))
            else:
                found.add(node.func.attr)
    return found


def _returns_settings_snapshot(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    names: set[str],
    modules: set[tuple[str, ...]],
) -> int | None:
    """Return the line of a return that builds a settings snapshot, if any."""
    for item in _scope_nodes(node):
        if (
            isinstance(item, ast.Return)
            and item.value is not None
            and isinstance(item.value, ast.Call)
            and _call_builds_settings_snapshot(item.value, names, modules)
        ):
            return item.lineno
    return None


def _snapshot_scan_violations(module: Module, rel: str, tree: ast.Module) -> list[str]:
    """Rule 42's clauses for one module file, in their pre-split order."""
    violations: list[str] = []
    in_settings_module = rel == "_settings.py"
    names, modules = _settings_bindings(tree)
    snapshot_names = _settings_snapshot_names(module)
    for node in tree.body:
        if (
            isinstance(node, ast.ClassDef)
            and not in_settings_module
            and (_class_defines_from_settings(node) or node.name in snapshot_names)
        ):
            violations.append(
                f"rule 42: {module.name}: {rel}:{node.lineno} defines the settings "
                f"snapshot {node.name} outside _settings.py"
            )
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not in_settings_module:
            returned_at = _returns_settings_snapshot(node, names, modules)
            if returned_at is not None:
                violations.append(
                    f"rule 42: {module.name}: {rel}:{returned_at} builds a settings "
                    "snapshot outside _settings.py"
                )
    for export in _declared_exports(tree) or ():
        resolved = _intra_module_import_names(tree, module).get(export, export)
        if resolved in snapshot_names or _RULE_42_EXPORTED_SNAPSHOT.search(resolved):
            violations.append(
                f"rule 42: {module.name}: {rel} exports the settings snapshot {resolved}"
            )
    return violations
