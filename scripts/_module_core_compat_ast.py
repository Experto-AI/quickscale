"""
AST import extraction and symbol resolution for the SA267(d) split.

The static pass collects ``quickscale_core`` imports from module source and
resolves each referenced module path and symbol against the on-disk core
source, including ``__getattr__`` lazy-facade chains.  The facade imports these
names from this defining sibling, never through the facade (decisions.md,
Split-Facade Seams).  Behavior is unchanged from the pre-split module.
"""

from __future__ import annotations

import ast
from pathlib import Path


class _CoreImportVisitor(ast.NodeVisitor):
    """Collect all ``quickscale_core`` import references from an AST."""

    def __init__(self) -> None:
        super().__init__()
        # (target_path, imported_names) where imported_names may be None
        # for ``import quickscale_core.x`` (whole-module import)
        self.imports: list[tuple[str, list[str] | None]] = []

    def _is_quickscale_core(self, module: str | None) -> bool:
        if module is None:
            return False
        return module == "quickscale_core" or module.startswith("quickscale_core.")

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if self._is_quickscale_core(alias.name):
                # ``import quickscale_core.dr_engine.adapter``
                self.imports.append((alias.name, None))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if self._is_quickscale_core(node.module):
            names = [a.name for a in node.names]
            # ``from quickscale_core.x import y``
            assert node.module is not None  # guaranteed by the guard above
            self.imports.append((node.module, names))


def _collect_core_imports(source_dir: Path) -> dict[Path, list[tuple[str, list[str] | None]]]:
    """
    Collect quickscale_core imports from a module source tree.

    Walks ``source_dir`` for ``.py`` files and returns a mapping from file
    path to the list of ``(quickscale_core_path, imported_names_or_None)``
    tuples found in that file.
    """
    results: dict[Path, list[tuple[str, list[str] | None]]] = {}
    for py_file in sorted(source_dir.rglob("*.py")):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            # Skip files with syntax errors (unlikely in a healthy repo)
            continue
        visitor = _CoreImportVisitor()
        visitor.visit(tree)
        if visitor.imports:
            results[py_file] = visitor.imports
    return results


def _module_path_to_fs_path(
    core_src_root: Path,
    module_path: str,
) -> Path | None:
    """
    Convert a dotted module path to a filesystem path.

    E.g. ``quickscale_core.dr_engine.primitives`` →
    ``<core_src_root>/quickscale_core/dr_engine/primitives.py``.

    Returns ``None`` if the path does not exist on disk.
    """
    # quickscale_core.dr_engine.primitives → quickscale_core/dr_engine/primitives
    relative = module_path.replace(".", "/")
    # Try package/__init__.py first, then module.py
    as_init = core_src_root / relative / "__init__.py"
    if as_init.is_file():
        return as_init
    as_module = core_src_root / f"{relative}.py"
    if as_module.is_file():
        return as_module
    return None


def _add_assignment_targets(names: set[str], targets: list[ast.expr]) -> None:
    """Add the simple names bound by assignment targets to *names*."""
    for target in targets:
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, ast.Tuple):
            for elt in target.elts:
                if isinstance(elt, ast.Name):
                    names.add(elt.id)


def _collect_literal_names(tree: ast.AST) -> tuple[set[str], bool]:
    """Return the top-level bound names and whether ``__getattr__`` is defined."""
    names: set[str] = set()
    has_getattr: bool = False

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
            if node.name == "__getattr__":
                has_getattr = True
        elif isinstance(node, ast.Assign):
            _add_assignment_targets(names, node.targets)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                names.add(node.target.id)
        elif isinstance(node, ast.ImportFrom):
            names.update(a.name for a in node.names if a.asname is None)
            names.update(a.asname for a in node.names if a.asname is not None)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    names.add(alias.asname)
                else:
                    # ``import quickscale_core`` - the local name is the
                    # last component (or the whole thing for a top-level pkg)
                    local = alias.name.split(".")[0]
                    names.add(local)
    return names, has_getattr


def _collect_all_list(tree: ast.AST) -> set[str] | None:
    """Return the literal ``__all__`` string list, or ``None`` when absent."""
    all_list: set[str] | None = None
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, ast.List):
                        all_list = {
                            elt.value
                            for elt in node.value.elts
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                        }
    return all_list


def _collect_defined_names(py_file: Path) -> set[str]:
    """
    Return the set of public names defined at the top level of *py_file*.

    Considers:
    - Top-level ``FunctionDef``, ``AsyncFunctionDef``, ``ClassDef``
    - Top-level ``Assign`` targets that are simple ``Name`` nodes
    - Top-level ``AnnAssign`` targets that are simple ``Name`` nodes
    - Re-exported imports (e.g. ``from x import y``) at top level
    - ``__all__`` if it is a literal list of strings
    - ``__getattr__`` for lazy-loading modules (trusts ``__all__`` directly)
    """
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
    except SyntaxError:
        return set()

    names, has_getattr = _collect_literal_names(tree)
    all_list = _collect_all_list(tree)

    # If __all__ is present, the public surface is restricted to that list.
    # For modules with __getattr__ (lazy-loading facades), trust __all__
    # directly — lazy symbols are resolved at runtime and won't appear in
    # the literal names set (the __getattr__ body handles them).
    if all_list is not None:
        if has_getattr:
            return all_list  # __getattr__ resolves lazy symbols at runtime
        return all_list & names  # only names that are actually defined

    return names


def _collect_lazy_symbol_names(tree: ast.AST) -> set[str]:
    """
    Collect lazy symbol names from frozenset literals in ``__getattr__`` modules.

    Handles patterns like::

        _LAZY_ORCHESTRATION_SYMBOLS: frozenset[str] = frozenset({"a", "b"})
        _LAZY_PRIMITIVES_SYMBOLS = frozenset({"c", "d"})

    Returns the set of string literals found in all such assignments.
    """
    lazy_names: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        target: ast.expr | None = None
        value: ast.expr | None = None

        if isinstance(node, ast.Assign):
            if len(node.targets) == 1:
                target = node.targets[0]
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            value = node.value  # type: ignore[assignment]

        if target is None or value is None:
            continue
        if not isinstance(target, ast.Name):
            continue
        if not target.id.startswith("_LAZY_") or "_SYMBOLS" not in target.id:
            continue

        # Value should be frozenset({...}) or frozenset[...]({...})
        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == "frozenset"
            and value.args
        ):
            container = value.args[0]
            if isinstance(container, (ast.Set, ast.List, ast.Tuple)):
                for elt in container.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        lazy_names.add(elt.value)
    return lazy_names


def _collect_submodule_aliases(tree: ast.AST) -> dict[str, str]:
    """
    Collect sub-module aliases from import statements in a module.

    Handles::

        from quickscale_core.runtime import dr as _dr
        import quickscale_core.runtime.dr as _dr

    Returns a mapping: ``{alias_name: dotted_module_path}``.
    """
    aliases: dict[str, str] = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if alias.asname:
                    aliases[alias.asname] = f"{node.module}.{alias.name}"
                else:
                    aliases[alias.name] = f"{node.module}.{alias.name}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    aliases[alias.asname] = alias.name
                else:
                    aliases[alias.name] = alias.name
    return aliases


def _collect_getattr_dynamic_submodules(tree: ast.AST) -> set[str]:
    """
    Collect literal lazy-import edges reachable from ``__getattr__``.

    Supports a facade that delegates to a helper such as ``_load_dr()`` whose
    body returns ``importlib.import_module("quickscale_core.runtime.dr")``.
    Only the ``__getattr__`` body and directly called local helpers are scanned,
    so unrelated dynamic imports do not widen the facade's reported surface.
    """
    functions = {
        node.name: node
        for node in ast.iter_child_nodes(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    getattr_node = functions.get("__getattr__")
    if getattr_node is None:
        return set()

    scan_nodes: list[ast.AST] = [getattr_node]
    called_helpers = {
        call.func.id
        for call in ast.walk(getattr_node)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
    }
    scan_nodes.extend(functions[name] for name in called_helpers if name in functions)

    module_paths: set[str] = set()
    for scan_node in scan_nodes:
        for call in ast.walk(scan_node):
            if not isinstance(call, ast.Call) or not call.args:
                continue
            if not (
                isinstance(call.func, ast.Attribute)
                and call.func.attr == "import_module"
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "importlib"
            ):
                continue
            module_arg = call.args[0]
            if (
                isinstance(module_arg, ast.Constant)
                and isinstance(module_arg.value, str)
                and module_arg.value.startswith("quickscale_core.")
            ):
                module_paths.add(module_arg.value)
    return module_paths


def _resolve_name_via_getattr_chain(
    name: str,
    target_file: Path,
    core_src_root: Path,
    *,
    _visited: set[Path] | None = None,
) -> bool:
    """
    Try to resolve *name* through ``__getattr__`` or direct eager imports.

    Checks:
    1. Whether the module defines ``__getattr__``.
    2. Lazy frozenset literal assignments (``_LAZY_*_SYMBOLS``).
    3. Direct-level eager imports that define *name* as a module-level
       attribute but may not appear in ``__all__``.
    4. Sub-module aliases (``from X import Y as _alias``), recursively.

    Guards against cycles via ``_visited``.
    """
    if _visited is None:
        _visited = set()
    if target_file in _visited:
        return False
    _visited.add(target_file)

    try:
        tree = ast.parse(target_file.read_text(encoding="utf-8"))
    except SyntaxError:
        return False

    # Collect all names defined in this module (from imports, defs, etc.)
    full_names = _collect_defined_names_internal(tree)

    # Check if __getattr__ is defined
    has_getattr = any(
        isinstance(node, ast.FunctionDef) and node.name == "__getattr__"
        for node in ast.iter_child_nodes(tree)
    )
    if has_getattr:
        # Check lazy frozenset literals (pre-existing lazy facade pattern)
        if name in _collect_lazy_symbol_names(tree):
            return True
    else:
        # Without __getattr__, check direct eager imports that define *name*
        # as a module-level attribute but may not be in __all__ ∩ names.
        if name in full_names:
            return True

    # Check sub-module aliases recursively
    for _alias_name, alias_module in _collect_submodule_aliases(tree).items():
        sub_path = _module_path_to_fs_path(core_src_root, alias_module)
        if sub_path and sub_path.is_file():
            # Check sub-module's defined names first
            sub_defined = _collect_defined_names(sub_path)
            if name in sub_defined:
                return True
            # Chase sub-module's __getattr__ chain
            if _resolve_name_via_getattr_chain(name, sub_path, core_src_root, _visited=_visited):
                return True

    # Follow literal importlib edges used by lazy facade helpers reached from
    # __getattr__. This preserves static compatibility checks without forcing
    # the production facade to import heavyweight sub-modules eagerly.
    for dynamic_module in _collect_getattr_dynamic_submodules(tree):
        sub_path = _module_path_to_fs_path(core_src_root, dynamic_module)
        if sub_path and sub_path.is_file():
            sub_defined = _collect_defined_names(sub_path)
            if name in sub_defined:
                return True
            if _resolve_name_via_getattr_chain(name, sub_path, core_src_root, _visited=_visited):
                return True

    return False


def _collect_defined_names_internal(tree: ast.AST) -> set[str]:
    """
    Collect all names assigned or imported in a module, including private.

    This is a subset of ``_collect_defined_names`` that returns the raw
    ``names`` set without filtering through ``__all__``.
    """
    names: set[str] = set()

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
                elif isinstance(target, ast.Tuple):
                    for elt in target.elts:
                        if isinstance(elt, ast.Name):
                            names.add(elt.id)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                names.add(node.target.id)
        elif isinstance(node, ast.ImportFrom):
            names.update(a.name for a in node.names if a.asname is None)
            names.update(a.asname for a in node.names if a.asname is not None)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    names.add(alias.asname)
                else:
                    local = alias.name.split(".")[0]
                    names.add(local)

    return names


def _resolve_import(
    core_src_root: Path,
    module_path: str,
    imported_names: list[str] | None,
) -> list[str]:
    """
    Resolve one collected import against the on-disk core source.

    Returns a list of human-readable issues (empty = compatible).

    *module_path* is the dotted import path (e.g.
    ``quickscale_core.dr_engine.primitives``).

    *imported_names* is ``None`` for ``import quickscale_core.x`` (whole-module
    import) or a list of symbol names for ``from quickscale_core.x import y``.
    """
    issues: list[str] = []

    target_file = _module_path_to_fs_path(core_src_root, module_path)
    if target_file is None:
        issues.append(f"  Module path does not exist: {module_path} (looked under {core_src_root})")
        return issues

    if imported_names is None:
        # ``import quickscale_core.x`` — just the module path itself needs
        # to exist, which we already confirmed.
        return issues

    defined = _collect_defined_names(target_file)
    for name in imported_names:
        if name == "*":
            # Star import — check __all__ if available
            if not defined:
                issues.append(
                    f"  Star import from {module_path}: target has no __all__ "
                    f"defined and no public names detected; requires manual review."
                )
            continue
        if name not in defined:
            # Fallback: the module may use __getattr__ to re-export symbols
            # from frozenset-based lazy tables or sub-module aliases.
            if _resolve_name_via_getattr_chain(name, target_file, core_src_root):
                continue
            issues.append(f"  Symbol {name!r} not found in {module_path}.")

    return issues
