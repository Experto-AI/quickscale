"""Temp-repository proofs for the module seal-freshness check."""

from __future__ import annotations

import subprocess
from pathlib import Path

import _publish_module_core as core_module
import _publish_module_git as git_module
import _publish_module_status as status_module
import check_module_seals
import pytest

MODULE = "auth"
VERSION = "0.89.0"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    """Build a repository with one module, one commit, and a local bare origin."""
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote)],
        capture_output=True,
        text=True,
        check=True,
    )
    repo = tmp_path / "repo"
    subprocess.run(
        ["git", "init", "-b", "main", str(repo)],
        capture_output=True,
        text=True,
        check=True,
    )
    _git(repo, "config", "user.name", "Seal Test")
    _git(repo, "config", "user.email", "seal@example.invalid")
    _git(repo, "remote", "add", "origin", str(remote))
    module_dir = repo / "quickscale_modules" / MODULE
    module_dir.mkdir(parents=True)
    (module_dir / "models.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")
    return repo


def _split(repo: Path) -> str:
    result = _git(
        repo,
        "subtree",
        "split",
        f"--prefix=quickscale_modules/{MODULE}",
        "--ignore-joins",
    )
    return result.stdout.strip().splitlines()[-1]


def _publish_branch(repo: Path, split_sha: str) -> None:
    _git(repo, "push", "origin", f"{split_sha}:refs/heads/splits/{MODULE}-module")


def _seal(repo: Path, split_sha: str) -> str:
    tag = f"splits/{MODULE}-module/{VERSION}"
    _publish_branch(repo, split_sha)
    _git(repo, "tag", "--annotate", tag, split_sha, "-m", tag)
    _git(repo, "push", "origin", f"refs/tags/{tag}")
    return tag


def test_unchanged_sealed_module_passes(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    tag = _seal(repository, _split(repository))

    assert check_module_seals.run_check(repository, version=VERSION, modules=[MODULE]) == 0
    output = capsys.readouterr().out
    assert f"sealed ({tag})" in output


def test_unsealed_module_passes(repository: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert check_module_seals.run_check(repository, version=VERSION, modules=[MODULE]) == 0
    output = capsys.readouterr().out
    assert "unsealed" in output


def test_stale_seal_fails_and_names_module(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seal(repository, _split(repository))
    (repository / "quickscale_modules" / MODULE / "models.py").write_text(
        "VALUE = 2\n", encoding="utf-8"
    )
    _git(repository, "commit", "-am", "change the module after its seal")

    assert check_module_seals.run_check(repository, version=VERSION, modules=[MODULE]) == 1
    output = capsys.readouterr().out
    assert "auth" in output
    assert "sealed but stale" in output
    assert "FAILED: auth" in output
    assert "phase-5--seal-the-split-tags" in output


def test_equal_tree_seal_reuse_is_not_stale(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Rule 6 reuses a prior seal commit when the split tree is unchanged."""
    split_sha = _split(repository)
    tree_sha = _git(repository, "rev-parse", f"{split_sha}^{{tree}}").stdout.strip()
    reused_commit = _git(
        repository, "commit-tree", tree_sha, "-m", "previous seal commit"
    ).stdout.strip()
    tag = _seal(repository, reused_commit)

    assert check_module_seals.run_check(repository, version=VERSION, modules=[MODULE]) == 0
    output = capsys.readouterr().out
    assert f"sealed ({tag})" in output


def test_unobservable_seal_fails_closed(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _seal(repository, _split(repository))

    def fail_resolution(*args: object, **kwargs: object) -> str:
        raise git_module.GitError("origin unreachable")

    monkeypatch.setattr(git_module, "resolve_remote_ref", fail_resolution)

    assert check_module_seals.run_check(repository, version=VERSION, modules=[MODULE]) == 2
    output = capsys.readouterr().out
    assert "could not inspect" in output
    assert "origin unreachable" in output


def test_split_branch_moved_after_seal_fails(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A sealed tag whose branch moved fails even when the local split matches."""
    sealed_commit = _git(repository, "rev-parse", "HEAD").stdout.strip()
    tag = _seal(repository, _split(repository))

    (repository / "quickscale_modules" / MODULE / "models.py").write_text(
        "VALUE = 2\n", encoding="utf-8"
    )
    _git(repository, "commit", "-am", "move the split branch after sealing")
    moved_split = _split(repository)
    _git(
        repository,
        "push",
        "-f",
        "origin",
        f"{moved_split}:refs/heads/splits/{MODULE}-module",
    )

    # Restore the module to the sealed content so the local split still
    # matches the tag; only the published branch tip has moved.
    _git(repository, "checkout", sealed_commit, "--", f"quickscale_modules/{MODULE}")
    _git(repository, "commit", "-m", "restore the sealed module content")

    assert check_module_seals.run_check(repository, version=VERSION, modules=[MODULE]) == 1
    output = capsys.readouterr().out
    assert "split branch" in output
    assert "moved from seal" in output
    assert tag in output
    assert "FAILED: auth" in output


def test_sealed_tag_without_split_branch_fails(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A seal with no published split branch cannot be consumed by an update."""
    split_sha = _split(repository)
    tag = f"splits/{MODULE}-module/{VERSION}"
    _git(repository, "tag", "--annotate", tag, split_sha, "-m", tag)
    _git(repository, "push", "origin", f"refs/tags/{tag}")

    assert check_module_seals.run_check(repository, version=VERSION, modules=[MODULE]) == 1
    output = capsys.readouterr().out
    assert "has no split branch" in output
    assert "FAILED: auth" in output


def test_unobservable_split_branch_fails_closed(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _seal(repository, _split(repository))
    real_resolve = git_module.resolve_remote_ref

    def fail_branch_resolution(remote: str, ref: str, **kwargs: object) -> str:
        if ref.startswith("splits/") and ref.count("/") == 1:
            raise git_module.GitError("branch unreadable")
        return real_resolve(remote, ref, **kwargs)

    monkeypatch.setattr(git_module, "resolve_remote_ref", fail_branch_resolution)

    assert check_module_seals.run_check(repository, version=VERSION, modules=[MODULE]) == 2
    output = capsys.readouterr().out
    assert "could not resolve split branch" in output
    assert "branch unreadable" in output


def test_seal_state_compares_tag_tree_with_current_split_tree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tag_commit = "a" * 40
    same_commit = "b" * 40
    other_commit = "c" * 40
    trees = {
        tag_commit: "shared-tree",
        same_commit: "shared-tree",
        other_commit: "other-tree",
    }
    monkeypatch.setattr(
        git_module, "resolve_split_tag", lambda module, version: "splits/auth-module/0.89.0"
    )
    monkeypatch.setattr(
        git_module,
        "resolve_remote_ref",
        lambda remote, ref, **kwargs: tag_commit,
    )
    monkeypatch.setattr(
        git_module,
        "get_tree_sha",
        lambda commit, path=None, *, runner: trees[commit],
    )
    runner = object()

    assert (
        status_module._get_module_seal_state(MODULE, VERSION, same_commit, runner)
        == f"sealed@{VERSION}"
    )
    assert (
        status_module._get_module_seal_state(MODULE, VERSION, other_commit, runner)
        == status_module.SEAL_STALE
    )


def test_status_reports_sealed_but_stale_as_blocking(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stale_sha = "a" * 40
    current_sha = "b" * 40
    monkeypatch.setattr(core_module, "_list_modules", lambda: [MODULE])
    monkeypatch.setattr(git_module, "_warn_uncommitted_changes", lambda runner: None)
    monkeypatch.setattr(status_module, "_show_provenance_diagnostics", lambda runner: True)
    monkeypatch.setattr(
        status_module,
        "_get_module_publish_state",
        lambda module, runner: ("up-to-date", current_sha, current_sha, "remote-live"),
    )
    monkeypatch.setattr(
        git_module, "resolve_split_tag", lambda module, version: "splits/auth-module/0.89.0"
    )
    monkeypatch.setattr(
        git_module,
        "resolve_remote_ref",
        lambda remote, ref, **kwargs: stale_sha,
    )
    monkeypatch.setattr(
        git_module,
        "get_tree_sha",
        lambda commit, path=None, *, runner: (
            "stale-tree" if commit == stale_sha else "current-tree"
        ),
    )

    assert status_module._show_status(object(), version=VERSION) is False
    output = capsys.readouterr().out
    assert "Sealed but stale (blocking): auth" in output
    assert "phase-5--seal-the-split-tags" in output
