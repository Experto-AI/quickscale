"""Sealed-tag verification and lockfile refresh for module updates (SA319 a)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml
from unittest.mock import Mock, patch

import pytest

from quickscale_core import __version__ as CORE_VERSION
from quickscale_core.utils.git_tags import (
    resolve_remote_tag as _REAL_RESOLVE_REMOTE_TAG,
)
from quickscale_cli.commands import _module_update
from quickscale_cli.commands import _module_update_io
from quickscale_cli.commands import _module_update_seal
from quickscale_cli.commands._module_update import _run_update_under_lock
from quickscale_cli.commands._module_shared import _sync_state_module_version
from quickscale_cli.commands._module_update_io import (
    _commit_regenerated_managed_wiring,
    _refresh_update_lockfile,
)
from quickscale_cli.commands._module_update_seal import (
    _UpdateSealError,
    _UpdateSealPlan,
    _preflight_update_seals,
    _resolve_update_seal,
)

_MODULE = "auth"
_TAG = f"splits/{_MODULE}-module/{CORE_VERSION}"
_BRANCH = f"splits/{_MODULE}-module"
_REAL_REMOTE_TREES = _module_update_seal._remote_trees


def _git(path: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _init_repo(path: Path, *, bare: bool = False) -> None:
    subprocess.run(
        ["git", "init", "-q", *(["--bare"] if bare else []), str(path)],
        check=True,
        capture_output=True,
    )
    if bare:
        return
    _git(path, "config", "user.name", "Seal Test")
    _git(path, "config", "user.email", "seal@example.invalid")


@pytest.fixture
def real_seal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Restore the real tag/tree seams the CLI conftest stubs for hermeticity."""
    monkeypatch.setattr(
        "quickscale_core.utils.git_tags.resolve_remote_tag",
        _REAL_RESOLVE_REMOTE_TAG,
    )
    monkeypatch.setattr(
        _module_update_seal,
        "_remote_trees",
        _REAL_REMOTE_TREES,
    )


@pytest.fixture
def split_remote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, real_seal: None
) -> tuple[Path, Path]:
    """Create a bare origin with a module split commit and a project checkout."""
    remote = tmp_path / "remote.git"
    work = tmp_path / "work"
    project = tmp_path / "project"
    _init_repo(remote, bare=True)
    _init_repo(work)
    _init_repo(project)
    (work / "module.yml").write_text(f'name: {_MODULE}\nversion: "{CORE_VERSION}"\n')
    (work / "src").mkdir()
    (work / "src" / "auth.py").write_text("VALUE = 1\n")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "initial module content")
    monkeypatch.chdir(project)
    return remote, work


def _publish(
    work: Path,
    remote: Path,
    *,
    branch_commit: str,
    tag_commit: str,
) -> None:
    _git(work, "push", "-q", str(remote), f"{branch_commit}:refs/heads/{_BRANCH}")
    _git(work, "tag", "--annotate", _TAG, tag_commit, "-m", _TAG)
    _git(work, "push", "-q", str(remote), f"refs/tags/{_TAG}")


def test_resolve_update_seal_accepts_a_branch_at_the_seal(
    split_remote: tuple[Path, Path],
) -> None:
    remote, work = split_remote
    commit = _git(work, "rev-parse", "HEAD")
    _publish(work, remote, branch_commit=commit, tag_commit=commit)

    plan = _resolve_update_seal(str(remote), _MODULE, CORE_VERSION)

    assert plan.tag == _TAG
    assert plan.branch == _BRANCH
    assert plan.tag_sha == commit
    assert plan.branch_sha == commit
    assert plan.version == CORE_VERSION


def test_resolve_update_seal_accepts_equal_tree_at_a_different_commit(
    split_remote: tuple[Path, Path],
) -> None:
    """Rule 6 reuses a prior seal commit when the split tree is unchanged."""
    remote, work = split_remote
    tag_commit = _git(work, "rev-parse", "HEAD")
    tree = _git(work, "rev-parse", "HEAD^{tree}")
    reused = _git(work, "commit-tree", tree, "-m", "same tree")
    _publish(work, remote, branch_commit=reused, tag_commit=tag_commit)

    plan = _resolve_update_seal(str(remote), _MODULE, CORE_VERSION)

    assert plan.tag_sha == tag_commit
    assert plan.branch_sha == reused


def test_resolve_update_seal_refuses_a_moved_branch(
    split_remote: tuple[Path, Path],
) -> None:
    remote, work = split_remote
    tag_commit = _git(work, "rev-parse", "HEAD")
    (work / "src" / "auth.py").write_text("VALUE = 2\n")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "move after seal")
    moved = _git(work, "rev-parse", "HEAD")
    _publish(work, remote, branch_commit=moved, tag_commit=tag_commit)

    with pytest.raises(_UpdateSealError, match="moved away from sealed tag"):
        _resolve_update_seal(str(remote), _MODULE, CORE_VERSION)


def test_resolve_update_seal_refuses_a_missing_tag(
    split_remote: tuple[Path, Path],
) -> None:
    remote, work = split_remote
    commit = _git(work, "rev-parse", "HEAD")
    _git(work, "push", "-q", str(remote), f"{commit}:refs/heads/{_BRANCH}")

    with pytest.raises(_UpdateSealError, match="sealed release tag"):
        _resolve_update_seal(str(remote), _MODULE, CORE_VERSION)


def test_preflight_stops_on_the_first_unverifiable_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = Mock(modules={"auth": Mock(), "blog": Mock()})
    calls: list[str] = []

    def _fake_resolve(remote: str, module: str, version: str) -> _UpdateSealPlan:
        del remote, version
        calls.append(module)
        if module == "blog":
            raise _UpdateSealError("split branch moved")
        return _UpdateSealPlan(module, CORE_VERSION, _TAG, "a" * 40, _BRANCH, "a" * 40)

    monkeypatch.setattr(_module_update_seal, "_resolve_update_seal", _fake_resolve)

    plans, failure = _preflight_update_seals(state, "remote", CORE_VERSION)

    assert calls == ["auth", "blog"]
    assert set(plans) == {"auth"}
    assert failure is not None
    assert failure[0] == "blog"
    assert "split branch moved" in str(failure[1])


def test_preflight_failure_aborts_before_any_pull(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = Mock(
        project=Mock(package="myapp"), modules={"auth": Mock(), "blog": Mock()}
    )
    monkeypatch.setattr(
        _module_update_seal,
        "_preflight_update_seals",
        lambda state, remote, version: (
            {},
            ("blog", _UpdateSealError("split branch moved")),
        ),
    )
    with (
        patch.object(_module_update, "_acquire_update_lock", return_value=Mock()),
        patch(
            "quickscale_cli.commands._module_update_guard._enforce_no_local_module_changes"
        ),
        patch("quickscale_core.utils.git_subtree.run_git_subtree_pull") as mock_pull,
    ):
        failed, updated, lock_failed, wiring_failed = _run_update_under_lock(
            state,
            Path.cwd(),
            no_preview=True,
            confirm_contract_adoption=False,
            allow_local_changes=False,
        )

    assert failed == ["blog"]
    assert updated == []
    assert lock_failed is False
    assert wiring_failed is False
    mock_pull.assert_not_called()


def test_lock_failure_rolls_back_the_updated_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = Mock(project=Mock(package="myapp"), modules={"auth": Mock()})
    plan = _UpdateSealPlan(_MODULE, CORE_VERSION, _TAG, "a" * 40, _BRANCH, "a" * 40)
    lock = Mock()
    monkeypatch.setattr(
        _module_update_seal,
        "_preflight_update_seals",
        lambda state, remote, version: (
            {_MODULE: plan},
            None,
        ),
    )
    with (
        patch.object(_module_update, "_acquire_update_lock", return_value=lock),
        patch(
            "quickscale_cli.commands._module_update_guard._enforce_no_local_module_changes"
        ),
        patch.object(_module_update, "_resolve_pre_update_head", return_value="b" * 40),
        patch.object(
            _module_update,
            "_update_all_modules",
            return_value=([], [_MODULE]),
        ),
        patch.object(_module_update_io, "_refresh_update_lockfile", return_value=False),
        patch.object(
            _module_update_io, "_roll_back_partial_module_update"
        ) as mock_rollback,
    ):
        failed, updated, lock_failed, wiring_failed = _run_update_under_lock(
            state,
            Path.cwd(),
            no_preview=True,
            confirm_contract_adoption=False,
            allow_local_changes=False,
        )

    assert failed == []
    assert updated == [_MODULE]
    assert lock_failed is True
    assert wiring_failed is False
    mock_rollback.assert_called_once()
    lock.release.assert_called_once()


def test_refresh_update_lockfile_runs_poetry_lock(
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\nname = 'demo'\n")
    completed = subprocess.CompletedProcess(
        args=["poetry", "lock"], returncode=0, stdout="", stderr=""
    )

    with patch("subprocess.run", return_value=completed) as mock_run:
        assert _refresh_update_lockfile(tmp_path) is True

    args, kwargs = mock_run.call_args
    assert args[0] == ["poetry", "lock"]
    assert kwargs["cwd"] == tmp_path
    assert kwargs["env"]["POETRY_VIRTUALENVS_IN_PROJECT"] == "true"


def test_refresh_update_lockfile_reports_a_poetry_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\nname = 'demo'\n")
    completed = subprocess.CompletedProcess(
        args=["poetry", "lock"], returncode=1, stdout="", stderr="solver exploded"
    )

    with patch("subprocess.run", return_value=completed):
        assert _refresh_update_lockfile(tmp_path) is False

    captured = capsys.readouterr()
    assert "Failed to refresh poetry.lock" in captured.err
    assert "solver exploded" in captured.err


def test_refresh_update_lockfile_reports_a_missing_poetry(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\nname = 'demo'\n")

    with patch("subprocess.run", side_effect=FileNotFoundError("no poetry")):
        assert _refresh_update_lockfile(tmp_path) is False

    captured = capsys.readouterr()
    assert "Failed to run 'poetry lock'" in captured.err
    assert "Install Poetry" in captured.err


def test_refresh_update_lockfile_skips_without_pyproject(tmp_path: Path) -> None:
    with patch("subprocess.run") as mock_run:
        assert _refresh_update_lockfile(tmp_path) is True
    mock_run.assert_not_called()


def test_wiring_commit_carries_the_refreshed_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "myapp" / "settings").mkdir(parents=True)
    (tmp_path / "myapp" / "settings" / "modules.py").write_text("# managed\n")
    (tmp_path / "myapp" / "urls_modules.py").write_text("# managed urls\n")
    quickscale_dir = tmp_path / ".quickscale"
    quickscale_dir.mkdir()
    (quickscale_dir / "state.yml").write_text("modules: {}\n")
    (tmp_path / "poetry.lock").write_text("baseline\n")
    _init_repo(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "baseline")
    monkeypatch.chdir(tmp_path)

    (tmp_path / "poetry.lock").write_text("refreshed\n")
    _commit_regenerated_managed_wiring("myapp")

    committed = _git(tmp_path, "show", "--name-only", "--format=", "HEAD").split()
    assert "poetry.lock" in committed
    assert _git(tmp_path, "status", "--porcelain") == ""


def test_sync_state_module_version_records_the_canonical_branch(
    tmp_path: Path,
) -> None:
    """An update that moves a module onto the split branch records that branch."""
    quickscale_dir = tmp_path / ".quickscale"
    quickscale_dir.mkdir()
    (quickscale_dir / "state.yml").write_text(
        yaml.dump(
            {
                "version": "1",
                "project": {
                    "slug": "myapp",
                    "package": "myapp",
                    "theme": "showcase_react",
                    "created_at": "2025-01-01T00:00:00",
                    "last_applied": "2025-01-01T00:00:00",
                },
                "modules": {
                    "auth": {
                        "name": "auth",
                        "version": "0.88.0",
                        "commit_sha": "b" * 40,
                        "embedded_at": "2025-01-01T00:00:00",
                        "prefix": "modules/auth",
                        "branch": "source",
                        "installed_at": "2025-01-01",
                    }
                },
            },
            sort_keys=False,
        )
    )

    _sync_state_module_version(
        tmp_path,
        "auth",
        CORE_VERSION,
        commit_sha="a" * 40,
        branch=_BRANCH,
    )

    from quickscale_core.schema.state_schema import StateManager

    state = StateManager(tmp_path).load()
    assert state is not None
    assert state.modules["auth"].branch == _BRANCH
    assert state.modules["auth"].commit_sha == "a" * 40
    assert state.modules["auth"].version == CORE_VERSION
