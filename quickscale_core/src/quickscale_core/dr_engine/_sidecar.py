"""Sidecar building and lifecycle for DR snapshots.

Manifest building, sidecar persistence, and snapshot descriptor management.
Cross-module references resolve through the sibling modules that define
them.

SA89b Phase 1: snapshot persistence operations are routed through the
module-level ``save_snapshot`` wrapper in ``quickscale_core.dr_engine.persistence``.
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
from quickscale_core.dr_engine.persistence import save_snapshot
import quickscale_core.dr_engine.primitives as _primitives
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


def _collect_media_inventory() -> tuple[
    str, str, str, dict[str, Any] | None, list[dict[str, Any]]
]:
    """Return live media inventory state without copying any object."""
    from quickscale_core.dr_engine._metadata import _load_storage_helpers

    storage_payload: dict[str, Any]
    try:
        storage_helpers = _load_storage_helpers()
        selection = storage_helpers.select_storage_backend(settings)
    except ModuleNotFoundError as exc:
        if exc.name in (
            "quickscale_modules_storage",
            "quickscale_modules_storage.services",
        ):
            selection = None
        else:
            # Storage helper is installed but a sub-dependency is missing.
            # Fail hard — do not silently fall back to local media.
            return "unsupported", str(exc), exc.__class__.__name__, None, []
    except Exception as exc:
        return "unsupported", str(exc), exc.__class__.__name__, None, []

    if selection is not None:
        storage_payload = {
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
                return (
                    "inventory_failed",
                    str(exc),
                    exc.__class__.__name__,
                    storage_payload,
                    [],
                )
            return "ready", "", "", storage_payload, remote_inventory
    else:
        storage_payload = {"backend": "local"}

    media_root_text = str(getattr(settings, "MEDIA_ROOT", "")).strip()
    storage_payload["media_root"] = media_root_text
    if not media_root_text:
        return "missing_media_root", "", "", storage_payload, []

    media_root = Path(media_root_text)
    if not media_root.exists():
        return "missing_local_root", "", "", storage_payload, []
    if not media_root.is_dir():
        return "invalid_local_root", "", "", storage_payload, []

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
    return "ready", "", "", storage_payload, local_inventory


def _build_media_sync_manifest(
    *,
    captured_at: datetime,
    snapshot_root: Path | None = None,
) -> dict[str, Any]:
    """Capture private media inventory plus, when asked, the media bytes.

    *snapshot_root* is the snapshot that will hold the captured set.  A
    capture with no readable media source fails the snapshot instead of
    recording an inventory the backup never froze; a project with no media
    root yet records an explicitly empty capture.
    """
    from quickscale_core.dr_engine._metadata import (
        _get_project_slug,
        _get_source_environment,
    )

    base_payload: dict[str, Any] = {
        "manifest_version": _primitives._BACKUP_MANIFEST_VERSION,
        "captured_at": captured_at.astimezone(timezone.utc).isoformat(),
        "project_slug": _get_project_slug(),
        "source_environment": _get_source_environment(),
    }
    status, reason, error_type, storage_payload, inventory = _collect_media_inventory()

    if status != "ready":
        payload: dict[str, Any] = {
            **base_payload,
            "status": status,
            "inventory": [],
        }
        if storage_payload is not None:
            payload = payload | {"storage": storage_payload}
        if reason:
            payload = payload | {"reason": reason}
        if error_type:
            payload = payload | {"error_type": error_type}
        if snapshot_root is None:
            return payload

        from quickscale_core.dr_engine import _media as _media

        if status in _media._MEDIA_CAPTURE_EMPTY_SOURCE_STATUSES:
            # A project without a media root has a valid, explicitly empty
            # capture; the source status stays visible on the capture itself.
            payload["capture"] = _media._build_empty_media_capture(
                snapshot_root,
                reason=status,
            )
            payload["status"] = "ready"
            payload["source_status"] = status
            return payload

        raise BackupError(
            "Media capture cannot start because the media source is "
            f"unavailable ({status}): {reason or 'no reason reported'}"
        )

    if snapshot_root is None:
        return {
            **base_payload,
            "status": "ready",
            "storage": storage_payload,
            "inventory": inventory,
        }

    from quickscale_core.dr_engine import _media as _media

    try:
        source_runtime = _media._resolve_media_runtime(settings)
        capture, captured_inventory = _media._capture_media_objects(
            inventory=inventory,
            snapshot_root=snapshot_root,
            source_runtime=source_runtime,
        )
    except BackupError:
        raise
    except Exception as exc:
        raise BackupError(f"Media capture failed: {exc}") from exc

    return {
        **base_payload,
        "status": "ready",
        "storage": storage_payload,
        "inventory": captured_inventory,
        "capture": capture,
    }


# ---------------------------------------------------------------------------
# Sidecar builder: env-var manifest
# ---------------------------------------------------------------------------


def _build_env_var_manifest(*, captured_at: datetime) -> dict[str, Any]:
    """Capture environment variable names only, never their values."""
    from quickscale_core.dr_engine._metadata import (
        _get_project_slug,
        _get_source_environment,
    )

    variable_names = sorted(os.environ.keys())
    return {
        "manifest_version": _primitives._BACKUP_MANIFEST_VERSION,
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
    from quickscale_core.dr_engine._metadata import (
        _get_project_slug,
        _get_source_environment,
    )

    return {
        "manifest_version": _primitives._BACKUP_MANIFEST_VERSION,
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
    from quickscale_core.dr_engine._policy import _load_active_policy_snapshot
    from quickscale_core.dr_engine._remote import (
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
            save_snapshot(
                snapshot, update_fields=["child_descriptors_json", "updated_at"]
            )
            raise
        except Exception as exc:
            error_message = f"Private remote upload failed for {filename}: {exc}"
            descriptor["status"] = "failed"
            descriptor["error"] = error_message
            sidecars[filename] = descriptor
            snapshot.child_descriptors_json = child_descriptors_json
            save_snapshot(
                snapshot, update_fields=["child_descriptors_json", "updated_at"]
            )
            raise BackupError(error_message) from exc

    sidecars[filename] = descriptor
    snapshot.child_descriptors_json = child_descriptors_json
    save_snapshot(snapshot, update_fields=["child_descriptors_json", "updated_at"])
    return descriptor


# ---------------------------------------------------------------------------
# Sidecar lifecycle: capture all sidecars
# ---------------------------------------------------------------------------


def _preserved_media_sidecar_payload(snapshot: Any) -> dict[str, Any] | None:
    """Return an existing healthy media manifest that must not be recaptured.

    A resume retries outstanding sidecar persistence; it must not replace a
    media set the snapshot already froze with whatever is live at resume time.
    """
    from quickscale_core.dr_engine import _media as _media

    try:
        manifest = _media._load_snapshot_media_manifest(snapshot)
    except BackupError:
        return None
    capture = manifest.get("capture")
    if not isinstance(capture, dict):
        return None
    capture_status = str(capture.get("status", "")).strip()
    if capture_status not in _media._MEDIA_CAPTURE_READY_STATUSES:
        return None
    if capture_status == _media._MEDIA_CAPTURE_STATUS_CAPTURED:
        issues = _media._collect_snapshot_media_capture_issues(
            snapshot,
            verify_checksums=True,
        )
        if issues:
            return None
    return manifest


def _capture_snapshot_sidecars(
    *,
    snapshot: Any,
    policy: BackupPolicySnapshot,
    captured_at: datetime,
    remote_uploader: Callable[..., str] | None,
) -> tuple[dict[str, Any], list[str]]:
    """Capture private sidecar manifests without breaking the dump-first contract."""
    from quickscale_core.dr_engine._metadata import _build_release_metadata
    from quickscale_core.dr_engine._remote import (
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
            lambda: _build_media_sync_manifest(
                captured_at=captured_at,
                snapshot_root=snapshot_root,
            ),
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

    preserved_media_payload = _preserved_media_sidecar_payload(snapshot)
    for filename, kind, payload_builder in sidecar_builders:
        local_path = snapshot_root / filename
        relative_path = _relative_snapshot_child_path(snapshot_root, local_path)
        try:
            payload = (
                preserved_media_payload
                if filename == _MEDIA_SYNC_MANIFEST_FILENAME
                and preserved_media_payload is not None
                else payload_builder()
            )
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
            if filename == _MEDIA_SYNC_MANIFEST_FILENAME and isinstance(
                payload.get("capture"), dict
            ):
                media_descriptor = _record_media_capture_descriptor(
                    snapshot_root=snapshot_root,
                    snapshot_remote_root=snapshot.remote_root_key,
                    payload=payload,
                    policy=policy,
                    uploader=uploader,
                    failures=failures,
                )
                if media_descriptor:
                    child_descriptors_json["media"] = media_descriptor
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


def _record_media_capture_descriptor(
    *,
    snapshot_root: Path,
    snapshot_remote_root: str,
    payload: dict[str, Any],
    policy: BackupPolicySnapshot,
    uploader: Callable[..., str],
    failures: list[str],
) -> dict[str, Any]:
    """Describe the captured media set and upload it for private-remote targets."""
    capture = payload.get("capture")
    if not isinstance(capture, dict):
        return {}

    relative_root = str(
        capture.get("relative_root") or _primitives._SNAPSHOT_MEDIA_DIRECTORY_NAME
    )
    capture_status = str(capture.get("status", "")).strip()
    descriptor = _build_snapshot_child_descriptor(
        kind="media_capture",
        status="ready",
        relative_path=relative_root,
        local_path=snapshot_root / relative_root,
        metadata={
            "capture_status": capture_status,
            "file_count": capture.get("file_count", 0),
            "total_bytes": capture.get("total_bytes", 0),
        },
    )
    if policy.target_mode != "private_remote" or capture_status != "captured":
        return descriptor

    from quickscale_core.dr_engine._remote import (
        _upload_snapshot_child_to_private_remote,
    )

    inventory = payload.get("inventory", [])
    remote_keys: list[str] = []
    for entry in inventory if isinstance(inventory, list) else []:
        if not isinstance(entry, dict):
            continue
        relative_path = str(entry.get("snapshot_relative_path", "")).strip()
        if not relative_path:
            continue
        try:
            remote_keys.append(
                _upload_snapshot_child_to_private_remote(
                    snapshot_root / relative_path,
                    policy=policy,
                    snapshot_remote_root=snapshot_remote_root,
                    relative_path=relative_path,
                    remote_uploader=uploader,
                )
            )
        except BackupError as exc:
            descriptor["status"] = "failed"
            descriptor["error"] = str(exc)
            descriptor["remote_keys"] = remote_keys
            failures.append(f"{relative_path}: {exc}")
            return descriptor
        except Exception as exc:
            error_message = f"Private remote upload failed for {relative_path}: {exc}"
            descriptor["status"] = "failed"
            descriptor["error"] = error_message
            descriptor["remote_keys"] = remote_keys
            failures.append(f"{relative_path}: {error_message}")
            return descriptor

    descriptor["remote_keys"] = remote_keys
    return descriptor


def _upload_to_private_remote(local_path: Path, policy: BackupPolicySnapshot) -> str:
    """Default upload callback — delegated to orchestration layer."""
    from quickscale_core.dr_engine._remote import (
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
