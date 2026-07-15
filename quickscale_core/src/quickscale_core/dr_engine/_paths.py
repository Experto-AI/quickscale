"""Snapshot path helpers and snapshot descriptor helpers.

Path construction and descriptor building for backup snapshots.  These
are pure computation functions that do not depend on Django models or
subprocess execution.
"""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quickscale_core.dr_engine.primitives import (
    BackupPolicySnapshot,
    _build_snapshot_child_descriptor,
    _relative_snapshot_child_path,
    _SNAPSHOTS_DIRECTORY_NAME,
    _SNAPSHOT_DATABASE_DIRECTORY_NAME,
    _REQUIRED_SNAPSHOT_SIDECAR_FILENAMES,
)


# ---------------------------------------------------------------------------
# Snapshot path helpers
# ---------------------------------------------------------------------------


def build_backup_filename(
    policy: BackupPolicySnapshot,
    *,
    now: datetime | None = None,
    suffix: str | None = None,
) -> str:
    """Build a deterministic operator-friendly backup filename."""
    from quickscale_core.dr_engine.orchestration import _get_project_slug

    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    timestamp_text = timestamp.strftime("%Y%m%dT%H%M%SZ")
    environment = os.getenv("QUICKSCALE_ENVIRONMENT", "local").strip() or "local"
    project_slug = _get_project_slug()
    resolved_suffix = suffix or "json"
    return (
        f"{policy.naming_prefix.strip()}-"
        f"{project_slug}-{environment}-{timestamp_text}.{resolved_suffix}"
    )


def get_local_backup_directory(policy: BackupPolicySnapshot) -> Path:
    """Resolve the configured private local backup directory."""
    from django.conf import settings

    directory = Path(policy.local_directory)
    if directory.is_absolute():
        return directory

    base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))
    return base_dir / directory


def _build_snapshot_local_root(
    policy: BackupPolicySnapshot,
    snapshot_id: str,
) -> Path:
    """Resolve the private local root directory for one stored snapshot."""
    return get_local_backup_directory(policy) / _SNAPSHOTS_DIRECTORY_NAME / snapshot_id


def _build_snapshot_remote_root(
    policy: BackupPolicySnapshot,
    snapshot_id: str,
) -> str:
    """Return the matching private remote root key for one stored snapshot."""
    remote_prefix = policy.remote_prefix.strip().strip("/")
    snapshot_segment = f"{_SNAPSHOTS_DIRECTORY_NAME}/{snapshot_id}"
    if remote_prefix:
        return f"{remote_prefix}/{snapshot_segment}"
    return snapshot_segment


def _replace_policy_remote_prefix(
    policy: BackupPolicySnapshot,
    remote_prefix: str,
) -> BackupPolicySnapshot:
    """Return a copy of the policy scoped to a more specific remote prefix."""
    return replace(policy, remote_prefix=remote_prefix)


def _snapshot_sidecar_path(snapshot: Any, filename: str) -> Path:
    """Resolve one sidecar file path under a snapshot root."""
    return Path(snapshot.local_root_path) / filename


# ---------------------------------------------------------------------------
# Snapshot descriptor helpers
# ---------------------------------------------------------------------------


def _build_snapshot_database_descriptor(
    snapshot: Any,
    artifact: Any,
) -> dict[str, Any]:
    """Build the authoritative dump descriptor stored on a snapshot row."""
    local_path = Path(artifact.local_path) if artifact.local_path else None
    snapshot_root = Path(snapshot.local_root_path)
    relative_path = f"{_SNAPSHOT_DATABASE_DIRECTORY_NAME}/{artifact.filename}"
    if local_path is not None:
        try:
            relative_path = _relative_snapshot_child_path(snapshot_root, local_path)
        except ValueError:
            relative_path = f"{_SNAPSHOT_DATABASE_DIRECTORY_NAME}/{artifact.filename}"

    return _build_snapshot_child_descriptor(
        kind="database_dump",
        status="ready",
        relative_path=relative_path,
        local_path=local_path,
        remote_key=artifact.remote_key,
        size_bytes=artifact.size_bytes,
        checksum_sha256=artifact.checksum_sha256,
        metadata={"backup_format": artifact.backup_format},
    )


def _get_snapshot_report_children(
    snapshot: Any,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Return normalized child descriptors used by snapshot reporting."""
    child_descriptors_json = (
        snapshot.child_descriptors_json
        if isinstance(snapshot.child_descriptors_json, dict)
        else {}
    )
    database_descriptor = child_descriptors_json.get("database")
    if not isinstance(database_descriptor, dict):
        database_descriptor = {}

    sidecars = child_descriptors_json.get("sidecars")
    if not isinstance(sidecars, dict):
        sidecars = {}

    return child_descriptors_json, database_descriptor, sidecars


def _build_snapshot_capture_resume_policy(
    snapshot: Any,
    policy: BackupPolicySnapshot,
) -> BackupPolicySnapshot:
    """Align the active policy with the stored snapshot topology for resume."""
    from quickscale_core.dr_engine.orchestration import (
        _resolve_artifact_remote_policy,
    )

    resolved_policy = replace(
        policy,
        target_mode=(
            "private_remote" if _snapshot_uses_private_remote(snapshot) else "local"
        ),
    )

    if resolved_policy.target_mode != "private_remote":
        return resolved_policy

    artifact = snapshot.authoritative_dump
    if artifact is None:
        return resolved_policy

    return _resolve_artifact_remote_policy(artifact, resolved_policy)


def _snapshot_uses_private_remote(snapshot: Any) -> bool:
    """Return whether the stored snapshot topology expects private remote upload."""
    if snapshot.remote_root_key.strip():
        return True

    artifact = snapshot.authoritative_dump
    return artifact is not None and (artifact.storage_target == "private_remote")


def _build_snapshot_lock_directory(snapshot: Any) -> Path:
    """Resolve the filesystem directory used for snapshot-scoped capture locking."""
    snapshot_root = Path(snapshot.local_root_path)
    if snapshot_root.parent.name == _SNAPSHOTS_DIRECTORY_NAME:
        return snapshot_root.parent.parent
    return snapshot_root.parent


def _snapshot_capture_is_complete(snapshot: Any) -> bool:
    """Return whether a stored snapshot already has a complete capture payload."""
    if snapshot.status != "ready":
        return False

    artifact = snapshot.authoritative_dump
    if artifact is None or artifact.status == "deleted":
        return False

    child_descriptors_json = (
        snapshot.child_descriptors_json
        if isinstance(snapshot.child_descriptors_json, dict)
        else {}
    )
    database_descriptor = child_descriptors_json.get("database")
    if not isinstance(database_descriptor, dict):
        return False
    if str(database_descriptor.get("status", "")).strip() != "ready":
        return False

    local_dump_available = bool(
        artifact.local_path and Path(artifact.local_path).exists()
    )
    if not local_dump_available and not artifact.remote_key:
        return False

    sidecars = child_descriptors_json.get("sidecars")
    if not isinstance(sidecars, dict):
        return False

    for filename in _REQUIRED_SNAPSHOT_SIDECAR_FILENAMES:
        descriptor = sidecars.get(filename)
        if not isinstance(descriptor, dict):
            return False
        if str(descriptor.get("status", "")).strip() != "ready":
            return False

        local_path_text = str(descriptor.get("local_path", "")).strip()
        local_path = (
            Path(local_path_text)
            if local_path_text
            else _snapshot_sidecar_path(snapshot, filename)
        )
        if (
            not local_path.exists()
            and not str(descriptor.get("remote_key", "")).strip()
        ):
            return False

    return True


__all__ = [
    "build_backup_filename",
    "get_local_backup_directory",
    "_build_snapshot_database_descriptor",
    "_build_snapshot_local_root",
    "_build_snapshot_remote_root",
    "_build_snapshot_capture_resume_policy",
    "_build_snapshot_lock_directory",
    "_get_snapshot_report_children",
    "_replace_policy_remote_prefix",
    "_snapshot_capture_is_complete",
    "_snapshot_sidecar_path",
    "_snapshot_uses_private_remote",
]
