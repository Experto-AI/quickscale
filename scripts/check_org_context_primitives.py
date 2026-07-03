#!/usr/bin/env python3
"""
SA13.1 — Warn-only AST lint gate for the three privatized org-context primitives.

Scans ``quickscale_modules/*/src/`` (excluding orgs itself) for imports of
the three underscored primitives (``_tenant_context``,
``_set_current_org_for_context``, ``_set_db_current_org_id``) and their
compatibility aliases (``tenant_context``, ``set_current_org_for_context``,
``set_db_current_org_id``) from ``quickscale_modules_orgs.current_org``.

This gate **warns only** (exit 0) during SA13.1 so pre-migration callers
continue to work.  SA13.4 will flip to hard-fail once SA13.2/13.3 migrate
all external callsites.

``org_scope`` and all other ``current_org`` symbols are exempt — they are
the permanent public API.

Exit codes:
    0 — always (warn-only mode during SA13.1–SA13.3)
    2 — a configuration or filesystem error
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
CORE_DIR_RELATIVE: Path = Path("quickscale_core")

# The three privatized primitives (private underscored names + compat aliases).
# These are the symbols the gate warns on.  All other symbols from
# quickscale_modules_orgs.current_org (notably org_scope) are exempt.
PRIVATIZED_PRIMITIVES: frozenset[str] = frozenset(
    {
        # Private underscored names (direct use)
        "_tenant_context",
        "_set_current_org_for_context",
        "_set_db_current_org_id",
        # Compatibility aliases (old public names, kept for SA13.2/13.3)
        "tenant_context",
        "set_current_org_for_context",
        "set_db_current_org_id",
    }
)

# Module names that are exempt from the lint gate.
# The orgs module itself may use these primitives internally.
EXEMPT_MODULES: frozenset[str] = frozenset({"orgs"})


# ---------------------------------------------------------------------------
# AST visitor: collect imports of the privatized primitives
# ---------------------------------------------------------------------------


class _OrgContextPrimitivesVisitor(ast.NodeVisitor):
    """Collect imports of the privatized org-context primitives."""

    def __init__(self) -> None:
        super().__init__()
        # List of (lineno, import_statement) for each flagged import
        self.violations: list[tuple[int, str]] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "quickscale_modules_orgs.current_org":
                # ``import quickscale_modules_orgs.current_org`` — cannot
                # detect which symbols are used without deeper analysis,
                # so we check the alias only.  This is a rare pattern;
                # module-level ``from ... import`` is the norm.
                continue
            if alias.name.startswith("quickscale_modules_orgs.current_org."):
                suffix = alias.name.split(".", 2)[2] if "." in alias.name.split(".", 2)[1] else ""
                if suffix and suffix in PRIVATIZED_PRIMITIVES:
                    self.violations.append((node.lineno, alias.name))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module is None:
            return
        if node.module != "quickscale_modules_orgs.current_org":
            return

        for alias in node.names:
            name = alias.name
            if name in PRIVATIZED_PRIMITIVES:
                self.violations.append((node.lineno, f"from {node.module} import {name}"))


def _check_module_source(source_dir: Path) -> dict[Path, list[tuple[int, str]]]:
    """
    Scan *source_dir* for imports of the privatized org-context primitives.

    Returns a mapping from file path to list of ``(lineno, import_statement)``
    tuples for every flagged import found.
    """
    results: dict[Path, list[tuple[int, str]]] = {}
    for py_file in sorted(source_dir.rglob("*.py")):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            # Skip files with syntax errors (unlikely in a healthy repo)
            continue
        visitor = _OrgContextPrimitivesVisitor()
        visitor.visit(tree)
        if visitor.violations:
            results[py_file] = visitor.violations
    return results


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Run the org-context primitives lint gate and exit 0 (warn-only)."""
    if argv is None:
        argv = sys.argv[1:]

    repo_root = _DEFAULT_REPO_ROOT
    if argv:
        repo_root = Path(argv[0]).resolve()

    modules_root = (repo_root / MODULES_DIR_RELATIVE).resolve()
    core_src_root = (repo_root / CORE_DIR_RELATIVE / "src").resolve()

    if not modules_root.is_dir():
        print(f"ERROR: Modules directory not found: {modules_root}", file=sys.stderr)
        return 2

    all_violations: list[tuple[str, Path, int, str]] = []

    # ---- Scan quickscale_modules/*/src/ -----------------------------------
    for mod_dir in sorted(modules_root.iterdir()):
        if not mod_dir.is_dir():
            continue

        mod_name = mod_dir.name

        # Skip exempt modules (orgs uses its own primitives internally)
        if mod_name in EXEMPT_MODULES:
            continue

        src_dir = mod_dir / "src"
        if not src_dir.is_dir():
            continue

        violations_by_file = _check_module_source(src_dir)

        if not violations_by_file:
            continue

        _header_printed = False
        for py_file, violations in sorted(violations_by_file.items()):
            rel_path = py_file.relative_to(src_dir)
            for lineno, import_stmt in violations:
                if not _header_printed:
                    print(f"[{mod_name}] Direct use of privatized org-context primitive(s):")
                    _header_printed = True
                print(f"  {rel_path}:{lineno}  {import_stmt}")
                all_violations.append((mod_name, rel_path, lineno, import_stmt))

    # ---- Scan quickscale_core/src/ as well (CR-SA13.1-001) ----------------
    # The core package owns the social managed-view generator and other
    # repo-owned emitters.  Scanning here catches any future direct Python-level
    # imports of the privatized primitives from core code.  Template-string
    # usages inside generated-file renderers are not AST-detectable; those
    # must be resolved by migrating the generator to emit org_scope instead
    # (done in SA13.1 follow-up).
    if core_src_root.is_dir():
        core_violations = _check_module_source(core_src_root)
        if core_violations:
            _header_printed = False
            for py_file, violations in sorted(core_violations.items()):
                rel_path = py_file.relative_to(core_src_root)
                for lineno, import_stmt in violations:
                    if not _header_printed:
                        print(
                            "[quickscale_core] Direct use of privatized org-context primitive(s):"
                        )
                        _header_printed = True
                    print(f"  {rel_path}:{lineno}  {import_stmt}")
                    all_violations.append(("quickscale_core", rel_path, lineno, import_stmt))

    total = len(all_violations)
    if total == 0:
        print(
            "No direct external use of privatized org-context primitives found — "
            "all module imports respect the SA13.1 boundary."
        )
    else:
        print(
            f"\n⚠️  {total} direct use(s) of privatized org-context primitive(s) found "
            f"(warn-only during SA13.1–SA13.3).\n"
            f"These should be migrated to `org_scope` / `PublicSystemOrgReadMixin` "
            f"in SA13.2/SA13.3.\n"
            f"Primitives flagged: {', '.join(sorted(PRIVATIZED_PRIMITIVES))}\n"
            f"Exempt modules: {', '.join(sorted(EXEMPT_MODULES))}\n"
            f"`org_scope` and other public symbols are never flagged."
        )

    # Warn-only: always exit 0 during SA13.1–SA13.3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
