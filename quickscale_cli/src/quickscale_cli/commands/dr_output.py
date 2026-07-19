"""Presentation helpers for disaster-recovery command output."""

from __future__ import annotations

import click

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quickscale_cli.commands.dr_commands import DisasterRecoveryContext


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
