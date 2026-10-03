"""Django-backed restore wrappers and the admin restore pipeline."""

from __future__ import annotations


from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from quickscale_core.dr_engine._lock import StagedAdminRestoreUpload
from quickscale_core.dr_engine.primitives import BackupPolicySnapshot
from quickscale_core.dr_engine.primitives import ShellCommandRunner
from quickscale_core.dr_engine.recovery import ArtifactLike
from quickscale_core.dr_engine.recovery import RemoteMaterializer
from quickscale_core.dr_engine.recovery import ResolvedRestoreSource
from quickscale_core.dr_engine.recovery import RestoreResult
from quickscale_core.dr_engine.recovery import RestoreSourceResolutionMode
from quickscale_core.dr_engine.recovery import RestoreWarning
from typing import Any
from typing import Mapping
from typing import cast
import hashlib

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quickscale_core.dr_engine.persistence import PersistedBackupArtifact

import quickscale_core.dr_engine.orchestration as _orchestration


def _get_restore_compatibility_issues(artifact: Any) -> list[str]:
    """Return restore guardrail issues — delegates to the core implementation."""
    current_engine = str(
        _orchestration.django.db.connections["default"].settings_dict.get("ENGINE")
        or ""
    ).strip()
    return _orchestration._core_get_restore_compatibility_issues(
        artifact,
        current_engine,
        installed_module_versions=_orchestration._collect_module_versions(),
    )


@contextmanager
def _resolve_restore_source(
    *,
    artifact: Any = None,
    file_path: str | Path | None = None,
    snapshot_id: str | None = None,
    resolution_mode: RestoreSourceResolutionMode = _orchestration.RestoreSourceResolutionMode.REMOTE_FALLBACK,
    policy: BackupPolicySnapshot | None = None,
    remote_materializer: RemoteMaterializer | None = None,
) -> Iterator[ResolvedRestoreSource]:
    """Resolve one restore source — Django-backed wrapper around core."""
    resolved_policy: BackupPolicySnapshot | None = policy

    def _policy_resolver(art: ArtifactLike) -> Any:
        nonlocal resolved_policy
        resolved_policy = _orchestration._resolve_artifact_remote_policy(
            cast("Any", art),
            resolved_policy or _orchestration._load_active_policy_snapshot(),
        )
        return resolved_policy

    with _orchestration._core_resolve_restore_source(
        artifact=artifact,
        file_path=file_path,
        snapshot_id=snapshot_id,
        resolution_mode=resolution_mode,
        remote_materializer=remote_materializer
        or _orchestration._materialize_private_remote_key,
        snapshot_resolver=_orchestration._resolve_authoritative_snapshot_dump,
        policy_resolver=_policy_resolver,
    ) as restore_source:
        yield restore_source


def _resolve_authoritative_snapshot_dump(snapshot_id: str) -> Any:
    """Resolve a snapshot id to its authoritative database dump artifact."""
    snapshot = _orchestration.get_backup_snapshot(snapshot_id)
    if snapshot.status == "deleted":
        raise _orchestration.BackupRestoreBlocked(
            f"Restore blocked because snapshot '{snapshot.snapshot_id}' has been deleted or pruned."
        )

    artifact = snapshot.authoritative_dump
    if artifact is None:
        raise _orchestration.BackupRestoreBlocked(
            "Restore blocked because the requested snapshot does not have an "
            "authoritative database dump artifact."
        )

    return artifact


def _ensure_postgresql_18_restore_runtime(current_engine: str) -> None:
    """Require the current restore runtime — delegates to core + Django-backed checker."""
    from quickscale_core.dr_engine.recovery import (
        _ensure_postgresql_18_restore_runtime as _core_ensure_runtime,
    )

    _core_ensure_runtime(
        current_engine,
        require_contract=_orchestration._require_postgresql_18_contract,
    )


def _restore_execution_allowed() -> bool:
    """Return whether destructive restore execution is permitted (Django-backed)."""
    return _orchestration._core_restore_execution_allowed(
        is_debug=_orchestration.settings.DEBUG
    )


def _execute_restore_for_resolved_source(
    restore_source: ResolvedRestoreSource,
    *,
    confirmation: str,
    dry_run: bool,
    allow_production: bool,
    shell_runner: ShellCommandRunner | None,
    recorded_module_versions: Mapping[str, str] | None = None,
) -> RestoreResult:
    """Run the guarded restore pipeline — Django-backed wrapper around core."""
    current_engine = str(
        _orchestration.django.db.connections["default"].settings_dict.get("ENGINE")
        or ""
    ).strip()
    connection_settings = _orchestration.django.db.connections["default"].settings_dict

    result = _orchestration._core_execute_restore_for_resolved_source(
        restore_source,
        confirmation=confirmation,
        dry_run=dry_run,
        allow_production=allow_production,
        shell_runner=shell_runner,
        current_engine=current_engine,
        connection_settings=connection_settings,
        is_debug=_orchestration.settings.DEBUG,
        pg_contract_checker=_orchestration._require_postgresql_18_contract,
        installed_module_versions=_orchestration._collect_module_versions(),
        recorded_module_versions=recorded_module_versions,
    )

    if result.executed and restore_source.artifact is not None:
        restore_warnings = _orchestration._persist_restore_artifact_metadata(
            restore_source.artifact,
            restored_at=_orchestration.django_timezone.now(),
        )
        if restore_warnings:
            result = replace(result, warnings=(*result.warnings, *restore_warnings))

    return result


def restore_backup_source(
    *,
    artifact: Any = None,
    file_path: str | Path | None = None,
    snapshot_id: str | None = None,
    confirmation: str,
    dry_run: bool = False,
    allow_production: bool = False,
    resolution_mode: RestoreSourceResolutionMode = (
        _orchestration.RestoreSourceResolutionMode.REMOTE_FALLBACK
    ),
    shell_runner: ShellCommandRunner | None = None,
    policy: BackupPolicySnapshot | None = None,
    remote_materializer: RemoteMaterializer | None = None,
    recorded_module_versions: Mapping[str, str] | None = None,
) -> RestoreResult:
    """Run guarded restore validation or execution for one restore source.

    *recorded_module_versions* carries the module vintage for a source that has
    no artifact row, such as a snapshot report restored by file path; the
    Django-backed restore path compares it with the installed modules.
    """
    with _orchestration._resolve_restore_source(
        artifact=artifact,
        file_path=file_path,
        snapshot_id=snapshot_id,
        resolution_mode=resolution_mode,
        policy=policy,
        remote_materializer=remote_materializer,
    ) as restore_source:
        return _orchestration._execute_restore_for_resolved_source(
            restore_source,
            confirmation=confirmation,
            dry_run=dry_run,
            allow_production=allow_production,
            shell_runner=shell_runner,
            recorded_module_versions=recorded_module_versions,
        )


def restore_backup_artifact(
    artifact: Any,
    *,
    confirmation: str,
    dry_run: bool = False,
    allow_production: bool = False,
    resolution_mode: RestoreSourceResolutionMode = (
        _orchestration.RestoreSourceResolutionMode.REMOTE_FALLBACK
    ),
    shell_runner: ShellCommandRunner | None = None,
    policy: BackupPolicySnapshot | None = None,
    remote_materializer: RemoteMaterializer | None = None,
) -> RestoreResult:
    """Run guarded restore validation or execution for a backup artifact."""
    return _orchestration.restore_backup_source(
        artifact=artifact,
        confirmation=confirmation,
        dry_run=dry_run,
        allow_production=allow_production,
        resolution_mode=resolution_mode,
        shell_runner=shell_runner,
        policy=policy,
        remote_materializer=remote_materializer,
    )


def _stage_admin_restore_upload(
    uploaded_file: Any,
    *,
    staging_directory: Path,
) -> StagedAdminRestoreUpload:
    """Write one uploaded admin restore file into a quarantined staging directory."""
    original_name = str(getattr(uploaded_file, "name", "")).strip()
    staged_name = Path(original_name).name or "uploaded-backup.dump"
    staged_path = staging_directory / staged_name
    digest = hashlib.sha256()
    size_bytes = 0

    try:
        with staged_path.open("wb") as handle:
            for chunk in _orchestration._iter_admin_restore_upload_chunks(
                uploaded_file
            ):
                if not chunk:
                    continue
                digest.update(chunk)
                handle.write(chunk)
                size_bytes += len(chunk)
    except OSError as exc:
        raise _orchestration.BackupError(
            f"Unable to stage uploaded backup file: {exc}"
        ) from exc

    if size_bytes < 1:
        raise _orchestration.BackupRestoreBlocked(
            "Restore blocked because the uploaded backup file is empty."
        )

    return _orchestration.StagedAdminRestoreUpload(
        local_path=staged_path,
        checksum_sha256=digest.hexdigest(),
        size_bytes=size_bytes,
    )


def _iter_admin_restore_upload_chunks(uploaded_file: Any) -> Iterator[bytes]:
    """Yield admin-uploaded restore bytes across Django upload implementations."""
    chunks_method = getattr(uploaded_file, "chunks", None)
    if callable(chunks_method):
        yielded_chunk = False
        for chunk in chunks_method():
            yielded_chunk = True
            if isinstance(chunk, bytes):
                yield chunk
            else:
                yield bytes(chunk)
        if yielded_chunk:
            return

    read_method = getattr(uploaded_file, "read", None)
    if not callable(read_method):
        raise _orchestration.BackupError(
            "Uploaded backup file does not provide a readable stream."
        )

    payload = read_method()
    if isinstance(payload, str):
        yield payload.encode("utf-8")
        return
    if isinstance(payload, bytes):
        yield payload
        return
    raise _orchestration.BackupError(
        "Uploaded backup file did not return bytes when read."
    )


def _cleanup_admin_restore_upload_directory(staging_directory: Path) -> str | None:
    """Delete one quarantined admin restore staging directory."""
    try:
        _orchestration.shutil.rmtree(staging_directory)
    except FileNotFoundError:
        return None
    except OSError as exc:
        return str(exc)
    return None


def _resolve_admin_uploaded_restore_artifact(
    *,
    checksum_sha256: str,
    size_bytes: int,
) -> PersistedBackupArtifact:
    """Resolve an uploaded file to exactly one trusted authoritative artifact.

    Delegates the ORM query and trust resolution to the registered persistence
    provider through the typed core ``resolve_admin_uploaded_restore_artifact``
    seam in ``quickscale_core.dr_engine.persistence``.
    """
    return _orchestration.resolve_admin_uploaded_restore_artifact(
        checksum_sha256=checksum_sha256, size_bytes=size_bytes
    )


def _persist_restore_artifact_metadata(
    artifact: Any,
    *,
    restored_at: datetime,
) -> tuple[RestoreWarning, ...]:
    """Best-effort persist restore metadata after pg_restore succeeds.

    SA89b Phase 1: delegates to the persistence provider.
    """
    return _orchestration.update_artifact_after_restore(
        artifact, restored_at=restored_at
    )


def restore_admin_uploaded_backup(
    uploaded_file: Any,
    *,
    confirmation: str,
    dry_run: bool = False,
    allow_production: bool = False,
    shell_runner: ShellCommandRunner | None = None,
    stale_threshold_minutes: int = 30,
) -> RestoreResult:
    """Restore one admin-uploaded backup after trusted snapshot-backed matching."""
    staging_directory = Path(
        _orchestration.mkdtemp(prefix="quickscale-backups-admin-upload-")
    )
    result: RestoreResult | None = None

    try:
        staged_upload = _orchestration._stage_admin_restore_upload(
            uploaded_file,
            staging_directory=staging_directory,
        )
        trusted_artifact = _orchestration._resolve_admin_uploaded_restore_artifact(
            checksum_sha256=staged_upload.checksum_sha256,
            size_bytes=staged_upload.size_bytes,
        )

        # CR-SA38-001: stale-aware RESTORING guard — parity with
        # prepare_admin_uploaded_restore_artifact (services.py) so the
        # uploaded-file dry-run path applies the same eligibility guard
        # and recovery guidance as the recorded-artifact branch.
        if trusted_artifact.status == "restoring":
            stale_threshold = _orchestration.django_timezone.now() - timedelta(
                minutes=stale_threshold_minutes
            )
            if (
                trusted_artifact.restore_started_at is not None
                and trusted_artifact.restore_started_at < stale_threshold
            ):
                raise _orchestration.BackupRestoreBlocked(
                    "This backup artifact's restore appears stale "
                    f"(started at {trusted_artifact.restore_started_at:%Y-%m-%d %H:%M:%S} UTC) — "
                    "the child process likely died. Reset the artifact status "
                    "from the BackupArtifact admin list to retry."
                )
            raise _orchestration.BackupRestoreBlocked(
                "This backup artifact is currently being "
                "restored. Wait for the restore to "
                "complete before retrying."
            )

        result = _orchestration._execute_restore_for_resolved_source(
            _orchestration.ResolvedRestoreSource(
                confirmation_value=trusted_artifact.filename,
                local_path=staged_upload.local_path,
                backup_format=trusted_artifact.backup_format,
                artifact=trusted_artifact,
            ),
            confirmation=confirmation,
            dry_run=dry_run,
            allow_production=allow_production,
            shell_runner=shell_runner,
        )
    except Exception as exc:
        cleanup_error = _orchestration._cleanup_admin_restore_upload_directory(
            staging_directory
        )
        if cleanup_error is not None:
            exc.add_note(
                "Failed to clean up staged admin restore upload directory "
                f"'{staging_directory}': {cleanup_error}"
            )
        raise

    assert result is not None  # noqa: S101 - internal invariant guaranteed by the caller
    cleanup_error = _orchestration._cleanup_admin_restore_upload_directory(
        staging_directory
    )
    if cleanup_error is None:
        return result

    return replace(
        result,
        warnings=(
            *result.warnings,
            _orchestration.RestoreWarning(
                code="admin_restore_upload_cleanup_failed",
                message=(
                    "Restore completed, but the staged admin upload directory "
                    "could not be cleaned up automatically."
                ),
                details={
                    "staging_directory": str(staging_directory),
                    "error": cleanup_error,
                },
            ),
        ),
    )
