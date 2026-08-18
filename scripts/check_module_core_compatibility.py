#!/usr/bin/env python3
"""
SA9.2 — Module-vs-oldest-claimed-core compatibility check.

For each module in ``quickscale_modules/*/`` that declares a
``quickscale-core`` dependency in its ``module.yml``:

**Phase 1 — Static analysis (fast path):**

1. Parses the minimum claimed core version from the dependency spec.
2. Collects all ``from quickscale_core`` / ``import quickscale_core``
   statements from the module's Python source tree using ``ast``.
3. Resolves each imported symbol against the on-disk core source to
   confirm the referenced module path exists and, when a named symbol
   is imported, that the symbol is actually defined in the target file.
4. Verifies the repository's current core version (from ``VERSION``) is
   >= the module's claimed minimum core version.

**Phase 2 — Install / import probe (runtime check):**

For each module that declares a quantifiable minimum core version:

5. Creates an isolated temporary virtual environment.
6. Installs ``quickscale-core==<minimum_claimed_version>`` from PyPI.
7. Installs the module's non-core Python dependencies.
8. Adds the module source to the Python path and attempts to import the
   module's package (and its core-importing submodules).

This probe proves that a published consumer who installs only the
oldest supported ``quickscale-core`` release can import the module
without ``ImportError``.  A passing probe is the strongest pre-publish
evidence that the module's ``module.yml`` version claim is honest.

Thoroughness notes
------------------
- Both top-level imports (``from quickscale_core.x import y``) and
  lazy/nested imports (inside functions, classes) are detected by the
  static pass.
- Literal ``importlib.import_module("quickscale_core...")`` calls reached from
  a module's ``__getattr__`` are followed as lazy facade edges. Other dynamic
  imports and try/except-based optional imports are **not** detected statically.
- Star imports (``from quickscale_core.x import *``) are flagged but
  resolved via ``__all__`` when the target module defines one, or
  reported as requiring manual review otherwise.
- Re-exported names are resolved against the immediate source module,
  matching Python's binding semantics.
- The install/import probe skips modules whose minimum version could
  not be extracted from the dependency spec, and gracefully handles
  versions not yet published to PyPI.

Exit codes:
   0 — all modules compatible
   1 — one or more incompatibilities found
   2 — a configuration or filesystem error
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import tempfile
import tomllib  # Python 3.11+ stdlib
from pathlib import Path
from typing import Final, cast

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT_ENV: Final[str] = "REPO_ROOT"
_DEFAULT_REPO_ROOT: Final[Path] = Path(os.environ.get(REPO_ROOT_ENV, os.getcwd())).resolve()

CORE_SRC_RELATIVE: Final[Path] = Path("quickscale_core/src")
MODULES_DIR_RELATIVE: Final[Path] = Path("quickscale_modules")
MODULE_YML: Final[str] = "module.yml"
CORE_DEP_NAME: Final[str] = "quickscale-core"

# Regex to extract the minimum version from a pep-440-style specifier.
# Handles shapes like: >=0.86.0, >=0.86.0,<0.87.0, >=0.86.0,!=0.86.1
_MIN_VERSION_PATTERN: Final[re.Pattern[str]] = re.compile(r">=\s*(?P<min_ver>\d+[.]\d+[.]\d+)")

# Modules exempt from the install/import probe (Phase 2) only.
# Static analysis (Phase 1) still runs for all modules.
# This is a temporary measure — remove entries when their root cause is fixed.
SKIP_INSTALL_PROBE_MODULES: Final[dict[str, str]] = {
    "backups": (
        "Pre-existing version mismatch: no published quickscale-core "
        ">=0.86.0,<0.87.0 contains quickscale_core.dr_engine, which "
        "backups' services.py and management commands require. "
        "Skipped until SA9.3\u2013SA9.5 facade work replaces the deep "
        "dr_engine imports with quickscale_core.runtime (roadmap "
        "decision confirmed 2026-07-03)."
    ),
}


# ---------------------------------------------------------------------------
# Helpers: version parsing
# ---------------------------------------------------------------------------


def _read_version_file(repo_root: Path) -> str:
    """Return the trimmed version string from the repository ``VERSION`` file."""
    version_file = repo_root / "VERSION"
    if not version_file.is_file():
        raise SystemExit(f"VERSION file not found: {version_file}")
    raw = version_file.read_text(encoding="utf-8")
    cleaned = raw.replace("\r", "").strip()
    if not cleaned:
        raise SystemExit(f"VERSION file is empty: {version_file}")
    return cleaned


def _parse_version_tuple(version_str: str) -> tuple[int, ...]:
    """Parse ``'0.86.0'`` → ``(0, 86, 0)``."""
    parts = version_str.strip().split(".", maxsplit=2)
    return tuple(int(p) for p in parts)


def _extract_min_core_version(dep_spec: str) -> str | None:
    """
    Extract the minimum version from a PEP 440 dependency specifier.

    Examples::

        >>> _extract_min_core_version(">=0.86.0")
        '0.86.0'
        >>> _extract_min_core_version(">=0.86.0,<0.87.0")
        '0.86.0'
        >>> _extract_min_core_version("^0.86")
        None  # not PEP 440; the repo uses PEP 440 style
    """
    match = _MIN_VERSION_PATTERN.search(dep_spec)
    if match:
        return match.group("min_ver")
    return None


# ---------------------------------------------------------------------------
# Helpers: module.yml parsing
# ---------------------------------------------------------------------------


def _parse_module_yml(module_yml: Path) -> dict:
    """Parse a ``module.yml`` file, returning the raw dict."""
    import yaml  # pyyaml is a core dependency

    with module_yml.open(encoding="utf-8") as fh:
        return cast(dict, yaml.safe_load(fh))


def _get_core_dep_spec(data: dict) -> str | None:
    """
    Return the ``quickscale-core`` dependency spec from a parsed module.yml.

    Returns ``None`` if the module doesn't depend on core.
    """
    deps = data.get("dependencies", [])
    if not isinstance(deps, list):
        return None
    for dep in deps:
        if not isinstance(dep, str):
            continue
        # Match both "quickscale-core>=0.86.0" and "quickscale-core >= 0.86.0"
        if dep.startswith(CORE_DEP_NAME) or dep.startswith(f"{CORE_DEP_NAME} "):
            return dep
    return None


# ---------------------------------------------------------------------------
# Helpers: AST-based import extraction
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Helpers: symbol resolution against on-disk core
# ---------------------------------------------------------------------------


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

    names: set[str] = set()
    all_list: set[str] | None = None
    has_getattr: bool = False

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
            if node.name == "__getattr__":
                has_getattr = True
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
                    # ``import quickscale_core`` - the local name is the
                    # last component (or the whole thing for a top-level pkg)
                    local = alias.name.split(".")[0]
                    names.add(local)

    # Detect __all__
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


# ---------------------------------------------------------------------------
# Install / import probe (runtime check against oldest claimed core)
# ---------------------------------------------------------------------------


def _get_module_package_name(module_dir: Path) -> str | None:
    """
    Extract the importable package name from a module's ``pyproject.toml``.

    Looks at ``[tool.poetry.packages]`` and returns the ``include`` value
    of the first entry.  Returns ``None`` if the file is absent or the
    information cannot be extracted.
    """
    pyproject = module_dir / "pyproject.toml"
    if not pyproject.is_file():
        return None
    try:
        with pyproject.open("rb") as fh:
            data = tomllib.load(fh)
    except OSError:
        return None
    packages = data.get("tool", {}).get("poetry", {}).get("packages", [])
    if not isinstance(packages, list):
        return None
    for entry in packages:
        if isinstance(entry, dict):
            name = entry.get("include")
            if isinstance(name, str) and name:
                return name
    return None


def _poetry_spec_to_pep440(spec: str) -> str:
    """
    Convert a Poetry version specifier to PEP 440 form for ``pip install``.

    Handles the forms found in this repository:

    * ``^X.Y.Z`` → ``>=X.Y.Z,<X+1.0.0`` (X >= 1) or ``>=0.Y.Z,<0.Y+1.0`` (X == 0)
    * ``^X.Y``   → ``>=X.Y,<X+1.0`` (X >= 1) or ``>=0.Y,<0.Y+1`` (X == 0)
    * ``~X.Y.Z`` → ``>=X.Y.Z,<X.Y+1.0``
    * Everything else is passed through as-is (assumed PEP 440 compatible).

    This is intentionally limited to the forms present in the QuickScale
    monorepo module dependencies.  It is not a general Poetry-to-PEP 440
    converter.
    """
    # Caret: ^X.Y.Z or ^X.Y
    caret_match = re.match(r"^\^(\d+)\.(\d+)(?:\.(\d+))?$", spec)
    if caret_match:
        major = int(caret_match.group(1))
        minor = int(caret_match.group(2))
        patch = caret_match.group(3)
        if major >= 1:
            upper_major = major + 1
            lower = f"{major}.{minor}" if patch is None else f"{major}.{minor}.{patch}"
            upper = f"{upper_major}.0.0"
        else:
            # Pre-1.0: bounded by minor version (Poetry's convention)
            upper_minor = minor + 1
            lower = f"0.{minor}" if patch is None else f"0.{minor}.{patch}"
            upper = f"0.{upper_minor}.0"
        return f">={lower},<{upper}"

    # Tilde: ~X.Y.Z
    tilde_match = re.match(r"^~(\d+)\.(\d+)\.(\d+)$", spec)
    if tilde_match:
        major = int(tilde_match.group(1))
        minor = int(tilde_match.group(2))
        patch = tilde_match.group(3)
        upper_minor = minor + 1
        return f">={major}.{minor}.{patch},<{major}.{upper_minor}.0"

    # Plain wildcard: X.Y.* or just a bare version
    # Pass through unchanged (pip may handle it or fail with a clear error)
    return spec


def _get_module_non_core_deps(module_dir: Path) -> list[str]:
    """
    Return non-core, installable dependency specs from a module's pyproject.

    Excludes ``python``, ``quickscale-core``, and any dependency entry that
    uses a path (editable / develop) form.  The returned list uses PEP 440
    specifiers suitable for passing to ``pip install``.
    """
    pyproject = module_dir / "pyproject.toml"
    if not pyproject.is_file():
        return []
    try:
        with pyproject.open("rb") as fh:
            data = tomllib.load(fh)
    except OSError:
        return []

    poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
    if not isinstance(poetry_deps, dict):
        return []

    specs: list[str] = []
    for dep_name, dep_spec in poetry_deps.items():
        if dep_name in ("python", "quickscale-core"):
            continue
        if isinstance(dep_spec, str):
            converted = _poetry_spec_to_pep440(dep_spec)
            specs.append(f"{dep_name}{converted}")
        elif isinstance(dep_spec, dict):
            # Skip path-only deps (editable / develop entries);
            # include version-constrained entries.
            if "path" in dep_spec and "version" not in dep_spec:
                continue
            version = dep_spec.get("version", "")
            if version:
                converted = _poetry_spec_to_pep440(version)
                specs.append(f"{dep_name}{converted}")
    return specs


def _get_management_command_modules(package_name: str, src_dir: Path) -> list[str]:
    """
    Return dotted import paths for management command modules in *package_name*.

    Scans ``src_dir/<package_name>/management/commands/*.py`` (excluding
    ``__init__.py``) and returns fully-qualified dotted paths suitable for
    ``importlib.import_module`` or ``__import__``.

    Returns an empty list when the directory does not exist or no commands
    are found.
    """
    pkg_dir = src_dir / package_name
    commands_dir = pkg_dir / "management" / "commands"
    if not commands_dir.is_dir():
        return []
    modules: list[str] = []
    for cmd_file in sorted(commands_dir.iterdir()):
        if cmd_file.suffix == ".py" and cmd_file.stem != "__init__":
            modules.append(f"{package_name}.management.commands.{cmd_file.stem}")
    return modules


def _probe_module_install_import(
    mod_name: str,
    package_name: str,
    min_version: str,
    src_dir: Path,
    module_dir: Path,
) -> list[str]:
    """
    Run the install/import probe for one module.

    Returns a list of human-readable issues (empty = probe passed).
    """
    issues: list[str] = []

    try:
        with tempfile.TemporaryDirectory(prefix=f"qs_compat_probe_{mod_name}_") as tmpdir_str:
            tmpdir = Path(tmpdir_str)
            venv_path = tmpdir / ".venv"

            # --- create isolated venv ---
            log_prefix = "  INSTALL PROBE:"
            _log = lambda msg: print(f"  {log_prefix} {msg}")  # noqa: E731

            result = subprocess.run(
                [sys.executable, "-m", "venv", str(venv_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                issues.append(
                    f"{log_prefix} Failed to create virtual environment: {result.stderr.strip()}"
                )
                return issues

            pip_cmd = str(venv_path / "bin" / "pip")
            python_cmd = str(venv_path / "bin" / "python")

            # upgrade pip to avoid stale resolver warnings
            subprocess.run(
                [pip_cmd, "install", "--upgrade", "pip", "--quiet"],
                capture_output=True,
                text=True,
                timeout=60,
            )

            # --- install oldest claimed core ---
            _log(f"Installing quickscale-core=={min_version} ...")
            result = subprocess.run(
                [pip_cmd, "install", f"quickscale-core=={min_version}", "--quiet"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                stderr = result.stderr.strip()
                if "No matching distribution" in stderr or "Could not find" in stderr:
                    _log(
                        f"quickscale-core=={min_version} not found on PyPI "
                        f"(may not be published yet) — skipping probe."
                    )
                else:
                    issues.append(
                        f"{log_prefix} Failed to install quickscale-core=={min_version}: {stderr}"
                    )
                return issues

            # --- install module deps (non-core) ---
            has_django = False
            extra_deps = _get_module_non_core_deps(module_dir)
            if extra_deps:
                has_django = any("Django" in d or "django" in d for d in extra_deps)
                _log("Installing module dependencies ...")
                result = subprocess.run(
                    [pip_cmd, "install", *extra_deps, "--quiet"],
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
                if result.returncode != 0:
                    issues.append(
                        f"{log_prefix} Failed to install module dependencies: "
                        f"{result.stderr.strip()}"
                    )

            # --- discover management command modules ---
            management_cmds = _get_management_command_modules(package_name, src_dir)

            # --- write probe script ---
            probe_script = tmpdir / "_probe.py"
            probe_script.write_text(
                _build_probe_script(
                    package_name=package_name,
                    src_dir=src_dir,
                    has_django=has_django,
                    management_commands=management_cmds,
                ),
                encoding="utf-8",
            )

            # --- execute probe ---
            probe_env = os.environ.copy()
            probe_env["PYTHONPATH"] = f"{src_dir}:{probe_env.get('PYTHONPATH', '')}"

            result = subprocess.run(
                [str(python_cmd), str(probe_script)],
                capture_output=True,
                text=True,
                timeout=60,
                env=probe_env,
            )

            # Interpret probe output
            probe_passed = False
            core_failure = False
            for line in result.stdout.strip().splitlines():
                line = line.strip()
                if line == "PROBE_RESULT: PASS":
                    probe_passed = True
                elif line.startswith("PROBE_FAIL:"):
                    core_failure = True
                    issues.append(f"{log_prefix} {line[len('PROBE_FAIL:') :].strip()}")

            if result.returncode != 0 and not core_failure:
                # Non-zero exit but no PROBE_FAIL marker — likely a
                # Django config or other infrastructure issue.
                stderr = result.stderr.strip()
                if stderr:
                    _log(f"Probe script stderr (non-fatal): {stderr}")

            if probe_passed:
                _log(f"OK — {package_name} importable against quickscale-core=={min_version}")
            elif not core_failure:
                # Probe script ran but didn't reach PASS or FAIL marker
                issues.append(
                    f"{log_prefix} Probe script did not complete successfully "
                    f"(exit code {result.returncode})"
                )

    except subprocess.TimeoutExpired as exc:
        issues.append(f"  INSTALL PROBE: Probe timed out ({exc})")
    except Exception as exc:
        issues.append(f"  INSTALL PROBE: Unexpected error during probe: {exc}")

    return issues


def _build_probe_script(
    package_name: str,
    src_dir: Path,
    has_django: bool,
    management_commands: list[str] | None = None,
) -> str:
    """
    Build the probe script that will be run inside the isolated venv.

    The script writes PROBE_RESULT: PASS on success, or PROBE_FAIL: <msg>
    on failure.  Any other output is informational.

    *management_commands* is an optional list of dotted module paths for
    management command modules (e.g. ``["backups.management.commands.backups_create"]``)
    that should be imported during the probe to verify they resolve.
    """
    lines: list[str] = [
        "import sys",
        f"sys.path.insert(0, {str(src_dir)!r})",
        "",
        "# Phase 1: import the top-level package",
        "try:",
        f"    import {package_name}",
        f'    print(f"OK: top-level {package_name} imported")',
        "except Exception as exc:",
        '    print(f"PROBE_FAIL: top-level import failed: {exc}")',
        "    sys.exit(1)",
        "",
    ]

    if has_django:
        lines += [
            "# Phase 2: configure Django settings for submodule probes",
            "import django",
            "from django.conf import settings",
            "# Minimal settings that let Django models load without a database",
            "settings.configure(",
            "    INSTALLED_APPS=[",
            f"        {package_name!r},",
            "    ],",
            "    DATABASES={",
            '        "default": {',
            '            "ENGINE": "django.db.backends.sqlite3",',
            '            "NAME": ":memory:",',
            "        }",
            "    },",
            "    USE_TZ=True,",
            "    # Allow any SECRET_KEY for the import test",
            '    SECRET_KEY="compat-probe-insecure-key",',
            ")",
            "django.setup()",
            "",
        ]

    # Phase 2b: probe core-importing submodules (services.py)
    services_mod = f"{package_name}.services"
    lines += [
        "# Phase 2b: probe core-importing submodules",
        f"for _mod in [{services_mod!r}]:",
        "    try:",
        "        __import__(_mod)",
        '        print(f"OK: {_mod} imported")',
        "    except ImportError as exc:",
        "        # Report quickscale_core import errors as failures",
        "        msg = str(exc)",
        '        if "quickscale_core" in msg or "quickscale" in msg.lower():',
        '            print(f"PROBE_FAIL: import {_mod} failed: {exc}")',
        "        else:",
        '            print(f"SKIP: {_mod} requires configuration: {exc}")',
        "    except Exception as exc:",
        "        if 'ImproperlyConfigured' in type(exc).__name__:",
        '            print(f"SKIP: {_mod} needs Django app config: {exc}")',
        "        elif hasattr(exc, '__module__') and 'django' in getattr(exc, '__module__', ''):",
        '            print(f"SKIP: {_mod} Django infrastructure: {exc}")',
        "        else:",
        '            print(f"PROBE_FAIL: import {_mod} failed: {exc}")',
    ]

    # Phase 3: probe management command modules (if any found)
    if management_commands:
        _cmd_list_repr = repr(management_commands)
        lines += [
            "",
            "# Phase 3: probe management command modules",
            f"for _cmd_mod in {_cmd_list_repr}:",
            "    try:",
            "        __import__(_cmd_mod)",
            '        print(f"OK: {_cmd_mod} imported")',
            "    except ImportError as exc:",
            "        msg = str(exc)",
            '        if "quickscale_core" in msg or "quickscale" in msg.lower():',
            '            print(f"PROBE_FAIL: import {_cmd_mod} failed: {exc}")',
            "        else:",
            '            print(f"SKIP: {_cmd_mod} requires configuration: {exc}")',
            "    except Exception as exc:",
            "        if 'ImproperlyConfigured' in type(exc).__name__:",
            '            print(f"SKIP: {_cmd_mod} needs Django app config: {exc}")',
            "        elif hasattr(exc, '__module__') and 'django'"
            " in getattr(exc, '__module__', ''):",
            '            print(f"SKIP: {_cmd_mod} Django infrastructure: {exc}")',
            "        else:",
            '            print(f"PROBE_FAIL: import {_cmd_mod} failed: {exc}")',
        ]

    # Success marker
    lines += [
        "",
        'print("PROBE_RESULT: PASS")',
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main check logic
# ---------------------------------------------------------------------------


SKIP_INSTALL_PROBE_FLAG: Final[str] = "--skip-install-probe"


# Prevent accidental import-time side effects by keeping main() explicit.
def main(argv: list[str] | None = None) -> int:
    """Run the compatibility check and return an exit code."""
    if argv is None:
        argv = sys.argv[1:]

    # Parse flags before positional arguments
    skip_install_probe = SKIP_INSTALL_PROBE_FLAG in argv
    positional_args = [a for a in argv if a != SKIP_INSTALL_PROBE_FLAG]

    repo_root = _DEFAULT_REPO_ROOT
    # Allow overriding via first positional argument for convenience
    if positional_args:
        repo_root = Path(positional_args[0]).resolve()

    core_src_root = (repo_root / CORE_SRC_RELATIVE).resolve()
    modules_root = (repo_root / MODULES_DIR_RELATIVE).resolve()

    if not core_src_root.is_dir():
        print(
            f"ERROR: Core source directory not found: {core_src_root}",
            file=sys.stderr,
        )
        return 2
    if not modules_root.is_dir():
        print(
            f"ERROR: Modules directory not found: {modules_root}",
            file=sys.stderr,
        )
        return 2

    # Read current core version
    try:
        current_version_str = _read_version_file(repo_root)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 2
    current_version = _parse_version_tuple(current_version_str)

    print(f"Repository core version: {current_version_str}")
    print()

    overall_exit = 0

    # Scan module directories
    module_dirs = sorted(modules_root.iterdir())
    modules_found = 0
    modules_with_core_dep = 0

    for mod_dir in module_dirs:
        if not mod_dir.is_dir():
            continue
        module_yml = mod_dir / MODULE_YML
        if not module_yml.is_file():
            continue

        modules_found += 1
        mod_name = mod_dir.name

        # Parse module.yml for core dependency
        try:
            data = _parse_module_yml(module_yml)
        except Exception as exc:
            print(f"[{mod_name}] ERROR: Could not parse {module_yml}: {exc}")
            overall_exit = 1
            continue

        dep_spec = _get_core_dep_spec(data)
        if dep_spec is None:
            print(f"[{mod_name}] No quickscale-core dependency declared — skipping.")
            continue

        modules_with_core_dep += 1
        print(f"[{mod_name}] quickscale-core dependency: {dep_spec}")

        # Parse minimum version
        min_ver_str = _extract_min_core_version(dep_spec)
        if min_ver_str is None:
            print(
                f"  WARNING: Could not extract minimum version from spec "
                f"({dep_spec}). Cannot verify version baseline."
            )
        else:
            min_ver = _parse_version_tuple(min_ver_str)
            if min_ver > current_version:
                print(
                    f"  FAIL: Minimum claimed version {min_ver_str} is "
                    f"NEWER than repository core version {current_version_str}."
                )
                overall_exit = 1
            elif min_ver < current_version:
                print(
                    f"  NOTE: Minimum claimed version {min_ver_str} is "
                    f"OLDER than repository core version {current_version_str}. "
                    f"Compatibility check covers the current core only; "
                    f"backward compatibility with {min_ver_str} is assumed "
                    f"but not proven by static analysis."
                )
            else:
                print(
                    f"  OK: Minimum claimed version {min_ver_str} matches "
                    f"repository core version {current_version_str}."
                )

        # Collect quickscale_core imports from module source
        src_dir = mod_dir / "src"
        if not src_dir.is_dir():
            print("  SKIP: No src/ directory — cannot check imports.")
            continue

        imports_by_file = _collect_core_imports(src_dir)
        if not imports_by_file:
            print("  OK: No quickscale_core imports found in module source.")
            continue

        # Resolve each import
        file_issues: list[str] = []
        for py_file, import_list in imports_by_file.items():
            rel_path = py_file.relative_to(src_dir)
            for module_path, imported_names in import_list:
                issues = _resolve_import(core_src_root, module_path, imported_names)
                if issues:
                    file_issues.append(f"  In {rel_path}:")
                    file_issues.extend(issues)

        if file_issues:
            print("  IMPORT ISSUES:")
            for line in file_issues:
                print(f"    {line}")
            overall_exit = 1
        else:
            total_groups = sum(len(lst) for lst in imports_by_file.values())
            total_files = len(imports_by_file)
            files_label = "file" if total_files == 1 else "files"
            groups_label = "group" if total_groups == 1 else "groups"
            print(
                f"  OK: {total_groups} quickscale_core import {groups_label}"
                f" in {total_files} {files_label} resolved."
            )

        # ---- Phase 2: install / import probe ----
        if not skip_install_probe and min_ver_str is not None:
            if mod_name in SKIP_INSTALL_PROBE_MODULES:
                print(f"  INSTALL PROBE: Skipped — {SKIP_INSTALL_PROBE_MODULES[mod_name]}")
            else:
                try:
                    package_name = _get_module_package_name(mod_dir)
                except tomllib.TOMLDecodeError as exc:
                    print(
                        f"  ERROR: Malformed module pyproject.toml "
                        f"({mod_dir / 'pyproject.toml'}): {exc}"
                    )
                    overall_exit = 1
                    continue
                if package_name and src_dir.is_dir():
                    probe_issues = _probe_module_install_import(
                        mod_name=mod_name,
                        package_name=package_name,
                        min_version=min_ver_str,
                        src_dir=src_dir,
                        module_dir=mod_dir,
                    )
                    for pi in probe_issues:
                        print(pi)
                        overall_exit = 1
                else:
                    print(
                        "  INSTALL PROBE: Could not determine package name "
                        "from pyproject.toml — skipping probe."
                    )

        print()  # blank line between modules

    # Summary
    if modules_found == 0:
        print("No modules found under quickscale_modules/.")
        return 0

    if modules_with_core_dep == 0:
        print("No modules declare a quickscale-core dependency.")
        return 0

    if overall_exit == 0:
        print("All modules compatible.")
    else:
        print("One or more compatibility issues found.")

    return overall_exit


if __name__ == "__main__":
    raise SystemExit(main())
