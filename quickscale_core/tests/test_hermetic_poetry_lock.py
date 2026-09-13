"""Contract tests for the generated-project Poetry lock shim."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


def _run_poetry(
    project_path: Path, *arguments: str
) -> subprocess.CompletedProcess[str]:
    """Run the test shim from one prospective generated-project root."""
    return subprocess.run(
        ["poetry", *arguments],
        cwd=project_path,
        capture_output=True,
        text=True,
        check=False,
    )


def _read_invocations(invocation_log: Path) -> list[list[str]]:
    """Read the shim's JSONL invocation record."""
    return [
        json.loads(line)
        for line in invocation_log.read_text(encoding="utf-8").splitlines()
    ]


@pytest.mark.parametrize(
    "arguments",
    [
        (),
        ("install",),
        ("lock", "--regenerate"),
    ],
)
def test_hermetic_poetry_lock_rejects_noncanonical_commands(
    hermetic_poetry_lock: tuple[str, Path],
    tmp_path: Path,
    arguments: tuple[str, ...],
) -> None:
    """Only the exact ``poetry lock`` argv is accepted and every attempt is logged."""
    _, invocation_log = hermetic_poetry_lock
    project_path = tmp_path / "generated-project"
    project_path.mkdir()
    (project_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (project_path / "manage.py").write_text("", encoding="utf-8")

    result = _run_poetry(project_path, *arguments)

    assert result.returncode == 64
    assert result.stdout == ""
    assert result.stderr == "test Poetry shim accepts only: poetry lock\n"
    assert not (project_path / "poetry.lock").exists()
    assert _read_invocations(invocation_log) == [["poetry", *arguments]]


@pytest.mark.parametrize(
    ("present_files", "missing_message"),
    [
        ({"manage.py"}, "pyproject.toml"),
        ({"pyproject.toml"}, "manage.py"),
        (set(), "pyproject.toml, manage.py"),
    ],
)
def test_hermetic_poetry_lock_requires_generated_project_root(
    hermetic_poetry_lock: tuple[str, Path],
    tmp_path: Path,
    present_files: set[str],
    missing_message: str,
) -> None:
    """The shim refuses to create a lock outside a generated-project root."""
    _, invocation_log = hermetic_poetry_lock
    project_path = tmp_path / "generated-project"
    project_path.mkdir()
    for filename in present_files:
        (project_path / filename).write_text("", encoding="utf-8")

    result = _run_poetry(project_path, "lock")

    assert result.returncode == 65
    assert result.stdout == ""
    assert result.stderr == (
        f"poetry lock must run in a generated project; missing: {missing_message}\n"
    )
    assert not (project_path / "poetry.lock").exists()
    assert _read_invocations(invocation_log) == [["poetry", "lock"]]


def test_hermetic_poetry_lock_is_repeatable_and_logs_each_invocation(
    hermetic_poetry_lock: tuple[str, Path],
    tmp_path: Path,
) -> None:
    """Repeated locks replace stale content with identical deterministic bytes."""
    expected_content, invocation_log = hermetic_poetry_lock
    project_path = tmp_path / "generated-project"
    project_path.mkdir()
    (project_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (project_path / "manage.py").write_text("", encoding="utf-8")
    lock_path = project_path / "poetry.lock"

    first = _run_poetry(project_path, "lock")
    first_bytes = lock_path.read_bytes()
    lock_path.write_text("stale lock\n", encoding="utf-8")
    second = _run_poetry(project_path, "lock")

    assert first.returncode == 0
    assert second.returncode == 0
    assert first.stdout == first.stderr == ""
    assert second.stdout == second.stderr == ""
    assert first_bytes == expected_content.encode("utf-8")
    assert lock_path.read_bytes() == first_bytes
    assert _read_invocations(invocation_log) == [
        ["poetry", "lock"],
        ["poetry", "lock"],
    ]
