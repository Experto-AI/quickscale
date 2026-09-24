"""Hermetic contracts for the project-contract vintage gate (SA207)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKER = REPO_ROOT / "scripts" / "check_project_contract_vintage.py"

SETTINGS_TEMPLATE = (
    "quickscale_core/src/quickscale_core/generator/templates/project_name/settings/base.py.j2"
)
START_TEMPLATE = "quickscale_core/src/quickscale_core/generator/templates/start.sh.j2"
DOCKERFILE_TEMPLATE = "quickscale_core/src/quickscale_core/generator/templates/Dockerfile.j2"
DECLARATION = "quickscale_core/src/quickscale_core/data/project_contract.yml"


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


def _stage(repo: Path, files: dict[str, str]) -> None:
    for relative, content in files.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")


@pytest.fixture
def repository(tmp_path: Path) -> tuple[Path, str]:
    """Build a repository whose starting tree already carries the declaration."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "user.email", "test@example.invalid")
    base = _commit(
        repo,
        "initial",
        {"README.md": "initial\n", DECLARATION: "steps: []\n"},
    )
    return repo, base


@pytest.fixture
def pre_declaration_repository(tmp_path: Path) -> tuple[Path, str]:
    """Build a repository whose starting tree predates the declaration."""
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
        "PROJECT_VINTAGE_BASE_REF",
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


@pytest.mark.parametrize(
    "template_path",
    [SETTINGS_TEMPLATE, START_TEMPLATE, DOCKERFILE_TEMPLATE],
)
def test_template_change_without_declaration_fails(
    repository: tuple[Path, str], template_path: str
) -> None:
    repo, base = repository
    commit = _commit(repo, "tweak generated settings", {template_path: "changed\n"})

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert commit[:12] in result.stderr
    assert template_path in result.stderr
    assert DECLARATION in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    "template_path",
    [SETTINGS_TEMPLATE, START_TEMPLATE, DOCKERFILE_TEMPLATE],
)
def test_template_change_with_declaration_passes(
    repository: tuple[Path, str], template_path: str
) -> None:
    repo, base = repository
    _commit(
        repo,
        "declare the template contract change",
        {
            template_path: "changed\n",
            DECLARATION: "steps:\n  - id: sa999-new\n    minimum: '0.89.0'\n",
        },
    )

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 0, result.stderr


def test_template_change_before_declaration_exists_is_exempt(
    pre_declaration_repository: tuple[Path, str],
) -> None:
    """Historical template changes predate the rule and do not block a PR."""
    repo, base = pre_declaration_repository
    _commit(repo, "historical template change", {SETTINGS_TEMPLATE: "old\n"})

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 0, result.stderr


def test_introducing_commit_may_change_template_with_declaration(
    pre_declaration_repository: tuple[Path, str],
) -> None:
    """The commit that adds the declaration may also change a template."""
    repo, base = pre_declaration_repository
    _commit(
        repo,
        "introduce the declaration",
        {
            SETTINGS_TEMPLATE: "new\n",
            DECLARATION: "steps:\n  - id: sa999-new\n    minimum: '0.89.0'\n",
        },
    )

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 0, result.stderr


def test_template_change_with_unchanged_step_id_fails(
    repository: tuple[Path, str],
) -> None:
    """Editing the declaration without a new id leaves adopters passing."""
    repo, _ = repository
    base = _commit(
        repo,
        "declare the step",
        {DECLARATION: ("steps:\n  - id: sa192-shared-design\n    minimum: '0.89.0'\n")},
    )
    _commit(
        repo,
        "template change with prose-only edit",
        {
            SETTINGS_TEMPLATE: "changed\n",
            DECLARATION: (
                "steps:\n  - id: sa192-shared-design\n    minimum: '0.89.0'\n    note: clarified\n"
            ),
        },
    )

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert "no new adoption step id" in result.stderr


def test_reintroducing_a_removed_step_id_fails(
    repository: tuple[Path, str],
) -> None:
    """Reusing an id projects already recorded is not a new adoption step."""
    repo, _ = repository
    _commit(
        repo,
        "declare the step",
        {DECLARATION: ("steps:\n  - id: sa192-shared-design\n    minimum: '0.89.0'\n")},
    )
    base = _commit(repo, "remove the step", {DECLARATION: "steps: []\n"})
    _commit(
        repo,
        "template change reintroducing the id",
        {
            SETTINGS_TEMPLATE: "changed\n",
            DECLARATION: (
                "steps:\n  - id: sa192-shared-design\n    minimum: '0.89.0'\n"
                "    note: new contract\n"
            ),
        },
    )

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert "no new adoption step id" in result.stderr


def test_staged_comment_only_declaration_edit_fails(
    repository: tuple[Path, str],
) -> None:
    repo, _ = repository
    _commit(
        repo,
        "declare the step",
        {DECLARATION: ("steps:\n  - id: sa192-shared-design\n    minimum: '0.89.0'\n")},
    )
    _stage(
        repo,
        {
            SETTINGS_TEMPLATE: "staged\n",
            DECLARATION: (
                "steps:\n  - id: sa192-shared-design\n    minimum: '0.89.0'\n    note: clarified\n"
            ),
        },
    )

    result = _run(repo, "--staged")

    assert result.returncode == 1
    assert "no new adoption step id" in result.stderr


def test_staged_declaration_deletion_with_template_change_fails(
    repository: tuple[Path, str],
) -> None:
    repo, _ = repository
    (repo / DECLARATION).unlink()
    template_path = repo / SETTINGS_TEMPLATE
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_text("staged\n", encoding="utf-8")
    _git(repo, "add", "-A")

    result = _run(repo, "--staged")

    assert result.returncode == 1
    assert "staged for deletion" in result.stderr


def test_deleting_declaration_with_template_change_fails(
    repository: tuple[Path, str],
) -> None:
    """Removing the declaration alongside a template change is a violation."""
    repo, base = repository
    (repo / DECLARATION).unlink()
    template_path = repo / SETTINGS_TEMPLATE
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_text("changed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "drop the declaration")

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert DECLARATION in result.stderr


def test_deleting_declaration_alone_does_not_disable_enforcement(
    repository: tuple[Path, str],
) -> None:
    """The introduction is a monotonic baseline, not the immediate parent."""
    repo, base = repository
    (repo / DECLARATION).unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "delete the declaration")
    _commit(repo, "later template change", {SETTINGS_TEMPLATE: "changed\n"})

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert SETTINGS_TEMPLATE in result.stderr


def test_declaration_only_change_passes(repository: tuple[Path, str]) -> None:
    repo, base = repository
    _commit(
        repo,
        "clarify adoption prose",
        {DECLARATION: "steps:\n  - id: sa999-new\n    minimum: '0.89.0'\n"},
    )

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 0, result.stderr


def test_unrelated_change_passes(repository: tuple[Path, str]) -> None:
    repo, base = repository
    _commit(repo, "docs tweak", {"docs/readme.md": "hello\n"})

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 0, result.stderr


def test_merged_in_template_change_is_still_checked(
    repository: tuple[Path, str],
) -> None:
    """Only the merge commit is skipped; the commits it brings in are checked."""
    repo, base = repository
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "feature template change", {SETTINGS_TEMPLATE: "feature\n"})
    _git(repo, "checkout", "-q", "-")
    _git(repo, "merge", "-q", "--no-ff", "feature", "-m", "merge feature")

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert "feature template change" in result.stderr
    assert SETTINGS_TEMPLATE in result.stderr


def test_staged_template_change_without_declaration_fails(
    repository: tuple[Path, str],
) -> None:
    repo, _ = repository
    _stage(repo, {SETTINGS_TEMPLATE: "staged\n"})

    result = _run(repo, "--staged")

    assert result.returncode == 1
    assert "staged changes" in result.stderr
    assert SETTINGS_TEMPLATE in result.stderr


def test_staged_template_change_with_declaration_passes(
    repository: tuple[Path, str],
) -> None:
    repo, _ = repository
    _stage(
        repo,
        {
            SETTINGS_TEMPLATE: "staged\n",
            DECLARATION: "steps:\n  - id: sa999-new\n    minimum: '0.89.0'\n",
        },
    )

    result = _run(repo, "--staged")

    assert result.returncode == 0, result.stderr


def test_staged_change_before_declaration_exists_is_exempt(
    pre_declaration_repository: tuple[Path, str],
) -> None:
    repo, _ = pre_declaration_repository
    _stage(repo, {SETTINGS_TEMPLATE: "staged\n"})

    result = _run(repo, "--staged")

    assert result.returncode == 0, result.stderr


def _conflicted_merge(repo: Path, base: str) -> None:
    """Leave the repository mid-merge with a conflicted template file."""
    _commit(repo, "main template change", {SETTINGS_TEMPLATE: "main\n"})
    _git(repo, "checkout", "-q", "-b", "feature", base)
    _commit(repo, "feature template change", {SETTINGS_TEMPLATE: "feature\n"})
    _git(repo, "checkout", "-q", "-")
    subprocess.run(
        ["git", "merge", "feature"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_merge_resolution_template_change_requires_new_step(
    repository: tuple[Path, str],
) -> None:
    """A conflict resolution that rewrites a template must declare a step."""
    repo, base = repository
    _conflicted_merge(repo, base)
    template_path = repo / SETTINGS_TEMPLATE
    template_path.write_text("resolved\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "merge feature with a resolution")

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert "merge resolution with no new adoption step id" in result.stderr


def test_staged_merge_resolution_requires_new_step(
    repository: tuple[Path, str],
) -> None:
    repo, base = repository
    _conflicted_merge(repo, base)
    template_path = repo / SETTINGS_TEMPLATE
    template_path.write_text("resolved\n", encoding="utf-8")
    _git(repo, "add", "-A")

    result = _run(repo, "--staged")

    assert result.returncode == 1
    assert "no new adoption step id" in result.stderr


def test_staged_merge_inherited_change_is_skipped(
    repository: tuple[Path, str],
) -> None:
    """Taking one side's template is not a resolution edit to declare."""
    repo, base = repository
    _conflicted_merge(repo, base)
    template_path = repo / SETTINGS_TEMPLATE
    template_path.write_text("main\n", encoding="utf-8")
    _git(repo, "add", "-A")

    result = _run(repo, "--staged")

    assert result.returncode == 0, result.stderr


def test_merged_branch_reintroduction_is_checked(
    repository: tuple[Path, str],
) -> None:
    """An id declared and removed on a merged branch is not new again."""
    repo, base = repository
    main_branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    _commit(
        repo,
        "main declaration keeps the step",
        {DECLARATION: "steps:\n  - id: sa-keep\n    minimum: '0.89.0'\n"},
    )
    _git(repo, "checkout", "-q", "-b", "feature", base)
    _commit(
        repo,
        "feature declares the old step",
        {DECLARATION: "steps:\n  - id: sa-old\n    minimum: '0.89.0'\n"},
    )
    _commit(
        repo,
        "feature drops the old step",
        {DECLARATION: "steps:\n  - id: sa-keep\n    minimum: '0.89.0'\n"},
    )
    _git(repo, "checkout", "-q", main_branch)
    _git(repo, "merge", "-q", "--no-ff", "feature", "-m", "merge feature")
    merged = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _commit(
        repo,
        "template change reusing the id",
        {
            SETTINGS_TEMPLATE: "changed\n",
            DECLARATION: (
                "steps:\n  - id: sa-keep\n    minimum: '0.89.0'\n"
                "  - id: sa-old\n    minimum: '0.89.0'\n"
            ),
        },
    )

    result = _run(repo, "--base-ref", merged)

    assert result.returncode == 1
    assert "no new adoption step id" in result.stderr


def test_unresolvable_base_ref_fails_closed(repository: tuple[Path, str]) -> None:
    repo, _ = repository

    result = _run(repo, "--base-ref", "does-not-exist")

    assert result.returncode == 2
    assert "ERROR: [PROJECT_CONTRACT_VINTAGE]" in result.stderr
    assert "Traceback" not in result.stderr


def test_environment_base_ref_override_is_honoured(
    repository: tuple[Path, str],
) -> None:
    repo, base = repository
    _commit(repo, "tweak generated settings", {SETTINGS_TEMPLATE: "changed\n"})

    result = _run(repo, environment={"PROJECT_VINTAGE_BASE_REF": base})

    assert result.returncode == 1
    assert SETTINGS_TEMPLATE in result.stderr


def test_repository_head_range_is_clean() -> None:
    """The checked-in history satisfies the gate at its own HEAD."""
    result = subprocess.run(
        [sys.executable, str(CHECKER), "--base-ref", "HEAD^"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr
