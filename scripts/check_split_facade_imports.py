#!/usr/bin/env python3
"""
SA234 — Split-facade import gate.

Each split package (the CLI command and utility facades, ``dr_engine``, and
billing) publishes its public surface through a facade module that re-exports
the names its private siblings define.  A private module (``_*.py``) resolves
collaborators through the sibling modules that define them and never imports
its own package's facade: the facade is a one-way re-export, not a call-time
dependency (decisions.md, Split-Facade Seams).

The gate models "facade" structurally: a public module in a scanned package
that imports from a private sibling in the same package is a facade.  A
private module importing any of those facade modules in its family fails the
gate, with the offending file and import printed.  A private module importing
a sibling that defines its own names (such as billing's ``exceptions`` /
``models`` or ``dr_engine``'s ``primitives``) stays legal.

Exit codes:
    0 — every private module respects the split-facade boundary
    1 — one or more private modules import a facade
    2 — the source tree could not be inspected (fail closed)
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# (module package, package directory relative to the repository root)
SCAN_ROOTS: tuple[tuple[str, Path], ...] = (
    ("quickscale_cli.commands", Path("quickscale_cli/src/quickscale_cli/commands")),
    ("quickscale_cli.utils", Path("quickscale_cli/src/quickscale_cli/utils")),
    (
        "quickscale_core.dr_engine",
        Path("quickscale_core/src/quickscale_core/dr_engine"),
    ),
    (
        "quickscale_modules_billing",
        Path("quickscale_modules/billing/src/quickscale_modules_billing"),
    ),
)

# Package roots that share one facade family: a private module may not import a
# facade from any directory listed under its own family root.
FAMILY_ROOTS: tuple[str, ...] = (
    "quickscale_cli",
    "quickscale_core.dr_engine",
    "quickscale_modules_billing",
)


class _InspectionError(Exception):
    """A required source file or directory could not be inspected."""


def _relative_import_module(module: str | None, level: int, module_prefix: str) -> str:
    """Resolve an ``ast.ImportFrom`` target against the importing module."""
    if level == 0:
        return module or ""
    parts = module_prefix.split(".")
    base = parts[: len(parts) - level]
    if module:
        base.append(module)
    return ".".join(base)


def _imported_modules(tree: ast.AST, module_prefix: str) -> list[tuple[int, str]]:
    """
    Collect ``(lineno, candidate module)`` for every import in *tree*.

    ``from package import facade`` yields both ``package`` and
    ``package.facade`` so a facade reached through its package binds.
    """
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            resolved = _relative_import_module(node.module, node.level, module_prefix)
            if not resolved:
                continue
            found.append((node.lineno, resolved))
            for alias in node.names:
                if alias.name != "*":
                    found.append((node.lineno, f"{resolved}.{alias.name}"))
    return found


def _parse(path: Path) -> ast.AST:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise _InspectionError(f"read failed: {path}: {exc}") from exc
    try:
        return ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        raise _InspectionError(f"AST parse failed: {path}: {exc}") from exc


def _facade_modules(
    parsed: list[tuple[Path, str, ast.AST]],
) -> set[str]:
    """Public modules that import a private sibling in the same package."""
    facades: set[str] = set()
    for path, module_prefix, tree in parsed:
        stem = path.stem
        if stem.startswith("_"):
            continue
        for _, imported in _imported_modules(tree, f"{module_prefix}.{stem}"):
            if imported.startswith(f"{module_prefix}._"):
                facades.add(f"{module_prefix}.{stem}")
                break
    return facades


def _scan_family(repo_root: Path, family_root: str) -> list[tuple[Path, int, str]]:
    """Return ``(file, lineno, facade_module)`` violations for one family."""
    expected: list[tuple[Path, str]] = [
        ((repo_root / relative).resolve(), module_prefix)
        for module_prefix, relative in SCAN_ROOTS
        if module_prefix == family_root or module_prefix.startswith(f"{family_root}.")
    ]
    missing = [str(root) for root, _ in expected if not root.is_dir()]
    if missing:
        raise _InspectionError("required scan directory not found: " + ", ".join(sorted(missing)))
    dirs = expected

    parsed: list[tuple[Path, str, ast.AST]] = []
    for root, module_prefix in dirs:
        for path in sorted(root.glob("*.py")):
            parsed.append((path, module_prefix, _parse(path)))
    facades = _facade_modules(parsed)

    violations: list[tuple[Path, int, str]] = []
    for path, module_prefix, tree in parsed:
        stem = path.stem
        if not stem.startswith("_"):
            continue
        for lineno, imported in _imported_modules(tree, f"{module_prefix}.{stem}"):
            if imported in facades:
                violations.append((path, lineno, imported))
    return violations


def main(argv: list[str] | None = None) -> int:
    """Run the split-facade import gate and return an exit code."""
    if argv is None:
        argv = sys.argv[1:]
    repo_root = Path(argv[0]).resolve() if argv else Path.cwd().resolve()

    all_violations: list[tuple[str, Path, int, str]] = []
    try:
        for family_root in FAMILY_ROOTS:
            for path, lineno, imported in _scan_family(repo_root, family_root):
                all_violations.append((family_root, path, lineno, imported))
    except _InspectionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if not all_violations:
        print(
            "All private modules resolve collaborators through defining "
            "siblings:\n"
            "  • No `_*.py` module imports its package's facade."
        )
        return 0

    current_family = ""
    for family_root, path, lineno, imported in all_violations:
        if family_root != current_family:
            print(f"[{family_root}] split-facade import violations:")
            current_family = family_root
        try:
            display = path.relative_to(repo_root)
        except ValueError:  # pragma: no cover - defensive
            display = path
        print(f"  {display}:{lineno}  {imported}")

    print(
        f"\n{len(all_violations)} split-facade import violation(s) found.\n"
        "A private module must import the sibling that defines the name; the "
        "facade is a one-way re-export and must not be imported back."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
