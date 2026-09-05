"""Tests for the advisory lock helper.

Covers ``quickscale_core.advisory_lock`` — the file-based advisory lock
with metadata, fail-fast contention, and manual-clear stale guidance
introduced in Phase 2 (M2).
"""

from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from quickscale_core import advisory_lock as lock_module
from quickscale_core.advisory_lock import (
    AdvisoryLock,
    AdvisoryLockContentionError,
    AdvisoryLockError,
    AdvisoryLockMetadata,
    _pid_is_alive,
)


# ---------------------------------------------------------------------------
# AdvisoryLockMetadata
# ---------------------------------------------------------------------------


class TestAdvisoryLockMetadata:
    """Tests for AdvisoryLockMetadata dataclass."""

    def test_to_dict_round_trip(self) -> None:
        metadata = AdvisoryLockMetadata(
            pid=12345,
            hostname="test-host",
            operation="apply",
            acquired_at="2025-01-01T10:00:00+00:00",
        )
        data = metadata.to_dict()
        assert data == {
            "pid": 12345,
            "hostname": "test-host",
            "operation": "apply",
            "acquired_at": "2025-01-01T10:00:00+00:00",
        }

        rebuilt = AdvisoryLockMetadata.from_dict(data)
        assert rebuilt.pid == metadata.pid
        assert rebuilt.hostname == metadata.hostname
        assert rebuilt.operation == metadata.operation
        assert rebuilt.acquired_at == metadata.acquired_at

    def test_default_acquired_at_is_iso(self) -> None:
        metadata = AdvisoryLockMetadata(pid=1, hostname="h", operation="op")
        datetime.fromisoformat(metadata.acquired_at)


# ---------------------------------------------------------------------------
# AdvisoryLock acquire / release
# ---------------------------------------------------------------------------


class TestAdvisoryLockAcquireRelease:
    """Tests for AdvisoryLock.acquire() and release()."""

    def test_acquire_creates_lock_file(self, tmp_path: Path) -> None:
        lock = AdvisoryLock(tmp_path, operation="test-op")
        try:
            lock.acquire()
            assert lock.lock_path.exists()
            assert lock.is_held_locally is True
        finally:
            lock.release()

    def test_acquire_writes_metadata(self, tmp_path: Path) -> None:
        lock = AdvisoryLock(tmp_path, operation="apply")
        try:
            metadata = lock.acquire()
            assert metadata.operation == "apply"
            assert metadata.pid == os.getpid()

            # Verify the file contents.
            with open(lock.lock_path) as f:
                data = yaml.safe_load(f)
            assert data["pid"] == os.getpid()
            assert data["operation"] == "apply"
        finally:
            lock.release()

    def test_acquire_fail_fast_on_contention(self, tmp_path: Path) -> None:
        lock1 = AdvisoryLock(tmp_path, operation="op1")
        lock2 = AdvisoryLock(tmp_path, operation="op2")

        try:
            lock1.acquire()
            with pytest.raises(AdvisoryLockContentionError) as excinfo:
                lock2.acquire()
            # Error message should mention the lock path and manual clear.
            assert str(lock1.lock_path) in str(excinfo.value)
            assert "rm" in str(excinfo.value)
        finally:
            lock1.release()

    def test_release_removes_lock_file(self, tmp_path: Path) -> None:
        lock = AdvisoryLock(tmp_path, operation="test")
        lock.acquire()
        assert lock.lock_path.exists()

        lock.release()
        assert not lock.lock_path.exists()
        assert lock.is_held_locally is False

    def test_release_without_acquire_is_noop(self, tmp_path: Path) -> None:
        lock = AdvisoryLock(tmp_path, operation="test")
        lock.release()  # Should not raise.
        assert lock.is_held_locally is False

    def test_release_preserves_replacement_inode(self, tmp_path: Path) -> None:
        """A replacement created after acquire is not removed by release."""
        lock = AdvisoryLock(tmp_path, operation="original")
        lock.acquire()
        acquired_identity = (lock.lock_path.stat().st_dev, lock.lock_path.stat().st_ino)
        replacement_source = tmp_path / "replacement-source"
        replacement_source.write_text("replacement")
        lock.lock_path.unlink()
        replacement_source.rename(lock.lock_path)
        replacement_identity = (
            lock.lock_path.stat().st_dev,
            lock.lock_path.stat().st_ino,
        )

        lock.release()

        assert replacement_identity != acquired_identity
        assert lock.lock_path.read_text() == "replacement"
        assert lock.is_held_locally is False
        assert lock._acquired_identity is None
        lock.lock_path.unlink()

    def test_inherited_pid_cannot_release_acquiring_process_lock(
        self, tmp_path: Path
    ) -> None:
        """A fork-inherited instance fails closed outside its acquiring PID."""
        lock = AdvisoryLock(tmp_path, operation="parent")
        lock.acquire()
        acquiring_pid = lock._acquired_pid
        assert acquiring_pid is not None

        with patch.object(lock_module.os, "getpid", return_value=acquiring_pid + 1):
            lock.release()

        assert lock.lock_path.exists()
        assert lock.is_held_locally is False
        assert lock._acquired_pid is None
        assert lock._acquisition_token is None
        lock.lock_path.unlink()

    def test_release_preserves_same_inode_with_different_token(
        self, tmp_path: Path
    ) -> None:
        """Identity reuse cannot bypass private acquisition-token parity."""
        lock = AdvisoryLock(tmp_path, operation="original")
        lock.acquire()
        acquired_identity = (lock.lock_path.stat().st_dev, lock.lock_path.stat().st_ino)
        replacement_data = yaml.safe_load(lock.lock_path.read_text())
        replacement_data[lock_module._ACQUISITION_TOKEN_KEY] = "replacement-token"
        lock.lock_path.write_text(yaml.dump(replacement_data, sort_keys=False))

        assert (lock.lock_path.stat().st_dev, lock.lock_path.stat().st_ino) == (
            acquired_identity
        )
        lock.release()

        assert lock.lock_path.exists()
        assert (
            yaml.safe_load(lock.lock_path.read_text())[
                lock_module._ACQUISITION_TOKEN_KEY
            ]
            == "replacement-token"
        )
        assert lock.is_held_locally is False
        lock.lock_path.unlink()

    def test_partial_writes_complete_parseable_metadata_and_release(
        self, tmp_path: Path
    ) -> None:
        """Short writes are retried until metadata is complete and releasable."""
        lock = AdvisoryLock(tmp_path, operation="short-write")
        real_write = lock_module.os.write
        write_sizes: list[int] = []

        def short_write(descriptor: int, payload: bytes) -> int:
            chunk = payload[: max(1, len(payload) // 2)]
            written = real_write(descriptor, chunk)
            write_sizes.append(written)
            return written

        with patch.object(lock_module.os, "write", side_effect=short_write):
            lock.acquire()

        metadata = lock.read_metadata()
        assert len(write_sizes) > 1
        assert metadata is not None
        assert metadata.pid == os.getpid()
        assert metadata.operation == "short-write"

        lock.release()
        assert not lock.lock_path.exists()
        assert lock.is_held_locally is False

    def test_zero_progress_write_fails_and_cleans_up(self, tmp_path: Path) -> None:
        """A zero-progress metadata write cannot report acquisition success."""
        lock = AdvisoryLock(tmp_path, operation="zero-progress")

        with patch.object(lock_module.os, "write", return_value=0):
            with pytest.raises(
                AdvisoryLockError, match="Failed to acquire advisory lock"
            ):
                lock.acquire()

        lock.release()
        assert not lock.lock_path.exists()
        assert lock.is_held_locally is False
        assert lock._acquired_identity is None
        assert lock._acquired_pid is None
        assert lock._acquisition_token is None

    def test_failed_write_cleans_up_created_lock(self, tmp_path: Path) -> None:
        """A failed metadata write does not leave a lock or local ownership."""
        lock = AdvisoryLock(tmp_path, operation="write-failure")
        with patch.object(lock_module.os, "write", side_effect=OSError("write failed")):
            with pytest.raises(
                AdvisoryLockError, match="Failed to acquire advisory lock"
            ):
                lock.acquire()

        assert not lock.lock_path.exists()
        assert lock.is_held_locally is False
        assert lock._acquired_identity is None

    def test_context_manager(self, tmp_path: Path) -> None:
        lock = AdvisoryLock(tmp_path, operation="test")
        with lock:
            assert lock.is_held_locally is True
            assert lock.lock_path.exists()
        assert lock.is_held_locally is False
        assert not lock.lock_path.exists()


# ---------------------------------------------------------------------------
# AdvisoryLock read_metadata / is_stale / clear_stale
# ---------------------------------------------------------------------------


class TestAdvisoryLockStaleDetection:
    """Tests for stale lock detection and manual clear."""

    def test_read_metadata_returns_none_when_no_lock(self, tmp_path: Path) -> None:
        lock = AdvisoryLock(tmp_path)
        assert lock.read_metadata() is None

    def test_read_metadata_returns_metadata_when_lock_exists(
        self, tmp_path: Path
    ) -> None:
        lock = AdvisoryLock(tmp_path, operation="apply")
        try:
            lock.acquire()
            metadata = lock.read_metadata()
            assert metadata is not None
            assert metadata.pid == os.getpid()
            assert metadata.operation == "apply"
        finally:
            lock.release()

    def test_is_stale_returns_true_when_no_lock(self, tmp_path: Path) -> None:
        lock = AdvisoryLock(tmp_path)
        assert lock.is_stale() is True

    def test_is_stale_returns_false_for_live_lock(self, tmp_path: Path) -> None:
        lock = AdvisoryLock(tmp_path, operation="test")
        try:
            lock.acquire()
            # Our own PID is alive, and the lock is fresh.
            assert lock.is_stale() is False
        finally:
            lock.release()

    def test_is_stale_returns_true_for_dead_pid(self, tmp_path: Path) -> None:
        lock = AdvisoryLock(tmp_path, operation="test")
        lock.state_dir.mkdir(parents=True, exist_ok=True)
        # Write a lock file with a non-existent PID.
        metadata = AdvisoryLockMetadata(
            pid=999999999,  # Almost certainly not running.
            hostname="test",
            operation="test",
        )
        with open(lock.lock_path, "w") as f:
            yaml.dump(metadata.to_dict(), f)

        assert lock.is_stale() is True

    def test_is_stale_returns_true_for_old_lock(self, tmp_path: Path) -> None:
        lock = AdvisoryLock(tmp_path, operation="test")
        lock.state_dir.mkdir(parents=True, exist_ok=True)
        # Write a lock file with an old timestamp.
        old_time = datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat()
        metadata = AdvisoryLockMetadata(
            pid=os.getpid(),
            hostname="test",
            operation="test",
            acquired_at=old_time,
        )
        with open(lock.lock_path, "w") as f:
            yaml.dump(metadata.to_dict(), f)

        assert lock.is_stale(max_age_seconds=1.0) is True

    def test_clear_stale_removes_dead_pid_lock(self, tmp_path: Path) -> None:
        lock = AdvisoryLock(tmp_path, operation="test")
        lock.state_dir.mkdir(parents=True, exist_ok=True)
        metadata = AdvisoryLockMetadata(
            pid=999999999,
            hostname="test",
            operation="test",
        )
        with open(lock.lock_path, "w") as f:
            yaml.dump(metadata.to_dict(), f)

        assert lock.clear_stale() is True
        assert not lock.lock_path.exists()

    def test_clear_stale_does_not_remove_live_lock(self, tmp_path: Path) -> None:
        lock = AdvisoryLock(tmp_path, operation="test")
        try:
            lock.acquire()
            # Our own PID is alive and the lock is fresh.
            assert lock.clear_stale() is False
            assert lock.lock_path.exists()
        finally:
            lock.release()

    def test_clear_stale_race_preserves_replacement_and_contention(
        self, tmp_path: Path
    ) -> None:
        """A locked stale inode cannot clear a replacement pathname."""
        stale = AdvisoryLock(tmp_path, operation="stale-clear")
        replacement = AdvisoryLock(tmp_path, operation="replacement")
        contender = AdvisoryLock(tmp_path, operation="contender")
        stale.state_dir.mkdir(parents=True, exist_ok=True)
        stale_metadata = AdvisoryLockMetadata(
            pid=999999999,
            hostname="test",
            operation="stale",
        )
        with open(stale.lock_path, "w") as handle:
            yaml.dump(stale_metadata.to_dict(), handle)
        seeded_identity = (stale.lock_path.stat().st_dev, stale.lock_path.stat().st_ino)
        replacement_source = tmp_path / "replacement-source"
        replacement_source.write_text("replacement")
        candidate_locked = threading.Event()
        contended = threading.Event()
        replacement_ready = threading.Event()
        real_flock = lock_module.fcntl.flock
        hook_armed = True
        hook_guard = threading.Lock()

        def coordinated_flock(descriptor: int, operation: int) -> None:
            nonlocal hook_armed
            real_flock(descriptor, operation)
            with hook_guard:
                should_coordinate = hook_armed
                hook_armed = False
            if should_coordinate:
                candidate_locked.set()
                assert contended.wait(timeout=5)
                stale.lock_path.unlink()
                replacement_source.rename(stale.lock_path)
                replacement._acquired = True
                replacement._acquired_identity = (
                    stale.lock_path.stat().st_dev,
                    stale.lock_path.stat().st_ino,
                )
                replacement_ready.set()

        clear_result: list[bool] = []
        contention_result: list[str] = []

        def clear_worker() -> None:
            clear_result.append(stale.clear_stale())

        def contender_worker() -> None:
            assert candidate_locked.wait(timeout=5)
            try:
                contender.acquire()
            except AdvisoryLockContentionError:
                contention_result.append("contention")
                contended.set()

        try:
            with patch.object(lock_module.fcntl, "flock", coordinated_flock):
                clear_thread = threading.Thread(target=clear_worker)
                contender_thread = threading.Thread(target=contender_worker)
                clear_thread.start()
                contender_thread.start()
                clear_thread.join(timeout=5)
                contender_thread.join(timeout=5)
                assert not clear_thread.is_alive()
                assert not contender_thread.is_alive()
            assert clear_result == [True]
            assert contention_result == ["contention"]
            assert replacement_ready.is_set()
            assert stale.lock_path.exists()
            current_identity = (
                stale.lock_path.stat().st_dev,
                stale.lock_path.stat().st_ino,
            )
            assert current_identity != seeded_identity
        finally:
            replacement.release()


# ---------------------------------------------------------------------------
# _pid_is_alive helper
# ---------------------------------------------------------------------------


class TestPidIsAlive:
    """Tests for the _pid_is_alive helper."""

    def test_current_pid_is_alive(self) -> None:
        assert _pid_is_alive(os.getpid()) is True

    def test_zero_pid_is_not_alive(self) -> None:
        assert _pid_is_alive(0) is False

    def test_negative_pid_is_not_alive(self) -> None:
        assert _pid_is_alive(-1) is False

    def test_nonexistent_pid_is_not_alive(self) -> None:
        assert _pid_is_alive(999999999) is False
