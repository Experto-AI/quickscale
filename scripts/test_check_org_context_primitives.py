"""
Fixture controls for the org-context primitives gate (SA326).

Each control pins one accepted or rejected form: the direct
``from quickscale_modules_orgs.current_org import <primitive>`` import, the
compatibility aliases, the re-export ``from quickscale_modules_orgs import
current_org`` form, and every attribute use of a primitive through a bound
``current_org`` module object.  The visitor tests need no filesystem; the
end-to-end cases build a temporary module tree so the gate's scan, output and
exit codes are exercised together.
"""

from __future__ import annotations

import ast
from pathlib import Path

from scripts.check_org_context_primitives import _OrgContextPrimitivesVisitor, main


def _violations(source: str) -> list[tuple[int, str]]:
    """Return the visitor's findings for one source string."""
    visitor = _OrgContextPrimitivesVisitor()
    visitor.visit(ast.parse(source))
    return visitor.violations


def _module_tree(root: Path, module: str, source: str) -> Path:
    """Write one module source file under a temporary repository root."""
    source_dir = root / "quickscale_modules" / module / "src"
    source_dir.mkdir(parents=True)
    (source_dir / "views.py").write_text(source, encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# Direct imports
# ---------------------------------------------------------------------------


def test_direct_private_import_is_flagged() -> None:
    """A direct import of an underscored primitive is a violation."""
    assert _violations("from quickscale_modules_orgs.current_org import _tenant_context\n")


def test_compatibility_alias_import_is_flagged() -> None:
    """The legacy public alias is still a privatized primitive."""
    assert _violations("from quickscale_modules_orgs.current_org import set_db_current_org_id\n")


def test_org_scope_import_passes() -> None:
    """``org_scope`` is the permanent public API and is exempt."""
    assert _violations("from quickscale_modules_orgs.current_org import org_scope\n") == []


# ---------------------------------------------------------------------------
# The re-export form
# ---------------------------------------------------------------------------


def test_from_package_import_current_org_is_flagged() -> None:
    """The re-export form is refused at the import line."""
    violations = _violations("from quickscale_modules_orgs import current_org\n")
    assert violations == [(1, "from quickscale_modules_orgs import current_org")]


def test_aliased_from_package_import_current_org_is_flagged() -> None:
    """Aliasing the re-export does not hide the refused form."""
    assert _violations("from quickscale_modules_orgs import current_org as co\n")


def test_from_package_import_other_symbol_passes() -> None:
    """Importing a public symbol from the package is not the refused form."""
    assert _violations("from quickscale_modules_orgs import org_scope\n") == []


# ---------------------------------------------------------------------------
# Attribute use through a bound module object
# ---------------------------------------------------------------------------


def test_imported_module_object_attribute_is_flagged() -> None:
    """``import ...current_org`` followed by a primitive attribute use fails."""
    source = (
        "import quickscale_modules_orgs.current_org\n"
        "with quickscale_modules_orgs.current_org._tenant_context(org):\n"
        "    pass\n"
    )
    assert _violations(source) == [(2, "quickscale_modules_orgs.current_org._tenant_context")]


def test_aliased_module_object_attribute_is_flagged() -> None:
    """A module-object alias still reaches the same privatized primitive."""
    source = (
        "import quickscale_modules_orgs.current_org as co\n"
        "co.set_current_org_for_context(request)\n"
    )
    assert _violations(source) == [(2, "co.set_current_org_for_context")]


def test_package_binding_attribute_chain_is_flagged() -> None:
    """``import quickscale_modules_orgs`` plus the full chain is refused."""
    source = (
        "import quickscale_modules_orgs as orgs\norgs.current_org._set_db_current_org_id(org_id)\n"
    )
    assert _violations(source) == [(2, "orgs.current_org._set_db_current_org_id")]


def test_package_binding_without_primitive_passes() -> None:
    """Holding the package binding alone is not a violation."""
    assert _violations("import quickscale_modules_orgs as orgs\n") == []


def test_module_object_non_primitive_attribute_passes() -> None:
    """A non-privatized attribute on the module object stays allowed."""
    source = "import quickscale_modules_orgs.current_org as co\nco.org_scope\n"
    assert _violations(source) == []


# ---------------------------------------------------------------------------
# End-to-end scan and exit codes
# ---------------------------------------------------------------------------


def test_clean_tree_exits_zero(tmp_path: Path, capsys) -> None:
    """A module tree with only public imports passes."""
    _module_tree(
        tmp_path,
        "demo",
        "from quickscale_modules_orgs.current_org import org_scope\n",
    )
    assert main([str(tmp_path)]) == 0
    assert "No direct external use" in capsys.readouterr().out


def test_violation_exits_one(tmp_path: Path, capsys) -> None:
    """The end-to-end gate reports the refused import form and exits 1."""
    _module_tree(
        tmp_path,
        "demo",
        "from quickscale_modules_orgs import current_org\n",
    )
    assert main([str(tmp_path)]) == 1
    output = capsys.readouterr().out
    assert "from quickscale_modules_orgs import current_org" in output


def test_orgs_module_is_exempt(tmp_path: Path) -> None:
    """The orgs module may use its own primitives internally."""
    _module_tree(
        tmp_path,
        "orgs",
        "from quickscale_modules_orgs.current_org import _tenant_context\n",
    )
    assert main([str(tmp_path)]) == 0


def test_missing_modules_directory_exits_two(tmp_path: Path, capsys) -> None:
    """A repository root without the module workspace fails closed."""
    assert main([str(tmp_path)]) == 2
    assert "Modules directory not found" in capsys.readouterr().err
