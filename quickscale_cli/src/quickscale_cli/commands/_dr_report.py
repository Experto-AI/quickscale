"""Plan payloads, execute selection, and report assembly for DR commands.

Implementation detail of :mod:`quickscale_cli.commands.dr_commands`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

import click

from quickscale_cli.commands._dr_context import DisasterRecoveryContext

import quickscale_core.dr_engine.primitives as _primitives

_DR_EXECUTE_SURFACES = ("env_vars", "database", "media")
_DR_EXECUTE_RETRYABLE_STATUSES = {
    "failed",
    "incomplete",
    "manual_required",
    "partial",
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
    release_metadata = sidecar_payloads.get(_primitives._RELEASE_METADATA_FILENAME, {})
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
    verification_payload = payloads.get(
        _primitives._PROMOTION_VERIFICATION_FILENAME, {}
    )
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
