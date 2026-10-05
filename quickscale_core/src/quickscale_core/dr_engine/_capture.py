"""Snapshot capture orchestration: create, resume, and post-dump completion."""

from __future__ import annotations


from copy import deepcopy
from datetime import datetime
from datetime import timezone
from pathlib import Path
from quickscale_core.dr_engine._types import _RemoteDeleter
from quickscale_core.dr_engine._types import _RemoteUploader
from quickscale_core.dr_engine.primitives import BackupPolicySnapshot
from quickscale_core.dr_engine.primitives import ShellCommandRunner
from typing import Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.contrib.auth.base_user import AbstractBaseUser


import quickscale_core.dr_engine._sidecar as _sidecar
import quickscale_core.dr_engine._state as _state
import quickscale_core.dr_engine._paths as _paths
import quickscale_core.dr_engine._policy as _policy
import quickscale_core.dr_engine._metadata as _metadata
import quickscale_core.dr_engine._remote as _remote
import quickscale_core.dr_engine.primitives as _primitives
import quickscale_core.dr_engine.persistence as _persistence
import quickscale_core.dr_engine._prune as _prune
import quickscale_core.dr_engine._lock as _lock
import quickscale_core.dr_engine.recovery as _recovery
import django
import shutil


def _complete_capture_after_dump(
    artifact: Any,
    snapshot: Any,
    *,
    resolved_policy: BackupPolicySnapshot,
    local_path: Path,
    remote_uploader: _RemoteUploader | None,
    remote_deleter: _RemoteDeleter | None,
    child_descriptors_json: dict[str, Any],
    previous_failure_note: str,
    now: datetime,
) -> Any:
    """Execute post-dump capture steps shared by create and resume paths.

    Handles remote upload, sidecar capture, success/failure persistence,
    and cleanup prune in one flow.
    """
    # Remote upload for private_remote targets
    if resolved_policy.target_mode == "private_remote" and not artifact.remote_key:
        uploader = remote_uploader or _remote._upload_to_private_remote
        try:
            remote_key = _remote._upload_snapshot_child_to_private_remote(
                local_path,
                policy=resolved_policy,
                snapshot_remote_root=snapshot.remote_root_key,
                relative_path=str(child_descriptors_json["database"]["relative_path"]),
                remote_uploader=uploader,
            )
        except _primitives.BackupError as exc:
            _state._mark_remote_upload_failure(
                artifact, local_path=local_path, error=exc
            )
            child_descriptors_json["database"]["status"] = "failed"
            child_descriptors_json["database"]["error"] = str(exc)
            _state._mark_snapshot_failed(
                snapshot,
                failure_note=f"database dump remote upload failed: {exc}",
                child_descriptors_json=child_descriptors_json,
            )
            raise _primitives.BackupError(
                f"Snapshot capture failed for snapshot '{snapshot.snapshot_id}': {exc}"
            ) from exc
        except Exception as exc:
            upload_error = _primitives.BackupError(
                "Snapshot capture failed for snapshot "
                f"'{snapshot.snapshot_id}': Private remote upload failed for "
                f"{artifact.filename}: {exc}"
            )
            _state._mark_remote_upload_failure(
                artifact,
                local_path=local_path,
                error=upload_error,
            )
            child_descriptors_json["database"]["status"] = "failed"
            child_descriptors_json["database"]["error"] = str(upload_error)
            _state._mark_snapshot_failed(
                snapshot,
                failure_note=(f"database dump remote upload failed: {upload_error}"),
                child_descriptors_json=child_descriptors_json,
            )
            raise upload_error from exc

        artifact.remote_key = remote_key
        try:
            _persistence.save_artifact(
                artifact, update_fields=["remote_key", "updated_at"]
            )
        except Exception as exc:
            cleanup_error = _state._rollback_remote_upload_after_persistence_failure(
                artifact,
                remote_key=remote_key,
                policy=resolved_policy,
                remote_deleter=remote_deleter,
            )
            message = (
                "Snapshot capture failed for snapshot "
                f"'{snapshot.snapshot_id}': Private remote metadata "
                f"persistence failed for {artifact.filename} after uploading remote key "
                f"'{remote_key}'."
            )
            if cleanup_error is None:
                message += " Uploaded remote cleanup succeeded."
            else:
                message += (
                    " Uploaded remote cleanup failed: "
                    f"{cleanup_error}. Manual cleanup may be required for "
                    f"'{remote_key}'."
                )
            child_descriptors_json["database"]["status"] = "failed"
            child_descriptors_json["database"]["remote_key"] = remote_key
            child_descriptors_json["database"]["error"] = message
            _state._mark_snapshot_failed(
                snapshot,
                failure_note=message,
                child_descriptors_json=child_descriptors_json,
            )
            raise _primitives.BackupError(message) from exc

        child_descriptors_json["database"]["remote_key"] = remote_key
        child_descriptors_json["database"].pop("error", None)
        snapshot.child_descriptors_json = child_descriptors_json
        _persistence.save_snapshot(
            snapshot, update_fields=["child_descriptors_json", "updated_at"]
        )

    # Capture sidecars
    child_descriptors_json, sidecar_failures = _sidecar._capture_snapshot_sidecars(
        snapshot=snapshot,
        policy=resolved_policy,
        captured_at=now,
        remote_uploader=remote_uploader,
    )
    snapshot.child_descriptors_json = child_descriptors_json
    if sidecar_failures:
        failure_note = "snapshot sidecar capture failed: " + "; ".join(sidecar_failures)
        snapshot.status = "failed"
        snapshot.failure_note = failure_note
        _persistence.save_snapshot(
            snapshot,
            update_fields=[
                "child_descriptors_json",
                "status",
                "failure_note",
                "updated_at",
            ],
        )
        _state._persist_snapshot_metadata_on_artifact(
            artifact,
            snapshot,
            note=failure_note,
        )
    else:
        snapshot.status = "ready"
        if artifact.status != "ready":
            artifact.status = "ready"
            _persistence.save_artifact(artifact, update_fields=["status", "updated_at"])
        snapshot.failure_note = ""
        _persistence.save_snapshot(
            snapshot,
            update_fields=[
                "child_descriptors_json",
                "status",
                "failure_note",
                "updated_at",
            ],
        )
        cleared_previous_note = _state._clear_appended_artifact_note(
            artifact,
            previous_failure_note,
        )
        _state._persist_snapshot_metadata_on_artifact(artifact, snapshot)
        if cleared_previous_note:
            _persistence.save_artifact(
                artifact, update_fields=["validation_notes", "updated_at"]
            )

    # Post-capture prune
    try:
        _prune.prune_expired_backups(policy=resolved_policy, now=now)
    except Exception as exc:
        _state._record_prune_failure_without_masking_success(artifact, error=exc)

    return artifact


def _validate_resume_preconditions(
    snapshot: Any, policy: BackupPolicySnapshot
) -> BackupPolicySnapshot:
    """Validate resume preconditions and return the resolved capture policy."""
    resolved_policy = _paths._build_snapshot_capture_resume_policy(snapshot, policy)
    issues = _policy._validate_policy_snapshot_internal(resolved_policy)
    if issues:
        raise _primitives.BackupConfigurationError("; ".join(issues))

    if snapshot.status == "deleted":
        raise _primitives.BackupError(
            f"Cannot resume snapshot '{snapshot.snapshot_id}' because it has already been deleted."
        )

    source_environment = _metadata._get_source_environment()
    if snapshot.source_environment != source_environment:
        raise _primitives.BackupError(
            f"Cannot resume snapshot '{snapshot.snapshot_id}' from environment "
            f"'{source_environment}' because it was captured from "
            f"'{snapshot.source_environment}'."
        )

    if (
        _paths._snapshot_uses_private_remote(snapshot)
        and not snapshot.remote_root_key.strip()
    ):
        raise _primitives.BackupError(
            f"Cannot resume snapshot '{snapshot.snapshot_id}' because its private remote root is missing."
        )

    if _paths._snapshot_capture_is_complete(snapshot):
        raise _primitives.BackupError(
            f"Backup snapshot '{snapshot.snapshot_id}' is already complete; resume is not needed."
        )
    return resolved_policy


def _resume_new_artifact(
    snapshot: Any,
    database_directory: Path,
    *,
    engine: str,
    database_name: str,
    resolved_policy: BackupPolicySnapshot,
    shell_runner: ShellCommandRunner | None,
    initiated_by: AbstractBaseUser | None,
    trigger: str,
    now: datetime,
) -> tuple[Any, Path]:
    """Build the dump artifact for one found on disk or captured during resume."""
    candidate_dump_files = sorted(
        path for path in database_directory.iterdir() if path.is_file()
    )
    if len(candidate_dump_files) > 1:
        raise _primitives.BackupError(
            f"Cannot resume snapshot '{snapshot.snapshot_id}' because multiple database dump candidates were found."
        )

    database_server_version: str | None = None
    database_server_major: int | None = None
    dump_client_version: str | None = None
    dump_client_major: int | None = None

    if candidate_dump_files:
        local_path = candidate_dump_files[0]
        backup_format = _recovery._detect_restore_file_format(local_path)
        if backup_format == "pg_dump_custom":
            (
                database_server_version,
                database_server_major,
                dump_client_version,
                dump_client_major,
            ) = _metadata._require_postgresql_18_contract(
                database_engine=engine,
                executable="pg_dump",
                operation="backup capture resume",
            )
    else:
        (
            local_path,
            backup_format,
            filename,
            database_server_version,
            database_server_major,
            dump_client_version,
            dump_client_major,
        ) = _metadata._create_database_dump(
            engine,
            resolved_policy,
            shell_runner=shell_runner,
            now=now,
            database_directory=database_directory,
            operation="backup capture resume",
        )

    checksum = _primitives._compute_sha256(local_path)
    size_bytes = local_path.stat().st_size
    metadata = _metadata._build_backup_metadata(
        created_at=now,
        backup_format=backup_format,
        database_engine=engine,
        database_name=database_name,
        target_mode=resolved_policy.target_mode,
        database_server_version=database_server_version,
        database_server_major=database_server_major,
        dump_client_version=dump_client_version,
        dump_client_major=dump_client_major,
    )
    metadata["snapshot_id"] = snapshot.snapshot_id
    if snapshot.remote_root_key:
        metadata["snapshot_remote_root_key"] = snapshot.remote_root_key

    artifact = _persistence.create_artifact(
        filename=local_path.name,
        storage_target=(
            "private_remote"
            if resolved_policy.target_mode == "private_remote"
            else "local"
        ),
        local_path=str(local_path),
        remote_bucket_name=resolved_policy.remote_bucket_name,
        remote_endpoint_url=resolved_policy.remote_endpoint_url,
        remote_region_name=resolved_policy.remote_region_name,
        checksum_sha256=checksum,
        size_bytes=size_bytes,
        backup_format=backup_format,
        database_engine=engine,
        database_name=database_name,
        database_server_major=database_server_major,
        dump_client_major=dump_client_major,
        metadata_json=metadata,
        initiated_by=initiated_by,
        trigger=trigger,
    )
    return artifact, local_path


def _resume_existing_artifact(
    artifact: Any, snapshot: Any, resolved_policy: BackupPolicySnapshot
) -> Path:
    """Validate and refresh an existing authoritative dump artifact on resume."""
    if artifact.status == "deleted":
        raise _primitives.BackupError(
            f"Cannot resume snapshot '{snapshot.snapshot_id}' because its authoritative dump artifact has been deleted."
        )

    local_path = _state._resolve_snapshot_database_local_path(snapshot, artifact)
    if not local_path.exists():
        raise _primitives.BackupError(
            f"Cannot resume snapshot '{snapshot.snapshot_id}' because the original authoritative dump file is missing."
        )

    validation_issues = _recovery._collect_local_backup_validation_issues(
        local_path,
        backup_format=artifact.backup_format,
        expected_checksum=artifact.checksum_sha256,
        expected_size=artifact.size_bytes,
    )
    if validation_issues:
        raise _primitives.BackupError(
            f"Cannot resume snapshot '{snapshot.snapshot_id}' because the original authoritative dump file is not valid: "
            + "; ".join(validation_issues)
        )

    update_fields: list[str] = []
    if artifact.local_path != str(local_path):
        artifact.local_path = str(local_path)
        update_fields.append("local_path")
    if (
        not (
            resolved_policy.target_mode == "private_remote" and not artifact.remote_key
        )
        and artifact.status != "ready"
    ):
        artifact.status = "ready"
        update_fields.append("status")
    if update_fields:
        _persistence.save_artifact(
            artifact, update_fields=[*update_fields, "updated_at"]
        )
    return local_path


def _resume_child_descriptors(snapshot: Any, artifact: Any) -> dict[str, Any]:
    """Return the refreshed child-descriptor document for a resumed snapshot."""
    child_descriptors_json = deepcopy(
        snapshot.child_descriptors_json
        if isinstance(snapshot.child_descriptors_json, dict)
        else {}
    )
    child_descriptors_json["database"] = _paths._build_snapshot_database_descriptor(
        snapshot,
        artifact,
    )
    sidecars = child_descriptors_json.get("sidecars")
    if not isinstance(sidecars, dict):
        child_descriptors_json["sidecars"] = {}
    return child_descriptors_json


def _resume_backup_capture(
    snapshot_id: str,
    *,
    initiated_by: AbstractBaseUser | None = None,
    trigger: str,
    policy: BackupPolicySnapshot,
    shell_runner: ShellCommandRunner | None,
    remote_uploader: _RemoteUploader | None,
    remote_deleter: _RemoteDeleter | None,
    now: datetime,
) -> Any:
    """Resume an incomplete snapshot capture using the existing snapshot id."""
    snapshot = _state.get_backup_snapshot(snapshot_id)
    resolved_policy = _validate_resume_preconditions(snapshot, policy)

    snapshot_lock_directory = _paths._build_snapshot_lock_directory(snapshot)
    snapshot_lock_directory.mkdir(parents=True, exist_ok=True)

    with _lock._backup_creation_lock(snapshot_lock_directory, now=now):
        _persistence.refresh_snapshot(snapshot)
        previous_failure_note = snapshot.failure_note.strip()
        snapshot_root = Path(snapshot.local_root_path)
        snapshot_root.mkdir(parents=True, exist_ok=True)
        database_directory = (
            snapshot_root / _primitives._SNAPSHOT_DATABASE_DIRECTORY_NAME
        )
        database_directory.mkdir(parents=True, exist_ok=True)

        connection_settings = django.db.connections["default"].settings_dict
        engine = str(connection_settings.get("ENGINE", ""))
        database_name = str(connection_settings.get("NAME", ""))
        artifact = snapshot.authoritative_dump

        if artifact is None:
            artifact, local_path = _resume_new_artifact(
                snapshot,
                database_directory,
                engine=engine,
                database_name=database_name,
                resolved_policy=resolved_policy,
                shell_runner=shell_runner,
                initiated_by=initiated_by,
                trigger=trigger,
                now=now,
            )
            snapshot.authoritative_dump = artifact
        else:
            local_path = _resume_existing_artifact(artifact, snapshot, resolved_policy)

        child_descriptors_json = _resume_child_descriptors(snapshot, artifact)
        snapshot.child_descriptors_json = child_descriptors_json
        _persistence.save_snapshot(
            snapshot,
            update_fields=[
                "authoritative_dump",
                "child_descriptors_json",
                "updated_at",
            ],
        )

        return _complete_capture_after_dump(
            artifact,
            snapshot,
            resolved_policy=resolved_policy,
            local_path=local_path,
            remote_uploader=remote_uploader,
            remote_deleter=remote_deleter,
            child_descriptors_json=child_descriptors_json,
            previous_failure_note=previous_failure_note,
            now=now,
        )


def create_backup(
    *,
    initiated_by: AbstractBaseUser | None = None,
    trigger: str = "manual",
    policy: BackupPolicySnapshot | None = None,
    shell_runner: ShellCommandRunner | None = None,
    remote_uploader: _RemoteUploader | None = None,
    remote_deleter: _RemoteDeleter | None = None,
    now: datetime | None = None,
    resume_snapshot_id: str | None = None,
) -> Any:
    """Create a backup artifact, optionally offloading it to private remote storage."""
    resolved_policy = policy or _policy._load_active_policy_snapshot()
    backup_started_at = now or datetime.now(timezone.utc)

    if resume_snapshot_id is not None:
        return _resume_backup_capture(
            resume_snapshot_id,
            initiated_by=initiated_by,
            trigger=trigger,
            policy=resolved_policy,
            shell_runner=shell_runner,
            remote_uploader=remote_uploader,
            remote_deleter=remote_deleter,
            now=backup_started_at,
        )

    issues = _policy._validate_policy_snapshot_internal(resolved_policy)
    if issues:
        raise _primitives.BackupConfigurationError("; ".join(issues))

    local_directory = _paths.get_local_backup_directory(resolved_policy)
    local_directory.mkdir(parents=True, exist_ok=True)

    with _lock._backup_creation_lock(local_directory, now=backup_started_at):
        connection_settings = django.db.connections["default"].settings_dict
        engine = str(connection_settings.get("ENGINE", ""))
        database_name = str(connection_settings.get("NAME", ""))
        previous_failure_note = ""
        snapshot_id = _primitives._mint_snapshot_id()
        snapshot_root = _paths._build_snapshot_local_root(resolved_policy, snapshot_id)
        snapshot_root.mkdir(parents=True, exist_ok=True)
        database_directory = (
            snapshot_root / _primitives._SNAPSHOT_DATABASE_DIRECTORY_NAME
        )
        database_directory.mkdir(parents=True, exist_ok=True)
        snapshot = _persistence.create_snapshot(
            snapshot_id=snapshot_id,
            status="pending",
            source_environment=_metadata._get_source_environment(),
            local_root_path=str(snapshot_root),
            remote_root_key=(
                _paths._build_snapshot_remote_root(resolved_policy, snapshot_id)
                if resolved_policy.target_mode == "private_remote"
                else ""
            ),
            child_descriptors_json={"sidecars": {}},
        )

        try:
            (
                local_path,
                backup_format,
                filename,
                database_server_version,
                database_server_major,
                dump_client_version,
                dump_client_major,
            ) = _metadata._create_database_dump(
                engine,
                resolved_policy,
                shell_runner=shell_runner,
                now=backup_started_at,
                database_directory=database_directory,
                operation="backup creation",
            )
        except Exception as exc:
            if snapshot_root.exists():
                shutil.rmtree(snapshot_root)
            _state._mark_snapshot_failed(
                snapshot,
                failure_note=f"snapshot preparation failed: {exc}",
            )
            raise _primitives.BackupError(
                f"Snapshot capture failed for snapshot '{snapshot.snapshot_id}': {exc}"
            ) from exc

        try:
            checksum = _primitives._compute_sha256(local_path)
            size_bytes = local_path.stat().st_size
        except Exception as exc:
            cleanup_error = _lock._cleanup_local_backup_file(local_path)
            failure_note = f"snapshot dump creation failed: {exc}"
            if cleanup_error is not None:
                failure_note += f"; cleanup failed: {cleanup_error}"
            _state._mark_snapshot_failed(snapshot, failure_note=failure_note)
            if cleanup_error is not None:
                exc.add_note(
                    f"Failed to clean up partial backup file '{local_path}': {cleanup_error}"
                )
            raise _primitives.BackupError(
                f"Snapshot capture failed for snapshot '{snapshot.snapshot_id}': {exc}"
            ) from exc

        metadata = _metadata._build_backup_metadata(
            created_at=backup_started_at,
            backup_format=backup_format,
            database_engine=engine,
            database_name=database_name,
            target_mode=resolved_policy.target_mode,
            database_server_version=database_server_version,
            database_server_major=database_server_major,
            dump_client_version=dump_client_version,
            dump_client_major=dump_client_major,
        )
        metadata["snapshot_id"] = snapshot.snapshot_id
        if snapshot.remote_root_key:
            metadata["snapshot_remote_root_key"] = snapshot.remote_root_key

        artifact = _persistence.create_artifact(
            filename=filename,
            storage_target=(
                "private_remote"
                if resolved_policy.target_mode == "private_remote"
                else "local"
            ),
            local_path=str(local_path),
            remote_bucket_name=resolved_policy.remote_bucket_name,
            remote_endpoint_url=resolved_policy.remote_endpoint_url,
            remote_region_name=resolved_policy.remote_region_name,
            checksum_sha256=checksum,
            size_bytes=size_bytes,
            backup_format=backup_format,
            database_engine=engine,
            database_name=database_name,
            database_server_major=database_server_major,
            dump_client_major=dump_client_major,
            metadata_json=metadata,
            initiated_by=initiated_by,
            trigger=trigger,
        )
        child_descriptors_json: dict[str, Any] = {
            "database": _paths._build_snapshot_database_descriptor(snapshot, artifact),
            "sidecars": {},
        }
        snapshot.authoritative_dump = artifact
        snapshot.child_descriptors_json = child_descriptors_json
        _persistence.save_snapshot(
            snapshot,
            update_fields=[
                "authoritative_dump",
                "child_descriptors_json",
                "updated_at",
            ],
        )

        return _complete_capture_after_dump(
            artifact,
            snapshot,
            resolved_policy=resolved_policy,
            local_path=local_path,
            remote_uploader=remote_uploader,
            remote_deleter=remote_deleter,
            child_descriptors_json=child_descriptors_json,
            previous_failure_note=previous_failure_note,
            now=backup_started_at,
        )
