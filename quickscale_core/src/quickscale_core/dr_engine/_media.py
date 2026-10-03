"""Media runtime resolution and snapshot media sync."""

from __future__ import annotations


from pathlib import Path
from typing import Any

import quickscale_core.dr_engine.orchestration as _orchestration


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
        selection = _orchestration._load_storage_helpers().select_storage_backend(
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
            raise _orchestration.BackupConfigurationError(str(exc)) from exc
    except Exception as exc:
        raise _orchestration.BackupConfigurationError(str(exc)) from exc

    if selection is not None:
        if require_s3_compatible and not selection.use_s3_compatible:
            raise _orchestration.BackupConfigurationError(
                "Railway-target media sync requires an s3-compatible target media backend; "
                "local MEDIA_ROOT is not a supported Railway target."
            )
        if selection.use_s3_compatible:
            bucket_name = str(selection.options.get("bucket_name", "")).strip()
            if not bucket_name:
                raise _orchestration.BackupConfigurationError(
                    "S3-compatible media sync requires AWS_STORAGE_BUCKET_NAME"
                )
            return {
                "backend": selection.backend,
                "use_s3_compatible": True,
                "storage": _orchestration._build_s3_storage_from_selection(selection),
                "bucket_name": bucket_name,
            }
    else:
        # Storage helpers unavailable — fall back to local detection.
        if require_s3_compatible:
            raise _orchestration.BackupConfigurationError(
                "Railway-target media sync requires an s3-compatible target media backend; "
                "storage helper is unavailable in this runtime."
            )

    media_root_text = str(
        _orchestration._read_setting_value(settings_obj, "MEDIA_ROOT", "")
    ).strip()
    if not media_root_text:
        raise _orchestration.BackupConfigurationError(
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
            _orchestration.shutil.copy2(source_path, target_path)
            return True

        target_storage = target_runtime["storage"]
        target_storage.connection.meta.client.upload_file(
            str(source_path),
            target_runtime["bucket_name"],
            _orchestration._storage_object_key(target_storage, relative_path),
        )
        return True

    source_storage = source_runtime["storage"]
    if not target_runtime["use_s3_compatible"]:
        target_path = Path(target_runtime["media_root"]) / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with source_storage.open(relative_path, mode="rb") as source_handle:
            target_path.write_bytes(source_handle.read())
        return True

    target_storage = target_runtime["storage"]
    with source_storage.open(relative_path, mode="rb") as source_handle:
        target_storage.connection.meta.client.upload_fileobj(
            source_handle,
            target_runtime["bucket_name"],
            _orchestration._storage_object_key(target_storage, relative_path),
        )
    return True


def sync_backup_snapshot_media(
    snapshot_id: str,
    *,
    dry_run: bool = False,
    target_runtime_settings: dict[str, str],
) -> dict[str, Any]:
    """Dry-run or execute media sync for one snapshot using target env overrides."""
    snapshot = _orchestration.get_backup_snapshot(snapshot_id)
    media_manifest = _orchestration._load_snapshot_sidecar_payload(
        snapshot, _orchestration._MEDIA_SYNC_MANIFEST_FILENAME
    )
    manifest_status = str(media_manifest.get("status", "")).strip()
    if manifest_status != "ready":
        raise _orchestration.BackupError(
            "Media sync requires a ready media manifest, found status "
            f"'{manifest_status or 'unknown'}'."
        )

    inventory = media_manifest.get("inventory", [])
    if not isinstance(inventory, list):
        raise _orchestration.BackupError("Media manifest inventory must be a list")

    source_runtime = _orchestration._resolve_media_runtime(_orchestration.settings)
    target_runtime = _orchestration._resolve_media_runtime(
        target_runtime_settings,
        require_s3_compatible=(
            str(target_runtime_settings.get(_orchestration._ROUTE_KIND_KEY, "")).strip()
            == "railway"
        ),
    )
    strategy = f"{source_runtime['backend']}_to_{target_runtime['backend']}"
    planned_count = 0
    copied_count = 0
    missing_paths: list[str] = []

    for entry in inventory:
        if not isinstance(entry, dict):
            continue
        relative_path = str(entry.get("relative_path", "")).strip().lstrip("/")
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

        copied = _orchestration._copy_media_item(
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
        "strategy": strategy,
        "source_backend": source_runtime["backend"],
        "target_backend": target_runtime["backend"],
        "planned_count": planned_count,
        "copied_count": copied_count,
        "missing_paths": missing_paths,
    }
