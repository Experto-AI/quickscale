"""Tests for the public disaster-recovery command surface."""

import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import call, patch

import click
import pytest
from click.testing import CliRunner

import quickscale_cli.commands.dr_commands as dr_commands
from quickscale_cli.commands.dr_commands import (
    DisasterRecoveryContext,
    DrRouteSpec,
    dr,
)
from quickscale_cli.utils.project_identity import ProjectIdentity


def _context(
    *,
    route: str = "local-to-railway-develop",
) -> DisasterRecoveryContext:
    route_specs = {
        "local-to-railway-develop": DrRouteSpec(
            label="local-to-railway-develop",
            source_kind="local",
            source_environment="local",
            target_kind="railway",
            target_environment="railway-develop",
        ),
        "railway-develop-to-railway-production": DrRouteSpec(
            label="railway-develop-to-railway-production",
            source_kind="railway",
            source_environment="railway-develop",
            target_kind="railway",
            target_environment="railway-production",
        ),
    }
    selected_route = route_specs[route]
    return DisasterRecoveryContext(
        route=selected_route,
        identity=ProjectIdentity(slug="myapp", package="myapp"),
        source_service=(
            "myapp-develop" if selected_route.source_kind == "railway" else None
        ),
        target_service="myapp-target",
        source_railway_environment=None,
        target_railway_environment=None,
        source_runtime_variables={"DEBUG": "False"},
        target_runtime_variables={"DEBUG": "False"},
    )


def test_capture_requires_source_service_for_railway_source_route() -> None:
    runner = CliRunner()

    with (
        patch("quickscale_cli.commands.dr_commands._validate_project_and_docker"),
        patch(
            "quickscale_cli.commands.dr_commands.resolve_project_identity",
            return_value=ProjectIdentity(slug="myapp", package="myapp"),
        ),
    ):
        result = runner.invoke(
            dr,
            [
                "capture",
                "--route",
                "railway-develop-to-railway-production",
            ],
        )

    assert result.exit_code == 1
    assert "requires --source-service" in result.output


def test_plan_requires_target_service_for_railway_target_route() -> None:
    runner = CliRunner()

    with patch("quickscale_cli.commands.dr_commands._validate_project_and_docker"):
        result = runner.invoke(
            dr,
            [
                "plan",
                "--route",
                "local-to-railway-develop",
                "--snapshot-id",
                "snap-123",
            ],
        )

    assert result.exit_code == 1
    assert "requires --target-service" in result.output


def test_capture_local_route_outputs_snapshot_summary() -> None:
    runner = CliRunner()
    context = _context()

    with (
        patch(
            "quickscale_cli.commands.dr_commands._build_context",
            return_value=context,
        ),
        patch(
            "quickscale_cli.commands.dr_commands._capture_snapshot_report",
            return_value={
                "snapshot_id": "snap-123",
                "source_environment": "local",
                "status": "ready",
                "authoritative_dump": {"filename": "db.dump"},
            },
        ),
    ):
        result = runner.invoke(
            dr,
            ["capture", "--route", "local-to-railway-develop"],
        )

    assert result.exit_code == 0
    assert "Snapshot id: snap-123" in result.output
    assert "Database artifact: db.dump" in result.output


def test_capture_outputs_json_snapshot_payload() -> None:
    runner = CliRunner()
    context = _context()

    with (
        patch(
            "quickscale_cli.commands.dr_commands._build_context",
            return_value=context,
        ),
        patch(
            "quickscale_cli.commands.dr_commands._capture_snapshot_report",
            return_value={
                "snapshot_id": "snap-123",
                "source_environment": "local",
                "status": "ready",
                "authoritative_dump": {"filename": "db.dump"},
            },
        ),
    ):
        result = runner.invoke(
            dr,
            ["capture", "--route", "local-to-railway-develop", "--json"],
        )

    assert result.exit_code == 0
    assert json.loads(result.output) == {
        "route": "local-to-railway-develop",
        "snapshot": {
            "snapshot_id": "snap-123",
            "source_environment": "local",
            "status": "ready",
            "authoritative_dump": {"filename": "db.dump"},
        },
    }


def test_plan_records_verification_and_shows_manual_actions() -> None:
    runner = CliRunner()
    context = _context()
    snapshot_report = {
        "snapshot_id": "snap-123",
        "sidecar_payloads": {
            "release-metadata.json": {"git_sha": "abc123", "app_version": "0.82.0"},
            "env-var-manifest.json": {
                "status": "ready",
                "names": ["DEBUG", "DATABASE_URL"],
            },
            "promotion-verification.json": {"reports": []},
        },
    }
    env_plan = {
        "status": "manual_required",
        "portable_candidates": ["DEBUG"],
        "portable_existing": [],
        "portable_conflicts": [],
        "manual_requirements": [{"name": "DATABASE_URL", "reason": "provider-owned"}],
        "ignored_count": 0,
    }

    with (
        patch(
            "quickscale_cli.commands.dr_commands._build_context",
            return_value=context,
        ),
        patch(
            "quickscale_cli.commands.dr_commands._fetch_snapshot_report",
            return_value=snapshot_report,
        ),
        patch(
            "quickscale_cli.commands.dr_commands._build_database_plan",
            return_value={
                "status": "ready",
                "message": "Restore validation completed successfully (dry run).",
            },
        ),
        patch(
            "quickscale_cli.commands.dr_commands._run_media_sync",
            return_value={"status": "ready", "planned_count": 3},
        ),
        patch(
            "quickscale_cli.commands.dr_commands._build_env_sync_plan",
            return_value=env_plan,
        ),
        patch(
            "quickscale_cli.commands.dr_commands._record_verification"
        ) as mocked_record,
    ):
        result = runner.invoke(
            dr,
            [
                "plan",
                "--route",
                "local-to-railway-develop",
                "--snapshot-id",
                "snap-123",
                "--target-service",
                "myapp-develop",
            ],
        )

    assert result.exit_code == 0
    assert "Plan status: manual_required" in result.output
    assert "Manual actions:" in result.output
    assert "DATABASE_URL" in result.output
    mocked_record.assert_called_once()
    assert mocked_record.call_args.kwargs["phase"] == "plan"


def test_plan_outputs_json_payload() -> None:
    runner = CliRunner()
    context = _context()

    with (
        patch(
            "quickscale_cli.commands.dr_commands._build_context",
            return_value=context,
        ),
        patch(
            "quickscale_cli.commands.dr_commands._fetch_snapshot_report",
            return_value={
                "snapshot_id": "snap-123",
                "sidecar_payloads": {
                    "release-metadata.json": {
                        "git_sha": "abc123",
                        "app_version": "0.82.0",
                    },
                },
            },
        ),
        patch(
            "quickscale_cli.commands.dr_commands._build_database_plan",
            return_value={
                "status": "ready",
                "message": "Restore validation completed successfully (dry run).",
            },
        ),
        patch(
            "quickscale_cli.commands.dr_commands._run_media_sync",
            return_value={"status": "ready", "planned_count": 2},
        ),
        patch(
            "quickscale_cli.commands.dr_commands._build_env_sync_plan",
            return_value={
                "status": "ready",
                "portable_candidates": ["DEBUG"],
                "portable_existing": [],
                "portable_conflicts": [],
                "manual_requirements": [],
                "ignored_count": 0,
            },
        ),
        patch("quickscale_cli.commands.dr_commands._record_verification"),
    ):
        result = runner.invoke(
            dr,
            [
                "plan",
                "--route",
                "local-to-railway-develop",
                "--snapshot-id",
                "snap-123",
                "--target-service",
                "myapp-target",
                "--json",
            ],
        )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "ready"
    assert payload["snapshot_id"] == "snap-123"
    assert payload["release_metadata"]["git_sha"] == "abc123"


def test_execute_runs_selected_surfaces_and_records_report() -> None:
    runner = CliRunner()
    context = _context()
    snapshot_report = {"snapshot_id": "snap-123", "sidecar_payloads": {}}

    with (
        patch(
            "quickscale_cli.commands.dr_commands._build_context",
            return_value=context,
        ),
        patch(
            "quickscale_cli.commands.dr_commands._fetch_snapshot_report",
            return_value=snapshot_report,
        ),
        patch(
            "quickscale_cli.commands.dr_commands._build_env_sync_plan",
            return_value={
                "portable_candidates": ["DEBUG"],
                "manual_requirements": [],
                "portable_conflicts": [],
            },
        ),
        patch(
            "quickscale_cli.commands.dr_commands._execute_portable_env_sync",
            return_value={"status": "completed", "copied": ["DEBUG"], "failed": []},
        ) as mocked_env,
        patch(
            "quickscale_cli.commands.dr_commands._execute_database_restore",
            return_value={
                "status": "completed",
                "restore_message": "Restore executed.",
            },
        ) as mocked_db,
        patch(
            "quickscale_cli.commands.dr_commands._run_media_sync",
            return_value={"status": "completed", "copied_count": 3},
        ) as mocked_media,
        patch(
            "quickscale_cli.commands.dr_commands._record_verification"
        ) as mocked_record,
    ):
        result = runner.invoke(
            dr,
            [
                "execute",
                "--route",
                "local-to-railway-develop",
                "--snapshot-id",
                "snap-123",
                "--target-service",
                "myapp-develop",
                "--env-vars",
                "--database",
                "--media",
            ],
        )

    assert result.exit_code == 0
    assert "Execution status: completed" in result.output
    mocked_env.assert_called_once()
    mocked_db.assert_called_once()
    mocked_media.assert_called_once_with(
        context,
        snapshot_id="snap-123",
        dry_run=False,
    )
    mocked_record.assert_called_once()
    assert mocked_record.call_args.kwargs["phase"] == "execute"


def test_execute_requires_at_least_one_selected_surface() -> None:
    runner = CliRunner()

    result = runner.invoke(
        dr,
        [
            "execute",
            "--route",
            "local-to-railway-develop",
            "--snapshot-id",
            "snap-123",
            "--target-service",
            "myapp-target",
        ],
    )

    assert result.exit_code == 1
    assert "Choose at least one operational surface" in result.output


def test_execute_outputs_json_partial_payload_and_records_rollback_pin() -> None:
    runner = CliRunner()
    context = _context()

    with (
        patch(
            "quickscale_cli.commands.dr_commands._build_context",
            return_value=context,
        ),
        patch(
            "quickscale_cli.commands.dr_commands._fetch_snapshot_report",
            return_value={"snapshot_id": "snap-123", "sidecar_payloads": {}},
        ),
        patch(
            "quickscale_cli.commands.dr_commands._build_env_sync_plan",
            return_value={
                "portable_candidates": [],
                "manual_requirements": [{"name": "DATABASE_URL"}],
                "portable_conflicts": [],
            },
        ),
        patch(
            "quickscale_cli.commands.dr_commands._set_rollback_pin",
            return_value={
                "rollback_pin": {
                    "active": True,
                    "expires_at": "2026-04-06T18:00:00+00:00",
                    "reason": "pre-production cutover",
                }
            },
        ) as mocked_pin,
        patch(
            "quickscale_cli.commands.dr_commands._execute_portable_env_sync",
            return_value={
                "status": "manual_required",
                "copied": [],
                "failed": [],
                "manual_requirements": [{"name": "DATABASE_URL"}],
                "portable_conflicts": [],
            },
        ),
        patch(
            "quickscale_cli.commands.dr_commands._record_verification"
        ) as mocked_record,
    ):
        result = runner.invoke(
            dr,
            [
                "execute",
                "--route",
                "local-to-railway-develop",
                "--snapshot-id",
                "snap-123",
                "--target-service",
                "myapp-target",
                "--env-vars",
                "--rollback-pin-hours",
                "6",
                "--rollback-pin-reason",
                "pre-production cutover",
                "--json",
            ],
        )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "partial"
    assert payload["rollback_pin"]["reason"] == "pre-production cutover"
    mocked_pin.assert_called_once()
    assert mocked_record.call_args.kwargs["status"] == "partial"


def test_execute_requires_rollback_pin_for_production_routes() -> None:
    runner = CliRunner()
    production_context = replace(
        _context(route="railway-develop-to-railway-production"),
        target_service="myapp-production",
    )

    with patch(
        "quickscale_cli.commands.dr_commands._build_context",
        return_value=production_context,
    ):
        result = runner.invoke(
            dr,
            [
                "execute",
                "--route",
                "railway-develop-to-railway-production",
                "--snapshot-id",
                "snap-123",
                "--source-service",
                "myapp-develop",
                "--target-service",
                "myapp-production",
                "--database",
            ],
        )

    assert result.exit_code == 1
    assert "require --rollback-pin-hours and --rollback-pin-reason" in result.output


def test_report_outputs_json_route_report() -> None:
    runner = CliRunner()
    context = _context()

    with (
        patch(
            "quickscale_cli.commands.dr_commands._build_context",
            return_value=context,
        ),
        patch(
            "quickscale_cli.commands.dr_commands._fetch_snapshot_report",
            return_value={
                "snapshot_id": "snap-123",
                "status": "ready",
                "source_environment": "local",
                "sidecar_payloads": {"promotion-verification.json": {"reports": []}},
            },
        ),
    ):
        result = runner.invoke(
            dr,
            [
                "report",
                "--route",
                "local-to-railway-develop",
                "--snapshot-id",
                "snap-123",
                "--json",
            ],
        )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["route"] == "local-to-railway-develop"
    assert payload["latest_records"] == {}


def test_report_formats_latest_plan_and_execute_records() -> None:
    runner = CliRunner()
    context = _context()
    snapshot_report = {
        "snapshot_id": "snap-123",
        "status": "ready",
        "sidecar_payloads": {
            "promotion-verification.json": {
                "reports": [
                    {
                        "route": "local-to-railway-develop",
                        "phase": "plan",
                        "status": "manual_required",
                    },
                    {
                        "route": "local-to-railway-develop",
                        "phase": "execute",
                        "status": "completed",
                    },
                ]
            }
        },
    }

    with (
        patch(
            "quickscale_cli.commands.dr_commands._build_context",
            return_value=context,
        ),
        patch(
            "quickscale_cli.commands.dr_commands._fetch_snapshot_report",
            return_value=snapshot_report,
        ),
    ):
        result = runner.invoke(
            dr,
            [
                "report",
                "--route",
                "local-to-railway-develop",
                "--snapshot-id",
                "snap-123",
            ],
        )

    assert result.exit_code == 0
    assert "Plan status: manual_required" in result.output
    assert "Execute status: completed" in result.output


def test_resolve_project_identity_wraps_value_error() -> None:
    with patch(
        "quickscale_cli.commands.dr_commands.resolve_project_identity",
        side_effect=ValueError("missing quickscale.yml"),
    ):
        with pytest.raises(click.ClickException, match="missing quickscale.yml"):
            dr_commands._resolve_project_identity()


def test_fetch_railway_runtime_variables_raises_when_lookup_fails() -> None:
    with patch(
        "quickscale_cli.commands.dr_commands.get_railway_variables",
        return_value=None,
    ):
        with pytest.raises(
            click.ClickException,
            match=r"Unable to load Railway variables for the target service 'myapp-production \(production\)'",
        ):
            dr_commands._fetch_railway_runtime_variables(
                service="myapp-production",
                railway_environment="production",
                role="target",
            )


def test_build_context_fetches_source_and_target_runtime_variables_for_railway_route() -> (
    None
):
    with (
        patch("quickscale_cli.commands.dr_commands._validate_project_and_docker"),
        patch(
            "quickscale_cli.commands.dr_commands._resolve_project_identity",
            return_value=ProjectIdentity(slug="myapp", package="myapp"),
        ),
        patch(
            "quickscale_cli.commands.dr_commands._fetch_railway_runtime_variables",
            side_effect=[{"DEBUG": "false"}, {"DEBUG": "true"}],
        ) as mocked_fetch,
    ):
        context = dr_commands._build_context(
            "railway-develop-to-railway-production",
            source_service="myapp-develop",
            target_service="myapp-production",
            source_railway_environment="develop",
            target_railway_environment="production",
            include_target=True,
        )

    assert context.source_service == "myapp-develop"
    assert context.target_service == "myapp-production"
    assert context.source_runtime_variables == {"DEBUG": "false"}
    assert context.target_runtime_variables == {"DEBUG": "true"}
    assert mocked_fetch.call_args_list == [
        call(
            service="myapp-develop",
            railway_environment="develop",
            role="source",
        ),
        call(
            service="myapp-production",
            railway_environment="production",
            role="target",
        ),
    ]


def test_manage_overrides_select_expected_settings_modules() -> None:
    context = _context()

    local_overrides = dr_commands._build_manage_overrides(
        context.identity,
        "local",
        runtime_variables={"DEBUG": "1"},
    )
    source_overrides = dr_commands._source_manage_overrides(context)
    target_overrides = dr_commands._target_manage_overrides(
        context,
        allow_restore=True,
    )

    assert local_overrides == {
        "DEBUG": "1",
        "DJANGO_SETTINGS_MODULE": "myapp.settings.local",
        "QUICKSCALE_ENVIRONMENT": "local",
    }
    assert source_overrides["DJANGO_SETTINGS_MODULE"] == "myapp.settings.local"
    assert target_overrides["DJANGO_SETTINGS_MODULE"] == "myapp.settings.production"
    assert target_overrides["QUICKSCALE_BACKUPS_ALLOW_RESTORE"] == "true"


def test_run_backend_container_command_handles_success_and_error_paths() -> None:
    with (
        patch(
            "quickscale_cli.commands.dr_commands.get_backend_container_name",
            return_value="backend",
        ),
        patch(
            "quickscale_cli.commands.dr_commands.subprocess.run",
            return_value=SimpleNamespace(returncode=0, stdout="ok", stderr=""),
        ) as mocked_run,
    ):
        output = dr_commands._run_backend_container_command(
            ["python", "manage.py", "check"],
            env_overrides={"B": "2", "A": "1"},
        )

    assert output == "ok"
    mocked_run.assert_called_once_with(
        [
            "docker",
            "exec",
            "-e",
            "A=1",
            "-e",
            "B=2",
            "backend",
            "python",
            "manage.py",
            "check",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    with (
        patch(
            "quickscale_cli.commands.dr_commands.get_backend_container_name",
            return_value="backend",
        ),
        patch(
            "quickscale_cli.commands.dr_commands.subprocess.run",
            return_value=SimpleNamespace(
                returncode=1,
                stdout="",
                stderr="Error response from daemon: No such container: backend",
            ),
        ),
    ):
        with pytest.raises(
            click.ClickException, match="Backend container is not running"
        ):
            dr_commands._run_backend_container_command(["env"])

    with (
        patch(
            "quickscale_cli.commands.dr_commands.get_backend_container_name",
            return_value="backend",
        ),
        patch(
            "quickscale_cli.commands.dr_commands.subprocess.run",
            return_value=SimpleNamespace(
                returncode=1,
                stdout="",
                stderr="permission denied",
            ),
        ),
    ):
        with pytest.raises(
            click.ClickException,
            match="Backend container command failed: python manage.py check :: permission denied",
        ):
            dr_commands._run_backend_container_command(["python", "manage.py", "check"])


def test_run_manage_json_validates_json_payload_shape() -> None:
    with patch(
        "quickscale_cli.commands.dr_commands._run_backend_container_command",
        return_value='{"status": "ready"}',
    ):
        assert dr_commands._run_manage_json(
            ["backups_create", "--json"],
            env_overrides={},
        ) == {"status": "ready"}

    with patch(
        "quickscale_cli.commands.dr_commands._run_backend_container_command",
        return_value="not-json",
    ):
        with pytest.raises(
            click.ClickException,
            match="Expected JSON output from manage.py backups_create --json",
        ):
            dr_commands._run_manage_json(["backups_create", "--json"], env_overrides={})

    with patch(
        "quickscale_cli.commands.dr_commands._run_backend_container_command",
        return_value='["ready"]',
    ):
        with pytest.raises(
            click.ClickException,
            match="Expected JSON object output from manage.py backups_create --json",
        ):
            dr_commands._run_manage_json(["backups_create", "--json"], env_overrides={})


def test_manage_wrappers_forward_expected_arguments() -> None:
    context = _context()

    with (
        patch.object(
            dr_commands,
            "_source_manage_overrides",
            return_value={"SOURCE": "1"},
        ),
        patch.object(
            dr_commands,
            "_run_manage_json",
            return_value={"status": "ready"},
        ) as mocked_manage,
    ):
        snapshot_report = dr_commands._fetch_snapshot_report(
            context,
            snapshot_id="snap-123",
            sidecar_payloads=(
                "promotion-verification.json",
                "release-metadata.json",
            ),
        )
        capture_report = dr_commands._capture_snapshot_report(context)
        verification_report = dr_commands._record_verification(
            context,
            snapshot_id="snap-123",
            phase="plan",
            status="ready",
            payload={"database": {"status": "ready"}},
        )
        pin_report = dr_commands._set_rollback_pin(
            context,
            snapshot_id="snap-123",
            hours=6,
            reason="release window",
        )

    assert snapshot_report == {"status": "ready"}
    assert capture_report == {"status": "ready"}
    assert verification_report == {"status": "ready"}
    assert pin_report == {"status": "ready"}
    assert mocked_manage.call_args_list[0] == call(
        [
            "backups_report",
            "snap-123",
            "--json",
            "--sidecar-payload",
            "promotion-verification.json",
            "--sidecar-payload",
            "release-metadata.json",
        ],
        env_overrides={"SOURCE": "1"},
    )
    assert mocked_manage.call_args_list[1] == call(
        ["backups_create", "--json"],
        env_overrides={"SOURCE": "1"},
    )
    assert mocked_manage.call_args_list[2] == call(
        [
            "backups_record_verification",
            "snap-123",
            "--route",
            "local-to-railway-develop",
            "--phase",
            "plan",
            "--status",
            "ready",
            "--payload-json",
            '{"database": {"status": "ready"}}',
            "--json",
        ],
        env_overrides={"SOURCE": "1"},
    )
    assert mocked_manage.call_args_list[3] == call(
        [
            "backups_pin",
            "snap-123",
            "--hours",
            "6",
            "--reason",
            "release window",
            "--json",
        ],
        env_overrides={"SOURCE": "1"},
    )

    with (
        patch.object(
            dr_commands,
            "_source_manage_overrides",
            return_value={"DEBUG": "false"},
        ),
        patch.object(
            dr_commands,
            "_run_manage_json",
            return_value={"status": "ready"},
        ) as mocked_manage,
    ):
        result = dr_commands._run_media_sync(
            replace(context, target_runtime_variables={"MEDIA_ROOT": "/tmp/media"}),
            snapshot_id="snap-123",
            dry_run=True,
        )

    assert result == {"status": "ready"}
    assert dr_commands._prefix_target_runtime_variables({"DEBUG": "true"}) == {
        "QUICKSCALE_DR_TARGET_DEBUG": "true"
    }
    mocked_manage.assert_called_once_with(
        ["backups_sync_media", "snap-123", "--json", "--dry-run"],
        env_overrides={
            "DEBUG": "false",
            "QUICKSCALE_DR_TARGET_MEDIA_ROOT": "/tmp/media",
            "QUICKSCALE_DR_TARGET_ROUTE_KIND": "railway",
        },
    )


def test_build_database_plan_validates_restore_metadata_and_returns_restore_payload() -> (
    None
):
    context = _context()

    with (
        patch.object(
            dr_commands,
            "_target_manage_overrides",
            return_value={"DJANGO_SETTINGS_MODULE": "myapp.settings.production"},
        ) as mocked_overrides,
        patch.object(
            dr_commands,
            "_run_backend_container_command",
            return_value="Restore validation completed successfully (dry run).\n",
        ) as mocked_backend,
    ):
        plan = dr_commands._build_database_plan(
            context,
            {
                "snapshot_id": "snap-123",
                "confirmation_value": "db.dump",
                "authoritative_dump": {
                    "local_path": "/tmp/db.dump",
                    "restore_scope": "local_only",
                    "restore_scope_label": "Local only",
                },
            },
        )

    assert plan == {
        "status": "ready",
        "message": "Restore validation completed successfully (dry run).",
        "restore_file": "/tmp/db.dump",
        "confirmation_value": "db.dump",
        "restore_scope": "local_only",
        "restore_scope_label": "Local only",
    }
    mocked_overrides.assert_called_once_with(context)
    mocked_backend.assert_called_once_with(
        [
            "python",
            "manage.py",
            "backups_restore",
            "--file",
            "/tmp/db.dump",
            "--confirm",
            "db.dump",
            "--dry-run",
        ],
        env_overrides={"DJANGO_SETTINGS_MODULE": "myapp.settings.production"},
    )

    with pytest.raises(
        click.ClickException,
        match="missing its authoritative restore file metadata",
    ):
        dr_commands._build_database_plan(
            context,
            {
                "snapshot_id": "snap-123",
                "confirmation_value": "",
                "authoritative_dump": {},
            },
        )


def test_load_source_live_variables_and_classify_env_var_cover_expected_cases() -> None:
    local_context = _context()

    with patch.object(
        dr_commands,
        "_run_backend_container_command",
        return_value="DEBUG=true\nINVALID\nBLOG_THEME=midnight\nDATABASE_URL=postgres://db\n",
    ):
        assert dr_commands._load_source_live_variables(local_context) == {
            "DEBUG": "true",
            "BLOG_THEME": "midnight",
            "DATABASE_URL": "postgres://db",
        }

    railway_context = replace(
        _context(route="railway-develop-to-railway-production"),
        source_runtime_variables={"DEBUG": "false"},
    )
    assert dr_commands._load_source_live_variables(railway_context) == {
        "DEBUG": "false"
    }
    assert dr_commands._classify_env_var("") == ("ignored", "blank name")
    assert dr_commands._classify_env_var("HOME") == (
        "ignored",
        "shell/runtime noise",
    )
    assert dr_commands._classify_env_var("POETRY_CACHE_DIR") == (
        "ignored",
        "shell/runtime noise",
    )
    assert dr_commands._classify_env_var("DATABASE_URL") == (
        "manual",
        "provider-owned or target-owned variable",
    )
    assert dr_commands._classify_env_var("AWS_ACCESS_KEY_ID") == (
        "manual",
        "provider-owned or target-owned variable",
    )
    assert dr_commands._classify_env_var("PUBLIC_BASE_URL") == (
        "manual",
        "sensitive or environment-specific variable",
    )
    assert dr_commands._classify_env_var("DEBUG") == (
        "portable",
        "portable variable",
    )
    assert dr_commands._classify_env_var("BLOG_THEME") == (
        "portable",
        "portable variable",
    )
    assert dr_commands._classify_env_var("UNLISTED_VAR") == (
        "manual",
        "outside the conservative portable allowlist",
    )


def test_build_env_sync_plan_handles_unavailable_and_manual_required_states() -> None:
    context = _context()

    unavailable = dr_commands._build_env_sync_plan(context, {"sidecar_payloads": {}})
    not_ready = dr_commands._build_env_sync_plan(
        context,
        {
            "sidecar_payloads": {
                "env-var-manifest.json": {
                    "status": "failed",
                    "reason": "capture failed",
                }
            }
        },
    )

    with patch.object(
        dr_commands,
        "_load_source_live_variables",
        return_value={
            "DEBUG": "true",
            "BLOG_THEME": "midnight",
            "FORMS_SITE_NAME": "MyApp",
            "DATABASE_URL": "postgres://source",
        },
    ):
        env_sync_plan = dr_commands._build_env_sync_plan(
            replace(
                context,
                target_runtime_variables={
                    "BLOG_THEME": "sunrise",
                    "FORMS_SITE_NAME": "MyApp",
                },
            ),
            {
                "sidecar_payloads": {
                    "env-var-manifest.json": {
                        "status": "ready",
                        "names": [
                            "HOME",
                            "DEBUG",
                            "BLOG_THEME",
                            "FORMS_SITE_NAME",
                            "DATABASE_URL",
                        ],
                    }
                }
            },
        )

    assert unavailable["status"] == "unavailable"
    assert unavailable["reason"] == (
        "env-var sidecar payload was not requested or could not be parsed"
    )
    assert not_ready["status"] == "unavailable"
    assert not_ready["reason"] == "capture failed"
    assert env_sync_plan == {
        "status": "manual_required",
        "portable_candidates": ["DEBUG"],
        "portable_existing": ["FORMS_SITE_NAME"],
        "portable_conflicts": [
            {
                "name": "BLOG_THEME",
                "reason": "target already defines a different value",
            }
        ],
        "manual_requirements": [
            {
                "name": "DATABASE_URL",
                "reason": "provider-owned or target-owned variable",
                "target_has_value": False,
            }
        ],
        "ignored_count": 1,
    }


def test_build_env_sync_plan_keeps_destructive_restore_gate_manual_only() -> None:
    context = _context()

    with patch.object(
        dr_commands,
        "_load_source_live_variables",
        return_value={"QUICKSCALE_BACKUPS_ALLOW_RESTORE": "true"},
    ):
        env_sync_plan = dr_commands._build_env_sync_plan(
            context,
            {
                "sidecar_payloads": {
                    "env-var-manifest.json": {
                        "status": "ready",
                        "names": ["QUICKSCALE_BACKUPS_ALLOW_RESTORE"],
                    }
                }
            },
        )

    assert env_sync_plan == {
        "status": "manual_required",
        "portable_candidates": [],
        "portable_existing": [],
        "portable_conflicts": [],
        "manual_requirements": [
            {
                "name": "QUICKSCALE_BACKUPS_ALLOW_RESTORE",
                "reason": "destructive restore gate must be set manually",
                "target_has_value": False,
            }
        ],
        "ignored_count": 0,
    }


def test_build_plan_payload_and_execute_portable_env_sync_cover_manual_and_partial_outcomes() -> (
    None
):
    context = _context()
    plan_payload = dr_commands._build_plan_payload(
        context,
        {
            "snapshot_id": "snap-123",
            "sidecar_payloads": {
                "release-metadata.json": {
                    "app_version": "0.82.0",
                    "git_sha": "abc123",
                    "module_versions": {"backups": "0.77.0"},
                }
            },
        },
        database_plan={"status": "ready"},
        media_plan={"status": "ready"},
        env_sync_plan={
            "status": "manual_required",
            "portable_candidates": [],
            "portable_existing": [],
            "portable_conflicts": [{"name": "BLOG_THEME"}],
            "manual_requirements": [{"name": "DATABASE_URL"}],
            "ignored_count": 0,
        },
    )

    with patch.object(
        dr_commands,
        "_load_source_live_variables",
        return_value={},
    ):
        skipped_result = dr_commands._execute_portable_env_sync(
            context,
            {
                "portable_candidates": [],
                "manual_requirements": [{"name": "DATABASE_URL"}],
                "portable_conflicts": [],
            },
        )

    with (
        patch.object(
            dr_commands,
            "_load_source_live_variables",
            return_value={"DEBUG": "true", "BLOG_THEME": "midnight"},
        ),
        patch.object(
            dr_commands,
            "set_railway_variables_batch",
            return_value=(False, ["BLOG_THEME"]),
        ) as mocked_set,
    ):
        partial_result = dr_commands._execute_portable_env_sync(
            context,
            {
                "portable_candidates": ["DEBUG", "BLOG_THEME"],
                "manual_requirements": [],
                "portable_conflicts": [],
            },
        )

    assert plan_payload["status"] == "manual_required"
    assert plan_payload["manual_actions"] == ["BLOG_THEME", "DATABASE_URL"]
    assert plan_payload["release_metadata"]["module_versions"] == {"backups": "0.77.0"}
    assert skipped_result == {
        "status": "manual_required",
        "copied": [],
        "failed": [],
        "manual_requirements": [{"name": "DATABASE_URL"}],
        "portable_conflicts": [],
    }
    assert partial_result == {
        "status": "partial",
        "copied": ["DEBUG"],
        "failed": ["BLOG_THEME"],
        "manual_requirements": [],
        "portable_conflicts": [],
    }
    mocked_set.assert_called_once_with(
        {"DEBUG": "true", "BLOG_THEME": "midnight"},
        service="myapp-target",
        environment=None,
    )


def test_execute_database_restore_runs_production_flow_and_missing_metadata_raises() -> (
    None
):
    production_context = replace(
        _context(route="railway-develop-to-railway-production"),
        target_service="myapp-production",
    )

    with (
        patch.object(
            dr_commands,
            "_target_manage_overrides",
            side_effect=[
                {"QUICKSCALE_BACKUPS_ALLOW_RESTORE": "true"},
                {"QUICKSCALE_ENVIRONMENT": "railway-production"},
                {"QUICKSCALE_ENVIRONMENT": "railway-production"},
            ],
        ) as mocked_overrides,
        patch.object(
            dr_commands,
            "_run_backend_container_command",
            side_effect=[
                "restore complete\n",
                "migrate complete\n",
                "check complete\n",
            ],
        ) as mocked_backend,
    ):
        restore_result = dr_commands._execute_database_restore(
            production_context,
            {
                "snapshot_id": "snap-123",
                "confirmation_value": "db.dump",
                "authoritative_dump": {"local_path": "/tmp/db.dump"},
            },
        )

    assert restore_result == {
        "status": "completed",
        "restore_message": "restore complete",
        "migrate_message": "migrate complete",
        "check_message": "check complete",
        "confirmation_value": "db.dump",
        "restore_file": "/tmp/db.dump",
    }
    assert mocked_overrides.call_args_list == [
        call(production_context, allow_restore=True),
        call(production_context),
        call(production_context),
    ]
    assert mocked_backend.call_args_list[0] == call(
        [
            "python",
            "manage.py",
            "backups_restore",
            "--file",
            "/tmp/db.dump",
            "--confirm",
            "db.dump",
            "--allow-production",
        ],
        env_overrides={"QUICKSCALE_BACKUPS_ALLOW_RESTORE": "true"},
    )

    with pytest.raises(
        click.ClickException,
        match="missing its authoritative restore file metadata",
    ):
        dr_commands._execute_database_restore(
            production_context,
            {
                "snapshot_id": "snap-123",
                "confirmation_value": "",
                "authoritative_dump": {},
            },
        )


def test_build_route_report_and_echo_helpers_render_optional_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    context = replace(
        _context(route="railway-develop-to-railway-production"),
        source_service="myapp-develop",
    )
    route_report = dr_commands._build_route_report(
        {
            "snapshot_id": "snap-123",
            "status": "ready",
            "source_environment": "local",
            "sidecar_payloads": {
                "promotion-verification.json": {
                    "reports": [
                        {
                            "route": "local-to-railway-develop",
                            "phase": "plan",
                            "status": "manual_required",
                        },
                        {
                            "route": "other-route",
                            "phase": "plan",
                            "status": "ignored",
                        },
                        {
                            "route": "local-to-railway-develop",
                            "phase": "execute",
                            "status": "completed",
                        },
                        {
                            "route": "local-to-railway-develop",
                            "phase": "",
                            "status": "ignored",
                        },
                    ]
                }
            },
        },
        route="local-to-railway-develop",
    )

    dr_commands._echo_capture_summary(
        context,
        {
            "snapshot_id": "snap-123",
            "source_environment": "railway-develop",
            "status": "ready",
            "authoritative_dump": {"filename": "db.dump"},
        },
    )
    dr_commands._echo_execute_summary(
        {
            "route": "local-to-railway-develop",
            "snapshot_id": "snap-123",
            "status": "partial",
            "rollback_pin": {"expires_at": "2026-04-06T18:00:00+00:00"},
            "env_vars": {"status": "manual_required"},
            "database": {"status": "skipped"},
            "media": {"status": "completed"},
        }
    )
    dr_commands._echo_report_summary(
        {
            "route": "local-to-railway-develop",
            "snapshot_id": "snap-123",
            "snapshot_status": "ready",
            "latest_records": {},
        }
    )

    captured = capsys.readouterr().out

    assert route_report["verification_records"] == [
        {
            "route": "local-to-railway-develop",
            "phase": "plan",
            "status": "manual_required",
        },
        {
            "route": "local-to-railway-develop",
            "phase": "execute",
            "status": "completed",
        },
        {
            "route": "local-to-railway-develop",
            "phase": "",
            "status": "ignored",
        },
    ]
    assert route_report["latest_records"] == {
        "plan": {
            "route": "local-to-railway-develop",
            "phase": "plan",
            "status": "manual_required",
        },
        "execute": {
            "route": "local-to-railway-develop",
            "phase": "execute",
            "status": "completed",
        },
    }
    assert "Source service: myapp-develop" in captured
    assert "Rollback pin expires at: 2026-04-06T18:00:00+00:00" in captured
    assert "No plan or execute records are stored for this route yet." in captured
