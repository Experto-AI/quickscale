"""Sidecar building and lifecycle for DR snapshots.

Manifest building, sidecar persistence, and snapshot descriptor management.
All functions here use lazy imports for cross-module references to avoid
circular imports with ``orchestration.py``.
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from django.conf import settings

from quickscale_core.dr_engine._lock import _cleanup_local_backup_file
from quickscale_core.dr_engine._paths import _snapshot_sidecar_path
from quickscale_core.dr_engine.primitives import (
    BackupError,
    BackupPolicySnapshot,
    _build_snapshot_child_descriptor,
    _compute_sha256,
    _ENV_VAR_MANIFEST_FILENAME,
    _MEDIA_SYNC_MANIFEST_FILENAME,
    _PROMOTION_VERIFICATION_FILENAME,
    _RELEASE_METADATA_FILENAME,
    _relative_snapshot_child_path,
    _write_json_file,
)


# ---------------------------------------------------------------------------
# Sidecar builder: media-sync manifest
# ---------------------------------------------------------------------------


def _build_media_sync_manifest(*, captured_at: datetime) -> dict[str, Any]:
    """Capture private media inventory or fail with explicit provider metadata."""
    from quickscale_core.dr_engine.orchestration import (
        _get_project_slug,
        _get_source_environment,
        _load_storage_helpers,
    )

    base_payload: dict[str, Any] = {
        "manifest_version": 1,
        "captured_at": captured_at.astimezone(timezone.utc).isoformat(),
        "project_slug": _get_project_slug(),
        "source_environment": _get_source_environment(),
    }
    try:
        storage_helpers = _load_storage_helpers()
        selection = storage_helpers.select_storage_backend(settings)
    except Exception as exc:
        return {
            **base_payload,
            "status": "unsupported",
            "reason": "storage helper is unavailable in this runtime",
            "error_type": exc.__class__.__name__,
            "storage": {
                "backend": (
                    str(
                        getattr(settings, "QUICKSCALE_STORAGE_BACKEND", "local")
                    ).strip()
                    or "local"
                ),
            },
            "inventory": [],
        }

    storage_payload: dict[str, Any] = {
        "backend": selection.backend,
        "django_backend": selection.django_backend,
        "use_s3_compatible": selection.use_s3_compatible,
    }
    if selection.use_s3_compatible:
        storage_payload.update(
            {
                "bucket_name": str(selection.options.get("bucket_name", "")),
                "endpoint_url": str(selection.options.get("endpoint_url", "")),
                "region_name": str(selection.options.get("region_name", "")),
                "querystring_auth": bool(
                    selection.options.get("querystring_auth", False)
                ),
                "access_key_id_configured": bool(
                    str(selection.options.get("access_key_id", ""))
                ),
                "secret_access_key_configured": bool(
                    str(selection.options.get("secret_access_key", ""))
                ),
            }
        )
        try:
            remote_inventory = storage_helpers.list_s3_compatible_media_inventory(
                settings
            )
        except Exception as exc:
            return {
                **base_payload,
                "status": "inventory_failed",
                "reason": str(exc),
                "error_type": exc.__class__.__name__,
                "storage": storage_payload,
                "inventory": [],
            }
        return {
            **base_payload,
            "status": "ready",
            "storage": storage_payload,
            "inventory": remote_inventory,
        }

    media_root_text = str(getattr(settings, "MEDIA_ROOT", "")).strip()
    storage_payload["media_root"] = media_root_text
    if not media_root_text:
        return {
            **base_payload,
            "status": "missing_media_root",
            "storage": storage_payload,
            "inventory": [],
        }

    media_root = Path(media_root_text)
    if not media_root.exists():
        return {
            **base_payload,
            "status": "missing_local_root",
            "storage": storage_payload,
            "inventory": [],
        }
    if not media_root.is_dir():
        return {
            **base_payload,
            "status": "invalid_local_root",
            "storage": storage_payload,
            "inventory": [],
        }

    local_inventory: list[dict[str, Any]] = []
    for file_path in sorted(path for path in media_root.rglob("*") if path.is_file()):
        file_stats = file_path.stat()
        local_inventory.append(
            {
                "relative_path": file_path.relative_to(media_root).as_posix(),
                "size_bytes": file_stats.st_size,
                "checksum_sha256": _compute_sha256(file_path),
                "modified_at": datetime.fromtimestamp(
                    file_stats.st_mtime,
                    tz=timezone.utc,
                ).isoformat(),
            }
        )

    return {
        **base_payload,
        "status": "ready",
        "storage": storage_payload,
        "inventory": local_inventory,
    }


# ---------------------------------------------------------------------------
# Sidecar builder: env-var manifest
# ---------------------------------------------------------------------------


def _build_env_var_manifest(*, captured_at: datetime) -> dict[str, Any]:
    """Capture environment variable names only, never their values."""
    from quickscale_core.dr_engine.orchestration import (
        _get_project_slug,
        _get_source_environment,
    )

    variable_names = sorted(os.environ.keys())
    return {
        "manifest_version": 1,
        "captured_at": captured_at.astimezone(timezone.utc).isoformat(),
        "project_slug": _get_project_slug(),
        "source_environment": _get_source_environment(),
        "status": "ready",
        "count": len(variable_names),
        "names": variable_names,
    }


# ---------------------------------------------------------------------------
# Sidecar builder: promotion verification placeholder
# ---------------------------------------------------------------------------


def _build_promotion_verification_placeholder(
    *,
    captured_at: datetime,
) -> dict[str, Any]:
    """Initialize the reserved promotion verification sidecar."""
    from quickscale_core.dr_engine.orchestration import (
        _get_project_slug,
        _get_source_environment,
    )

    return {
        "manifest_version": 1,
        "captured_at": captured_at.astimezone(timezone.utc).isoformat(),
        "project_slug": _get_project_slug(),
        "source_environment": _get_source_environment(),
        "status": "reserved",
        "updated_at": captured_at.astimezone(timezone.utc).isoformat(),
        "reports": [],
        "notes": "Reserved for route-specific plan and execute reports.",
        "rollback_pin": {"expires_at": None, "reason": ""},
    }


# ---------------------------------------------------------------------------
# Sidecar lifecycle: load
# ---------------------------------------------------------------------------


def _load_snapshot_sidecar_payload(
    snapshot: Any,
    filename: str,
) -> dict[str, Any]:
    """Read and validate one JSON sidecar payload for a snapshot."""
    local_path = _snapshot_sidecar_path(snapshot, filename)
    if not local_path.exists():
        raise BackupError(f"Snapshot sidecar not found: {filename}")

    try:
        payload = json.loads(local_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise BackupError(
            f"Unable to read snapshot sidecar '{filename}': {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise BackupError(f"Snapshot sidecar '{filename}' is not valid JSON") from exc

    if not isinstance(payload, dict):
        raise BackupError(f"Snapshot sidecar '{filename}' must contain a JSON object")
    return payload


# ---------------------------------------------------------------------------
# Sidecar lifecycle: persist
# ---------------------------------------------------------------------------


def _persist_snapshot_sidecar_payload(
    snapshot: Any,
    *,
    filename: str,
    kind: str,
    payload: dict[str, Any],
    policy: BackupPolicySnapshot | None = None,
    remote_uploader: Callable[..., str] | None = None,
) -> dict[str, Any]:
    """Write one sidecar payload and refresh its snapshot descriptor."""
    from quickscale_core.dr_engine.orchestration import (
        _load_active_policy_snapshot,
        _upload_snapshot_child_to_private_remote,
    )

    local_path = _snapshot_sidecar_path(snapshot, filename)
    _write_json_file(local_path, payload)

    child_descriptors_json = deepcopy(
        snapshot.child_descriptors_json
        if isinstance(snapshot.child_descriptors_json, dict)
        else {}
    )
    sidecars = child_descriptors_json.setdefault("sidecars", {})
    if not isinstance(sidecars, dict):
        sidecars = {}
        child_descriptors_json["sidecars"] = sidecars

    relative_path = _relative_snapshot_child_path(
        Path(snapshot.local_root_path), local_path
    )
    descriptor = _build_snapshot_child_descriptor(
        kind=kind,
        status="ready",
        relative_path=relative_path,
        local_path=local_path,
        size_bytes=local_path.stat().st_size,
        checksum_sha256=_compute_sha256(local_path),
        metadata={"manifest_status": str(payload.get("status", "")).strip()},
    )

    existing_descriptor = sidecars.get(filename)
    if isinstance(existing_descriptor, dict):
        existing_remote_key = str(existing_descriptor.get("remote_key", "")).strip()
        if existing_remote_key:
            descriptor["remote_key"] = existing_remote_key

    resolved_policy = policy or _load_active_policy_snapshot()
    if snapshot.remote_root_key and resolved_policy.target_mode == "private_remote":
        uploader = remote_uploader or _upload_to_private_remote
        try:
            descriptor["remote_key"] = _upload_snapshot_child_to_private_remote(
                local_path,
                policy=resolved_policy,
                snapshot_remote_root=snapshot.remote_root_key,
                relative_path=relative_path,
                remote_uploader=uploader,
            )
        except BackupError as exc:
            descriptor["status"] = "failed"
            descriptor["error"] = str(exc)
            sidecars[filename] = descriptor
            snapshot.child_descriptors_json = child_descriptors_json
            snapshot.save(update_fields=["child_descriptors_json", "updated_at"])
            raise
        except Exception as exc:
            error_message = f"Private remote upload failed for {filename}: {exc}"
            descriptor["status"] = "failed"
            descriptor["error"] = error_message
            sidecars[filename] = descriptor
            snapshot.child_descriptors_json = child_descriptors_json
            snapshot.save(update_fields=["child_descriptors_json", "updated_at"])
            raise BackupError(error_message) from exc

    sidecars[filename] = descriptor
    snapshot.child_descriptors_json = child_descriptors_json
    snapshot.save(update_fields=["child_descriptors_json", "updated_at"])
    return descriptor


# ---------------------------------------------------------------------------
# Sidecar lifecycle: capture all sidecars
# ---------------------------------------------------------------------------


def _capture_snapshot_sidecars(
    *,
    snapshot: Any,
    policy: BackupPolicySnapshot,
    captured_at: datetime,
    remote_uploader: Callable[..., str] | None,
) -> tuple[dict[str, Any], list[str]]:
    """Capture private sidecar manifests without breaking the dump-first contract."""
    from quickscale_core.dr_engine.orchestration import (
        _build_release_metadata,
        _upload_snapshot_child_to_private_remote,
    )

    snapshot_root = Path(snapshot.local_root_path)
    child_descriptors_json = deepcopy(
        snapshot.child_descriptors_json
        if isinstance(snapshot.child_descriptors_json, dict)
        else {}
    )
    sidecar_descriptors = child_descriptors_json.setdefault("sidecars", {})
    if not isinstance(sidecar_descriptors, dict):
        sidecar_descriptors = {}
        child_descriptors_json["sidecars"] = sidecar_descriptors

    failures: list[str] = []
    uploader = remote_uploader or _upload_to_private_remote
    sidecar_builders: tuple[
        tuple[str, str, Callable[[], dict[str, Any]]],
        ...,
    ] = (
        (
            _MEDIA_SYNC_MANIFEST_FILENAME,
            "media_sync_manifest",
            lambda: _build_media_sync_manifest(captured_at=captured_at),
        ),
        (
            _ENV_VAR_MANIFEST_FILENAME,
            "env_var_manifest",
            lambda: _build_env_var_manifest(captured_at=captured_at),
        ),
        (
            _RELEASE_METADATA_FILENAME,
            "release_metadata",
            lambda: _build_release_metadata(captured_at=captured_at),
        ),
        (
            _PROMOTION_VERIFICATION_FILENAME,
            "promotion_verification",
            lambda: _build_promotion_verification_placeholder(
                captured_at=captured_at,
            ),
        ),
    )

    for filename, kind, payload_builder in sidecar_builders:
        local_path = snapshot_root / filename
        relative_path = _relative_snapshot_child_path(snapshot_root, local_path)
        try:
            payload = payload_builder()
            manifest_status = str(payload.get("status", "")).strip()
            metadata = {"manifest_status": manifest_status} if manifest_status else None
            _write_json_file(local_path, payload)
            descriptor = _build_snapshot_child_descriptor(
                kind=kind,
                status="ready",
                relative_path=relative_path,
                local_path=local_path,
                size_bytes=local_path.stat().st_size,
                checksum_sha256=_compute_sha256(local_path),
                metadata=metadata,
            )
            if policy.target_mode == "private_remote":
                try:
                    remote_key = _upload_snapshot_child_to_private_remote(
                        local_path,
                        policy=policy,
                        snapshot_remote_root=snapshot.remote_root_key,
                        relative_path=relative_path,
                        remote_uploader=uploader,
                    )
                except BackupError as exc:
                    descriptor["status"] = "failed"
                    descriptor["error"] = str(exc)
                    failures.append(f"{filename}: {exc}")
                except Exception as exc:
                    error_message = (
                        f"Private remote upload failed for {filename}: {exc}"
                    )
                    descriptor["status"] = "failed"
                    descriptor["error"] = error_message
                    failures.append(f"{filename}: {error_message}")
                else:
                    descriptor["remote_key"] = remote_key
            sidecar_descriptors[filename] = descriptor
        except Exception as exc:
            cleanup_error = _cleanup_local_backup_file(local_path)
            error_message = str(exc)
            if cleanup_error is not None:
                error_message += f"; cleanup failed: {cleanup_error}"
            sidecar_descriptors[filename] = _build_snapshot_child_descriptor(
                kind=kind,
                status="failed",
                relative_path=relative_path,
                local_path=local_path,
                error=error_message,
            )
            failures.append(f"{filename}: {error_message}")

    child_descriptors_json["sidecars"] = sidecar_descriptors
    return child_descriptors_json, failures


# ---------------------------------------------------------------------------
# Private helpers referenced by multiple sidecar functions
# ---------------------------------------------------------------------------


def _upload_to_private_remote(local_path: Path, policy: BackupPolicySnapshot) -> str:
    """Default upload callback — delegated to orchestration layer."""
    from quickscale_core.dr_engine.orchestration import (
        _upload_to_private_remote as _core_upload,
    )

    return _core_upload(local_path, policy)


__all__ = [
    "_build_env_var_manifest",
    "_build_media_sync_manifest",
    "_build_promotion_verification_placeholder",
    "_capture_snapshot_sidecars",
    "_load_snapshot_sidecar_payload",
    "_persist_snapshot_sidecar_payload",
]
