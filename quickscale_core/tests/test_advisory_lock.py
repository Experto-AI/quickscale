"""Tests for the advisory lock helper.

Covers ``quickscale_core.advisory_lock`` — the file-based advisory lock
with metadata, fail-fast contention, and manual-clear stale guidance
introduced in Phase 2 (M2).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from quickscale_core.advisory_lock import (
    AdvisoryLock,
    AdvisoryLockContentionError,
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
