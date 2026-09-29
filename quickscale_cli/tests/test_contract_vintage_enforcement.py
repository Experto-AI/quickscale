"""Regression coverage for enforced generated-file contract vintages."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import click
from click.testing import CliRunner
import pytest

from quickscale_cli.commands import (
    apply_command,
    deployment_commands,
    module_commands,
    status_command,
)
from quickscale_cli.commands.contract_vintage import (
    declared_adoption_step_ids,
    enforce_contract_vintage,
    record_contract_adoption,
)
from quickscale_core.manifest import ContractVintage, ModuleManifest
from quickscale_core.manifest.loader import (
    load_manifest_from_path,
    load_project_contract_vintage,
)
from quickscale_core.project_state import ProjectStateManager
from quickscale_core.schema.state_schema import (
    ModuleState,
    ProjectState,
    QuickScaleState,
    StateManager,
)


_DECLARED_STEP_IDS = tuple(step.id for step in load_project_contract_vintage().steps)
# The ids a confirmation records for the default fixture state: the project
# declaration steps plus each installed module's declared vintage id.
_RECORDED_STEP_IDS = tuple(declared_adoption_step_ids(("orgs",)))


def _state(
    project_contract: str | None,
    *,
    modules: tuple[str, ...] = ("orgs",),
    adopted_steps: tuple[str, ...] = (),
) -> QuickScaleState:
    return QuickScaleState(
        version="1",
        project=ProjectState(
            slug="example",
            package="example",
            theme="showcase_react",
            project_contract=project_contract,
            adopted_contract_steps=list(adopted_steps),
        ),
        modules={
            name: ModuleState(
                name=name,
                version="0.89.0",
                prefix=f"modules/{name}",
                branch=f"splits/{name}-module",
                installed_at="2026-09-16T00:00:00",
            )
            for name in modules
        },
    )


def _orgs_manifest() -> ModuleManifest:
    return ModuleManifest(
        name="orgs",
        version="0.89.0",
        contract_vintage=ContractVintage(
            minimum="0.89.0",
            manual_adoption_steps=[
                "Adopt settings/production.py",
                "Adopt start.sh",
                "Adopt Dockerfile",
            ],
        ),
    )


def test_orgs_no_longer_owns_the_runtime_role_contract() -> None:
    """SA207: the project-wide runtime-role contract lives in the declaration.

    SA211 gives orgs its own provider-ID classification step; that step must
    not reintroduce the relocated runtime-role prose.
    """
    manifest_path = Path(__file__).parents[2] / "quickscale_modules/orgs/module.yml"
    manifest = load_manifest_from_path(manifest_path)

    vintage = manifest.contract_vintage
    steps = " ".join(vintage.manual_adoption_steps) if vintage is not None else ""
    assert "RUNTIME_DB_ROLE" not in steps
    assert "quickscale_runtime" not in steps
    assert "start.sh" not in steps
    assert "db/init.sql" not in steps


def test_orgs_declares_the_provider_id_classification_step() -> None:
    """SA211: the SA208 conformance boundary is an identified adoption step."""
    manifest_path = Path(__file__).parents[2] / "quickscale_modules/orgs/module.yml"
    manifest = load_manifest_from_path(manifest_path)

    vintage = manifest.contract_vintage
    assert vintage is not None
    assert vintage.id == "sa221-orgs-check-id"
    assert vintage.minimum == "0.89.0"
    steps = " ".join(vintage.manual_adoption_steps)
    assert "provider_id_classification" in steps
    assert "provider-backed" in steps
    assert "not-provider-backed" in steps
    assert "quickscale_orgs.E001" in steps


@pytest.mark.parametrize("module_name", ["auth", "billing", "blog", "listings", "crm"])
def test_styled_modules_no_longer_copy_the_design_contract(module_name: str) -> None:
    """SA207: the shared-design prose lives once, at the project level."""
    manifest_path = (
        Path(__file__).parents[2] / f"quickscale_modules/{module_name}/module.yml"
    )
    manifest = load_manifest_from_path(manifest_path)

    if manifest.contract_vintage is None:
        return
    steps = " ".join(manifest.contract_vintage.manual_adoption_steps)
    assert "templates/base.html" not in steps
    assert "frontend/vite.config.ts" not in steps
    assert "QUICKSCALE_FRONTEND_HOST_PORT" not in steps


def test_project_declaration_declares_each_template_contract_step() -> None:
    declaration = load_project_contract_vintage()
    steps = {step.id: step for step in declaration.steps}

    assert {
        "sa192-shared-design",
        "sa200-proxy-trust",
        "sa201-throttling",
        "sa206-runtime-settings-facade",
        "runtime-role-contract",
    } <= set(steps)
    for step in steps.values():
        assert step.minimum == "0.89.0"
        assert step.title
        assert step.manual_adoption_steps

    runtime_role = " ".join(steps["runtime-role-contract"].manual_adoption_steps)
    assert "settings/production.py" in runtime_role
    assert "start.sh" in runtime_role
    assert "db/init.sql" in runtime_role
    assert ".env.example" in runtime_role
    assert "docker-compose.yml" in runtime_role
    assert "Dockerfile" in runtime_role
    assert "OPERATIONS.md" in runtime_role
    assert "existing local database" in runtime_role
    assert "password in the adopted local RUNTIME_DATABASE_URL" in runtime_role
    assert "reset the disposable Compose database volume" in runtime_role

    sa192 = " ".join(steps["sa192-shared-design"].manual_adoption_steps)
    assert "templates/base.html" in sa192
    assert "frontend/vite.config.ts" in sa192
    assert "QUICKSCALE_FRONTEND_HOST_PORT" in sa192
    assert "pnpm build" in sa192

    sa200 = " ".join(steps["sa200-proxy-trust"].manual_adoption_steps)
    assert "SECURE_PROXY_SSL_HEADER" in sa200
    assert "USE_X_FORWARDED_FOR" in sa200

    sa201 = " ".join(steps["sa201-throttling"].manual_adoption_steps)
    assert "ScopedRateThrottle" in sa201
    assert "quickscale_billing_checkout" in sa201
    assert "REST_FRAMEWORK" in sa201

    sa206 = " ".join(steps["sa206-runtime-settings-facade"].manual_adoption_steps)
    assert "quickscale_core.runtime.settings" in sa206


def test_railway_guide_lists_the_complete_089_adoption_path() -> None:
    guide_path = Path(__file__).parents[2] / "docs/deployment/railway.md"
    guide = guide_path.read_text()
    adoption = guide.split("For an existing generated project", 1)[1].split(
        "## Manual Deployment", 1
    )[0]
    normalized_adoption = " ".join(adoption.split())

    for generated_path in (
        "settings/production.py",
        "settings/base.py",
        "db/init.sql",
        ".env.example",
        "docker-compose.yml",
        "start.sh",
        "Dockerfile",
        "OPERATIONS.md",
    ):
        assert f"`{generated_path}`" in normalized_adoption
    assert "existing local database" in normalized_adoption
    assert "password in the adopted local `RUNTIME_DATABASE_URL`" in normalized_adoption
    assert "reset the disposable Compose database" in normalized_adoption


def _billing_manifest() -> ModuleManifest:
    return ModuleManifest(
        name="billing",
        version="0.89.0",
        contract_vintage=ContractVintage(
            id="sa209-stripe-webhook-version",
            minimum="0.89.0",
            manual_adoption_steps=["Recreate the Stripe webhook endpoint"],
        ),
    )


@pytest.mark.parametrize("project_contract", [None, "0.87.0"])
def test_shared_enforcement_refuses_old_projects(project_contract: str | None) -> None:
    with pytest.raises(click.Abort):
        enforce_contract_vintage(
            _state(project_contract),
            {"orgs": _orgs_manifest()},
            operation="'quickscale update'",
            acknowledged=False,
        )


def test_mid_cycle_generation_is_refused_despite_current_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A project sharing the package version has not adopted SA201's step."""
    with pytest.raises(click.Abort):
        enforce_contract_vintage(
            _state("0.89.0"),
            {"billing": _billing_manifest()},
            operation="'quickscale update'",
            acknowledged=False,
        )

    captured = capsys.readouterr()
    assert "generated project (sa201-throttling)" in captured.err
    assert "billing requires project_contract >= 0.89.0" in captured.err


def test_adopted_step_ids_satisfy_the_declaration() -> None:
    enforce_contract_vintage(
        _state(
            "0.89.0",
            adopted_steps=(*_DECLARED_STEP_IDS, "sa209-stripe-webhook-version"),
        ),
        {"billing": _billing_manifest()},
        operation="'quickscale update'",
        acknowledged=False,
    )


def _orgs_provider_id_manifest() -> ModuleManifest:
    return ModuleManifest(
        name="orgs",
        version="0.89.0",
        contract_vintage=ContractVintage(
            id="sa208-provider-id-classification",
            minimum="0.89.0",
            manual_adoption_steps=["Classify every *_id field"],
        ),
    )


def test_provider_id_step_refuses_an_unadopted_project(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """SA211: SA208's conformance boundary is enforced as an identified step."""
    with pytest.raises(click.Abort):
        enforce_contract_vintage(
            _state("0.89.0", adopted_steps=_DECLARED_STEP_IDS),
            {"orgs": _orgs_provider_id_manifest()},
            operation="'quickscale update'",
            acknowledged=False,
        )

    captured = capsys.readouterr()
    assert "orgs requires project_contract >= 0.89.0" in captured.err
    assert "Classify every *_id field" in captured.err


def test_provider_id_step_is_satisfied_when_the_id_is_recorded() -> None:
    enforce_contract_vintage(
        _state(
            "0.89.0",
            adopted_steps=(
                *_DECLARED_STEP_IDS,
                "sa208-provider-id-classification",
            ),
        ),
        {"orgs": _orgs_provider_id_manifest()},
        operation="'quickscale update'",
        acknowledged=False,
    )


def test_update_records_adoption_after_module_mutations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """SA207: the adoption write never dirties the tree before a subtree pull."""
    project = tmp_path / "example"
    project.mkdir()
    state = _state("0.87.0")
    StateManager(project).save(state)
    for command in (
        ["git", "init", "-q"],
        ["git", "config", "user.name", "Test User"],
        ["git", "config", "user.email", "test@example.invalid"],
        ["git", "add", "-A"],
        ["git", "commit", "-qm", "baseline"],
    ):
        subprocess.run(command, cwd=project, check=True, capture_output=True, text=True)

    observed: dict[str, str] = {}

    def _update(name: str, module_state: object, remote: str, no_preview: bool) -> bool:
        del module_state, remote, no_preview
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project,
            check=True,
            capture_output=True,
            text=True,
        )
        observed[name] = status.stdout.strip()
        return True

    manager = Mock()
    manager.load_state.return_value = state

    monkeypatch.chdir(project)
    monkeypatch.setattr(module_commands, "_validate_update_environment", Mock())
    monkeypatch.setattr(
        module_commands, "ProjectStateManager", Mock(return_value=manager)
    )
    monkeypatch.setattr(module_commands, "_warn_version_drift_for_update", Mock())
    monkeypatch.setattr(
        module_commands, "_validate_module_readiness", Mock(return_value=True)
    )
    monkeypatch.setattr(module_commands, "_update_single_module", _update)
    monkeypatch.setattr(
        module_commands,
        "_regenerate_and_record_managed_wiring",
        lambda *args, **kwargs: (True, "regenerated"),
    )
    monkeypatch.setattr(
        module_commands,
        "_commit_regenerated_managed_wiring",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(module_commands, "AdvisoryLock", Mock(return_value=Mock()))
    monkeypatch.setattr(module_commands.click, "confirm", Mock(return_value=True))

    result = CliRunner().invoke(
        module_commands.update, ["--no-preview", "--confirm-contract-adoption"]
    )

    assert result.exit_code == 0
    assert observed["orgs"] == ""
    reloaded = ProjectStateManager(project).load_state()
    assert reloaded is not None
    assert reloaded.project.project_contract == "0.89.0"
    assert reloaded.project.adopted_contract_steps == list(_RECORDED_STEP_IDS)
    status_after = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    )
    assert status_after.stdout.strip() == ""
    log = subprocess.run(
        ["git", "log", "-1", "--format=%s"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    )
    assert log.stdout.strip() == "chore: record generated-project contract adoption"


def test_update_billing_names_the_sa201_throttling_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SA207: a project behind SA201 is refused and told which step to adopt."""
    state = _state("0.87.0", modules=("billing", "orgs"))
    manager = Mock()
    manager.load_state.return_value = state
    update_module = Mock(return_value=True)

    monkeypatch.setattr(module_commands, "_validate_update_environment", Mock())
    monkeypatch.setattr(
        module_commands, "ProjectStateManager", Mock(return_value=manager)
    )
    monkeypatch.setattr(module_commands, "_warn_version_drift_for_update", Mock())
    monkeypatch.setattr(
        module_commands, "_validate_module_readiness", Mock(return_value=True)
    )
    monkeypatch.setattr(module_commands, "_update_single_module", update_module)

    result = CliRunner().invoke(module_commands.update, ["--no-preview"])

    assert result.exit_code == 1
    assert "generated project (sa201-throttling)" in result.output
    assert "ScopedRateThrottle" in result.output
    assert update_module.call_count == 0


def test_update_confirm_contract_adoption_records_and_proceeds(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "example"
    project.mkdir()
    state = _state("0.87.0")
    manager = Mock()
    manager.load_state.return_value = state
    update_module = Mock(return_value=True)
    lock = Mock()

    monkeypatch.chdir(project)
    monkeypatch.setattr(module_commands, "_validate_update_environment", Mock())
    monkeypatch.setattr(
        module_commands, "ProjectStateManager", Mock(return_value=manager)
    )
    monkeypatch.setattr(module_commands, "_warn_version_drift_for_update", Mock())
    monkeypatch.setattr(
        module_commands, "_validate_module_readiness", Mock(return_value=True)
    )
    monkeypatch.setattr(module_commands, "_update_single_module", update_module)
    monkeypatch.setattr(
        module_commands,
        "_regenerate_and_record_managed_wiring",
        lambda *args, **kwargs: (True, "regenerated"),
    )
    monkeypatch.setattr(
        module_commands,
        "_commit_regenerated_managed_wiring",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(module_commands, "AdvisoryLock", Mock(return_value=lock))
    monkeypatch.setattr(module_commands, "_commit_contract_adoption", Mock())
    monkeypatch.setattr(module_commands.click, "confirm", Mock(return_value=True))

    result = CliRunner().invoke(
        module_commands.update, ["--no-preview", "--confirm-contract-adoption"]
    )

    assert result.exit_code == 0
    assert update_module.call_count == 1
    assert state.project.project_contract == "0.89.0"
    assert state.project.adopted_contract_steps == list(_RECORDED_STEP_IDS)
    reloaded = ProjectStateManager(project).load_state()
    assert reloaded is not None
    assert reloaded.project.project_contract == "0.89.0"
    assert reloaded.project.adopted_contract_steps == list(_RECORDED_STEP_IDS)


def test_executed_apply_records_adoption_under_its_own_lock(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """SA207: the execution path records under the lock it already holds."""
    state = _state("0.87.0")
    StateManager(tmp_path).save(state)
    ctx = SimpleNamespace(
        existing_state=state,
        qs_config=SimpleNamespace(modules={"orgs": object()}),
        delta=SimpleNamespace(has_changes=True),
        output_path=tmp_path,
        has_pending_post_embed_recovery=False,
        confirm_contract_adoption=True,
    )
    execute_locked = Mock()

    monkeypatch.setattr(apply_command, "_warn_version_drift_for_apply", Mock())
    monkeypatch.setattr(apply_command, "_refresh_context_after_lock", Mock())
    monkeypatch.setattr(apply_command, "_validate_split_ref_override_coverage", Mock())
    monkeypatch.setattr(apply_command, "_attempt_provenance_repair_if_needed", Mock())
    monkeypatch.setattr(apply_command, "_handle_delta_and_existing_state", Mock())
    monkeypatch.setattr(apply_command, "_execute_apply_steps_locked", execute_locked)

    apply_command._execute_apply_steps(ctx, False, True, True)

    assert execute_locked.call_count == 1
    reloaded = ProjectStateManager(tmp_path).load_state()
    assert reloaded is not None
    assert reloaded.project.project_contract == "0.89.0"
    assert reloaded.project.adopted_contract_steps == list(_RECORDED_STEP_IDS)


def test_record_contract_adoption_never_moves_the_vintage_backwards(
    tmp_path: Path,
) -> None:
    """SA207: a newer recorded contract survives an older CLI's confirmation."""
    project = tmp_path / "example"
    project.mkdir()
    state = _state("0.90.0")

    recorded = record_contract_adoption(state, project)

    assert recorded == "0.90.0"
    assert state.project.project_contract == "0.90.0"
    assert state.project.adopted_contract_steps == list(_RECORDED_STEP_IDS)


def test_status_treats_empty_modules_marker_as_consolidated(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """SA207: the explicit empty modules marker is authoritative for status."""
    project = tmp_path / "example"
    project.mkdir()
    StateManager(project).save(_state("0.89.0", modules=()))
    (project / ".quickscale" / "config.yml").write_text(
        "default_remote: https://example.com/r.git\nmodules: {}\n"
    )
    monkeypatch.chdir(project)

    result = CliRunner().invoke(status_command.status, ["--json"])

    assert result.exit_code == 0
    diagnostics = json.loads(result.output)["drift"]
    assert diagnostics["state_consolidated"] is True
    assert diagnostics["legacy_compat_active"] is False


def test_record_contract_adoption_preserves_unknown_newer_ids(
    tmp_path: Path,
) -> None:
    """SA207: an older CLI must not discard ids it does not declare."""
    project = tmp_path / "example"
    project.mkdir()
    state = _state("0.90.0", adopted_steps=("sa210-new-verified-step",))

    recorded = record_contract_adoption(state, project)

    assert recorded == "0.90.0"
    assert state.project.project_contract == "0.90.0"
    assert set(state.project.adopted_contract_steps or ()) >= {
        "sa210-new-verified-step",
        *_DECLARED_STEP_IDS,
    }


def test_status_text_marks_ignored_legacy_hashes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """SA207: a stale legacy ledger is reported as ignored, not in use."""
    project = tmp_path / "example"
    project.mkdir()
    StateManager(project).save(_state("0.89.0", modules=()))
    ProjectStateManager(project).save_managed_file_hashes(
        {"example/settings/modules.py": "abc123"}
    )
    monkeypatch.chdir(project)

    result = CliRunner().invoke(status_command.status, [])

    assert result.exit_code == 0
    assert "ignored" in result.output
    assert "using legacy" not in result.output


def test_record_contract_adoption_is_idempotent(tmp_path: Path) -> None:
    project = tmp_path / "example"
    project.mkdir()
    state = _state("0.89.0")

    recorded = record_contract_adoption(state, project)
    recorded_again = record_contract_adoption(state, project)

    assert recorded == "0.89.0"
    assert recorded_again == "0.89.0"
    assert state.project.project_contract == "0.89.0"
    assert state.project.adopted_contract_steps == list(_RECORDED_STEP_IDS)


def test_record_contract_adoption_keeps_consolidated_state_authoritative(
    tmp_path: Path,
) -> None:
    """SA207: recording must not re-activate legacy read-through import."""
    project = tmp_path / "example"
    project.mkdir()
    ProjectStateManager(project).save_state(_state("0.87.0", modules=()))
    ProjectStateManager(project).save_managed_file_hashes(
        {"example/settings/modules.py": "abc123"}
    )
    before = ProjectStateManager(project).load_state()
    assert before is not None
    assert before.managed_files == {}

    record_contract_adoption(before, project)

    reloaded = ProjectStateManager(project).load_state()
    assert reloaded is not None
    assert reloaded.project.project_contract == "0.89.0"
    assert reloaded.managed_files == {}


def test_locked_apply_path_records_confirmation_on_no_delta(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """SA207: the provenance-repair no-delta path records under the lock."""
    state = _state("0.87.0")
    StateManager(tmp_path).save(state)
    ctx = SimpleNamespace(
        output_path=tmp_path,
        existing_state=state,
        qs_config=SimpleNamespace(modules={"orgs": object()}),
        delta=SimpleNamespace(has_changes=False),
        has_pending_post_embed_recovery=False,
        confirm_contract_adoption=True,
    )
    handle_delta = Mock()
    execute_locked = Mock()

    monkeypatch.setattr(apply_command, "_refresh_context_after_lock", Mock())
    monkeypatch.setattr(apply_command, "_validate_split_ref_override_coverage", Mock())
    monkeypatch.setattr(apply_command, "_attempt_provenance_repair_if_needed", Mock())
    monkeypatch.setattr(apply_command, "_handle_delta_and_existing_state", handle_delta)
    monkeypatch.setattr(apply_command, "_execute_apply_steps_locked", execute_locked)

    apply_command._execute_apply_steps(ctx, False, True, True)

    assert handle_delta.call_count == 0
    assert execute_locked.call_count == 0
    reloaded = ProjectStateManager(tmp_path).load_state()
    assert reloaded is not None
    assert reloaded.project.adopted_contract_steps == list(_RECORDED_STEP_IDS)


def test_deploy_confirm_contract_adoption_records(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """SA207: deploy records the confirmed adoption after its preflight."""
    state = _state("0.87.0", modules=())
    StateManager(tmp_path).save(state)
    manager = Mock()
    manager.load_state.return_value = state
    first_step = Mock()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        deployment_commands, "ProjectStateManager", Mock(return_value=manager)
    )
    monkeypatch.setattr(
        deployment_commands, "_check_uncommitted_changes_step", first_step
    )
    monkeypatch.setattr(deployment_commands, "_verify_railway_files_step", Mock())
    monkeypatch.setattr(deployment_commands, "_verify_dependencies_step", Mock())
    monkeypatch.setattr(deployment_commands, "_check_poetry_lock_step", Mock())
    monkeypatch.setattr(deployment_commands, "_ensure_railway_cli_step", Mock())
    monkeypatch.setattr(deployment_commands, "_ensure_railway_auth_step", Mock())
    monkeypatch.setattr(deployment_commands, "_init_railway_project_step", Mock())
    monkeypatch.setattr(
        deployment_commands, "_app_service_exists_step", Mock(return_value=False)
    )
    monkeypatch.setattr(
        deployment_commands, "_setup_postgres_step", Mock(return_value="Postgres")
    )
    monkeypatch.setattr(deployment_commands, "_create_app_service_step", Mock())
    monkeypatch.setattr(
        deployment_commands, "_existing_service_variables", Mock(return_value={})
    )
    monkeypatch.setattr(
        deployment_commands, "_link_database_step", Mock(return_value=True)
    )
    monkeypatch.setattr(
        deployment_commands, "_generate_domain_step", Mock(return_value="example.test")
    )
    monkeypatch.setattr(deployment_commands, "_configure_env_vars_step", Mock())
    monkeypatch.setattr(deployment_commands, "_deploy_app_step", Mock())
    monkeypatch.setattr(
        deployment_commands, "_verify_deployment_step", Mock(return_value=True)
    )
    monkeypatch.setattr(deployment_commands, "_display_summary", Mock())

    result = CliRunner().invoke(
        deployment_commands.railway,
        ["--project-name", "example", "--confirm-contract-adoption"],
    )

    assert result.exit_code == 0
    assert first_step.call_count == 1
    reloaded = ProjectStateManager(tmp_path).load_state()
    assert reloaded is not None
    assert reloaded.project.adopted_contract_steps == list(_DECLARED_STEP_IDS)


def test_apply_refuses_before_normalizing_config(tmp_path: Path) -> None:
    project = tmp_path / "example"
    project.mkdir()
    StateManager(project).save(_state(None, modules=("auth",)))
    config_path = project / "quickscale.yml"
    original_config = """\
version: "1"
project:
  slug: example
  package: example
  theme: showcase_react
modules:
  auth:
docker:
  start: false
"""
    config_path.write_text(original_config)

    result = CliRunner().invoke(
        apply_command.apply,
        [str(config_path), "--no-modules", "--no-docker"],
    )

    assert result.exit_code == 1
    assert "generated project (sa201-throttling)" in result.output
    assert config_path.read_text() == original_config
    assert "Added implied module config" not in result.output


def test_status_uses_shipped_vintage_for_old_embedded_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "example"
    project.mkdir()
    StateManager(project).save(_state("0.87.0", modules=("billing",)))
    embedded_module = project / "modules" / "billing"
    embedded_module.mkdir(parents=True)
    (embedded_module / "module.yml").write_text('name: billing\nversion: "0.87.0"\n')
    monkeypatch.chdir(project)

    result = CliRunner().invoke(status_command.status, ["--json"])

    assert result.exit_code == 0
    diagnostics = json.loads(result.output)["drift"]["contract_vintage"]
    assert diagnostics["project_contract"] == "0.87.0"
    assert diagnostics["project_steps_behind_count"] == len(_DECLARED_STEP_IDS)
    assert diagnostics["modules_behind_count"] == 1
    assert diagnostics["modules_behind"][0]["module"] == "billing"
    assert diagnostics["modules_behind"][0]["minimum"] == "0.89.0"


def test_status_reports_adopted_steps_as_satisfied(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """SA207: status must consult the recorded ids, not just the version."""
    project = tmp_path / "example"
    project.mkdir()
    StateManager(project).save(
        _state("0.89.0", modules=(), adopted_steps=_DECLARED_STEP_IDS)
    )
    monkeypatch.chdir(project)

    result = CliRunner().invoke(status_command.status, ["--json"])

    assert result.exit_code == 0
    diagnostics = json.loads(result.output)["drift"]["contract_vintage"]
    assert diagnostics["project_step_count"] == len(_DECLARED_STEP_IDS)
    assert diagnostics["project_steps_behind_count"] == 0


def test_apply_confirm_contract_adoption_records_without_config_change(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """SA207: an unchanged configuration still has an adoption-only path."""
    state = _state("0.87.0")
    StateManager(tmp_path).save(state)
    context = SimpleNamespace(
        existing_state=state,
        qs_config=SimpleNamespace(modules={"orgs": object()}),
        delta=SimpleNamespace(has_changes=False),
        output_path=tmp_path,
        has_pending_post_embed_recovery=False,
    )
    execute = Mock()
    config_path = tmp_path / "quickscale.yml"
    config_path.write_text("version: '1'\n")

    monkeypatch.setattr(
        apply_command, "_resolve_apply_preflight", Mock(return_value=tmp_path)
    )
    monkeypatch.setattr(
        apply_command, "_prepare_apply_context", Mock(return_value=context)
    )
    monkeypatch.setattr(apply_command, "_validate_split_ref_override_coverage", Mock())
    monkeypatch.setattr(apply_command, "_display_config_summary", Mock())
    monkeypatch.setattr(
        apply_command, "_provenance_repair_might_be_needed", Mock(return_value=False)
    )
    monkeypatch.setattr(apply_command, "_execute_apply_steps", execute)

    result = CliRunner().invoke(
        apply_command.apply, [str(config_path), "--confirm-contract-adoption"]
    )

    assert result.exit_code == 0
    assert execute.call_count == 0
    reloaded = ProjectStateManager(tmp_path).load_state()
    assert reloaded is not None
    assert reloaded.project.project_contract == "0.89.0"
    assert reloaded.project.adopted_contract_steps == list(_RECORDED_STEP_IDS)


def test_status_keeps_unknown_orphan_as_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "example"
    project.mkdir()
    StateManager(project).save(_state("0.89.0", modules=("auth",)))
    orphan_module = project / "modules" / "mystery"
    orphan_module.mkdir(parents=True)
    (orphan_module / "module.yml").write_text('name: mystery\nversion: "0.89.0"\n')
    monkeypatch.chdir(project)

    result = CliRunner().invoke(status_command.status, ["--json"])

    assert result.exit_code == 0
    filesystem_drift = json.loads(result.output)["drift"]["filesystem_drift"]
    assert filesystem_drift["missing_modules"] == ["auth"]
    assert filesystem_drift["orphaned_modules"] == ["mystery"]


@pytest.mark.parametrize(
    ("project_contract", "adopted_steps", "acknowledged", "expected_exit"),
    [
        ("0.87.0", (), False, 1),
        (None, (), False, 1),
        ("0.87.0", (), True, 0),
        # A mid-cycle generation shares 0.89.0 but never adopted the steps.
        ("0.89.0", (), False, 1),
        ("0.89.0", _DECLARED_STEP_IDS, False, 0),
    ],
)
def test_update_enforces_vintage_before_module_mutation(
    monkeypatch: pytest.MonkeyPatch,
    project_contract: str | None,
    adopted_steps: tuple[str, ...],
    acknowledged: bool,
    expected_exit: int,
) -> None:
    state = _state(project_contract, adopted_steps=adopted_steps)
    manager = Mock()
    manager.load_state.return_value = state
    update_module = Mock(return_value=True)
    lock = Mock()

    monkeypatch.setattr(module_commands, "_validate_update_environment", Mock())
    monkeypatch.setattr(
        module_commands, "ProjectStateManager", Mock(return_value=manager)
    )
    monkeypatch.setattr(module_commands, "_warn_version_drift_for_update", Mock())
    monkeypatch.setattr(
        module_commands, "_validate_module_readiness", Mock(return_value=True)
    )
    monkeypatch.setattr(
        module_commands,
        "enforce_shipped_contract_vintage",
        lambda current_state, module_names, **kwargs: enforce_contract_vintage(
            current_state,
            {"orgs": _orgs_manifest()},
            operation=kwargs["operation"],
            acknowledged=kwargs["acknowledged"],
        ),
    )
    monkeypatch.setattr(module_commands, "_update_single_module", update_module)
    monkeypatch.setattr(
        module_commands,
        "_regenerate_and_record_managed_wiring",
        lambda *args, **kwargs: (True, "regenerated"),
    )
    monkeypatch.setattr(
        module_commands,
        "_commit_regenerated_managed_wiring",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(module_commands, "AdvisoryLock", Mock(return_value=lock))
    monkeypatch.setattr(module_commands.click, "confirm", Mock(return_value=True))

    args = ["--no-preview"]
    if acknowledged:
        args.append("--acknowledge-contract-vintage")
    result = CliRunner().invoke(module_commands.update, args)

    assert result.exit_code == expected_exit
    assert update_module.call_count == (1 if expected_exit == 0 else 0)
    if expected_exit:
        assert "Cannot run 'quickscale update'" in result.output
        assert "generated project (sa192-shared-design)" in result.output


@pytest.mark.parametrize(
    ("project_contract", "adopted_steps", "has_state", "acknowledged", "expected_exit"),
    [
        ("0.87.0", (), True, False, 1),
        (None, (), True, False, 1),
        ("0.87.0", (), True, True, 0),
        ("0.89.0", (), True, False, 1),
        ("0.89.0", _DECLARED_STEP_IDS, True, False, 0),
        (None, (), False, False, 0),
    ],
)
def test_apply_enforces_vintage_before_execution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    project_contract: str | None,
    adopted_steps: tuple[str, ...],
    has_state: bool,
    acknowledged: bool,
    expected_exit: int,
) -> None:
    state = _state(project_contract, adopted_steps=adopted_steps) if has_state else None
    context = SimpleNamespace(
        existing_state=state,
        qs_config=SimpleNamespace(modules={"orgs": object()}),
        delta=object(),
        output_path=tmp_path,
        has_pending_post_embed_recovery=False,
    )
    execute = Mock()
    config_path = tmp_path / "quickscale.yml"
    config_path.write_text("version: '1'\n")

    monkeypatch.setattr(
        apply_command, "_resolve_apply_preflight", Mock(return_value=tmp_path)
    )
    monkeypatch.setattr(
        apply_command, "_prepare_apply_context", Mock(return_value=context)
    )
    monkeypatch.setattr(
        apply_command,
        "enforce_shipped_contract_vintage",
        lambda current_state, module_names, **kwargs: enforce_contract_vintage(
            current_state,
            {"orgs": _orgs_manifest()},
            operation=kwargs["operation"],
            acknowledged=kwargs["acknowledged"],
        ),
    )
    monkeypatch.setattr(apply_command, "_validate_split_ref_override_coverage", Mock())
    monkeypatch.setattr(apply_command, "_display_config_summary", Mock())
    monkeypatch.setattr(
        apply_command, "_provenance_repair_might_be_needed", Mock(return_value=False)
    )
    monkeypatch.setattr(apply_command, "_handle_delta_and_existing_state", Mock())
    monkeypatch.setattr(apply_command, "_check_output_directory", Mock())
    monkeypatch.setattr(apply_command, "_confirm_apply", Mock(return_value=False))
    monkeypatch.setattr(apply_command, "_execute_apply_steps", execute)

    args = [str(config_path)]
    if acknowledged:
        args.append("--acknowledge-contract-vintage")
    result = CliRunner().invoke(apply_command.apply, args)

    assert result.exit_code == expected_exit
    assert execute.call_count == (1 if expected_exit == 0 else 0)
    if expected_exit:
        assert "Cannot run 'quickscale apply'" in result.output
        assert "generated project (sa192-shared-design)" in result.output


@pytest.mark.parametrize(
    ("project_contract", "adopted_steps", "has_state", "acknowledged", "expected_exit"),
    [
        ("0.87.0", (), True, False, 1),
        (None, (), True, False, 1),
        ("0.87.0", (), True, True, 0),
        ("0.89.0", (), True, False, 1),
        ("0.89.0", _DECLARED_STEP_IDS, True, False, 0),
        (None, (), False, False, 0),
    ],
)
def test_deploy_enforces_vintage_before_preflight(
    monkeypatch: pytest.MonkeyPatch,
    project_contract: str | None,
    adopted_steps: tuple[str, ...],
    has_state: bool,
    acknowledged: bool,
    expected_exit: int,
) -> None:
    state = (
        _state(project_contract, modules=(), adopted_steps=adopted_steps)
        if has_state
        else None
    )
    manager = Mock()
    manager.load_state.return_value = state
    first_step = Mock()

    monkeypatch.setattr(
        deployment_commands, "ProjectStateManager", Mock(return_value=manager)
    )
    monkeypatch.setattr(
        deployment_commands, "_check_uncommitted_changes_step", first_step
    )
    monkeypatch.setattr(deployment_commands, "_verify_railway_files_step", Mock())
    monkeypatch.setattr(deployment_commands, "_verify_dependencies_step", Mock())
    monkeypatch.setattr(deployment_commands, "_check_poetry_lock_step", Mock())
    monkeypatch.setattr(deployment_commands, "_ensure_railway_cli_step", Mock())
    monkeypatch.setattr(deployment_commands, "_ensure_railway_auth_step", Mock())
    monkeypatch.setattr(deployment_commands, "_init_railway_project_step", Mock())
    monkeypatch.setattr(
        deployment_commands, "_app_service_exists_step", Mock(return_value=False)
    )
    monkeypatch.setattr(
        deployment_commands, "_setup_postgres_step", Mock(return_value="Postgres")
    )
    monkeypatch.setattr(deployment_commands, "_create_app_service_step", Mock())
    monkeypatch.setattr(
        deployment_commands, "_existing_service_variables", Mock(return_value={})
    )
    monkeypatch.setattr(
        deployment_commands, "_link_database_step", Mock(return_value=True)
    )
    monkeypatch.setattr(
        deployment_commands, "_generate_domain_step", Mock(return_value="example.test")
    )
    monkeypatch.setattr(deployment_commands, "_configure_env_vars_step", Mock())
    monkeypatch.setattr(deployment_commands, "_deploy_app_step", Mock())
    monkeypatch.setattr(
        deployment_commands, "_verify_deployment_step", Mock(return_value=True)
    )
    monkeypatch.setattr(deployment_commands, "_display_summary", Mock())

    args = ["--project-name", "example"]
    if acknowledged:
        args.append("--acknowledge-contract-vintage")
    result = CliRunner().invoke(deployment_commands.railway, args)

    assert result.exit_code == expected_exit
    assert first_step.call_count == (1 if expected_exit == 0 else 0)
    if expected_exit:
        expected_contract = project_contract or "unknown (legacy project)"
        assert (
            f"Cannot run 'quickscale deploy railway': project contract"
            f" {expected_contract} is behind."
        ) in result.output
        assert "generated project (sa201-throttling)" in result.output
