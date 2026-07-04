"""Disaster-recovery and environment-migration command surface.

F5.3: All DR operations now call the explicit typed adapter
(``quickscale_core.dr_engine.adapter``) through the thin
``dr_adapter_call`` management command bridge, replacing the previous
docker-exec/management-command/env-var/stdout-JSON protocol.
"""

from __future__ import annotations

from copy import deepcopy
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click

from quickscale_cli.commands.development_commands import _validate_project_and_docker
from quickscale_core.contracts.module_options import get_env_var_portability
from quickscale_core.dr_engine.primitives import (
    _ENV_VAR_MANIFEST_FILENAME,
    _PROMOTION_VERIFICATION_FILENAME,
    _RELEASE_METADATA_FILENAME,
)
from quickscale_core.utils.project_identity import (
    ProjectIdentity,
    resolve_project_identity,
)
from quickscale_cli.utils.project_manager import get_backend_container_name
from quickscale_cli.utils.railway_utils import (
    get_railway_variables,
    set_railway_variables_batch,
)

# Sidecar filename constant used by env-sync planning (maps to
# _ENV_VAR_MANIFEST_FILENAME in primitives.py).
_ENV_MANIFEST_FILENAME = _ENV_VAR_MANIFEST_FILENAME


@dataclass(frozen=True)
class DrRouteSpec:
    """Immutable route contract for one DR workflow."""

    label: str
    source_kind: str
    source_environment: str
    target_kind: str
    target_environment: str

    def source_requires_service(self) -> bool:
        return self.source_kind == "railway"

    def target_requires_service(self) -> bool:
        return self.target_kind == "railway"

    def involves_production(self) -> bool:
        return "railway-production" in {
            self.source_environment,
            self.target_environment,
        }


@dataclass(frozen=True)
class DisasterRecoveryContext:
    """Resolved route context for one DR command execution."""

    route: DrRouteSpec
    identity: ProjectIdentity
    source_service: str | None
    target_service: str | None
    source_railway_environment: str | None
    target_railway_environment: str | None
    source_runtime_variables: dict[str, str]
    target_runtime_variables: dict[str, str]


_DR_ROUTES: dict[str, DrRouteSpec] = {
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
    "railway-production-to-railway-develop": DrRouteSpec(
        label="railway-production-to-railway-develop",
        source_kind="railway",
        source_environment="railway-production",
        target_kind="railway",
        target_environment="railway-develop",
    ),
}
_ROUTE_CHOICE = click.Choice(tuple(_DR_ROUTES), case_sensitive=True)
_DR_EXECUTE_SURFACES = ("env_vars", "database", "media")
_DR_EXECUTE_RETRYABLE_STATUSES = {
    "failed",
    "incomplete",
    "manual_required",
    "partial",
}


@click.group()
def dr() -> None:
    """Disaster-recovery and environment-migration workflows."""


def _resolve_route(route: str) -> DrRouteSpec:
    return _DR_ROUTES[route]


def _resolve_project_identity() -> ProjectIdentity:
    try:
        return resolve_project_identity(Path.cwd())
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


def _validate_route_services(
    route: DrRouteSpec,
    *,
    source_service: str | None,
    target_service: str | None,
    include_target: bool,
) -> None:
    if route.source_requires_service() and not source_service:
        raise click.ClickException(
            f"Route '{route.label}' requires --source-service for the Railway source."
        )
    if include_target and route.target_requires_service() and not target_service:
        raise click.ClickException(
            f"Route '{route.label}' requires --target-service for the Railway target."
        )


def _fetch_railway_runtime_variables(
    *,
    service: str,
    railway_environment: str | None,
    role: str,
) -> dict[str, str]:
    try:
        variables = get_railway_variables(
            service=service,
            environment=railway_environment,
        )
    except ValueError as exc:
        label = service
        if railway_environment:
            label = f"{service} ({railway_environment})"
        raise click.ClickException(
            f"Railway CLI output format error for {role} service '{label}': {exc}"
        ) from exc
    if variables is None:
        label = service
        if railway_environment:
            label = f"{service} ({railway_environment})"
        raise click.ClickException(
            f"Unable to load Railway variables for the {role} service '{label}'."
        )
    return variables


def _build_context(
    route_label: str,
    *,
    source_service: str | None,
    target_service: str | None,
    source_railway_environment: str | None,
    target_railway_environment: str | None,
    include_target: bool,
) -> DisasterRecoveryContext:
    _validate_project_and_docker()
    route = _resolve_route(route_label)
    _validate_route_services(
        route,
        source_service=source_service,
        target_service=target_service,
        include_target=include_target,
    )
    identity = _resolve_project_identity()

    source_runtime_variables: dict[str, str] = {}
    if route.source_requires_service():
        assert source_service is not None
        source_runtime_variables = _fetch_railway_runtime_variables(
            service=source_service,
            railway_environment=source_railway_environment,
            role="source",
        )

    target_runtime_variables: dict[str, str] = {}
    if include_target and route.target_requires_service():
        assert target_service is not None
        target_runtime_variables = _fetch_railway_runtime_variables(
            service=target_service,
            railway_environment=target_railway_environment,
            role="target",
        )

    return DisasterRecoveryContext(
        route=route,
        identity=identity,
        source_service=source_service,
        target_service=target_service,
        source_railway_environment=source_railway_environment,
        target_railway_environment=target_railway_environment,
        source_runtime_variables=source_runtime_variables,
        target_runtime_variables=target_runtime_variables,
    )


def _call_adapter(
    function_name: str,
    /,
    **kwargs: Any,
) -> dict[str, Any]:
    """Call a DR adapter function inside the backend container.

    Uses the thin ``dr_adapter_call`` management command as the transport
    bridge — no env-var protocol, no per-operation management commands.
    """
    args_json = json.dumps(kwargs, default=str)
    docker_command = [
        "docker",
        "exec",
        get_backend_container_name(),
        "python",
        "manage.py",
        "dr_adapter_call",
        function_name,
        "--args-json",
        args_json,
    ]

    result = subprocess.run(
        docker_command,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode == 0:
        try:
            return json.loads(result.stdout)  # type: ignore[no-any-return]
        except json.JSONDecodeError as exc:
            raise click.ClickException(
                f"DR adapter '{function_name}' returned invalid JSON."
            ) from exc

    error_output = (result.stderr or result.stdout or "unknown error").strip()
    if "No such container" in error_output or "is not running" in error_output:
        raise click.ClickException(
            "Backend container is not running. Start services with 'quickscale up' first."
        )
    raise click.ClickException(f"DR adapter '{function_name}' failed: {error_output}")


def _fetch_snapshot_report(
    context: DisasterRecoveryContext,
    *,
    snapshot_id: str,
    sidecar_payloads: tuple[str, ...] = (),
) -> dict[str, Any]:
    return _call_adapter(
        "fetch_snapshot_report",
        snapshot_id=snapshot_id,
        sidecar_payloads=list(sidecar_payloads),
    )


def _capture_snapshot_report(
    context: DisasterRecoveryContext,
    *,
    resume_snapshot_id: str | None = None,
) -> dict[str, Any]:
    return _call_adapter(
        "capture_snapshot",
        trigger="manual",
        resume_snapshot_id=resume_snapshot_id,
    )


def _record_verification(
    context: DisasterRecoveryContext,
    *,
    snapshot_id: str,
    phase: str,
    status: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return _call_adapter(
        "record_verification",
        snapshot_id=snapshot_id,
        route=context.route.label,
        phase=phase,
        status=status,
        payload=payload,
    )


def _set_rollback_pin(
    context: DisasterRecoveryContext,
    *,
    snapshot_id: str,
    hours: int,
    reason: str,
) -> dict[str, Any]:
    return _call_adapter(
        "set_rollback_pin",
        snapshot_id=snapshot_id,
        hours=hours,
        reason=reason,
    )


def _run_media_sync(
    context: DisasterRecoveryContext,
    *,
    snapshot_id: str,
    dry_run: bool,
) -> dict[str, Any]:
    """Run media sync via the adapter, carrying route kind for Railway-target guard."""
    target_settings = dict(context.target_runtime_variables)
    target_settings["ROUTE_KIND"] = context.route.target_kind
    return _call_adapter(
        "sync_media",
        snapshot_id=snapshot_id,
        dry_run=dry_run,
        target_runtime_settings=target_settings,
    )


def _build_database_plan(
    context: DisasterRecoveryContext,
    snapshot_report: dict[str, Any],
) -> dict[str, Any]:
    return _call_adapter(
        "build_database_plan",
        snapshot_report=snapshot_report,
    )


def _load_source_live_variables(context: DisasterRecoveryContext) -> dict[str, str]:
    if context.route.source_kind == "railway":
        return context.source_runtime_variables

    docker_command = [
        "docker",
        "exec",
        get_backend_container_name(),
        "env",
    ]
    result = subprocess.run(
        docker_command,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        error = (result.stderr or result.stdout or "unknown error").strip()
        raise click.ClickException(
            f"Unable to read source environment variables: {error}"
        )
    environment: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        environment[key] = value
    return environment


def _classify_env_var(name: str) -> tuple[str, str]:
    """Backward-compatible wrapper around the centralized helper.

    The classification rules live in
    :func:`quickscale_core.contracts.module_options.get_env_var_portability`
    so that the schema layer and any future caller can reuse them. This
    thin shim preserves the original private name and signature so any
    caller that still reaches into ``dr_commands._classify_env_var`` —
    including the legacy test suite — continues to receive the same
    ``(category, reason)`` tuple with the same reason strings.
    """
    return get_env_var_portability(name)


def _build_env_sync_plan(
    context: DisasterRecoveryContext,
    snapshot_report: dict[str, Any],
) -> dict[str, Any]:
    payloads = snapshot_report.get("sidecar_payloads") or {}
    env_manifest = payloads.get(_ENV_MANIFEST_FILENAME)
    if not isinstance(env_manifest, dict):
        return {
            "status": "unavailable",
            "portable_candidates": [],
            "portable_conflicts": [],
            "portable_existing": [],
            "manual_requirements": [],
            "ignored_count": 0,
            "reason": "env-var sidecar payload was not requested or could not be parsed",
        }

    if str(env_manifest.get("status", "")).strip() != "ready":
        return {
            "status": "unavailable",
            "portable_candidates": [],
            "portable_conflicts": [],
            "portable_existing": [],
            "manual_requirements": [],
            "ignored_count": 0,
            "reason": str(env_manifest.get("reason", "env-var manifest is not ready")),
        }

    source_live_variables = _load_source_live_variables(context)
    target_live_variables = context.target_runtime_variables
    portable_candidates: list[str] = []
    portable_existing: list[str] = []
    portable_conflicts: list[dict[str, str]] = []
    manual_requirements: list[dict[str, Any]] = []
    ignored_count = 0

    raw_names = env_manifest.get("names", [])
    source_names = [name for name in raw_names if isinstance(name, str)]
    for name in sorted(source_names):
        category, reason = _classify_env_var(name)
        if category == "ignored":
            ignored_count += 1
            continue

        source_value = str(source_live_variables.get(name, "")).strip()
        target_value = str(target_live_variables.get(name, "")).strip()

        if category == "portable":
            if not source_value:
                continue
            if not target_value:
                portable_candidates.append(name)
                continue
            if target_value == source_value:
                portable_existing.append(name)
                continue
            portable_conflicts.append(
                {
                    "name": name,
                    "reason": "target already defines a different value",
                }
            )
            continue

        manual_requirements.append(
            {
                "name": name,
                "reason": reason,
                "target_has_value": bool(target_value),
            }
        )

    status = "ready"
    if portable_conflicts or manual_requirements:
        status = "manual_required"

    return {
        "status": status,
        "portable_candidates": portable_candidates,
        "portable_existing": portable_existing,
        "portable_conflicts": portable_conflicts,
        "manual_requirements": manual_requirements,
        "ignored_count": ignored_count,
    }


def _build_plan_payload(
    context: DisasterRecoveryContext,
    snapshot_report: dict[str, Any],
    *,
    database_plan: dict[str, Any],
    media_plan: dict[str, Any],
    env_sync_plan: dict[str, Any],
) -> dict[str, Any]:
    sidecar_payloads = snapshot_report.get("sidecar_payloads") or {}
    release_metadata = sidecar_payloads.get(_RELEASE_METADATA_FILENAME, {})
    manual_actions = [
        item["name"] for item in env_sync_plan.get("manual_requirements", [])
    ] + [item["name"] for item in env_sync_plan.get("portable_conflicts", [])]
    status = "ready" if not manual_actions else "manual_required"

    return {
        "status": status,
        "snapshot_id": snapshot_report["snapshot_id"],
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
        "database": database_plan,
        "media": media_plan,
        "env_vars": env_sync_plan,
        "release_metadata": {
            "app_version": release_metadata.get("app_version"),
            "git_sha": release_metadata.get("git_sha"),
            "module_versions": release_metadata.get("module_versions", {}),
        },
        "manual_actions": sorted(set(manual_actions)),
    }


def _execute_portable_env_sync(
    context: DisasterRecoveryContext,
    env_sync_plan: dict[str, Any],
) -> dict[str, Any]:
    source_live_variables = _load_source_live_variables(context)
    variables_to_copy = {
        name: source_live_variables[name]
        for name in env_sync_plan.get("portable_candidates", [])
        if str(source_live_variables.get(name, "")).strip()
    }
    if not variables_to_copy:
        status = "skipped"
        if env_sync_plan.get("manual_requirements") or env_sync_plan.get(
            "portable_conflicts"
        ):
            status = "manual_required"
        return {
            "status": status,
            "copied": [],
            "failed": [],
            "manual_requirements": env_sync_plan.get("manual_requirements", []),
            "portable_conflicts": env_sync_plan.get("portable_conflicts", []),
        }

    success, failed_keys = set_railway_variables_batch(
        variables_to_copy,
        service=context.target_service,
        environment=context.target_railway_environment,
    )
    copied = sorted(set(variables_to_copy) - set(failed_keys))
    status = "completed" if success else "partial"
    return {
        "status": status,
        "copied": copied,
        "failed": sorted(failed_keys),
        "manual_requirements": env_sync_plan.get("manual_requirements", []),
        "portable_conflicts": env_sync_plan.get("portable_conflicts", []),
    }


def _execute_database_restore(
    context: DisasterRecoveryContext,
    snapshot_report: dict[str, Any],
) -> dict[str, Any]:
    allow_production = context.route.target_environment == "railway-production"
    return _call_adapter(
        "execute_database_restore",
        snapshot_report=snapshot_report,
        allow_production=allow_production,
    )


def _latest_route_phase_record(
    snapshot_report: dict[str, Any],
    *,
    route: str,
    phase: str,
) -> dict[str, Any] | None:
    """Return the latest stored route record for one verification phase."""
    route_report = _build_route_report(snapshot_report, route=route)
    latest_records = route_report.get("latest_records", {})
    if not isinstance(latest_records, dict):
        return None

    record = latest_records.get(phase)
    return record if isinstance(record, dict) else None


def _latest_execute_surface_statuses(
    latest_execute_record: dict[str, Any] | None,
) -> dict[str, str]:
    """Extract the last recorded execute status for each operational surface."""
    if latest_execute_record is None:
        return {}

    payload = latest_execute_record.get("payload")
    if not isinstance(payload, dict):
        return {}

    statuses: dict[str, str] = {}
    for surface_name in _DR_EXECUTE_SURFACES:
        surface_payload = payload.get(surface_name)
        if not isinstance(surface_payload, dict):
            continue
        statuses[surface_name] = str(surface_payload.get("status") or "").strip()
    return statuses


def _latest_execute_surface_payloads(
    latest_execute_record: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Return deep-copied surface payloads from the latest execute record."""
    if latest_execute_record is None:
        return {}

    payload = latest_execute_record.get("payload")
    if not isinstance(payload, dict):
        return {}

    carried_payloads: dict[str, dict[str, Any]] = {}
    for surface_name in _DR_EXECUTE_SURFACES:
        surface_payload = payload.get(surface_name)
        if isinstance(surface_payload, dict):
            carried_payloads[surface_name] = deepcopy(surface_payload)
    return carried_payloads


def _resolve_execute_surface_selection(
    *,
    latest_execute_record: dict[str, Any] | None,
    database: bool,
    media: bool,
    env_vars: bool,
    resume: bool,
) -> tuple[str, ...]:
    """Resolve which DR surfaces should run for this execute invocation."""
    explicit_selection = tuple(
        surface_name
        for selected, surface_name in (
            (env_vars, "env_vars"),
            (database, "database"),
            (media, "media"),
        )
        if selected
    )
    if explicit_selection:
        return explicit_selection

    if not resume:
        raise click.ClickException(
            "Choose at least one operational surface: --database, --media, or --env-vars."
        )

    if latest_execute_record is None:
        raise click.ClickException(
            "Cannot resume execute because no prior execute record is stored for this route and snapshot."
        )

    payload = latest_execute_record.get("payload")
    if not isinstance(payload, dict):
        raise click.ClickException(
            "Cannot resume execute because the latest execute record does not contain a structured payload."
        )

    return tuple(
        surface_name
        for surface_name in _DR_EXECUTE_SURFACES
        if isinstance(payload.get(surface_name), dict)
        and str(payload[surface_name].get("status") or "").strip()
        in _DR_EXECUTE_RETRYABLE_STATUSES
    )


def _surface_result_requires_follow_up(surface_payload: dict[str, Any]) -> bool:
    """Return whether one execute surface still needs additional work."""
    return (
        str(surface_payload.get("status") or "").strip()
        in _DR_EXECUTE_RETRYABLE_STATUSES
    )


def _build_route_report(
    snapshot_report: dict[str, Any],
    *,
    route: str,
) -> dict[str, Any]:
    payloads = snapshot_report.get("sidecar_payloads") or {}
    verification_payload = payloads.get(_PROMOTION_VERIFICATION_FILENAME, {})
    records = verification_payload.get("reports", [])
    route_records = [
        record
        for record in records
        if isinstance(record, dict) and record.get("route") == route
    ]
    latest_records: dict[str, dict[str, Any]] = {}
    for record in route_records:
        phase = str(record.get("phase") or "").strip()
        if phase:
            latest_records[phase] = record

    return {
        "snapshot_id": snapshot_report["snapshot_id"],
        "route": route,
        "source_environment": snapshot_report.get("source_environment"),
        "snapshot_status": snapshot_report.get("status"),
        "verification_records": route_records,
        "latest_records": latest_records,
    }


def _echo_json(payload: dict[str, Any]) -> None:
    click.echo(json.dumps(payload, indent=2, sort_keys=True))


def _echo_capture_summary(
    context: DisasterRecoveryContext,
    snapshot_report: dict[str, Any],
) -> None:
    click.echo(f"Route: {context.route.label}")
    click.echo(f"Snapshot id: {snapshot_report['snapshot_id']}")
    click.echo(f"Source environment: {snapshot_report['source_environment']}")
    if context.source_service:
        click.echo(f"Source service: {context.source_service}")
    click.echo(f"Snapshot status: {snapshot_report['status']}")
    authoritative_dump = snapshot_report.get("authoritative_dump") or {}
    click.echo(f"Database artifact: {authoritative_dump.get('filename', 'unknown')}")


def _echo_plan_summary(plan_payload: dict[str, Any]) -> None:
    click.echo(f"Route: {plan_payload['route']}")
    click.echo(f"Snapshot id: {plan_payload['snapshot_id']}")
    click.echo(f"Plan status: {plan_payload['status']}")
    click.echo(f"Database: {plan_payload['database']['status']}")
    click.echo(f"Media: {plan_payload['media']['status']}")
    click.echo(f"Env vars: {plan_payload['env_vars']['status']}")
    manual_actions = plan_payload.get("manual_actions", [])
    if manual_actions:
        click.echo("Manual actions:")
        for name in manual_actions:
            click.echo(f"  - {name}")


def _echo_execute_summary(execute_payload: dict[str, Any]) -> None:
    click.echo(f"Route: {execute_payload['route']}")
    click.echo(f"Snapshot id: {execute_payload['snapshot_id']}")
    click.echo(f"Execution status: {execute_payload['status']}")
    if execute_payload.get("rollback_pin"):
        rollback_pin = execute_payload["rollback_pin"]
        click.echo(
            f"Rollback pin expires at: {rollback_pin.get('expires_at') or 'none'}"
        )
    for surface_name in ("env_vars", "database", "media"):
        surface_payload = execute_payload.get(surface_name)
        if not isinstance(surface_payload, dict):
            continue
        click.echo(
            f"{surface_name.replace('_', ' ').title()}: {surface_payload['status']}"
        )


def _echo_report_summary(route_report: dict[str, Any]) -> None:
    click.echo(f"Route: {route_report['route']}")
    click.echo(f"Snapshot id: {route_report['snapshot_id']}")
    click.echo(f"Snapshot status: {route_report['snapshot_status']}")
    latest_records = route_report.get("latest_records", {})
    if not latest_records:
        click.echo("No plan or execute records are stored for this route yet.")
        return
    for phase in ("plan", "execute"):
        record = latest_records.get(phase)
        if not isinstance(record, dict):
            continue
        click.echo(f"{phase.title()} status: {record.get('status', 'unknown')}")


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
