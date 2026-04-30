"""Operational services for private backup creation, validation, pruning, and restore."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from enum import StrEnum
import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from importlib import import_module
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any, Callable, Protocol, Sequence, cast
from uuid import uuid4

import django
from django.apps import apps
from django.conf import settings
from django.db import DatabaseError
from django.core.files import File
from django.core.management import call_command
from django.utils import timezone as django_timezone

from quickscale_modules_backups.models import (
    BackupArtifact,
    BackupPolicy,
    BackupSnapshot,
)

if TYPE_CHECKING:
    from django.contrib.auth.base_user import AbstractBaseUser

_LOCK_FILENAME = ".quickscale-backup-create.lock"
_LOCK_TIMEOUT_SECONDS = 300
_DEFAULT_REMOTE_ACCESS_KEY_ID_ENV_VAR = "QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID"
_DEFAULT_REMOTE_SECRET_ACCESS_KEY_ENV_VAR = (
    "QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY"
)
_REQUIRED_POSTGRESQL_MAJOR = 18
_LEADING_MAJOR_VERSION_PATTERN = re.compile(r"^\s*(\d+)")
_ANY_MAJOR_VERSION_PATTERN = re.compile(r"(\d+)")
_POSTGRESQL_CUSTOM_ARCHIVE_MAGIC = b"PGDMP"
_SNAPSHOTS_DIRECTORY_NAME = "snapshots"
_SNAPSHOT_DATABASE_DIRECTORY_NAME = "database"
_MEDIA_SYNC_MANIFEST_FILENAME = "media-sync-manifest.json"
_ENV_VAR_MANIFEST_FILENAME = "env-var-manifest.json"
_RELEASE_METADATA_FILENAME = "release-metadata.json"
_PROMOTION_VERIFICATION_FILENAME = "promotion-verification.json"
_REQUIRED_SNAPSHOT_SIDECAR_FILENAMES = (
    _MEDIA_SYNC_MANIFEST_FILENAME,
    _ENV_VAR_MANIFEST_FILENAME,
    _RELEASE_METADATA_FILENAME,
    _PROMOTION_VERIFICATION_FILENAME,
)
_DR_TARGET_ENV_PREFIX = "QUICKSCALE_DR_TARGET_"
_DR_TARGET_ROUTE_KIND_KEY = "ROUTE_KIND"


def _postgresql_18_client_tooling_guidance() -> str:
    """Return operator guidance for the PostgreSQL 18 client-tooling contract."""
    return (
        " Install PostgreSQL 18 client tooling via the PGDG apt repository plus "
        "'postgresql-client-18' in Docker/CI runtimes, or run the command in an "
        "environment that already provides PostgreSQL 18 pg_dump/pg_restore. "
        "Existing generated projects must adopt those Docker/CI/E2E file changes "
        "manually because quickscale apply does not rewrite user-owned files."
    )


class BackupError(Exception):
    """Base error for backup operations."""


class BackupConfigurationError(BackupError):
    """Raised when backup policy settings are invalid for the requested operation."""


class BackupLockError(BackupError):
    """Raised when a backup operation is already running."""


class BackupRestoreBlocked(BackupError):
    """Raised when destructive restore execution is intentionally blocked."""


class ShellCommandRunner(Protocol):
    """Protocol for shell-based backup and restore runners."""

    def __call__(
        self,
        command: Sequence[str],
        *,
        env: dict[str, str] | None = None,
    ) -> None: ...


class RemoteUploader(Protocol):
    """Protocol used for optional private remote artifact offload."""

    def __call__(self, local_path: Path, policy: "BackupPolicySnapshot") -> str: ...


class RemoteDeleter(Protocol):
    """Protocol used for private remote artifact deletion."""

    def __call__(self, remote_key: str, policy: "BackupPolicySnapshot") -> None: ...


class RemoteMaterializer(Protocol):
    """Protocol used for temporary private remote restore materialization."""

    def __call__(
        self,
        remote_key: str,
        policy: "BackupPolicySnapshot",
        destination: Path,
    ) -> None: ...


class StorageBackendSelectionLike(Protocol):
    """Typed shape used from the storage helper module."""

    backend: str
    django_backend: str
    use_s3_compatible: bool
    options: dict[str, Any]


class StorageHelpersModule(Protocol):
    """Typed subset of the storage helper module used by backups."""

    def list_s3_compatible_media_inventory(
        self,
        settings_obj: Any,
    ) -> list[dict[str, Any]]: ...

    def select_storage_backend(
        self,
        settings_obj: Any,
    ) -> StorageBackendSelectionLike: ...


@dataclass(frozen=True)
class BackupPolicySnapshot:
    """Immutable view of the active backup policy."""

    retention_days: int
    naming_prefix: str
    target_mode: str
    local_directory: str
    remote_bucket_name: str
    remote_prefix: str
    remote_endpoint_url: str
    remote_region_name: str
    remote_access_key_id_env_var: str
    remote_secret_access_key_env_var: str
    automation_enabled: bool
    schedule: str

    @classmethod
    def from_model(cls, policy: BackupPolicy) -> "BackupPolicySnapshot":
        """Create a snapshot from a database policy record."""
        return cls(
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

    @classmethod
    def from_settings(cls) -> "BackupPolicySnapshot":
        """Create a snapshot from Django settings defaults."""
        return cls(
            retention_days=int(
                getattr(settings, "QUICKSCALE_BACKUPS_RETENTION_DAYS", 14)
            ),
            naming_prefix=str(
                getattr(settings, "QUICKSCALE_BACKUPS_NAMING_PREFIX", "db")
            ),
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
                    _DEFAULT_REMOTE_ACCESS_KEY_ID_ENV_VAR,
                )
            ),
            remote_secret_access_key_env_var=str(
                getattr(
                    settings,
                    "QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR",
                    _DEFAULT_REMOTE_SECRET_ACCESS_KEY_ENV_VAR,
                )
            ),
            automation_enabled=bool(
                getattr(settings, "QUICKSCALE_BACKUPS_AUTOMATION_ENABLED", False)
            ),
            schedule=str(getattr(settings, "QUICKSCALE_BACKUPS_SCHEDULE", "0 2 * * *")),
        )

    def resolve_remote_access_key_id(self) -> str:
        """Return the runtime private-remote access key id from the environment."""
        env_var_name = (
            self.remote_access_key_id_env_var.strip()
            or _DEFAULT_REMOTE_ACCESS_KEY_ID_ENV_VAR
        )
        return os.getenv(env_var_name, "").strip()

    def resolve_remote_secret_access_key(self) -> str:
        """Return the runtime private-remote secret access key from the environment."""
        env_var_name = (
            self.remote_secret_access_key_env_var.strip()
            or _DEFAULT_REMOTE_SECRET_ACCESS_KEY_ENV_VAR
        )
        return os.getenv(env_var_name, "").strip()


@dataclass(frozen=True)
class RestoreWarning:
    """Structured non-fatal warning emitted after restore execution."""

    code: str
    message: str
    details: dict[str, str] | None = None


class RestoreSourceResolutionMode(StrEnum):
    """How restore source resolution may use private remote artifacts."""

    REMOTE_FALLBACK = "remote_fallback"
    LOCAL_ONLY = "local_only"


@dataclass(frozen=True)
class RestoreResult:
    """Return value for guarded restore execution."""

    executed: bool
    dry_run: bool
    message: str
    warnings: tuple[RestoreWarning, ...] = ()


@dataclass(frozen=True)
class ResolvedRestoreSource:
    """Resolved local restore input used by the guarded restore pipeline."""

    confirmation_value: str
    local_path: Path
    backup_format: str
    artifact: BackupArtifact | None = None

    def is_export_only(self) -> bool:
        """Return whether this resolved source is blocked as export-only."""
        if self.artifact is None:
            return self.backup_format == "json"
        return self.artifact.is_export_only()


def ensure_default_policy() -> BackupPolicy:
    """Ensure a default policy row exists for admin-driven workflows."""
    snapshot = BackupPolicySnapshot.from_settings()
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


def load_policy_snapshot() -> BackupPolicySnapshot:
    """Load the active runtime policy snapshot with managed settings precedence."""
    settings_snapshot = BackupPolicySnapshot.from_settings()
    policy = BackupPolicy.objects.order_by("pk").first()
    if policy is None:
        return settings_snapshot

    ensure_default_policy()
    return settings_snapshot


def validate_policy_snapshot(policy: BackupPolicySnapshot) -> list[str]:
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


def build_backup_filename(
    policy: BackupPolicySnapshot,
    *,
    now: datetime | None = None,
    suffix: str | None = None,
) -> str:
    """Build a deterministic operator-friendly backup filename."""
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
    directory = Path(policy.local_directory)
    if directory.is_absolute():
        return directory

    base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))
    return base_dir / directory


def _get_source_environment() -> str:
    """Return the active QuickScale environment name with a conservative default."""
    return os.getenv("QUICKSCALE_ENVIRONMENT", "local").strip() or "local"


def _mint_snapshot_id() -> str:
    """Return an opaque stable identifier for one stored snapshot."""
    return uuid4().hex


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


def _relative_snapshot_child_path(snapshot_root: Path, child_path: Path) -> str:
    """Return a stable snapshot-relative path for one child file."""
    return child_path.relative_to(snapshot_root).as_posix()


def _build_snapshot_child_descriptor(
    *,
    kind: str,
    status: str,
    relative_path: str,
    local_path: Path | None = None,
    remote_key: str = "",
    error: str = "",
    size_bytes: int | None = None,
    checksum_sha256: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build JSON metadata describing one child stored under a snapshot root."""
    descriptor: dict[str, Any] = {
        "kind": kind,
        "status": status,
        "relative_path": relative_path,
        "local_path": str(local_path) if local_path is not None else "",
    }
    if remote_key:
        descriptor["remote_key"] = remote_key
    if error:
        descriptor["error"] = error
    if size_bytes is not None:
        descriptor["size_bytes"] = size_bytes
    if checksum_sha256:
        descriptor["checksum_sha256"] = checksum_sha256
    if metadata:
        descriptor["metadata"] = metadata
    return descriptor


def _build_snapshot_database_descriptor(
    snapshot: BackupSnapshot,
    artifact: BackupArtifact,
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
        status=BackupSnapshot.STATUS_READY,
        relative_path=relative_path,
        local_path=local_path,
        remote_key=artifact.remote_key,
        size_bytes=artifact.size_bytes,
        checksum_sha256=artifact.checksum_sha256,
        metadata={"backup_format": artifact.backup_format},
    )


def _write_json_file(path: Path, payload: dict[str, Any]) -> None:
    """Write a JSON payload with deterministic formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
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


def _snapshot_sidecar_path(snapshot: BackupSnapshot, filename: str) -> Path:
    """Resolve one sidecar file path under a snapshot root."""
    return Path(snapshot.local_root_path) / filename


def _load_snapshot_sidecar_payload(
    snapshot: BackupSnapshot,
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


def _persist_snapshot_sidecar_payload(
    snapshot: BackupSnapshot,
    *,
    filename: str,
    kind: str,
    payload: dict[str, Any],
    policy: BackupPolicySnapshot | None = None,
    remote_uploader: RemoteUploader | None = None,
) -> dict[str, Any]:
    """Write one sidecar payload and refresh its snapshot descriptor."""
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
        status=BackupSnapshot.STATUS_READY,
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

    resolved_policy = policy or load_policy_snapshot()
    if (
        snapshot.remote_root_key
        and resolved_policy.target_mode == BackupPolicy.TARGET_MODE_PRIVATE_REMOTE
    ):
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
            descriptor["status"] = BackupSnapshot.STATUS_FAILED
            descriptor["error"] = str(exc)
            sidecars[filename] = descriptor
            snapshot.child_descriptors_json = child_descriptors_json
            snapshot.save(update_fields=["child_descriptors_json", "updated_at"])
            raise
        except Exception as exc:
            error_message = f"Private remote upload failed for {filename}: {exc}"
            descriptor["status"] = BackupSnapshot.STATUS_FAILED
            descriptor["error"] = error_message
            sidecars[filename] = descriptor
            snapshot.child_descriptors_json = child_descriptors_json
            snapshot.save(update_fields=["child_descriptors_json", "updated_at"])
            raise BackupError(error_message) from exc

    sidecars[filename] = descriptor
    snapshot.child_descriptors_json = child_descriptors_json
    snapshot.save(update_fields=["child_descriptors_json", "updated_at"])
    return descriptor


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


def _load_storage_helpers() -> StorageHelpersModule:
    """Load the storage helper module behind a typed local boundary."""
    return cast(
        StorageHelpersModule, import_module("quickscale_modules_storage.helpers")
    )


def _build_media_sync_manifest(*, captured_at: datetime) -> dict[str, Any]:
    """Capture private media inventory or fail closed with explicit provider metadata."""
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


def _build_env_var_manifest(*, captured_at: datetime) -> dict[str, Any]:
    """Capture environment variable names only, never their values."""
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


def _build_promotion_verification_placeholder(
    *,
    captured_at: datetime,
) -> dict[str, Any]:
    """Initialize the reserved promotion verification sidecar."""
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


@contextmanager
def _backup_creation_lock(
    local_directory: Path,
    *,
    now: datetime | None = None,
) -> Iterator[None]:
    """Acquire and release a cross-process filesystem lock for backup creation."""
    lock_path = _acquire_backup_lock(local_directory, now=now)
    try:
        yield
    finally:
        _release_backup_lock(lock_path)


def _acquire_backup_lock(
    local_directory: Path,
    *,
    now: datetime | None = None,
) -> Path:
    """Create an exclusive lock file to prevent overlapping backup runs."""
    local_directory.mkdir(parents=True, exist_ok=True)
    lock_path = local_directory / _LOCK_FILENAME
    lock_time = now or datetime.now(timezone.utc)

    for _ in range(2):
        try:
            descriptor = os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError:
            if not _clear_stale_backup_lock(lock_path, now=lock_time):
                raise BackupLockError(
                    "A backup operation is already in progress. Wait for it to "
                    "finish first."
                )
            continue
        except OSError as exc:
            raise BackupError(
                f"Unable to create backup lock file at {lock_path}: {exc}"
            ) from exc

        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "pid": os.getpid(),
                        "created_at": lock_time.astimezone(timezone.utc).isoformat(),
                    },
                    handle,
                )
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            cleanup_error = _cleanup_local_backup_file(lock_path)
            details = f"Unable to write backup lock file at {lock_path}: {exc}"
            if cleanup_error is not None:
                details += f"; cleanup failed: {cleanup_error}"
            raise BackupError(details) from exc

        return lock_path

    raise BackupLockError(
        "A backup operation is already in progress. Wait for it to finish first."
    )


def _clear_stale_backup_lock(lock_path: Path, *, now: datetime) -> bool:
    """Remove an expired lock file so a new backup run can proceed."""
    try:
        lock_mtime = lock_path.stat().st_mtime
    except FileNotFoundError:
        return True

    if (now.timestamp() - lock_mtime) <= _LOCK_TIMEOUT_SECONDS:
        return False

    try:
        lock_path.unlink()
    except FileNotFoundError:
        return True
    except OSError as exc:
        raise BackupError(
            f"Unable to clear stale backup lock file at {lock_path}: {exc}"
        ) from exc
    return True


def _release_backup_lock(lock_path: Path) -> None:
    """Remove the backup lock file after the operation finishes."""
    try:
        lock_path.unlink()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise BackupError(
            f"Unable to remove backup lock file at {lock_path}: {exc}"
        ) from exc


def _cleanup_local_backup_file(local_path: Path) -> str | None:
    """Delete a local backup file and return an error message if cleanup fails."""
    try:
        local_path.unlink(missing_ok=True)
    except OSError as exc:
        return str(exc)
    return None


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
    remote_deleter: RemoteDeleter | None = None,
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


def _upload_snapshot_child_to_private_remote(
    local_path: Path,
    *,
    policy: BackupPolicySnapshot,
    snapshot_remote_root: str,
    relative_path: str,
    remote_uploader: RemoteUploader,
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


def _capture_snapshot_sidecars(
    *,
    snapshot: BackupSnapshot,
    policy: BackupPolicySnapshot,
    captured_at: datetime,
    remote_uploader: RemoteUploader | None,
) -> tuple[dict[str, Any], list[str]]:
    """Capture private sidecar manifests without breaking the dump-first contract."""
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
                status=BackupSnapshot.STATUS_READY,
                relative_path=relative_path,
                local_path=local_path,
                size_bytes=local_path.stat().st_size,
                checksum_sha256=_compute_sha256(local_path),
                metadata=metadata,
            )
            if policy.target_mode == BackupPolicy.TARGET_MODE_PRIVATE_REMOTE:
                try:
                    remote_key = _upload_snapshot_child_to_private_remote(
                        local_path,
                        policy=policy,
                        snapshot_remote_root=snapshot.remote_root_key,
                        relative_path=relative_path,
                        remote_uploader=uploader,
                    )
                except BackupError as exc:
                    descriptor["status"] = BackupSnapshot.STATUS_FAILED
                    descriptor["error"] = str(exc)
                    failures.append(f"{filename}: {exc}")
                except Exception as exc:
                    error_message = (
                        f"Private remote upload failed for {filename}: {exc}"
                    )
                    descriptor["status"] = BackupSnapshot.STATUS_FAILED
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
                status=BackupSnapshot.STATUS_FAILED,
                relative_path=relative_path,
                local_path=local_path,
                error=error_message,
            )
            failures.append(f"{filename}: {error_message}")

    child_descriptors_json["sidecars"] = sidecar_descriptors
    return child_descriptors_json, failures


def _get_authoritative_snapshot_for_artifact(
    artifact: BackupArtifact,
) -> BackupSnapshot | None:
    """Return the linked snapshot for a dump artifact if one exists."""
    try:
        return artifact.authoritative_snapshot
    except BackupSnapshot.DoesNotExist:
        return None


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


def _delete_snapshot_storage(
    snapshot: BackupSnapshot,
    *,
    policy: BackupPolicySnapshot,
    remote_deleter: RemoteDeleter | None = None,
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


def _snapshot_uses_private_remote(snapshot: BackupSnapshot) -> bool:
    """Return whether the stored snapshot topology expects private remote upload."""
    if snapshot.remote_root_key.strip():
        return True

    artifact = snapshot.authoritative_dump
    return artifact is not None and (
        artifact.storage_target == BackupArtifact.STORAGE_TARGET_PRIVATE_REMOTE
    )


def _build_snapshot_capture_resume_policy(
    snapshot: BackupSnapshot,
    policy: BackupPolicySnapshot,
) -> BackupPolicySnapshot:
    """Align the active policy with the stored snapshot topology for resume."""
    resolved_policy = replace(
        policy,
        target_mode=(
            BackupPolicy.TARGET_MODE_PRIVATE_REMOTE
            if _snapshot_uses_private_remote(snapshot)
            else BackupPolicy.TARGET_MODE_LOCAL
        ),
    )

    if resolved_policy.target_mode != BackupPolicy.TARGET_MODE_PRIVATE_REMOTE:
        return resolved_policy

    artifact = snapshot.authoritative_dump
    if artifact is None:
        return resolved_policy

    return _resolve_artifact_remote_policy(artifact, resolved_policy)


def _build_snapshot_lock_directory(snapshot: BackupSnapshot) -> Path:
    """Resolve the filesystem directory used for snapshot-scoped capture locking."""
    snapshot_root = Path(snapshot.local_root_path)
    if snapshot_root.parent.name == _SNAPSHOTS_DIRECTORY_NAME:
        return snapshot_root.parent.parent
    return snapshot_root.parent


def _snapshot_capture_is_complete(snapshot: BackupSnapshot) -> bool:
    """Return whether a stored snapshot already has a complete capture payload."""
    if snapshot.status != BackupSnapshot.STATUS_READY:
        return False

    artifact = snapshot.authoritative_dump
    if artifact is None or artifact.status == BackupArtifact.STATUS_DELETED:
        return False

    child_descriptors_json = (
        snapshot.child_descriptors_json
        if isinstance(snapshot.child_descriptors_json, dict)
        else {}
    )
    database_descriptor = child_descriptors_json.get("database")
    if not isinstance(database_descriptor, dict):
        return False
    if (
        str(database_descriptor.get("status", "")).strip()
        != BackupSnapshot.STATUS_READY
    ):
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
        if str(descriptor.get("status", "")).strip() != BackupSnapshot.STATUS_READY:
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
        return Path(artifact.local_path)
    return (
        Path(snapshot.local_root_path)
        / _SNAPSHOT_DATABASE_DIRECTORY_NAME
        / artifact.filename
    )


def _resume_backup_capture(
    snapshot_id: str,
    *,
    initiated_by: AbstractBaseUser | None = None,
    trigger: str,
    policy: BackupPolicySnapshot,
    shell_runner: ShellCommandRunner | None,
    remote_uploader: RemoteUploader | None,
    now: datetime,
) -> BackupArtifact:
    """Resume an incomplete snapshot capture using the existing snapshot id."""
    snapshot = get_backup_snapshot(snapshot_id)
    resolved_policy = _build_snapshot_capture_resume_policy(snapshot, policy)
    issues = validate_policy_snapshot(resolved_policy)
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
                if "postgresql" in engine:
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
                    backup_format = "pg_dump_custom"
                    filename = build_backup_filename(
                        resolved_policy,
                        now=now,
                        suffix="dump",
                    )
                else:
                    backup_format = "json"
                    filename = build_backup_filename(
                        resolved_policy,
                        now=now,
                        suffix="json",
                    )
                local_path = database_directory / filename
                if backup_format == "pg_dump_custom":
                    _dump_postgresql_database(
                        local_path,
                        connection_settings,
                        shell_runner=shell_runner,
                    )
                else:
                    _dump_database_as_json(local_path)

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

        if (
            resolved_policy.target_mode == BackupPolicy.TARGET_MODE_PRIVATE_REMOTE
            and not artifact.remote_key
        ):
            uploader = remote_uploader or _upload_to_private_remote
            local_path = _resolve_snapshot_database_local_path(snapshot, artifact)
            try:
                remote_key = _upload_snapshot_child_to_private_remote(
                    local_path,
                    policy=resolved_policy,
                    snapshot_remote_root=snapshot.remote_root_key,
                    relative_path=str(
                        child_descriptors_json["database"]["relative_path"]
                    ),
                    remote_uploader=uploader,
                )
            except BackupError as exc:
                _mark_remote_upload_failure(artifact, local_path=local_path, error=exc)
                child_descriptors_json["database"]["status"] = (
                    BackupSnapshot.STATUS_FAILED
                )
                child_descriptors_json["database"]["error"] = str(exc)
                _mark_snapshot_failed(
                    snapshot,
                    failure_note=f"database dump remote upload failed: {exc}",
                    child_descriptors_json=child_descriptors_json,
                )
                raise
            except Exception as exc:
                upload_error = BackupError(
                    f"Private remote upload failed for {artifact.filename}: {exc}"
                )
                _mark_remote_upload_failure(
                    artifact,
                    local_path=local_path,
                    error=upload_error,
                )
                child_descriptors_json["database"]["status"] = (
                    BackupSnapshot.STATUS_FAILED
                )
                child_descriptors_json["database"]["error"] = str(upload_error)
                _mark_snapshot_failed(
                    snapshot,
                    failure_note=(
                        f"database dump remote upload failed: {upload_error}"
                    ),
                    child_descriptors_json=child_descriptors_json,
                )
                raise upload_error from exc

            artifact.remote_key = remote_key
            artifact.status = BackupArtifact.STATUS_READY
            metadata_json = dict(artifact.metadata_json)
            metadata_json.pop("remote_upload_error", None)
            metadata_json.pop("remote_upload_failed_at", None)
            artifact.metadata_json = metadata_json
            update_fields = ["remote_key", "status", "metadata_json", "updated_at"]
            if artifact.validation_notes.startswith("remote upload failed: "):
                artifact.validation_notes = ""
                update_fields.insert(3, "validation_notes")
            artifact.save(update_fields=update_fields)

            child_descriptors_json["database"]["remote_key"] = remote_key
            child_descriptors_json["database"].pop("error", None)
            snapshot.child_descriptors_json = child_descriptors_json
            snapshot.save(update_fields=["child_descriptors_json", "updated_at"])

        child_descriptors_json, sidecar_failures = _capture_snapshot_sidecars(
            snapshot=snapshot,
            policy=resolved_policy,
            captured_at=now,
            remote_uploader=remote_uploader,
        )
        snapshot.child_descriptors_json = child_descriptors_json
        if sidecar_failures:
            failure_note = "snapshot sidecar capture failed: " + "; ".join(
                sidecar_failures
            )
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

        try:
            prune_expired_backups(policy=resolved_policy, now=now)
        except Exception as exc:
            _record_prune_failure_without_masking_success(artifact, error=exc)
        return artifact


def create_backup(
    *,
    initiated_by: AbstractBaseUser | None = None,
    trigger: str = "manual",
    policy: BackupPolicySnapshot | None = None,
    shell_runner: ShellCommandRunner | None = None,
    remote_uploader: RemoteUploader | None = None,
    remote_deleter: RemoteDeleter | None = None,
    now: datetime | None = None,
    resume_snapshot_id: str | None = None,
) -> BackupArtifact:
    """Create a backup artifact, optionally offloading it to private remote storage."""
    resolved_policy = policy or load_policy_snapshot()
    backup_started_at = now or datetime.now(timezone.utc)

    if resume_snapshot_id is not None:
        return _resume_backup_capture(
            resume_snapshot_id,
            initiated_by=initiated_by,
            trigger=trigger,
            policy=resolved_policy,
            shell_runner=shell_runner,
            remote_uploader=remote_uploader,
            now=backup_started_at,
        )

    issues = validate_policy_snapshot(resolved_policy)
    if issues:
        raise BackupConfigurationError("; ".join(issues))

    local_directory = get_local_backup_directory(resolved_policy)
    local_directory.mkdir(parents=True, exist_ok=True)

    with _backup_creation_lock(local_directory, now=backup_started_at):
        connection_settings = django.db.connections["default"].settings_dict
        engine = str(connection_settings.get("ENGINE", ""))
        database_name = str(connection_settings.get("NAME", ""))
        backup_note = ""
        database_server_version: str | None = None
        database_server_major: int | None = None
        dump_client_version: str | None = None
        dump_client_major: int | None = None
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
            if "postgresql" in engine:
                (
                    database_server_version,
                    database_server_major,
                    dump_client_version,
                    dump_client_major,
                ) = _require_postgresql_18_contract(
                    database_engine=engine,
                    executable="pg_dump",
                    operation="backup creation",
                )
                backup_format = "pg_dump_custom"
                filename = build_backup_filename(
                    resolved_policy,
                    now=backup_started_at,
                    suffix="dump",
                )
                local_path = database_directory / filename
            else:
                backup_format = "json"
                filename = build_backup_filename(
                    resolved_policy,
                    now=backup_started_at,
                    suffix="json",
                )
                local_path = database_directory / filename
        except Exception as exc:
            _mark_snapshot_failed(
                snapshot,
                failure_note=f"snapshot preparation failed: {exc}",
            )
            raise BackupError(
                f"Snapshot capture failed for snapshot '{snapshot.snapshot_id}': {exc}"
            ) from exc
        try:
            if backup_format == "pg_dump_custom":
                _dump_postgresql_database(
                    local_path,
                    connection_settings,
                    shell_runner=shell_runner,
                )
            else:
                _dump_database_as_json(local_path)

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
        if backup_note:
            metadata["degraded_backup_reason"] = backup_note
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
            validation_notes=backup_note,
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

        if resolved_policy.target_mode == BackupPolicy.TARGET_MODE_PRIVATE_REMOTE:
            uploader = remote_uploader or _upload_to_private_remote
            try:
                remote_key = _upload_snapshot_child_to_private_remote(
                    local_path,
                    policy=resolved_policy,
                    snapshot_remote_root=snapshot.remote_root_key,
                    relative_path=str(
                        child_descriptors_json["database"]["relative_path"]
                    ),
                    remote_uploader=uploader,
                )
            except BackupError as exc:
                _mark_remote_upload_failure(artifact, local_path=local_path, error=exc)
                child_descriptors_json["database"]["status"] = (
                    BackupSnapshot.STATUS_FAILED
                )
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
                child_descriptors_json["database"]["status"] = (
                    BackupSnapshot.STATUS_FAILED
                )
                child_descriptors_json["database"]["error"] = str(upload_error)
                _mark_snapshot_failed(
                    snapshot,
                    failure_note=(
                        f"database dump remote upload failed: {upload_error}"
                    ),
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
                child_descriptors_json["database"]["status"] = (
                    BackupSnapshot.STATUS_FAILED
                )
                child_descriptors_json["database"]["remote_key"] = remote_key
                child_descriptors_json["database"]["error"] = message
                _mark_snapshot_failed(
                    snapshot,
                    failure_note=message,
                    child_descriptors_json=child_descriptors_json,
                )
                raise BackupError(message) from exc

            child_descriptors_json["database"]["remote_key"] = remote_key
            snapshot.child_descriptors_json = child_descriptors_json
            snapshot.save(update_fields=["child_descriptors_json", "updated_at"])

        child_descriptors_json, sidecar_failures = _capture_snapshot_sidecars(
            snapshot=snapshot,
            policy=resolved_policy,
            captured_at=backup_started_at,
            remote_uploader=remote_uploader,
        )
        snapshot.child_descriptors_json = child_descriptors_json
        if sidecar_failures:
            failure_note = "snapshot sidecar capture failed: " + "; ".join(
                sidecar_failures
            )
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
            snapshot.failure_note = ""
            snapshot.save(
                update_fields=[
                    "child_descriptors_json",
                    "status",
                    "failure_note",
                    "updated_at",
                ]
            )
            _persist_snapshot_metadata_on_artifact(artifact, snapshot)

        try:
            prune_expired_backups(policy=resolved_policy, now=backup_started_at)
        except Exception as exc:
            _record_prune_failure_without_masking_success(artifact, error=exc)
        return artifact


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


def build_backup_snapshot_report(
    snapshot: BackupSnapshot,
    *,
    now: datetime | None = None,
    sidecar_payloads: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Build a structured report for one stored snapshot."""
    report_time = now or django_timezone.now()
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


def record_backup_snapshot_verification(
    snapshot_id: str,
    *,
    route: str,
    phase: str,
    status: str,
    payload: dict[str, Any],
    now: datetime | None = None,
    policy: BackupPolicySnapshot | None = None,
    remote_uploader: RemoteUploader | None = None,
) -> dict[str, Any]:
    """Append one route-specific report to the verification sidecar."""
    normalized_route = route.strip()
    normalized_phase = phase.strip()
    normalized_status = status.strip()
    if not normalized_route:
        raise BackupConfigurationError("route cannot be blank")
    if not normalized_phase:
        raise BackupConfigurationError("phase cannot be blank")
    if not normalized_status:
        raise BackupConfigurationError("status cannot be blank")

    snapshot = get_backup_snapshot(snapshot_id)
    recorded_at = now or django_timezone.now()
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

    verification_payload = {
        "manifest_version": 1,
        "captured_at": verification_payload.get(
            "captured_at",
            snapshot.created_at.astimezone(timezone.utc).isoformat(),
        ),
        "snapshot_id": snapshot.snapshot_id,
        "project_slug": _get_project_slug(),
        "source_environment": snapshot.source_environment,
        "status": normalized_status,
        "updated_at": recorded_at.astimezone(timezone.utc).isoformat(),
        "reports": [
            *existing_reports,
            {
                "route": normalized_route,
                "phase": normalized_phase,
                "status": normalized_status,
                "recorded_at": recorded_at.astimezone(timezone.utc).isoformat(),
                "payload": payload,
            },
        ],
        "notes": verification_payload.get(
            "notes",
            "Reserved for route-specific plan and execute reports.",
        ),
        "rollback_pin": {
            "active": snapshot.has_active_rollback_pin(now=recorded_at),
            "expires_at": (
                snapshot.rollback_pin_expires_at.astimezone(timezone.utc).isoformat()
                if snapshot.rollback_pin_expires_at is not None
                else None
            ),
            "reason": snapshot.rollback_pin_reason,
        },
    }
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


def _load_target_runtime_settings() -> dict[str, str]:
    """Load DR target runtime settings passed in through the env prefix."""
    target_settings = {
        key.removeprefix(_DR_TARGET_ENV_PREFIX): value
        for key, value in os.environ.items()
        if key.startswith(_DR_TARGET_ENV_PREFIX)
    }
    if not target_settings:
        raise BackupConfigurationError(
            "Target runtime variables were not provided. Supply QUICKSCALE_DR_TARGET_* env vars before syncing media."
        )
    return target_settings


def _build_s3_storage_from_selection(selection: Any) -> Any:
    """Construct an s3-compatible storage object from one backend selection."""
    from storages.backends.s3 import S3Storage  # type: ignore[import-untyped]

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
    except Exception as exc:
        raise BackupConfigurationError(
            "Media sync requires quickscale_modules_storage.helpers to resolve storage backends."
        ) from exc

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
    target_settings = _load_target_runtime_settings()
    target_runtime = _resolve_media_runtime(
        target_settings,
        require_s3_compatible=(
            str(target_settings.get(_DR_TARGET_ROUTE_KIND_KEY, "")).strip() == "railway"
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


def set_backup_snapshot_rollback_pin(
    snapshot_id: str,
    *,
    ttl_hours: int,
    reason: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Set or refresh a time-bounded rollback pin on one stored snapshot."""
    if ttl_hours < 1:
        raise BackupConfigurationError("ttl_hours must be at least 1")

    resolved_reason = reason.strip()
    if not resolved_reason:
        raise BackupConfigurationError("reason cannot be blank")

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
    snapshot.rollback_pin_expires_at = pinned_at + timedelta(hours=ttl_hours)
    snapshot.rollback_pin_reason = resolved_reason
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
    snapshot.rollback_pin_expires_at = None
    snapshot.rollback_pin_reason = ""
    snapshot.save(
        update_fields=[
            "rollback_pin_expires_at",
            "rollback_pin_reason",
            "updated_at",
        ]
    )
    return build_backup_snapshot_report(snapshot, now=cleared_at)


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


def download_backup_path(artifact: BackupArtifact) -> Path:
    """Return the local operator download path for an artifact."""
    if not artifact.local_path:
        raise BackupError("This artifact does not have a local download path.")

    local_path = Path(artifact.local_path)
    if not local_path.exists():
        raise BackupError(f"Backup file not found: {local_path}")
    return local_path


def delete_artifact_files(
    artifact: BackupArtifact,
    *,
    policy: BackupPolicySnapshot | None = None,
    remote_deleter: RemoteDeleter | None = None,
) -> None:
    """Delete local and remote artifact files without deleting the database row."""
    resolved_policy = policy or load_policy_snapshot()
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
    remote_deleter: RemoteDeleter | None = None,
) -> int:
    """Delete expired backup files and mark their metadata records as deleted."""
    resolved_policy = policy or load_policy_snapshot()
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
        if confirmation.strip() != restore_source.confirmation_value:
            raise BackupRestoreBlocked(
                "Confirmation must exactly match the backup filename."
            )

        if restore_source.is_export_only():
            if restore_source.artifact is None:
                raise BackupRestoreBlocked(
                    "Restore blocked because JSON file inputs are not a supported "
                    "restore input."
                )
            raise BackupRestoreBlocked(
                "Restore blocked because export_only artifacts are not a supported "
                "restore input."
            )

        source_issues = _get_restore_source_validation_issues(restore_source)
        if source_issues:
            raise BackupRestoreBlocked(
                "Restore blocked because backup validation failed: "
                + "; ".join(source_issues)
            )

        current_engine = str(
            django.db.connections["default"].settings_dict.get("ENGINE") or ""
        ).strip()
        compatibility_issues = _get_restore_source_compatibility_issues(
            restore_source,
            current_engine,
        )
        if compatibility_issues:
            compatibility_prefix = (
                "Restore blocked because artifact compatibility validation failed: "
                if restore_source.artifact is not None
                else "Restore blocked because restore compatibility validation failed: "
            )
            raise BackupRestoreBlocked(
                compatibility_prefix + "; ".join(compatibility_issues)
            )

        if dry_run:
            _ensure_postgresql_18_restore_runtime(current_engine)
            _ensure_operator_supplied_custom_archive_valid(
                restore_source,
                shell_runner=shell_runner,
            )
            return RestoreResult(
                executed=False,
                dry_run=True,
                message="Restore validation completed successfully (dry run).",
            )

        if not _restore_execution_allowed():
            message = (
                "Restore execution is blocked outside local development until "
                "QUICKSCALE_BACKUPS_ALLOW_RESTORE=true is set."
            )
            if allow_production:
                message += " --allow-production does not bypass this environment gate."
            raise BackupRestoreBlocked(message)

        if restore_source.backup_format != "pg_dump_custom":
            raise BackupRestoreBlocked(
                "Executable restore is only supported for PostgreSQL custom-format "
                "artifacts. Use --dry-run for JSON fallback backups."
            )

        _ensure_postgresql_18_restore_runtime(current_engine)
        _ensure_operator_supplied_custom_archive_valid(
            restore_source,
            shell_runner=shell_runner,
        )

        connection_settings = django.db.connections["default"].settings_dict
        command, env = _build_pg_restore_command(
            restore_source.local_path,
            connection_settings,
        )
        runner = shell_runner or _run_shell_command
        runner(command, env=env)

        restore_warnings: tuple[RestoreWarning, ...] = ()
        if restore_source.artifact is not None:
            restore_warnings = _persist_restore_artifact_metadata(
                restore_source.artifact,
                restored_at=django_timezone.now(),
            )

        return RestoreResult(
            executed=True,
            dry_run=False,
            message=(f"Restore executed for {restore_source.confirmation_value}."),
            warnings=restore_warnings,
        )


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


def _extract_leading_major_version(version_text: str | None) -> int | None:
    """Return the leading major version number from a server version string."""
    if not version_text:
        return None

    match = _LEADING_MAJOR_VERSION_PATTERN.match(version_text)
    if match is None:
        return None

    major = int(match.group(1))
    return major if major > 0 else None


def _extract_any_major_version(version_text: str | None) -> int | None:
    """Return the first major version number found in a tool version string."""
    if not version_text:
        return None

    match = _ANY_MAJOR_VERSION_PATTERN.search(version_text)
    if match is None:
        return None

    major = int(match.group(1))
    return major if major > 0 else None


def _require_postgresql_18_contract(
    *,
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
            "determined." + _postgresql_18_client_tooling_guidance()
        )
    if tool_major != _REQUIRED_POSTGRESQL_MAJOR:
        raise BackupError(
            "PostgreSQL "
            f"{operation} requires PostgreSQL {_REQUIRED_POSTGRESQL_MAJOR} "
            f"{executable} tooling, found '{tool_version}'."
            + _postgresql_18_client_tooling_guidance()
        )

    return database_server_version, database_server_major, tool_version, tool_major


def _get_postgresql_tool_version(executable: str) -> str:
    """Return the installed PostgreSQL client-tool version string."""
    guidance = (
        _postgresql_18_client_tooling_guidance()
        if executable in {"pg_dump", "pg_restore"}
        else ""
    )
    try:
        result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            check=False,
            text=True,
            env=os.environ.copy(),
        )
    except FileNotFoundError as exc:
        raise _missing_executable_backup_error(executable) from exc

    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise BackupError(
            f"Unable to determine {executable} version: {stderr}{guidance}"
        )

    output = result.stdout.strip() or result.stderr.strip()
    if not output:
        raise BackupError(
            f"Unable to determine {executable} version: command returned no output."
            + guidance
        )
    return output


def _database_server_version_query(engine: str) -> str | None:
    """Return a read-only version query for supported backup backends."""
    engine_family = _database_engine_family(engine)
    if engine_family == "postgresql":
        return "SHOW server_version"
    if engine_family == "sqlite":
        return "SELECT sqlite_version()"
    return None


def _get_restore_compatibility_issues(artifact: BackupArtifact) -> list[str]:
    """Return restore guardrail issues for current database engine compatibility."""
    issues: list[str] = []
    connection_settings = django.db.connections["default"].settings_dict
    current_engine = str(connection_settings.get("ENGINE") or "").strip()
    current_engine_family = _database_engine_family(current_engine)
    artifact_engine_family = _database_engine_family(artifact.database_engine)

    if artifact_engine_family != current_engine_family:
        issues.append(
            "artifact database engine "
            f"'{artifact.database_engine}' is incompatible with current database "
            f"engine '{current_engine}'"
        )

    expected_format = _expected_backup_format_for_engine(current_engine)
    if artifact.backup_format != expected_format:
        issues.append(
            "artifact backup format "
            f"'{artifact.backup_format}' is incompatible with current database "
            f"engine '{current_engine}' (expected '{expected_format}')"
        )

    if (
        artifact_engine_family == "postgresql"
        and artifact.backup_format == "pg_dump_custom"
    ):
        if (
            artifact.database_server_major is not None
            and artifact.database_server_major != _REQUIRED_POSTGRESQL_MAJOR
        ):
            issues.append(
                "artifact database server major "
                f"'{artifact.database_server_major}' is incompatible with the "
                f"PostgreSQL {_REQUIRED_POSTGRESQL_MAJOR} restore contract"
            )
        if (
            artifact.dump_client_major is not None
            and artifact.dump_client_major != _REQUIRED_POSTGRESQL_MAJOR
        ):
            issues.append(
                "artifact dump client major "
                f"'{artifact.dump_client_major}' is incompatible with the "
                f"PostgreSQL {_REQUIRED_POSTGRESQL_MAJOR} restore contract"
            )

    return issues


def _collect_local_backup_validation_issues(
    local_path: Path | None,
    *,
    backup_format: str,
    expected_checksum: str | None = None,
    expected_size: int | None = None,
) -> list[str]:
    """Validate one local backup file without mutating artifact state."""
    issues: list[str] = []

    if local_path is None or not local_path.exists():
        issues.append("local backup artifact is missing")
        return issues

    if expected_checksum is not None:
        calculated_checksum = _compute_sha256(local_path)
        if calculated_checksum != expected_checksum:
            issues.append("checksum mismatch detected")

    if expected_size is not None:
        actual_size = local_path.stat().st_size
        if actual_size != expected_size:
            issues.append("size mismatch detected")

    if backup_format == "json":
        try:
            json.loads(local_path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            issues.append("json backup payload is not valid JSON")
        except json.JSONDecodeError:
            issues.append("json backup payload is not valid JSON")

    return issues


def _get_restore_source_validation_issues(
    restore_source: ResolvedRestoreSource,
) -> list[str]:
    """Return validation issues for the resolved restore source."""
    if restore_source.artifact is not None:
        return _collect_local_backup_validation_issues(
            restore_source.local_path,
            backup_format=restore_source.artifact.backup_format,
            expected_checksum=restore_source.artifact.checksum_sha256,
            expected_size=restore_source.artifact.size_bytes,
        )

    if not restore_source.local_path.exists():
        return [f"restore file not found: {restore_source.local_path}"]
    if not restore_source.local_path.is_file():
        return [f"restore file is not a regular file: {restore_source.local_path}"]
    return []


def _get_restore_source_compatibility_issues(
    restore_source: ResolvedRestoreSource,
    current_engine: str,
) -> list[str]:
    """Return compatibility issues for artifact and operator-supplied sources."""
    if restore_source.artifact is not None:
        return _get_restore_compatibility_issues(restore_source.artifact)

    if _database_engine_family(current_engine) != "postgresql":
        return ["operator-supplied restore files require a PostgreSQL target database"]
    return []


def _ensure_operator_supplied_custom_archive_valid(
    restore_source: ResolvedRestoreSource,
    *,
    shell_runner: ShellCommandRunner | None = None,
) -> None:
    """Require file-mode restore inputs to be real PostgreSQL custom archives."""
    if (
        restore_source.artifact is not None
        or restore_source.backup_format != "pg_dump_custom"
    ):
        return

    try:
        with restore_source.local_path.open("rb") as handle:
            archive_magic = handle.read(len(_POSTGRESQL_CUSTOM_ARCHIVE_MAGIC))
    except OSError as exc:
        raise BackupRestoreBlocked(
            "Restore blocked because the operator-supplied file could not be "
            f"inspected: {exc}"
        ) from exc

    if archive_magic != _POSTGRESQL_CUSTOM_ARCHIVE_MAGIC:
        raise BackupRestoreBlocked(
            "Restore blocked because operator-supplied file is not a valid "
            "PostgreSQL custom archive."
        )

    runner = shell_runner or _run_shell_command
    try:
        runner(["pg_restore", "--list", str(restore_source.local_path)], env=None)
    except BackupError as exc:
        raise BackupRestoreBlocked(
            "Restore blocked because operator-supplied file is not a valid "
            f"PostgreSQL custom archive: {exc}"
        ) from exc


def _normalize_restore_file_path(file_path: str | Path) -> Path:
    """Resolve operator-supplied restore file paths relative to the current cwd."""
    resolved_path = Path(file_path).expanduser()
    if not resolved_path.is_absolute():
        resolved_path = Path.cwd() / resolved_path
    return resolved_path


def _detect_restore_file_format(file_path: Path) -> str:
    """Infer the operator-supplied restore input format from the file name."""
    if file_path.suffix.lower() == ".json":
        return "json"
    return "pg_dump_custom"


@contextmanager
def _resolve_restore_source(
    *,
    artifact: BackupArtifact | None,
    file_path: str | Path | None,
    snapshot_id: str | None,
    resolution_mode: RestoreSourceResolutionMode,
    policy: BackupPolicySnapshot | None,
    remote_materializer: RemoteMaterializer | None,
) -> Iterator[ResolvedRestoreSource]:
    """Resolve one restore source into a local file path for the guarded pipeline."""
    provided_source_count = sum(
        source is not None for source in (artifact, file_path, snapshot_id)
    )
    if provided_source_count != 1:
        raise BackupRestoreBlocked(
            "Choose exactly one restore source: an artifact id, --snapshot-id, or --file PATH."
        )

    if file_path is not None:
        resolved_path = _normalize_restore_file_path(file_path)
        yield ResolvedRestoreSource(
            confirmation_value=resolved_path.name,
            local_path=resolved_path,
            backup_format=_detect_restore_file_format(resolved_path),
        )
        return

    if snapshot_id is not None:
        artifact = _resolve_authoritative_snapshot_dump(snapshot_id)

    assert artifact is not None
    local_path = Path(artifact.local_path) if artifact.local_path else None
    if local_path is not None and local_path.exists():
        yield ResolvedRestoreSource(
            confirmation_value=artifact.filename,
            local_path=local_path,
            backup_format=artifact.backup_format,
            artifact=artifact,
        )
        return

    if resolution_mode == RestoreSourceResolutionMode.LOCAL_ONLY:
        raise BackupRestoreBlocked(
            "Restore blocked because the local backup artifact is missing and "
            "this restore source resolution mode does not allow private remote "
            "materialization."
        )

    if not artifact.remote_key:
        raise BackupRestoreBlocked(
            "Restore blocked because the local backup artifact is missing and no "
            "private remote artifact is available."
        )

    resolved_policy = _resolve_artifact_remote_policy(
        artifact,
        policy or load_policy_snapshot(),
    )
    materializer = remote_materializer or _materialize_private_remote_key
    with TemporaryDirectory(prefix="quickscale-backups-restore-") as temp_dir:
        materialized_path = Path(temp_dir) / artifact.filename
        try:
            materializer(artifact.remote_key, resolved_policy, materialized_path)
        except BackupError as exc:
            raise BackupRestoreBlocked(
                "Restore blocked because private remote materialization failed for "
                f"{artifact.filename}: {exc}"
            ) from exc
        except Exception as exc:
            raise BackupRestoreBlocked(
                "Restore blocked because private remote materialization failed for "
                f"{artifact.filename}: {exc}"
            ) from exc

        if not materialized_path.exists():
            raise BackupRestoreBlocked(
                "Restore blocked because private remote materialization did not "
                f"produce a local file for {artifact.filename}."
            )

        yield ResolvedRestoreSource(
            confirmation_value=artifact.filename,
            local_path=materialized_path,
            backup_format=artifact.backup_format,
            artifact=artifact,
        )


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

    return artifact


def _ensure_postgresql_18_restore_runtime(current_engine: str) -> None:
    """Require the current restore runtime to satisfy the PostgreSQL 18 contract."""
    if _database_engine_family(current_engine) != "postgresql":
        return

    try:
        _require_postgresql_18_contract(
            database_engine=current_engine,
            executable="pg_restore",
            operation="restore",
        )
    except BackupError as exc:
        raise BackupRestoreBlocked(str(exc)) from exc


def _database_engine_family(engine: str) -> str:
    """Normalize database engines into restore compatibility families."""
    normalized_engine = engine.strip().lower()
    if "postgresql" in normalized_engine:
        return "postgresql"
    if "sqlite" in normalized_engine:
        return "sqlite"
    return normalized_engine


def _expected_backup_format_for_engine(engine: str) -> str:
    """Return the backup format QuickScale expects for the current engine."""
    if _database_engine_family(engine) == "postgresql":
        return "pg_dump_custom"
    return "json"


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


def _get_project_slug() -> str:
    base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))
    candidate = base_dir.name.strip()
    if candidate:
        return candidate
    return settings.ROOT_URLCONF.split(".", maxsplit=1)[0]


def _compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 64), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dump_database_as_json(local_path: Path) -> None:
    buffer = StringIO()
    call_command("dumpdata", stdout=buffer)
    local_path.write_text(buffer.getvalue(), encoding="utf-8")


def _dump_postgresql_database(
    local_path: Path,
    connection_settings: dict[str, Any],
    *,
    shell_runner: ShellCommandRunner | None = None,
) -> None:
    command, env = _build_pg_dump_command(local_path, connection_settings)
    runner = shell_runner or _run_shell_command
    runner(command, env=env)


def _build_pg_dump_command(
    local_path: Path,
    connection_settings: dict[str, Any],
) -> tuple[list[str], dict[str, str] | None]:
    command = ["pg_dump", "--format=c", "--file", str(local_path)]
    if host := str(connection_settings.get("HOST") or "").strip():
        command.extend(["--host", host])
    if port := str(connection_settings.get("PORT") or "").strip():
        command.extend(["--port", port])
    if user := str(connection_settings.get("USER") or "").strip():
        command.extend(["--username", user])

    database_name = str(connection_settings.get("NAME") or "").strip()
    if not database_name:
        raise BackupConfigurationError("DATABASES['default']['NAME'] is required")
    command.append(database_name)

    password = str(connection_settings.get("PASSWORD") or "").strip()
    env = None
    if password:
        env = {"PGPASSWORD": password}
    return command, env


def _build_pg_restore_command(
    local_path: Path,
    connection_settings: dict[str, Any],
) -> tuple[list[str], dict[str, str] | None]:
    command = [
        "pg_restore",
        "--clean",
        "--if-exists",
        "--no-owner",
    ]
    if host := str(connection_settings.get("HOST") or "").strip():
        command.extend(["--host", host])
    if port := str(connection_settings.get("PORT") or "").strip():
        command.extend(["--port", port])
    if user := str(connection_settings.get("USER") or "").strip():
        command.extend(["--username", user])

    database_name = str(connection_settings.get("NAME") or "").strip()
    if not database_name:
        raise BackupConfigurationError("DATABASES['default']['NAME'] is required")

    command.extend(["--dbname", database_name, str(local_path)])
    password = str(connection_settings.get("PASSWORD") or "").strip()
    env = None
    if password:
        env = {"PGPASSWORD": password}
    return command, env


def _run_shell_command(
    command: Sequence[str],
    *,
    env: dict[str, str] | None = None,
) -> None:
    command_env = os.environ.copy()
    if env:
        command_env.update(env)

    try:
        result = subprocess.run(
            list(command),
            capture_output=True,
            check=False,
            text=True,
            env=command_env,
        )
    except FileNotFoundError as exc:
        executable = str(command[0]).strip() if command else "command"
        raise _missing_executable_backup_error(executable) from exc
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise BackupError(f"Command failed: {' '.join(command)} :: {stderr}")


def _missing_executable_backup_error(executable: str) -> BackupError:
    """Build a consistent missing-executable error for shell-backed operations."""
    hint = ""
    if executable in {"pg_dump", "pg_restore"}:
        hint = _postgresql_18_client_tooling_guidance()
    return BackupError(
        f"Required executable '{executable}' is not installed in this runtime.{hint}"
    )


def _resolve_private_remote_credentials(
    policy: BackupPolicySnapshot,
) -> tuple[str, str]:
    """Resolve runtime private-remote credentials from the configured env vars."""
    access_key_id = policy.resolve_remote_access_key_id()
    secret_access_key = policy.resolve_remote_secret_access_key()

    if not access_key_id:
        env_var_name = (
            policy.remote_access_key_id_env_var.strip()
            or _DEFAULT_REMOTE_ACCESS_KEY_ID_ENV_VAR
        )
        raise BackupConfigurationError(
            f"Environment variable '{env_var_name}' is required for private_remote backups"
        )
    if not secret_access_key:
        env_var_name = (
            policy.remote_secret_access_key_env_var.strip()
            or _DEFAULT_REMOTE_SECRET_ACCESS_KEY_ENV_VAR
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
    storage.delete(remote_key)


def _restore_execution_allowed() -> bool:
    if settings.DEBUG:
        return True
    return os.getenv("QUICKSCALE_BACKUPS_ALLOW_RESTORE", "").strip().lower() == "true"
