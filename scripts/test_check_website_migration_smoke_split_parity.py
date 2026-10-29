"""
Behavioral controls for the SA267(d) ``check_website_migration_smoke`` script split.

SA267 has closed, so SA278 retired the pre-split surface pins; these controls
keep the split's structural invariants and the exact gate diagnostics
captured from the pre-split module as behavioral tests, so a later change
cannot silently drop, reorder, or reword them.
"""

from __future__ import annotations

import ast
from pathlib import Path

import check_website_migration_smoke as smoke
import pytest

#: ``(module, facade module name)`` for every private sibling; a sibling must
#: never import its own facade back.
SPLIT_SIBLINGS = {
    "_website_migration_smoke_cases": "check_website_migration_smoke",
    "_website_migration_smoke_support": "check_website_migration_smoke",
}


def test_split_siblings_never_import_their_facade() -> None:
    """Siblings reach collaborators through defining siblings, never the facade."""
    for module_name, facade in SPLIT_SIBLINGS.items():
        module = __import__(module_name)
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[-1] != facade, (module_name, node.lineno)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[-1] != facade, (module_name, node.lineno)


# ---------------------------------------------------------------------------
# Diagnostics captured from the pre-split module
# ---------------------------------------------------------------------------


def test_require_keeps_its_exact_diagnostic() -> None:
    """The shared assertion helper keeps its pre-split exception and text."""
    with pytest.raises(smoke.SmokeError) as excinfo:
        smoke._require(False, "synthetic smoke failure")
    assert str(excinfo.value) == "synthetic smoke failure"


def test_fixture_generation_guard_keeps_exact_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Generating a fixture without the lock guard keeps its pre-split wording."""
    monkeypatch.delenv("QS_SKIP_POETRY_LOCK", raising=False)
    with pytest.raises(smoke.SmokeError) as excinfo:
        smoke._generate_project(tmp_path, "guard-probe")
    assert str(excinfo.value) == (
        "smoke fixture generation must disable real Poetry lock execution"
    )


def test_project_app_guard_keeps_exact_message(tmp_path: Path) -> None:
    """Re-writing an existing project app keeps its pre-split wording."""
    app = tmp_path / "properties"
    app.mkdir()
    (app / "__init__.py").write_text("")
    with pytest.raises(smoke.SmokeError) as excinfo:
        smoke._write_project_app(tmp_path, "properties")
    assert str(excinfo.value) == f"project app properties already exists in {tmp_path}"
