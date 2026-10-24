"""Coverage for the journaled module-set update transaction (SA319 (b))."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import click
import pytest
import yaml
from click.testing import CliRunner

from quickscale_core import __version__ as CORE_VERSION
from quickscale_core.project_state_manager import ProjectStateManager
from quickscale_core.schema.state_schema import StateManager
from quickscale_cli.commands import _context
from quickscale_cli.commands import _module_update
from quickscale_cli.commands import _module_update_guard
import quickscale_cli.commands._module_update_seal as _module_update_seal
from quickscale_cli.commands import _module_update_journal as journal
from quickscale_cli.commands._module_shared import _validate_update_environment
from quickscale_cli.commands._module_update import (
    _run_update_under_lock,
    update,
)
from quickscale_cli.commands._module_update_journal import (
    _ModuleUpdateTarget,
    _UpdateJournalError,
)

_REAL_MISSING_REQUIRED = _module_update._missing_required_module_error

_MODULES = ("backups", "notifications")
_PREFIX = "modules"


class _SimulatedKill(BaseException):
    """A hard interruption that bypasses the handled-failure rollback."""


@pytest.fixture(autouse=True)
def _stub_module_content_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fixtures embed modules without a real subtree history."""
    monkeypatch.setattr(
        _module_update_guard,
        "_collect_module_content_drift",
        lambda state, project_path: [],
    )


def _git(project: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _write_project(tmp_path: Path) -> Path:
    """Create a two-module generated project as a real git repository."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "myapp" / "settings").mkdir(parents=True)
    (project / "myapp" / "__init__.py").write_text("")
    (project / "myapp" / "settings" / "__init__.py").write_text("")
    (project / "myapp" / "settings" / "modules.py").write_text("# managed\n")
    (project / "myapp" / "urls_modules.py").write_text("# managed urls\n")
    (project / "pyproject.toml").write_text(
        '[tool.poetry.dependencies]\npython = "^3.14"\n'
    )
    (project / ".gitignore").write_text(".quickscale/*.lock\n")
    (project / "quickscale.yml").write_text(
        "\n".join(
            [
                'version: "1"',
                "project:",
                "  slug: myapp",
                "  package: myapp",
                "  theme: showcase_react",
                "modules:",
                *[f"  {name}: {{}}" for name in _MODULES],
                "docker:",
                "  start: false",
                "",
            ]
        )
    )
    state_dir = project / ".quickscale"
    state_dir.mkdir()
    (state_dir / "state.yml").write_text(
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
                    name: {
                        "name": name,
                        "version": "0.88.0",
                        "commit_sha": "c" * 40,
                        "embedded_at": "2025-01-01T00:00:00",
                        "prefix": f"{_PREFIX}/{name}",
                        "branch": f"splits/{name}-module",
                        "installed_at": "2025-01-01",
                        "options": {},
                    }
                    for name in _MODULES
                },
                "managed_files": {},
            },
            sort_keys=False,
        )
    )
    for name in _MODULES:
        module_dir = project / _PREFIX / name
        module_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text(
            f'name: {name}\nversion: "{CORE_VERSION}"\n'
        )
        (module_dir / "pulled.py").write_text("# old content\n")
    for command in (
        ["init", "-q"],
        ["config", "user.name", "Test User"],
        ["config", "user.email", "test@example.invalid"],
        ["add", "-A"],
        ["commit", "-qm", "baseline"],
    ):
        _git(project, *command)
    return project


def _commit_pull(project: Path, prefix: str) -> str:
    """Mirror the transport commit a real ``git subtree pull`` creates."""
    module_name = prefix.rsplit("/", 1)[-1]
    (project / prefix / "module.yml").write_text(
        f'name: {module_name}\nversion: "{CORE_VERSION}"\n'
    )
    (project / prefix / "pulled.py").write_text("# updated content\n")
    _git(project, "add", "-A", "--", prefix)
    _git(project, "commit", "-qm", f"subtree pull {module_name}")
    return "updated"


def _pull_side_effect(project: Path, *, kill_on: str | None = None, probe=None):
    def _pull(prefix: str, remote: str, branch: str, squash: bool) -> str:
        del remote, branch, squash
        module_name = prefix.rsplit("/", 1)[-1]
        if kill_on == module_name:
            raise _SimulatedKill
        if probe is not None:
            probe(project)
        return _commit_pull(project, prefix)

    return _pull


def _fake_content_matcher(project: Path, target: _ModuleUpdateTarget) -> bool:
    """The fake pulls write this marker instead of a real split commit."""
    return (
        project / _PREFIX / target.name / "pulled.py"
    ).read_text() == "# updated content\n"


def _journal_present_with_the_set(project: Path) -> None:
    recorded = journal._load_update_journal(project)
    assert recorded is not None
    assert {target.name for target in recorded.targets} == set(_MODULES)
    assert recorded.pre_update_head


def _state_save_spy() -> tuple[object, list[object]]:
    calls: list[object] = []
    real_save = ProjectStateManager.save_state

    def _save(self, state):
        calls.append(state)
        real_save(self, state)

    return _save, calls


def _invoke_update(project: Path, monkeypatch: pytest.MonkeyPatch, *args: str):
    monkeypatch.chdir(project)
    with patch("click.confirm", return_value=True):
        return CliRunner().invoke(update, ["--no-preview", *args])


def test_update_journals_the_set_writes_state_once_and_commits_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = _write_project(tmp_path)
    spy, save_calls = _state_save_spy()

    with (
        patch(
            "quickscale_core.utils.git_repo.resolve_remote_ref",
            return_value="a" * 40,
        ),
        patch(
            "quickscale_core.utils.git_subtree.run_git_subtree_pull",
            side_effect=_pull_side_effect(project, probe=_journal_present_with_the_set),
        ),
        patch(
            "quickscale_cli.commands._module_embed._sync_module_dependencies",
            return_value=True,
        ),
        patch(
            "quickscale_cli.commands._module_update_io._regenerate_and_record_managed_wiring",
            return_value=(True, "regenerated"),
        ),
        patch.object(ProjectStateManager, "save_state", spy),
        patch.object(
            _module_update, "_missing_required_module_error", return_value=None
        ),
    ):
        result = _invoke_update(project, monkeypatch, "--acknowledge-contract-vintage")

    assert result.exit_code == 0, result.output
    assert journal._update_journal_path(project).exists() is False
    assert len(save_calls) == 1

    state = StateManager(project).load()
    assert state is not None
    for name in _MODULES:
        assert state.modules[name].version == CORE_VERSION
        assert state.modules[name].commit_sha == "a" * 40
        assert state.modules[name].branch == f"splits/{name}-module"
        assert (
            project / _PREFIX / name / "module.yml"
        ).read_text() == f'name: {name}\nversion: "{CORE_VERSION}"\n'

    messages = _git(project, "log", "--pretty=%s").splitlines()
    assert messages.count("chore(modules): update installed modules") == 1
    assert not any(
        message.startswith("chore(modules): update ")
        and message != "chore(modules): update installed modules"
        for message in messages
    )
    assert _git(project, "status", "--porcelain") == ""
    committed = _git(project, "show", "--name-only", "--format=", "HEAD").split()
    assert "update-journal.yml" not in committed


def test_killed_update_resumes_to_one_coherent_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = _write_project(tmp_path)
    monkeypatch.chdir(project)
    state = ProjectStateManager(project).load_state()
    assert state is not None

    with (
        patch(
            "quickscale_core.utils.git_repo.resolve_remote_ref",
            return_value="a" * 40,
        ),
        patch(
            "quickscale_core.utils.git_subtree.run_git_subtree_pull",
            side_effect=_pull_side_effect(project, kill_on=_MODULES[1]),
        ),
        patch(
            "quickscale_cli.commands._module_embed._sync_module_dependencies",
            return_value=True,
        ),
        patch(
            "quickscale_cli.commands._module_update_io._regenerate_and_record_managed_wiring",
            return_value=(True, "regenerated"),
        ),
        patch.object(_module_update, "_module_matches_target", _fake_content_matcher),
        patch.object(
            _module_update, "_missing_required_module_error", return_value=None
        ),
    ):
        with pytest.raises(_SimulatedKill):
            _run_update_under_lock(
                state,
                project,
                no_preview=True,
                confirm_contract_adoption=False,
                allow_local_changes=False,
            )

    # The journal survives a hard interruption; the first module's transport
    # commit is at HEAD while state still describes the old set.
    assert journal._update_journal_path(project).exists()
    interrupted = StateManager(project).load()
    assert interrupted is not None
    assert interrupted.modules[_MODULES[0]].commit_sha == "c" * 40
    assert (
        project / _PREFIX / _MODULES[0] / "pulled.py"
    ).read_text() == "# updated content\n"
    assert (
        project / _PREFIX / _MODULES[1] / "pulled.py"
    ).read_text() == "# old content\n"

    spy, save_calls = _state_save_spy()
    resumed_state = ProjectStateManager(project).load_state()
    assert resumed_state is not None
    with (
        patch(
            "quickscale_core.utils.git_repo.resolve_remote_ref",
            return_value="a" * 40,
        ),
        patch(
            "quickscale_core.utils.git_subtree.run_git_subtree_pull",
            side_effect=_pull_side_effect(project),
        ),
        patch(
            "quickscale_cli.commands._module_embed._sync_module_dependencies",
            return_value=True,
        ),
        patch(
            "quickscale_cli.commands._module_update_io._regenerate_and_record_managed_wiring",
            return_value=(True, "regenerated"),
        ),
        patch.object(_module_update, "_module_matches_target", _fake_content_matcher),
        patch.object(ProjectStateManager, "save_state", spy),
    ):
        outcome = _run_update_under_lock(
            resumed_state,
            project,
            no_preview=True,
            confirm_contract_adoption=False,
            allow_local_changes=False,
        )

    assert outcome.failed_modules == []
    assert journal._update_journal_path(project).exists() is False
    assert len(save_calls) == 1
    final_state = StateManager(project).load()
    assert final_state is not None
    for name in _MODULES:
        assert final_state.modules[name].version == CORE_VERSION
        assert final_state.modules[name].commit_sha == "a" * 40
        assert (project / _PREFIX / name / "pulled.py").read_text() == (
            "# updated content\n"
        )
    assert _git(project, "status", "--porcelain") == ""
    messages = _git(project, "log", "--pretty=%s").splitlines()
    assert messages.count("chore(modules): update installed modules") == 1


def test_resume_reloads_state_after_a_crash_between_the_state_write_and_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The restored state, not the interrupted run's state, drives the rerun.

    A crash after ``state.yml`` was written but before the set commit leaves
    a journal plus a new state file over mixed content.  Recovery restores
    both files; the flow must reload state before the hand-edit guard judges
    the restored tree.
    """
    project = _write_project(tmp_path)
    monkeypatch.chdir(project)
    pre_update_head = _git(project, "rev-parse", "HEAD")
    journal._write_update_journal(
        project,
        pre_update_head=pre_update_head,
        targets=tuple(
            _ModuleUpdateTarget(name, CORE_VERSION, f"splits/{name}-module", "a" * 40)
            for name in _MODULES
        ),
    )
    # Simulate the interrupted run: one pull landed and state.yml was saved
    # for the whole set before the process died.
    _commit_pull(project, f"{_PREFIX}/backups")
    state_path = project / ".quickscale" / "state.yml"
    state_document = yaml.safe_load(state_path.read_text())
    for name in _MODULES:
        state_document["modules"][name]["version"] = CORE_VERSION
        state_document["modules"][name]["commit_sha"] = "a" * 40
    state_path.write_text(yaml.safe_dump(state_document, sort_keys=False))
    _git(project, "add", "-A", "--", ".quickscale/state.yml")
    _git(project, "commit", "-qm", "interrupted state write")

    state = ProjectStateManager(project).load_state()
    assert state is not None
    with (
        patch(
            "quickscale_core.utils.git_repo.resolve_remote_ref",
            return_value="a" * 40,
        ),
        patch(
            "quickscale_core.utils.git_subtree.run_git_subtree_pull",
            side_effect=_pull_side_effect(project),
        ),
        patch(
            "quickscale_cli.commands._module_embed._sync_module_dependencies",
            return_value=True,
        ),
        patch(
            "quickscale_cli.commands._module_update_io._regenerate_and_record_managed_wiring",
            return_value=(True, "regenerated"),
        ),
        patch.object(_module_update, "_module_matches_target", _fake_content_matcher),
    ):
        outcome = _run_update_under_lock(
            state,
            project,
            no_preview=True,
            confirm_contract_adoption=False,
            allow_local_changes=False,
        )

    assert outcome.failed_modules == []
    final_state = StateManager(project).load()
    assert final_state is not None
    for name in _MODULES:
        assert final_state.modules[name].version == CORE_VERSION
        assert final_state.modules[name].commit_sha == "a" * 40
        assert (project / _PREFIX / name / "pulled.py").read_text() == (
            "# updated content\n"
        )
    assert journal._update_journal_path(project).exists() is False


def test_public_update_resumes_with_uncommitted_transaction_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The public CLI recovers before the ordinary clean-tree gate refuses."""
    project = _write_project(tmp_path)
    pre_update_head = _git(project, "rev-parse", "HEAD")
    targets = tuple(
        _ModuleUpdateTarget(name, CORE_VERSION, f"splits/{name}-module", "a" * 40)
        for name in _MODULES
    )
    journal._write_update_journal(
        project, pre_update_head=pre_update_head, targets=targets
    )
    state_path = project / ".quickscale" / "state.yml"
    state_document = yaml.safe_load(state_path.read_text())
    state_document["modules"][_MODULES[0]]["version"] = "0.89.1"
    state_path.write_text(yaml.safe_dump(state_document, sort_keys=False))
    (project / "pyproject.toml").write_text(
        '[tool.poetry.dependencies]\npython = "^3.14"\n# interrupted\n'
    )
    # A managed output the interrupted regeneration created before its commit:
    # Git reports it as an individual untracked file, not a collapsed dir.
    (project / ".github").mkdir()
    (project / ".github" / "quickscale-ci-env").write_text("POSTHOG_API_KEY=ph_test\n")

    with (
        patch(
            "quickscale_core.utils.git_subtree.run_git_subtree_pull",
            side_effect=_pull_side_effect(project),
        ),
        patch(
            "quickscale_cli.commands._module_embed._sync_module_dependencies",
            return_value=True,
        ),
        patch(
            "quickscale_cli.commands._module_update_io._regenerate_and_record_managed_wiring",
            return_value=(True, "regenerated"),
        ),
        patch.object(_module_update, "_module_matches_target", _fake_content_matcher),
        patch.object(
            _module_update, "_missing_required_module_error", return_value=None
        ),
    ):
        result = _invoke_update(project, monkeypatch, "--acknowledge-contract-vintage")

    assert result.exit_code == 0, result.output
    assert journal._update_journal_path(project).exists() is False
    state = StateManager(project).load()
    assert state is not None
    for name in _MODULES:
        assert state.modules[name].version == CORE_VERSION
        assert state.modules[name].commit_sha == "a" * 40
    assert _git(project, "status", "--porcelain") == ""


def _write_two_split_branches(
    tmp_path: Path,
) -> tuple[Path, dict[str, str], dict[str, str]]:
    """Create a bare remote with one sealed-shape branch per fixture module."""
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", str(remote)], check=True, capture_output=True
    )
    initials: dict[str, str] = {}
    targets: dict[str, str] = {}
    for name in _MODULES:
        work = tmp_path / f"work-{name}"
        work.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=work, check=True, capture_output=True)
        _git(work, "config", "user.name", "Test User")
        _git(work, "config", "user.email", "test@example.invalid")
        _git(work, "checkout", "-b", f"splits/{name}-module")
        (work / "module.yml").write_text(f'name: {name}\nversion: "{CORE_VERSION}"\n')
        (work / "pulled.py").write_text("# old content\n")
        _git(work, "add", "-A")
        _git(work, "commit", "-qm", "initial module content")
        initials[name] = _git(work, "rev-parse", "HEAD")
        _git(work, "push", "-q", str(remote), f"splits/{name}-module")
        (work / "pulled.py").write_text("# updated content\n")
        _git(work, "add", "-A")
        _git(work, "commit", "-qm", "updated module content")
        targets[name] = _git(work, "rev-parse", "HEAD")
        _git(work, "push", "-q", str(remote), f"splits/{name}-module")
    return remote, initials, targets


def _write_real_project(tmp_path: Path, remote: Path, initials: dict[str, str]) -> Path:
    """Create a project whose module subtrees came from the split remote."""
    from quickscale_core.utils.git_subtree import run_git_subtree_add

    project = _write_project(tmp_path)
    for name in _MODULES:
        shutil.rmtree(project / _PREFIX / name)
    _git(project, "add", "-A")
    _git(project, "commit", "-qm", "prepare for subtree add")
    state_path = project / ".quickscale" / "state.yml"
    state_document = yaml.safe_load(state_path.read_text())
    for name in _MODULES:
        run_git_subtree_add(
            prefix=f"{_PREFIX}/{name}",
            remote=str(remote),
            branch=initials[name],
            squash=True,
            path=project,
        )
        state_document["modules"][name]["commit_sha"] = initials[name]
        state_document["modules"][name]["version"] = "0.88.0"
    state_path.write_text(yaml.safe_dump(state_document, sort_keys=False))
    _git(project, "add", "-A")
    _git(project, "commit", "-qm", "embedded module baseline")
    return project


def test_real_subtree_resume_skips_completed_pulls_and_finishes_the_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A completed subtree pull is not re-pulled; the remaining one is."""
    from quickscale_core.utils.git_subtree import run_git_subtree_pull

    remote, initials, targets = _write_two_split_branches(tmp_path)
    project = _write_real_project(tmp_path, remote, initials)
    pre_update_head = _git(project, "rev-parse", "HEAD")
    journal._write_update_journal(
        project,
        pre_update_head=pre_update_head,
        targets=tuple(
            _ModuleUpdateTarget(
                name, CORE_VERSION, f"splits/{name}-module", targets[name]
            )
            for name in _MODULES
        ),
    )
    # Simulate the interrupted run: the first module's real subtree pull committed,
    # never ran, and state.yml still describes the old set.
    run_git_subtree_pull(
        prefix=f"{_PREFIX}/backups",
        remote=str(remote),
        branch=targets["backups"],
        squash=True,
        path=project,
    )
    assert (
        project / _PREFIX / _MODULES[0] / "pulled.py"
    ).read_text() == "# updated content\n"

    with (
        patch.object(_module_update, "_MODULE_UPDATE_REMOTE", str(remote)),
        patch(
            "quickscale_cli.commands._module_embed._sync_module_dependencies",
            return_value=True,
        ),
        patch(
            "quickscale_cli.commands._module_update_io._regenerate_and_record_managed_wiring",
            return_value=(True, "regenerated"),
        ),
        patch("click.confirm", return_value=True),
    ):
        monkeypatch.chdir(project)
        result = CliRunner().invoke(
            update, ["--no-preview", "--acknowledge-contract-vintage"]
        )

    assert result.exit_code == 0, result.output
    # The completed pull is still at its target and was not reverted; the
    # remaining module reached the same target through a real subtree pull.
    for name in _MODULES:
        assert (project / _PREFIX / name / "pulled.py").read_text() == (
            "# updated content\n"
        )
    state = StateManager(project).load()
    assert state is not None
    for name in _MODULES:
        assert state.modules[name].commit_sha == targets[name]
        assert state.modules[name].version == CORE_VERSION
    assert journal._update_journal_path(project).exists() is False
    assert _git(project, "status", "--porcelain") == ""


def test_resume_refuses_unrelated_staged_work_before_restoring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Operator work outside the transaction is never committed by recovery."""
    project = _write_project(tmp_path)
    pre_update_head = _git(project, "rev-parse", "HEAD")
    journal._write_update_journal(
        project,
        pre_update_head=pre_update_head,
        targets=tuple(
            _ModuleUpdateTarget(name, CORE_VERSION, f"splits/{name}-module", "a" * 40)
            for name in _MODULES
        ),
    )
    (project / "operator-note.txt").write_text("keep me\n")
    _git(project, "add", "--", "operator-note.txt")

    with (
        patch("quickscale_core.utils.git_subtree.run_git_subtree_pull") as mock_pull,
        patch.object(_module_update, "_module_matches_target", _fake_content_matcher),
    ):
        result = _invoke_update(project, monkeypatch, "--acknowledge-contract-vintage")

    assert result.exit_code != 0
    assert "Uncommitted changes outside the interrupted update's files" in result.output
    mock_pull.assert_not_called()
    assert _git(project, "rev-parse", "HEAD") == pre_update_head
    assert "operator-note.txt" in _git(project, "diff", "--cached", "--name-only")
    assert (project / "operator-note.txt").read_text() == "keep me\n"
    assert journal._update_journal_path(project).exists()


def test_local_guard_refusal_never_creates_a_journal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pre-pull guard refusal leaves apply reachable on every retry."""
    project = _write_project(tmp_path)
    (project / "quickscale.yml").write_text(
        "\n".join(
            [
                'version: "1"',
                "project:",
                "  slug: myapp",
                "  package: myapp",
                "  theme: showcase_react",
                "modules:",
                f"  {_MODULES[0]}: {{}}",
                "docker:",
                "  start: false",
                "",
            ]
        )
    )

    _git(project, "add", "quickscale.yml")
    _git(project, "commit", "-qm", "desired state removes a module")

    with patch("quickscale_core.utils.git_subtree.run_git_subtree_pull") as mock_pull:
        first = _invoke_update(project, monkeypatch, "--acknowledge-contract-vintage")
        second = _invoke_update(project, monkeypatch, "--acknowledge-contract-vintage")

    assert first.exit_code != 0
    assert second.exit_code != 0
    assert "no longer includes this installed module" in first.output
    assert "no longer includes this installed module" in second.output
    assert journal._update_journal_path(project).exists() is False
    mock_pull.assert_not_called()


def test_target_only_required_module_is_fetched_before_journal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A requirement present only in the target refuses before the journal.

    The seal can equal the branch tip, in which case preflight has no reason
    to fetch the target object; the requirement check must fetch it itself
    instead of silently treating the target manifest as absent.
    """
    remote, initials, targets = _write_two_split_branches(tmp_path)
    work = tmp_path / "work-backups"
    (work / "module.yml").write_text(
        f'name: backups\nversion: "{CORE_VERSION}"\nrequired_modules:\n  - storage\n'
    )
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "target requires storage")
    targets["backups"] = _git(work, "rev-parse", "HEAD")
    _git(work, "push", "-q", str(remote), "splits/backups-module")

    project = _write_project(tmp_path)
    monkeypatch.chdir(project)
    state = ProjectStateManager(project).load_state()
    assert state is not None
    plans = {
        name: _module_update_seal._UpdateSealPlan(
            module=name,
            version=CORE_VERSION,
            tag=f"splits/{name}-module/{CORE_VERSION}",
            tag_sha=targets[name],
            branch=f"splits/{name}-module",
            branch_sha=targets[name],
        )
        for name in _MODULES
    }

    with patch.object(_module_update, "_MODULE_UPDATE_REMOTE", str(remote)):
        error = _REAL_MISSING_REQUIRED(project, state, plans)

    assert error is not None
    assert "'backups' requires 'storage'" in error
    target_check = subprocess.run(
        ["git", "cat-file", "-e", f"{targets['backups']}^{{commit}}"],
        cwd=project,
        capture_output=True,
        check=False,
    )
    assert target_check.returncode == 0


def test_crash_after_the_set_commit_clears_the_journal_without_redoing_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An already-committed transaction is recognized, not restored again."""
    project = _write_project(tmp_path)
    pre_update_head = _git(project, "rev-parse", "HEAD")
    state_path = project / ".quickscale" / "state.yml"
    state_document = yaml.safe_load(state_path.read_text())
    for name in _MODULES:
        state_document["modules"][name]["version"] = CORE_VERSION
        state_document["modules"][name]["commit_sha"] = "a" * 40
        (project / _PREFIX / name / "pulled.py").write_text("# updated content\n")
    state_document["project"]["adopted_contract_steps"] = ["sa-test-adoption"]
    state_path.write_text(yaml.safe_dump(state_document, sort_keys=False))
    recorded = journal._write_update_journal(
        project,
        pre_update_head=pre_update_head,
        targets=tuple(
            _ModuleUpdateTarget(name, CORE_VERSION, f"splits/{name}-module", "a" * 40)
            for name in _MODULES
        ),
    )
    _git(project, "add", "-A", "--", "modules", ".quickscale/state.yml")
    _git(
        project,
        "commit",
        "-qm",
        "chore(modules): update installed modules"
        f"\n\nQS-Update-Transaction: {recorded.transaction_id}",
    )
    set_head = _git(project, "rev-parse", "HEAD")
    commit_count = int(_git(project, "rev-list", "--count", "HEAD"))

    with (
        patch("quickscale_core.utils.git_subtree.run_git_subtree_pull") as mock_pull,
        patch.object(_module_update, "_module_matches_target", _fake_content_matcher),
    ):
        result = _invoke_update(project, monkeypatch, "--acknowledge-contract-vintage")

    assert result.exit_code == 0, result.output
    assert journal._update_journal_path(project).exists() is False
    assert _git(project, "rev-parse", "HEAD") == set_head
    assert int(_git(project, "rev-list", "--count", "HEAD")) == commit_count
    mock_pull.assert_not_called()
    final_state = StateManager(project).load()
    assert final_state is not None
    assert final_state.project.adopted_contract_steps == ["sa-test-adoption"]


def test_resume_recovers_when_state_was_deleted_mid_restoration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing state.yml does not turn a pending recovery into a no-op."""
    project = _write_project(tmp_path)
    pre_update_head = _git(project, "rev-parse", "HEAD")
    journal._write_update_journal(
        project,
        pre_update_head=pre_update_head,
        targets=tuple(
            _ModuleUpdateTarget(name, CORE_VERSION, f"splits/{name}-module", "a" * 40)
            for name in _MODULES
        ),
    )
    (project / ".quickscale" / "state.yml").unlink()

    with (
        patch(
            "quickscale_core.utils.git_subtree.run_git_subtree_pull",
            side_effect=_pull_side_effect(project),
        ),
        patch(
            "quickscale_cli.commands._module_embed._sync_module_dependencies",
            return_value=True,
        ),
        patch(
            "quickscale_cli.commands._module_update_io._regenerate_and_record_managed_wiring",
            return_value=(True, "regenerated"),
        ),
        patch.object(_module_update, "_module_matches_target", _fake_content_matcher),
        patch.object(
            _module_update, "_missing_required_module_error", return_value=None
        ),
    ):
        result = _invoke_update(project, monkeypatch, "--acknowledge-contract-vintage")

    assert result.exit_code == 0, result.output
    assert "No modules installed" not in result.output
    assert (project / ".quickscale" / "state.yml").exists()
    assert journal._update_journal_path(project).exists() is False
    final_state = StateManager(project).load()
    assert final_state is not None
    for name in _MODULES:
        assert final_state.modules[name].commit_sha == "a" * 40
    assert _git(project, "status", "--porcelain") == ""


def test_noop_transaction_is_not_mistaken_for_an_already_committed_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A no-op update still finalizes its adoption instead of short-circuiting."""
    project = _write_project(tmp_path)
    state_path = project / ".quickscale" / "state.yml"
    state_document = yaml.safe_load(state_path.read_text())
    for name in _MODULES:
        state_document["modules"][name]["commit_sha"] = "a" * 40
        (project / _PREFIX / name / "pulled.py").write_text("# updated content\n")
    state_document["project"].pop("adopted_contract_steps", None)
    state_path.write_text(yaml.safe_dump(state_document, sort_keys=False))
    _git(project, "add", "-A", "--", "modules", ".quickscale/state.yml")
    _git(project, "commit", "-qm", "already at target")
    pre_update_head = _git(project, "rev-parse", "HEAD")
    journal._write_update_journal(
        project,
        pre_update_head=pre_update_head,
        targets=tuple(
            _ModuleUpdateTarget(name, CORE_VERSION, f"splits/{name}-module", "a" * 40)
            for name in _MODULES
        ),
    )
    (project / "operator-note.txt").write_text("unrelated\n")
    _git(project, "add", "operator-note.txt")
    _git(project, "commit", "-qm", "operator note")

    with (
        patch("quickscale_core.utils.git_subtree.run_git_subtree_pull") as mock_pull,
        patch(
            "quickscale_cli.commands._module_embed._sync_module_dependencies",
            return_value=True,
        ),
        patch(
            "quickscale_cli.commands._module_update_io._regenerate_and_record_managed_wiring",
            return_value=(True, "regenerated"),
        ),
        patch.object(_module_update, "_module_matches_target", _fake_content_matcher),
    ):
        result = _invoke_update(project, monkeypatch, "--confirm-contract-adoption")

    assert result.exit_code == 0, result.output
    assert "already completed" not in result.output
    mock_pull.assert_not_called()
    assert journal._update_journal_path(project).exists() is False
    assert _git(project, "rev-parse", "HEAD") != pre_update_head
    final_state = StateManager(project).load()
    assert final_state is not None
    assert final_state.project.adopted_contract_steps


def test_malformed_journal_fails_closed_before_any_pull(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = _write_project(tmp_path)
    monkeypatch.chdir(project)
    (project / ".quickscale" / "update-journal.yml").write_text("modules: [\n")
    state = ProjectStateManager(project).load_state()
    assert state is not None

    with (
        patch("quickscale_core.utils.git_subtree.run_git_subtree_pull") as mock_pull,
        pytest.raises(_UpdateJournalError),
    ):
        _run_update_under_lock(
            state,
            project,
            no_preview=True,
            confirm_contract_adoption=False,
            allow_local_changes=False,
        )

    mock_pull.assert_not_called()
    assert (project / ".quickscale" / "update-journal.yml").exists()


def test_malformed_target_manifest_refuses_before_journal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A target manifest that cannot be validated fails closed."""
    project = _write_project(tmp_path)
    monkeypatch.chdir(project)
    (project / "module.yml").write_text("required_modules: [\n")
    _git(project, "add", "module.yml")
    _git(project, "commit", "-qm", "malformed target manifest")
    target = _git(project, "rev-parse", "HEAD")
    state = ProjectStateManager(project).load_state()
    assert state is not None
    plan = _module_update_seal._UpdateSealPlan(
        module=_MODULES[0],
        version=CORE_VERSION,
        tag=f"splits/{_MODULES[0]}-module/{CORE_VERSION}",
        tag_sha=target,
        branch=f"splits/{_MODULES[0]}-module",
        branch_sha=target,
    )

    error = _REAL_MISSING_REQUIRED(project, state, {_MODULES[0]: plan})

    assert error is not None
    assert "not valid YAML" in error
    assert journal._update_journal_path(project).exists() is False


def test_guard_refusal_for_option_drift_never_creates_a_journal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Desired/applied option drift refuses before the journal on every retry."""
    project = _write_project(tmp_path)
    (project / "quickscale.yml").write_text(
        "\n".join(
            [
                'version: "1"',
                "project:",
                "  slug: myapp",
                "  package: myapp",
                "  theme: showcase_react",
                "modules:",
                f"  {_MODULES[0]}:",
                "    retention_days: 7",
                f"  {_MODULES[1]}: {{}}",
                "docker:",
                "  start: false",
                "",
            ]
        )
    )
    _git(project, "add", "quickscale.yml")
    _git(project, "commit", "-qm", "desired option drift")

    with patch("quickscale_core.utils.git_subtree.run_git_subtree_pull") as mock_pull:
        first = _invoke_update(project, monkeypatch, "--acknowledge-contract-vintage")
        second = _invoke_update(project, monkeypatch, "--acknowledge-contract-vintage")

    assert first.exit_code != 0
    assert second.exit_code != 0
    assert "Local desired state differs from applied module options" in first.output
    assert journal._update_journal_path(project).exists() is False
    mock_pull.assert_not_called()


def test_apply_refuses_while_an_update_journal_is_pending(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = _write_project(tmp_path)
    (project / ".quickscale" / "update-journal.yml").write_text(
        yaml.safe_dump(
            {
                "version": "1",
                "pre_update_head": "b" * 40,
                "modules": [
                    {
                        "name": "auth",
                        "version": CORE_VERSION,
                        "branch": "splits/auth-module",
                        "commit_sha": "a" * 40,
                    }
                ],
            }
        )
    )

    with pytest.raises(click.Abort):
        _context._enforce_apply_contract_vintage_preflight(
            project / "quickscale.yml",
            project,
            acknowledged=False,
        )

    assert "interrupted module update" in capsys.readouterr().err.lower()


def test_deploy_refuses_while_an_update_journal_is_pending(tmp_path: Path) -> None:
    project = _write_project(tmp_path)
    (project / ".quickscale" / "update-journal.yml").write_text("{}")

    from quickscale_cli.commands.deployment_commands import railway

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.chdir(project)
        result = CliRunner().invoke(railway, [])

    assert result.exit_code != 0
    assert "interrupted module update" in result.output.lower()


def test_update_environment_defers_to_the_pending_journal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = _write_project(tmp_path)
    monkeypatch.chdir(project)
    (project / ".quickscale" / "update-journal.yml").write_text("{}")

    # The journal owns its dirty paths; the resume path validates them under
    # the lock instead of the ordinary clean-tree gate.
    (project / "other-untracked.txt").write_text("dirty\n")
    _validate_update_environment()

    (project / ".quickscale" / "update-journal.yml").unlink()
    with pytest.raises(Exception):
        _validate_update_environment()


def test_journal_round_trip_and_closed_schema(tmp_path: Path) -> None:
    targets = (
        _ModuleUpdateTarget("auth", CORE_VERSION, "splits/auth-module", "a" * 40),
        _ModuleUpdateTarget("blog", CORE_VERSION, "splits/blog-module", "b" * 40),
    )
    journal._write_update_journal(tmp_path, pre_update_head="b" * 40, targets=targets)

    recorded = journal._load_update_journal(tmp_path)
    assert recorded is not None
    assert recorded.pre_update_head == "b" * 40
    assert recorded.targets == targets

    payload = yaml.safe_load(journal._update_journal_path(tmp_path).read_text())
    payload["unknown"] = "value"
    journal._update_journal_path(tmp_path).write_text(yaml.safe_dump(payload))
    with pytest.raises(_UpdateJournalError, match="unknown keys"):
        journal._load_update_journal(tmp_path)

    with pytest.raises(_UpdateJournalError, match="without a module target"):
        journal._write_update_journal(tmp_path, pre_update_head="b" * 40, targets=())

    journal._clear_update_journal(tmp_path)
    assert journal._load_update_journal(tmp_path) is None
