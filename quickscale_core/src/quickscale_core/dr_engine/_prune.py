"""Artifact deletion, expiry pruning, and download path safety."""

from __future__ import annotations


from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path
from quickscale_core.dr_engine._types import _RemoteDeleter
from quickscale_core.dr_engine.primitives import BackupPolicySnapshot
from typing import Any
import os


import quickscale_core.dr_engine._state as _state
import quickscale_core.dr_engine.persistence as _persistence
import quickscale_core.dr_engine.primitives as _primitives
import quickscale_core.dr_engine._policy as _policy
import quickscale_core.dr_engine._remote as _remote
import django.utils.timezone as _django_timezone
import quickscale_core.dr_engine._paths as _paths


def delete_artifact_files(
    artifact: Any,
    *,
    policy: BackupPolicySnapshot | None = None,
    remote_deleter: _RemoteDeleter | None = None,
) -> None:
    """Delete local and remote artifact files without deleting the database row."""
    resolved_policy = policy or _policy._load_active_policy_snapshot()
    snapshot = _state._get_authoritative_snapshot_for_artifact(artifact)
    if snapshot is not None:
        _remote._delete_snapshot_storage(
            snapshot,
            policy=resolved_policy,
            remote_deleter=remote_deleter,
        )
        snapshot.status = "deleted"
        snapshot.child_descriptors_json = _state._mark_snapshot_descriptors_deleted(
            snapshot.child_descriptors_json
            if isinstance(snapshot.child_descriptors_json, dict)
            else {}
        )
        _persistence.save_snapshot(
            snapshot, update_fields=["status", "child_descriptors_json", "updated_at"]
        )
        return

    local_path = Path(artifact.local_path) if artifact.local_path else None
    if local_path and local_path.exists():
        local_path.unlink()

    if artifact.remote_key:
        deleter = remote_deleter or _remote._delete_private_remote_key
        deleter(
            artifact.remote_key,
            _state._resolve_artifact_remote_policy(artifact, resolved_policy),
        )


def prune_expired_backups(
    *,
    policy: BackupPolicySnapshot | None = None,
    now: datetime | None = None,
    remote_deleter: _RemoteDeleter | None = None,
    dry_run: bool = False,
) -> int:
    """Delete expired backup files and mark their metadata records as deleted.

    With ``dry_run=True``, report how many records would be deleted and write
    nothing.
    """
    resolved_policy = policy or _policy._load_active_policy_snapshot(
        ensure_default=not dry_run
    )
    prune_started_at = now or datetime.now(timezone.utc)
    cutoff = prune_started_at - timedelta(days=resolved_policy.retention_days)

    if dry_run:
        expired_snapshot_count = sum(
            1
            for snapshot in _persistence.iter_expired_snapshots(cutoff)
            if not snapshot.has_active_rollback_pin(now=prune_started_at)
        )
        expired_orphan_count = sum(
            1 for _ in _persistence.iter_expired_unlinked_artifacts(cutoff)
        )
        return expired_snapshot_count + expired_orphan_count

    deleted_count = 0
    deleted_at = _django_timezone.now()

    expired_snapshots = _persistence.iter_expired_snapshots(cutoff)
    for snapshot in expired_snapshots:
        if snapshot.has_active_rollback_pin(now=prune_started_at):
            continue

        _remote._delete_snapshot_storage(
            snapshot,
            policy=resolved_policy,
            remote_deleter=remote_deleter,
        )
        snapshot.status = "deleted"
        snapshot.child_descriptors_json = _state._mark_snapshot_descriptors_deleted(
            snapshot.child_descriptors_json
            if isinstance(snapshot.child_descriptors_json, dict)
            else {}
        )
        _persistence.save_snapshot(
            snapshot, update_fields=["status", "child_descriptors_json", "updated_at"]
        )

        artifact = snapshot.authoritative_dump
        if artifact is not None and artifact.deleted_at is None:
            artifact.status = "deleted"
            artifact.deleted_at = deleted_at
            _persistence.save_artifact(
                artifact, update_fields=["status", "deleted_at", "updated_at"]
            )

        deleted_count += 1

    expired = _persistence.iter_expired_unlinked_artifacts(cutoff)

    for artifact in expired:
        delete_artifact_files(
            artifact,
            policy=resolved_policy,
            remote_deleter=remote_deleter,
        )
        artifact.status = "deleted"
        artifact.deleted_at = deleted_at
        _persistence.save_artifact(
            artifact, update_fields=["status", "deleted_at", "updated_at"]
        )
        deleted_count += 1

    return deleted_count


def _is_path_within_root(candidate_path: Path, root_path: Path) -> bool:
    """Return whether one absolute path stays inside one absolute root."""
    try:
        candidate_path.relative_to(root_path)
    except ValueError:
        return False
    return True


def _path_uses_symlink_within_root(candidate_path: Path, root_path: Path) -> bool:
    """Return whether one candidate path traverses any symlink below a root."""
    if not _is_path_within_root(candidate_path, root_path):
        return False

    current = root_path
    for part in candidate_path.relative_to(root_path).parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _get_authoritative_local_backup_roots(
    artifact: Any,
    policy: BackupPolicySnapshot,
) -> tuple[Path, ...]:
    """Return the local roots that may legitimately contain an artifact download."""
    roots = [
        Path(os.path.abspath(os.fspath(_paths.get_local_backup_directory(policy))))
    ]
    snapshot = _state._get_authoritative_snapshot_for_artifact(artifact)
    if snapshot is not None:
        roots.append(Path(os.path.abspath(snapshot.local_root_path)))

    unique_roots: list[Path] = []
    for root in roots:
        if root not in unique_roots:
            unique_roots.append(root)
    return tuple(unique_roots)


def download_backup_path(
    artifact: Any,
    *,
    policy: BackupPolicySnapshot | None = None,
) -> Path:
    """Return the local operator download path for an artifact."""
    if not artifact.local_path:
        raise _primitives.BackupError(
            "This artifact does not have a local download path."
        )

    candidate_path = Path(artifact.local_path).expanduser()
    absolute_candidate = Path(os.path.abspath(os.fspath(candidate_path)))
    if not absolute_candidate.exists():
        raise _primitives.BackupError(f"Backup file not found: {absolute_candidate}")

    resolved_policy = policy or _policy._load_active_policy_snapshot()
    resolved_candidate = absolute_candidate.resolve(strict=True)
    if not resolved_candidate.is_file():
        raise _primitives.BackupError(
            f"Backup file is not a regular file: {resolved_candidate}"
        )

    for authoritative_root in _get_authoritative_local_backup_roots(
        artifact,
        resolved_policy,
    ):
        if not _is_path_within_root(absolute_candidate, authoritative_root):
            continue
        if _path_uses_symlink_within_root(absolute_candidate, authoritative_root):
            raise _primitives.BackupError("Backup download path cannot use symlinks.")

        resolved_root = authoritative_root.resolve(strict=False)
        if not _is_path_within_root(resolved_candidate, resolved_root):
            raise _primitives.BackupError(
                "Backup download path must stay within authoritative backup roots."
            )

        return resolved_candidate

    raise _primitives.BackupError(
        "Backup download path must stay within authoritative backup roots."
    )
