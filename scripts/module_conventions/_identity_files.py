"""
Rule 28's private-facade discovery and its log-channel helper.

Implementation detail of :mod:`scripts.module_conventions.rules_identity`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast

from scripts.module_conventions.core import Module, _import_package_parts, _parse


def _facade_targets(module: Module) -> set[str]:
    """Private top-level modules imported by a public sibling (its facade)."""
    package = f"quickscale_modules_{module.name}"
    targets: set[str] = set()
    for entry, source in module.files.items():
        if entry.startswith("_") or not entry.endswith(".py") or "/" in entry:
            continue
        for node in ast.walk(_parse(source)):
            if isinstance(node, ast.ImportFrom):
                parts = _import_package_parts(node, module.name)
                if parts is None:
                    continue
                if len(parts) == 1:
                    targets.update(alias.name for alias in node.names if alias.name.startswith("_"))
                elif len(parts) == 2 and parts[1].startswith("_"):
                    targets.add(parts[1])
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if not alias.name.startswith(f"{package}."):
                        continue
                    rest = alias.name[len(package) + 1 :]
                    if "." not in rest and rest.startswith("_"):
                        targets.add(rest)
    return targets


def _module_named_logger_line(tree: ast.Module) -> int | None:
    """Return the line of the first ``getLogger(__name__)`` call, or ``None``."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        function = node.func
        if isinstance(function, ast.Attribute):
            call_name = function.attr
        elif isinstance(function, ast.Name):
            call_name = function.id
        else:
            continue
        if call_name != "getLogger":
            continue
        first = node.args[0]
        if isinstance(first, ast.Name) and first.id == "__name__":
            return node.lineno
    return None
