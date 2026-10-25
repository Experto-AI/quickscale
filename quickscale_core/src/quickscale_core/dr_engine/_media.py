"""Media runtime resolution and snapshot media sync."""

from __future__ import annotations


from pathlib import Path
from typing import Any


import quickscale_core.dr_engine._state as _state
import quickscale_core.dr_engine._sidecar as _sidecar
import quickscale_core.dr_engine.primitives as _primitives
import django.conf as _conf
import quickscale_core.dr_engine._metadata as _metadata
import os
import shutil
import stat
import tempfile
import quickscale_core.dr_engine._types as _types


# At most this many bytes of one relayed object stay in memory during an
# s3-to-s3 copy; larger objects roll to an on-disk temporary file.
_MEDIA_RELAY_SPOOL_MAX_BYTES = 64 * 1024 * 1024

_MEDIA_CAPTURE_STATUS_CAPTURED = "captured"
_MEDIA_CAPTURE_STATUS_EMPTY = "empty"
_MEDIA_CAPTURE_READY_STATUSES = frozenset(
    {_MEDIA_CAPTURE_STATUS_CAPTURED, _MEDIA_CAPTURE_STATUS_EMPTY}
)
_MEDIA_CAPTURE_EMPTY_SOURCE_STATUSES = frozenset(
    {"missing_media_root", "missing_local_root"}
)


def _normalize_media_relative_path(relative_path: Any) -> str:
    """Return one safe snapshot-relative media path or refuse it.

    Media names arrive from a manifest or an object store, so a traversal
    segment must fail the operation instead of escaping the snapshot root.
    """
    normalized = str(relative_path or "").strip().replace("\\", "/").lstrip("/")
    if not normalized:
        raise _primitives.BackupError("Media capture entry has an empty relative path")

    path = Path(normalized)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise _primitives.BackupError(
            f"Media path '{relative_path}' is not a safe relative path"
        )
    return path.as_posix()


def _snapshot_media_root(snapshot: Any) -> Path:
    """Return the captured media directory under one snapshot root."""
    return (
        Path(str(snapshot.local_root_path)) / _primitives._SNAPSHOT_MEDIA_DIRECTORY_NAME
    )


def _capture_media_objects(
    *,
    inventory: list[dict[str, Any]],
    snapshot_root: Path,
    source_runtime: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Copy every inventoried media object into the snapshot and verify it.

    Returns the capture descriptor and the inventory enriched with the
    recorded snapshot path and content checksum.  Any unreadable or changed
    object fails the capture; a backup must never claim a media set it did not
    actually freeze.
    """
    snapshot_media_root = snapshot_root / _primitives._SNAPSHOT_MEDIA_DIRECTORY_NAME
    _primitives._ensure_private_directory(snapshot_media_root)
    target_runtime = {
        "backend": "local",
        "use_s3_compatible": False,
        "media_root": snapshot_media_root,
    }

    captured_inventory: list[dict[str, Any]] = []
    total_bytes = 0
    for entry in inventory:
        if not isinstance(entry, dict):
            raise _primitives.BackupError("Media inventory entry must be an object")
        relative_path = _normalize_media_relative_path(entry.get("relative_path"))
        target_path = snapshot_media_root / relative_path
        _primitives._ensure_private_directory(target_path.parent)

        copied = _copy_media_item(
            relative_path=relative_path,
            source_runtime=source_runtime,
            target_runtime=target_runtime,
        )
        if not copied:
            raise _primitives.BackupError(
                f"Media capture could not read '{relative_path}' from the "
                "source media backend"
            )

        _primitives._ensure_private_file(target_path)
        digest = _primitives._compute_sha256(target_path)
        recorded_digest = str(entry.get("checksum_sha256", "")).strip()
        if recorded_digest and digest != recorded_digest:
            raise _primitives.BackupError(
                f"Media capture detected changed content for '{relative_path}'"
            )

        size_bytes = target_path.stat().st_size
        recorded_size = entry.get("size_bytes")
        if (
            isinstance(recorded_size, int)
            and not isinstance(recorded_size, bool)
            and size_bytes != recorded_size
        ):
            raise _primitives.BackupError(
                f"Media capture detected a changed size for '{relative_path}'"
            )
        captured_inventory.append(
            {
                **entry,
                "relative_path": relative_path,
                "snapshot_relative_path": (
                    f"{_primitives._SNAPSHOT_MEDIA_DIRECTORY_NAME}/{relative_path}"
                ),
                "snapshot_size_bytes": size_bytes,
                "snapshot_checksum_sha256": digest,
            }
        )
        total_bytes += size_bytes

    return (
        {
            "status": (
                _MEDIA_CAPTURE_STATUS_CAPTURED
                if captured_inventory
                else _MEDIA_CAPTURE_STATUS_EMPTY
            ),
            "relative_root": _primitives._SNAPSHOT_MEDIA_DIRECTORY_NAME,
            "file_count": len(captured_inventory),
            "total_bytes": total_bytes,
        },
        captured_inventory,
    )


def _build_empty_media_capture(snapshot_root: Path, *, reason: str) -> dict[str, Any]:
    """Record an empty captured set for a project with no media root yet."""
    _primitives._ensure_private_directory(
        snapshot_root / _primitives._SNAPSHOT_MEDIA_DIRECTORY_NAME
    )
    return {
        "status": _MEDIA_CAPTURE_STATUS_EMPTY,
        "relative_root": _primitives._SNAPSHOT_MEDIA_DIRECTORY_NAME,
        "file_count": 0,
        "total_bytes": 0,
        "reason": reason,
    }


def _load_snapshot_media_manifest(snapshot: Any) -> dict[str, Any]:
    """Return one snapshot's media manifest payload."""
    return _sidecar._load_snapshot_sidecar_payload(
        snapshot, _primitives._MEDIA_SYNC_MANIFEST_FILENAME
    )


def _get_snapshot_media_capture(snapshot: Any) -> dict[str, Any] | None:
    """Return the recorded media capture descriptor, or ``None`` when absent."""
    try:
        manifest = _load_snapshot_media_manifest(snapshot)
    except _primitives.BackupError:
        return None
    capture = manifest.get("capture")
    return capture if isinstance(capture, dict) else None


def _collect_snapshot_media_capture_issues(
    snapshot: Any,
    *,
    verify_checksums: bool,
) -> list[str]:
    """Return why a snapshot's captured media set cannot be trusted.

    A snapshot without a capture descriptor is a legacy database-only
    recovery point and reports no issue.  A recorded capture must name every
    file it froze; checksums are verified only when the caller reads the bytes.
    """
    try:
        manifest = _load_snapshot_media_manifest(snapshot)
    except _primitives.BackupError as exc:
        return [str(exc)]

    capture = manifest.get("capture")
    if not isinstance(capture, dict):
        return []

    status = str(capture.get("status", "")).strip()
    if status == _MEDIA_CAPTURE_STATUS_EMPTY:
        return []
    if status != _MEDIA_CAPTURE_STATUS_CAPTURED:
        return [
            "media capture status is "
            f"'{status or 'unknown'}' instead of '{_MEDIA_CAPTURE_STATUS_CAPTURED}'"
        ]

    inventory = manifest.get("inventory")
    if not isinstance(inventory, list):
        return ["media capture inventory is not a list"]

    media_root = _snapshot_media_root(snapshot)
    issues: list[str] = []
    for entry in inventory:
        if not isinstance(entry, dict):
            issues.append("media capture inventory entry is not an object")
            continue
        try:
            relative_path = _normalize_media_relative_path(entry.get("relative_path"))
        except _primitives.BackupError as exc:
            issues.append(str(exc))
            continue

        captured_path = media_root / relative_path
        if not captured_path.is_file():
            issues.append(f"captured media file is missing: {relative_path}")
            continue

        recorded_size = entry.get("snapshot_size_bytes", entry.get("size_bytes"))
        if (
            isinstance(recorded_size, int)
            and not isinstance(recorded_size, bool)
            and captured_path.stat().st_size != recorded_size
        ):
            issues.append(f"captured media file changed size: {relative_path}")

        expected_checksum = str(entry.get("snapshot_checksum_sha256", "")).strip()
        if (
            verify_checksums
            and expected_checksum
            and _primitives._compute_sha256(captured_path) != expected_checksum
        ):
            issues.append(f"captured media file changed content: {relative_path}")
    return issues


def _snapshot_media_capture_is_remote_available(snapshot: Any) -> bool:
    """Return whether the media descriptor records every frozen remote object."""
    descriptors = (
        snapshot.child_descriptors_json
        if isinstance(snapshot.child_descriptors_json, dict)
        else {}
    )
    descriptor = descriptors.get("media")
    if not isinstance(descriptor, dict):
        return False
    if str(descriptor.get("status", "")).strip() != "ready":
        return False
    metadata = descriptor.get("metadata")
    if not isinstance(metadata, dict):
        return False

    capture_status = str(metadata.get("capture_status", "")).strip()
    if capture_status == _MEDIA_CAPTURE_STATUS_EMPTY:
        return True
    if capture_status != _MEDIA_CAPTURE_STATUS_CAPTURED:
        return False

    remote_keys = descriptor.get("remote_keys")
    file_count = metadata.get("file_count")
    if (
        not isinstance(remote_keys, list)
        or not isinstance(file_count, int)
        or isinstance(file_count, bool)
        or file_count < 1
    ):
        return False
    return len(remote_keys) >= file_count


def _snapshot_media_capture_integrity_issues(snapshot: Any) -> list[str]:
    """Return integrity issues for a captured set, or none when remote-only.

    A snapshot with no media descriptor and no local manifest predates the
    media capture and stays a database-only recovery point.  A version 2
    manifest must record its capture, and a captured set is either complete
    locally or proven complete by the descriptor's remote-key list.
    """
    descriptors = (
        snapshot.child_descriptors_json
        if isinstance(snapshot.child_descriptors_json, dict)
        else {}
    )
    has_media_descriptor = isinstance(descriptors.get("media"), dict)
    if _snapshot_media_capture_is_remote_available(snapshot):
        return []

    try:
        manifest = _load_snapshot_media_manifest(snapshot)
    except _primitives.BackupError as exc:
        if not has_media_descriptor:
            # A legacy remote-only snapshot records no media descriptor.
            return []
        return [str(exc)]

    manifest_version = manifest.get("manifest_version")
    if isinstance(manifest_version, bool) or not isinstance(manifest_version, int):
        manifest_version = None
    capture = manifest.get("capture")
    if not isinstance(capture, dict):
        if (
            manifest_version is not None
            and manifest_version >= _primitives._BACKUP_MANIFEST_VERSION_WITH_MEDIA
        ):
            return ["media manifest records no complete captured media set"]
        return []
    return _collect_snapshot_media_capture_issues(
        snapshot,
        verify_checksums=False,
    )


def _resolve_captured_media_source(snapshot: Any) -> dict[str, Any]:
    """Return the local runtime that reads a snapshot's captured media set."""
    return {
        "backend": "local",
        "use_s3_compatible": False,
        "media_root": _snapshot_media_root(snapshot),
    }


def _build_s3_storage_from_selection(selection: Any) -> Any:
    """Construct an s3-compatible storage object from one backend selection."""
    from storages.backends.s3 import S3Storage

    options: dict[str, Any] = {
        "bucket_name": str(selection.options.get("bucket_name", "")).strip(),
        "querystring_auth": bool(selection.options.get("querystring_auth", False)),
        "default_acl": str(selection.options.get("default_acl", "")).strip(),
    }
    if endpoint_url := str(selection.options.get("endpoint_url", "")).strip():
        options["endpoint_url"] = endpoint_url
    if region_name := str(selection.options.get("region_name", "")).strip():
        options["region_name"] = region_name
    if access_key := str(selection.options.get("access_key_id", "")).strip():
        options["access_key"] = access_key
    if secret_key := str(selection.options.get("secret_access_key", "")).strip():
        options["secret_key"] = secret_key
    return S3Storage(**options)


def _resolve_media_runtime(
    settings_obj: Any,
    *,
    require_s3_compatible: bool = False,
) -> dict[str, Any]:
    """Resolve local or s3-compatible media runtime settings."""
    try:
        selection = _metadata._load_storage_helpers().select_storage_backend(
            settings_obj
        )
    except ModuleNotFoundError as exc:
        if exc.name in (
            "quickscale_modules_storage",
            "quickscale_modules_storage.services",
        ):
            selection = None
        else:
            # Storage helper is installed but a sub-dependency is missing.
            # Fail hard — do not silently fall back to local media.
            raise _primitives.BackupConfigurationError(str(exc)) from exc
    except Exception as exc:
        raise _primitives.BackupConfigurationError(str(exc)) from exc

    if selection is not None:
        if require_s3_compatible and not selection.use_s3_compatible:
            raise _primitives.BackupConfigurationError(
                "Railway-target media sync requires an s3-compatible target media backend; "
                "local MEDIA_ROOT is not a supported Railway target."
            )
        if selection.use_s3_compatible:
            bucket_name = str(selection.options.get("bucket_name", "")).strip()
            if not bucket_name:
                raise _primitives.BackupConfigurationError(
                    "S3-compatible media sync requires AWS_STORAGE_BUCKET_NAME"
                )
            return {
                "backend": selection.backend,
                "use_s3_compatible": True,
                "storage": _build_s3_storage_from_selection(selection),
                "bucket_name": bucket_name,
            }
    else:
        # Storage helpers unavailable — fall back to local detection.
        if require_s3_compatible:
            raise _primitives.BackupConfigurationError(
                "Railway-target media sync requires an s3-compatible target media backend; "
                "storage helper is unavailable in this runtime."
            )

    media_root_text = str(
        _metadata._read_setting_value(settings_obj, "MEDIA_ROOT", "")
    ).strip()
    if not media_root_text:
        raise _primitives.BackupConfigurationError(
            "Local media sync requires MEDIA_ROOT to be configured"
        )
    return {
        "backend": "local",
        "use_s3_compatible": False,
        "media_root": Path(media_root_text),
    }


def _storage_object_key(storage: Any, relative_path: str) -> str:
    """Build the provider object key for one media item."""
    location_prefix = str(getattr(storage, "location", "") or "").strip().strip("/")
    relative_segment = relative_path.lstrip("/")
    if location_prefix:
        return f"{location_prefix}/{relative_segment}"
    return relative_segment


def _copy_media_item(
    *,
    relative_path: str,
    source_runtime: dict[str, Any],
    target_runtime: dict[str, Any],
) -> bool:
    """Copy one media item between local and s3-compatible runtimes."""
    if not source_runtime["use_s3_compatible"]:
        source_path = Path(source_runtime["media_root"]) / relative_path
        if not source_path.exists():
            return False
        if not target_runtime["use_s3_compatible"]:
            target_path = Path(target_runtime["media_root"]) / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            existing_mode = (
                stat.S_IMODE(target_path.stat().st_mode)
                if target_path.exists()
                else None
            )
            shutil.copy2(source_path, target_path)
            if existing_mode is not None:
                # Keep the destination's serving permissions; copy2 would
                # otherwise replace them with the private snapshot mode.
                os.chmod(target_path, existing_mode)
            else:
                # Snapshot files stay private (0600); a first published copy
                # gets the process umask so the serving user can read it.
                current_umask = os.umask(0)
                os.umask(current_umask)
                os.chmod(target_path, 0o666 & ~current_umask)
            return True

        target_storage = target_runtime["storage"]
        target_storage.connection.meta.client.upload_file(
            str(source_path),
            target_runtime["bucket_name"],
            _storage_object_key(target_storage, relative_path),
        )
        return True

    source_storage = source_runtime["storage"]
    if not target_runtime["use_s3_compatible"]:
        target_path = Path(target_runtime["media_root"]) / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        # The storage API's ``open()`` spools each whole object in memory
        # (``AWS_S3_MAX_MEMORY_SIZE`` defaults to unbounded), so stream
        # through the provider client's chunked download instead, into an
        # exclusively created sibling file that replaces the destination
        # only on success.
        download_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=target_path.parent,
                prefix=f".{target_path.name}.",
                suffix=".part",
                delete=False,
            ) as download_handle:
                download_path = Path(download_handle.name)
                source_storage.connection.meta.client.download_fileobj(
                    source_runtime["bucket_name"],
                    _storage_object_key(source_storage, relative_path),
                    download_handle,
                )
            # The staging file was created private; publish it with the mode the
            # destination had, or the umask default a plain create would get.
            if target_path.exists():
                shutil.copymode(target_path, download_path)
            else:
                current_umask = os.umask(0)
                os.umask(current_umask)
                os.chmod(download_path, 0o666 & ~current_umask)
            download_path.replace(target_path)
        except Exception:
            # Any failure after staging begins — the download, the mode apply,
            # or the publish rename — removes the staging file.
            if download_path is not None:
                download_path.unlink(missing_ok=True)
            raise
        return True

    target_storage = target_runtime["storage"]
    # S3Storage.open() spools whole objects in memory, so relay through the
    # provider clients via a memory-bounded spool instead of the storage API.
    with tempfile.SpooledTemporaryFile(
        max_size=_MEDIA_RELAY_SPOOL_MAX_BYTES
    ) as staging:
        source_storage.connection.meta.client.download_fileobj(
            source_runtime["bucket_name"],
            _storage_object_key(source_storage, relative_path),
            staging,
        )
        staging.seek(0)
        target_storage.connection.meta.client.upload_fileobj(
            staging,
            target_runtime["bucket_name"],
            _storage_object_key(target_storage, relative_path),
        )
    return True


def sync_backup_snapshot_media(
    snapshot_id: str,
    *,
    dry_run: bool = False,
    target_runtime_settings: dict[str, str],
) -> dict[str, Any]:
    """Validate or restore one snapshot's media set against target env overrides.

    A captured media set is copied from the snapshot, so the restored files
    match the frozen recovery point.  A legacy snapshot without captured media
    falls back to the live source backend and names that source in the result.
    """
    snapshot = _state.get_backup_snapshot(snapshot_id)
    media_manifest = _sidecar._load_snapshot_sidecar_payload(
        snapshot, _primitives._MEDIA_SYNC_MANIFEST_FILENAME
    )
    manifest_status = str(media_manifest.get("status", "")).strip()
    if manifest_status != "ready":
        raise _primitives.BackupError(
            "Media sync requires a ready media manifest, found status "
            f"'{manifest_status or 'unknown'}'."
        )

    inventory = media_manifest.get("inventory", [])
    if not isinstance(inventory, list):
        raise _primitives.BackupError("Media manifest inventory must be a list")

    target_runtime = _resolve_media_runtime(
        target_runtime_settings,
        require_s3_compatible=(
            str(target_runtime_settings.get(_types._ROUTE_KIND_KEY, "")).strip()
            == "railway"
        ),
    )

    manifest_version = media_manifest.get("manifest_version")
    if isinstance(manifest_version, bool) or not isinstance(manifest_version, int):
        manifest_version = None
    if manifest_version not in _primitives._SUPPORTED_BACKUP_MANIFEST_VERSIONS:
        raise _primitives.BackupError(
            "Media sync requires a supported media manifest version, found "
            f"'{manifest_version if manifest_version is not None else 'unknown'}'."
        )

    capture = media_manifest.get("capture")
    capture_status = (
        str(capture.get("status", "")).strip() if isinstance(capture, dict) else ""
    )
    if capture_status and capture_status not in _MEDIA_CAPTURE_READY_STATUSES:
        raise _primitives.BackupError(
            "Media sync requires a completed media capture, found status "
            f"'{capture_status}'."
        )
    if not capture_status and manifest_version >= 2:
        raise _primitives.BackupError(
            "Media sync refuses a version "
            f"{manifest_version} manifest without a completed captured media set."
        )

    if capture_status:
        capture_issues = _collect_snapshot_media_capture_issues(
            snapshot,
            verify_checksums=True,
        )
        if capture_issues:
            raise _primitives.BackupError(
                "Media sync cannot restore the captured set: "
                + "; ".join(capture_issues)
            )
        source_runtime = _resolve_captured_media_source(snapshot)
        source_kind = "snapshot"
    else:
        # Only a validated version 1 snapshot may read the media that is live
        # now; a version 2 manifest without a capture is a damaged backup.
        source_runtime = _resolve_media_runtime(_conf.settings)
        source_kind = "live"

    strategy = f"{source_runtime['backend']}_to_{target_runtime['backend']}"
    planned_count = 0
    copied_count = 0
    missing_paths: list[str] = []

    for entry in inventory:
        if not isinstance(entry, dict):
            continue
        try:
            relative_path = _normalize_media_relative_path(entry.get("relative_path"))
        except _primitives.BackupError as exc:
            raise _primitives.BackupError(str(exc)) from exc
        if not relative_path:
            continue

        planned_count += 1
        if dry_run:
            if (
                not source_runtime["use_s3_compatible"]
                and not (Path(source_runtime["media_root"]) / relative_path).exists()
            ):
                missing_paths.append(relative_path)
            continue

        copied = _copy_media_item(
            relative_path=relative_path,
            source_runtime=source_runtime,
            target_runtime=target_runtime,
        )
        if copied:
            copied_count += 1
        else:
            missing_paths.append(relative_path)

    status = "ready" if dry_run else "completed"
    if missing_paths:
        status = "partial"

    return {
        "snapshot_id": snapshot.snapshot_id,
        "status": status,
        "dry_run": dry_run,
        "source": source_kind,
        "strategy": strategy,
        "source_backend": source_runtime["backend"],
        "target_backend": target_runtime["backend"],
        "planned_count": planned_count,
        "copied_count": copied_count,
        "missing_paths": missing_paths,
    }
