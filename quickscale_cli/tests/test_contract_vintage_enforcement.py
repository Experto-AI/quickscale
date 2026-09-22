"""Regression coverage for enforced generated-file contract vintages."""

from __future__ import annotations

import json
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
from quickscale_cli.commands.contract_vintage import enforce_contract_vintage
from quickscale_cli.commands.deployment_commands import RAILWAY_CONTRACT_VINTAGE
from quickscale_core.manifest import ContractVintage, ModuleManifest
from quickscale_core.manifest.loader import load_manifest_from_path
from quickscale_core.schema.state_schema import (
    ModuleState,
    ProjectState,
    QuickScaleState,
    StateManager,
)


def _state(
    project_contract: str | None,
    *,
    modules: tuple[str, ...] = ("orgs",),
) -> QuickScaleState:
    return QuickScaleState(
        version="1",
        project=ProjectState(
            slug="example",
            package="example",
            theme="showcase_react",
            project_contract=project_contract,
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


def test_orgs_declares_the_089_generated_file_contract() -> None:
    manifest_path = Path(__file__).parents[2] / "quickscale_modules/orgs/module.yml"
    manifest = load_manifest_from_path(manifest_path)

    assert manifest.contract_vintage is not None
    assert manifest.contract_vintage.minimum == "0.89.0"
    steps = " ".join(manifest.contract_vintage.manual_adoption_steps)
    assert "settings/production.py" in steps
    assert "settings/base.py" in steps
    assert "start.sh" in steps
    assert "db/init.sql" in steps
    assert ".env.example" in steps
    assert "docker-compose.yml" in steps
    assert "Dockerfile" in steps
    assert "OPERATIONS.md" in steps
    assert "existing local database" in steps
    assert "password in the adopted local RUNTIME_DATABASE_URL" in steps
    assert "reset the disposable Compose database volume" in steps
    assert manifest.contract_vintage == RAILWAY_CONTRACT_VINTAGE


@pytest.mark.parametrize("module_name", ["auth", "billing", "blog", "listings", "crm"])
def test_styled_modules_declare_the_089_design_contract(module_name: str) -> None:
    manifest_path = (
        Path(__file__).parents[2] / f"quickscale_modules/{module_name}/module.yml"
    )
    manifest = load_manifest_from_path(manifest_path)

    assert manifest.contract_vintage is not None
    assert manifest.contract_vintage.minimum == "0.89.0"
    steps = " ".join(manifest.contract_vintage.manual_adoption_steps)
    assert "templates/base.html" in steps
    assert "templates/index.html" in steps
    assert "templates/social/*.html" in steps
    assert "frontend/assets/index.css" in steps
    assert "frontend/vite.config.ts" in steps
    assert "/static/frontend/" in steps
    assert "exact HTTP/WebSocket Host enforcement" in steps
    assert "settings/local.py" in steps
    assert "QUICKSCALE_FRONTEND_HOST_PORT" in steps
    assert "QUICKSCALE_FRONTEND_ORIGIN" in steps
    assert "malformed origins fail explicitly" in steps
    assert "docker-compose.yml" in steps
    assert "${QUICKSCALE_FRONTEND_HOST_PORT:-5173}:5173" in steps
    assert "probes Vite with the effective Host" in steps
    assert "pnpm build" in steps


def test_railway_declares_the_same_089_generated_file_contract() -> None:
    assert RAILWAY_CONTRACT_VINTAGE.minimum == "0.89.0"
    steps = " ".join(RAILWAY_CONTRACT_VINTAGE.manual_adoption_steps)
    assert "settings/production.py" in steps
    assert "settings/base.py" in steps
    assert "start.sh" in steps
    assert "db/init.sql" in steps
    assert ".env.example" in steps
    assert "docker-compose.yml" in steps
    assert "Dockerfile" in steps
    assert "OPERATIONS.md" in steps
    assert "existing local database" in steps
    assert "password in the adopted local RUNTIME_DATABASE_URL" in steps
    assert "reset the disposable Compose database volume" in steps


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


@pytest.mark.parametrize("project_contract", [None, "0.87.0"])
def test_shared_enforcement_refuses_old_projects(project_contract: str | None) -> None:
    with pytest.raises(click.Abort):
        enforce_contract_vintage(
            _state(project_contract),
            {"orgs": _orgs_manifest()},
            operation="'quickscale update'",
            acknowledged=False,
        )


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
    assert "orgs requires project_contract >= 0.89.0" in result.output
    assert config_path.read_text() == original_config
    assert "Added implied module config" not in result.output


def test_status_uses_shipped_vintage_for_old_embedded_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "example"
    project.mkdir()
    StateManager(project).save(_state("0.87.0"))
    embedded_module = project / "modules" / "orgs"
    embedded_module.mkdir(parents=True)
    (embedded_module / "module.yml").write_text('name: orgs\nversion: "0.87.0"\n')
    monkeypatch.chdir(project)

    result = CliRunner().invoke(status_command.status, ["--json"])

    assert result.exit_code == 0
    diagnostics = json.loads(result.output)["drift"]["contract_vintage"]
    assert diagnostics["project_contract"] == "0.87.0"
    assert diagnostics["modules_behind_count"] == 1
    assert diagnostics["modules_behind"][0]["module"] == "orgs"
    assert diagnostics["modules_behind"][0]["minimum"] == "0.89.0"


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
    ("project_contract", "acknowledged", "expected_exit"),
    [
        ("0.87.0", False, 1),
        (None, False, 1),
        ("0.87.0", True, 0),
        ("0.89.0", False, 0),
    ],
)
def test_update_enforces_vintage_before_module_mutation(
    monkeypatch: pytest.MonkeyPatch,
    project_contract: str | None,
    acknowledged: bool,
    expected_exit: int,
) -> None:
    state = _state(project_contract)
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
    monkeypatch.setattr(module_commands, "AdvisoryLock", Mock(return_value=lock))
    monkeypatch.setattr(module_commands.click, "confirm", Mock(return_value=True))

    args = ["--no-preview"]
    if acknowledged:
        args.append("--acknowledge-contract-vintage")
    result = CliRunner().invoke(module_commands.update, args)

    assert result.exit_code == expected_exit
    assert update_module.call_count == (1 if expected_exit == 0 else 0)
    if expected_exit:
        assert "orgs requires project_contract >= 0.89.0" in result.output


@pytest.mark.parametrize(
    ("project_contract", "has_state", "acknowledged", "expected_exit"),
    [
        ("0.87.0", True, False, 1),
        (None, True, False, 1),
        ("0.87.0", True, True, 0),
        ("0.89.0", True, False, 0),
        (None, False, False, 0),
    ],
)
def test_apply_enforces_vintage_before_execution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    project_contract: str | None,
    has_state: bool,
    acknowledged: bool,
    expected_exit: int,
) -> None:
    state = _state(project_contract) if has_state else None
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
        assert "orgs requires project_contract >= 0.89.0" in result.output


@pytest.mark.parametrize(
    ("project_contract", "has_state", "acknowledged", "expected_exit"),
    [
        ("0.87.0", True, False, 1),
        (None, True, False, 1),
        ("0.87.0", True, True, 0),
        ("0.89.0", True, False, 0),
        (None, False, False, 0),
    ],
)
def test_deploy_enforces_vintage_before_preflight(
    monkeypatch: pytest.MonkeyPatch,
    project_contract: str | None,
    has_state: bool,
    acknowledged: bool,
    expected_exit: int,
) -> None:
    state = _state(project_contract, modules=()) if has_state else None
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
        assert (
            "quickscale deploy railway requires project_contract >= 0.89.0"
            in result.output
        )
