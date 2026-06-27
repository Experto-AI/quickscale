"""Lock management for DR backup operations.

Cross-process filesystem locking to prevent overlapping backup runs.  Also
carries the :class:`StagedAdminRestoreUpload` dataclass used by the admin
restore flow.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from quickscale_core.dr_engine.primitives import BackupError


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LOCK_FILENAME = ".quickscale-backup-create.lock"
_LOCK_TIMEOUT_SECONDS = 300

# ---------------------------------------------------------------------------
# Error class
# ---------------------------------------------------------------------------


class BackupLockError(BackupError):
    """Raised when a backup operation is already running."""


@dataclass(frozen=True)
class StagedAdminRestoreUpload:
    """Quarantined admin-uploaded restore input plus trusted-match metadata."""

    local_path: Path
    checksum_sha256: str
    size_bytes: int


# ---------------------------------------------------------------------------
# Lock lifecycle
# ---------------------------------------------------------------------------


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


__all__ = [
    "BackupLockError",
    "StagedAdminRestoreUpload",
    "_acquire_backup_lock",
    "_backup_creation_lock",
    "_cleanup_local_backup_file",
    "_clear_stale_backup_lock",
    "_release_backup_lock",
]
