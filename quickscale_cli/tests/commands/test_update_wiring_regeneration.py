"""Regression coverage for managed-wiring regeneration during module updates.

``quickscale update`` is documented to regenerate the QuickScale-managed wiring
files (``<package>/settings/modules.py`` and ``<package>/urls_modules.py``).
Module-contributed settings — such as the stemmed DRF throttle scopes and their
rates — only take effect once that regeneration runs against the freshly pulled
manifests, so an update that skips it leaves module code and managed settings
out of step.  Regeneration validates every embedded manifest against the
running core version, so it runs once, after all module pulls succeed; a mixed
old/new module set would otherwise fail mid-update.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import yaml
from click.testing import CliRunner

from quickscale_core import __version__ as CORE_VERSION
from quickscale_core.project_state import (
    ProjectStateManager,
    hash_managed_file,
)
from quickscale_core.schema.state_schema import StateError, StateManager
from quickscale_core.utils.git_utils import GitError
from quickscale_cli.commands.module_commands import (
    _commit_regenerated_managed_wiring,
    _regenerate_and_record_managed_wiring,
    update,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_MANIFEST_ROOT = REPO_ROOT / "quickscale_modules"

STALE_MODULES_PY = (
    '"""QuickScale managed module settings."""\n'
    "\n"
    "MODULE_SETTINGS: dict[str, object] = {\n"
    '    "QUICKSCALE_BILLING_ENABLED": True,\n'
    '    "REST_FRAMEWORK": {\n'
    '        "DEFAULT_THROTTLE_RATES": {\n'
    '            "billing_checkout": "30/hour",\n'
    '            "form_submit": "5/hour",\n'
    "        },\n"
    "    },\n"
    "}\n"
)


def _write_project(tmp_path: Path) -> Path:
    """Create a minimal generated-project layout whose wiring is pre-rename."""
    (tmp_path / "myapp" / "settings").mkdir(parents=True)
    (tmp_path / "myapp" / "__init__.py").write_text("")
    (tmp_path / "myapp" / "settings" / "__init__.py").write_text("")
    (tmp_path / "myapp" / "settings" / "modules.py").write_text(STALE_MODULES_PY)
    (tmp_path / "quickscale.yml").write_text(
        "\n".join(
            [
                'version: "1"',
                "project:",
                "  slug: myapp",
                "  package: myapp",
                "  theme: showcase_react",
                "modules:",
                "  billing: {}",
                "  forms: {}",
                "docker:",
                "  start: false",
            ]
        )
        + "\n"
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.poetry.dependencies]\npython = "^3.14"\n'
    )
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
                    "project_contract": CORE_VERSION,
                },
                "modules": {
                    "billing": {
                        "name": "billing",
                        "version": "0.88.0",
                        "prefix": "modules/billing",
                        "branch": "splits/billing-module",
                        "options": {},
                    },
                    "forms": {
                        "name": "forms",
                        "version": "0.88.0",
                        "prefix": "modules/forms",
                        "branch": "splits/forms-module",
                        "options": {},
                    },
                },
                "managed_files": {},
            }
        )
    )
    (quickscale_dir / "config.yml").write_text(
        "modules:\n  billing:\n    installed_version: 0.88.0\n"
        "  forms:\n    installed_version: 0.88.0\n"
    )
    for module_name in ("billing", "forms"):
        module_dir = tmp_path / "modules" / module_name
        module_dir.mkdir(parents=True)
        manifest_text = (MODULE_MANIFEST_ROOT / module_name / "module.yml").read_text()
        (module_dir / "module.yml").write_text(
            manifest_text.replace(f'version: "{CORE_VERSION}"', 'version: "0.88.0"')
        )

    for command in (
        ["git", "init", "-q"],
        ["git", "config", "user.name", "Test User"],
        ["git", "config", "user.email", "test@example.invalid"],
        ["git", "add", "-A"],
        ["git", "commit", "-qm", "baseline"],
    ):
        subprocess.run(command, cwd=tmp_path, check=True, capture_output=True)

    return tmp_path


def _update_mocks(project_path: Path):
    """Patch the update flow's git, version, and dependency seams."""

    def _fake_subtree_pull(prefix: str, remote: str, branch: str, squash: bool) -> str:
        del remote, branch, squash
        module_name = prefix.rsplit("/", 1)[-1]
        (project_path / prefix / "module.yml").write_text(
            (MODULE_MANIFEST_ROOT / module_name / "module.yml").read_text()
        )
        # A real pull can add files; the rollback must remove them.
        (project_path / prefix / "new_pull_file.py").write_text("# added by the pull\n")
        return "updated"

    def _module_info(module_name: str) -> Mock:
        return Mock(
            prefix=f"modules/{module_name}",
            branch=f"splits/{module_name}-module",
            installed_version="0.88.0",
        )

    config = Mock(
        modules={
            "billing": _module_info("billing"),
            "forms": _module_info("forms"),
        },
        default_remote="https://github.com/Experto-AI/quickscale.git",
    )
    return (
        patch(
            "quickscale_cli.commands.module_commands.load_config",
            return_value=config,
        ),
        patch(
            "quickscale_cli.commands.module_commands.resolve_remote_ref",
            return_value="a" * 40,
        ),
        patch(
            "quickscale_cli.commands.module_commands.run_git_subtree_pull",
            side_effect=_fake_subtree_pull,
        ),
        patch(
            "quickscale_cli.commands.module_commands.click.confirm",
            return_value=True,
        ),
        patch(
            "quickscale_cli.commands.module_commands._sync_module_dependencies",
            return_value=True,
        ),
    )


def test_update_regenerates_wiring_once_every_module_is_pulled(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A mixed-version two-module update regenerates and commits wiring once.

    Both embedded manifests start at an older version; if regeneration ran
    between the pulls, the still-old second module would fail the core
    version check and the update would abort.
    """
    project = _write_project(tmp_path)
    monkeypatch.chdir(project)
    baseline_count = int(
        subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=project,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )

    load_config_patch, resolve_patch, pull_patch, confirm_patch, deps_patch = (
        _update_mocks(project)
    )
    with load_config_patch, resolve_patch, pull_patch, confirm_patch, deps_patch:
        result = CliRunner().invoke(
            update,
            ["--no-preview", "--acknowledge-contract-vintage"],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.output

    wiring = (project / "myapp" / "settings" / "modules.py").read_text()
    assert "quickscale_billing_checkout" in wiring
    assert "quickscale_forms_submit" in wiring
    assert '"billing_checkout"' not in wiring
    assert '"form_submit"' not in wiring

    commit_messages = subprocess.run(
        ["git", "log", "--pretty=%s", "-n", "4"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert "chore: regenerate managed module wiring" in commit_messages
    final_count = int(
        subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=project,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    assert final_count == baseline_count + 3

    committed_paths = subprocess.run(
        ["git", "show", "--name-only", "--format=", "HEAD"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    assert "myapp/settings/modules.py" in committed_paths
    assert "myapp/urls_modules.py" in committed_paths

    state = StateManager(project).load()
    assert state is not None
    for relative in ("settings/modules.py", "urls_modules.py"):
        path_str = f"myapp/{relative}"
        assert path_str in state.managed_files
        assert state.managed_files[path_str].hash == hash_managed_file(
            project / path_str
        )
    assert ProjectStateManager(project).detect_managed_file_drift() == []


def test_regeneration_failure_restores_pre_update_wiring(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A failed regeneration restores the pre-update wiring from its snapshot."""
    project = _write_project(tmp_path)
    wiring_path = project / "myapp" / "settings" / "modules.py"

    def _failing_regeneration(
        project_path: Path,
        *,
        project_package: str | None = None,
    ) -> tuple[bool, str]:
        del project_package
        # Simulate a partial write before the failure so the snapshot restore
        # is exercised, not just the early-return path.
        (project_path / "myapp" / "settings" / "modules.py").write_text(
            "# partial regeneration\n"
        )
        return False, "wiring conflict"

    with patch(
        "quickscale_cli.commands.module_commands.regenerate_managed_wiring",
        side_effect=_failing_regeneration,
    ):
        success, message = _regenerate_and_record_managed_wiring(project, "myapp")

    assert success is False
    assert message == "wiring conflict"
    assert wiring_path.read_text() == STALE_MODULES_PY


def test_partial_failure_rolls_back_modules_committed_before_it(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A later module failure restores the modules committed before it.

    Otherwise the successfully updated module's new code would stay paired
    with the pre-update managed wiring, and its renamed throttle scope would
    raise at request time.
    """
    project = _write_project(tmp_path)
    monkeypatch.chdir(project)
    baseline_manifest = (project / "modules" / "billing" / "module.yml").read_text()

    load_config_patch, _resolve_patch, pull_patch, confirm_patch, deps_patch = (
        _update_mocks(project)
    )
    resolve_patch = patch(
        "quickscale_cli.commands.module_commands.resolve_remote_ref",
        side_effect=["a" * 40, GitError("network unavailable")],
    )
    with load_config_patch, resolve_patch, pull_patch, confirm_patch, deps_patch:
        result = CliRunner().invoke(
            update,
            ["--no-preview", "--acknowledge-contract-vintage"],
            catch_exceptions=False,
        )

    assert result.exit_code != 0
    assert "rolled back" in result.output

    # The module updated before the failure is restored to its pre-update code,
    # including removal of the files its pull added.
    assert (
        project / "modules" / "billing" / "module.yml"
    ).read_text() == baseline_manifest
    assert not (project / "modules" / "billing" / "new_pull_file.py").exists()
    # The wiring was never regenerated, so it stays consistent with that code.
    assert (project / "myapp" / "settings" / "modules.py").read_text() == (
        STALE_MODULES_PY
    )
    # The rollback commit leaves a clean tree for the operator's next command.
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert status == ""
    messages = subprocess.run(
        ["git", "log", "--pretty=%s", "-n", "3"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "chore: roll back partial module update" in messages


def test_partial_failure_rollback_runs_under_the_update_lock(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """The partial-failure rollback runs while the advisory lock is held."""
    project = _write_project(tmp_path)
    monkeypatch.chdir(project)
    observed: dict[str, bool] = {}

    from quickscale_cli.commands import module_commands

    real_rollback = module_commands._roll_back_partial_module_update

    def _probe(
        project_path: Path,
        pre_update_head: str,
        updated_modules: list[str],
        project_package: str | None = None,
    ) -> None:
        observed["lock_held"] = (project_path / ".quickscale" / "state.lock").exists()
        real_rollback(
            project_path,
            pre_update_head,
            updated_modules,
            project_package,
        )

    load_config_patch, _resolve_patch, pull_patch, confirm_patch, deps_patch = (
        _update_mocks(project)
    )
    resolve_patch = patch(
        "quickscale_cli.commands.module_commands.resolve_remote_ref",
        side_effect=["a" * 40, GitError("network unavailable")],
    )
    with (
        load_config_patch,
        resolve_patch,
        pull_patch,
        confirm_patch,
        deps_patch,
        patch.object(
            module_commands,
            "_roll_back_partial_module_update",
            side_effect=_probe,
        ),
    ):
        result = CliRunner().invoke(
            update,
            ["--no-preview", "--acknowledge-contract-vintage"],
            catch_exceptions=False,
        )

    assert result.exit_code != 0
    assert observed["lock_held"] is True
    assert not (project / ".quickscale" / "state.lock").exists()


def test_regeneration_failure_rolls_back_updated_modules(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A failed regeneration after successful pulls restores the modules.

    The command must not leave the updated modules' new scope code paired
    with the pre-update managed wiring.
    """
    project = _write_project(tmp_path)
    monkeypatch.chdir(project)
    baseline_manifests = {
        name: (project / "modules" / name / "module.yml").read_text()
        for name in ("billing", "forms")
    }

    load_config_patch, resolve_patch, pull_patch, confirm_patch, deps_patch = (
        _update_mocks(project)
    )
    with (
        load_config_patch,
        resolve_patch,
        pull_patch,
        confirm_patch,
        deps_patch,
        patch(
            "quickscale_cli.commands.module_commands.regenerate_managed_wiring",
            return_value=(False, "wiring conflict"),
        ),
    ):
        result = CliRunner().invoke(
            update,
            ["--no-preview", "--acknowledge-contract-vintage"],
            catch_exceptions=False,
        )

    assert result.exit_code != 0
    for name, baseline in baseline_manifests.items():
        assert (project / "modules" / name / "module.yml").read_text() == baseline
        assert not (project / "modules" / name / "new_pull_file.py").exists()
    assert (project / "myapp" / "settings" / "modules.py").read_text() == (
        STALE_MODULES_PY
    )
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert status == ""
    messages = subprocess.run(
        ["git", "log", "--pretty=%s", "-n", "3"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "chore: roll back partial module update" in messages


def test_post_pull_phase_failure_rolls_back_updated_modules(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Any failure after the pulls rolls back the modules they committed.

    The post-pull phase covers the state read, regeneration, hash recording,
    and the wiring commit; an error in any of them must not leave new module
    code paired with the pre-update managed wiring.
    """
    project = _write_project(tmp_path)
    monkeypatch.chdir(project)
    baseline_manifests = {
        name: (project / "modules" / name / "module.yml").read_text()
        for name in ("billing", "forms")
    }

    load_config_patch, resolve_patch, pull_patch, confirm_patch, deps_patch = (
        _update_mocks(project)
    )
    with (
        load_config_patch,
        resolve_patch,
        pull_patch,
        confirm_patch,
        deps_patch,
        patch(
            "quickscale_cli.commands.module_commands._regenerate_and_record_managed_wiring",
            side_effect=RuntimeError("state read failed"),
        ),
    ):
        result = CliRunner().invoke(
            update,
            ["--no-preview", "--acknowledge-contract-vintage"],
            catch_exceptions=False,
        )

    assert result.exit_code != 0
    assert "state read failed" in result.output
    for name, baseline in baseline_manifests.items():
        assert (project / "modules" / name / "module.yml").read_text() == baseline
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert status == ""
    messages = subprocess.run(
        ["git", "log", "--pretty=%s", "-n", "3"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "chore: roll back partial module update" in messages


def test_failed_wiring_commit_rolls_back_wiring_and_modules(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A rejected wiring commit must not leave new wiring with old module code.

    The wiring helper stages the regenerated files before committing; when
    the commit fails, the staged new wiring must be removed by the rollback
    rather than riding into the rollback commit.
    """
    project = _write_project(tmp_path)
    monkeypatch.chdir(project)
    baseline_manifests = {
        name: (project / "modules" / name / "module.yml").read_text()
        for name in ("billing", "forms")
    }

    def _stage_then_fail(project_package: str) -> None:
        subprocess.run(
            [
                "git",
                "add",
                "-A",
                "--",
                f"{project_package}/settings/modules.py",
                f"{project_package}/urls_modules.py",
            ],
            cwd=project,
            check=True,
            capture_output=True,
        )
        raise GitError("wiring commit rejected")

    load_config_patch, resolve_patch, pull_patch, confirm_patch, deps_patch = (
        _update_mocks(project)
    )
    with (
        load_config_patch,
        resolve_patch,
        pull_patch,
        confirm_patch,
        deps_patch,
        patch(
            "quickscale_cli.commands.module_commands._commit_regenerated_managed_wiring",
            side_effect=_stage_then_fail,
        ),
    ):
        result = CliRunner().invoke(
            update,
            ["--no-preview", "--acknowledge-contract-vintage"],
            catch_exceptions=False,
        )

    assert result.exit_code != 0
    assert "wiring commit rejected" in result.output
    # The pre-update wiring is restored and the regenerated files are gone.
    assert (project / "myapp" / "settings" / "modules.py").read_text() == (
        STALE_MODULES_PY
    )
    assert not (project / "myapp" / "urls_modules.py").exists()
    for name, baseline in baseline_manifests.items():
        assert (project / "modules" / name / "module.yml").read_text() == baseline

    committed_wiring = subprocess.run(
        ["git", "show", "HEAD:myapp/settings/modules.py"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert committed_wiring == STALE_MODULES_PY
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert status == ""
    messages = subprocess.run(
        ["git", "log", "--pretty=%s", "-n", "3"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "chore: roll back partial module update" in messages


def test_post_pull_state_load_failure_triggers_rollback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A StateError from the post-pull state read triggers the rollback."""
    project = _write_project(tmp_path)
    monkeypatch.chdir(project)

    from quickscale_cli.commands import module_commands

    real_load = module_commands.ProjectStateManager.load_state
    calls = {"count": 0}

    def _flaky_load(self):
        calls["count"] += 1
        if calls["count"] == 1:
            return real_load(self)
        raise StateError("corrupt state")

    config = Mock(
        modules={"billing": Mock(), "forms": Mock()},
        default_remote="https://github.com/Experto-AI/quickscale.git",
    )
    with (
        patch(
            "quickscale_cli.commands.module_commands.load_config",
            return_value=config,
        ),
        patch(
            "quickscale_cli.commands.module_commands.click.confirm",
            return_value=True,
        ),
        patch(
            "quickscale_cli.commands.module_commands._update_single_module",
            return_value=True,
        ),
        patch(
            "quickscale_cli.commands.module_commands._warn_version_drift_for_update",
            Mock(),
        ),
        patch.object(module_commands.ProjectStateManager, "load_state", _flaky_load),
        patch.object(
            module_commands,
            "_roll_back_partial_module_update",
        ) as mock_rollback,
    ):
        result = CliRunner().invoke(
            update,
            ["--no-preview", "--acknowledge-contract-vintage"],
            catch_exceptions=False,
        )

    assert result.exit_code != 0
    assert "corrupt state" in result.output
    mock_rollback.assert_called_once()
    assert mock_rollback.call_args.args[2] == ["billing", "forms"]


def test_hash_persistence_failure_restores_wiring(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A failure while recording wiring hashes restores the wiring snapshot."""
    project = _write_project(tmp_path)
    wiring_path = project / "myapp" / "settings" / "modules.py"

    def _partial_regeneration(
        project_path: Path,
        *,
        project_package: str | None = None,
    ) -> tuple[bool, str]:
        del project_package
        (project_path / "myapp" / "settings" / "modules.py").write_text(
            "# regenerated\n"
        )
        return True, "regenerated"

    with (
        patch(
            "quickscale_cli.commands.module_commands.regenerate_managed_wiring",
            side_effect=_partial_regeneration,
        ),
        patch(
            "quickscale_cli.commands.module_commands._record_managed_wiring_hashes",
            side_effect=RuntimeError("state save failed"),
        ),
    ):
        success, message = _regenerate_and_record_managed_wiring(project, "myapp")

    assert success is False
    assert message == "state save failed"
    assert wiring_path.read_text() == STALE_MODULES_PY


def test_wiring_commit_stages_removed_managed_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A regeneration that removes the managed directory commits the deletion."""
    (tmp_path / "myapp" / "settings").mkdir(parents=True)
    (tmp_path / "myapp" / "settings" / "modules.py").write_text("# managed\n")
    (tmp_path / "myapp" / "urls_modules.py").write_text("# managed urls\n")
    managed_dir = tmp_path / "myapp" / "quickscale_managed"
    managed_dir.mkdir()
    (managed_dir / "social_urls.py").write_text("# managed transport\n")
    quickscale_dir = tmp_path / ".quickscale"
    quickscale_dir.mkdir()
    (quickscale_dir / "state.yml").write_text("modules: {}\n")
    for command in (
        ["git", "init", "-q"],
        ["git", "config", "user.name", "Test User"],
        ["git", "config", "user.email", "test@example.invalid"],
        ["git", "add", "-A"],
        ["git", "commit", "-qm", "baseline"],
    ):
        subprocess.run(command, cwd=tmp_path, check=True, capture_output=True)
    monkeypatch.chdir(tmp_path)

    shutil.rmtree(managed_dir)

    _commit_regenerated_managed_wiring("myapp")

    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert status == ""
    committed = subprocess.run(
        ["git", "show", "--name-status", "--format=", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "D\tmyapp/quickscale_managed/social_urls.py" in committed


def test_commit_regenerated_managed_wiring_stages_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """The wiring commit carries the regenerated files and the hash state."""
    (tmp_path / "myapp" / "settings").mkdir(parents=True)
    (tmp_path / "myapp" / "settings" / "modules.py").write_text("# managed\n")
    (tmp_path / "myapp" / "urls_modules.py").write_text("# managed urls\n")
    quickscale_dir = tmp_path / ".quickscale"
    quickscale_dir.mkdir()
    (quickscale_dir / "state.yml").write_text("modules: {}\n")
    for command in (
        ["git", "init", "-q"],
        ["git", "config", "user.name", "Test User"],
        ["git", "config", "user.email", "test@example.invalid"],
        ["git", "add", "-A"],
        ["git", "commit", "-qm", "baseline"],
    ):
        subprocess.run(command, cwd=tmp_path, check=True, capture_output=True)
    monkeypatch.chdir(tmp_path)

    (tmp_path / "myapp" / "settings" / "modules.py").write_text("# regenerated\n")
    (quickscale_dir / "state.yml").write_text("modules: {}\nmanaged_files: {}\n")

    _commit_regenerated_managed_wiring("myapp")

    committed = subprocess.run(
        ["git", "show", "--name-only", "--format=", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    assert "myapp/settings/modules.py" in committed
    assert ".quickscale/state.yml" in committed
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert status == ""
