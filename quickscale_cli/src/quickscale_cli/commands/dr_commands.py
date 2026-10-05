"""Disaster-recovery and environment-migration command surface.

F5.3: All DR operations now call the explicit typed adapter
(``quickscale_core.dr_engine.adapter``) through the thin
``quickscale_backups_dr_adapter_call`` management command bridge, replacing the previous
docker-exec/management-command/env-var/stdout-JSON protocol.

The implementation lives in private sibling modules grouped by concern
(``_dr_context``, ``_dr_adapter``, ``_dr_env_sync``, ``_dr_report``); this module owns the public command surface, re-exports public names for
unchanged import paths, and resolves collaborators through the sibling modules
that define them (decisions.md, Split-Facade Seams).
"""

from __future__ import annotations

from typing import Any

import click as click

from quickscale_core.contracts.module_options import (
    get_env_var_portability as get_env_var_portability,
)
from quickscale_core.utils.theme_validation import (
    ThemeValidationError as ThemeValidationError,
    validate_theme_preflight as validate_theme_preflight,
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
)
import quickscale_cli.commands.dr_output as _dr_output
import quickscale_core.dr_engine.primitives as _primitives
import quickscale_cli.commands._dr_context as _dr_context
import quickscale_cli.commands._dr_adapter as _dr_adapter
import quickscale_cli.commands._dr_env_sync as _dr_env_sync
import quickscale_cli.commands._dr_report as _dr_report

# Sidecar filename constant used by env-sync planning (maps to
# _ENV_VAR_MANIFEST_FILENAME in primitives.py).
_ENV_MANIFEST_FILENAME = _primitives._ENV_VAR_MANIFEST_FILENAME


@click.group()
def dr() -> None:
    """Disaster-recovery and environment-migration workflows."""


@dr.command()
@click.option("--route", type=_dr_context._ROUTE_CHOICE, required=True)
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
    context = _dr_context._build_context(
        route,
        source_service=source_service,
        target_service=None,
        source_railway_environment=source_railway_environment,
        target_railway_environment=None,
        include_target=False,
    )
    snapshot_report = _dr_adapter._capture_snapshot_report(
        context,
        resume_snapshot_id=str(resume_snapshot_id or "").strip() or None,
    )
    if as_json:
        _dr_report._echo_json(
            {"route": context.route.label, "snapshot": snapshot_report}
        )
        return
    _dr_output._echo_capture_summary(context, snapshot_report)


@dr.command()
@click.option("--route", type=_dr_context._ROUTE_CHOICE, required=True)
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
    context = _dr_context._build_context(
        route,
        source_service=source_service,
        target_service=target_service,
        source_railway_environment=source_railway_environment,
        target_railway_environment=target_railway_environment,
        include_target=True,
    )
    snapshot_report = _dr_adapter._fetch_snapshot_report(
        context,
        snapshot_id=snapshot_id,
        sidecar_payloads=(
            _ENV_MANIFEST_FILENAME,
            _primitives._PROMOTION_VERIFICATION_FILENAME,
            _primitives._RELEASE_METADATA_FILENAME,
        ),
    )
    database_plan = _dr_adapter._build_database_plan(context, snapshot_report)
    media_plan = _dr_adapter._run_media_sync(
        context, snapshot_id=snapshot_id, dry_run=True
    )
    env_sync_plan = _dr_env_sync._build_env_sync_plan(context, snapshot_report)
    plan_payload = _dr_report._build_plan_payload(
        context,
        snapshot_report,
        database_plan=database_plan,
        media_plan=media_plan,
        env_sync_plan=env_sync_plan,
    )
    _dr_adapter._record_verification(
        context,
        snapshot_id=snapshot_id,
        phase="plan",
        status=plan_payload["status"],
        payload=plan_payload,
    )
    if as_json:
        _dr_report._echo_json(plan_payload)
        return
    _dr_output._echo_plan_summary(plan_payload)


def _require_execute_surface_selection(
    *, database: bool, media: bool, env_vars: bool, resume: bool
) -> None:
    """Reject an execute invocation that selects no operational surface."""
    if not any((database, media, env_vars)) and not resume:
        raise click.ClickException(
            "Choose at least one operational surface: --database, --media, or --env-vars."
        )


def _require_production_rollback_pin(
    context: Any, *, hours: int | None, reason: str | None, resume: bool
) -> None:
    """Require a rollback pin before executing against a production route."""
    if resume or not context.route.involves_production():
        return
    if hours is not None and str(reason or "").strip():
        return
    raise click.ClickException(
        "Routes involving Railway production require --rollback-pin-hours and --rollback-pin-reason before execution."
    )


def _require_resume_rollback_pin(
    context: Any,
    existing_rollback_pin: dict[str, Any] | None,
    *,
    hours: int | None,
    reason: str | None,
    resume: bool,
) -> None:
    """Require a rollback pin (or an active stored one) when resuming production."""
    if not (context.route.involves_production() and resume):
        return
    if hours is not None and str(reason or "").strip():
        return
    if existing_rollback_pin is not None and existing_rollback_pin.get("active"):
        return
    raise click.ClickException(
        "Routes involving Railway production require --rollback-pin-hours and --rollback-pin-reason before execution."
    )


def _execute_one_surface(
    context: Any,
    surface_name: str,
    *,
    snapshot_id: str,
    snapshot_report: dict[str, Any],
    env_sync_plan: dict[str, Any],
) -> dict[str, Any]:
    """Run one selected DR surface and return its result payload."""
    if surface_name == "env_vars":
        return _dr_env_sync._execute_portable_env_sync(context, env_sync_plan)
    if surface_name == "database":
        return _dr_adapter._execute_database_restore(context, snapshot_report)
    return _dr_adapter._run_media_sync(
        context,
        snapshot_id=snapshot_id,
        dry_run=False,
    )


def _execute_selected_surfaces(
    context: Any,
    *,
    snapshot_id: str,
    snapshot_report: dict[str, Any],
    selected_surfaces: Any,
    latest_execute_record: dict[str, Any] | None,
    env_sync_plan: dict[str, Any],
    resume: bool,
    execute_payload: dict[str, Any],
) -> bool:
    """Run each selected surface in order; True when a selected surface failed."""
    latest_surface_statuses = _dr_report._latest_execute_surface_statuses(
        latest_execute_record
    )
    surface_failure = False
    for surface_name in _dr_report._DR_EXECUTE_SURFACES:
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
            execute_payload[surface_name] = _execute_one_surface(
                context,
                surface_name,
                snapshot_id=snapshot_id,
                snapshot_report=snapshot_report,
                env_sync_plan=env_sync_plan,
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
    return surface_failure


def _mark_partial_execute_payload(execute_payload: dict[str, Any]) -> None:
    """Mark the execute payload partial when a surface needs follow-up."""
    if any(
        _dr_report._surface_result_requires_follow_up(surface)
        for surface in (
            execute_payload["env_vars"],
            execute_payload["database"],
            execute_payload["media"],
        )
        if isinstance(surface, dict)
    ):
        execute_payload["status"] = "partial"


@dr.command()
@click.option("--route", type=_dr_context._ROUTE_CHOICE, required=True)
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
    _require_execute_surface_selection(
        database=database, media=media, env_vars=env_vars, resume=resume
    )

    context = _dr_context._build_context(
        route,
        source_service=source_service,
        target_service=target_service,
        source_railway_environment=source_railway_environment,
        target_railway_environment=target_railway_environment,
        include_target=True,
    )
    _require_production_rollback_pin(
        context,
        hours=rollback_pin_hours,
        reason=rollback_pin_reason,
        resume=resume,
    )

    snapshot_report = _dr_adapter._fetch_snapshot_report(
        context,
        snapshot_id=snapshot_id,
        sidecar_payloads=(
            _ENV_MANIFEST_FILENAME,
            _primitives._PROMOTION_VERIFICATION_FILENAME,
            _primitives._RELEASE_METADATA_FILENAME,
        ),
    )
    latest_execute_record = (
        _dr_report._latest_route_phase_record(
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
    selected_surfaces = _dr_report._resolve_execute_surface_selection(
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
    _require_resume_rollback_pin(
        context,
        existing_rollback_pin,
        hours=rollback_pin_hours,
        reason=rollback_pin_reason,
        resume=resume,
    )

    env_sync_plan = _dr_env_sync._build_env_sync_plan(context, snapshot_report)

    rollback_pin: dict[str, Any] | None = existing_rollback_pin
    if rollback_pin_hours is not None and str(rollback_pin_reason or "").strip():
        rollback_report = _dr_adapter._set_rollback_pin(
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
    execute_payload.update(
        _dr_report._latest_execute_surface_payloads(latest_execute_record)
    )

    _execute_selected_surfaces(
        context,
        snapshot_id=snapshot_id,
        snapshot_report=snapshot_report,
        selected_surfaces=selected_surfaces,
        latest_execute_record=latest_execute_record,
        env_sync_plan=env_sync_plan,
        resume=resume,
        execute_payload=execute_payload,
    )
    _mark_partial_execute_payload(execute_payload)

    _dr_adapter._record_verification(
        context,
        snapshot_id=snapshot_id,
        phase="execute",
        status=execute_payload["status"],
        payload=execute_payload,
    )
    if as_json:
        _dr_report._echo_json(execute_payload)
        return
    _dr_output._echo_execute_summary(execute_payload)


@dr.command()
@click.option("--route", type=_dr_context._ROUTE_CHOICE, required=True)
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
    context = _dr_context._build_context(
        route,
        source_service=source_service,
        target_service=None,
        source_railway_environment=source_railway_environment,
        target_railway_environment=None,
        include_target=False,
    )
    snapshot_report = _dr_adapter._fetch_snapshot_report(
        context,
        snapshot_id=snapshot_id,
        sidecar_payloads=(_primitives._PROMOTION_VERIFICATION_FILENAME,),
    )
    route_report = _dr_report._build_route_report(
        snapshot_report, route=context.route.label
    )
    if as_json:
        _dr_report._echo_json(route_report)
        return
    _dr_output._echo_report_summary(route_report)
