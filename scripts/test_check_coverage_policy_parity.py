"""
Behavioral controls for the SA267(d) ``check_coverage_policy`` refactor.

SA267 has closed, so SA278 retired the pre-split surface pins; these controls
keep the exact policy diagnostics captured from the pre-split module as
behavioral tests, so a later change cannot silently drop, reorder, or reword
them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import check_coverage_policy as coverage_gate
import pytest


def _coverage_document(files: dict[str, Any]) -> dict[str, Any]:
    return {"files": files, "totals": {}}


def _write_coverage(tmp_path: Path, files: dict[str, Any]) -> Path:
    path = tmp_path / "coverage.json"
    path.write_text(json.dumps(_coverage_document(files)), encoding="utf-8")
    return path


def _summary(covered: int, statements: int, percent: float) -> dict[str, Any]:
    return {
        "covered_lines": covered,
        "num_statements": statements,
        "percent_covered": percent,
    }


def test_file_classification_keeps_its_pre_split_semantics() -> None:
    """Canonical package paths classify; traversal and self-reference do not."""
    assert coverage_gate._classify_file("quickscale_core/a.py") == "quickscale_core"
    assert coverage_gate._classify_file("quickscale_cli/b.py") == "quickscale_cli"
    assert coverage_gate._classify_file("./quickscale_core/a.py") is None
    assert coverage_gate._classify_file("quickscale_core/../other.py") is None
    assert coverage_gate._classify_file("other/a.py") is None


def test_passing_report_keeps_exact_output_and_exit_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A passing fixture keeps its pre-split report lines and exit code."""
    path = _write_coverage(
        tmp_path,
        {
            "quickscale_core/a.py": {"summary": _summary(19, 20, 95.0)},
            "quickscale_cli/b.py": {"summary": _summary(19, 20, 95.0)},
        },
    )
    assert coverage_gate.check_policy(str(path)) == 0
    assert capsys.readouterr().out == (
        "Coverage Policy Check (equal-weight package mean)\n"
        "  Mean threshold:       90.0%\n"
        "  Per-file threshold:   80.0%\n"
        "  Files measured:       2\n"
        "  Packages found:       2\n"
        "    quickscale_cli: 95.00%  (19/20 stmts)\n"
        "    quickscale_core: 95.00%  (19/20 stmts)\n"
        "  Equal-weight mean:    95.00%\n"
        "  Equal-weight mean 95.00% meets 90.0% threshold\n"
        "  All 2 files meet 80.0% per-file threshold\n"
    )


def test_failing_report_keeps_exact_output_and_exit_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A failing fixture keeps its pre-split report lines and exit code."""
    path = _write_coverage(
        tmp_path,
        {
            "quickscale_core/a.py": {"summary": _summary(10, 10, 100.0)},
            "quickscale_cli/b.py": {"summary": _summary(5, 10, 50.0)},
        },
    )
    assert coverage_gate.check_policy(str(path)) == 1
    assert capsys.readouterr().out == (
        "Coverage Policy Check (equal-weight package mean)\n"
        "  Mean threshold:       90.0%\n"
        "  Per-file threshold:   80.0%\n"
        "  Files measured:       2\n"
        "  Packages found:       2\n"
        "    quickscale_cli: 50.00%  (5/10 stmts)\n"
        "    quickscale_core: 100.00%  (10/10 stmts)\n"
        "  Equal-weight mean:    75.00%\n"
        "  FAIL - equal-weight mean 75.00% is below 90.0%\n"
        "  FAIL - 1 file(s) below 80.0%:\n"
        "      quickscale_cli/b.py: 50.00% (5/10)\n"
    )


def test_missing_required_package_keeps_exact_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A coverage set without the CLI package keeps its pre-split diagnostic."""
    path = _write_coverage(
        tmp_path,
        {"quickscale_core/a.py": {"summary": _summary(19, 20, 95.0)}},
    )
    assert coverage_gate.check_policy(str(path)) == 2
    captured = capsys.readouterr()
    assert captured.err.splitlines()[-1] == (
        "ERROR: Coverage data missing required package(s): quickscale_cli. "
        "Both quickscale_core and quickscale_cli must have measured files."
    )


def test_unknown_path_keeps_exact_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A file outside the recognised trees keeps its pre-split diagnostic."""
    path = _write_coverage(
        tmp_path,
        {
            "quickscale_core/a.py": {"summary": _summary(19, 20, 95.0)},
            "quickscale_cli/b.py": {"summary": _summary(19, 20, 95.0)},
            "other/c.py": {"summary": _summary(1, 1, 100.0)},
        },
    )
    assert coverage_gate.check_policy(str(path)) == 2
    captured = capsys.readouterr()
    assert captured.err.splitlines() == [
        "ERROR: Found files outside recognised package trees (quickscale_core, quickscale_cli):",
        "    other/c.py",
    ]


def test_zero_statements_package_keeps_exact_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A package with no measurable statements keeps its pre-split diagnostic."""
    path = _write_coverage(
        tmp_path,
        {
            "quickscale_core/a.py": {"summary": _summary(0, 0, 100.0)},
            "quickscale_cli/b.py": {"summary": _summary(19, 20, 95.0)},
        },
    )
    assert coverage_gate.check_policy(str(path)) == 2
    captured = capsys.readouterr()
    assert captured.err.splitlines()[-1] == (
        "ERROR: Package 'quickscale_core' has 0 measurable statements."
    )


def test_missing_coverage_file_keeps_exact_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A missing coverage file keeps its pre-split diagnostic and exit code."""
    absent = tmp_path / "absent.json"
    assert coverage_gate.check_policy(str(absent)) == 2
    captured = capsys.readouterr()
    assert captured.err.splitlines()[-1] == f"ERROR: Coverage JSON not found: {absent}"
