"""
Parity controls for the SA267(d) ``check_module_core_imports`` refactor.

The module keeps its pre-split surface; ``main`` was decomposed into private
helpers without moving any name.  These controls pin the preserved surface,
the callable homes and signatures, and the exact gate diagnostics captured
from the pre-split module, so a later slice cannot silently drop, relocate,
or reword them.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any

import check_module_core_imports as imports_gate
import pytest

#: Every pre-split name consumers reach through the module.  The refactor must
#: keep every one of them.
FROZEN_SURFACE = (
    "ALLOWED_CORE_IMPORTS",
    "CORE_SRC_RELATIVE",
    "MODULES_DIR_RELATIVE",
    "Path",
    "REPO_ROOT_ENV",
    "_CoreImportLinterVisitor",
    "_DEFAULT_REPO_ROOT",
    "_ModulesImportLinterVisitor",
    "_ScanResults",
    "_check_core_source",
    "_check_module_source",
    "_parse_source_file",
    "annotations",
    "ast",
    "main",
    "os",
    "sys",
)

#: Every pre-split callable; the in-place refactor moves none of them.
FROZEN_CALLABLE_SURFACE = (
    "_CoreImportLinterVisitor",
    "_ModulesImportLinterVisitor",
    "_ScanResults",
    "_check_core_source",
    "_check_module_source",
    "_parse_source_file",
    "main",
)

#: The pre-split signature of every callable consumers invoke.
FROZEN_SIGNATURES = {
    "_check_core_source": "(source_dir: 'Path') -> '_ScanResults'",
    "_check_module_source": "(source_dir: 'Path', module_name: 'str') -> '_ScanResults'",
    "_parse_source_file": "(py_file: 'Path', results: '_ScanResults') -> 'ast.AST | None'",
    "main": "(argv: 'list[str] | None' = None) -> 'int'",
}


def _normalized_signature(function: Callable[..., Any]) -> str:
    return str(inspect.signature(function))


def test_module_surface_is_preserved() -> None:
    """Every pre-split name stays reachable on the module."""
    missing = [name for name in FROZEN_SURFACE if not hasattr(imports_gate, name)]
    assert missing == []


def test_frozen_callable_signatures_are_unchanged() -> None:
    """Each callable consumers invoke keeps its pre-split signature."""
    observed = {
        name: _normalized_signature(getattr(imports_gate, name)) for name in FROZEN_SIGNATURES
    }
    assert observed == FROZEN_SIGNATURES


def test_pre_split_callables_stay_in_the_module() -> None:
    """The in-place refactor relocates no callable to another module."""
    observed = {name: getattr(imports_gate, name).__module__ for name in FROZEN_CALLABLE_SURFACE}
    assert observed == dict.fromkeys(FROZEN_CALLABLE_SURFACE, "check_module_core_imports")


def _write_module_source(root: Path, body: str) -> None:
    source = root / "quickscale_modules" / "demo" / "src"
    source.mkdir(parents=True)
    (source / "demo.py").write_text(body, encoding="utf-8")


def _write_core_source(root: Path, body: str) -> None:
    source = root / "quickscale_core" / "src" / "quickscale_core"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text(body, encoding="utf-8")


def test_missing_scan_roots_keep_exact_messages(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A repository without either scan root keeps its pre-split diagnostics."""
    assert imports_gate.main([str(tmp_path)]) == 1
    captured = capsys.readouterr()
    assert captured.err.splitlines() == [
        f"ERROR: Required scan root not found: {tmp_path / 'quickscale_modules'}; "
        "cannot perform forward direction scan.",
        f"ERROR: Required scan root not found: "
        f"{tmp_path / 'quickscale_core' / 'src' / 'quickscale_core'}; "
        "cannot perform reverse direction scan.",
        "ERROR: One or more required scan roots were not found; gate cannot verify the boundary.",
    ]
    assert captured.out == ""


def test_clean_repository_keeps_exact_success_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A boundary-respecting repository keeps its pre-split success text."""
    _write_module_source(tmp_path, "from quickscale_core.runtime import settings\n")
    _write_core_source(tmp_path, "import django\n")
    assert imports_gate.main([str(tmp_path)]) == 0
    assert capsys.readouterr().out == (
        "All imports respect the core↔module boundary:\n"
        "  • Module code imports only from the public runtime facades.\n"
        "  • Core source has zero imports from quickscale_modules.\n"
    )


def test_forward_violation_keeps_exact_lines_and_exit_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A disallowed module import keeps its pre-split lines and exit code."""
    _write_module_source(tmp_path, "from quickscale_core.dr_engine import adapter\n")
    _write_core_source(tmp_path, "import django\n")
    assert imports_gate.main([str(tmp_path)]) == 1
    assert capsys.readouterr().out == (
        "[demo] Core import boundary violations:\n"
        "  demo.py:1  quickscale_core.dr_engine\n"
        "\n"
        "1 import boundary violation(s) found.\n"
        "Module code must import from one of: "
        "quickscale_core.runtime, quickscale_core.runtime.manifest\n"
        "All module code must use the public quickscale_core.runtime facade.\n"
        "Core source must not import from quickscale_modules at all.\n"
    )


def test_reverse_violation_keeps_exact_lines_and_exit_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A core import of a module keeps its pre-split lines and exit code."""
    _write_module_source(tmp_path, "import django\n")
    _write_core_source(tmp_path, "from quickscale_modules.auth import views\n")
    assert imports_gate.main([str(tmp_path)]) == 1
    assert capsys.readouterr().out == (
        "Core source import boundary violations (quickscale_modules prohibited):\n"
        "  __init__.py:1  quickscale_modules.auth\n"
        "\n"
        "1 import boundary violation(s) found.\n"
        "Module code must import from one of: "
        "quickscale_core.runtime, quickscale_core.runtime.manifest\n"
        "All module code must use the public quickscale_core.runtime facade.\n"
        "Core source must not import from quickscale_modules at all.\n"
    )


def test_unreadable_source_keeps_fail_closed_diagnostic(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An undecodable file keeps its pre-split fail-closed wording."""
    source = tmp_path / "quickscale_modules" / "demo" / "src"
    source.mkdir(parents=True)
    broken = source / "demo.py"
    broken.write_bytes(b"\xff\xfe\x00not utf-8")
    _write_core_source(tmp_path, "import django\n")
    assert imports_gate.main([str(tmp_path)]) == 1
    captured = capsys.readouterr()
    assert captured.err.splitlines() == [
        f"ERROR: Unable to inspect {broken}: read failed: "
        "'utf-8' codec can't decode byte 0xff in position 0: invalid start byte",
        "ERROR: 1 source file(s) could not be inspected; gate cannot verify the boundary.",
    ]


def test_syntax_error_source_keeps_fail_closed_diagnostic(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A syntactically invalid file keeps its pre-split fail-closed wording."""
    source = tmp_path / "quickscale_modules" / "demo" / "src"
    source.mkdir(parents=True)
    broken = source / "demo.py"
    broken.write_text("def broken(:\n", encoding="utf-8")
    _write_core_source(tmp_path, "import django\n")
    assert imports_gate.main([str(tmp_path)]) == 1
    captured = capsys.readouterr()
    assert captured.err.splitlines()[0].startswith(
        f"ERROR: Unable to inspect {broken}: AST parse failed:"
    )
    assert captured.err.splitlines()[-1] == (
        "ERROR: 1 source file(s) could not be inspected; gate cannot verify the boundary."
    )
