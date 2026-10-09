#!/usr/bin/env python3
"""
SA234/SA259 — Split-facade import gate.

Each split package publishes its public surface through facade modules that
re-export names their private siblings (``_*.py``) define.  A private module
imports the sibling modules that define its collaborators and never reaches a
facade of its own distribution: the facade is a one-way re-export, not a
call-time dependency (decisions.md, Split-Facade Seams).

Scope is derived from the layout, never hand-listed: every first-party
distribution (a directory with ``pyproject.toml`` beside ``src/``) contributes
each package under its ``src/`` tree that carries at least one private module.
A package's family is its distribution root, so a private module may not reach
a facade from any package of its own distribution.

The gate models "facade" structurally at module level: a public module that
imports a private sibling at module level publishes a re-export surface.  A
private module fails when it imports such a facade module, or a name the
facade does not define itself; a name the facade defines (a class, function,
or assignment) is that name's definer and stays legal, as does importing a
sibling that defines its own names.  ``__init__.py`` is the package's own
public surface rather than a private module and is never a violation site.

Exit codes:
    0 — every private module respects the split-facade boundary
    1 — one or more private modules reach a facade
    2 — the source tree could not be inspected (fail closed)
"""

from __future__ import annotations

import ast
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Directories that never carry first-party distributions: hidden trees,
# virtual environments, installed dependencies, and interpreter caches.
_WORKSPACE_DIRS = frozenset({".git", ".venv", "venv", "node_modules", "__pycache__"})


class _InspectionError(Exception):
    """A required source file or directory could not be inspected."""


@dataclass
class _Module:
    """One parsed top-level module of a scanned package."""

    path: Path
    name: str
    tree: ast.Module
    defined: frozenset[str]
    is_facade: bool


@dataclass
class _Package:
    """One layout-derived package carrying at least one private module."""

    prefix: str
    family: str
    directory: Path
    modules: dict[str, _Module] = field(default_factory=dict)


def _relative_module(module: str | None, level: int, module_name: str) -> str:
    """Resolve an ``ast.ImportFrom`` target against the importing module."""
    if level == 0:
        return module or ""
    parts = module_name.split(".")
    base = parts[: len(parts) - level]
    if module:
        base.append(module)
    return ".".join(base)


def _module_level_imports(tree: ast.Module, module_name: str) -> list[tuple[int, str, str | None]]:
    """
    Collect ``(lineno, target module, imported name)`` at module level.

    A plain ``import`` yields a ``None`` name; a ``from`` import yields the
    resolved module and the imported name (``"*"`` for a star import).
    """
    found: list[tuple[int, str, str | None]] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name, None) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            resolved = _relative_module(node.module, node.level, module_name)
            if not resolved:
                continue
            found.extend((node.lineno, resolved, alias.name) for alias in node.names)
    return found


def _all_imports(tree: ast.Module, module_name: str) -> list[tuple[int, str, str | None]]:
    """Collect ``(lineno, target module, imported name)`` for every import."""
    found: list[tuple[int, str, str | None]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name, None) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            resolved = _relative_module(node.module, node.level, module_name)
            if not resolved:
                continue
            found.extend((node.lineno, resolved, alias.name) for alias in node.names)
    return found


def _binds_private_sibling(target: str, name: str | None, prefix: str) -> bool:
    """
    Return whether an import reaches a private sibling of the scanned package.

    Both forms bind the sibling: a direct module import (``from ._x import y``
    or ``import pkg._x``) and a name import through the package
    (``from . import _x``).
    """
    if target.startswith(f"{prefix}._"):
        return True
    return bool(name) and name != "*" and f"{target}.{name}".startswith(f"{prefix}._")


def _defined_names(tree: ast.Module) -> frozenset[str]:
    """
    Return every name the module defines at its own top level.

    Imports bind names without defining them, so a re-exported name stays
    absent: only classes, functions, and assignments count as definitions,
    including those inside module-level ``if``/``try`` bodies.
    """
    names: set[str] = set()

    def collect(body: list[ast.stmt]) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Assign):
                names.update(target.id for target in node.targets if isinstance(target, ast.Name))
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names.add(node.target.id)
            elif isinstance(node, ast.TypeAlias) and isinstance(node.name, ast.Name):
                names.add(node.name.id)
            elif isinstance(node, (ast.If, ast.Try)):
                collect(node.body)
                for handler in getattr(node, "handlers", []):
                    collect(handler.body)
                collect(getattr(node, "orelse", []))
                collect(getattr(node, "finalbody", []))

    collect(tree.body)
    return frozenset(names)


def _parse(path: Path) -> ast.Module:
    """Read and parse one module, failing closed on any inspection error."""
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise _InspectionError(f"read failed: {path}: {exc}") from exc
    try:
        return ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        raise _InspectionError(f"AST parse failed: {path}: {exc}") from exc


def _iter_distributions(repo_root: Path) -> list[tuple[str, Path]]:
    """
    Return ``(family, distribution package directory)`` pairs from the layout.

    A first-party distribution is a directory holding ``pyproject.toml`` beside
    a ``src/`` tree with an importable package.  Hidden and vendored trees are
    pruned, and the repository root's own ``pyproject.toml`` is not a package.
    """
    distributions: list[tuple[str, Path]] = []
    for directory, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = sorted(
            name for name in dirnames if name not in _WORKSPACE_DIRS and not name.startswith(".")
        )
        if "pyproject.toml" not in filenames:
            continue
        pyproject_dir = Path(directory)
        if pyproject_dir == repo_root:
            continue
        src = pyproject_dir / "src"
        if not src.is_dir():
            continue
        for candidate in sorted(src.iterdir()):
            if candidate.is_dir() and (candidate / "__init__.py").is_file():
                distributions.append((candidate.name, candidate))
    return distributions


def _iter_package_dirs(distribution_root: Path) -> list[Path]:
    """Return every package directory under one distribution's root package."""
    found: list[Path] = []
    stack = [distribution_root]
    while stack:
        directory = stack.pop()
        if not (directory / "__init__.py").is_file():
            continue
        found.append(directory)
        stack.extend(
            sorted(
                child
                for child in directory.iterdir()
                if child.is_dir()
                and child.name != "__pycache__"
                and (child / "__init__.py").is_file()
            )
        )
    return sorted(found)


def discover_scope(repo_root: Path) -> dict[str, _Package]:
    """
    Return every layout-derived split package, keyed by dotted prefix.

    The scope is the layout: a package is scanned when it carries at least one
    private module (``_*.py`` other than ``__init__.py``).  Packages without
    split files are outside the gate's subject and are not indexed.
    """
    distributions = _iter_distributions(repo_root)
    if not distributions:
        raise _InspectionError(
            f"layout discovery found no first-party distribution under {repo_root}"
        )

    packages: dict[str, _Package] = {}
    total_package_dirs = 0
    for family, distribution_root in distributions:
        for directory in _iter_package_dirs(distribution_root):
            total_package_dirs += 1
            prefix = ".".join([family, *directory.relative_to(distribution_root).parts])
            modules: dict[str, _Module] = {}
            has_private_module = False
            for path in sorted(directory.glob("*.py")):
                if path.stem.startswith("_") and path.stem != "__init__":
                    has_private_module = True
                module_name = prefix if path.stem == "__init__" else f"{prefix}.{path.stem}"
                tree = _parse(path)
                modules[module_name] = _Module(
                    path=path,
                    name=module_name,
                    tree=tree,
                    defined=_defined_names(tree),
                    is_facade=False,
                )
            if not has_private_module:
                continue
            for module in modules.values():
                if module.path.stem.startswith("_"):
                    continue
                module.is_facade = any(
                    _binds_private_sibling(target, name, prefix)
                    for _, target, name in _module_level_imports(module.tree, module.name)
                )
            packages[prefix] = _Package(
                prefix=prefix, family=family, directory=directory, modules=modules
            )

    if total_package_dirs == 0:
        raise _InspectionError(f"layout discovery found no package under {repo_root} (fail closed)")
    return packages


def _facade_index(
    packages: dict[str, _Package],
) -> tuple[dict[str, _Module], dict[str, str]]:
    """Index facade modules and every scanned module's family."""
    facades: dict[str, _Module] = {}
    families: dict[str, str] = {}
    for package in packages.values():
        for module in package.modules.values():
            families[module.name] = package.family
            if module.is_facade:
                facades[module.name] = module
    return facades, families


def _collect_violations(
    packages: dict[str, _Package],
    facades: dict[str, _Module],
    families: dict[str, str],
) -> list[tuple[Path, int, str, str | None]]:
    """Return ``(file, lineno, module, name)`` for every split-facade breach."""
    violations: list[tuple[Path, int, str, str | None]] = []
    for package in sorted(packages.values(), key=lambda item: item.prefix):
        for module in sorted(package.modules.values(), key=lambda item: str(item.path)):
            stem = module.path.stem
            if not stem.startswith("_") or stem == "__init__":
                continue
            for lineno, target, name in _all_imports(module.tree, module.name):
                facade = facades.get(target)
                if facade is not None and families.get(target) == package.family:
                    if name is None or name == "*":
                        violations.append((module.path, lineno, target, None))
                    elif name not in facade.defined:
                        violations.append((module.path, lineno, target, name))
                    continue
                if name is None or name == "*":
                    continue
                submodule = f"{target}.{name}"
                sub_facade = facades.get(submodule)
                if sub_facade is not None and families.get(submodule) == package.family:
                    violations.append((module.path, lineno, submodule, None))
    return violations


def main(argv: list[str] | None = None) -> int:
    """Run the split-facade import gate and return an exit code."""
    if argv is None:
        argv = sys.argv[1:]
    repo_root = Path(argv[0]).resolve() if argv else Path.cwd().resolve()

    try:
        packages = discover_scope(repo_root)
        facades, families = _facade_index(packages)
        violations = _collect_violations(packages, facades, families)
    except _InspectionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if not violations:
        print(
            "All private modules resolve collaborators through defining "
            "siblings:\n"
            f"  • Scanned {len(packages)} layout-derived split package(s).\n"
            "  • No `_*.py` module reaches a facade in its family."
        )
        return 0

    current_family = ""
    for path, lineno, target, name in violations:
        family = families.get(target, "")
        if family != current_family:
            print(f"[{family}] split-facade import violations:")
            current_family = family
        try:
            display = path.relative_to(repo_root)
        except ValueError:  # pragma: no cover - defensive
            display = path
        imported = target if name is None else f"{target}.{name}"
        print(f"  {display}:{lineno}  {imported}")

    print(
        f"\n{len(violations)} split-facade import violation(s) found.\n"
        "A private module must import the sibling that defines the name; a "
        "facade is a one-way re-export and must not be imported back."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
