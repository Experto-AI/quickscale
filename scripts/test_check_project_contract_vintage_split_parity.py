"""
Behavioral controls for the SA267(d) ``check_project_contract_vintage`` script split.

SA267 has closed, so SA278 retired the pre-split surface pins; these controls
keep the split's structural invariants and the exact gate diagnostics
captured from the pre-split module as behavioral tests, so a later change
cannot silently drop, reorder, or reword them.
"""

from __future__ import annotations

import ast
from pathlib import Path

import check_project_contract_vintage as vintage
import pytest

#: ``(module, facade module name)`` for every private sibling; a sibling must
#: never import its own facade back.
SPLIT_SIBLINGS = {
    "_vintage_emission": "check_project_contract_vintage",
    "_vintage_git": "check_project_contract_vintage",
    "_vintage_manifest": "check_project_contract_vintage",
    "_vintage_staged": "check_project_contract_vintage",
}


def test_every_private_sibling_is_covered() -> None:
    """A new ``_vintage_*`` sibling joins the structural control automatically."""
    scripts = Path(vintage.__file__).parent
    siblings = {path.stem for path in scripts.glob("_vintage_*.py")}
    assert siblings == set(SPLIT_SIBLINGS)


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


def test_unsafe_ref_message_is_exact() -> None:
    """An unsafe or empty ref keeps its pre-split fail-closed wording."""
    with pytest.raises(vintage.VintageError) as excinfo:
        vintage._resolve_commit("")
    assert str(excinfo.value) == "unsafe or empty Git ref: ''"


def test_declaration_malformed_message_is_exact() -> None:
    """A declaration without a steps list keeps its pre-split wording."""
    with pytest.raises(vintage.VintageError) as excinfo:
        vintage._declared_step_ids("steps: notalist\n", "at deadbeef")
    assert str(excinfo.value) == (
        f"{vintage.DECLARATION_PATH} at deadbeef must declare a 'steps' list"
    )


def test_module_vintage_malformed_message_is_exact() -> None:
    """A manifest that is not valid YAML keeps its pre-split wording."""
    with pytest.raises(vintage.VintageError) as excinfo:
        vintage._module_vintage("not: [valid", "probe")
    assert str(excinfo.value).startswith("cannot parse module manifest probe:")


def test_generator_paths_classification_is_exact() -> None:
    """The generator-path filter keeps its pre-split classification."""
    assert vintage._generator_paths(
        (
            "quickscale_core/src/quickscale_core/generator/x.py",
            "quickscale_core/src/quickscale_core/generator/templates/y.j2",
            "other.py",
        )
    ) == ("quickscale_core/src/quickscale_core/generator/x.py",)


def test_manifest_path_classification_is_exact() -> None:
    """The manifest-path predicate keeps its pre-split classification."""
    assert vintage._is_module_manifest_path("quickscale_modules/auth/module.yml") is True
    assert (
        vintage._is_module_manifest_path(
            "quickscale_core/src/quickscale_core/data/manifests/auth/module.yml"
        )
        is True
    )
    assert vintage._is_module_manifest_path("scripts/module.yml") is False


def test_report_output_is_byte_identical(capsys: pytest.CaptureFixture[str]) -> None:
    """The failure report keeps its pre-split text byte for byte."""
    violation = vintage.Violation(
        "a" * 40,
        "subject line",
        ("quickscale_core/src/quickscale_core/generator/templates/x.j2",),
        reason="no new adoption step id",
    )
    vintage._report((violation,))
    assert capsys.readouterr().err == (
        "ERROR: [PROJECT_CONTRACT_VINTAGE] generated-project contract changes "
        "without a new adoption step id:\n"
        "  aaaaaaaaaaaa subject line (no new adoption step id)\n"
        "    quickscale_core/src/quickscale_core/generator/templates/x.j2\n"
        "\n"
        f"Declare the change in {vintage.DECLARATION_PATH} under a new adoption step id "
        "in the same commit, or give the changed module manifest step a new id "
        "(see the SA207/SA211 declaration blocks).\n"
    )
