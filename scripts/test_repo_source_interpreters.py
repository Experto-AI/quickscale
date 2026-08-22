"""Tests for the repository-source interpreter guard."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from check_repo_source_interpreters import find_violations

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts" / "check_repo_source_interpreters.py"


def test_repository_has_no_bare_repo_source_executors() -> None:
    """All shell and script-test repository-source consumers use project Python."""
    assert find_violations(ROOT) == []


def test_guard_rejects_bare_shell_repo_source(tmp_path: Path) -> None:
    """A shell command invoking python3 on a .py source is rejected."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "bad.sh").write_text("python3 scripts/example.py\n", encoding="utf-8")
    (scripts / "test_empty.py").write_text("", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(GUARD), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "bare Python executes a repository .py file" in result.stdout


def test_guard_rejects_indirect_bare_shell_repo_source(tmp_path: Path) -> None:
    """The former version-tool fallback cannot hide behind shell variables."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "bad.sh").write_text(
        'PYTHON="${PYTHON:-python3}"\nREPO_SOURCE="scripts/example.py"\n"$PYTHON" "$REPO_SOURCE"\n',
        encoding="utf-8",
    )
    (scripts / "test_empty.py").write_text("", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(GUARD), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "bare Python variable executes a repository .py file" in result.stdout


def test_guard_rejects_bare_python_test_executor(tmp_path: Path) -> None:
    """A subprocess test executor using bare python for a source is rejected."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "test_bad.py").write_text(
        "import subprocess\nsubprocess.run(['python', 'scripts/example.py'])\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(GUARD), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "bare python may execute a repository Python source" in result.stdout


def test_guard_allows_stdlib_python_c_commands(tmp_path: Path) -> None:
    """A Python -c helper is not a repository-source execution."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "check.sh").write_text("python3 -c 'print(1)'\n", encoding="utf-8")
    (scripts / "test_empty.py").write_text("", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(GUARD), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0


def test_project_python_relative_override_survives_directory_change() -> None:
    """A root-relative explicit interpreter resolves to a stable absolute path."""
    result = subprocess.run(
        [
            "bash",
            "-c",
            (
                "source scripts/_python_requirement.sh; "
                'PYTHON=".venv/bin/python"; '
                'resolved="$(quickscale_project_python "$PWD")"; '
                'printf "%s\\n" "$resolved"; '
                'cd /; "$resolved" -c "print(\'directory-change-ok\')"'
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    output_lines = result.stdout.splitlines()
    assert Path(output_lines[0]).is_absolute()
    assert output_lines[1] == "directory-change-ok"
