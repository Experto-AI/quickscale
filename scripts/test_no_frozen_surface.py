"""
Fail when a parity test reintroduces a frozen pre-split surface.

SA267's and SA268's slices split the gate scripts and the conformance harness
into facades plus private siblings and added a parity test per family whose
``FROZEN_SURFACE`` pinned every module-level name the pre-split module
published.  SA267 and SA268 have closed, so SA278 retired the gate-parity name
lists and SA279 the harness's; every parity file keeps only its behavioral
corpus and its structural invariants.  This control keeps the retirement
closed: a ``test_*_parity.py`` anywhere under ``scripts/`` that defines a
module-level ``FROZEN_*`` name fails the suite.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_PARITY_PATTERN = "test_*_parity.py"


def _bound_targets(statement: ast.stmt) -> list[ast.expr]:
    """Return the assignment targets a module-level statement binds."""
    if isinstance(statement, ast.Assign):
        return list(statement.targets)
    if isinstance(statement, ast.AnnAssign):
        return [statement.target]
    return []


def _frozen_names(target: ast.expr) -> list[str]:
    """Return every ``FROZEN_*`` name one assignment target binds."""
    if isinstance(target, ast.Name):
        return [target.id] if target.id.startswith("FROZEN_") else []
    if isinstance(target, (ast.Tuple, ast.List)):
        names: list[str] = []
        for element in target.elts:
            names.extend(_frozen_names(element))
        return names
    return []


def _frozen_surface_names(path: Path) -> list[str]:
    """Return every module-level ``FROZEN_*`` name a parity file defines."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for statement in tree.body:
        for target in _bound_targets(statement):
            names.extend(_frozen_names(target))
    return names


def _frozen_surfaces(root: Path) -> dict[str, list[str]]:
    """Return every parity file under *root* that defines a ``FROZEN_*`` name."""
    frozen: dict[str, list[str]] = {}
    for path in sorted(root.rglob(_PARITY_PATTERN)):
        names = _frozen_surface_names(path)
        if names:
            frozen[str(path.relative_to(root))] = names
    return frozen


def test_no_frozen_surface_survives_under_scripts() -> None:
    """A closed split leaves behavioral corpora only, never a frozen surface."""
    assert _frozen_surfaces(_SCRIPTS_DIR) == {}


def test_nested_parity_file_is_discovered(tmp_path: Path) -> None:
    """A parity file in a nested harness package still fails the guard."""
    nested = tmp_path / "tests_module_conventions" / "routes"
    nested.mkdir(parents=True)
    (nested / "test_routes_parity.py").write_text(
        'FROZEN_SURFACE = ("rule_7_urls",)\n', encoding="utf-8"
    )
    assert _frozen_surfaces(tmp_path) == {
        "tests_module_conventions/routes/test_routes_parity.py": ["FROZEN_SURFACE"]
    }
