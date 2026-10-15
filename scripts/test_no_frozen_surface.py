"""
Fail when a gate-parity test reintroduces a frozen pre-split surface.

SA267's slices split the gate scripts into facades plus private siblings and
added a parity test per family whose ``FROZEN_SURFACE`` pinned every
module-level name the pre-split module published.  SA267 has closed, so SA278
deleted those name lists; every gate-parity file keeps only its behavioral
corpus and its structural invariants.  This control keeps the retirement
closed: a ``test_*_parity.py`` directly under ``scripts/`` that defines a
module-level ``FROZEN_*`` name fails the suite.

Scope is the gate-parity tests directly under ``scripts/``; SA279 extends the
same rule to the conformance harness under ``scripts/tests_module_conventions/``.
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


def test_no_frozen_surface_survives_under_scripts() -> None:
    """A closed split leaves behavioral corpora only, never a frozen surface."""
    frozen: dict[str, list[str]] = {}
    for path in sorted(_SCRIPTS_DIR.glob(_PARITY_PATTERN)):
        names = _frozen_surface_names(path)
        if names:
            frozen[path.name] = names
    assert frozen == {}
