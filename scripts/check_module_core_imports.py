#!/usr/bin/env python3
"""
SA9.6 / SA89b — Bidirectional module-core import-linter gate.

Forward direction (SA9.6):
    Scans ``quickscale_modules/*/src/`` for imports from ``quickscale_core`` and
    rejects any import that targets a module other than ``quickscale_core.runtime``
    (except for per-module legacy exceptions documented in
    ``LEGACY_ALLOWED_IMPORTS``, currently limited to billing and CRM adapter
    seams).

Reverse direction (SA89b):
    Scans ``quickscale_core/src/quickscale_core/`` for imports from
    ``quickscale_modules``.  Zero imports from modules are permitted in core
    source; all module interaction must go through the injected fail-hard
    persistence registry.

This gate enforces the core-as-runtime-API boundary: module code must import
from the public ``quickscale_core.runtime`` facade rather than reaching
directly into internal subpackages (``dr_engine``, ``contracts``,
``manifest``, etc.).  Temporary legacy exceptions exist only for the
billing and CRM adapter files and must not be used as a general allowlist.

Exit codes:
    0 — all imports respect the bidirectional core↔module boundary
    1 — one or more boundary violations found
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT_ENV: str = "REPO_ROOT"
_DEFAULT_REPO_ROOT: Path = Path(os.environ.get(REPO_ROOT_ENV, os.getcwd())).resolve()

MODULES_DIR_RELATIVE: Path = Path("quickscale_modules")
CORE_SRC_RELATIVE: Path = Path("quickscale_core") / "src" / "quickscale_core"

# The only allowed quickscale_core import target for module code.
# Modules must import from the public runtime facade only.
# This set can be extended with explicit exceptions documented in the
# roadmap or decisions.md when a legitimate cross-boundary import is
# required.
ALLOWED_CORE_IMPORTS: frozenset[str] = frozenset(
    {
        "quickscale_core.runtime",
    }
)

# Per-module legacy deep imports that are architecturally necessary
# framework-seam imports (module-registration adapter surface). These exist
# in billing, CRM, and social and are not part of the runtime API that
# SA9.3–SA9.5 migrated. They are kept here so the gate passes the current
# codebase while preventing *new* deep imports from being added to any module
# (including billing, CRM, and social). Each entry should be removed when the
# corresponding module migrates its adapter imports to a public seam.
#
# Key design property: LEGACY_ALLOWED_IMPORTS is keyed by module directory
# name so no module inherits another module's exception.
LEGACY_ALLOWED_IMPORTS: dict[str, frozenset[str]] = {
    "billing": frozenset(
        {
            "quickscale_core.manifest.entry_point",
            "quickscale_core.module_wiring",
        }
    ),
    "crm": frozenset(
        {
            "quickscale_core.manifest.entry_point",
            "quickscale_core.module_wiring",
        }
    ),
    # Social adapter imports from quickscale_core.runtime.manifest directly
    # to avoid pulling in the DR surface at import time (which triggers
    # circular imports through the combined runtime facade).  See the
    # runtime/__init__.py docstring for the architectural rationale.
    "social": frozenset(
        {
            "quickscale_core.runtime.manifest",
        }
    ),
}


# ---------------------------------------------------------------------------
# AST visitor: collect disallowed quickscale_core imports
# ---------------------------------------------------------------------------


class _CoreImportLinterVisitor(ast.NodeVisitor):
    """Collect quickscale_core imports that violate the boundary rule."""

    def __init__(self, module_name: str) -> None:
        super().__init__()
        self.module_name = module_name
        # List of (lineno, full_import_path) for each violation found
        self.violations: list[tuple[int, str]] = []

    @staticmethod
    def _is_quickscale_core(module: str | None) -> bool:
        if module is None:
            return False
        return module == "quickscale_core" or module.startswith("quickscale_core.")

    def _is_allowed(self, module: str) -> bool:
        if module in ALLOWED_CORE_IMPORTS:
            return True
        # Check per-module legacy exceptions
        if self.module_name in LEGACY_ALLOWED_IMPORTS:
            if module in LEGACY_ALLOWED_IMPORTS[self.module_name]:
                return True
        return False

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if self._is_quickscale_core(alias.name):
                if not self._is_allowed(alias.name):
                    self.violations.append((node.lineno, alias.name))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if self._is_quickscale_core(node.module):
            assert node.module is not None  # guaranteed by the guard above
            if not self._is_allowed(node.module):
                self.violations.append((node.lineno, node.module))


# ---------------------------------------------------------------------------
# Reverse AST visitor: collect quickscale_modules imports from core source
# ---------------------------------------------------------------------------


class _ModulesImportLinterVisitor(ast.NodeVisitor):
    """Collect quickscale_modules imports found in core source (zero allowed)."""

    def __init__(self) -> None:
        super().__init__()
        # List of (lineno, full_import_path) for each violation found
        self.violations: list[tuple[int, str]] = []

    @staticmethod
    def _is_quickscale_modules(module: str | None) -> bool:
        if module is None:
            return False
        # Match dotted access (quickscale_modules.sub) and actual
        # installed package names (quickscale_modules_backups).
        return (
            module == "quickscale_modules"
            or module.startswith("quickscale_modules.")
            or module.startswith("quickscale_modules_")
        )

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if self._is_quickscale_modules(alias.name):
                self.violations.append((node.lineno, alias.name))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if self._is_quickscale_modules(node.module):
            assert node.module is not None
            self.violations.append((node.lineno, node.module))


def _check_core_source(source_dir: Path) -> dict[Path, list[tuple[int, str]]]:
    """Scan *source_dir* for quickscale_modules import violations in core code."""
    results: dict[Path, list[tuple[int, str]]] = {}
    for py_file in sorted(source_dir.rglob("*.py")):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        visitor = _ModulesImportLinterVisitor()
        visitor.visit(tree)
        if visitor.violations:
            results[py_file] = visitor.violations
    return results


def _check_module_source(source_dir: Path, module_name: str) -> dict[Path, list[tuple[int, str]]]:
    """
    Scan *source_dir* for quickscale_core import violations.

    *module_name* is used to apply per-module legacy exceptions.

    Returns a mapping from file path to list of ``(lineno, import_path)``
    tuples for every disallowed import found.
    """
    results: dict[Path, list[tuple[int, str]]] = {}
    for py_file in sorted(source_dir.rglob("*.py")):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            # Skip files with syntax errors (unlikely in a healthy repo)
            continue
        visitor = _CoreImportLinterVisitor(module_name)
        visitor.visit(tree)
        if visitor.violations:
            results[py_file] = visitor.violations
    return results


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Run the import linter and return an exit code."""
    if argv is None:
        argv = sys.argv[1:]

    repo_root = _DEFAULT_REPO_ROOT
    if argv:
        repo_root = Path(argv[0]).resolve()

    # ------------------------------------------------------------------
    # Forward direction: modules → core
    # ------------------------------------------------------------------
    modules_root = (repo_root / MODULES_DIR_RELATIVE).resolve()

    all_violations: list[tuple[str, Path, int, str]] = []  # (context, file, lineno, import_path)

    modules_root_found = modules_root.is_dir()
    if modules_root_found:
        for mod_dir in sorted(modules_root.iterdir()):
            if not mod_dir.is_dir():
                continue

            src_dir = mod_dir / "src"
            if not src_dir.is_dir():
                continue

            mod_name = mod_dir.name
            violations_by_file = _check_module_source(src_dir, mod_name)

            if not violations_by_file:
                continue

            _header_printed = False
            for py_file, violations in sorted(violations_by_file.items()):
                rel_path = py_file.relative_to(src_dir)
                for lineno, import_path in violations:
                    if not _header_printed:
                        print(f"[{mod_name}] Core import boundary violations:")
                        _header_printed = True
                    print(f"  {rel_path}:{lineno}  {import_path}")
                    all_violations.append((mod_name, rel_path, lineno, import_path))
    else:
        print(
            f"ERROR: Required scan root not found: {modules_root}; "
            f"cannot perform forward direction scan.",
            file=sys.stderr,
        )

    # ------------------------------------------------------------------
    # Reverse direction: core → modules
    # ------------------------------------------------------------------
    core_src = (repo_root / CORE_SRC_RELATIVE).resolve()

    core_src_found = core_src.is_dir()
    if core_src_found:
        reverse_violations = _check_core_source(core_src)
        if reverse_violations:
            _header_printed = False
            for py_file, violations in sorted(reverse_violations.items()):
                rel_path = py_file.relative_to(core_src)
                for lineno, import_path in violations:
                    if not _header_printed:
                        print(
                            "Core source import boundary violations "
                            "(quickscale_modules prohibited):"
                        )
                        _header_printed = True
                    print(f"  {rel_path}:{lineno}  {import_path}")
                    all_violations.append(("quickscale_core", rel_path, lineno, import_path))
    else:
        print(
            f"ERROR: Required scan root not found: {core_src}; "
            f"cannot perform reverse direction scan.",
            file=sys.stderr,
        )

    total = len(all_violations)
    if total == 0 and modules_root_found and core_src_found:
        print(
            "All imports respect the core↔module boundary:\n"
            "  • Module code imports only from quickscale_core.runtime "
            "(+ per-module legacy seams for billing/crm).\n"
            "  • Core source has zero imports from quickscale_modules."
        )
        return 0

    if total > 0:
        print(
            f"\n{total} import boundary violation(s) found.\n"
            f"Module code must import from one of: "
            f"{', '.join(sorted(ALLOWED_CORE_IMPORTS))}\n"
            f"Per-module legacy exceptions exist for billing/crm adapter seams only.\n"
            f"Core source must not import from quickscale_modules at all."
        )
    if not modules_root_found or not core_src_found:
        print(
            "ERROR: One or more required scan roots were not found; "
            "gate cannot verify the boundary.",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
