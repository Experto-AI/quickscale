"""
Behavioral controls for the SA267(d) ``check_module_core_compatibility`` script split.

SA267 has closed, so SA278 retired the pre-split surface pins; these controls
keep the split's structural invariants and the exact gate diagnostics
captured from the pre-split module as behavioral tests, so a later change
cannot silently drop, reorder, or reword them.
"""

from __future__ import annotations

import ast
from pathlib import Path

import check_module_core_compatibility as compat
import pytest

#: ``(module, facade module name)`` for every private sibling; a sibling must
#: never import its own facade back.
SPLIT_SIBLINGS = {
    "_module_core_compat_ast": "check_module_core_compatibility",
    "_module_core_compat_probe": "check_module_core_compatibility",
    "_module_core_compat_versions": "check_module_core_compatibility",
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


def test_version_helpers_keep_their_pre_split_semantics() -> None:
    """The lockstep-spec derivation keeps its exact pre-split results."""
    assert compat._expected_core_spec("0.88.0") == ">=0.88.0,<0.89.0"
    assert compat._extract_min_core_version(">=0.86.0,<0.87.0") == "0.86.0"
    assert compat._extract_min_core_version("^0.86") is None
    assert compat._declared_core_spec("quickscale-core>=0.1.0") == ">=0.1.0"


def test_poetry_spec_conversion_is_exact() -> None:
    """The Poetry-to-PEP 440 conversion keeps its pre-split forms."""
    assert compat._poetry_spec_to_pep440("^1.2.3") == ">=1.2.3,<2.0.0"
    assert compat._poetry_spec_to_pep440("^0.5") == ">=0.5,<0.6.0"
    assert compat._poetry_spec_to_pep440("~1.2.3") == ">=1.2.3,<1.3.0"
    assert compat._poetry_spec_to_pep440(">=1.0") == ">=1.0"


def test_missing_version_file_keeps_exact_diagnostic(tmp_path: Path) -> None:
    """A missing VERSION file keeps its pre-split fail-closed wording."""
    with pytest.raises(SystemExit) as excinfo:
        compat._read_version_file(tmp_path)
    assert str(excinfo.value) == f"VERSION file not found: {tmp_path / 'VERSION'}"


def test_stale_pin_report_is_byte_identical(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A stale lockstep pin keeps its pre-split report lines and exit code."""
    (tmp_path / "VERSION").write_text("0.89.0", encoding="utf-8")
    (tmp_path / "quickscale_core" / "src").mkdir(parents=True)
    module_dir = tmp_path / "quickscale_modules" / "demo"
    module_dir.mkdir(parents=True)
    (module_dir / "module.yml").write_text(
        "name: demo\ndependencies:\n  - quickscale-core\n", encoding="utf-8"
    )
    (module_dir / "pyproject.toml").write_text(
        '[tool.poetry.dependencies]\nquickscale-core = ">=0.1.0,<0.2.0"\n',
        encoding="utf-8",
    )
    assert compat.main([str(tmp_path)]) == 1
    assert capsys.readouterr().out == (
        "Repository core version: 0.89.0\n"
        "\n"
        "[demo] quickscale-core dependency: quickscale-core\n"
        "  FAIL: lockstep pin is >=0.1.0,<0.2.0; expected >=0.89.0,<0.90.0 "
        "for core 0.89.0.\n"
        "  SKIP: No src/ directory — cannot check imports.\n"
        "One or more compatibility issues found.\n"
    )
