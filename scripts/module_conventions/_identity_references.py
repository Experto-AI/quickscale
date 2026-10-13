"""
Rule 34's by-name references to another module and its layer table.

Implementation detail of :mod:`scripts.module_conventions.rules_identity`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast

from scripts.module_conventions.core import (
    MODULE_LAYERS,
    Corpus,
    Module,
    _call_func_name,
    _cross_module_imports,
    _docstring_nodes,
    _parse,
    _same_layer_cycles,
)


def _name_reference_target(value: str) -> str | None:
    """Resolve an app label, model label, namespace, or package path to its module."""
    for module in sorted(MODULE_LAYERS, key=len, reverse=True):
        for stem in (f"quickscale_modules_{module}", f"quickscale_{module}"):
            if value == stem:
                return module
            if value.startswith(stem) and len(value) > len(stem) and value[len(stem)] in ".:_":
                return module
    return None


def _migration_model_reference_ids(tree: ast.Module) -> set[int]:
    """Return the nodes a migration may use to reach another module's models."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_func_name(node) == "get_model":
            for argument in node.args:
                if isinstance(argument, ast.Constant):
                    ids.add(id(argument))
            for keyword in node.keywords:
                if keyword.arg in {"app_label", "model_name"} and isinstance(
                    keyword.value, ast.Constant
                ):
                    ids.add(id(keyword.value))
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = list(node.targets) if isinstance(node, ast.Assign) else [node.target]
            if not any(
                isinstance(target, ast.Name) and target.id in {"dependencies", "run_before"}
                for target in targets
            ):
                continue
            if node.value is None:
                continue
            for child in ast.walk(node.value):
                if isinstance(child, ast.Constant):
                    ids.add(id(child))
    return ids


def _is_migration_model_path(value: str, target: str) -> bool:
    """Return True for a migration's historical model path or label (rule 5)."""
    package = f"quickscale_modules_{target}.models"
    label = f"quickscale_{target}"
    return value == package or value.startswith(f"{package}.") or value.startswith(f"{label}.")


def _name_reference_file_scan(
    module: Module,
    rel: str,
    tree: ast.Module,
    docstrings: set[int],
    model_ids: set[int],
    *,
    in_migrations: bool,
    layer: int,
) -> tuple[list[str], list[str], list[str]]:
    """Return one file's rule 34 violations and its same-layer edges."""
    violations: list[str] = []
    name_targets: list[str] = []
    import_targets: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        if id(node) in docstrings:
            continue
        target = _name_reference_target(node.value)
        if target is None or target == module.name:
            continue
        if in_migrations and (
            id(node) in model_ids or _is_migration_model_path(node.value, target)
        ):
            continue
        other_layer = MODULE_LAYERS.get(target)
        if other_layer is None:
            continue
        if other_layer > layer:
            violations.append(
                f"rule 34: {module.name}: {rel}:{node.lineno} references {target} "
                f"by name upward (layer {other_layer} above layer {layer})"
            )
        elif other_layer == layer:
            name_targets.append(target)
    for other, path, _names, _lineno, _kind in _cross_module_imports(tree):
        if other == module.name:
            continue
        if in_migrations and path[:1] == ("models",):
            continue
        if MODULE_LAYERS.get(other) == layer:
            import_targets.append(other)
    return violations, name_targets, import_targets


def rule_34_name_references(corpus: Corpus) -> list[str]:
    """
    Rule 34: references to another module by name obey the layer table.

    The statically checkable clauses over non-import references: app labels,
    package paths given to ``import_module``, model labels, URL namespaces,
    label prefixes, and ``apps.get_model`` / ``apps.is_installed`` /
    ``apps.get_app_config`` arguments.  Imports stay with rule 5; a migration's
    historical model lookups (``get_model`` arguments, ``dependencies`` /
    ``run_before`` entries, and ``.models`` paths or dotted model labels) are
    excepted there and here, while its other by-name references are checked.
    """
    violations: list[str] = []
    name_edges: set[tuple[str, str]] = set()
    edges: dict[str, set[str]] = {}
    for module in corpus.modules:
        layer = MODULE_LAYERS.get(module.name)
        if layer is None:
            continue
        for rel, text in module.files.items():
            if not rel.endswith(".py"):
                continue
            in_migrations = rel.startswith("migrations/")
            tree = _parse(text)
            docstrings = _docstring_nodes(tree)
            model_ids = _migration_model_reference_ids(tree) if in_migrations else set()
            file_violations, name_targets, import_targets = _name_reference_file_scan(
                module,
                rel,
                tree,
                docstrings,
                model_ids,
                in_migrations=in_migrations,
                layer=layer,
            )
            violations.extend(file_violations)
            for target in name_targets:
                name_edges.add((module.name, target))
            for other in import_targets:
                edges.setdefault(module.name, set()).add(other)
    for source, target in name_edges:
        edges.setdefault(source, set()).add(target)
    for cycle in _same_layer_cycles(edges):
        if any((a, b) in name_edges for a, b in zip(cycle, cycle[1:])):
            violations.append(f"rule 34: same-layer name-reference cycle: {' -> '.join(cycle)}")
    return violations
