"""DR orchestration — Django-aware backup/snapshot capture, sidecar lifecycle,
report building, prune, media sync, and remote storage operations.

This module owns the orchestration logic extracted from the embeddable backups
module.  It is Django-aware (imports models and Django settings) but does not
depend on ``services.py``.  ``services.py`` imports from this module and adds
thin Django-facing wrappers where needed.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from importlib import import_module
from io import StringIO
from pathlib import Path
from tempfile import mkdtemp
from typing import TYPE_CHECKING, Any, Protocol, cast

import django
from django.apps import apps
from django.conf import settings
from django.core.files import File
from django.core.management import call_command
from django.db import DatabaseError
from django.utils import timezone as django_timezone

from quickscale_core.dr_engine.primitives import (
    BackupConfigurationError,
    BackupError,
    BackupPolicySnapshot,
    ShellCommandRunner,
    _compute_sha256,
    _database_engine_family,
    _dump_postgresql_database,
    _ENV_VAR_MANIFEST_FILENAME,
    _extract_any_major_version,
    _extract_leading_major_version,
    _get_postgresql_tool_version,
    _MEDIA_SYNC_MANIFEST_FILENAME,
    _mint_snapshot_id,
    _PROMOTION_VERIFICATION_FILENAME,
    _RELEASE_METADATA_FILENAME,
    _REQUIRED_POSTGRESQL_MAJOR,
    _REQUIRED_SNAPSHOT_SIDECAR_FILENAMES,
    _SNAPSHOT_DATABASE_DIRECTORY_NAME,
)
from quickscale_core.dr_engine.recovery import (
    ArtifactLike,
    BackupRestoreBlocked,
    RemoteMaterializer,
    ResolvedRestoreSource,
    RestoreResult,
    RestoreSourceResolutionMode,
    RestoreWarning,
    _collect_local_backup_validation_issues,
    _detect_restore_file_format,
    _execute_restore_for_resolved_source as _core_execute_restore_for_resolved_source,
    _get_restore_compatibility_issues as _core_get_restore_compatibility_issues,
    _resolve_restore_source as _core_resolve_restore_source,
    _restore_execution_allowed as _core_restore_execution_allowed,
)
from quickscale_core.dr_engine.verification import (
    _build_clear_rollback_pin_fields,
    _build_verification_payload,
    _compute_rollback_pin_fields,
    _validate_verification_inputs,
)

if TYPE_CHECKING:
    from django.contrib.auth.base_user import AbstractBaseUser

from quickscale_modules_backups.models import (
    BackupArtifact,
    BackupPolicy,
    BackupSnapshot,
)  # noqa: E402  # isort:skip

# AF6 Phase 3 — re-exports from concern-focused sibling modules.
# These names are defined in the sibling modules and re-exported here so that
# existing import paths (quickscale_core.dr_engine.orchestration.xxx) and test
# patch targets continue to work unchanged.
from quickscale_core.dr_engine._lock import (  # noqa: E402, F401
    BackupLockError,
    StagedAdminRestoreUpload,
    _acquire_backup_lock,
    _backup_creation_lock,
    _cleanup_local_backup_file,
    _clear_stale_backup_lock,
    _release_backup_lock,
)
from quickscale_core.dr_engine._paths import (  # noqa: E402, F401
    _build_snapshot_capture_resume_policy,
    _build_snapshot_database_descriptor,
    _build_snapshot_local_root,
    _build_snapshot_lock_directory,
    _build_snapshot_remote_root,
    _get_snapshot_report_children,
    _replace_policy_remote_prefix,
    _snapshot_capture_is_complete,
    _snapshot_sidecar_path,
    _snapshot_uses_private_remote,
    build_backup_filename,
    get_local_backup_directory,
)
from quickscale_core.dr_engine._sidecar import (  # noqa: E402, F401
    _build_env_var_manifest,
    _build_media_sync_manifest,
    _build_promotion_verification_placeholder,
    _capture_snapshot_sidecars,
    _load_snapshot_sidecar_payload,
    _persist_snapshot_sidecar_payload,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ROUTE_KIND_KEY = "ROUTE_KIND"

# ---------------------------------------------------------------------------
# Protocols (Django-aware — used by orchestration functions)
# ---------------------------------------------------------------------------


class _RemoteUploader(Protocol):
    """Protocol used for optional private remote artifact offload."""

    def __call__(self, local_path: Path, policy: BackupPolicySnapshot) -> str: ...


class _RemoteDeleter(Protocol):
    """Protocol used for private remote artifact deletion."""

    def __call__(self, remote_key: str, policy: BackupPolicySnapshot) -> None: ...


class _StorageBackendSelectionLike(Protocol):
    """Typed shape used from the storage helper module."""

    backend: str
    django_backend: str
    use_s3_compatible: bool
    options: dict[str, Any]


class _StorageHelpersModule(Protocol):
    """Typed subset of the storage helper module used by backups."""

    def list_s3_compatible_media_inventory(
        self,
        settings_obj: Any,
    ) -> list[dict[str, Any]]: ...

    def select_storage_backend(
        self,
        settings_obj: Any,
    ) -> _StorageBackendSelectionLike: ...


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------


def _get_source_environment() -> str:
    """Return the active QuickScale environment name with a conservative default."""
    return os.getenv("QUICKSCALE_ENVIRONMENT", "local").strip() or "local"


def _get_project_slug() -> str:
    base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))
    candidate = base_dir.name.strip()
    if candidate:
        return candidate
    return str(settings.ROOT_URLCONF.split(".", maxsplit=1)[0])


def _collect_module_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for app_config in apps.get_app_configs():
        if not app_config.name.startswith("quickscale_modules_"):
            continue
        try:
            package = import_module(app_config.name)
        except Exception:
            continue
        versions[app_config.name] = str(getattr(package, "__version__", "unknown"))
    return versions


def _get_git_revision() -> str | None:
    """Return the best-effort current git revision for release metadata."""
    base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            check=False,
            text=True,
            cwd=base_dir,
        )
    except OSError:
        return None

    if result.returncode != 0:
        return None

    revision = result.stdout.strip()
    return revision or None


def _load_storage_helpers() -> _StorageHelpersModule:
    """Load the storage helper module behind a typed local boundary."""
    return cast(
        _StorageHelpersModule, import_module("quickscale_modules_storage.helpers")
    )


def _read_setting_value(
    settings_obj: Any,
    key: str,
    default: Any,
) -> Any:
    """Read one setting key from a Django settings object or plain mapping."""
    if isinstance(settings_obj, dict):
        return settings_obj.get(key, default)
    return getattr(settings_obj, key, default)


# AF6 Phase 3 — extracted to quickscale_core.dr_engine._lock


# AF6 Phase 3 — extracted to quickscale_core.dr_engine._paths


# AF6 Phase 3 — _build_media_sync_manifest, _build_env_var_manifest,
# _build_promotion_verification_placeholder, and sidecar lifecycle
# extracted to quickscale_core.dr_engine._sidecar


def _build_release_metadata(*, captured_at: datetime) -> dict[str, Any]:
    """Capture release metadata reserved for later snapshot-aware CLI phases."""
    return {
        "manifest_version": 1,
        "captured_at": captured_at.astimezone(timezone.utc).isoformat(),
        "project_slug": _get_project_slug(),
        "source_environment": _get_source_environment(),
        "status": "ready",
        "app_version": str(getattr(settings, "QUICKSCALE_APP_VERSION", "unknown")),
        "django_version": django.get_version(),
        "module_versions": _collect_module_versions(),
        "git_sha": _get_git_revision(),
    }


# AF6 Phase 3 — snapshot descriptor helpers extracted to quickscale_core.dr_engine._paths


# ---------------------------------------------------------------------------
# Backup capture helper — common dump creation logic
# ---------------------------------------------------------------------------


def _create_database_dump(
    engine: str,
    resolved_policy: BackupPolicySnapshot,
    *,
    shell_runner: ShellCommandRunner | None,
    now: datetime,
    database_directory: Path,
    operation: str = "backup creation",
) -> tuple[Path, str, str, str | None, int | None, str | None, int | None]:
    """Create a database dump and return structured dump metadata.

    Returns (local_path, backup_format, filename, database_server_version,
    database_server_major, dump_client_version, dump_client_major).
    """
    database_server_version: str | None = None
    database_server_major: int | None = None
    dump_client_version: str | None = None
    dump_client_major: int | None = None

    if "postgresql" in engine:
        (
            database_server_version,
            database_server_major,
            dump_client_version,
            dump_client_major,
        ) = _require_postgresql_18_contract(
            database_engine=engine,
            executable="pg_dump",
            operation=operation,
        )
        backup_format = "pg_dump_custom"
        filename = build_backup_filename(
            resolved_policy,
            now=now,
            suffix="dump",
        )
        local_path = database_directory / filename
        _dump_postgresql_database(
            local_path,
            django.db.connections["default"].settings_dict,
            shell_runner=shell_runner,
        )
    else:
        backup_format = "json"
        filename = build_backup_filename(
            resolved_policy,
            now=now,
            suffix="json",
        )
        local_path = database_directory / filename
        _dump_database_as_json(local_path)

    return (
        local_path,
        backup_format,
        filename,
        database_server_version,
        database_server_major,
        dump_client_version,
        dump_client_major,
    )


def _dump_database_as_json(local_path: Path) -> None:
    buffer = StringIO()
    call_command("dumpdata", stdout=buffer)
    local_path.write_text(buffer.getvalue(), encoding="utf-8")


# ---------------------------------------------------------------------------
# Backup metadata helpers
# ---------------------------------------------------------------------------


def _build_backup_metadata(
    *,
    created_at: datetime,
    backup_format: str,
    database_engine: str,
    database_name: str,
    target_mode: str,
    database_server_version: str | None = None,
    database_server_major: int | None = None,
    dump_client_version: str | None = None,
    dump_client_major: int | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "created_at": created_at.astimezone(timezone.utc).isoformat(),
        "backup_format": backup_format,
        "database_engine": database_engine,
        "database_name": database_name,
        "django_version": django.get_version(),
        "environment": os.getenv("QUICKSCALE_ENVIRONMENT", "local") or "local",
        "target_mode": target_mode,
        "module_versions": _collect_module_versions(),
        "app_version": str(getattr(settings, "QUICKSCALE_APP_VERSION", "unknown")),
    }
    resolved_database_server_version = database_server_version
    if resolved_database_server_version is None:
        resolved_database_server_version = _get_database_server_version(database_engine)
    if resolved_database_server_version is not None:
        metadata["database_server_version"] = resolved_database_server_version
    if database_server_major is not None:
        metadata["database_server_major"] = database_server_major
    if dump_client_version is not None:
        metadata["pg_dump_version"] = dump_client_version
    if dump_client_major is not None:
        metadata["dump_client_major"] = dump_client_major
    return metadata


def _get_database_server_version(engine: str) -> str | None:
    """Return best-effort database server version metadata for the active backend."""
    version_query = _database_server_version_query(engine)
    if version_query is None:
        return None

    connection = django.db.connections["default"]
    try:
        with connection.cursor() as cursor:
            cursor.execute(version_query)
            row = cursor.fetchone()
    except Exception:
        return None

    if not row:
        return None

    database_server_version = str(row[0]).strip()
    return database_server_version or None


def _database_server_version_query(engine: str) -> str | None:
    """Return a read-only version query for supported backup backends."""
    engine_family = _database_engine_family(engine)
    if engine_family == "postgresql":
        return "SHOW server_version"
    if engine_family == "sqlite":
        return "SELECT sqlite_version()"
    return None


def _require_postgresql_18_contract(
    database_engine: str,
    executable: str,
    operation: str,
) -> tuple[str, int, str, int]:
    """Require a PostgreSQL 18 server plus PostgreSQL 18 client tooling."""
    if _database_engine_family(database_engine) != "postgresql":
        raise BackupConfigurationError(
            "PostgreSQL contract checks require DATABASES['default']['ENGINE'] to "
            "use PostgreSQL."
        )

    database_server_version = _get_database_server_version(database_engine)
    if database_server_version is None:
        raise BackupError(
            "PostgreSQL "
            f"{operation} requires a PostgreSQL {_REQUIRED_POSTGRESQL_MAJOR} "
            "server, but the current server version could not be determined."
        )
    database_server_major = _extract_leading_major_version(database_server_version)
    if database_server_major is None:
        raise BackupError(
            "PostgreSQL "
            f"{operation} requires a PostgreSQL {_REQUIRED_POSTGRESQL_MAJOR} "
            "server, but the current server version could not be determined."
        )
    if database_server_major != _REQUIRED_POSTGRESQL_MAJOR:
        raise BackupError(
            "PostgreSQL "
            f"{operation} requires a PostgreSQL {_REQUIRED_POSTGRESQL_MAJOR} "
            f"server, found '{database_server_version}'."
        )

    tool_version = _get_postgresql_tool_version(executable)
    tool_major = _extract_any_major_version(tool_version)
    if tool_major is None:
        raise BackupError(
            "PostgreSQL "
            f"{operation} requires PostgreSQL {_REQUIRED_POSTGRESQL_MAJOR} "
            f"{executable} tooling, but the installed tool version could not be "
            "determined." + _get_postgresql_18_guidance()
        )
    if tool_major != _REQUIRED_POSTGRESQL_MAJOR:
        raise BackupError(
            "PostgreSQL "
            f"{operation} requires PostgreSQL {_REQUIRED_POSTGRESQL_MAJOR} "
            f"{executable} tooling, found '{tool_version}'."
            + _get_postgresql_18_guidance()
        )

    return database_server_version, database_server_major, tool_version, tool_major


def _get_postgresql_18_guidance() -> str:
    """Return operator guidance for the PostgreSQL 18 client-tooling contract."""
    from quickscale_core.dr_engine.primitives import (
        _postgresql_18_client_tooling_guidance as _guidance,
    )

    return _guidance()


# ---------------------------------------------------------------------------
# Snapshot failure / state management
# ---------------------------------------------------------------------------


def _mark_snapshot_failed(
    snapshot: BackupSnapshot,
    *,
    failure_note: str,
    child_descriptors_json: dict[str, Any] | None = None,
) -> None:
    """Persist a failed snapshot outcome without hiding the stored dump artifact."""
    snapshot.status = BackupSnapshot.STATUS_FAILED
    snapshot.failure_note = failure_note
    update_fields = ["status", "failure_note", "updated_at"]
    if child_descriptors_json is not None:
        snapshot.child_descriptors_json = child_descriptors_json
        update_fields.append("child_descriptors_json")
    snapshot.save(update_fields=update_fields)


def _mark_remote_upload_failure(
    artifact: BackupArtifact,
    *,
    local_path: Path,
    error: BackupError,
) -> None:
    """Persist a failed remote-offload outcome without destroying the local dump."""
    notes = f"remote upload failed: {error}"
    artifact.remote_key = ""
    artifact.status = BackupArtifact.STATUS_FAILED
    artifact.validation_notes = notes
    artifact.metadata_json = {
        **artifact.metadata_json,
        "remote_upload_error": str(error),
        "remote_upload_failed_at": django_timezone.now().isoformat(),
    }
    artifact.save(
        update_fields=[
            "local_path",
            "remote_key",
            "status",
            "validation_notes",
            "metadata_json",
            "updated_at",
        ]
    )


def _rollback_remote_upload_after_persistence_failure(
    artifact: BackupArtifact,
    *,
    remote_key: str,
    policy: BackupPolicySnapshot,
    remote_deleter: _RemoteDeleter | None = None,
) -> str | None:
    """Best-effort delete a remote object uploaded before metadata persistence failed."""
    deleter = remote_deleter or _delete_private_remote_key
    try:
        deleter(
            remote_key,
            _resolve_artifact_remote_policy(artifact, policy),
        )
    except Exception as exc:
        return str(exc)
    return None


def _record_prune_failure_without_masking_success(
    artifact: BackupArtifact,
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
        "prune_failed_at": django_timezone.now().isoformat(),
    }

    try:
        artifact.save(update_fields=["validation_notes", "metadata_json", "updated_at"])
    except Exception:
        return


def _persist_snapshot_metadata_on_artifact(
    artifact: BackupArtifact,
    snapshot: BackupSnapshot,
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
    artifact.save(update_fields=update_fields)


def _clear_appended_artifact_note(artifact: BackupArtifact, note: str) -> bool:
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
    snapshot: BackupSnapshot,
    artifact: BackupArtifact,
) -> Path:
    """Resolve the authoritative local dump path for a stored snapshot."""
    if artifact.local_path:
        return Path(str(artifact.local_path))
    return (
        Path(str(snapshot.local_root_path))
        / _SNAPSHOT_DATABASE_DIRECTORY_NAME
        / str(artifact.filename)
    )


def _mark_snapshot_descriptors_deleted(
    child_descriptors_json: dict[str, Any],
) -> dict[str, Any]:
    """Return a copy of snapshot child metadata with deleted status applied."""
    updated = deepcopy(child_descriptors_json)
    database_descriptor = updated.get("database")
    if isinstance(database_descriptor, dict):
        database_descriptor["status"] = BackupSnapshot.STATUS_DELETED

    sidecars = updated.get("sidecars")
    if isinstance(sidecars, dict):
        for descriptor in sidecars.values():
            if isinstance(descriptor, dict):
                descriptor["status"] = BackupSnapshot.STATUS_DELETED

    return updated


def _get_authoritative_snapshot_for_artifact(
    artifact: BackupArtifact,
) -> BackupSnapshot | None:
    """Return the linked snapshot for a dump artifact if one exists."""
    try:
        return cast("BackupSnapshot", artifact.authoritative_snapshot)  # type: ignore[attr-defined]
    except BackupSnapshot.DoesNotExist:
        return None


def _resolve_artifact_remote_policy(
    artifact: BackupArtifact,
    fallback_policy: BackupPolicySnapshot,
) -> BackupPolicySnapshot:
    """Build remote deletion context from artifact location plus active credentials."""
    if artifact.storage_target != BackupArtifact.STORAGE_TARGET_PRIVATE_REMOTE:
        return fallback_policy

    return BackupPolicySnapshot(
        retention_days=fallback_policy.retention_days,
        naming_prefix=fallback_policy.naming_prefix,
        target_mode=BackupPolicy.TARGET_MODE_PRIVATE_REMOTE,
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


# ---------------------------------------------------------------------------
# Upload / materialize / delete — private remote S3 operations
# ---------------------------------------------------------------------------


def _resolve_private_remote_credentials(
    policy: BackupPolicySnapshot,
) -> tuple[str, str]:
    """Resolve runtime private-remote credentials from the configured env vars."""
    access_key_id = policy.resolve_remote_access_key_id()
    secret_access_key = policy.resolve_remote_secret_access_key()

    if not access_key_id:
        from quickscale_core.dr_engine.primitives import (
            _DEFAULT_REMOTE_ACCESS_KEY_ID_ENV_VAR as _DEFAULT_ACCESS_KEY_ENV,
        )

        env_var_name = (
            policy.remote_access_key_id_env_var.strip() or _DEFAULT_ACCESS_KEY_ENV
        )
        raise BackupConfigurationError(
            f"Environment variable '{env_var_name}' is required for private_remote backups"
        )
    if not secret_access_key:
        from quickscale_core.dr_engine.primitives import (
            _DEFAULT_REMOTE_SECRET_ACCESS_KEY_ENV_VAR as _DEFAULT_SECRET_ENV,
        )

        env_var_name = (
            policy.remote_secret_access_key_env_var.strip() or _DEFAULT_SECRET_ENV
        )
        raise BackupConfigurationError(
            f"Environment variable '{env_var_name}' is required for private_remote backups"
        )

    return access_key_id, secret_access_key


def _upload_to_private_remote(local_path: Path, policy: BackupPolicySnapshot) -> str:
    from storages.backends.s3 import S3Storage  # type: ignore[import-untyped]

    access_key_id, secret_access_key = _resolve_private_remote_credentials(policy)

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
    remote_prefix = policy.remote_prefix.strip().strip("/")
    remote_key = (
        f"{remote_prefix}/{local_path.name}" if remote_prefix else local_path.name
    )
    with local_path.open("rb") as handle:
        storage.save(remote_key, File(handle, name=local_path.name))
    return remote_key


def _materialize_private_remote_key(
    remote_key: str,
    policy: BackupPolicySnapshot,
    destination: Path,
) -> None:
    from storages.backends.s3 import S3Storage

    access_key_id, secret_access_key = _resolve_private_remote_credentials(policy)

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
                shutil.copyfileobj(source_handle, destination_handle)
    except Exception as exc:
        cleanup_error = _cleanup_local_backup_file(destination)
        details = f"Private remote materialization failed for {remote_key}: {exc}"
        if cleanup_error is not None:
            details += f"; cleanup failed: {cleanup_error}"
        raise BackupError(details) from exc


def _delete_private_remote_key(remote_key: str, policy: BackupPolicySnapshot) -> None:
    from storages.backends.s3 import S3Storage

    access_key_id, secret_access_key = _resolve_private_remote_credentials(policy)

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
    storage.delete(remote_key)


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
        _replace_policy_remote_prefix(policy, remote_prefix),
    )


# ---------------------------------------------------------------------------
# Snapshot storage deletion
# ---------------------------------------------------------------------------


def _delete_snapshot_storage(
    snapshot: BackupSnapshot,
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
        deleter = remote_deleter or _delete_private_remote_key
        remote_policy = (
            _resolve_artifact_remote_policy(artifact, policy)
            if artifact is not None
            else policy
        )
        for remote_key in sorted(remote_keys):
            deleter(remote_key, remote_policy)

    if snapshot_root.exists():
        shutil.rmtree(snapshot_root)

    if artifact is not None and artifact.local_path:
        artifact_local_path = Path(artifact.local_path)
        if artifact_local_path.exists():
            artifact_local_path.unlink()


# ---------------------------------------------------------------------------
# Capture orchestration — create_backup and resume
# ---------------------------------------------------------------------------

# _complete_capture_after_dump is a shared helper used by both create_backup and
# _resume_backup_capture.  It handles the common post-dump steps: remote upload,
# sidecar capture, state persistence, and prune.


def _complete_capture_after_dump(
    artifact: BackupArtifact,
    snapshot: BackupSnapshot,
    *,
    resolved_policy: BackupPolicySnapshot,
    local_path: Path,
    remote_uploader: _RemoteUploader | None,
    remote_deleter: _RemoteDeleter | None,
    child_descriptors_json: dict[str, Any],
    previous_failure_note: str,
    now: datetime,
) -> BackupArtifact:
    """Execute post-dump capture steps shared by create and resume paths.

    Handles remote upload, sidecar capture, success/failure persistence,
    and cleanup prune in one flow.
    """
    # Remote upload for private_remote targets
    if (
        resolved_policy.target_mode == BackupPolicy.TARGET_MODE_PRIVATE_REMOTE
        and not artifact.remote_key
    ):
        uploader = remote_uploader or _upload_to_private_remote
        try:
            remote_key = _upload_snapshot_child_to_private_remote(
                local_path,
                policy=resolved_policy,
                snapshot_remote_root=snapshot.remote_root_key,
                relative_path=str(child_descriptors_json["database"]["relative_path"]),
                remote_uploader=uploader,
            )
        except BackupError as exc:
            _mark_remote_upload_failure(artifact, local_path=local_path, error=exc)
            child_descriptors_json["database"]["status"] = BackupSnapshot.STATUS_FAILED
            child_descriptors_json["database"]["error"] = str(exc)
            _mark_snapshot_failed(
                snapshot,
                failure_note=f"database dump remote upload failed: {exc}",
                child_descriptors_json=child_descriptors_json,
            )
            raise BackupError(
                f"Snapshot capture failed for snapshot '{snapshot.snapshot_id}': {exc}"
            ) from exc
        except Exception as exc:
            upload_error = BackupError(
                "Snapshot capture failed for snapshot "
                f"'{snapshot.snapshot_id}': Private remote upload failed for "
                f"{artifact.filename}: {exc}"
            )
            _mark_remote_upload_failure(
                artifact,
                local_path=local_path,
                error=upload_error,
            )
            child_descriptors_json["database"]["status"] = BackupSnapshot.STATUS_FAILED
            child_descriptors_json["database"]["error"] = str(upload_error)
            _mark_snapshot_failed(
                snapshot,
                failure_note=(f"database dump remote upload failed: {upload_error}"),
                child_descriptors_json=child_descriptors_json,
            )
            raise upload_error from exc

        artifact.remote_key = remote_key
        try:
            artifact.save(update_fields=["remote_key", "updated_at"])
        except Exception as exc:
            cleanup_error = _rollback_remote_upload_after_persistence_failure(
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
            child_descriptors_json["database"]["status"] = BackupSnapshot.STATUS_FAILED
            child_descriptors_json["database"]["remote_key"] = remote_key
            child_descriptors_json["database"]["error"] = message
            _mark_snapshot_failed(
                snapshot,
                failure_note=message,
                child_descriptors_json=child_descriptors_json,
            )
            raise BackupError(message) from exc

        child_descriptors_json["database"]["remote_key"] = remote_key
        child_descriptors_json["database"].pop("error", None)
        snapshot.child_descriptors_json = child_descriptors_json
        snapshot.save(update_fields=["child_descriptors_json", "updated_at"])

    # Capture sidecars
    child_descriptors_json, sidecar_failures = _capture_snapshot_sidecars(
        snapshot=snapshot,
        policy=resolved_policy,
        captured_at=now,
        remote_uploader=remote_uploader,
    )
    snapshot.child_descriptors_json = child_descriptors_json
    if sidecar_failures:
        failure_note = "snapshot sidecar capture failed: " + "; ".join(sidecar_failures)
        snapshot.status = BackupSnapshot.STATUS_FAILED
        snapshot.failure_note = failure_note
        snapshot.save(
            update_fields=[
                "child_descriptors_json",
                "status",
                "failure_note",
                "updated_at",
            ]
        )
        _persist_snapshot_metadata_on_artifact(
            artifact,
            snapshot,
            note=failure_note,
        )
    else:
        snapshot.status = BackupSnapshot.STATUS_READY
        if artifact.status != BackupArtifact.STATUS_READY:
            artifact.status = BackupArtifact.STATUS_READY
            artifact.save(update_fields=["status", "updated_at"])
        snapshot.failure_note = ""
        snapshot.save(
            update_fields=[
                "child_descriptors_json",
                "status",
                "failure_note",
                "updated_at",
            ]
        )
        cleared_previous_note = _clear_appended_artifact_note(
            artifact,
            previous_failure_note,
        )
        _persist_snapshot_metadata_on_artifact(artifact, snapshot)
        if cleared_previous_note:
            artifact.save(update_fields=["validation_notes", "updated_at"])

    # Post-capture prune
    try:
        prune_expired_backups(policy=resolved_policy, now=now)
    except Exception as exc:
        _record_prune_failure_without_masking_success(artifact, error=exc)

    return artifact


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
) -> BackupArtifact:
    """Resume an incomplete snapshot capture using the existing snapshot id."""
    snapshot = get_backup_snapshot(snapshot_id)
    resolved_policy = _build_snapshot_capture_resume_policy(snapshot, policy)
    issues = _validate_policy_snapshot_internal(resolved_policy)
    if issues:
        raise BackupConfigurationError("; ".join(issues))

    if snapshot.status == BackupSnapshot.STATUS_DELETED:
        raise BackupError(
            f"Cannot resume snapshot '{snapshot.snapshot_id}' because it has already been deleted."
        )

    source_environment = _get_source_environment()
    if snapshot.source_environment != source_environment:
        raise BackupError(
            f"Cannot resume snapshot '{snapshot.snapshot_id}' from environment "
            f"'{source_environment}' because it was captured from "
            f"'{snapshot.source_environment}'."
        )

    if _snapshot_uses_private_remote(snapshot) and not snapshot.remote_root_key.strip():
        raise BackupError(
            f"Cannot resume snapshot '{snapshot.snapshot_id}' because its private remote root is missing."
        )

    if _snapshot_capture_is_complete(snapshot):
        raise BackupError(
            f"Backup snapshot '{snapshot.snapshot_id}' is already complete; resume is not needed."
        )

    snapshot_lock_directory = _build_snapshot_lock_directory(snapshot)
    snapshot_lock_directory.mkdir(parents=True, exist_ok=True)

    with _backup_creation_lock(snapshot_lock_directory, now=now):
        snapshot.refresh_from_db()
        previous_failure_note = snapshot.failure_note.strip()
        snapshot_root = Path(snapshot.local_root_path)
        snapshot_root.mkdir(parents=True, exist_ok=True)
        database_directory = snapshot_root / _SNAPSHOT_DATABASE_DIRECTORY_NAME
        database_directory.mkdir(parents=True, exist_ok=True)

        connection_settings = django.db.connections["default"].settings_dict
        engine = str(connection_settings.get("ENGINE", ""))
        database_name = str(connection_settings.get("NAME", ""))
        artifact = snapshot.authoritative_dump

        if artifact is None:
            candidate_dump_files = sorted(
                path for path in database_directory.iterdir() if path.is_file()
            )
            if len(candidate_dump_files) > 1:
                raise BackupError(
                    f"Cannot resume snapshot '{snapshot.snapshot_id}' because multiple database dump candidates were found."
                )

            database_server_version: str | None = None
            database_server_major: int | None = None
            dump_client_version: str | None = None
            dump_client_major: int | None = None

            if candidate_dump_files:
                local_path = candidate_dump_files[0]
                backup_format = _detect_restore_file_format(local_path)
                if backup_format == "pg_dump_custom":
                    (
                        database_server_version,
                        database_server_major,
                        dump_client_version,
                        dump_client_major,
                    ) = _require_postgresql_18_contract(
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
                ) = _create_database_dump(
                    engine,
                    resolved_policy,
                    shell_runner=shell_runner,
                    now=now,
                    database_directory=database_directory,
                    operation="backup capture resume",
                )

            checksum = _compute_sha256(local_path)
            size_bytes = local_path.stat().st_size
            metadata = _build_backup_metadata(
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

            artifact = BackupArtifact.objects.create(
                filename=local_path.name,
                storage_target=(
                    BackupArtifact.STORAGE_TARGET_PRIVATE_REMOTE
                    if resolved_policy.target_mode
                    == BackupPolicy.TARGET_MODE_PRIVATE_REMOTE
                    else BackupArtifact.STORAGE_TARGET_LOCAL
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
            snapshot.authoritative_dump = artifact
        else:
            if artifact.status == BackupArtifact.STATUS_DELETED:
                raise BackupError(
                    f"Cannot resume snapshot '{snapshot.snapshot_id}' because its authoritative dump artifact has been deleted."
                )

            local_path = _resolve_snapshot_database_local_path(snapshot, artifact)
            if not local_path.exists():
                raise BackupError(
                    f"Cannot resume snapshot '{snapshot.snapshot_id}' because the original authoritative dump file is missing."
                )

            validation_issues = _collect_local_backup_validation_issues(
                local_path,
                backup_format=artifact.backup_format,
                expected_checksum=artifact.checksum_sha256,
                expected_size=artifact.size_bytes,
            )
            if validation_issues:
                raise BackupError(
                    f"Cannot resume snapshot '{snapshot.snapshot_id}' because the original authoritative dump file is not valid: "
                    + "; ".join(validation_issues)
                )

            update_fields: list[str] = []
            if artifact.local_path != str(local_path):
                artifact.local_path = str(local_path)
                update_fields.append("local_path")
            if (
                not (
                    resolved_policy.target_mode
                    == BackupPolicy.TARGET_MODE_PRIVATE_REMOTE
                    and not artifact.remote_key
                )
                and artifact.status != BackupArtifact.STATUS_READY
            ):
                artifact.status = BackupArtifact.STATUS_READY
                update_fields.append("status")
            if update_fields:
                artifact.save(update_fields=[*update_fields, "updated_at"])

        child_descriptors_json = deepcopy(
            snapshot.child_descriptors_json
            if isinstance(snapshot.child_descriptors_json, dict)
            else {}
        )
        child_descriptors_json["database"] = _build_snapshot_database_descriptor(
            snapshot,
            artifact,
        )
        sidecars = child_descriptors_json.get("sidecars")
        if not isinstance(sidecars, dict):
            child_descriptors_json["sidecars"] = {}
        snapshot.child_descriptors_json = child_descriptors_json
        snapshot.save(
            update_fields=[
                "authoritative_dump",
                "child_descriptors_json",
                "updated_at",
            ]
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
) -> BackupArtifact:
    """Create a backup artifact, optionally offloading it to private remote storage."""
    resolved_policy = policy or _load_active_policy_snapshot()
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

    issues = _validate_policy_snapshot_internal(resolved_policy)
    if issues:
        raise BackupConfigurationError("; ".join(issues))

    local_directory = get_local_backup_directory(resolved_policy)
    local_directory.mkdir(parents=True, exist_ok=True)

    with _backup_creation_lock(local_directory, now=backup_started_at):
        connection_settings = django.db.connections["default"].settings_dict
        engine = str(connection_settings.get("ENGINE", ""))
        database_name = str(connection_settings.get("NAME", ""))
        previous_failure_note = ""
        snapshot_id = _mint_snapshot_id()
        snapshot_root = _build_snapshot_local_root(resolved_policy, snapshot_id)
        snapshot_root.mkdir(parents=True, exist_ok=True)
        database_directory = snapshot_root / _SNAPSHOT_DATABASE_DIRECTORY_NAME
        database_directory.mkdir(parents=True, exist_ok=True)
        snapshot = BackupSnapshot.objects.create(
            snapshot_id=snapshot_id,
            status=BackupSnapshot.STATUS_PENDING,
            source_environment=_get_source_environment(),
            local_root_path=str(snapshot_root),
            remote_root_key=(
                _build_snapshot_remote_root(resolved_policy, snapshot_id)
                if resolved_policy.target_mode
                == BackupPolicy.TARGET_MODE_PRIVATE_REMOTE
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
            ) = _create_database_dump(
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
            _mark_snapshot_failed(
                snapshot,
                failure_note=f"snapshot preparation failed: {exc}",
            )
            raise BackupError(
                f"Snapshot capture failed for snapshot '{snapshot.snapshot_id}': {exc}"
            ) from exc

        try:
            checksum = _compute_sha256(local_path)
            size_bytes = local_path.stat().st_size
        except Exception as exc:
            cleanup_error = _cleanup_local_backup_file(local_path)
            failure_note = f"snapshot dump creation failed: {exc}"
            if cleanup_error is not None:
                failure_note += f"; cleanup failed: {cleanup_error}"
            _mark_snapshot_failed(snapshot, failure_note=failure_note)
            if cleanup_error is not None:
                exc.add_note(
                    f"Failed to clean up partial backup file '{local_path}': {cleanup_error}"
                )
            raise BackupError(
                f"Snapshot capture failed for snapshot '{snapshot.snapshot_id}': {exc}"
            ) from exc

        metadata = _build_backup_metadata(
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

        artifact = BackupArtifact.objects.create(
            filename=filename,
            storage_target=(
                BackupArtifact.STORAGE_TARGET_PRIVATE_REMOTE
                if resolved_policy.target_mode
                == BackupPolicy.TARGET_MODE_PRIVATE_REMOTE
                else BackupArtifact.STORAGE_TARGET_LOCAL
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
            "database": _build_snapshot_database_descriptor(snapshot, artifact),
            "sidecars": {},
        }
        snapshot.authoritative_dump = artifact
        snapshot.child_descriptors_json = child_descriptors_json
        snapshot.save(
            update_fields=[
                "authoritative_dump",
                "child_descriptors_json",
                "updated_at",
            ]
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


# ---------------------------------------------------------------------------
# Report building
# ---------------------------------------------------------------------------


def _resolve_snapshot_provenance_value(
    *,
    field_name: str,
    candidates: Sequence[tuple[str, str]],
    issues: list[str],
) -> str | None:
    """Resolve one provenance value and note mismatches across stored sources."""
    populated_candidates = [
        (source, value) for source, value in candidates if value.strip()
    ]
    if not populated_candidates:
        issues.append(f"{field_name} is not recorded on the snapshot seam")
        return None

    unique_values = {value for _, value in populated_candidates}
    if len(unique_values) > 1:
        mismatch_details = ", ".join(
            f"{source}={value}" for source, value in populated_candidates
        )
        issues.append(
            f"{field_name} is inconsistent across snapshot provenance sources: "
            f"{mismatch_details}"
        )

    return populated_candidates[0][1]


def _build_snapshot_full_backup_contract(
    snapshot: BackupSnapshot,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the canonical full-backup completeness/provenance contract."""
    evaluated_at = now or django_timezone.now()
    _, database_descriptor, sidecars = _get_snapshot_report_children(snapshot)

    completeness_issues: list[str] = []
    provenance_issues: list[str] = []

    if snapshot.status != BackupSnapshot.STATUS_READY:
        completeness_issues.append(f"snapshot status is '{snapshot.status}'")

    authoritative_dump = snapshot.authoritative_dump
    database_status = str(database_descriptor.get("status", "")).strip() or "missing"
    database_relative_path = str(database_descriptor.get("relative_path", "")).strip()
    database_local_available = False
    database_remote_available = False
    database_remote_key = str(database_descriptor.get("remote_key", "")).strip()

    authoritative_dump_payload: dict[str, Any] | None = None
    if authoritative_dump is None:
        completeness_issues.append("authoritative database dump is missing")
    else:
        database_local_path = _resolve_snapshot_database_local_path(
            snapshot,
            authoritative_dump,
        )
        database_local_available = database_local_path.exists()
        database_remote_available = bool(
            database_remote_key or authoritative_dump.remote_key
        )
        if authoritative_dump.status == BackupArtifact.STATUS_DELETED:
            completeness_issues.append("authoritative database dump has been deleted")
        if database_status != BackupSnapshot.STATUS_READY:
            completeness_issues.append(f"database dump status is '{database_status}'")
        if not database_local_available and not database_remote_available:
            completeness_issues.append(
                "database dump is unavailable in both local and remote storage"
            )

        authoritative_dump_payload = {
            "artifact_id": authoritative_dump.pk,
            "filename": authoritative_dump.filename,
            "backup_format": authoritative_dump.backup_format,
            "database_engine": authoritative_dump.database_engine,
            "database_name": authoritative_dump.database_name,
            "checksum_sha256": authoritative_dump.checksum_sha256,
            "size_bytes": authoritative_dump.size_bytes,
        }

    required_sidecars: dict[str, dict[str, Any]] = {}
    loaded_sidecar_payloads: dict[str, dict[str, Any]] = {}
    expected_manifest_statuses = {
        _MEDIA_SYNC_MANIFEST_FILENAME: "ready",
        _ENV_VAR_MANIFEST_FILENAME: "ready",
        _RELEASE_METADATA_FILENAME: "ready",
    }

    for filename in _REQUIRED_SNAPSHOT_SIDECAR_FILENAMES:
        raw_descriptor = sidecars.get(filename)
        descriptor = raw_descriptor if isinstance(raw_descriptor, dict) else {}
        sidecar_status = str(descriptor.get("status", "")).strip() or "missing"
        metadata = descriptor.get("metadata", {})
        manifest_status = ""
        if isinstance(metadata, dict):
            manifest_status = str(metadata.get("manifest_status", "")).strip()

        local_path_text = str(descriptor.get("local_path", "")).strip()
        local_path = (
            Path(local_path_text)
            if local_path_text
            else _snapshot_sidecar_path(snapshot, filename)
        )
        local_available = local_path.exists()
        remote_available = bool(str(descriptor.get("remote_key", "")).strip())

        required_sidecars[filename] = {
            "status": sidecar_status,
            "manifest_status": manifest_status,
            "local_available": local_available,
            "remote_available": remote_available,
        }

        if not isinstance(raw_descriptor, dict):
            completeness_issues.append(f"{filename} descriptor is missing")
        elif sidecar_status != BackupSnapshot.STATUS_READY:
            completeness_issues.append(f"{filename} status is '{sidecar_status}'")
        if not local_available and not remote_available:
            completeness_issues.append(
                f"{filename} is unavailable in both local and remote storage"
            )

        expected_manifest_status = expected_manifest_statuses.get(filename)
        if (
            expected_manifest_status is not None
            and manifest_status != expected_manifest_status
        ):
            completeness_issues.append(
                f"{filename} manifest status is '{manifest_status or 'missing'}'"
            )

        if local_available:
            try:
                loaded_sidecar_payloads[filename] = _load_snapshot_sidecar_payload(
                    snapshot,
                    filename,
                )
            except BackupError as exc:
                provenance_issues.append(
                    f"{filename} could not be loaded for provenance validation: {exc}"
                )
        elif not remote_available:
            provenance_issues.append(
                f"{filename} provenance payload is unavailable for inspection"
            )

    project_slug_candidates: list[tuple[str, str]] = []
    source_environment_candidates: list[tuple[str, str]] = [
        ("snapshot", snapshot.source_environment.strip())
    ]
    sidecar_captured_at: dict[str, str | None] = {}
    for filename, payload in loaded_sidecar_payloads.items():
        payload_project_slug = str(payload.get("project_slug", "")).strip()
        if payload_project_slug:
            project_slug_candidates.append((filename, payload_project_slug))
        else:
            provenance_issues.append(f"{filename} is missing project_slug")

        payload_source_environment = str(payload.get("source_environment", "")).strip()
        if payload_source_environment:
            source_environment_candidates.append((filename, payload_source_environment))
        else:
            provenance_issues.append(f"{filename} is missing source_environment")

        captured_at = payload.get("captured_at")
        sidecar_captured_at[filename] = (
            str(captured_at).strip() if captured_at is not None else None
        )

    project_slug = _resolve_snapshot_provenance_value(
        field_name="project_slug",
        candidates=project_slug_candidates,
        issues=provenance_issues,
    )
    source_environment = _resolve_snapshot_provenance_value(
        field_name="source_environment",
        candidates=source_environment_candidates,
        issues=provenance_issues,
    )

    release_payload = loaded_sidecar_payloads.get(_RELEASE_METADATA_FILENAME, {})
    module_versions = release_payload.get("module_versions", {})
    release_summary = {
        "app_version": release_payload.get("app_version"),
        "django_version": release_payload.get("django_version"),
        "module_versions": module_versions if isinstance(module_versions, dict) else {},
        "git_sha": release_payload.get("git_sha"),
    }

    completeness_status = "complete" if not completeness_issues else "incomplete"
    provenance_status = "consistent" if not provenance_issues else "inconsistent"

    return {
        "status": (
            "complete"
            if completeness_status == "complete" and provenance_status == "consistent"
            else "incomplete"
        ),
        "validated_at": evaluated_at.astimezone(timezone.utc).isoformat(),
        "completeness": {
            "status": completeness_status,
            "issues": completeness_issues,
            "database": {
                "status": database_status,
                "relative_path": database_relative_path,
                "local_available": database_local_available,
                "remote_available": database_remote_available,
            },
            "required_sidecars": required_sidecars,
        },
        "provenance": {
            "status": provenance_status,
            "issues": provenance_issues,
            "snapshot_id": snapshot.snapshot_id,
            "project_slug": project_slug,
            "source_environment": source_environment,
            "captured_at": snapshot.created_at.astimezone(timezone.utc).isoformat(),
            "sidecar_captured_at": sidecar_captured_at,
            "authoritative_dump": authoritative_dump_payload,
            "release": release_summary,
        },
    }


def build_backup_snapshot_report(
    snapshot: BackupSnapshot,
    *,
    now: datetime | None = None,
    sidecar_payloads: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Build a structured report for one stored snapshot."""
    report_time = now or django_timezone.now()
    _, database_descriptor, sidecars = _get_snapshot_report_children(snapshot)
    full_backup_contract = _build_snapshot_full_backup_contract(
        snapshot,
        now=report_time,
    )

    authoritative_dump = snapshot.authoritative_dump
    authoritative_dump_payload: dict[str, Any] | None = None
    if authoritative_dump is not None:
        authoritative_dump_payload = {
            "artifact_id": authoritative_dump.pk,
            "filename": authoritative_dump.filename,
            "status": authoritative_dump.status,
            "storage_target": authoritative_dump.storage_target,
            "backup_format": authoritative_dump.backup_format,
            "restore_scope": authoritative_dump.effective_restore_scope(),
            "restore_scope_label": authoritative_dump.restore_scope_label(),
            "local_path": authoritative_dump.local_path,
            "remote_key": authoritative_dump.remote_key,
            "checksum_sha256": authoritative_dump.checksum_sha256,
            "size_bytes": authoritative_dump.size_bytes,
            "created_at": authoritative_dump.created_at.astimezone(
                timezone.utc
            ).isoformat(),
        }

    sidecar_summary: dict[str, dict[str, str]] = {}
    for filename, descriptor in sorted(sidecars.items()):
        if not isinstance(descriptor, dict):
            continue
        sidecar_summary[filename] = {
            "kind": str(descriptor.get("kind", "")).strip(),
            "status": str(descriptor.get("status", "")).strip(),
            "manifest_status": str(
                descriptor.get("metadata", {}).get("manifest_status", "")
            ).strip(),
        }

    requested_sidecar_payloads = tuple(
        dict.fromkeys(
            filename.strip()
            for filename in (sidecar_payloads or ())
            if filename.strip()
        )
    )
    included_sidecar_payloads: dict[str, dict[str, Any]] = {}
    sidecar_payload_errors: dict[str, str] = {}
    for filename in requested_sidecar_payloads:
        try:
            included_sidecar_payloads[filename] = _load_snapshot_sidecar_payload(
                snapshot,
                filename,
            )
        except BackupError as exc:
            sidecar_payload_errors[filename] = str(exc)

    return {
        "snapshot_id": snapshot.snapshot_id,
        "status": snapshot.status,
        "source_environment": snapshot.source_environment,
        "created_at": snapshot.created_at.astimezone(timezone.utc).isoformat(),
        "updated_at": snapshot.updated_at.astimezone(timezone.utc).isoformat(),
        "failure_note": snapshot.failure_note,
        "confirmation_value": (
            authoritative_dump.filename if authoritative_dump is not None else ""
        ),
        "local_root_path": snapshot.local_root_path,
        "remote_root_key": snapshot.remote_root_key,
        "authoritative_dump": authoritative_dump_payload,
        "rollback_pin": {
            "active": snapshot.has_active_rollback_pin(now=report_time),
            "expires_at": (
                snapshot.rollback_pin_expires_at.astimezone(timezone.utc).isoformat()
                if snapshot.rollback_pin_expires_at is not None
                else None
            ),
            "reason": snapshot.rollback_pin_reason,
        },
        "children": {
            "database": database_descriptor,
            "sidecars": sidecars,
        },
        "full_backup": full_backup_contract,
        "sidecar_summary": sidecar_summary,
        "sidecar_payloads": included_sidecar_payloads,
        "sidecar_payload_errors": sidecar_payload_errors,
    }


def report_backup_snapshot(
    snapshot_id: str,
    *,
    now: datetime | None = None,
    sidecar_payloads: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Return a structured report for one stored snapshot id."""
    snapshot = get_backup_snapshot(snapshot_id)
    return build_backup_snapshot_report(
        snapshot,
        now=now,
        sidecar_payloads=sidecar_payloads,
    )


# ---------------------------------------------------------------------------
# Prune lifecycle
# ---------------------------------------------------------------------------


def delete_artifact_files(
    artifact: BackupArtifact,
    *,
    policy: BackupPolicySnapshot | None = None,
    remote_deleter: _RemoteDeleter | None = None,
) -> None:
    """Delete local and remote artifact files without deleting the database row."""
    resolved_policy = policy or _load_active_policy_snapshot()
    snapshot = _get_authoritative_snapshot_for_artifact(artifact)
    if snapshot is not None:
        _delete_snapshot_storage(
            snapshot,
            policy=resolved_policy,
            remote_deleter=remote_deleter,
        )
        snapshot.status = BackupSnapshot.STATUS_DELETED
        snapshot.child_descriptors_json = _mark_snapshot_descriptors_deleted(
            snapshot.child_descriptors_json
            if isinstance(snapshot.child_descriptors_json, dict)
            else {}
        )
        snapshot.save(update_fields=["status", "child_descriptors_json", "updated_at"])
        return

    local_path = Path(artifact.local_path) if artifact.local_path else None
    if local_path and local_path.exists():
        local_path.unlink()

    if artifact.remote_key:
        deleter = remote_deleter or _delete_private_remote_key
        deleter(
            artifact.remote_key,
            _resolve_artifact_remote_policy(artifact, resolved_policy),
        )


def prune_expired_backups(
    *,
    policy: BackupPolicySnapshot | None = None,
    now: datetime | None = None,
    remote_deleter: _RemoteDeleter | None = None,
) -> int:
    """Delete expired backup files and mark their metadata records as deleted."""
    resolved_policy = policy or _load_active_policy_snapshot()
    prune_started_at = now or datetime.now(timezone.utc)
    cutoff = prune_started_at - timedelta(days=resolved_policy.retention_days)

    deleted_count = 0
    deleted_at = django_timezone.now()

    expired_snapshots = BackupSnapshot.objects.filter(
        created_at__lt=cutoff,
    ).exclude(status=BackupSnapshot.STATUS_DELETED)
    for snapshot in expired_snapshots:
        if snapshot.has_active_rollback_pin(now=prune_started_at):
            continue

        _delete_snapshot_storage(
            snapshot,
            policy=resolved_policy,
            remote_deleter=remote_deleter,
        )
        snapshot.status = BackupSnapshot.STATUS_DELETED
        snapshot.child_descriptors_json = _mark_snapshot_descriptors_deleted(
            snapshot.child_descriptors_json
            if isinstance(snapshot.child_descriptors_json, dict)
            else {}
        )
        snapshot.save(update_fields=["status", "child_descriptors_json", "updated_at"])

        artifact = snapshot.authoritative_dump
        if artifact is not None and artifact.deleted_at is None:
            artifact.status = BackupArtifact.STATUS_DELETED
            artifact.deleted_at = deleted_at
            artifact.save(update_fields=["status", "deleted_at", "updated_at"])

        deleted_count += 1

    expired = BackupArtifact.objects.filter(
        deleted_at__isnull=True,
        created_at__lt=cutoff,
        authoritative_snapshot__isnull=True,
    )

    for artifact in expired:
        delete_artifact_files(
            artifact,
            policy=resolved_policy,
            remote_deleter=remote_deleter,
        )
        artifact.status = BackupArtifact.STATUS_DELETED
        artifact.deleted_at = deleted_at
        artifact.save(update_fields=["status", "deleted_at", "updated_at"])
        deleted_count += 1

    return deleted_count


# ---------------------------------------------------------------------------
# Media sync
# ---------------------------------------------------------------------------


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
        selection = _load_storage_helpers().select_storage_backend(settings_obj)
    except ModuleNotFoundError as exc:
        if exc.name in (
            "quickscale_modules_storage",
            "quickscale_modules_storage.helpers",
        ):
            selection = None
        else:
            # Storage helper is installed but a sub-dependency is missing.
            # Fail hard — do not silently fall back to local media.
            raise BackupConfigurationError(str(exc)) from exc
    except Exception as exc:
        raise BackupConfigurationError(str(exc)) from exc

    if selection is not None:
        if require_s3_compatible and not selection.use_s3_compatible:
            raise BackupConfigurationError(
                "Railway-target media sync requires an s3-compatible target media backend; "
                "local MEDIA_ROOT is not a supported Railway target."
            )
        if selection.use_s3_compatible:
            bucket_name = str(selection.options.get("bucket_name", "")).strip()
            if not bucket_name:
                raise BackupConfigurationError(
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
            raise BackupConfigurationError(
                "Railway-target media sync requires an s3-compatible target media backend; "
                "storage helper is unavailable in this runtime."
            )

    media_root_text = str(_read_setting_value(settings_obj, "MEDIA_ROOT", "")).strip()
    if not media_root_text:
        raise BackupConfigurationError(
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
            shutil.copy2(source_path, target_path)
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
        with source_storage.open(relative_path, mode="rb") as source_handle:
            target_path.write_bytes(source_handle.read())
        return True

    target_storage = target_runtime["storage"]
    with source_storage.open(relative_path, mode="rb") as source_handle:
        target_storage.connection.meta.client.upload_fileobj(
            source_handle,
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
    """Dry-run or execute media sync for one snapshot using target env overrides."""
    snapshot = get_backup_snapshot(snapshot_id)
    media_manifest = _load_snapshot_sidecar_payload(
        snapshot, _MEDIA_SYNC_MANIFEST_FILENAME
    )
    manifest_status = str(media_manifest.get("status", "")).strip()
    if manifest_status != "ready":
        raise BackupError(
            "Media sync requires a ready media manifest, found status "
            f"'{manifest_status or 'unknown'}'."
        )

    inventory = media_manifest.get("inventory", [])
    if not isinstance(inventory, list):
        raise BackupError("Media manifest inventory must be a list")

    source_runtime = _resolve_media_runtime(settings)
    target_runtime = _resolve_media_runtime(
        target_runtime_settings,
        require_s3_compatible=(
            str(target_runtime_settings.get(_ROUTE_KIND_KEY, "")).strip() == "railway"
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
        "strategy": strategy,
        "source_backend": source_runtime["backend"],
        "target_backend": target_runtime["backend"],
        "planned_count": planned_count,
        "copied_count": copied_count,
        "missing_paths": missing_paths,
    }


# ---------------------------------------------------------------------------
# Validation helpers (internal, policy validation without Django model access)
# ---------------------------------------------------------------------------


def _validate_policy_snapshot_internal(policy: BackupPolicySnapshot) -> list[str]:
    """Return human-readable validation issues for a backup policy snapshot."""
    issues: list[str] = []

    if policy.retention_days < 1:
        issues.append("retention_days must be at least 1 day")

    prefix = policy.naming_prefix.strip()
    if not prefix:
        issues.append("naming_prefix cannot be blank")

    if policy.target_mode not in {
        BackupPolicy.TARGET_MODE_LOCAL,
        BackupPolicy.TARGET_MODE_PRIVATE_REMOTE,
    }:
        issues.append("target_mode must be 'local' or 'private_remote'")

    if not policy.local_directory.strip():
        issues.append("local_directory cannot be blank")

    if policy.automation_enabled and not policy.schedule.strip():
        issues.append("schedule is required when automation_enabled is true")

    if policy.target_mode == BackupPolicy.TARGET_MODE_PRIVATE_REMOTE:
        if not policy.remote_bucket_name.strip():
            issues.append(
                "remote_bucket_name is required when target_mode is private_remote"
            )
        if not policy.remote_access_key_id_env_var.strip():
            issues.append(
                "remote_access_key_id_env_var is required when target_mode is private_remote"
            )
        if not policy.remote_secret_access_key_env_var.strip():
            issues.append(
                "remote_secret_access_key_env_var is required when target_mode is private_remote"
            )
        if not (
            policy.remote_region_name.strip() or policy.remote_endpoint_url.strip()
        ):
            issues.append(
                "private_remote mode requires remote_region_name or remote_endpoint_url"
            )

    return issues


# ---------------------------------------------------------------------------
# Snapshot retrieval (Django wrapper)
# ---------------------------------------------------------------------------


def get_backup_snapshot(snapshot_id: str) -> BackupSnapshot:
    """Return one stored snapshot addressed by the public snapshot locator."""
    normalized_snapshot_id = snapshot_id.strip()
    if not normalized_snapshot_id:
        raise BackupConfigurationError("snapshot_id cannot be blank")

    try:
        return BackupSnapshot.objects.select_related("authoritative_dump").get(
            snapshot_id=normalized_snapshot_id
        )
    except BackupSnapshot.DoesNotExist as exc:
        raise BackupError(
            f"Backup snapshot not found: {normalized_snapshot_id}"
        ) from exc


# ---------------------------------------------------------------------------
# Policy loading (Django wrapper)
# ---------------------------------------------------------------------------


def _load_active_policy_snapshot() -> BackupPolicySnapshot:
    """Load the active runtime policy snapshot with managed settings precedence."""
    settings_snapshot = _build_policy_snapshot_from_settings()
    policy = BackupPolicy.objects.order_by("pk").first()
    if policy is None:
        return settings_snapshot

    _ensure_default_policy_internal()
    return settings_snapshot


def _ensure_default_policy_internal() -> BackupPolicy:
    """Ensure a default policy row exists for admin-driven workflows."""
    snapshot = _build_policy_snapshot_from_settings()
    from dataclasses import asdict

    defaults = asdict(snapshot)
    policy, _ = BackupPolicy.objects.get_or_create(key="default", defaults=defaults)
    updated_fields = [
        field_name
        for field_name, value in defaults.items()
        if getattr(policy, field_name) != value
    ]
    if updated_fields:
        for field_name in updated_fields:
            setattr(policy, field_name, defaults[field_name])
        policy.save(update_fields=[*updated_fields, "updated_at"])
    return policy


def _build_policy_snapshot_from_model(policy: BackupPolicy) -> BackupPolicySnapshot:
    """Create a BackupPolicySnapshot from a database policy record."""
    return BackupPolicySnapshot(
        retention_days=policy.retention_days,
        naming_prefix=policy.naming_prefix,
        target_mode=policy.target_mode,
        local_directory=policy.local_directory,
        remote_bucket_name=policy.remote_bucket_name,
        remote_prefix=policy.remote_prefix,
        remote_endpoint_url=policy.remote_endpoint_url,
        remote_region_name=policy.remote_region_name,
        remote_access_key_id_env_var=policy.remote_access_key_id_env_var,
        remote_secret_access_key_env_var=policy.remote_secret_access_key_env_var,
        automation_enabled=policy.automation_enabled,
        schedule=policy.schedule,
    )


def _build_policy_snapshot_from_settings() -> BackupPolicySnapshot:
    """Create a BackupPolicySnapshot from Django settings defaults."""
    return BackupPolicySnapshot(
        retention_days=int(getattr(settings, "QUICKSCALE_BACKUPS_RETENTION_DAYS", 14)),
        naming_prefix=str(getattr(settings, "QUICKSCALE_BACKUPS_NAMING_PREFIX", "db")),
        target_mode=str(
            getattr(
                settings,
                "QUICKSCALE_BACKUPS_TARGET_MODE",
                BackupPolicy.TARGET_MODE_LOCAL,
            )
        ),
        local_directory=str(
            getattr(
                settings,
                "QUICKSCALE_BACKUPS_LOCAL_DIRECTORY",
                ".quickscale/backups",
            )
        ),
        remote_bucket_name=str(
            getattr(settings, "QUICKSCALE_BACKUPS_REMOTE_BUCKET_NAME", "")
        ),
        remote_prefix=str(
            getattr(settings, "QUICKSCALE_BACKUPS_REMOTE_PREFIX", "backups/private")
        ),
        remote_endpoint_url=str(
            getattr(settings, "QUICKSCALE_BACKUPS_REMOTE_ENDPOINT_URL", "")
        ),
        remote_region_name=str(
            getattr(settings, "QUICKSCALE_BACKUPS_REMOTE_REGION_NAME", "")
        ),
        remote_access_key_id_env_var=str(
            getattr(
                settings,
                "QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR",
                "QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID",
            )
        ),
        remote_secret_access_key_env_var=str(
            getattr(
                settings,
                "QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR",
                "QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY",
            )
        ),
        automation_enabled=bool(
            getattr(settings, "QUICKSCALE_BACKUPS_AUTOMATION_ENABLED", False)
        ),
        schedule=str(getattr(settings, "QUICKSCALE_BACKUPS_SCHEDULE", "0 2 * * *")),
    )


# ---------------------------------------------------------------------------
# Path safety / download helpers
# ---------------------------------------------------------------------------


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
    artifact: BackupArtifact,
    policy: BackupPolicySnapshot,
) -> tuple[Path, ...]:
    """Return the local roots that may legitimately contain an artifact download."""
    roots = [Path(os.path.abspath(os.fspath(get_local_backup_directory(policy))))]
    snapshot = _get_authoritative_snapshot_for_artifact(artifact)
    if snapshot is not None:
        roots.append(Path(os.path.abspath(snapshot.local_root_path)))

    unique_roots: list[Path] = []
    for root in roots:
        if root not in unique_roots:
            unique_roots.append(root)
    return tuple(unique_roots)


def download_backup_path(
    artifact: BackupArtifact,
    *,
    policy: BackupPolicySnapshot | None = None,
) -> Path:
    """Return the local operator download path for an artifact."""
    if not artifact.local_path:
        raise BackupError("This artifact does not have a local download path.")

    candidate_path = Path(artifact.local_path).expanduser()
    absolute_candidate = Path(os.path.abspath(os.fspath(candidate_path)))
    if not absolute_candidate.exists():
        raise BackupError(f"Backup file not found: {absolute_candidate}")

    resolved_policy = policy or _load_active_policy_snapshot()
    resolved_candidate = absolute_candidate.resolve(strict=True)
    if not resolved_candidate.is_file():
        raise BackupError(f"Backup file is not a regular file: {resolved_candidate}")

    for authoritative_root in _get_authoritative_local_backup_roots(
        artifact,
        resolved_policy,
    ):
        if not _is_path_within_root(absolute_candidate, authoritative_root):
            continue
        if _path_uses_symlink_within_root(absolute_candidate, authoritative_root):
            raise BackupError("Backup download path cannot use symlinks.")

        resolved_root = authoritative_root.resolve(strict=False)
        if not _is_path_within_root(resolved_candidate, resolved_root):
            raise BackupError(
                "Backup download path must stay within authoritative backup roots."
            )

        return resolved_candidate

    raise BackupError(
        "Backup download path must stay within authoritative backup roots."
    )


# ---------------------------------------------------------------------------
# Django-backed restore wrappers
# ---------------------------------------------------------------------------


def _get_restore_compatibility_issues(artifact: BackupArtifact) -> list[str]:
    """Return restore guardrail issues — delegates to the core implementation."""
    current_engine = str(
        django.db.connections["default"].settings_dict.get("ENGINE") or ""
    ).strip()
    return _core_get_restore_compatibility_issues(artifact, current_engine)


@contextmanager
def _resolve_restore_source(
    *,
    artifact: BackupArtifact | None = None,
    file_path: str | Path | None = None,
    snapshot_id: str | None = None,
    resolution_mode: RestoreSourceResolutionMode = RestoreSourceResolutionMode.REMOTE_FALLBACK,
    policy: BackupPolicySnapshot | None = None,
    remote_materializer: RemoteMaterializer | None = None,
) -> Iterator[ResolvedRestoreSource]:
    """Resolve one restore source — Django-backed wrapper around core."""
    resolved_policy: BackupPolicySnapshot | None = policy

    def _policy_resolver(art: ArtifactLike) -> Any:
        nonlocal resolved_policy
        resolved_policy = _resolve_artifact_remote_policy(
            cast("BackupArtifact", art),
            resolved_policy or _load_active_policy_snapshot(),
        )
        return resolved_policy

    with _core_resolve_restore_source(
        artifact=artifact,
        file_path=file_path,
        snapshot_id=snapshot_id,
        resolution_mode=resolution_mode,
        remote_materializer=remote_materializer or _materialize_private_remote_key,
        snapshot_resolver=_resolve_authoritative_snapshot_dump,
        policy_resolver=_policy_resolver,
    ) as restore_source:
        yield restore_source


def _resolve_authoritative_snapshot_dump(snapshot_id: str) -> BackupArtifact:
    """Resolve a snapshot id to its authoritative database dump artifact."""
    snapshot = get_backup_snapshot(snapshot_id)
    if snapshot.status == BackupSnapshot.STATUS_DELETED:
        raise BackupRestoreBlocked(
            f"Restore blocked because snapshot '{snapshot.snapshot_id}' has been deleted or pruned."
        )

    artifact = snapshot.authoritative_dump
    if artifact is None:
        raise BackupRestoreBlocked(
            "Restore blocked because the requested snapshot does not have an "
            "authoritative database dump artifact."
        )

    return cast("BackupArtifact", artifact)


def _ensure_postgresql_18_restore_runtime(current_engine: str) -> None:
    """Require the current restore runtime — delegates to core + Django-backed checker."""
    from quickscale_core.dr_engine.recovery import (
        _ensure_postgresql_18_restore_runtime as _core_ensure_runtime,
    )

    _core_ensure_runtime(
        current_engine,
        require_contract=_require_postgresql_18_contract,
    )


def _restore_execution_allowed() -> bool:
    """Return whether destructive restore execution is permitted (Django-backed)."""
    return _core_restore_execution_allowed(is_debug=settings.DEBUG)


def _execute_restore_for_resolved_source(
    restore_source: ResolvedRestoreSource,
    *,
    confirmation: str,
    dry_run: bool,
    allow_production: bool,
    shell_runner: ShellCommandRunner | None,
) -> RestoreResult:
    """Run the guarded restore pipeline — Django-backed wrapper around core."""
    current_engine = str(
        django.db.connections["default"].settings_dict.get("ENGINE") or ""
    ).strip()
    connection_settings = django.db.connections["default"].settings_dict

    result = _core_execute_restore_for_resolved_source(
        restore_source,
        confirmation=confirmation,
        dry_run=dry_run,
        allow_production=allow_production,
        shell_runner=shell_runner,
        current_engine=current_engine,
        connection_settings=connection_settings,
        is_debug=settings.DEBUG,
        pg_contract_checker=_require_postgresql_18_contract,
    )

    if result.executed and restore_source.artifact is not None:
        restore_warnings = _persist_restore_artifact_metadata(
            cast("BackupArtifact", restore_source.artifact),
            restored_at=django_timezone.now(),
        )
        if restore_warnings:
            result = replace(result, warnings=(*result.warnings, *restore_warnings))

    return result


def restore_backup_source(
    *,
    artifact: BackupArtifact | None = None,
    file_path: str | Path | None = None,
    snapshot_id: str | None = None,
    confirmation: str,
    dry_run: bool = False,
    allow_production: bool = False,
    resolution_mode: RestoreSourceResolutionMode = (
        RestoreSourceResolutionMode.REMOTE_FALLBACK
    ),
    shell_runner: ShellCommandRunner | None = None,
    policy: BackupPolicySnapshot | None = None,
    remote_materializer: RemoteMaterializer | None = None,
) -> RestoreResult:
    """Run guarded restore validation or execution for one restore source."""
    with _resolve_restore_source(
        artifact=artifact,
        file_path=file_path,
        snapshot_id=snapshot_id,
        resolution_mode=resolution_mode,
        policy=policy,
        remote_materializer=remote_materializer,
    ) as restore_source:
        return _execute_restore_for_resolved_source(
            restore_source,
            confirmation=confirmation,
            dry_run=dry_run,
            allow_production=allow_production,
            shell_runner=shell_runner,
        )


def restore_backup_artifact(
    artifact: BackupArtifact,
    *,
    confirmation: str,
    dry_run: bool = False,
    allow_production: bool = False,
    resolution_mode: RestoreSourceResolutionMode = (
        RestoreSourceResolutionMode.REMOTE_FALLBACK
    ),
    shell_runner: ShellCommandRunner | None = None,
    policy: BackupPolicySnapshot | None = None,
    remote_materializer: RemoteMaterializer | None = None,
) -> RestoreResult:
    """Run guarded restore validation or execution for a backup artifact."""
    return restore_backup_source(
        artifact=artifact,
        confirmation=confirmation,
        dry_run=dry_run,
        allow_production=allow_production,
        resolution_mode=resolution_mode,
        shell_runner=shell_runner,
        policy=policy,
        remote_materializer=remote_materializer,
    )


# ---------------------------------------------------------------------------
# Admin restore pipeline
# ---------------------------------------------------------------------------


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
            for chunk in _iter_admin_restore_upload_chunks(uploaded_file):
                if not chunk:
                    continue
                digest.update(chunk)
                handle.write(chunk)
                size_bytes += len(chunk)
    except OSError as exc:
        raise BackupError(f"Unable to stage uploaded backup file: {exc}") from exc

    if size_bytes < 1:
        raise BackupRestoreBlocked(
            "Restore blocked because the uploaded backup file is empty."
        )

    return StagedAdminRestoreUpload(
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
        raise BackupError("Uploaded backup file does not provide a readable stream.")

    payload = read_method()
    if isinstance(payload, str):
        yield payload.encode("utf-8")
        return
    if isinstance(payload, bytes):
        yield payload
        return
    raise BackupError("Uploaded backup file did not return bytes when read.")


def _cleanup_admin_restore_upload_directory(staging_directory: Path) -> str | None:
    """Delete one quarantined admin restore staging directory."""
    try:
        shutil.rmtree(staging_directory)
    except FileNotFoundError:
        return None
    except OSError as exc:
        return str(exc)
    return None


def _resolve_admin_uploaded_restore_artifact(
    *,
    checksum_sha256: str,
    size_bytes: int,
) -> BackupArtifact:
    """Resolve an uploaded file to exactly one trusted authoritative artifact."""
    normalized_checksum = checksum_sha256.strip().lower()
    if not normalized_checksum:
        raise BackupRestoreBlocked(
            "Restore blocked because the uploaded backup file checksum could not be determined."
        )
    if size_bytes < 1:
        raise BackupRestoreBlocked(
            "Restore blocked because the uploaded backup file is empty."
        )

    candidates = list(
        BackupArtifact.objects.filter(
            checksum_sha256=normalized_checksum,
            size_bytes=size_bytes,
        )
        .select_related("authoritative_snapshot")
        .order_by("pk")
    )
    if not candidates:
        raise BackupRestoreBlocked(
            "Restore blocked because the uploaded backup file does not match any recorded authoritative backup artifact."
        )

    trusted_candidates: list[BackupArtifact] = []
    trust_issues: list[str] = []
    for candidate in candidates:
        trust_issue = _get_admin_uploaded_restore_artifact_trust_issue(candidate)
        if trust_issue is None:
            trusted_candidates.append(candidate)
            continue
        trust_issues.append(trust_issue)

    if not trusted_candidates:
        issue_message = (
            trust_issues[0]
            if trust_issues
            else "no trusted metadata match was available"
        )
        raise BackupRestoreBlocked(
            "Restore blocked because the uploaded backup file could not be resolved "
            f"to a trusted authoritative backup artifact: {issue_message}."
        )

    if len(trusted_candidates) > 1:
        raise BackupRestoreBlocked(
            "Restore blocked because the uploaded backup file matches multiple trusted authoritative backup artifacts."
        )

    return trusted_candidates[0]


def _get_admin_uploaded_restore_artifact_trust_issue(
    artifact: BackupArtifact,
) -> str | None:
    """Return why one checksum-matched artifact is not trusted for admin upload."""
    if artifact.status == BackupArtifact.STATUS_DELETED:
        return "matching recorded artifact has been deleted"
    if artifact.is_export_only() or artifact.backup_format != "pg_dump_custom":
        return "matching recorded artifact is not a PostgreSQL custom-format restore candidate"
    if artifact.effective_restore_scope() not in {
        BackupArtifact.RESTORE_SCOPE_LOCAL_ONLY,
        BackupArtifact.RESTORE_SCOPE_PORTABLE,
    }:
        return "matching recorded artifact is not classified as an eligible restore candidate"

    snapshot = _get_authoritative_snapshot_for_artifact(artifact)
    if snapshot is None:
        return "matching recorded artifact is not linked to an authoritative snapshot"
    if snapshot.status == BackupSnapshot.STATUS_DELETED:
        return "matching authoritative snapshot has been deleted or pruned"

    full_backup_contract = _build_snapshot_full_backup_contract(snapshot)
    if str(full_backup_contract.get("status", "")).strip() != "complete":
        contract_issues = _summarize_full_backup_contract_issues(full_backup_contract)
        if contract_issues:
            return (
                "matching authoritative snapshot does not satisfy the full-backup "
                f"contract: {contract_issues}"
            )
        return (
            "matching authoritative snapshot does not satisfy the full-backup contract"
        )

    provenance = full_backup_contract.get("provenance", {})
    authoritative_dump = (
        provenance.get("authoritative_dump", {}) if isinstance(provenance, dict) else {}
    )
    if not isinstance(authoritative_dump, dict):
        return "matching authoritative snapshot does not record authoritative dump metadata"
    if authoritative_dump.get("artifact_id") != artifact.pk:
        return "matching authoritative snapshot does not point back to this artifact"
    if (
        str(authoritative_dump.get("checksum_sha256", "")).strip()
        != artifact.checksum_sha256
    ):
        return "matching authoritative snapshot checksum metadata does not match the artifact row"
    if authoritative_dump.get("size_bytes") != artifact.size_bytes:
        return "matching authoritative snapshot size metadata does not match the artifact row"

    return None


def _summarize_full_backup_contract_issues(
    full_backup_contract: dict[str, Any],
) -> str:
    """Flatten completeness and provenance issues from the Phase 1 contract."""
    issues: list[str] = []

    completeness = full_backup_contract.get("completeness", {})
    if isinstance(completeness, dict):
        completeness_issues = completeness.get("issues", [])
        if isinstance(completeness_issues, list):
            issues.extend(
                str(issue).strip()
                for issue in completeness_issues
                if str(issue).strip()
            )

    provenance = full_backup_contract.get("provenance", {})
    if isinstance(provenance, dict):
        provenance_issues = provenance.get("issues", [])
        if isinstance(provenance_issues, list):
            issues.extend(
                str(issue).strip() for issue in provenance_issues if str(issue).strip()
            )

    return "; ".join(dict.fromkeys(issues))


def _persist_restore_artifact_metadata(
    artifact: BackupArtifact,
    *,
    restored_at: datetime,
) -> tuple[RestoreWarning, ...]:
    """Best-effort persist restore metadata after pg_restore succeeds."""
    try:
        updated_rows = BackupArtifact.objects.filter(pk=artifact.pk).update(
            status=BackupArtifact.STATUS_RESTORED,
            restored_at=restored_at,
            updated_at=restored_at,
        )
    except DatabaseError as exc:
        return (
            RestoreWarning(
                code="artifact_metadata_not_persisted_after_restore",
                message=(
                    "Restore executed, but backup artifact metadata could not be "
                    "persisted after the restored database changed."
                ),
                details={
                    "artifact_id": str(artifact.pk),
                    "error_type": exc.__class__.__name__,
                    "filename": artifact.filename,
                },
            ),
        )

    if updated_rows == 0:
        return (
            RestoreWarning(
                code="artifact_row_missing_after_restore",
                message=(
                    "Restore executed, but the original backup artifact row no "
                    "longer exists in the restored database."
                ),
                details={
                    "artifact_id": str(artifact.pk),
                    "filename": artifact.filename,
                },
            ),
        )

    artifact.status = BackupArtifact.STATUS_RESTORED
    artifact.restored_at = restored_at
    return ()


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
    staging_directory = Path(mkdtemp(prefix="quickscale-backups-admin-upload-"))
    result: RestoreResult | None = None

    try:
        staged_upload = _stage_admin_restore_upload(
            uploaded_file,
            staging_directory=staging_directory,
        )
        trusted_artifact = _resolve_admin_uploaded_restore_artifact(
            checksum_sha256=staged_upload.checksum_sha256,
            size_bytes=staged_upload.size_bytes,
        )

        # CR-SA38-001: stale-aware RESTORING guard — parity with
        # prepare_admin_uploaded_restore_artifact (services.py) so the
        # uploaded-file dry-run path applies the same eligibility guard
        # and recovery guidance as the recorded-artifact branch.
        if trusted_artifact.status == BackupArtifact.STATUS_RESTORING:
            stale_threshold = django_timezone.now() - timedelta(
                minutes=stale_threshold_minutes
            )
            if (
                trusted_artifact.restore_started_at is not None
                and trusted_artifact.restore_started_at < stale_threshold
            ):
                raise BackupRestoreBlocked(
                    "This backup artifact's restore appears stale "
                    f"(started at {trusted_artifact.restore_started_at:%Y-%m-%d %H:%M:%S} UTC) — "
                    "the child process likely died. Reset the artifact status "
                    "from the BackupArtifact admin list to retry."
                )
            raise BackupRestoreBlocked(
                "This backup artifact is currently being "
                "restored. Wait for the restore to "
                "complete before retrying."
            )

        result = _execute_restore_for_resolved_source(
            ResolvedRestoreSource(
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
        cleanup_error = _cleanup_admin_restore_upload_directory(staging_directory)
        if cleanup_error is not None:
            exc.add_note(
                "Failed to clean up staged admin restore upload directory "
                f"'{staging_directory}': {cleanup_error}"
            )
        raise

    assert result is not None
    cleanup_error = _cleanup_admin_restore_upload_directory(staging_directory)
    if cleanup_error is None:
        return result

    return replace(
        result,
        warnings=(
            *result.warnings,
            RestoreWarning(
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


# ---------------------------------------------------------------------------
# Verification and rollback-pin wrappers (Django-backed)
# ---------------------------------------------------------------------------


def record_backup_snapshot_verification(
    snapshot_id: str,
    *,
    route: str,
    phase: str,
    status: str,
    payload: dict[str, Any],
    now: datetime | None = None,
    policy: BackupPolicySnapshot | None = None,
    remote_uploader: _RemoteUploader | None = None,
) -> dict[str, Any]:
    """Append one route-specific report to the verification sidecar.

    This is a Django-facing wrapper.  The verification payload is assembled
    by ``_build_verification_payload`` in ``dr_engine.verification``.
    """
    normalized_route = route.strip()
    normalized_phase = phase.strip()
    normalized_status = status.strip()
    _validate_verification_inputs(
        route=normalized_route,
        phase=normalized_phase,
        status=normalized_status,
    )

    snapshot = get_backup_snapshot(snapshot_id)
    recorded_at = now or django_timezone.now()
    full_backup_contract = _build_snapshot_full_backup_contract(
        snapshot,
        now=recorded_at,
    )
    try:
        verification_payload = _load_snapshot_sidecar_payload(
            snapshot,
            _PROMOTION_VERIFICATION_FILENAME,
        )
    except BackupError:
        verification_payload = {}

    existing_reports = verification_payload.get("reports")
    if not isinstance(existing_reports, list):
        existing_reports = []

    verification_payload = _build_verification_payload(
        snapshot_id=snapshot.snapshot_id,
        project_slug=_get_project_slug(),
        source_environment=snapshot.source_environment,
        captured_at=verification_payload.get(
            "captured_at",
            snapshot.created_at.astimezone(timezone.utc).isoformat(),
        ),
        status=normalized_status,
        updated_at=recorded_at.astimezone(timezone.utc).isoformat(),
        full_backup_contract=full_backup_contract,
        existing_reports=existing_reports,
        existing_notes=verification_payload.get(
            "notes",
            "Reserved for route-specific plan and execute reports.",
        ),
        rollback_pin_active=snapshot.has_active_rollback_pin(now=recorded_at),
        rollback_pin_expires_at=(
            snapshot.rollback_pin_expires_at.astimezone(timezone.utc).isoformat()
            if snapshot.rollback_pin_expires_at is not None
            else None
        ),
        rollback_pin_reason=snapshot.rollback_pin_reason,
        route=normalized_route,
        phase=normalized_phase,
        payload=payload,
    )
    _persist_snapshot_sidecar_payload(
        snapshot,
        filename=_PROMOTION_VERIFICATION_FILENAME,
        kind="promotion_verification",
        payload=verification_payload,
        policy=policy,
        remote_uploader=remote_uploader,
    )
    return build_backup_snapshot_report(
        snapshot,
        now=recorded_at,
        sidecar_payloads=[_PROMOTION_VERIFICATION_FILENAME],
    )


def validate_backup_artifact(artifact: BackupArtifact) -> list[str]:
    """Validate artifact integrity and update its validation status."""
    local_path = Path(artifact.local_path) if artifact.local_path else None
    issues = _collect_local_backup_validation_issues(
        local_path,
        backup_format=artifact.backup_format,
        expected_checksum=artifact.checksum_sha256,
        expected_size=artifact.size_bytes,
    )

    artifact.validated_at = django_timezone.now()
    artifact.validation_notes = "; ".join(issues)
    artifact.status = (
        BackupArtifact.STATUS_FAILED if issues else BackupArtifact.STATUS_VALIDATED
    )
    artifact.save(
        update_fields=["validated_at", "validation_notes", "status", "updated_at"]
    )
    return issues


def set_backup_snapshot_rollback_pin(
    snapshot_id: str,
    *,
    ttl_hours: int,
    reason: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Set or refresh a time-bounded rollback pin on one stored snapshot."""
    snapshot = get_backup_snapshot(snapshot_id)
    if snapshot.status == BackupSnapshot.STATUS_DELETED:
        raise BackupError(
            f"Backup snapshot '{snapshot.snapshot_id}' has already been deleted"
        )
    if snapshot.authoritative_dump is None:
        raise BackupError(
            f"Backup snapshot '{snapshot.snapshot_id}' does not have an authoritative dump"
        )

    pinned_at = now or django_timezone.now()
    fields = _compute_rollback_pin_fields(
        ttl_hours=ttl_hours,
        reason=reason,
        now=pinned_at,
    )
    snapshot.rollback_pin_expires_at = fields["rollback_pin_expires_at"]
    snapshot.rollback_pin_reason = fields["rollback_pin_reason"]
    snapshot.save(
        update_fields=[
            "rollback_pin_expires_at",
            "rollback_pin_reason",
            "updated_at",
        ]
    )
    return build_backup_snapshot_report(snapshot, now=pinned_at)


def clear_backup_snapshot_rollback_pin(
    snapshot_id: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Clear any active rollback pin on one stored snapshot."""
    snapshot = get_backup_snapshot(snapshot_id)
    if snapshot.status == BackupSnapshot.STATUS_DELETED:
        raise BackupError(
            f"Backup snapshot '{snapshot.snapshot_id}' has already been deleted"
        )

    cleared_at = now or django_timezone.now()
    fields = _build_clear_rollback_pin_fields()
    snapshot.rollback_pin_expires_at = fields["rollback_pin_expires_at"]
    snapshot.rollback_pin_reason = fields["rollback_pin_reason"]
    snapshot.save(
        update_fields=[
            "rollback_pin_expires_at",
            "rollback_pin_reason",
            "updated_at",
        ]
    )
    return build_backup_snapshot_report(snapshot, now=cleared_at)
