"""End-to-end coverage for the embedded-module hand-edit guard (SA305)."""

from __future__ import annotations

import json
import subprocess
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml
from click.testing import CliRunner, Result

from quickscale_core import __version__ as CORE_VERSION
from quickscale_core.utils.git_subtree import run_git_subtree_add
from quickscale_cli.commands._module_update import update
from quickscale_cli.commands.status_command import status

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


def _init_git_repo(path: Path, *, bare: bool = False) -> None:
    """Create a git repository with a committer identity."""
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


def _write_split_remote(tmp_path: Path) -> tuple[Path, str, str]:
    """Create a split remote with an initial and a newer module commit."""
    remote_dir = tmp_path / "remote.git"
    work_dir = tmp_path / "remote-work"
    _init_git_repo(remote_dir, bare=True)
    _init_git_repo(work_dir)
    (work_dir / "module.yml").write_text(f'name: auth\nversion: "{CORE_VERSION}"\n')
    (work_dir / "pyproject.toml").write_text(
        "[project]\n"
        'name = "quickscale-module-auth"\n'
        "\n"
        "[tool.poetry.dependencies]\n"
        'python = "^3.14"\n'
        f'quickscale-core = ">={CORE_VERSION},<0.90.0"\n'
    )
    (work_dir / "src").mkdir()
    (work_dir / "src" / "auth.py").write_text("VALUE = 1\n")
    migrations_dir = work_dir / "src" / "quickscale_modules_auth" / "migrations"
    migrations_dir.mkdir(parents=True)
    (migrations_dir / "__init__.py").write_text("")
    (migrations_dir / "0001_initial.py").write_text("# applied migration\n")
    _run_git(work_dir, "add", "-A")
    _run_git(work_dir, "commit", "-qm", "initial module content")
    _run_git(work_dir, "push", "-q", str(remote_dir), "source")
    initial_sha = _run_git(work_dir, "rev-parse", "HEAD")

    (work_dir / "src" / "auth.py").write_text("VALUE = 2\n")
    _run_git(work_dir, "add", "-A")
    _run_git(work_dir, "commit", "-qm", "newer module content")
    _run_git(work_dir, "push", "-q", str(remote_dir), "source")
    latest_sha = _run_git(work_dir, "rev-parse", "HEAD")
    return remote_dir, initial_sha, latest_sha


def _write_project(tmp_path: Path, remote_dir: Path, commit_sha: str) -> Path:
    """Create a clean project whose auth module came from the split remote."""
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
        branch=commit_sha,
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
                        "commit_sha": commit_sha,
                        "embedded_at": "2025-01-01T00:00:00",
                        "prefix": _MODULE_PREFIX,
                        "branch": "source",
                        "installed_at": "2025-01-01",
                    }
                },
            },
            sort_keys=False,
        )
    )
    _run_git(project, "add", "-A")
    _run_git(project, "commit", "-qm", "state baseline")
    return project


def _commit_local_edit(project: Path) -> Path:
    """Commit a hand edit under the embedded module."""
    edited_path = project / _MODULE_PREFIX / "src" / "auth.py"
    edited_path.write_text("VALUE = 'local fix'\n")
    _run_git(project, "add", "-A")
    _run_git(project, "commit", "-qm", "hand fix")
    return edited_path


def _rewrite_state_commit_sha(project: Path, commit_sha: str | None) -> None:
    """Replace or remove the module's recorded commit in state.yml."""
    state_path = project / ".quickscale" / "state.yml"
    state = yaml.safe_load(state_path.read_text())
    if commit_sha is None:
        state["modules"]["auth"].pop("commit_sha", None)
    else:
        state["modules"]["auth"]["commit_sha"] = commit_sha
    state_path.write_text(yaml.dump(state, sort_keys=False))
    _run_git(project, "add", "-A")
    _run_git(project, "commit", "-qm", "state update")


def _patched_update(
    latest_sha: str,
    args: list[str],
    *,
    pull_mock: object | None = None,
) -> tuple[Result, object]:
    """Invoke ``quickscale update`` without network or wiring regeneration."""
    pull = pull_mock if pull_mock is not None else Mock(return_value="updated")
    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "quickscale_core.utils.git_repo.resolve_remote_ref",
                return_value=latest_sha,
            )
        )
        stack.enter_context(
            patch(
                "quickscale_cli.commands.contract_vintage.enforce_shipped_contract_vintage"
            )
        )
        stack.enter_context(
            patch(
                "quickscale_cli.commands._module_update._regenerate_update_wiring",
                return_value=True,
            )
        )
        stack.enter_context(
            patch(
                "quickscale_core.utils.git_subtree.run_git_subtree_pull",
                pull,
            )
        )
        return CliRunner().invoke(update, args, input="y\n"), pull


def test_update_refuses_a_committed_hand_edit_and_names_the_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default update stops before any pull and lists the edited file."""
    remote_dir, initial_sha, latest_sha = _write_split_remote(tmp_path)
    project = _write_project(tmp_path, remote_dir, initial_sha)
    _commit_local_edit(project)
    monkeypatch.chdir(project)

    result, pull = _patched_update(latest_sha, ["--no-preview"])

    assert result.exit_code != 0
    assert "Local changes detected in embedded module(s)" in result.output
    assert f"{_MODULE_PREFIX}/src/auth.py" in result.output
    assert "--allow-local-changes" in result.output
    pull.assert_not_called()


def test_update_allows_the_override_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The override flag lets the update proceed past the hand-edit guard."""
    remote_dir, initial_sha, latest_sha = _write_split_remote(tmp_path)
    project = _write_project(tmp_path, remote_dir, initial_sha)
    _commit_local_edit(project)
    monkeypatch.chdir(project)

    result, pull = _patched_update(
        latest_sha, ["--no-preview", "--allow-local-changes"]
    )

    assert result.exit_code == 0, result.output
    assert "may be overwritten" in result.output
    pull.assert_called_once()
    state = yaml.safe_load((project / ".quickscale" / "state.yml").read_text())
    assert state["modules"]["auth"]["commit_sha"] == latest_sha


def test_status_reports_the_same_module_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``quickscale status`` prints the changed path and exposes it in JSON."""
    remote_dir, initial_sha, _ = _write_split_remote(tmp_path)
    project = _write_project(tmp_path, remote_dir, initial_sha)
    _commit_local_edit(project)
    monkeypatch.chdir(project)
    runner = CliRunner()

    text_result = runner.invoke(status, [])

    assert text_result.exit_code == 0, text_result.output
    assert "Module content drift" in text_result.output
    assert f"{_MODULE_PREFIX}/src/auth.py" in text_result.output

    json_result = runner.invoke(status, ["--json"])

    assert json_result.exit_code == 0, json_result.output
    payload = json.loads(json_result.output)
    drift = payload["drift"]["module_content_drift"]
    assert drift[0]["module"] == "auth"
    assert drift[0]["changed_paths"] == [f"{_MODULE_PREFIX}/src/auth.py"]
    assert drift[0]["unverifiable_reason"] is None


@pytest.mark.parametrize(
    ("commit_sha", "reason_fragment"),
    [
        (None, "does not record a commit_sha"),
        ("b" * 40, "not in this project's git history"),
    ],
)
def test_update_refuses_unverifiable_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    commit_sha: str | None,
    reason_fragment: str,
) -> None:
    """A missing or unavailable baseline is refused, not silently accepted."""
    remote_dir, initial_sha, latest_sha = _write_split_remote(tmp_path)
    project = _write_project(tmp_path, remote_dir, initial_sha)
    _rewrite_state_commit_sha(project, commit_sha)
    monkeypatch.chdir(project)

    result, pull = _patched_update(latest_sha, ["--no-preview"])

    assert result.exit_code != 0
    assert "Cannot verify embedded module(s)" in result.output
    assert reason_fragment in result.output
    assert "--allow-local-changes" in result.output
    pull.assert_not_called()


def test_update_allows_override_for_unverifiable_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The override flag explicitly authorizes proceeding without a baseline."""
    remote_dir, initial_sha, latest_sha = _write_split_remote(tmp_path)
    project = _write_project(tmp_path, remote_dir, initial_sha)
    _rewrite_state_commit_sha(project, None)
    monkeypatch.chdir(project)

    result, pull = _patched_update(
        latest_sha, ["--no-preview", "--allow-local-changes"]
    )

    assert result.exit_code == 0, result.output
    assert "continuing because --allow-local-changes was passed" in result.output
    pull.assert_called_once()
