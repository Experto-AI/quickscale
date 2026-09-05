"""Hermetic contracts for the behavioural-commit testimony gate (SA166)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKER = REPO_ROOT / "scripts" / "check_commit_testimony.py"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )


def _commit(repo: Path, message: str, files: dict[str, str]) -> str:
    for relative, content in files.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


@pytest.fixture
def repository(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "user.email", "test@example.invalid")
    base = _commit(repo, "initial", {"README.md": "initial\n"})
    return repo, base


def _run(
    repo: Path, *args: str, environment: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for name in (
        "GITHUB_BASE_REF",
        "GITHUB_EVENT_PATH",
        "TESTIMONY_BASE_REF",
    ):
        env.pop(name, None)
    if environment:
        env.update(environment)
    return subprocess.run(
        [sys.executable, str(CHECKER), *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_untitled_workflow_commit_fails(repository: tuple[Path, str]) -> None:
    repo, base = repository
    commit = _commit(
        repo,
        "adjust CI",
        {".github/workflows/ci.yml": "name: CI\n"},
    )

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert commit[:12] in result.stderr
    assert ".github/workflows/ci.yml" in result.stderr
    assert "roadmap reference" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    "message",
    ["feat(sa166): add gate", "SA166: add gate", "feat(v88): checkpoint lifecycle work"],
)
def test_roadmap_reference_satisfies_workflow_commit(
    repository: tuple[Path, str], message: str
) -> None:
    repo, base = repository
    _commit(repo, message, {".github/workflows/ci.yml": "name: CI\n"})

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 0, result.stderr
    assert "Commit testimony passed" in result.stdout


def test_same_commit_changelog_entry_satisfies_release_commit(
    repository: tuple[Path, str],
) -> None:
    repo, base = repository
    _commit(
        repo,
        "v0.88.0: QuickScale 0.88.0",
        {
            ".github/workflows/publish.yml": "name: Publish\n",
            "CHANGELOG.md": "Release testimony\n",
        },
    )

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 0, result.stderr


def test_release_shaped_message_without_testimony_is_not_an_exemption(
    repository: tuple[Path, str],
) -> None:
    repo, base = repository
    _commit(
        repo,
        "v0.87.0: QuickScale 0.87.0",
        {".github/workflows/publish.yml": "name: Publish\n"},
    )

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert "v0.87.0: QuickScale 0.87.0" in result.stderr


def test_provisioning_station_change_requires_testimony(
    repository: tuple[Path, str],
) -> None:
    repo, _ = repository
    base = _commit(
        repo,
        "seed station",
        {
            "Makefile": (
                "integration:\n"
                "\tscripts/provision_ci_postgres.sh run --profile restricted -- scripts/test.sh\n"
            )
        },
    )
    _commit(
        repo,
        "change profile",
        {
            "Makefile": (
                "integration:\n"
                "\tscripts/provision_ci_postgres.sh run --profile isolation -- scripts/test.sh\n"
            )
        },
    )

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert "Makefile (provisioning station)" in result.stderr


def test_provisioning_station_continuation_change_requires_testimony(
    repository: tuple[Path, str],
) -> None:
    repo, _ = repository
    base = _commit(
        repo,
        "seed multiline station",
        {
            "Makefile": (
                "integration:\n"
                "\tscripts/provision_ci_postgres.sh run \\\n"
                "\t\t--profile restricted -- scripts/test.sh\n"
            )
        },
    )
    _commit(
        repo,
        "change multiline profile",
        {
            "Makefile": (
                "integration:\n"
                "\tscripts/provision_ci_postgres.sh run \\\n"
                "\t\t--profile isolation -- scripts/test.sh\n"
            )
        },
    )

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert "Makefile (provisioning station)" in result.stderr


def test_moving_provisioning_station_requires_testimony(
    repository: tuple[Path, str],
) -> None:
    repo, _ = repository
    base = _commit(
        repo,
        "seed station target",
        {
            "Makefile": (
                "integration:\n"
                "\tscripts/provision_ci_postgres.sh run --profile restricted -- scripts/test.sh\n"
                "\nother:\n"
            )
        },
    )
    _commit(
        repo,
        "move station target",
        {
            "Makefile": (
                "integration:\n"
                "\nother:\n"
                "\tscripts/provision_ci_postgres.sh run --profile restricted -- scripts/test.sh\n"
            )
        },
    )

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert "Makefile (provisioning station)" in result.stderr


def test_unrelated_makefile_change_is_quiet(
    repository: tuple[Path, str],
) -> None:
    repo, _ = repository
    base = _commit(
        repo,
        "seed station",
        {
            "Makefile": (
                "integration:\n"
                "\tscripts/provision_ci_postgres.sh run --profile restricted -- scripts/test.sh\n"
                + "\n" * 8
                + "help:\n\t@echo old\n"
            )
        },
    )
    _commit(
        repo,
        "adjust unrelated help",
        {
            "Makefile": (
                "integration:\n"
                "\tscripts/provision_ci_postgres.sh run --profile restricted -- scripts/test.sh\n"
                + "\n" * 8
                + "help:\n\t@echo new\n"
            )
        },
    )

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 0, result.stderr


def test_every_non_merge_commit_in_range_is_checked(
    repository: tuple[Path, str],
) -> None:
    repo, base = repository
    missed = _commit(
        repo,
        "untitled topology change",
        {"scripts/gate_registry.json": "{}\n"},
    )
    _commit(repo, "docs(sa166): follow-up", {"notes.md": "follow-up\n"})

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert missed[:12] in result.stderr


def test_pull_request_base_wins_over_synchronize_before(
    repository: tuple[Path, str],
) -> None:
    repo, base = repository
    missed = _commit(
        repo,
        "untitled topology change",
        {"scripts/gate_registry.json": "{}\n"},
    )
    previous_head = _commit(repo, "docs follow-up", {"notes.md": "first\n"})
    _commit(repo, "docs follow-up", {"notes.md": "second\n"})
    event_path = repo / "pull-request-event.json"
    event_path.write_text(
        json.dumps(
            {
                "before": previous_head,
                "pull_request": {"base": {"sha": base}},
            }
        ),
        encoding="utf-8",
    )

    result = _run(repo, environment={"GITHUB_EVENT_PATH": str(event_path)})

    assert result.returncode == 1
    assert missed[:12] in result.stderr


def test_default_range_checks_head_commit(repository: tuple[Path, str]) -> None:
    repo, _ = repository
    _commit(repo, "untitled", {".github/workflows/ci.yml": "name: CI\n"})

    result = _run(repo)

    assert result.returncode == 1


def test_unresolvable_base_fails_closed_without_traceback(
    repository: tuple[Path, str],
) -> None:
    repo, _ = repository

    result = _run(repo, "--base-ref", "missing-ref")

    assert result.returncode == 2
    assert "ERROR: [COMMIT_TESTIMONY]" in result.stderr
    assert "missing-ref" in result.stderr
    assert "Traceback" not in result.stderr
