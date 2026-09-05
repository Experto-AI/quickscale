"""Lock management for DR backup operations.

Cross-process filesystem locking to prevent overlapping backup runs.  Also
carries the :class:`StagedAdminRestoreUpload` dataclass used by the admin
restore flow.
"""

from __future__ import annotations

import fcntl
import json
import os
import secrets
import threading
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
_BackupLockOwnerKey = tuple[int, int, Path]
_BackupLockOwnership = tuple[tuple[int, int], str]
_backup_lock_ownership: dict[_BackupLockOwnerKey, _BackupLockOwnership] = {}
_backup_lock_ownership_guard = threading.Lock()

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

        acquired_identity: tuple[int, int] | None = None
        owner_token = secrets.token_hex(16)
        try:
            acquired_identity = _file_identity_from_descriptor(descriptor)
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            payload = json.dumps(
                {
                    "pid": os.getpid(),
                    "created_at": lock_time.astimezone(timezone.utc).isoformat(),
                    "owner_token": owner_token,
                }
            )
            _write_descriptor(descriptor, payload.encode("utf-8"))
            os.fsync(descriptor)
        except OSError as exc:
            cleanup_error = (
                "ownership identity unavailable; lock retained"
                if acquired_identity is None
                else _cleanup_owned_backup_lock(lock_path, acquired_identity)
            )
            details = f"Unable to write backup lock file at {lock_path}: {exc}"
            if cleanup_error is not None:
                details += f"; cleanup failed: {cleanup_error}"
            raise BackupError(details) from exc
        finally:
            os.close(descriptor)

        owner_key = _backup_lock_owner_key(lock_path)
        if acquired_identity is None:  # pragma: no cover - successful fstat assigns it
            raise BackupError(f"Unable to identify backup lock file at {lock_path}")
        with _backup_lock_ownership_guard:
            _backup_lock_ownership[owner_key] = (acquired_identity, owner_token)
        return lock_path

    raise BackupLockError(
        "A backup operation is already in progress. Wait for it to finish first."
    )


def _clear_stale_backup_lock(lock_path: Path, *, now: datetime) -> bool:
    """Remove an expired lock file so a new backup run can proceed."""
    try:
        descriptor = os.open(lock_path, os.O_RDONLY)
    except FileNotFoundError:
        return True
    except OSError as exc:
        raise BackupError(
            f"Unable to inspect stale backup lock file at {lock_path}: {exc}"
        ) from exc

    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        candidate_identity = _file_identity_from_descriptor(descriptor)
        lock_mtime = os.fstat(descriptor).st_mtime
        if (now.timestamp() - lock_mtime) <= _LOCK_TIMEOUT_SECONDS:
            return False

        try:
            current_identity = _file_identity_from_path(lock_path)
        except FileNotFoundError:
            return True
        if current_identity != candidate_identity:
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
    except OSError as exc:
        raise BackupError(
            f"Unable to inspect stale backup lock file at {lock_path}: {exc}"
        ) from exc
    finally:
        os.close(descriptor)


def _release_backup_lock(lock_path: Path) -> None:
    """Remove the backup lock file after the operation finishes."""
    owner_key = _backup_lock_owner_key(lock_path)
    with _backup_lock_ownership_guard:
        ownership = _backup_lock_ownership.pop(owner_key, None)

    if ownership is None:
        return
    acquired_identity, owner_token = ownership

    try:
        descriptor = os.open(lock_path, os.O_RDONLY)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise BackupError(
            f"Unable to remove backup lock file at {lock_path}: {exc}"
        ) from exc

    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        opened_identity = _file_identity_from_descriptor(descriptor)
        if opened_identity != acquired_identity:
            return
        if _backup_lock_token_from_descriptor(descriptor) != owner_token:
            return
        try:
            current_identity = _file_identity_from_path(lock_path)
        except FileNotFoundError:
            return
        if current_identity == acquired_identity:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                return
    except OSError as exc:
        raise BackupError(
            f"Unable to remove backup lock file at {lock_path}: {exc}"
        ) from exc
    finally:
        os.close(descriptor)


def _backup_lock_owner_key(lock_path: Path) -> _BackupLockOwnerKey:
    """Bind process-local ownership to the acquiring execution thread."""
    return os.getpid(), threading.get_ident(), lock_path


def _file_identity_from_descriptor(descriptor: int) -> tuple[int, int]:
    """Return the device and inode identity held by an open descriptor."""
    stat_result = os.fstat(descriptor)
    return stat_result.st_dev, stat_result.st_ino


def _file_identity_from_path(lock_path: Path) -> tuple[int, int]:
    """Return the current device and inode identity at a lock pathname."""
    stat_result = lock_path.stat()
    return stat_result.st_dev, stat_result.st_ino


def _backup_lock_token_from_descriptor(descriptor: int) -> str | None:
    """Read a private acquisition token from one locked descriptor."""
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while chunk := os.read(descriptor, 8192):
        chunks.append(chunk)
    try:
        data = json.loads(b"".join(chunks).decode("utf-8"))
    except UnicodeDecodeError, json.JSONDecodeError:
        return None
    token = data.get("owner_token") if isinstance(data, dict) else None
    return token if isinstance(token, str) else None


def _write_descriptor(descriptor: int, payload: bytes) -> None:
    """Write a complete payload even when the OS accepts only a prefix."""
    remaining = memoryview(payload)
    while remaining:
        written = os.write(descriptor, remaining)
        if written <= 0:
            raise OSError("backup lock write made no progress")
        remaining = remaining[written:]


def _cleanup_owned_backup_lock(
    lock_path: Path, acquired_identity: tuple[int, int]
) -> str | None:
    """Remove a failed acquisition only while its inode remains at the path."""
    try:
        current_identity = _file_identity_from_path(lock_path)
    except FileNotFoundError:
        return None
    except OSError as exc:
        return str(exc)
    if current_identity != acquired_identity:
        return None
    return _cleanup_local_backup_file(lock_path)


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
