"""Tests for local-edit detection against an embedded module's recorded tree."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import quickscale_cli.utils.module_provenance as _module_provenance
from quickscale_cli.utils.module_provenance import detect_module_content_drift
from quickscale_core.utils.git_subtree import run_git_subtree_add

_MODULE_PREFIX = "modules/auth"


def _run_git(path: Path, *args: str) -> str:
    """Run one git command in *path* and return its stripped stdout."""
    return subprocess.run(
        ["git", *args],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _init_git_repo(path: Path) -> None:
    """Create a git repository with a committer identity."""
    subprocess.run(["git", "init", "-q", str(path)], check=True, capture_output=True)
    _run_git(path, "config", "user.name", "Test User")
    _run_git(path, "config", "user.email", "test@example.invalid")


def _write_source_module(tmp_path: Path) -> tuple[Path, str]:
    """Create a module split whose root is the module content."""
    source = tmp_path / "source"
    source.mkdir()
    _init_git_repo(source)
    (source / "module.yml").write_text('name: auth\nversion: "0.89.0"\n')
    (source / "pyproject.toml").write_text(
        "[project]\n"
        'name = "quickscale-module-auth"\n'
        "\n"
        "[tool.poetry.dependencies]\n"
        'python = "^3.14"\n'
        'quickscale-core = {path = "../../quickscale_core", develop = true}\n'
    )
    (source / "src").mkdir()
    (source / "src" / "auth.py").write_text("ANSWER = 1\n")
    _run_git(source, "add", "-A")
    _run_git(source, "commit", "-qm", "module content")
    return source, _run_git(source, "rev-parse", "HEAD")


def _write_project_with_subtree(tmp_path: Path) -> tuple[Path, str]:
    """Create a git project that embedded the source module via subtree."""
    source, commit_sha = _write_source_module(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    _init_git_repo(project)
    (project / "README.md").write_text("project\n")
    _run_git(project, "add", "-A")
    _run_git(project, "commit", "-qm", "scaffold")
    run_git_subtree_add(
        prefix=_MODULE_PREFIX,
        remote=str(source),
        branch=commit_sha,
        squash=True,
        path=project,
    )
    return project, commit_sha


def _apply_embed_pyproject_rewrite(project: Path) -> None:
    """Apply the dependency rewrite the embed path performs."""
    pyproject_path = project / _MODULE_PREFIX / "pyproject.toml"
    pyproject_path.write_text(
        pyproject_path.read_text().replace(
            '{path = "../../quickscale_core", develop = true}',
            '">=0.89.0,<0.90.0"',
        )
    )


def _commit_all(project: Path, message: str) -> None:
    """Commit the current work tree so the project is clean again."""
    _run_git(project, "add", "-A")
    _run_git(project, "commit", "-qm", message)


def test_unchanged_module_is_clean(tmp_path: Path) -> None:
    """An untouched subtree, including its embed-time rewrite, reports no drift."""
    project, commit_sha = _write_project_with_subtree(tmp_path)
    _apply_embed_pyproject_rewrite(project)
    _commit_all(project, "embed rewrite")

    drift = detect_module_content_drift(project, "auth", commit_sha)

    assert drift.verifiable
    assert drift.changed_paths == ()


def test_hand_edited_file_is_reported(tmp_path: Path) -> None:
    """A committed hand edit is reported with its project-relative path."""
    project, commit_sha = _write_project_with_subtree(tmp_path)
    (project / _MODULE_PREFIX / "src" / "auth.py").write_text("ANSWER = 2\n")
    _commit_all(project, "hand edit")

    drift = detect_module_content_drift(project, "auth", commit_sha)

    assert drift.verifiable
    assert drift.changed_paths == ("modules/auth/src/auth.py",)


def test_added_and_deleted_files_are_reported(tmp_path: Path) -> None:
    """Added files and missing recorded files both count as local edits."""
    project, commit_sha = _write_project_with_subtree(tmp_path)
    (project / _MODULE_PREFIX / "src" / "auth.py").unlink()
    (project / _MODULE_PREFIX / "src" / "extra.py").write_text("EXTRA = True\n")
    _commit_all(project, "change files")

    drift = detect_module_content_drift(project, "auth", commit_sha)

    assert drift.verifiable
    assert drift.changed_paths == (
        "modules/auth/src/auth.py",
        "modules/auth/src/extra.py",
    )


def test_ignored_files_are_not_reported(tmp_path: Path) -> None:
    """Ignored build artifacts do not count as hand edits."""
    project, commit_sha = _write_project_with_subtree(tmp_path)
    (project / ".gitignore").write_text("__pycache__/\n")
    _run_git(project, "add", ".gitignore")
    _run_git(project, "commit", "-qm", "ignore")
    cache_dir = project / _MODULE_PREFIX / "src" / "__pycache__"
    cache_dir.mkdir()
    (cache_dir / "auth.cpython-314.pyc").write_bytes(b"cache")

    drift = detect_module_content_drift(project, "auth", commit_sha)

    assert drift.changed_paths == ()


def test_pyproject_hand_edit_outside_rewritten_dependency_is_reported(
    tmp_path: Path,
) -> None:
    """The rewrite allowance does not hide edits elsewhere in pyproject.toml."""
    project, commit_sha = _write_project_with_subtree(tmp_path)
    _apply_embed_pyproject_rewrite(project)
    pyproject_path = project / _MODULE_PREFIX / "pyproject.toml"
    pyproject_path.write_text(
        pyproject_path.read_text().replace('python = "^3.14"', 'python = "^3.13"')
    )
    _commit_all(project, "hand edit")

    drift = detect_module_content_drift(project, "auth", commit_sha)

    assert drift.changed_paths == ("modules/auth/pyproject.toml",)


def test_falls_back_to_the_local_subtree_squash_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pruned split object still compares through the recorded squash commit."""
    project, commit_sha = _write_project_with_subtree(tmp_path)
    monkeypatch.setattr(_module_provenance, "_is_split_commit", lambda *args: False)
    (project / _MODULE_PREFIX / "src" / "auth.py").write_text("ANSWER = 3\n")

    drift = detect_module_content_drift(project, "auth", commit_sha)

    assert drift.verifiable
    assert drift.changed_paths == ("modules/auth/src/auth.py",)


@pytest.mark.parametrize("commit_sha", [None, "", "abc123", "not-a-sha"])
def test_missing_recorded_commit_is_unverifiable(
    tmp_path: Path, commit_sha: str | None
) -> None:
    """A missing or malformed recorded SHA is reported, not treated as clean."""
    project, _ = _write_project_with_subtree(tmp_path)

    drift = detect_module_content_drift(project, "auth", commit_sha)

    assert not drift.verifiable
    assert drift.changed_paths == ()
    assert drift.unverifiable_reason


def test_non_git_project_is_unverifiable(tmp_path: Path) -> None:
    """A project without git history cannot prove the module is unedited."""
    project = tmp_path / "plain"
    (project / _MODULE_PREFIX).mkdir(parents=True)

    drift = detect_module_content_drift(project, "auth", "a" * 40)

    assert not drift.verifiable
    assert "not a git repository" in (drift.unverifiable_reason or "")
