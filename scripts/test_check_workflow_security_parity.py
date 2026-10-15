"""
Behavioral controls for the SA267(c) ``check_workflow_security`` refactor.

SA267 has closed, so SA278 retired the pre-split surface pins; these controls
keep the exact gate diagnostics captured from the pre-split module as
behavioral tests, so a later change cannot silently drop, reorder, or reword
them.
"""

from __future__ import annotations

import json
from pathlib import Path

import check_workflow_security as workflow_gate
import pytest

FINDING = {
    "ident": "unpinned-uses",
    "desc": "unpinned action reference",
    "locations": [
        {
            "symbolic": {"key": {"Local": {"verbatim_path": ".github/workflows/x.yml"}}},
            "concrete": {"location": {"start_point": {"row": 9, "column": 15}}},
        }
    ],
}


def test_pinned_version_missing_pin_keeps_exact_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A missing or non-exact pin keeps its pre-split wording."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[tool.poetry]\nname = "probe"\n', encoding="utf-8")
    monkeypatch.setattr(workflow_gate, "PYPROJECT_PATH", pyproject)
    with pytest.raises(workflow_gate.GateError) as excinfo:
        workflow_gate._pinned_version()
    assert str(excinfo.value) == (
        f"{pyproject} must pin zizmor to an exact version under "
        "[tool.poetry.group.dev.dependencies]"
    )


def test_pinned_version_unreadable_keeps_exact_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A pyproject that cannot be decoded keeps its pre-split wording."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_bytes(b"\xff\xfe\x00not utf-8")
    monkeypatch.setattr(workflow_gate, "PYPROJECT_PATH", pyproject)
    with pytest.raises(workflow_gate.GateError) as excinfo:
        workflow_gate._pinned_version()
    assert str(excinfo.value).startswith(f"could not read {pyproject}:")


def test_missing_executable_keeps_exact_remediation(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing zizmor keeps its pre-split remediation and pinned version."""
    monkeypatch.setattr(workflow_gate, "_resolve_zizmor", lambda: None)
    with pytest.raises(workflow_gate.GateError) as excinfo:
        workflow_gate._require_executable("1.30.0")
    assert str(excinfo.value) == (
        "zizmor executable not found on PATH. pyproject.toml pins zizmor 1.30.0 "
        "as a Poetry dev dependency — run: poetry install"
    )


def test_missing_target_keeps_exact_message(tmp_path: Path) -> None:
    """A missing workflow target keeps its pre-split wording."""
    absent = tmp_path / "absent"
    with pytest.raises(workflow_gate.GateError) as excinfo:
        workflow_gate._workflow_target([str(absent)])
    assert str(excinfo.value) == f"workflow target not found: {absent}"


def test_parse_report_rejections_keep_exact_messages() -> None:
    """Every malformed zizmor report keeps its pre-split diagnostic."""
    with pytest.raises(workflow_gate.GateError) as excinfo:
        workflow_gate._parse_zizmor_report("not json", "")
    assert str(excinfo.value).startswith("unparseable zizmor report:")
    with pytest.raises(workflow_gate.GateError) as excinfo:
        workflow_gate._parse_zizmor_report("{}", "")
    assert str(excinfo.value) == "unexpected zizmor report shape: dict"
    with pytest.raises(workflow_gate.GateError) as excinfo:
        workflow_gate._parse_zizmor_report("[1]", "")
    assert str(excinfo.value) == "unexpected zizmor finding shape"


def test_finding_location_format_is_exact() -> None:
    """The finding location renders as ``path:row:column`` with stable placeholders."""
    assert workflow_gate._finding_path(FINDING) == ".github/workflows/x.yml"
    assert workflow_gate._finding_position(FINDING) == "9:15"
    assert workflow_gate._finding_path({}) == "<unknown file>"
    assert workflow_gate._finding_position({}) == "?"


def test_cli_argument_parsing_is_preserved() -> None:
    """The flag extraction keeps its pre-split semantics and order."""
    assert workflow_gate._parse_cli_arguments(["--preflight"]) == (True, False, [])
    assert workflow_gate._parse_cli_arguments(["--generated-template", "dir"]) == (
        False,
        True,
        ["dir"],
    )
    assert workflow_gate._parse_cli_arguments(["dir"]) == (False, False, ["dir"])


def _workflow_directory(tmp_path: Path, *, body: str = "permissions: {}\n") -> Path:
    directory = tmp_path / ".github" / "workflows"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "fixture.yml").write_text(body, encoding="utf-8")
    return directory


def _install_scan_probe(
    monkeypatch: pytest.MonkeyPatch, *, report: str, returncode: int = 0
) -> None:
    monkeypatch.setattr(workflow_gate, "_resolve_zizmor", lambda: "zizmor")
    monkeypatch.setattr(
        workflow_gate,
        "_run_zizmor",
        lambda _executable, _target: (returncode, report, ""),
    )


def test_clean_run_keeps_exact_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A clean scan keeps its pre-split success line and exit code."""
    directory = _workflow_directory(tmp_path)
    _install_scan_probe(monkeypatch, report="[]")
    assert workflow_gate.main([str(directory)]) == 0
    assert capsys.readouterr().out == f"workflow security gate clean: {directory}\n"


def test_findings_keep_exact_lines_and_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A finding keeps its pre-split location line, total line, and exit code."""
    directory = _workflow_directory(tmp_path)
    _install_scan_probe(monkeypatch, report=json.dumps([FINDING]), returncode=14)
    assert workflow_gate.main([str(directory)]) == 1
    captured = capsys.readouterr()
    assert captured.err.splitlines()[-1] == "workflow security findings: 1"
    assert ".github/workflows/x.yml:9:15: unpinned-uses: unpinned action reference" in (
        captured.err
    )


def test_missing_permissions_keeps_exact_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A workflow without a top-level permissions block keeps its pre-split lines."""
    directory = _workflow_directory(tmp_path, body="name: Fixture\n")
    _install_scan_probe(monkeypatch, report="[]")
    assert workflow_gate.main([str(directory)]) == 1
    captured = capsys.readouterr()
    fixture = directory / "fixture.yml"
    assert (
        f"{fixture}: missing-top-level-permissions: no workflow-level permissions block"
        in captured.err
    )
    assert captured.err.splitlines()[-1] == "workflow security findings: 1"


def test_empty_report_with_findings_status_keeps_exact_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty report paired with a findings exit keeps its pre-split diagnostic."""
    directory = _workflow_directory(tmp_path)
    _install_scan_probe(monkeypatch, report="[]", returncode=14)
    with pytest.raises(workflow_gate.GateError) as excinfo:
        workflow_gate.main([str(directory)])
    assert str(excinfo.value) == "zizmor exited 14 with an empty report"
