"""
Hermetic contracts for the workflow-security gate (SA202).

The gate's contract is exercised with a fake ``zizmor`` on ``PATH`` so the
suite needs no network access.  The acceptance-critical half -- that the gate
fails on an unpinned ``uses:`` ref and on a workflow missing a top-level
``permissions:`` block -- is proven against the real ``zizmor`` audit rules on
fixture workflows, and skipped only when the tool is absent from the
environment.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

import scripts.check_workflow_security as workflow_gate

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKER = REPO_ROOT / "scripts" / "check_workflow_security.py"
PYPROJECT = REPO_ROOT / "pyproject.toml"
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
REAL_ZIZMOR = shutil.which("zizmor")
PINNED_ZIZMOR = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["tool"]["poetry"]["group"][
    "dev"
]["dependencies"]["zizmor"]

PINNED_CHECKOUT = "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v6.1.0"


def _run(arguments: list[str], path: str | None = None) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    if path is not None:
        environment["PATH"] = path
    return subprocess.run(
        [sys.executable, str(CHECKER), *arguments],
        capture_output=True,
        text=True,
        timeout=120,
        env=environment,
        check=False,
    )


def _fake_zizmor(tmp_path: Path, payload: str, exit_code: int) -> Path:
    """Install a fake ``zizmor`` that prints ``payload`` and exits ``exit_code``."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    script = bin_dir / "zizmor"
    script.write_text(
        f"#!{sys.executable}\nimport sys\nsys.stdout.write({payload!r})\nsys.exit({exit_code})\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return bin_dir


def _workflow(tmp_path: Path, body: str) -> Path:
    """Write one fixture workflow and return its path."""
    directory = tmp_path / ".github" / "workflows"
    directory.mkdir(parents=True, exist_ok=True)
    fixture = directory / "fixture.yml"
    fixture.write_text(body, encoding="utf-8")
    return fixture


CLEAN_WORKFLOW = f"""name: Fixture
on: push
permissions:
  contents: read
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: {PINNED_CHECKOUT}
"""


def test_clean_report_exits_zero(tmp_path: Path) -> None:
    """An empty report with a clean status passes the gate."""
    bin_dir = _fake_zizmor(tmp_path, "[]", 0)
    completed = _run([], str(bin_dir))
    assert completed.returncode == 0, completed.stderr
    assert "clean" in completed.stdout


def test_findings_report_exits_one(tmp_path: Path) -> None:
    """A finding report fails the gate and names each finding."""
    finding = [
        {
            "ident": "unpinned-uses",
            "desc": "unpinned action reference",
            "locations": [
                {
                    "symbolic": {"key": {"Local": {"verbatim_path": ".github/workflows/x.yml"}}},
                    "concrete": {"location": {"start_point": {"row": 9, "column": 15}}},
                }
            ],
        }
    ]
    bin_dir = _fake_zizmor(tmp_path, json.dumps(finding), 14)
    completed = _run([], str(bin_dir))
    assert completed.returncode == 1
    assert "unpinned-uses" in completed.stderr
    assert ".github/workflows/x.yml:9:15" in completed.stderr


def test_missing_tool_exits_two(tmp_path: Path) -> None:
    """A missing zizmor executable fails closed."""
    empty = tmp_path / "empty"
    empty.mkdir()
    completed = _run([], str(empty))
    assert completed.returncode == 2
    assert "infrastructure failure" in completed.stderr


def test_missing_tool_names_the_exact_remediation(tmp_path: Path) -> None:
    """The failure must say how to fix it, not just that it's missing."""
    empty = tmp_path / "empty"
    empty.mkdir()
    completed = _run([], str(empty))
    assert completed.returncode == 2
    assert "poetry install" in completed.stderr
    assert PINNED_ZIZMOR in completed.stderr


def test_pinned_version_is_read_from_pyproject() -> None:
    """The version the gate reports is pyproject.toml's pin, not a local copy."""
    assert workflow_gate._pinned_version() == PINNED_ZIZMOR


def test_pinned_version_fails_closed_without_an_exact_pin(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A missing zizmor pin or a non-exact requirement is infrastructure failure."""
    pyproject = tmp_path / "pyproject.toml"
    monkeypatch.setattr(workflow_gate, "PYPROJECT_PATH", pyproject)
    for body in (
        '[tool.poetry]\nname = "probe"\n',
        '[tool.poetry.group.dev.dependencies]\nzizmor = "^1.30"\n',
        "tool = 1\n",
    ):
        pyproject.write_text(body, encoding="utf-8")
        with pytest.raises(workflow_gate.GateError, match="exact version"):
            workflow_gate._pinned_version()


def test_pinned_version_fails_closed_on_an_unreadable_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A pyproject.toml that is not valid UTF-8 is infrastructure failure."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_bytes(b"\xff\xfe\x00not utf-8")
    monkeypatch.setattr(workflow_gate, "PYPROJECT_PATH", pyproject)
    with pytest.raises(workflow_gate.GateError, match="could not read"):
        workflow_gate._pinned_version()


def test_resolved_outside_project_environment_warns_but_still_runs(tmp_path: Path) -> None:
    """A PATH hit outside this interpreter's own env is flagged, not trusted silently."""
    bin_dir = _fake_zizmor(tmp_path, "[]", 0)
    completed = _run([], str(bin_dir))
    assert completed.returncode == 0, completed.stderr
    assert "outside this interpreter's environment" in completed.stderr
    assert "poetry install" in completed.stderr


@pytest.mark.skipif(REAL_ZIZMOR is None, reason="zizmor is not installed")
def test_correctly_synced_environment_does_not_warn() -> None:
    """
    A properly `poetry install`-ed zizmor must not trigger the stray-tool warning.

    Regression for comparing against ``Path(sys.executable).resolve().parent``,
    which follows the venv python's symlink to its base interpreter and lands
    outside ``.venv/bin`` -- so a correctly installed zizmor sitting right next
    to it would spuriously warn on every run, including in CI.
    """
    completed = _run([str(WORKFLOWS)])
    assert completed.returncode == 0, completed.stderr
    assert "outside this interpreter's environment" not in completed.stderr


def test_preflight_reports_ok_without_requiring_workflows(tmp_path: Path) -> None:
    """`make check`'s preflight step only needs zizmor resolution, not a workflow tree."""
    bin_dir = _fake_zizmor(tmp_path, "[]", 0)
    completed = _run(["--preflight"], str(bin_dir))
    assert completed.returncode == 0, completed.stderr
    assert "preflight ok" in completed.stdout


def test_preflight_fails_fast_when_zizmor_is_missing(tmp_path: Path) -> None:
    """The preflight step must exit 2 with the install remediation, like the full run."""
    empty = tmp_path / "empty"
    empty.mkdir()
    completed = _run(["--preflight"], str(empty))
    assert completed.returncode == 2
    assert "poetry install" in completed.stderr


def test_unparseable_report_exits_two(tmp_path: Path) -> None:
    """A report that is not JSON fails closed."""
    bin_dir = _fake_zizmor(tmp_path, "not json", 0)
    completed = _run([], str(bin_dir))
    assert completed.returncode == 2
    assert "unparseable" in completed.stderr


def test_empty_report_with_findings_status_exits_two(tmp_path: Path) -> None:
    """An empty report paired with a findings exit status fails closed."""
    bin_dir = _fake_zizmor(tmp_path, "[]", 14)
    completed = _run([], str(bin_dir))
    assert completed.returncode == 2
    assert "empty report" in completed.stderr


def test_missing_directory_exits_two(tmp_path: Path) -> None:
    """A missing workflow directory fails closed."""
    bin_dir = _fake_zizmor(tmp_path, "[]", 0)
    completed = _run([str(tmp_path / "absent")], str(bin_dir))
    assert completed.returncode == 2
    assert "not found" in completed.stderr


@pytest.mark.skipif(REAL_ZIZMOR is None, reason="zizmor is not installed")
def test_real_zizmor_fails_on_unpinned_uses(tmp_path: Path) -> None:
    """SA202: the gate fails on an unpinned ``uses:`` reference."""
    directory = _workflow(
        tmp_path,
        "name: Fixture\non: push\npermissions:\n  contents: read\n"
        "jobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - uses: actions/checkout@v6\n",
    )
    completed = _run([str(directory)])
    assert completed.returncode == 1, completed.stderr
    assert "unpinned-uses" in completed.stderr


@pytest.mark.skipif(REAL_ZIZMOR is None, reason="zizmor is not installed")
def test_real_zizmor_fails_on_missing_top_level_permissions(tmp_path: Path) -> None:
    """SA202: the gate fails on a workflow with no top-level ``permissions:``."""
    directory = _workflow(
        tmp_path,
        f"name: Fixture\non: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n"
        f"    steps:\n      - uses: {PINNED_CHECKOUT}\n",
    )
    completed = _run([str(directory)])
    assert completed.returncode == 1, completed.stderr
    assert "excessive-permissions" in completed.stderr


@pytest.mark.skipif(REAL_ZIZMOR is None, reason="zizmor is not installed")
def test_real_zizmor_fails_on_job_level_only_permissions(tmp_path: Path) -> None:
    """SA202: a job-level block does not satisfy the workflow-level requirement."""
    directory = _workflow(
        tmp_path,
        f"name: Fixture\non: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n"
        f"    permissions:\n      contents: read\n    steps:\n      - uses: {PINNED_CHECKOUT}\n",
    )
    completed = _run([str(directory)])
    assert completed.returncode == 1, completed.stderr
    assert "missing-top-level-permissions" in completed.stderr


@pytest.mark.skipif(REAL_ZIZMOR is None, reason="zizmor is not installed")
def test_real_zizmor_fails_on_inline_ignore_of_unpinned_uses(tmp_path: Path) -> None:
    """SA202: an inline zizmor ignore comment cannot suppress the pinning rule."""
    directory = _workflow(
        tmp_path,
        "name: Fixture\non: push\npermissions:\n  contents: read\n"
        "jobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - uses: actions/checkout@v6 # zizmor: ignore[unpinned-uses]\n",
    )
    completed = _run([str(directory)])
    assert completed.returncode == 1, completed.stderr
    assert "unpinned-uses" in completed.stderr


@pytest.mark.skipif(REAL_ZIZMOR is None, reason="zizmor is not installed")
def test_real_zizmor_passes_on_hardened_workflow(tmp_path: Path) -> None:
    """A pinned workflow with a top-level permissions block passes."""
    completed = _run([str(_workflow(tmp_path, CLEAN_WORKFLOW))])
    assert completed.returncode == 0, completed.stderr


@pytest.mark.skipif(REAL_ZIZMOR is None, reason="zizmor is not installed")
def test_repository_workflows_pass_the_gate() -> None:
    """The repository's own workflows satisfy the gate contract."""
    completed = _run([str(WORKFLOWS)])
    assert completed.returncode == 0, completed.stderr
