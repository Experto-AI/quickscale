"""Disaster-recovery and environment-migration command surface.

F5.3: All DR operations now call the explicit typed adapter
(``quickscale_core.dr_engine.adapter``) through the thin
``quickscale_backups_dr_adapter_call`` management command bridge, replacing the previous
docker-exec/management-command/env-var/stdout-JSON protocol.

The implementation lives in private sibling modules grouped by concern
(``_dr_context``, ``_dr_adapter``, ``_dr_env_sync``, ``_dr_report``); this
module owns the public command surface and re-exports every name that
previously lived here (Module Conventions rule 28), so existing
``quickscale_cli.commands.dr_commands`` imports and test patch targets keep
working unchanged.
"""

from __future__ import annotations

from copy import deepcopy as deepcopy
import json as json
import subprocess as subprocess
from dataclasses import dataclass as dataclass
from pathlib import Path as Path
from typing import Any as Any

import click as click

from quickscale_cli.commands.development_commands import (
    _validate_project_and_docker as _validate_project_and_docker,
)
from quickscale_cli.commands.dr_output import (
    _echo_capture_summary as _echo_capture_summary,
    _echo_execute_summary as _echo_execute_summary,
    _echo_plan_summary as _echo_plan_summary,
    _echo_report_summary as _echo_report_summary,
)
from quickscale_core.contracts.module_options import (
    get_env_var_portability as get_env_var_portability,
)
from quickscale_core.utils.theme_validation import (
    ThemeValidationError as ThemeValidationError,
    validate_theme_preflight as validate_theme_preflight,
)
from quickscale_core.dr_engine.primitives import (
    _ENV_VAR_MANIFEST_FILENAME as _ENV_VAR_MANIFEST_FILENAME,
    _PROMOTION_VERIFICATION_FILENAME as _PROMOTION_VERIFICATION_FILENAME,
    _RELEASE_METADATA_FILENAME as _RELEASE_METADATA_FILENAME,
)
from quickscale_core.utils.project_identity import (
    ProjectIdentity as ProjectIdentity,
    resolve_project_identity as resolve_project_identity,
)
from quickscale_cli.utils.project_manager import (
    get_backend_container_name as get_backend_container_name,
)
from quickscale_cli.utils.railway_utils import (
    get_railway_variables as get_railway_variables,
    set_railway_variables_batch as set_railway_variables_batch,
)
from quickscale_cli.commands._dr_context import (
    DisasterRecoveryContext as DisasterRecoveryContext,
    DrRouteSpec as DrRouteSpec,
    _DR_ROUTES as _DR_ROUTES,
    _ROUTE_CHOICE as _ROUTE_CHOICE,
    _build_context as _build_context,
    _fetch_railway_runtime_variables as _fetch_railway_runtime_variables,
    _resolve_project_identity as _resolve_project_identity,
    _resolve_route as _resolve_route,
    _validate_route_services as _validate_route_services,
)
from quickscale_cli.commands._dr_adapter import (
    _build_database_plan as _build_database_plan,
    _call_adapter as _call_adapter,
    _capture_snapshot_report as _capture_snapshot_report,
    _execute_database_restore as _execute_database_restore,
    _fetch_snapshot_report as _fetch_snapshot_report,
    _load_source_live_variables as _load_source_live_variables,
    _record_verification as _record_verification,
    _run_media_sync as _run_media_sync,
    _set_rollback_pin as _set_rollback_pin,
)
from quickscale_cli.commands._dr_env_sync import (
    _build_env_sync_plan as _build_env_sync_plan,
    _classify_env_var as _classify_env_var,
    _execute_portable_env_sync as _execute_portable_env_sync,
)
from quickscale_cli.commands._dr_report import (
    _DR_EXECUTE_RETRYABLE_STATUSES as _DR_EXECUTE_RETRYABLE_STATUSES,
    _DR_EXECUTE_SURFACES as _DR_EXECUTE_SURFACES,
    _build_plan_payload as _build_plan_payload,
    _build_route_report as _build_route_report,
    _echo_json as _echo_json,
    _latest_execute_surface_payloads as _latest_execute_surface_payloads,
    _latest_execute_surface_statuses as _latest_execute_surface_statuses,
    _latest_route_phase_record as _latest_route_phase_record,
    _resolve_execute_surface_selection as _resolve_execute_surface_selection,
    _surface_result_requires_follow_up as _surface_result_requires_follow_up,
)

# Sidecar filename constant used by env-sync planning (maps to
# _ENV_VAR_MANIFEST_FILENAME in primitives.py).
_ENV_MANIFEST_FILENAME = _ENV_VAR_MANIFEST_FILENAME


@click.group()
def dr() -> None:
    """Disaster-recovery and environment-migration workflows."""


@dr.command()
@click.option("--route", type=_ROUTE_CHOICE, required=True)
@click.option("--source-service")
@click.option("--source-railway-environment")
@click.option("--resume", "resume_snapshot_id")
@click.option("--json", "as_json", is_flag=True)
def capture(
    route: str,
    source_service: str | None,
    source_railway_environment: str | None,
    resume_snapshot_id: str | None,
    as_json: bool,
) -> None:
    """Capture a stored snapshot for one DR route source."""
    context = _build_context(
        route,
        source_service=source_service,
        target_service=None,
        source_railway_environment=source_railway_environment,
        target_railway_environment=None,
        include_target=False,
    )
    snapshot_report = _capture_snapshot_report(
        context,
        resume_snapshot_id=str(resume_snapshot_id or "").strip() or None,
    )
    if as_json:
        _echo_json({"route": context.route.label, "snapshot": snapshot_report})
        return
    _echo_capture_summary(context, snapshot_report)


@dr.command()
@click.option("--route", type=_ROUTE_CHOICE, required=True)
@click.option("--snapshot-id", required=True)
@click.option("--source-service")
@click.option("--target-service")
@click.option("--source-railway-environment")
@click.option("--target-railway-environment")
@click.option("--json", "as_json", is_flag=True)
def plan(
    route: str,
    snapshot_id: str,
    source_service: str | None,
    target_service: str | None,
    source_railway_environment: str | None,
    target_railway_environment: str | None,
    as_json: bool,
) -> None:
    """Build and persist a dry-run DR plan for one stored snapshot."""
    context = _build_context(
        route,
        source_service=source_service,
        target_service=target_service,
        source_railway_environment=source_railway_environment,
        target_railway_environment=target_railway_environment,
        include_target=True,
    )
    snapshot_report = _fetch_snapshot_report(
        context,
        snapshot_id=snapshot_id,
        sidecar_payloads=(
            _ENV_MANIFEST_FILENAME,
            _PROMOTION_VERIFICATION_FILENAME,
            _RELEASE_METADATA_FILENAME,
        ),
    )
    database_plan = _build_database_plan(context, snapshot_report)
    media_plan = _run_media_sync(context, snapshot_id=snapshot_id, dry_run=True)
    env_sync_plan = _build_env_sync_plan(context, snapshot_report)
    plan_payload = _build_plan_payload(
        context,
        snapshot_report,
        database_plan=database_plan,
        media_plan=media_plan,
        env_sync_plan=env_sync_plan,
    )
    _record_verification(
        context,
        snapshot_id=snapshot_id,
        phase="plan",
        status=plan_payload["status"],
        payload=plan_payload,
    )
    if as_json:
        _echo_json(plan_payload)
        return
    _echo_plan_summary(plan_payload)


@dr.command()
@click.option("--route", type=_ROUTE_CHOICE, required=True)
@click.option("--snapshot-id", required=True)
@click.option("--source-service")
@click.option("--target-service")
@click.option("--source-railway-environment")
@click.option("--target-railway-environment")
@click.option("--database", is_flag=True)
@click.option("--media", is_flag=True)
@click.option("--env-vars", is_flag=True)
@click.option("--rollback-pin-hours", type=int)
@click.option("--rollback-pin-reason")
@click.option("--resume", is_flag=True)
@click.option("--json", "as_json", is_flag=True)
def execute(
    route: str,
    snapshot_id: str,
    source_service: str | None,
    target_service: str | None,
    source_railway_environment: str | None,
    target_railway_environment: str | None,
    database: bool,
    media: bool,
    env_vars: bool,
    rollback_pin_hours: int | None,
    rollback_pin_reason: str | None,
    resume: bool,
    as_json: bool,
) -> None:
    """Execute selected DR surfaces for one stored snapshot."""
    if not any((database, media, env_vars)) and not resume:
        raise click.ClickException(
            "Choose at least one operational surface: --database, --media, or --env-vars."
        )

    context = _build_context(
        route,
        source_service=source_service,
        target_service=target_service,
        source_railway_environment=source_railway_environment,
        target_railway_environment=target_railway_environment,
        include_target=True,
    )
    if context.route.involves_production() and not resume:
        if rollback_pin_hours is None or not str(rollback_pin_reason or "").strip():
            raise click.ClickException(
                "Routes involving Railway production require --rollback-pin-hours and --rollback-pin-reason before execution."
            )

    snapshot_report = _fetch_snapshot_report(
        context,
        snapshot_id=snapshot_id,
        sidecar_payloads=(
            _ENV_MANIFEST_FILENAME,
            _PROMOTION_VERIFICATION_FILENAME,
            _RELEASE_METADATA_FILENAME,
        ),
    )
    latest_execute_record = (
        _latest_route_phase_record(
            snapshot_report,
            route=context.route.label,
            phase="execute",
        )
        if resume
        else None
    )
    if resume and latest_execute_record is None:
        raise click.ClickException(
            "Cannot resume execute because no prior execute record is stored for this route and snapshot."
        )
    selected_surfaces = _resolve_execute_surface_selection(
        latest_execute_record=latest_execute_record,
        database=database,
        media=media,
        env_vars=env_vars,
        resume=resume,
    )

    rollback_pin_payload = snapshot_report.get("rollback_pin")
    existing_rollback_pin = (
        rollback_pin_payload if isinstance(rollback_pin_payload, dict) else None
    )
    if context.route.involves_production():
        rollback_pin_active = bool(
            existing_rollback_pin is not None and existing_rollback_pin.get("active")
        )
        if resume and (
            rollback_pin_hours is None or not str(rollback_pin_reason or "").strip()
        ):
            if not rollback_pin_active:
                raise click.ClickException(
                    "Routes involving Railway production require --rollback-pin-hours and --rollback-pin-reason before execution."
                )

    env_sync_plan = _build_env_sync_plan(context, snapshot_report)

    rollback_pin: dict[str, Any] | None = existing_rollback_pin
    if rollback_pin_hours is not None and str(rollback_pin_reason or "").strip():
        rollback_report = _set_rollback_pin(
            context,
            snapshot_id=snapshot_id,
            hours=rollback_pin_hours,
            reason=str(rollback_pin_reason),
        )
        rollback_pin = rollback_report.get("rollback_pin")

    execute_payload: dict[str, Any] = {
        "status": "completed",
        "snapshot_id": snapshot_id,
        "route": context.route.label,
        "source": {
            "environment": context.route.source_environment,
            "service": context.source_service,
            "railway_environment": context.source_railway_environment,
        },
        "target": {
            "environment": context.route.target_environment,
            "service": context.target_service,
            "railway_environment": context.target_railway_environment,
        },
        "rollback_pin": rollback_pin,
        "env_vars": {"status": "skipped"},
        "database": {"status": "skipped"},
        "media": {"status": "skipped"},
    }
    execute_payload.update(_latest_execute_surface_payloads(latest_execute_record))

    latest_surface_statuses = _latest_execute_surface_statuses(latest_execute_record)
    surface_failure = False
    for surface_name in _DR_EXECUTE_SURFACES:
        if surface_name not in selected_surfaces:
            continue

        if surface_failure:
            execute_payload[surface_name] = {
                "status": "incomplete",
                "reason": "not attempted because an earlier selected surface failed",
            }
            continue

        if resume and latest_surface_statuses.get(surface_name) == "completed":
            execute_payload[surface_name] = {
                "status": "skipped",
                "reason": "already completed in the latest execute record",
            }
            continue

        try:
            if surface_name == "env_vars":
                execute_payload[surface_name] = _execute_portable_env_sync(
                    context,
                    env_sync_plan,
                )
            elif surface_name == "database":
                execute_payload[surface_name] = _execute_database_restore(
                    context,
                    snapshot_report,
                )
            else:
                execute_payload[surface_name] = _run_media_sync(
                    context,
                    snapshot_id=snapshot_id,
                    dry_run=False,
                )
        except click.ClickException as exc:
            execute_payload[surface_name] = {
                "status": "failed",
                "error": str(exc),
                "error_type": exc.__class__.__name__,
            }
            surface_failure = True
        except Exception as exc:
            execute_payload[surface_name] = {
                "status": "failed",
                "error": str(exc),
                "error_type": exc.__class__.__name__,
            }
            surface_failure = True

    if any(
        _surface_result_requires_follow_up(surface)
        for surface in (
            execute_payload["env_vars"],
            execute_payload["database"],
            execute_payload["media"],
        )
        if isinstance(surface, dict)
    ):
        execute_payload["status"] = "partial"

    _record_verification(
        context,
        snapshot_id=snapshot_id,
        phase="execute",
        status=execute_payload["status"],
        payload=execute_payload,
    )
    if as_json:
        _echo_json(execute_payload)
        return
    _echo_execute_summary(execute_payload)


@dr.command()
@click.option("--route", type=_ROUTE_CHOICE, required=True)
@click.option("--snapshot-id", required=True)
@click.option("--source-service")
@click.option("--source-railway-environment")
@click.option("--json", "as_json", is_flag=True)
def report(
    route: str,
    snapshot_id: str,
    source_service: str | None,
    source_railway_environment: str | None,
    as_json: bool,
) -> None:
    """Show the stored plan/execute report state for one route and snapshot."""
    context = _build_context(
        route,
        source_service=source_service,
        target_service=None,
        source_railway_environment=source_railway_environment,
        target_railway_environment=None,
        include_target=False,
    )
    snapshot_report = _fetch_snapshot_report(
        context,
        snapshot_id=snapshot_id,
        sidecar_payloads=(_PROMOTION_VERIFICATION_FILENAME,),
    )
    route_report = _build_route_report(snapshot_report, route=context.route.label)
    if as_json:
        _echo_json(route_report)
        return
    _echo_report_summary(route_report)
