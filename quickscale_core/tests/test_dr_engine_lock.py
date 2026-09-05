"""Tests for quickscale_core.dr_engine._lock — backup lock lifecycle."""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from quickscale_core.dr_engine import _lock as lock_module
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
        assert len(data["owner_token"]) == 32

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

    def test_oserror_on_write(self, tmp_path: Path) -> None:
        """An OSError from os.write raises BackupError and cleans up."""
        with patch.object(lock_module.os, "write", side_effect=OSError("write failed")):
            with pytest.raises(BackupError, match="Unable to write backup lock") as exc:
                _acquire_backup_lock(tmp_path)
            error_text = str(exc.value)
            assert "write failed" in error_text

    def test_partial_write_completes_lock_metadata(self, tmp_path: Path) -> None:
        """A short regular-file write is completed before acquisition returns."""
        real_write = lock_module.os.write
        write_calls = 0

        def short_first_write(descriptor: int, payload: bytes) -> int:
            nonlocal write_calls
            write_calls += 1
            chunk = payload[:1] if write_calls == 1 else payload
            return real_write(descriptor, chunk)

        with patch.object(lock_module.os, "write", side_effect=short_first_write):
            lock_path = _acquire_backup_lock(tmp_path)

        assert write_calls >= 2
        assert json.loads(lock_path.read_text())["pid"] == os.getpid()
        _release_backup_lock(lock_path)

    def test_failed_write_preserves_replacement_inode(self, tmp_path: Path) -> None:
        """Failed acquisition cleanup cannot remove a replacement pathname."""
        lock_path = tmp_path / ".quickscale-backup-create.lock"
        replacement_source = tmp_path / "replacement-source"
        replacement_source.write_text("replacement")

        def replace_then_fail(*_args, **_kwargs) -> None:
            lock_path.unlink()
            replacement_source.rename(lock_path)
            raise OSError("write failed")

        with patch.object(lock_module.os, "write", side_effect=replace_then_fail):
            with pytest.raises(BackupError, match="Unable to write backup lock"):
                _acquire_backup_lock(tmp_path)

        assert lock_path.read_text() == "replacement"


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
    def test_release_without_acquisition_preserves_lock_file(
        self, tmp_path: Path
    ) -> None:
        """An unowned release cannot remove another execution's lock."""
        lock_path = tmp_path / ".lock"
        lock_path.write_text("data")
        _release_backup_lock(lock_path)
        assert lock_path.read_text() == "data"

    def test_release_file_not_found_is_silent(self, tmp_path: Path) -> None:
        """Releasing a lock that does not exist is a no-op."""
        lock_path = tmp_path / ".nonexistent.lock"
        _release_backup_lock(lock_path)  # should not raise

    def test_release_oserror_raises_backup_error(self, tmp_path: Path) -> None:
        """OSError during release raises BackupError."""
        lock_path = _acquire_backup_lock(tmp_path)
        with patch.object(Path, "unlink", side_effect=OSError("unlink failed")):
            with pytest.raises(BackupError, match="Unable to remove backup lock"):
                _release_backup_lock(lock_path)
        lock_path.unlink()

    def test_release_preserves_replacement_inode(self, tmp_path: Path) -> None:
        """A replacement created after acquire is not removed by release."""
        lock_path = _acquire_backup_lock(tmp_path)
        acquired_identity = (lock_path.stat().st_dev, lock_path.stat().st_ino)
        replacement_source = tmp_path / "replacement-source"
        replacement_source.write_text("replacement")
        lock_path.unlink()
        replacement_source.rename(lock_path)
        replacement_identity = (lock_path.stat().st_dev, lock_path.stat().st_ino)

        _release_backup_lock(lock_path)

        assert replacement_identity != acquired_identity
        assert lock_path.read_text() == "replacement"
        assert all(
            identity != acquired_identity
            for identity, _token in lock_module._backup_lock_ownership.values()
        )
        lock_path.unlink()

    def test_release_preserves_same_inode_with_changed_owner_token(
        self, tmp_path: Path
    ) -> None:
        """An inode match alone cannot authorize release of a later owner."""
        lock_path = _acquire_backup_lock(tmp_path)
        replacement = json.loads(lock_path.read_text())
        replacement["owner_token"] = "later-owner"
        lock_path.write_text(json.dumps(replacement))

        _release_backup_lock(lock_path)

        assert json.loads(lock_path.read_text())["owner_token"] == "later-owner"

    def test_release_keeps_later_thread_acquisition(self, tmp_path: Path) -> None:
        """An earlier holder cannot release a later holder's replacement."""
        first_acquired = threading.Event()
        second_acquired = threading.Event()
        release_first = threading.Event()
        first_released = threading.Event()
        release_second = threading.Event()
        second_identity: list[tuple[int, int]] = []
        errors: list[Exception] = []

        def first_holder() -> None:
            try:
                lock_path = _acquire_backup_lock(tmp_path)
                first_acquired.set()
                if not release_first.wait(timeout=5):
                    raise AssertionError("first release was not signaled")
                _release_backup_lock(lock_path)
                first_released.set()
            except (AssertionError, BackupError, OSError) as exc:
                errors.append(exc)

        def second_holder() -> None:
            try:
                if not first_acquired.wait(timeout=5):
                    raise AssertionError("first acquisition did not complete")
                lock_path = tmp_path / ".quickscale-backup-create.lock"
                lock_path.unlink()
                lock_path = _acquire_backup_lock(tmp_path)
                second_identity.append(
                    (lock_path.stat().st_dev, lock_path.stat().st_ino)
                )
                second_acquired.set()
                if not release_second.wait(timeout=5):
                    raise AssertionError("second release was not signaled")
                _release_backup_lock(lock_path)
            except (AssertionError, BackupError, OSError) as exc:
                errors.append(exc)

        first_thread = threading.Thread(target=first_holder)
        second_thread = threading.Thread(target=second_holder)
        first_thread.start()
        second_thread.start()
        assert second_acquired.wait(timeout=5)
        release_first.set()
        assert first_released.wait(timeout=5)

        lock_path = tmp_path / ".quickscale-backup-create.lock"
        assert (lock_path.stat().st_dev, lock_path.stat().st_ino) == second_identity[0]

        release_second.set()
        first_thread.join(timeout=5)
        second_thread.join(timeout=5)
        assert not first_thread.is_alive()
        assert not second_thread.is_alive()
        assert errors == []
        assert not lock_path.exists()


class TestBackupLockReplacementRace:
    def test_stale_clear_race_has_one_holder_and_one_contention(
        self, tmp_path: Path
    ) -> None:
        """A stale candidate is serialized before its replacement is created."""
        lock_path = tmp_path / ".quickscale-backup-create.lock"
        lock_path.write_text("seeded stale")
        old_stamp = time.time() - 600
        os.utime(lock_path, (old_stamp, old_stamp))
        seeded_identity = (lock_path.stat().st_dev, lock_path.stat().st_ino)
        seeded_descriptor = os.open(lock_path, os.O_RDONLY)
        flock_barrier = threading.Barrier(2)
        acquired = threading.Event()
        contended = threading.Event()
        release_holder = threading.Event()
        real_flock = lock_module.fcntl.flock
        flock_calls = 0
        flock_calls_guard = threading.Lock()
        replacement_guard = tmp_path / "replacement-inode-guard"
        original_open = lock_module.os.open

        def create_without_inode_reuse(file, flags, mode=0o777, *, dir_fd=None):
            if Path(file) == lock_path and flags & os.O_EXCL and not lock_path.exists():
                replacement_guard.write_text("inode guard")
            if dir_fd is None:
                return original_open(file, flags, mode)
            return original_open(file, flags, mode, dir_fd=dir_fd)

        def coordinated_flock(descriptor: int, operation: int) -> None:
            nonlocal flock_calls
            with flock_calls_guard:
                should_rendezvous = flock_calls < 2
                flock_calls += 1
            if should_rendezvous:
                flock_barrier.wait(timeout=5)
            real_flock(descriptor, operation)

        results: list[str] = []

        def worker(label: str) -> None:
            try:
                result = _acquire_backup_lock(tmp_path)
                results.append(f"{label}: holder")
                acquired.set()
                if not release_holder.wait(timeout=5):
                    raise AssertionError("holder release was not signaled")
                _release_backup_lock(result)
            except BackupLockError:
                results.append(f"{label}: contention")
                contended.set()

        try:
            with (
                patch.object(lock_module.fcntl, "flock", coordinated_flock),
                patch.object(lock_module.os, "open", create_without_inode_reuse),
            ):
                threads = [
                    threading.Thread(target=worker, args=(f"worker-{number}",))
                    for number in (1, 2)
                ]
                for thread in threads:
                    thread.start()
                assert acquired.wait(timeout=5)
                assert contended.wait(timeout=5)
                assert lock_path.exists()
                current_identity = (lock_path.stat().st_dev, lock_path.stat().st_ino)
                assert current_identity != seeded_identity
                release_holder.set()
                for thread in threads:
                    thread.join(timeout=5)
        finally:
            release_holder.set()
            os.close(seeded_descriptor)
            replacement_guard.unlink(missing_ok=True)
        assert (
            sorted(results).count("worker-1: holder")
            + sorted(results).count("worker-2: holder")
            == 1
        )
        assert len([result for result in results if result.endswith("contention")]) == 1


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
