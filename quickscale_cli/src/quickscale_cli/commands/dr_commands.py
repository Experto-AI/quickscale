"""Disaster-recovery and environment-migration command surface."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click

from quickscale_cli.commands.development_commands import _validate_project_and_docker
from quickscale_cli.utils.project_identity import (
    ProjectIdentity,
    resolve_project_identity,
)
from quickscale_cli.utils.project_manager import get_backend_container_name
from quickscale_cli.utils.railway_utils import (
    get_railway_variables,
    set_railway_variables_batch,
)

_TARGET_ENV_PREFIX = "QUICKSCALE_DR_TARGET_"
_ENV_MANIFEST_FILENAME = "env-var-manifest.json"
_PROMOTION_VERIFICATION_FILENAME = "promotion-verification.json"
_RELEASE_METADATA_FILENAME = "release-metadata.json"

_IGNORED_ENV_EXACT = {
    "HOME",
    "HOSTNAME",
    "LANG",
    "OLDPWD",
    "PATH",
    "PWD",
    "PYTHONUNBUFFERED",
    "SHELL",
    "SHLVL",
    "TERM",
    "TZ",
    "USER",
    "_",
}
_IGNORED_ENV_PREFIXES = (
    "GPG_",
    "LC_",
    "NODE_",
    "NPM_",
    "PIP_",
    "PNPM_",
    "POETRY_",
    "PYTHON",
    "VIRTUAL_ENV",
)
_PORTABLE_ENV_EXACT = {"DEBUG"}
_PORTABLE_ENV_PREFIXES = (
    "ACCOUNT_",
    "ANALYTICS_",
    "BLOG_",
    "DJANGO_",
    "FORMS_",
    "LISTINGS_",
    "NOTIFICATIONS_",
    "QUICKSCALE_",
    "SOCIAL_",
    "SOCIALACCOUNT_",
)
_NON_PORTABLE_ENV_EXACT = {
    "ALLOWED_HOSTS",
    "CSRF_TRUSTED_ORIGINS",
    "DATABASE_URL",
    "DJANGO_SETTINGS_MODULE",
    "MEDIA_ROOT",
    "MEDIA_URL",
    "PORT",
    "SECRET_KEY",
    "STATIC_URL",
}
_NON_PORTABLE_ENV_PREFIXES = (
    "AWS_",
    "CELERY_BROKER_",
    "CLOUDFLARE_",
    "DATABASE_",
    "DJANGO_SUPERUSER_",
    "EMAIL_",
    "PG",
    "POSTGRES",
    "R2_",
    "RAILWAY_",
    "REDIS_",
    "RESEND_",
    "SENTRY_",
    "SMTP_",
    "STRIPE_",
)
_NON_PORTABLE_ENV_CONTAINS = (
    "BACKUPS_REMOTE",
    "BUCKET",
    "COOKIE",
    "CSRF",
    "DOMAIN",
    "ENDPOINT",
    "HOST",
    "KEY",
    "ORIGIN",
    "PASSWORD",
    "PRIVATE",
    "PUBLIC_BASE_URL",
    "REGION",
    "SECRET",
    "STORAGE_",
    "TOKEN",
    "URL",
)


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
    variables = get_railway_variables(
        service=service,
        environment=railway_environment,
    )
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


def _settings_module(identity: ProjectIdentity, environment_label: str) -> str:
    if environment_label == "local":
        return f"{identity.package}.settings.local"
    return f"{identity.package}.settings.production"


def _build_manage_overrides(
    identity: ProjectIdentity,
    environment_label: str,
    *,
    runtime_variables: dict[str, str] | None = None,
    allow_restore: bool = False,
) -> dict[str, str]:
    overrides = dict(runtime_variables or {})
    overrides["DJANGO_SETTINGS_MODULE"] = _settings_module(identity, environment_label)
    overrides["QUICKSCALE_ENVIRONMENT"] = environment_label
    if allow_restore:
        overrides["QUICKSCALE_BACKUPS_ALLOW_RESTORE"] = "true"
    return overrides


def _source_manage_overrides(
    context: DisasterRecoveryContext,
    *,
    allow_restore: bool = False,
) -> dict[str, str]:
    return _build_manage_overrides(
        context.identity,
        context.route.source_environment,
        runtime_variables=context.source_runtime_variables,
        allow_restore=allow_restore,
    )


def _target_manage_overrides(
    context: DisasterRecoveryContext,
    *,
    allow_restore: bool = False,
) -> dict[str, str]:
    return _build_manage_overrides(
        context.identity,
        context.route.target_environment,
        runtime_variables=context.target_runtime_variables,
        allow_restore=allow_restore,
    )


def _run_backend_container_command(
    command_args: list[str],
    *,
    env_overrides: dict[str, str] | None = None,
) -> str:
    docker_command = ["docker", "exec"]
    for key, value in sorted((env_overrides or {}).items()):
        docker_command.extend(["-e", f"{key}={value}"])
    docker_command.extend([get_backend_container_name(), *command_args])

    result = subprocess.run(
        docker_command,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return result.stdout

    error_output = (result.stderr or result.stdout or "unknown error").strip()
    if "No such container" in error_output or "is not running" in error_output:
        raise click.ClickException(
            "Backend container is not running. Start services with 'quickscale up' first."
        )
    raise click.ClickException(
        f"Backend container command failed: {' '.join(command_args)} :: {error_output}"
    )


def _run_manage_json(
    manage_args: list[str],
    *,
    env_overrides: dict[str, str],
) -> dict[str, Any]:
    output = _run_backend_container_command(
        ["python", "manage.py", *manage_args],
        env_overrides=env_overrides,
    )
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        raise click.ClickException(
            f"Expected JSON output from manage.py {' '.join(manage_args)}."
        ) from exc
    if not isinstance(payload, dict):
        raise click.ClickException(
            f"Expected JSON object output from manage.py {' '.join(manage_args)}."
        )
    return payload


def _fetch_snapshot_report(
    context: DisasterRecoveryContext,
    *,
    snapshot_id: str,
    sidecar_payloads: tuple[str, ...] = (),
) -> dict[str, Any]:
    manage_args = ["backups_report", snapshot_id, "--json"]
    for filename in sidecar_payloads:
        manage_args.extend(["--sidecar-payload", filename])
    return _run_manage_json(
        manage_args,
        env_overrides=_source_manage_overrides(context),
    )


def _capture_snapshot_report(context: DisasterRecoveryContext) -> dict[str, Any]:
    return _run_manage_json(
        ["backups_create", "--json"],
        env_overrides=_source_manage_overrides(context),
    )


def _record_verification(
    context: DisasterRecoveryContext,
    *,
    snapshot_id: str,
    phase: str,
    status: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return _run_manage_json(
        [
            "backups_record_verification",
            snapshot_id,
            "--route",
            context.route.label,
            "--phase",
            phase,
            "--status",
            status,
            "--payload-json",
            json.dumps(payload, sort_keys=True),
            "--json",
        ],
        env_overrides=_source_manage_overrides(context),
    )


def _set_rollback_pin(
    context: DisasterRecoveryContext,
    *,
    snapshot_id: str,
    hours: int,
    reason: str,
) -> dict[str, Any]:
    return _run_manage_json(
        [
            "backups_pin",
            snapshot_id,
            "--hours",
            str(hours),
            "--reason",
            reason,
            "--json",
        ],
        env_overrides=_source_manage_overrides(context),
    )


def _prefix_target_runtime_variables(
    target_runtime_variables: dict[str, str],
) -> dict[str, str]:
    return {
        f"{_TARGET_ENV_PREFIX}{key}": value
        for key, value in target_runtime_variables.items()
    }


def _target_media_sync_variables(
    context: DisasterRecoveryContext,
) -> dict[str, str]:
    return {
        **context.target_runtime_variables,
        "ROUTE_KIND": context.route.target_kind,
    }


def _run_media_sync(
    context: DisasterRecoveryContext,
    *,
    snapshot_id: str,
    dry_run: bool,
) -> dict[str, Any]:
    manage_args = ["backups_sync_media", snapshot_id, "--json"]
    if dry_run:
        manage_args.append("--dry-run")
    env_overrides = _source_manage_overrides(context)
    env_overrides.update(
        _prefix_target_runtime_variables(_target_media_sync_variables(context))
    )
    return _run_manage_json(manage_args, env_overrides=env_overrides)


def _build_database_plan(
    context: DisasterRecoveryContext,
    snapshot_report: dict[str, Any],
) -> dict[str, Any]:
    authoritative_dump = snapshot_report.get("authoritative_dump") or {}
    restore_file = str(authoritative_dump.get("local_path") or "").strip()
    confirmation_value = str(snapshot_report.get("confirmation_value") or "").strip()
    if not restore_file or not confirmation_value:
        raise click.ClickException(
            f"Snapshot '{snapshot_report['snapshot_id']}' is missing its authoritative restore file metadata."
        )

    output = _run_backend_container_command(
        [
            "python",
            "manage.py",
            "backups_restore",
            "--file",
            restore_file,
            "--confirm",
            confirmation_value,
            "--dry-run",
        ],
        env_overrides=_target_manage_overrides(context),
    )
    return {
        "status": "ready",
        "message": output.strip(),
        "restore_file": restore_file,
        "confirmation_value": confirmation_value,
        "restore_scope": authoritative_dump.get("restore_scope"),
        "restore_scope_label": authoritative_dump.get("restore_scope_label"),
    }


def _load_source_live_variables(context: DisasterRecoveryContext) -> dict[str, str]:
    if context.route.source_kind == "railway":
        return context.source_runtime_variables

    output = _run_backend_container_command(["env"])
    environment: dict[str, str] = {}
    for line in output.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        environment[key] = value
    return environment


def _is_manual_only_restore_gate(normalized_name: str) -> bool:
    return normalized_name == "QUICKSCALE_BACKUPS_ALLOW_RESTORE" or (
        normalized_name.startswith("QUICKSCALE_")
        and "ALLOW" in normalized_name
        and "RESTORE" in normalized_name
    )


def _classify_env_var(name: str) -> tuple[str, str]:
    normalized = name.strip().upper()
    if not normalized:
        return "ignored", "blank name"
    if normalized in _IGNORED_ENV_EXACT:
        return "ignored", "shell/runtime noise"
    if any(normalized.startswith(prefix) for prefix in _IGNORED_ENV_PREFIXES):
        return "ignored", "shell/runtime noise"
    if _is_manual_only_restore_gate(normalized):
        return "manual", "destructive restore gate must be set manually"
    if normalized in _NON_PORTABLE_ENV_EXACT:
        return "manual", "provider-owned or target-owned variable"
    if any(normalized.startswith(prefix) for prefix in _NON_PORTABLE_ENV_PREFIXES):
        return "manual", "provider-owned or target-owned variable"
    if any(token in normalized for token in _NON_PORTABLE_ENV_CONTAINS):
        return "manual", "sensitive or environment-specific variable"
    if normalized in _PORTABLE_ENV_EXACT:
        return "portable", "portable variable"
    if any(normalized.startswith(prefix) for prefix in _PORTABLE_ENV_PREFIXES):
        return "portable", "portable variable"
    return "manual", "outside the conservative portable allowlist"


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
    authoritative_dump = snapshot_report.get("authoritative_dump") or {}
    restore_file = str(authoritative_dump.get("local_path") or "").strip()
    confirmation_value = str(snapshot_report.get("confirmation_value") or "").strip()
    if not restore_file or not confirmation_value:
        raise click.ClickException(
            f"Snapshot '{snapshot_report['snapshot_id']}' is missing its authoritative restore file metadata."
        )

    restore_args = [
        "python",
        "manage.py",
        "backups_restore",
        "--file",
        restore_file,
        "--confirm",
        confirmation_value,
    ]
    if context.route.target_environment == "railway-production":
        restore_args.append("--allow-production")

    restore_message = _run_backend_container_command(
        restore_args,
        env_overrides=_target_manage_overrides(context, allow_restore=True),
    )
    migrate_message = _run_backend_container_command(
        ["python", "manage.py", "migrate", "--noinput"],
        env_overrides=_target_manage_overrides(context),
    )
    check_message = _run_backend_container_command(
        ["python", "manage.py", "check"],
        env_overrides=_target_manage_overrides(context),
    )
    return {
        "status": "completed",
        "restore_message": restore_message.strip(),
        "migrate_message": migrate_message.strip(),
        "check_message": check_message.strip(),
        "confirmation_value": confirmation_value,
        "restore_file": restore_file,
    }


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
@click.option("--json", "as_json", is_flag=True)
def capture(
    route: str,
    source_service: str | None,
    source_railway_environment: str | None,
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
    snapshot_report = _capture_snapshot_report(context)
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
    as_json: bool,
) -> None:
    """Execute selected DR surfaces for one stored snapshot."""
    if not any((database, media, env_vars)):
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
    if context.route.involves_production():
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
    env_sync_plan = _build_env_sync_plan(context, snapshot_report)

    rollback_pin: dict[str, Any] | None = None
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

    if env_vars:
        execute_payload["env_vars"] = _execute_portable_env_sync(context, env_sync_plan)
    if database:
        execute_payload["database"] = _execute_database_restore(
            context, snapshot_report
        )
    if media:
        execute_payload["media"] = _run_media_sync(
            context,
            snapshot_id=snapshot_id,
            dry_run=False,
        )

    if any(
        surface.get("status") in {"partial", "manual_required"}
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
