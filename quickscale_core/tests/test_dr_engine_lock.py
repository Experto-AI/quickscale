"""Tests for quickscale_core.dr_engine._lock — backup lock lifecycle."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from quickscale_core.dr_engine._lock import (
    BackupLockError,
    StagedAdminRestoreUpload,
    _acquire_backup_lock,
    _backup_creation_lock,
    _cleanup_local_backup_file,
    _clear_stale_backup_lock,
    _release_backup_lock,
)
from quickscale_core.dr_engine.primitives import BackupError


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


class TestStagedAdminRestoreUpload:
    def test_fields(self) -> None:
        """Verify the frozen dataclass stores all expected fields."""
        entry = StagedAdminRestoreUpload(
            local_path=Path("/tmp/restore.dump"),
            checksum_sha256="abc123",
            size_bytes=4096,
        )
        assert entry.local_path == Path("/tmp/restore.dump")
        assert entry.checksum_sha256 == "abc123"
        assert entry.size_bytes == 4096

    def test_frozen(self) -> None:
        """Verify the dataclass is frozen (immutable)."""
        entry = StagedAdminRestoreUpload(
            local_path=Path("/tmp/x"), checksum_sha256="a", size_bytes=1
        )
        with pytest.raises(AttributeError):
            entry.size_bytes = 2  # type: ignore[misc]


# ---------------------------------------------------------------------------
# _backup_creation_lock (context manager)
# ---------------------------------------------------------------------------


class TestBackupCreationLock:
    def test_acquire_and_release(self, tmp_path: Path) -> None:
        """Context manager acquires lock, yields, then releases."""
        lock_filename = ".quickscale-backup-create.lock"
        lock_path = tmp_path / lock_filename

        assert not lock_path.exists()
        with _backup_creation_lock(tmp_path):
            assert lock_path.exists()
            data = json.loads(lock_path.read_text())
            assert "pid" in data
            assert "created_at" in data
        # Lock file should be removed after context exits
        assert not lock_path.exists()

    def test_raises_when_already_locked(self, tmp_path: Path) -> None:
        """Acquiring a second lock on the same directory raises BackupLockError."""
        lock_path = tmp_path / ".quickscale-backup-create.lock"
        lock_path.write_text("{}")

        old_mtime = time.time() - 1
        os.utime(lock_path, (old_mtime, old_mtime))
        # The lock file we just created is not stale (it's not old enough)
        # Actually with timestamp-based check, we risk flakiness.
        # Instead, use a known recent mtime that won't trigger stale logic.
        # We need the mtime to be MORE recent than _LOCK_TIMEOUT_SECONDS (300)
        # to NOT be stale. Creating it now means it's fresh, so _clear_stale
        # returns False and BackupLockError is raised.
        with pytest.raises(BackupLockError, match="already in progress"):
            with _backup_creation_lock(tmp_path):
                pass  # pragma: no cover


# ---------------------------------------------------------------------------
# _acquire_backup_lock
# ---------------------------------------------------------------------------


class TestAcquireBackupLock:
    def test_happy_path(self, tmp_path: Path) -> None:
        """Creates lock file, writes JSON PID metadata, returns lock path."""
        lock_path = _acquire_backup_lock(tmp_path)
        assert lock_path == tmp_path / ".quickscale-backup-create.lock"
        assert lock_path.exists()
        data = json.loads(lock_path.read_text())
        assert data["pid"] == os.getpid()
        assert "created_at" in data

    def test_with_explicit_now(self, tmp_path: Path) -> None:
        """Passing an explicit 'now' uses that timestamp in the payload."""
        fixed_now = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        lock_path = _acquire_backup_lock(tmp_path, now=fixed_now)
        data = json.loads(lock_path.read_text())
        assert data["created_at"] == "2026-06-15T12:00:00+00:00"

    def test_clears_stale_lock_and_retries(self, tmp_path: Path) -> None:
        """When a stale lock exists, it is cleared and a new one is created."""
        lock_path = tmp_path / ".quickscale-backup-create.lock"
        # Create a lock file that looks very old (well past 300s timeout)
        lock_path.write_text("stale data")
        old_stamp = time.time() - 600  # 10 minutes old
        os.utime(lock_path, (old_stamp, old_stamp))
        assert lock_path.exists()

        result = _acquire_backup_lock(tmp_path)
        assert result == lock_path
        # The stale lock should have been replaced with fresh JSON metadata
        data = json.loads(lock_path.read_text())
        assert data["pid"] == os.getpid()

    def test_raises_when_stale_lock_cannot_be_cleared(self, tmp_path: Path) -> None:
        """A non-stale lock raises BackupLockError."""
        lock_path = tmp_path / ".quickscale-backup-create.lock"
        lock_path.write_text("fresh lock")
        # Use a current mtime — lock is not stale
        with pytest.raises(BackupLockError, match="already in progress"):
            _acquire_backup_lock(tmp_path)

    def test_mkdir_creates_parents(self, tmp_path: Path) -> None:
        """mkdir parents=True creates the directory tree if missing."""
        nested = tmp_path / "a" / "b" / "c"
        _acquire_backup_lock(nested)
        assert nested.is_dir()
        assert (nested / ".quickscale-backup-create.lock").exists()

    def test_oserror_on_open_raises_backup_error(self, tmp_path: Path) -> None:
        """An unexpected OSError from os.open raises BackupError."""
        with patch("os.open", side_effect=OSError("open failed")):
            with pytest.raises(BackupError, match="Unable to create backup lock"):
                _acquire_backup_lock(tmp_path)

    def test_oserror_on_write_fdopen(self, tmp_path: Path) -> None:
        """An OSError from os.fdopen json-dump flushes to BackupError with cleanup."""
        with patch("os.fdopen") as mock_fdopen:
            mock_handle = mock_fdopen.return_value.__enter__.return_value
            mock_handle.flush.side_effect = OSError("write failed")
            with pytest.raises(BackupError, match="Unable to write backup lock") as exc:
                _acquire_backup_lock(tmp_path)
            error_text = str(exc.value)
            assert "write failed" in error_text


# ---------------------------------------------------------------------------
# _clear_stale_backup_lock
# ---------------------------------------------------------------------------


class TestClearStaleBackupLock:
    def test_no_lock_file_returns_true(self, tmp_path: Path) -> None:
        """When the lock file does not exist, return True (no contention)."""
        lock_path = tmp_path / ".nonexistent.lock"
        now = datetime.now(timezone.utc)
        assert _clear_stale_backup_lock(lock_path, now=now) is True

    def test_lock_not_stale_returns_false(self, tmp_path: Path) -> None:
        """When the lock is recent (within timeout), return False."""
        lock_path = tmp_path / ".fresh.lock"
        lock_path.write_text("fresh")
        now = datetime.now(timezone.utc)
        assert _clear_stale_backup_lock(lock_path, now=now) is False

    def test_lock_stale_removes_and_returns_true(self, tmp_path: Path) -> None:
        """A lock older than the timeout is removed and returns True."""
        lock_path = tmp_path / ".stale.lock"
        lock_path.write_text("stale")
        old_stamp = time.time() - 600  # 10 min > 300s timeout
        os.utime(lock_path, (old_stamp, old_stamp))
        now = datetime.now(timezone.utc)
        result = _clear_stale_backup_lock(lock_path, now=now)
        assert result is True
        assert not lock_path.exists()

    def test_oserror_on_unlink_raises_backup_error(self, tmp_path: Path) -> None:
        """OSError while unlinking a stale lock raises BackupError."""
        lock_path = tmp_path / ".stale_lock_unlink_error.lock"
        lock_path.write_text("stale")
        old_stamp = time.time() - 600
        os.utime(lock_path, (old_stamp, old_stamp))
        with patch.object(Path, "unlink", side_effect=OSError("unlink failed")):
            with pytest.raises(BackupError, match="Unable to clear stale backup lock"):
                _clear_stale_backup_lock(lock_path, now=datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# _release_backup_lock
# ---------------------------------------------------------------------------


class TestReleaseBackupLock:
    def test_releases_lock_file(self, tmp_path: Path) -> None:
        """Normal release removes the lock file."""
        lock_path = tmp_path / ".lock"
        lock_path.write_text("data")
        _release_backup_lock(lock_path)
        assert not lock_path.exists()

    def test_release_file_not_found_is_silent(self, tmp_path: Path) -> None:
        """Releasing a lock that does not exist is a no-op."""
        lock_path = tmp_path / ".nonexistent.lock"
        _release_backup_lock(lock_path)  # should not raise

    def test_release_oserror_raises_backup_error(self, tmp_path: Path) -> None:
        """OSError during release raises BackupError."""
        lock_path = tmp_path / ".lock"
        lock_path.write_text("data")
        with patch.object(Path, "unlink", side_effect=OSError("unlink failed")):
            with pytest.raises(BackupError, match="Unable to remove backup lock"):
                _release_backup_lock(lock_path)


# ---------------------------------------------------------------------------
# _cleanup_local_backup_file
# ---------------------------------------------------------------------------


class TestCleanupLocalBackupFile:
    def test_cleanup_success_returns_none(self, tmp_path: Path) -> None:
        """Successful deletion returns None."""
        target = tmp_path / "file.txt"
        target.write_text("data")
        result = _cleanup_local_backup_file(target)
        assert result is None
        assert not target.exists()

    def test_cleanup_missing_file_is_silent(self, tmp_path: Path) -> None:
        """Missing file (missing_ok=True) returns None without error."""
        target = tmp_path / "nonexistent.txt"
        result = _cleanup_local_backup_file(target)
        assert result is None

    def test_cleanup_oserror_returns_error_string(self, tmp_path: Path) -> None:
        """OSError during cleanup returns the error message as a string."""
        target = tmp_path / "protected.txt"
        target.write_text("data")
        with patch.object(Path, "unlink", side_effect=OSError("permission denied")):
            result = _cleanup_local_backup_file(target)
            assert result is not None
            assert "permission denied" in result


# ---------------------------------------------------------------------------
# _backup_creation_lock — three-turn retry exhausted
# ---------------------------------------------------------------------------


class TestBackupCreationLockExhausted:
    def test_two_stale_cycles_exhausted_raises(self, tmp_path: Path) -> None:
        """_acquire_backup_lock exhausts 2 retries when os.open always gets
        FileExistsError and clear_stale always returns True."""
        # Patch os.open to always raise FileExistsError, and make
        # _clear_stale_backup_lock always return True so we exhaust
        # the loop and hit the fallback raise on line 114.
        with (
            patch(
                "os.open",
                side_effect=FileExistsError(),
            ),
            patch(
                "quickscale_core.dr_engine._lock._clear_stale_backup_lock",
                return_value=True,
            ),
        ):
            with pytest.raises(BackupLockError, match="already in progress"):
                _acquire_backup_lock(tmp_path)
