"""Adapter bridge and live-variable loading for the DR command surface.

Implementation detail of :mod:`quickscale_cli.commands.dr_commands`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

import click

from quickscale_cli.commands._dr_context import DisasterRecoveryContext
import quickscale_cli.commands.dr_commands as _dr_commands


def _call_adapter(
    function_name: str,
    /,
    **kwargs: Any,
) -> dict[str, Any]:
    """Call a DR adapter function inside the backend container.

    The JSON payload is piped through stdin (``docker exec -i``) instead
    of passing ``--args-json`` on the command line, keeping secret values
    off process argv (SA31).
    """
    args_json = json.dumps(kwargs, default=str)
    docker_command = [
        "docker",
        "exec",
        "-i",
        _dr_commands.get_backend_container_name(),
        "python",
        "manage.py",
        "quickscale_backups_dr_adapter_call",
        function_name,
    ]

    result = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
        docker_command,
        input=args_json,
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
    return _dr_commands._call_adapter(
        "fetch_snapshot_report",
        snapshot_id=snapshot_id,
        sidecar_payloads=list(sidecar_payloads),
    )


def _capture_snapshot_report(
    context: DisasterRecoveryContext,
    *,
    resume_snapshot_id: str | None = None,
) -> dict[str, Any]:
    return _dr_commands._call_adapter(
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
    return _dr_commands._call_adapter(
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
    return _dr_commands._call_adapter(
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
    return _dr_commands._call_adapter(
        "sync_media",
        snapshot_id=snapshot_id,
        dry_run=dry_run,
        target_runtime_settings=target_settings,
    )


def _build_database_plan(
    context: DisasterRecoveryContext,
    snapshot_report: dict[str, Any],
) -> dict[str, Any]:
    return _dr_commands._call_adapter(
        "build_database_plan",
        snapshot_report=snapshot_report,
    )


def _execute_database_restore(
    context: DisasterRecoveryContext,
    snapshot_report: dict[str, Any],
) -> dict[str, Any]:
    allow_production = context.route.target_environment == "railway-production"
    return _dr_commands._call_adapter(
        "execute_database_restore",
        snapshot_report=snapshot_report,
        allow_production=allow_production,
    )


def _load_source_live_variables(context: DisasterRecoveryContext) -> dict[str, str]:
    if context.route.source_kind == "railway":
        return context.source_runtime_variables

    docker_command = [
        "docker",
        "exec",
        _dr_commands.get_backend_container_name(),
        "env",
    ]
    result = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
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
