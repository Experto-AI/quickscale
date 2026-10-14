"""Coverage for the update migration-content identity guard (SA204 slice e).

``quickscale update`` replaces an embedded module's files with the remote
content.  When the module's version label does not change, the applied
migration files must survive byte-identical: the clean-break policy rewrites
``0001_initial`` in place across releases, so a same-label rewrite would leave
the database's applied schema unidentified.  A new migration file is still
applied forward, and a version-label change is a release upgrade whose database
handling stays the operator's documented fresh-database path.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml
from click.testing import CliRunner

from quickscale_core import __version__ as CORE_VERSION
from quickscale_core.utils.git_subtree import run_git_subtree_add
from quickscale_cli.commands._module_update import (
    _get_update_migration_issues,
    _update_single_module,
    update,
)

_APPLIED_MIGRATION = "# applied migration content\n"
_PULLED_MIGRATION = "# rewritten by the pull\n"
_MODULE_PREFIX = "modules/auth"
_MODULE_VERSION = "0.71.0"
_MODULE_MANIFEST_ROOT = Path(__file__).resolve().parents[3] / "quickscale_modules"


def _migrations_dir(project_path: Path) -> Path:
    return (
        project_path / _MODULE_PREFIX / "src" / "quickscale_modules_auth" / "migrations"
    )


def _write_update_project(tmp_path: Path) -> Path:
    """Create a minimal project whose embedded auth module ships one migration."""
    migrations_dir = _migrations_dir(tmp_path)
    migrations_dir.mkdir(parents=True)
    (tmp_path / _MODULE_PREFIX / "module.yml").write_text(
        f'name: auth\nversion: "{_MODULE_VERSION}"\n'
    )
    (migrations_dir / "0001_initial.py").write_text(_APPLIED_MIGRATION)
    quickscale_dir = tmp_path / ".quickscale"
    quickscale_dir.mkdir()
    (quickscale_dir / "state.yml").write_text(
        yaml.dump(
            {
                "version": "1",
                "project": {
                    "slug": "myproject",
                    "package": "myproject",
                    "theme": "showcase_react",
                    "created_at": "2025-01-01T00:00:00",
                    "last_applied": "2025-01-01T00:00:00",
                },
                "modules": {
                    "auth": {
                        "name": "auth",
                        "version": _MODULE_VERSION,
                        "commit_sha": "a" * 40,
                        "embedded_at": "2025-01-01T00:00:00",
                        "prefix": _MODULE_PREFIX,
                        "branch": "splits/auth-module",
                        "installed_at": "2025-01-01",
                    }
                },
            }
        )
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.poetry.dependencies]\npython = "^3.14"\n'
    )
    return tmp_path


def _run_update(project_path: Path, *, pulled_version: str, pull):
    """Run the single-module update with the git and version seams patched."""
    module_info = Mock(prefix=_MODULE_PREFIX, branch="splits/auth-module")
    with (
        patch(
            "quickscale_core.utils.git_repo.resolve_remote_ref",
            return_value="a" * 40,
        ),
        patch(
            "quickscale_core.utils.git_subtree.run_git_subtree_pull",
            side_effect=pull,
        ),
        patch(
            "quickscale_cli.commands._module_shared._read_embedded_module_version",
            return_value=pulled_version,
        ),
        patch(
            "quickscale_cli.commands._module_update_io._commit_module_update",
        ) as mock_commit,
    ):
        result = _update_single_module(
            "auth",
            module_info,
            "https://example.com/repo.git",
            no_preview=True,
        )
    return result, mock_commit


@pytest.fixture
def update_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A generated-project fixture whose cwd is the project root."""
    project = _write_update_project(tmp_path)
    monkeypatch.chdir(project)
    return project


def test_equal_label_migration_edit_is_refused_and_rolled_back(
    update_project: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A same-label rewrite of an applied migration is refused and restored."""
    project = update_project
    migration_path = _migrations_dir(project) / "0001_initial.py"

    def _pull(*, prefix, remote, branch, squash):
        del remote, branch, squash
        (
            project
            / prefix
            / "src"
            / "quickscale_modules_auth"
            / "migrations"
            / "0001_initial.py"
        ).write_text(_PULLED_MIGRATION)
        return "updated"

    result, mock_commit = _run_update(
        project, pulled_version=_MODULE_VERSION, pull=_pull
    )

    captured = capsys.readouterr()
    assert result is False
    assert (
        "applied migration content changed under the equal version label"
        " '0.71.0'" in captured.err
    )
    assert "migration '0001_initial.py' changed content" in captured.err
    assert "Reconcile the embedded module content" in captured.err
    # The rollback restored the applied content and nothing was committed.
    assert migration_path.read_text() == _APPLIED_MIGRATION
    mock_commit.assert_not_called()


def test_equal_label_migration_removal_is_refused_and_rolled_back(
    update_project: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A same-label pull that drops the migrations package is refused."""
    project = update_project
    migration_path = _migrations_dir(project) / "0001_initial.py"

    def _pull(*, prefix, remote, branch, squash):
        del remote, branch, squash
        shutil.rmtree(
            project / prefix / "src" / "quickscale_modules_auth" / "migrations"
        )
        return "updated"

    result, mock_commit = _run_update(
        project, pulled_version=_MODULE_VERSION, pull=_pull
    )

    captured = capsys.readouterr()
    assert result is False
    assert "migration '0001_initial.py' is no longer present" in captured.err
    assert migration_path.read_text() == _APPLIED_MIGRATION
    mock_commit.assert_not_called()


def test_equal_label_unidentifiable_updated_content_is_refused(
    update_project: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An updated module whose migration content cannot be hashed is refused."""
    project = update_project
    migration_path = _migrations_dir(project) / "0001_initial.py"

    def _pull(*, prefix, remote, branch, squash):
        del remote, branch, squash
        (
            project
            / prefix
            / "src"
            / "quickscale_modules_auth"
            / "migrations"
            / "0001_initial.py"
        ).unlink()
        return "updated"

    result, mock_commit = _run_update(
        project, pulled_version=_MODULE_VERSION, pull=_pull
    )

    captured = capsys.readouterr()
    assert result is False
    assert (
        "the updated module's migration content could not be identified" in captured.err
    )
    assert migration_path.read_text() == _APPLIED_MIGRATION
    mock_commit.assert_not_called()


def test_equal_label_added_migration_is_applied_forward(
    update_project: Path,
) -> None:
    """An added migration under an unchanged label is applied forward."""
    project = update_project

    def _pull(*, prefix, remote, branch, squash):
        del remote, branch, squash
        (
            project
            / prefix
            / "src"
            / "quickscale_modules_auth"
            / "migrations"
            / "0002_add_field.py"
        ).write_text("# new migration\n")
        return "updated"

    result, mock_commit = _run_update(
        project, pulled_version=_MODULE_VERSION, pull=_pull
    )

    assert result is True
    mock_commit.assert_called_once()
    assert (
        _migrations_dir(project) / "0002_add_field.py"
    ).read_text() == "# new migration\n"


def test_version_label_change_allows_a_migration_rewrite(
    update_project: Path,
) -> None:
    """A label change is a release upgrade; content comparison is skipped."""
    project = update_project
    migration_path = _migrations_dir(project) / "0001_initial.py"

    def _pull(*, prefix, remote, branch, squash):
        del remote, branch, squash
        (
            project
            / prefix
            / "src"
            / "quickscale_modules_auth"
            / "migrations"
            / "0001_initial.py"
        ).write_text(_PULLED_MIGRATION)
        return "updated"

    result, mock_commit = _run_update(project, pulled_version="0.82.0", pull=_pull)

    assert result is True
    mock_commit.assert_called_once()
    assert migration_path.read_text() == _PULLED_MIGRATION


def test_unidentifiable_applied_identity_skips_the_guard(
    update_project: Path,
) -> None:
    """A pre-pull tree without a source package leaves nothing to compare.

    Such a tree is repaired by the update itself, so the guard must not
    refuse it.
    """
    project = update_project
    shutil.rmtree(project / _MODULE_PREFIX / "src")

    def _pull(*, prefix, remote, branch, squash):
        del remote, branch, squash
        migrations_dir = (
            project / prefix / "src" / "quickscale_modules_auth" / "migrations"
        )
        migrations_dir.mkdir(parents=True)
        (migrations_dir / "0001_initial.py").write_text(_PULLED_MIGRATION)
        return "updated"

    result, mock_commit = _run_update(
        project, pulled_version=_MODULE_VERSION, pull=_pull
    )

    assert result is True
    mock_commit.assert_called_once()


def test_get_update_migration_issues_contract() -> None:
    """The mismatch helper reads applied files against the updated module."""
    assert _get_update_migration_issues(None, {"0001_initial.py": "x"}) == []
    assert _get_update_migration_issues({}, {"0001_initial.py": "x"}) == []
    assert _get_update_migration_issues({"0001_initial.py": "x"}, None) == [
        "the updated module's migration content could not be identified"
    ]
    assert (
        _get_update_migration_issues(
            {"0001_initial.py": "x"}, {"0001_initial.py": "x", "0002_a.py": "y"}
        )
        == []
    )
    assert _get_update_migration_issues(
        {"0001_initial.py": "x"}, {"0001_initial.py": "y"}
    ) == ["migration '0001_initial.py' changed content"]
    assert _get_update_migration_issues({"0001_initial.py": "x"}, {}) == [
        "migration '0001_initial.py' is no longer present"
    ]


def _run_git(project_path: Path, *args: str) -> str:
    """Run one git command in *project_path* and return its stripped stdout."""
    return subprocess.run(
        ["git", *args],
        cwd=project_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _init_git_repo(path: Path, *, bare: bool = False) -> None:
    """Create a git repository with a known branch and committer identity."""
    subprocess.run(
        ["git", "init", "-q", *(["--bare"] if bare else []), str(path)],
        check=True,
        capture_output=True,
    )
    if bare:
        return
    _run_git(path, "checkout", "-b", "source")
    _run_git(path, "config", "user.name", "Test User")
    _run_git(path, "config", "user.email", "test@example.invalid")


def _write_split_remote(tmp_path: Path) -> tuple[Path, str]:
    """Create a split-branch remote whose second commit rewrites ``0001``.

    The remote mirrors the real split layout — the module tree sits at the
    branch root — and keeps the version label unchanged across the rewrite.
    Returns the remote path and the first commit's SHA.
    """
    remote_dir = tmp_path / "remote.git"
    work_dir = tmp_path / "remote-work"
    _init_git_repo(remote_dir, bare=True)
    _init_git_repo(work_dir)
    migrations_dir = work_dir / "src" / "quickscale_modules_auth" / "migrations"
    migrations_dir.mkdir(parents=True)
    (work_dir / "module.yml").write_text(
        (_MODULE_MANIFEST_ROOT / "auth" / "module.yml").read_text()
    )
    (migrations_dir / "0001_initial.py").write_text(_APPLIED_MIGRATION)
    _run_git(work_dir, "add", "-A")
    _run_git(work_dir, "commit", "-qm", "initial module content")
    _run_git(work_dir, "push", "-q", str(remote_dir), "source")
    applied_sha = _run_git(work_dir, "rev-parse", "HEAD")
    (migrations_dir / "0001_initial.py").write_text(_PULLED_MIGRATION)
    _run_git(work_dir, "add", "-A")
    _run_git(work_dir, "commit", "-qm", "rewrite under the same label")
    _run_git(work_dir, "push", "-q", str(remote_dir), "source")
    return remote_dir, applied_sha


def _write_real_update_project(
    tmp_path: Path, remote_dir: Path, applied_sha: str
) -> Path:
    """Create a git project whose ``modules/auth`` subtree came from the remote."""
    project = tmp_path / "project"
    project.mkdir()
    _init_git_repo(project)
    (project / "pyproject.toml").write_text(
        '[tool.poetry.dependencies]\npython = "^3.14"\n'
    )
    (project / "quickscale.yml").write_text(
        "\n".join(
            [
                'version: "1"',
                "project:",
                "  slug: myapp",
                "  package: myapp",
                "  theme: showcase_react",
                "modules:",
                "  auth: {}",
                "docker:",
                "  start: false",
            ]
        )
        + "\n"
    )
    _run_git(project, "add", "-A")
    _run_git(project, "commit", "-qm", "scaffold")
    run_git_subtree_add(
        prefix=_MODULE_PREFIX,
        remote=str(remote_dir),
        branch=applied_sha,
        squash=True,
        path=project,
    )
    quickscale_dir = project / ".quickscale"
    quickscale_dir.mkdir()
    (quickscale_dir / "state.yml").write_text(
        yaml.dump(
            {
                "version": "1",
                "project": {
                    "slug": "myapp",
                    "package": "myapp",
                    "theme": "showcase_react",
                    "project_contract": CORE_VERSION,
                    "created_at": "2025-01-01T00:00:00",
                    "last_applied": "2025-01-01T00:00:00",
                },
                "modules": {
                    "auth": {
                        "name": "auth",
                        "version": CORE_VERSION,
                        "commit_sha": applied_sha,
                        "embedded_at": "2025-01-01T00:00:00",
                        "prefix": _MODULE_PREFIX,
                        "branch": "source",
                        "installed_at": "2025-01-01",
                    }
                },
            }
        )
    )
    _run_git(project, "add", "-A")
    _run_git(project, "commit", "-qm", "baseline")
    return project


def test_refused_real_subtree_pull_restores_git_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A refused real subtree pull must not leave the rejected content at HEAD.

    ``git subtree pull`` commits the pulled rewrite before the guard can
    refuse it, so the refusal has to restore the pre-pull content as the
    effective HEAD and commit that restoration; otherwise the rejected
    migration stays effective and the staged reversal blocks the next update.
    """
    remote_dir, applied_sha = _write_split_remote(tmp_path)
    project = _write_real_update_project(tmp_path, remote_dir, applied_sha)
    monkeypatch.chdir(project)
    migration_relpath = (
        f"{_MODULE_PREFIX}/src/quickscale_modules_auth/migrations/0001_initial.py"
    )
    applied_content = _run_git(project, "show", f"HEAD:{migration_relpath}")

    real_single_module_update = _update_single_module

    def _update_from_local_remote(name, info, default_remote, no_preview):
        del default_remote
        return real_single_module_update(name, info, str(remote_dir), no_preview)

    with (
        patch(
            "quickscale_cli.commands._module_update._update_single_module",
            side_effect=_update_from_local_remote,
        ),
        patch("click.confirm", return_value=True),
    ):
        result = CliRunner().invoke(
            update,
            ["--no-preview", "--acknowledge-contract-vintage"],
            catch_exceptions=False,
        )

    assert result.exit_code != 0
    assert (
        "applied migration content changed under the equal version label"
        in result.output
    )
    assert "migration '0001_initial.py' changed content" in result.output

    # The rejected rewrite is not the effective committed content, and the
    # restoration is committed so the next update starts from a clean tree.
    assert _run_git(project, "show", f"HEAD:{migration_relpath}") == applied_content
    assert _run_git(project, "status", "--porcelain") == ""
    assert "chore: roll back partial module update" in _run_git(
        project, "log", "--pretty=%s", "-n", "2"
    )
