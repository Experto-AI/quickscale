"""
Hermetic contracts for the generated-workflow actionlint gate (SA306).

The gate's contract is exercised with a fake ``actionlint`` on ``PATH`` so the
suite needs no network access.  The acceptance-critical half -- that actionlint
rejects the job-level ``hashFiles`` guard GitHub refuses -- is proven against
the real tool on a fixture workflow and skipped only when it is absent.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import scripts.check_generated_workflow_lint as lint_gate

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKER = REPO_ROOT / "scripts" / "check_generated_workflow_lint.py"
REAL_ACTIONLINT = shutil.which("actionlint")
PINNED_CHECKOUT = "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v6.1.0"


def _run(
    path: str | None = None, arguments: list[str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the gate, optionally with a restricted ``PATH`` and explicit arguments."""
    environment = dict(os.environ)
    if path is not None:
        environment["PATH"] = path
    return subprocess.run(
        [sys.executable, str(CHECKER), *(arguments or [])],
        capture_output=True,
        text=True,
        timeout=300,
        env=environment,
        check=False,
    )


def _fake_actionlint(
    tmp_path: Path,
    *,
    version: str = lint_gate.ACTIONLINT_VERSION,
    exit_code: int = 0,
    stdout: str = "",
    record_dir: Path | None = None,
) -> Path:
    """Install a fake actionlint that reports a version, optionally records, and exits."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "actionlint"
    script.write_text(
        f"#!{sys.executable}\n"
        "import json\n"
        "import pathlib\n"
        "import shutil\n"
        "import sys\n"
        f"record_dir = {str(record_dir) if record_dir is not None else None!r}\n"
        "record_dir = pathlib.Path(record_dir) if record_dir else None\n"
        'if "--version" in sys.argv:\n'
        f"    sys.stdout.write({version!r} + chr(10))\n"
        "    raise SystemExit(0)\n"
        "if record_dir is not None:\n"
        "    record_dir.mkdir(parents=True, exist_ok=True)\n"
        "    (record_dir / 'argv.json').write_text(json.dumps(sys.argv[1:]))\n"
        "    workflow = next(\n"
        "        (pathlib.Path(arg) for arg in sys.argv[1:]"
        " if arg.endswith(('.yml', '.yaml'))),\n"
        "        None,\n"
        "    )\n"
        "    if workflow is not None:\n"
        "        shutil.copy2(workflow, record_dir / 'seen-workflow.yml')\n"
        f"sys.stdout.write({stdout!r})\n"
        f"raise SystemExit({exit_code})\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return bin_dir


def _path_with(bin_dir: Path) -> str:
    """Put the fake tool first and keep the host tools a render may need."""
    return f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"


def test_missing_tool_fails_closed(tmp_path: Path) -> None:
    """A missing actionlint executable fails closed with the release link."""
    empty = tmp_path / "empty"
    empty.mkdir()
    completed = _run(str(empty))
    assert completed.returncode == 2
    assert lint_gate.EXECUTABLE in completed.stderr
    assert lint_gate.ACTIONLINT_VERSION in completed.stderr
    assert lint_gate.ACTIONLINT_RELEASES_URL in completed.stderr


def test_version_mismatch_fails_closed(tmp_path: Path) -> None:
    """A different actionlint release fails closed before any render."""
    bin_dir = _fake_actionlint(tmp_path, version="1.7.11")
    completed = _run(_path_with(bin_dir))
    assert completed.returncode == 2
    assert "must be 1.7.12" in completed.stderr
    assert "1.7.11" in completed.stderr


def test_clean_rendered_workflow_exits_zero(tmp_path: Path) -> None:
    """The gate lints the rendered ci.yml and passes when actionlint is silent."""
    record_dir = tmp_path / "record"
    bin_dir = _fake_actionlint(tmp_path, record_dir=record_dir)
    completed = _run(_path_with(bin_dir))
    assert completed.returncode == 0, completed.stderr
    assert "generated workflow lint clean" in completed.stdout

    arguments = json.loads((record_dir / "argv.json").read_text(encoding="utf-8"))
    assert arguments[:2] == ["-no-color", "-oneline"]
    assert arguments[-1].endswith(".github/workflows/ci.yml")
    assert lint_gate.GENERATED_PROBE_SLUG in arguments[-1]

    rendered = (record_dir / "seen-workflow.yml").read_text(encoding="utf-8")
    assert "frontend-lint:" in rendered
    assert "if: ${{ hashFiles('frontend/package.json')" not in rendered
    assert "Run frontend tests" in rendered
    assert PINNED_CHECKOUT in rendered


def test_findings_fail_the_gate(tmp_path: Path) -> None:
    """An actionlint finding fails the gate with its diagnostic and count."""
    diagnostic = (
        '.github/workflows/ci.yml:133:13: calling function "hashFiles" is not '
        "allowed here [expression]\n"
    )
    bin_dir = _fake_actionlint(tmp_path, exit_code=1, stdout=diagnostic)
    completed = _run(_path_with(bin_dir))
    assert completed.returncode == 1
    assert "hashFiles" in completed.stderr
    assert "generated workflow lint findings: 1" in completed.stderr


def test_findings_without_a_diagnostic_fail_closed(tmp_path: Path) -> None:
    """A findings exit status with no text is infrastructure failure, not a pass."""
    bin_dir = _fake_actionlint(tmp_path, exit_code=1)
    completed = _run(_path_with(bin_dir))
    assert completed.returncode == 2
    assert "without a diagnostic" in completed.stderr


def test_unexpected_exit_fails_closed(tmp_path: Path) -> None:
    """An actionlint fatal error is infrastructure failure, never a pass."""
    bin_dir = _fake_actionlint(tmp_path, exit_code=3, stdout="boom\n")
    completed = _run(_path_with(bin_dir))
    assert completed.returncode == 2
    assert "exited 3" in completed.stderr
    assert "boom" in completed.stderr


def test_arguments_are_rejected(tmp_path: Path) -> None:
    """The gate has no mode that skips the fresh render."""
    bin_dir = _fake_actionlint(tmp_path)
    completed = _run(_path_with(bin_dir), arguments=["--existing-project"])
    assert completed.returncode == 2
    assert "usage:" in completed.stderr


@pytest.mark.skipif(REAL_ACTIONLINT is None, reason="actionlint is not installed")
def test_real_actionlint_accepts_the_rendered_workflow() -> None:
    """SA306: the rendered generated workflow passes the real actionlint."""
    completed = _run()
    assert completed.returncode == 0, completed.stderr
    assert "generated workflow lint clean" in completed.stdout


@pytest.mark.skipif(REAL_ACTIONLINT is None, reason="actionlint is not installed")
def test_real_actionlint_rejects_the_former_job_level_guard(tmp_path: Path) -> None:
    """The check is real: actionlint rejects the guard this change removed."""
    workflow = tmp_path / "ci.yml"
    workflow.write_text(
        "name: CI\n"
        "on: push\n"
        "permissions:\n"
        "  contents: read\n"
        "jobs:\n"
        "  frontend-lint:\n"
        "    runs-on: ubuntu-latest\n"
        "    if: ${{ hashFiles('frontend/package.json') != '' }}\n"
        "    steps:\n"
        "      - run: echo ok\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [REAL_ACTIONLINT, "-no-color", "-oneline", str(workflow)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 1, completed.stderr
    assert "hashFiles" in completed.stdout
    assert "not allowed here" in completed.stdout
