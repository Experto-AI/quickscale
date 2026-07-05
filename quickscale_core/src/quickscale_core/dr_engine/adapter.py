"""Typed DR adapter entrypoints for the single supported CLI-to-Django path: the CLI calls a function from ``ADAPTER_FUNCTIONS``, the backups app's ``dr_adapter_call`` bridge dispatches it inside Django, and each adapter lazily imports the service implementation then returns a JSON-serializable ``dict[str, Any]`` response with no hidden env-var transport layer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quickscale_core.dr_engine.primitives import BackupError

if TYPE_CHECKING:
    from collections.abc import Sequence

# ---------------------------------------------------------------------------
# Adapter function registry
# ---------------------------------------------------------------------------

ADAPTER_FUNCTIONS: dict[str, Any] = {}


def _register(fn: Any) -> Any:
    """Register *fn* in ``ADAPTER_FUNCTIONS`` keyed by its ``__name__``."""
    ADAPTER_FUNCTIONS[fn.__name__] = fn
    return fn


# ---------------------------------------------------------------------------
# Snapshot capture
# ---------------------------------------------------------------------------


@_register
def capture_snapshot(
    *,
    trigger: str = "manual",
    resume_snapshot_id: str | None = None,
) -> dict[str, Any]:
    """Capture a stored snapshot and return its structured report.

    This is the adapter replacement for the ``backups_create`` management
    command.  Parameters are explicit (no env-var protocol).
    """
    from quickscale_modules_backups.services import (
        build_backup_snapshot_report,
        create_backup,
    )

    try:
        artifact = create_backup(
            trigger=trigger,
            resume_snapshot_id=resume_snapshot_id,
        )
    except BackupError as exc:
        raise BackupError(str(exc)) from exc

    snapshot = getattr(artifact, "authoritative_snapshot", None)
    if snapshot is None:
        raise BackupError("Created backup is missing its stored snapshot record.")

    report = build_backup_snapshot_report(snapshot)
    return report


# ---------------------------------------------------------------------------
# Snapshot report fetching
# ---------------------------------------------------------------------------


@_register
def fetch_snapshot_report(
    snapshot_id: str,
    sidecar_payloads: Sequence[str] = (),
) -> dict[str, Any]:
    """Fetch a structured snapshot report, optionally including sidecar payloads.

    Adapter replacement for the ``backups_report`` management command.
    """
    from quickscale_modules_backups.services import report_backup_snapshot

    return report_backup_snapshot(
        snapshot_id,
        sidecar_payloads=tuple(sidecar_payloads),
    )


# ---------------------------------------------------------------------------
# Verification recording
# ---------------------------------------------------------------------------


@_register
def record_verification(
    *,
    snapshot_id: str,
    route: str,
    phase: str,
    status: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Record one route-specific plan or execute verification report.

    Adapter replacement for the ``backups_record_verification`` management
    command.
    """
    from quickscale_modules_backups.services import (
        record_backup_snapshot_verification,
    )

    return record_backup_snapshot_verification(
        snapshot_id,
        route=route,
        phase=phase,
        status=status,
        payload=payload,
    )


# ---------------------------------------------------------------------------
# Rollback pin management
# ---------------------------------------------------------------------------


@_register
def set_rollback_pin(
    *,
    snapshot_id: str,
    hours: int,
    reason: str,
) -> dict[str, Any]:
    """Set a time-bounded rollback pin on one stored snapshot.

    Adapter replacement for ``backups_pin`` (set path).
    """
    from quickscale_modules_backups.services import (
        set_backup_snapshot_rollback_pin,
    )

    return set_backup_snapshot_rollback_pin(
        snapshot_id,
        ttl_hours=hours,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# Database plan (dry-run restore validation)
# ---------------------------------------------------------------------------


@_register
def build_database_plan(
    snapshot_report: dict[str, Any],
) -> dict[str, Any]:
    """Build a dry-run database restore plan from a snapshot report.

    Extracts restore file metadata from the report and validates through
    the guarded restore pipeline in dry-run mode.
    """
    from quickscale_modules_backups.services import restore_backup_source

    authoritative_dump = snapshot_report.get("authoritative_dump") or {}
    restore_file = str(authoritative_dump.get("local_path") or "").strip()
    confirmation_value = str(snapshot_report.get("confirmation_value") or "").strip()
    if not restore_file or not confirmation_value:
        raise BackupError(
            f"Snapshot '{snapshot_report.get('snapshot_id', 'unknown')}' "
            "is missing its authoritative restore file metadata."
        )

    result = restore_backup_source(
        file_path=restore_file,
        confirmation=confirmation_value,
        dry_run=True,
    )

    return {
        "status": "ready",
        "message": result.message,
        "restore_file": restore_file,
        "confirmation_value": confirmation_value,
        "restore_scope": authoritative_dump.get("restore_scope"),
        "restore_scope_label": authoritative_dump.get("restore_scope_label"),
    }


# ---------------------------------------------------------------------------
# Database restore execution
# ---------------------------------------------------------------------------


@_register
def execute_database_restore(
    snapshot_report: dict[str, Any],
    *,
    allow_production: bool = False,
) -> dict[str, Any]:
    """Execute a guarded database restore, then run migrate and check.

    Returns a dict with restore/migrate/check status messages.
    """
    from django.core.management import call_command

    from quickscale_modules_backups.services import restore_backup_source

    authoritative_dump = snapshot_report.get("authoritative_dump") or {}
    restore_file = str(authoritative_dump.get("local_path") or "").strip()
    confirmation_value = str(snapshot_report.get("confirmation_value") or "").strip()
    if not restore_file or not confirmation_value:
        raise BackupError(
            f"Snapshot '{snapshot_report.get('snapshot_id', 'unknown')}' "
            "is missing its authoritative restore file metadata."
        )

    restore_result = restore_backup_source(
        file_path=restore_file,
        confirmation=confirmation_value,
        dry_run=False,
        allow_production=allow_production,
    )

    # Run post-restore migration and health check.
    from io import StringIO

    migrate_buffer = StringIO()
    call_command("migrate", "--noinput", stdout=migrate_buffer)
    migrate_message = migrate_buffer.getvalue().strip()

    check_buffer = StringIO()
    call_command("check", stdout=check_buffer)
    check_message = check_buffer.getvalue().strip()

    return {
        "status": "completed",
        "restore_message": restore_result.message,
        "migrate_message": migrate_message,
        "check_message": check_message,
        "confirmation_value": confirmation_value,
        "restore_file": restore_file,
    }


# ---------------------------------------------------------------------------
# Media sync
# ---------------------------------------------------------------------------


@_register
def sync_media(
    snapshot_id: str,
    *,
    dry_run: bool = False,
    target_runtime_settings: dict[str, str],
) -> dict[str, Any]:
    """Dry-run or execute media sync for one snapshot.

    ``target_runtime_settings`` is the required explicit runtime payload.
    """
    from quickscale_modules_backups.services import sync_backup_snapshot_media

    return sync_backup_snapshot_media(
        snapshot_id,
        dry_run=dry_run,
        target_runtime_settings=target_runtime_settings,
    )


# ---------------------------------------------------------------------------
# Prune expired backups
# ---------------------------------------------------------------------------


@_register
def prune_backups() -> dict[str, Any]:
    """Prune expired backup artifacts per the active retention policy.

    Adapter replacement for the ``backups_prune`` management command.
    """
    from quickscale_modules_backups.services import prune_expired_backups

    deleted_count = prune_expired_backups()
    return {"deleted_count": deleted_count}


# ---------------------------------------------------------------------------
# Artifact validation
# ---------------------------------------------------------------------------


@_register
def validate_artifact(
    artifact_id: int,
) -> dict[str, Any]:
    """Validate one backup artifact checksum and local availability.

    Adapter replacement for the ``backups_validate`` management command.
    """
    from quickscale_modules_backups.models import BackupArtifact
    from quickscale_modules_backups.services import validate_backup_artifact

    try:
        artifact = BackupArtifact.objects.get(pk=artifact_id)
    except BackupArtifact.DoesNotExist as exc:
        raise BackupError(f"Backup artifact not found: {artifact_id}") from exc

    issues = validate_backup_artifact(artifact)
    return {
        "artifact_id": artifact_id,
        "issues": issues,
        "valid": len(issues) == 0,
    }


# ---------------------------------------------------------------------------
# Rollback pin clear
# ---------------------------------------------------------------------------


@_register
def clear_rollback_pin(
    *,
    snapshot_id: str,
) -> dict[str, Any]:
    """Clear any active rollback pin on one stored snapshot.

    Adapter replacement for the ``backups_pin`` (clear path) management
    command.
    """
    from quickscale_modules_backups.services import (
        clear_backup_snapshot_rollback_pin,
    )

    return clear_backup_snapshot_rollback_pin(snapshot_id)


# ---------------------------------------------------------------------------
# Admin restore (artifact / snapshot-id / file-path)
# ---------------------------------------------------------------------------


@_register
def restore_backup(
    *,
    artifact_id: int | None = None,
    snapshot_id: str | None = None,
    file_path: str | None = None,
    confirmation: str,
    dry_run: bool = False,
    allow_production: bool = False,
    resolution_mode: Any | None = None,
) -> dict[str, Any]:
    """Validate or execute a guarded restore from one of three source types.

    Adapter replacement for the ``backups_restore`` management command.

    When *resolution_mode* is ``None`` (the default), the underlying
    ``restore_backup_source`` uses its own default
    (``REMOTE_FALLBACK``).  Pass ``LOCAL_ONLY`` to forbid remote
    materialization.
    """
    from quickscale_core.dr_engine.recovery import RestoreSourceResolutionMode
    from quickscale_modules_backups.models import BackupArtifact
    from quickscale_modules_backups.services import restore_backup_source

    if resolution_mode is None:
        resolution_mode = RestoreSourceResolutionMode.REMOTE_FALLBACK

    artifact = None
    if artifact_id is not None:
        try:
            artifact = BackupArtifact.objects.get(pk=artifact_id)
        except BackupArtifact.DoesNotExist as exc:
            raise BackupError(f"Backup artifact not found: {artifact_id}") from exc

    result = restore_backup_source(
        artifact=artifact,
        file_path=file_path,
        snapshot_id=snapshot_id,
        confirmation=confirmation,
        dry_run=dry_run,
        allow_production=allow_production,
        resolution_mode=resolution_mode,
    )

    return {
        "message": result.message,
        "warnings": [{"code": w.code, "message": w.message} for w in result.warnings],
    }
