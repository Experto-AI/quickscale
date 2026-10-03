"""Private remote (S3-compatible) upload, materialize, and delete operations."""

from __future__ import annotations


from pathlib import Path
from quickscale_core.dr_engine._types import _RemoteDeleter
from quickscale_core.dr_engine._types import _RemoteUploader
from quickscale_core.dr_engine.primitives import BackupPolicySnapshot
from typing import Any

import quickscale_core.dr_engine.orchestration as _orchestration


def _resolve_private_remote_credentials(
    policy: BackupPolicySnapshot,
) -> tuple[str, str]:
    """Resolve runtime private-remote credentials from the configured env vars."""
    access_key_id = policy.resolve_remote_access_key_id()
    secret_access_key = policy.resolve_remote_secret_access_key()

    if not access_key_id:
        raise _orchestration.BackupConfigurationError(
            "Environment variable "
            f"'{policy.remote_access_key_id_env_var.strip()}' is required for "
            "private_remote backups"
        )
    if not secret_access_key:
        raise _orchestration.BackupConfigurationError(
            "Environment variable "
            f"'{policy.remote_secret_access_key_env_var.strip()}' is required for "
            "private_remote backups"
        )

    return access_key_id, secret_access_key


def _upload_to_private_remote(local_path: Path, policy: BackupPolicySnapshot) -> str:
    access_key_id, secret_access_key = (
        _orchestration._resolve_private_remote_credentials(policy)
    )

    options: dict[str, Any] = {
        "bucket_name": policy.remote_bucket_name,
        "querystring_auth": True,
        "default_acl": "",
    }
    if policy.remote_endpoint_url.strip():
        options["endpoint_url"] = policy.remote_endpoint_url.strip()
    if policy.remote_region_name.strip():
        options["region_name"] = policy.remote_region_name.strip()
    options["access_key"] = access_key_id
    options["secret_key"] = secret_access_key

    remote_prefix = policy.remote_prefix.strip().strip("/")
    remote_key = (
        f"{remote_prefix}/{local_path.name}" if remote_prefix else local_path.name
    )
    _orchestration.upload_file_to_s3(local_path, remote_key, options)
    return remote_key


def _materialize_private_remote_key(
    remote_key: str,
    policy: BackupPolicySnapshot,
    destination: Path,
) -> None:
    from storages.backends.s3 import S3Storage

    access_key_id, secret_access_key = (
        _orchestration._resolve_private_remote_credentials(policy)
    )

    options: dict[str, Any] = {
        "bucket_name": policy.remote_bucket_name,
        "querystring_auth": True,
        "default_acl": "",
    }
    if policy.remote_endpoint_url.strip():
        options["endpoint_url"] = policy.remote_endpoint_url.strip()
    if policy.remote_region_name.strip():
        options["region_name"] = policy.remote_region_name.strip()
    options["access_key"] = access_key_id
    options["secret_key"] = secret_access_key

    storage = S3Storage(**options)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with storage.open(remote_key, mode="rb") as source_handle:
            with destination.open("wb") as destination_handle:
                _orchestration.shutil.copyfileobj(source_handle, destination_handle)
    except Exception as exc:
        cleanup_error = _orchestration._cleanup_local_backup_file(destination)
        details = f"Private remote materialization failed for {remote_key}: {exc}"
        if cleanup_error is not None:
            details += f"; cleanup failed: {cleanup_error}"
        raise _orchestration.BackupError(details) from exc


def _delete_private_remote_key(remote_key: str, policy: BackupPolicySnapshot) -> None:
    access_key_id, secret_access_key = (
        _orchestration._resolve_private_remote_credentials(policy)
    )

    options: dict[str, Any] = {
        "bucket_name": policy.remote_bucket_name,
        "querystring_auth": True,
        "default_acl": "",
    }
    if policy.remote_endpoint_url.strip():
        options["endpoint_url"] = policy.remote_endpoint_url.strip()
    if policy.remote_region_name.strip():
        options["region_name"] = policy.remote_region_name.strip()
    options["access_key"] = access_key_id
    options["secret_key"] = secret_access_key

    _orchestration.delete_s3_key(remote_key, options)


def _upload_snapshot_child_to_private_remote(
    local_path: Path,
    *,
    policy: BackupPolicySnapshot,
    snapshot_remote_root: str,
    relative_path: str,
    remote_uploader: _RemoteUploader,
) -> str:
    """Upload one snapshot child while preserving the snapshot-relative remote layout."""
    relative_parent = Path(relative_path).parent.as_posix()
    remote_prefix = snapshot_remote_root
    if relative_parent not in {"", "."}:
        remote_prefix = f"{snapshot_remote_root}/{relative_parent}"
    return remote_uploader(
        local_path,
        _orchestration._replace_policy_remote_prefix(policy, remote_prefix),
    )


def _delete_snapshot_storage(
    snapshot: Any,
    *,
    policy: BackupPolicySnapshot,
    remote_deleter: _RemoteDeleter | None = None,
) -> None:
    """Delete all private files associated with one stored snapshot."""
    snapshot_root = Path(snapshot.local_root_path)
    artifact = snapshot.authoritative_dump
    remote_keys: set[str] = set()
    child_descriptors_json = (
        snapshot.child_descriptors_json
        if isinstance(snapshot.child_descriptors_json, dict)
        else {}
    )

    database_descriptor = child_descriptors_json.get("database")
    if isinstance(database_descriptor, dict):
        remote_key = str(database_descriptor.get("remote_key", "")).strip()
        if remote_key:
            remote_keys.add(remote_key)

    sidecars = child_descriptors_json.get("sidecars")
    if isinstance(sidecars, dict):
        for descriptor in sidecars.values():
            if not isinstance(descriptor, dict):
                continue
            remote_key = str(descriptor.get("remote_key", "")).strip()
            if remote_key:
                remote_keys.add(remote_key)

    if artifact is not None and artifact.remote_key:
        remote_keys.add(artifact.remote_key)

    if remote_keys:
        deleter = remote_deleter or _orchestration._delete_private_remote_key
        remote_policy = (
            _orchestration._resolve_artifact_remote_policy(artifact, policy)
            if artifact is not None
            else policy
        )
        for remote_key in sorted(remote_keys):
            deleter(remote_key, remote_policy)

    if snapshot_root.exists():
        _orchestration.shutil.rmtree(snapshot_root)

    if artifact is not None and artifact.local_path:
        artifact_local_path = Path(artifact.local_path)
        if artifact_local_path.exists():
            artifact_local_path.unlink()
