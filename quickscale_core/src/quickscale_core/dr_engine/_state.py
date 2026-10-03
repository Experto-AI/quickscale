"""Snapshot state, failure persistence, and artifact policy resolution."""

from __future__ import annotations


from copy import deepcopy
from pathlib import Path
from quickscale_core.dr_engine._types import _RemoteDeleter
from quickscale_core.dr_engine.primitives import BackupError
from quickscale_core.dr_engine.primitives import BackupPolicySnapshot
from typing import Any

import quickscale_core.dr_engine.orchestration as _orchestration


def _mark_snapshot_failed(
    snapshot: Any,
    *,
    failure_note: str,
    child_descriptors_json: dict[str, Any] | None = None,
) -> None:
    """Persist a failed snapshot outcome without hiding the stored dump artifact."""
    snapshot.status = "failed"
    snapshot.failure_note = failure_note
    update_fields = ["status", "failure_note", "updated_at"]
    if child_descriptors_json is not None:
        snapshot.child_descriptors_json = child_descriptors_json
        update_fields.append("child_descriptors_json")
    _orchestration.save_snapshot(snapshot, update_fields=update_fields)


def _mark_remote_upload_failure(
    artifact: Any,
    *,
    local_path: Path,
    error: BackupError,
) -> None:
    """Persist a failed remote-offload outcome without destroying the local dump."""
    notes = f"remote upload failed: {error}"
    artifact.remote_key = ""
    artifact.status = "failed"
    artifact.validation_notes = notes
    artifact.metadata_json = {
        **artifact.metadata_json,
        "remote_upload_error": str(error),
        "remote_upload_failed_at": _orchestration.django_timezone.now().isoformat(),
    }
    _orchestration.save_artifact(
        artifact,
        update_fields=[
            "local_path",
            "remote_key",
            "status",
            "validation_notes",
            "metadata_json",
            "updated_at",
        ],
    )


def _rollback_remote_upload_after_persistence_failure(
    artifact: Any,
    *,
    remote_key: str,
    policy: BackupPolicySnapshot,
    remote_deleter: _RemoteDeleter | None = None,
) -> str | None:
    """Best-effort delete a remote object uploaded before metadata persistence failed."""
    deleter = remote_deleter or _orchestration._delete_private_remote_key
    try:
        deleter(
            remote_key,
            _orchestration._resolve_artifact_remote_policy(artifact, policy),
        )
    except Exception as exc:
        return str(exc)
    return None


def _record_prune_failure_without_masking_success(
    artifact: Any,
    *,
    error: Exception,
) -> None:
    """Persist prune warnings on the new artifact without changing success state."""
    note = f"prune failed after backup creation: {error}"
    existing_notes = artifact.validation_notes.strip()
    artifact.validation_notes = f"{existing_notes}; {note}" if existing_notes else note
    artifact.metadata_json = {
        **artifact.metadata_json,
        "prune_error": str(error),
        "prune_failed_at": _orchestration.django_timezone.now().isoformat(),
    }

    try:
        _orchestration.save_artifact(
            artifact,
            update_fields=["validation_notes", "metadata_json", "updated_at"],
        )
    except Exception:
        return


def _persist_snapshot_metadata_on_artifact(
    artifact: Any,
    snapshot: Any,
    *,
    note: str | None = None,
) -> None:
    """Store internal snapshot references on the dump artifact metadata."""
    artifact.metadata_json = {
        **artifact.metadata_json,
        "snapshot_id": snapshot.snapshot_id,
        "snapshot_status": snapshot.status,
    }
    if snapshot.remote_root_key:
        artifact.metadata_json["snapshot_remote_root_key"] = snapshot.remote_root_key

    update_fields = ["metadata_json", "updated_at"]
    if note is not None:
        existing_notes = artifact.validation_notes.strip()
        artifact.validation_notes = (
            f"{existing_notes}; {note}" if existing_notes else note
        )
        update_fields.append("validation_notes")
    _orchestration.save_artifact(artifact, update_fields=update_fields)


def _clear_appended_artifact_note(artifact: Any, note: str) -> bool:
    """Remove one trailing snapshot-failure note appended during a prior attempt."""
    normalized_note = note.strip()
    existing_notes = artifact.validation_notes.strip()
    if not normalized_note or not existing_notes:
        return False

    if existing_notes == normalized_note:
        artifact.validation_notes = ""
        return True

    suffix = f"; {normalized_note}"
    if existing_notes.endswith(suffix):
        artifact.validation_notes = existing_notes.removesuffix(suffix)
        return True

    return False


def _resolve_snapshot_database_local_path(
    snapshot: Any,
    artifact: Any,
) -> Path:
    """Resolve the authoritative local dump path for a stored snapshot."""
    if artifact.local_path:
        return Path(str(artifact.local_path))
    return (
        Path(str(snapshot.local_root_path))
        / _orchestration._SNAPSHOT_DATABASE_DIRECTORY_NAME
        / str(artifact.filename)
    )


def _mark_snapshot_descriptors_deleted(
    child_descriptors_json: dict[str, Any],
) -> dict[str, Any]:
    """Return a copy of snapshot child metadata with deleted status applied."""
    updated = deepcopy(child_descriptors_json)
    database_descriptor = updated.get("database")
    if isinstance(database_descriptor, dict):
        database_descriptor["status"] = "deleted"

    sidecars = updated.get("sidecars")
    if isinstance(sidecars, dict):
        for descriptor in sidecars.values():
            if isinstance(descriptor, dict):
                descriptor["status"] = "deleted"

    return updated


def _get_authoritative_snapshot_for_artifact(
    artifact: Any,
) -> Any | None:
    """Return the linked snapshot for a dump artifact if one exists.

    SA89b Phase 1: delegates to the persistence provider.
    """
    return _orchestration.get_authoritative_snapshot_for_artifact(artifact)


def _resolve_artifact_remote_policy(
    artifact: Any,
    fallback_policy: BackupPolicySnapshot,
) -> BackupPolicySnapshot:
    """Build remote deletion context from artifact location plus active credentials."""
    if artifact.storage_target != "private_remote":
        return fallback_policy

    return _orchestration.BackupPolicySnapshot(
        retention_days=fallback_policy.retention_days,
        naming_prefix=fallback_policy.naming_prefix,
        target_mode="private_remote",
        local_directory=fallback_policy.local_directory,
        remote_bucket_name=(
            artifact.remote_bucket_name or fallback_policy.remote_bucket_name
        ),
        remote_prefix=fallback_policy.remote_prefix,
        remote_endpoint_url=(
            artifact.remote_endpoint_url or fallback_policy.remote_endpoint_url
        ),
        remote_region_name=(
            artifact.remote_region_name or fallback_policy.remote_region_name
        ),
        remote_access_key_id_env_var=fallback_policy.remote_access_key_id_env_var,
        remote_secret_access_key_env_var=(
            fallback_policy.remote_secret_access_key_env_var
        ),
        automation_enabled=fallback_policy.automation_enabled,
        schedule=fallback_policy.schedule,
    )


def get_backup_snapshot(snapshot_id: str) -> Any:
    """Return one stored snapshot addressed by the public snapshot locator.

    SA89b Phase 1: delegates to the persistence provider.
    """
    return _orchestration._get_backup_snapshot_from_persistence(snapshot_id)
