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
import quickscale_cli.commands._module_update_guard as _module_update_guard
import quickscale_cli.commands._module_update_io as _module_update_io
import quickscale_cli.commands._module_update_journal as _module_update_journal
import quickscale_cli.commands._module_update as _module_update
import quickscale_core.project_state_manager as _project_state_manager

import shutil
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml
from click.testing import CliRunner

from quickscale_core import __version__ as CORE_VERSION
from quickscale_core.contracts.module_options import STRIPE_API_VERSION
from quickscale_core.project_state import (
    ProjectStateManager,
    hash_managed_file,
)
from quickscale_core.schema.state_schema import StateError, StateManager
from quickscale_core.utils.git_utils import GitError
from quickscale_cli.commands._module_update_io import (
    _commit_module_update_set,
    _regenerate_and_record_managed_wiring,
)
from quickscale_cli.commands._module_update import update

_REAL_MISSING_REQUIRED = _module_update._missing_required_module_error

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_MANIFEST_ROOT = REPO_ROOT / "quickscale_modules"


@pytest.fixture(autouse=True)
def _stub_module_content_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep these update-mechanics tests independent of SA305 provenance.

    Their fixtures embed modules without a real subtree history, so the
    hand-edit guard would refuse every update; the guard has dedicated
    command-boundary coverage in test_update_local_changes.py.
    """
    monkeypatch.setattr(
        _module_update_guard,
        "_collect_module_content_drift",
        lambda state, project_path: [],
    )


#: The emitted generated-project ``.gitignore`` template, verbatim (it holds
#: no Jinja constructs), so the update fixture carries the real ignore rules.
_GITIGNORE_TEMPLATE = (
    REPO_ROOT
    / "quickscale_core"
    / "src"
    / "quickscale_core"
    / "generator"
    / "templates"
    / ".gitignore.j2"
)

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


#: The fixture's installed set: billing and forms plus their transitive
#: required-module closure (rule 39), in deterministic state order.
_FIXTURE_MODULES = (
    "analytics",
    "auth",
    "billing",
    "forms",
    "notifications",
    "orgs",
)


def _write_project(
    tmp_path: Path, module_names: tuple[str, ...] = _FIXTURE_MODULES
) -> Path:
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
                *(f"  {name}: {{}}" for name in module_names),
                "docker:",
                "  start: false",
            ]
        )
        + "\n"
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.poetry.dependencies]\npython = "^3.14"\n'
    )
    # The generated project's actual ignore rules (the emitted .gitignore is
    # this template verbatim) exclude local secret files.  The managed CI
    # environment file must not match them, or the update flow's explicit
    # staging of the managed paths is refused (SA286).
    (tmp_path / ".gitignore").write_text(_GITIGNORE_TEMPLATE.read_text())
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
                    name: {
                        "name": name,
                        "version": "0.88.0",
                        "prefix": f"modules/{name}",
                        "branch": f"splits/{name}-module",
                        "options": {},
                    }
                    for name in module_names
                },
                "managed_files": {},
            }
        )
    )
    (quickscale_dir / "config.yml").write_text(
        "modules:\n"
        + "\n".join(
            f"  {name}:\n    installed_version: 0.88.0" for name in module_names
        )
        + "\n"
    )
    for module_name in module_names:
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


def _update_mocks(project_path: Path, module_names: tuple[str, ...] = _FIXTURE_MODULES):
    """Patch the update flow's git, version, and dependency seams."""

    def _fake_subtree_pull(prefix: str, remote: str, branch: str, squash: bool) -> str:
        del remote, branch, squash
        module_name = prefix.rsplit("/", 1)[-1]
        (project_path / prefix / "module.yml").write_text(
            (MODULE_MANIFEST_ROOT / module_name / "module.yml").read_text()
        )
        # A real pull can add files; the rollback must remove them.
        (project_path / prefix / "new_pull_file.py").write_text("# added by the pull\n")
        # ``git subtree pull`` commits its content before the next pull runs;
        # mimic that transport commit so the project is clean between modules.
        for command in (
            ["git", "add", "-A", "--", prefix],
            ["git", "commit", "-qm", f"subtree pull {module_name}"],
        ):
            subprocess.run(
                command,
                cwd=project_path,
                check=True,
                capture_output=True,
            )
        return "updated"

    def _module_info(module_name: str) -> Mock:
        return Mock(
            prefix=f"modules/{module_name}",
            branch=f"splits/{module_name}-module",
            installed_version="0.88.0",
        )

    config = Mock(
        modules={name: _module_info(name) for name in module_names},
        default_remote="https://github.com/Experto-AI/quickscale.git",
    )
    return (
        patch(
            "quickscale_core.config.load_config",
            return_value=config,
        ),
        patch(
            "quickscale_core.utils.git_repo.resolve_remote_ref",
            return_value="a" * 40,
        ),
        patch(
            "quickscale_core.utils.git_subtree.run_git_subtree_pull",
            side_effect=_fake_subtree_pull,
        ),
        patch(
            "click.confirm",
            return_value=True,
        ),
        patch(
            "quickscale_cli.commands._module_embed._sync_module_dependencies",
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
    assert commit_messages[0] == "chore(modules): update installed modules"
    assert "chore: regenerate managed module wiring" not in commit_messages
    final_count = int(
        subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=project,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    assert final_count == baseline_count + len(_FIXTURE_MODULES) + 1

    committed_paths = subprocess.run(
        ["git", "show", "--name-only", "--format=", "HEAD"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    assert "myapp/settings/modules.py" in committed_paths
    assert "myapp/urls_modules.py" in committed_paths
    assert "frontend/src/quickscaleSeam.d.ts" in committed_paths
    assert "frontend/src/quickscaleSeam.keys.ts" in committed_paths
    assert "frontend/src/quickscaleSeam.hooks.ts" in committed_paths
    assert ".github/quickscale-ci-env" in committed_paths
    assert "quickscale-operations.md" in committed_paths

    # The managed CI environment file renders from the freshly pulled
    # embedded manifests' ci_env declarations (SA286).
    ci_environment = (project / ".github" / "quickscale-ci-env").read_text()
    assert "POSTHOG_API_KEY=ph_test_ci" in ci_environment
    assert "STRIPE_SECRET_KEY=sk_test_ci" in ci_environment
    assert "QUICKSCALE_BILLING_WEBHOOK_SECRET=whsec_test_ci" in ci_environment
    assert "RESEND_API_KEY=re_test_ci" in ci_environment

    # The managed operations page renders from the freshly pulled embedded
    # manifests' operations declarations (SA286), with the core contract
    # token resolved.
    operations_page = (project / "quickscale-operations.md").read_text()
    assert "## Stripe Billing" in operations_page
    assert "invoice.paid" in operations_page
    assert STRIPE_API_VERSION in operations_page

    state = StateManager(project).load()
    assert state is not None
    for path_str in (
        "myapp/settings/modules.py",
        "myapp/urls_modules.py",
        "frontend/src/quickscaleSeam.d.ts",
        "frontend/src/quickscaleSeam.keys.ts",
        "frontend/src/quickscaleSeam.hooks.ts",
        ".github/quickscale-ci-env",
        "quickscale-operations.md",
    ):
        assert path_str in state.managed_files
        assert state.managed_files[path_str].hash == hash_managed_file(
            project / path_str
        )
    assert ProjectStateManager(project).detect_managed_file_drift() == []


def test_record_managed_hashes_keeps_pre_consolidation_tracking(
    tmp_path: Path,
) -> None:
    """Recording wiring hashes imports legacy tracking before it saves state.

    A pre-consolidation state.yml carries no branch/prefix/installed_at; those
    live in the legacy config.yml, and the save that materializes the
    managed_files section must not make them unreadable first.
    """
    project = _write_project(tmp_path)
    state_path = project / ".quickscale" / "state.yml"
    raw_state = yaml.safe_load(state_path.read_text())
    raw_state.pop("managed_files", None)
    for module_entry in raw_state["modules"].values():
        for tracking_key in ("prefix", "branch", "installed_at"):
            module_entry.pop(tracking_key, None)
    state_path.write_text(yaml.dump(raw_state, sort_keys=False))
    # A parseable pre-consolidation legacy config carries the tracking data.
    (project / ".quickscale" / "config.yml").write_text(
        yaml.safe_dump(
            {
                "default_remote": "https://github.com/Experto-AI/quickscale.git",
                "modules": {
                    name: {
                        "prefix": f"modules/{name}",
                        "branch": f"splits/{name}-module",
                        "installed_version": "0.88.0",
                        "installed_at": "2024-01-01",
                    }
                    for name in _FIXTURE_MODULES
                },
            },
            sort_keys=False,
        )
    )

    manager = ProjectStateManager(project)
    state = manager.load_state()
    assert state is not None
    _module_update_io._record_managed_wiring_hashes(state, project, "myapp")
    manager.save_state(state)

    refreshed = ProjectStateManager(project).load_state()
    assert refreshed is not None
    assert refreshed.modules["billing"].branch == "splits/billing-module"
    assert refreshed.modules["billing"].prefix == "modules/billing"


def test_update_refuses_a_set_missing_a_requirement_before_journaling(
    tmp_path: Path, monkeypatch
) -> None:
    """A required-module gap refuses before the transaction starts.

    The documented repair is ``quickscale apply``; starting a journaled
    transaction would make apply refuse, so the gap is checked before the
    journal and the project is unchanged.
    """
    installed = ("auth", "listings", "notifications", "orgs")
    project = _write_project(tmp_path, installed)
    monkeypatch.chdir(project)
    monkeypatch.setattr(
        _module_update, "_missing_required_module_error", _REAL_MISSING_REQUIRED
    )

    load_config_patch, resolve_patch, pull_patch, confirm_patch, deps_patch = (
        _update_mocks(project, installed)
    )
    with load_config_patch, resolve_patch, pull_patch, confirm_patch, deps_patch:
        result = CliRunner().invoke(
            update,
            ["--no-preview", "--acknowledge-contract-vintage"],
            catch_exceptions=False,
        )

    assert result.exit_code != 0
    assert "'listings' requires 'storage'" in result.output
    assert "quickscale apply" in result.output
    assert _module_update_journal._update_journal_path(project).exists() is False
    state = yaml.safe_load((project / ".quickscale" / "state.yml").read_text())
    assert "storage" not in state.get("modules", {})
    assert "listings" in state.get("modules", {})


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

    manager = ProjectStateManager(project)
    state = manager.load_state()
    assert state is not None
    with patch(
        "quickscale_cli.utils.module_wiring_manager.regenerate_managed_wiring",
        side_effect=_failing_regeneration,
    ):
        success, message = _regenerate_and_record_managed_wiring(
            project, "myapp", state
        )

    assert success is False
    assert message == "wiring conflict"
    assert wiring_path.read_text() == STALE_MODULES_PY


def test_partial_failure_keeps_the_recorded_set_for_resume(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A later module failure keeps the completed pull and the journal."""
    project = _write_project(tmp_path)
    monkeypatch.chdir(project)
    # The fixture order decides which module the mock pulls first; the
    # restoration assertions must target that module, not a later one.
    first_module = _FIXTURE_MODULES[0]

    load_config_patch, resolve_patch, _pull_patch, confirm_patch, deps_patch = (
        _update_mocks(project)
    )
    pulled: list[str] = []

    def _fail_second_pull(prefix: str, remote: str, branch: str, squash: bool) -> str:
        del remote, branch, squash
        if pulled:
            raise GitError("network unavailable")
        pulled.append(prefix)
        module_name = prefix.rsplit("/", 1)[-1]
        (project / prefix / "module.yml").write_text(
            (MODULE_MANIFEST_ROOT / module_name / "module.yml").read_text()
        )
        (project / prefix / "new_pull_file.py").write_text("# added by the pull\n")
        for command in (
            ["git", "add", "-A", "--", prefix],
            ["git", "commit", "-qm", f"subtree pull {module_name}"],
        ):
            subprocess.run(command, cwd=project, check=True, capture_output=True)
        return "updated"

    with (
        load_config_patch,
        resolve_patch,
        patch(
            "quickscale_core.utils.git_subtree.run_git_subtree_pull",
            side_effect=_fail_second_pull,
        ),
        confirm_patch,
        deps_patch,
    ):
        result = CliRunner().invoke(
            update,
            ["--no-preview", "--acknowledge-contract-vintage"],
            catch_exceptions=False,
        )

    assert result.exit_code != 0
    assert "recorded module set is kept" in result.output

    # The completed module stays at its pulled content; the failing module's
    # own snapshot restore leaves it at the baseline.
    assert (project / "modules" / first_module / "module.yml").read_text() == (
        (MODULE_MANIFEST_ROOT / first_module / "module.yml").read_text()
    )
    assert (project / "modules" / first_module / "new_pull_file.py").exists()
    assert (project / "myapp" / "settings" / "modules.py").read_text() == (
        STALE_MODULES_PY
    )
    assert _module_update_journal._update_journal_path(project).exists()
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert status == "?? .quickscale/update-journal.yml"
    messages = subprocess.run(
        ["git", "log", "--pretty=%s", "-n", "3"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "chore: roll back partial module update" not in messages


def test_journal_is_written_under_the_update_lock(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """The transaction journal is written while the advisory lock is held."""
    project = _write_project(tmp_path)
    monkeypatch.chdir(project)
    observed: dict[str, bool] = {}

    load_config_patch, resolve_patch, _pull_patch, confirm_patch, deps_patch = (
        _update_mocks(project)
    )
    pulled: list[str] = []

    def _fail_second_pull(prefix: str, remote: str, branch: str, squash: bool) -> str:
        del remote, branch, squash
        if pulled:
            raise GitError("network unavailable")
        observed["lock_held"] = (project / ".quickscale" / "state.lock").exists()
        pulled.append(prefix)
        module_name = prefix.rsplit("/", 1)[-1]
        (project / prefix / "module.yml").write_text(
            (MODULE_MANIFEST_ROOT / module_name / "module.yml").read_text()
        )
        for command in (
            ["git", "add", "-A", "--", prefix],
            ["git", "commit", "-qm", f"subtree pull {module_name}"],
        ):
            subprocess.run(command, cwd=project, check=True, capture_output=True)
        return "updated"

    with (
        load_config_patch,
        resolve_patch,
        patch(
            "quickscale_core.utils.git_subtree.run_git_subtree_pull",
            side_effect=_fail_second_pull,
        ),
        confirm_patch,
        deps_patch,
    ):
        result = CliRunner().invoke(
            update,
            ["--no-preview", "--acknowledge-contract-vintage"],
            catch_exceptions=False,
        )

    assert result.exit_code != 0
    assert observed["lock_held"] is True
    assert not (project / ".quickscale" / "state.lock").exists()
    assert _module_update_journal._update_journal_path(project).exists()


def test_regeneration_failure_keeps_the_set_for_resume(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A failed regeneration after successful pulls keeps the journal."""
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
            "quickscale_cli.utils.module_wiring_manager.regenerate_managed_wiring",
            return_value=(False, "wiring conflict"),
        ),
    ):
        result = CliRunner().invoke(
            update,
            ["--no-preview", "--acknowledge-contract-vintage"],
            catch_exceptions=False,
        )

    assert result.exit_code != 0
    assert "recorded module set is kept" in result.output
    for name in baseline_manifests:
        assert (project / "modules" / name / "new_pull_file.py").exists()
    assert (project / "myapp" / "settings" / "modules.py").read_text() == (
        STALE_MODULES_PY
    )
    assert _module_update_journal._update_journal_path(project).exists()


def test_post_pull_phase_failure_keeps_the_set_for_resume(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Any failure after the pulls keeps the journal for the next run."""
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
            "quickscale_cli.commands._module_update_io._regenerate_and_record_managed_wiring",
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
    assert "recorded module set is kept" in result.output
    for name in baseline_manifests:
        assert (project / "modules" / name / "new_pull_file.py").exists()
    assert _module_update_journal._update_journal_path(project).exists()


def test_failed_set_commit_keeps_the_set_for_resume(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A rejected set commit keeps the journal and the staged wiring."""
    project = _write_project(tmp_path)
    monkeypatch.chdir(project)
    baseline_manifests = {
        name: (project / "modules" / name / "module.yml").read_text()
        for name in ("billing", "forms")
    }

    def _stage_then_fail(
        module_names: list[str], project_package: str, *, transaction_id=None
    ) -> None:
        del module_names, transaction_id
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
            "quickscale_cli.commands._module_update_io._commit_module_update_set",
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
    # The transaction remains recorded; the next resume restores and redoes
    # the tracking and wiring writes.
    assert _module_update_journal._update_journal_path(project).exists()
    for name in baseline_manifests:
        assert (project / "modules" / name / "new_pull_file.py").exists()
    committed_wiring = subprocess.run(
        ["git", "show", "HEAD:myapp/settings/modules.py"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert committed_wiring == STALE_MODULES_PY


def test_post_pull_state_save_failure_keeps_the_journal(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A StateError from the set's single state save keeps the journal."""
    project = _write_project(tmp_path)
    monkeypatch.chdir(project)

    load_config_patch, resolve_patch, pull_patch, confirm_patch, deps_patch = (
        _update_mocks(project)
    )
    with (
        load_config_patch,
        resolve_patch,
        pull_patch,
        confirm_patch,
        deps_patch,
        patch.object(
            _project_state_manager.ProjectStateManager,
            "save_state",
            side_effect=StateError("corrupt state"),
        ),
    ):
        result = CliRunner().invoke(
            update,
            ["--no-preview", "--acknowledge-contract-vintage"],
            catch_exceptions=False,
        )

    assert result.exit_code != 0
    assert "corrupt state" in result.output
    assert _module_update_journal._update_journal_path(project).exists()


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

    manager = ProjectStateManager(project)
    state = manager.load_state()
    assert state is not None
    with (
        patch(
            "quickscale_cli.utils.module_wiring_manager.regenerate_managed_wiring",
            side_effect=_partial_regeneration,
        ),
        patch(
            "quickscale_cli.commands._module_update_io._record_managed_wiring_hashes",
            side_effect=RuntimeError("state save failed"),
        ),
    ):
        success, message = _regenerate_and_record_managed_wiring(
            project, "myapp", state
        )

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

    _commit_module_update_set([], "myapp")

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


def test_commit_module_update_set_stages_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """The set commit carries the regenerated files and the hash state."""
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

    _commit_module_update_set([], "myapp")

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
