"""Operational services for private backup creation, validation, pruning, and restore."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import hashlib
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from importlib import import_module
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, Sequence

import django
from django.apps import apps
from django.conf import settings
from django.core.files import File
from django.core.management import call_command
from django.utils import timezone as django_timezone

from quickscale_modules_backups.models import BackupArtifact, BackupPolicy

if TYPE_CHECKING:
    from django.contrib.auth.base_user import AbstractBaseUser

_LOCK_FILENAME = ".quickscale-backup-create.lock"
_LOCK_TIMEOUT_SECONDS = 300
_DEFAULT_REMOTE_ACCESS_KEY_ID_ENV_VAR = "QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID"
_DEFAULT_REMOTE_SECRET_ACCESS_KEY_ENV_VAR = (
    "QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY"
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
class RestoreResult:
    """Return value for guarded restore execution."""

    executed: bool
    dry_run: bool
    message: str


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
    """Persist a failed remote-offload outcome and clean local leftovers."""
    cleanup_error = _cleanup_local_backup_file(local_path)
    notes = f"remote upload failed: {error}"
    if cleanup_error is None:
        artifact.local_path = ""
    else:
        notes += f"; cleanup failed: {cleanup_error}"

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


def create_backup(
    *,
    initiated_by: AbstractBaseUser | None = None,
    trigger: str = "manual",
    policy: BackupPolicySnapshot | None = None,
    shell_runner: ShellCommandRunner | None = None,
    remote_uploader: RemoteUploader | None = None,
    remote_deleter: RemoteDeleter | None = None,
    now: datetime | None = None,
) -> BackupArtifact:
    """Create a backup artifact, optionally offloading it to private remote storage."""
    resolved_policy = policy or load_policy_snapshot()
    issues = validate_policy_snapshot(resolved_policy)
    if issues:
        raise BackupConfigurationError("; ".join(issues))

    backup_started_at = now or datetime.now(timezone.utc)
    local_directory = get_local_backup_directory(resolved_policy)
    local_directory.mkdir(parents=True, exist_ok=True)

    with _backup_creation_lock(local_directory, now=backup_started_at):
        connection_settings = django.db.connections["default"].settings_dict
        engine = str(connection_settings.get("ENGINE", ""))
        database_name = str(connection_settings.get("NAME", ""))

        if "postgresql" in engine:
            backup_format = "pg_dump_custom"
            filename = build_backup_filename(
                resolved_policy,
                now=backup_started_at,
                suffix="dump",
            )
            local_path = local_directory / filename
        else:
            backup_format = "json"
            filename = build_backup_filename(
                resolved_policy,
                now=backup_started_at,
                suffix="json",
            )
            local_path = local_directory / filename
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
            if cleanup_error is not None:
                exc.add_note(
                    f"Failed to clean up partial backup file '{local_path}': {cleanup_error}"
                )
            raise

        metadata = _build_backup_metadata(
            created_at=backup_started_at,
            backup_format=backup_format,
            database_engine=engine,
            database_name=database_name,
            target_mode=resolved_policy.target_mode,
        )

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
            metadata_json=metadata,
            initiated_by=initiated_by,
            trigger=trigger,
        )

        if resolved_policy.target_mode == BackupPolicy.TARGET_MODE_PRIVATE_REMOTE:
            uploader = remote_uploader or _upload_to_private_remote
            try:
                remote_key = uploader(local_path, resolved_policy)
            except BackupError as exc:
                _mark_remote_upload_failure(artifact, local_path=local_path, error=exc)
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
                    "Private remote metadata persistence failed for "
                    f"{artifact.filename} after uploading remote key "
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
                raise BackupError(message) from exc

        try:
            prune_expired_backups(policy=resolved_policy, now=backup_started_at)
        except Exception as exc:
            _record_prune_failure_without_masking_success(artifact, error=exc)
        return artifact


def validate_backup_artifact(artifact: BackupArtifact) -> list[str]:
    """Validate artifact integrity and update its validation status."""
    issues: list[str] = []
    local_path = Path(artifact.local_path) if artifact.local_path else None

    if local_path is None or not local_path.exists():
        issues.append("local backup artifact is missing")
    else:
        calculated_checksum = _compute_sha256(local_path)
        if calculated_checksum != artifact.checksum_sha256:
            issues.append("checksum mismatch detected")
        actual_size = local_path.stat().st_size
        if actual_size != artifact.size_bytes:
            issues.append("size mismatch detected")
        if artifact.backup_format == "json":
            try:
                json.loads(local_path.read_text(encoding="utf-8"))
            except UnicodeDecodeError, json.JSONDecodeError:
                issues.append("json backup payload is not valid JSON")

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
    local_path = Path(artifact.local_path) if artifact.local_path else None
    if local_path and local_path.exists():
        local_path.unlink()

    resolved_policy = policy or load_policy_snapshot()
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
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(
        days=resolved_policy.retention_days
    )

    expired = BackupArtifact.objects.filter(
        deleted_at__isnull=True,
        created_at__lt=cutoff,
    )

    deleted_count = 0
    deleted_at = django_timezone.now()
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
    shell_runner: ShellCommandRunner | None = None,
) -> RestoreResult:
    """Run guarded restore validation or execution for a backup artifact."""
    if confirmation.strip() != artifact.filename:
        raise BackupRestoreBlocked(
            "Confirmation must exactly match the backup filename."
        )

    issues = validate_backup_artifact(artifact)
    if issues:
        raise BackupRestoreBlocked(
            "Restore blocked because backup validation failed: " + "; ".join(issues)
        )

    compatibility_issues = _get_restore_compatibility_issues(artifact)
    if compatibility_issues:
        raise BackupRestoreBlocked(
            "Restore blocked because artifact compatibility validation failed: "
            + "; ".join(compatibility_issues)
        )

    if dry_run:
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

    if artifact.backup_format != "pg_dump_custom":
        raise BackupRestoreBlocked(
            "Executable restore is only supported for PostgreSQL custom-format "
            "artifacts. Use --dry-run for JSON fallback backups."
        )

    local_path = download_backup_path(artifact)
    connection_settings = django.db.connections["default"].settings_dict
    command, env = _build_pg_restore_command(
        local_path,
        connection_settings,
    )
    runner = shell_runner or _run_shell_command
    runner(command, env=env)

    artifact.status = BackupArtifact.STATUS_RESTORED
    artifact.restored_at = django_timezone.now()
    artifact.save(update_fields=["status", "restored_at", "updated_at"])

    return RestoreResult(
        executed=True,
        dry_run=False,
        message=f"Restore executed for {artifact.filename}.",
    )


def _build_backup_metadata(
    *,
    created_at: datetime,
    backup_format: str,
    database_engine: str,
    database_name: str,
    target_mode: str,
) -> dict[str, Any]:
    metadata = {
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
    database_server_version = _get_database_server_version(database_engine)
    if database_server_version is not None:
        metadata["database_server_version"] = database_server_version
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

    return issues


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

    result = subprocess.run(
        list(command),
        capture_output=True,
        check=False,
        text=True,
        env=command_env,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise BackupError(f"Command failed: {' '.join(command)} :: {stderr}")


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
