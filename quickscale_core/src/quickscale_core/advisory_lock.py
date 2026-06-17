"""Advisory lock helper for QuickScale state operations.

Provides an exclusive-create (``O_CREAT | O_EXCL``) file-based advisory
lock with metadata.  Used to serialize concurrent QuickScale operations
that mutate ``.quickscale/state.yml``.

Design constraints (Phase 2 / M2):

* **Standard library only** — no third-party lock-file dependencies.
* **Fail-fast contention** — if the lock file already exists, raise
  immediately.  No retry loops, no blocking waits.
* **No auto-eviction** — the helper never deletes a lock it did not
  create.  Stale locks must be cleared manually.
* **Metadata in lock file** — the lock file contains YAML with PID,
  hostname, timestamp, and the operation name so that operators can
  diagnose contention.
* **Manual-clear stale guidance** — :meth:`AdvisoryLock.is_stale`
  inspects the lock metadata and reports whether the owning process
  is still alive.  :meth:`AdvisoryLock.clear_stale` removes a stale
  lock after confirming the owning PID is gone.

The lock file lives at ``.quickscale/<name>.lock`` next to ``state.yml``.
"""

from __future__ import annotations

import errno
import os
import socket
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


class AdvisoryLockError(Exception):
    """Raised when an advisory lock operation fails."""


class AdvisoryLockContentionError(AdvisoryLockError):
    """Raised when the lock file already exists (fail-fast contention)."""


@dataclass
class AdvisoryLockMetadata:
    """Metadata stored inside the lock file.

    Attributes:
        pid: Process ID of the lock owner.
        hostname: Hostname of the machine that acquired the lock.
        operation: Name of the operation holding the lock.
        acquired_at: ISO-8601 UTC timestamp when the lock was acquired.

    """

    pid: int
    hostname: str
    operation: str
    acquired_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        """Return a YAML-friendly dictionary representation."""
        return {
            "pid": self.pid,
            "hostname": self.hostname,
            "operation": self.operation,
            "acquired_at": self.acquired_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AdvisoryLockMetadata":
        """Build metadata from a YAML mapping."""
        return cls(
            pid=int(data["pid"]),
            hostname=str(data.get("hostname", "unknown")),
            operation=str(data.get("operation", "unknown")),
            acquired_at=str(
                data.get(
                    "acquired_at",
                    datetime.now(timezone.utc).isoformat(),
                )
            ),
        )


class AdvisoryLock:
    """File-based advisory lock with metadata and fail-fast contention.

    Usage::

        lock = AdvisoryLock(project_path, operation="apply")
        try:
            lock.acquire()
            # ... critical section ...
        finally:
            lock.release()

    The lock is scoped to a project directory.  The lock file is created
    at ``.quickscale/<name>.lock`` where ``name`` defaults to ``state``
    (i.e. ``.quickscale/state.lock``).

    Args:
        project_path: Root of the generated project.
        operation: Human-readable name of the operation acquiring the lock.
        name: Base name for the lock file (without ``.lock`` suffix).

    """

    def __init__(
        self,
        project_path: Path,
        operation: str = "quickscale",
        name: str = "state",
    ) -> None:
        self.project_path = Path(project_path)
        self.state_dir = self.project_path / ".quickscale"
        self.lock_path = self.state_dir / f"{name}.lock"
        self.operation = operation
        self._acquired = False
        self._metadata: AdvisoryLockMetadata | None = None

    @property
    def is_held_locally(self) -> bool:
        """Return True if this instance currently holds the lock."""
        return self._acquired

    def acquire(self) -> AdvisoryLockMetadata:
        """Acquire the advisory lock.

        Returns:
            The :class:`AdvisoryLockMetadata` written to the lock file.

        Raises:
            AdvisoryLockContentionError: If the lock file already exists.
            AdvisoryLockError: For other I/O or serialization errors.

        """
        self.state_dir.mkdir(parents=True, exist_ok=True)

        metadata = AdvisoryLockMetadata(
            pid=os.getpid(),
            hostname=socket.gethostname(),
            operation=self.operation,
        )

        try:
            # Exclusive create: O_CREAT | O_EXCL fails if file exists.
            fd = os.open(
                str(self.lock_path),
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o644,
            )
        except OSError as error:
            if error.errno == errno.EEXIST:
                raise AdvisoryLockContentionError(
                    f"Advisory lock {self.lock_path} is already held. "
                    f"Check the lock file for the owning PID and operation. "
                    f"If the owning process is gone, remove the lock file "
                    f"manually: rm {self.lock_path}"
                ) from error
            raise AdvisoryLockError(
                f"Failed to acquire advisory lock {self.lock_path}: {error}"
            ) from error

        try:
            payload = yaml.dump(
                metadata.to_dict(),
                default_flow_style=False,
                sort_keys=False,
            )
            os.write(fd, payload.encode("utf-8"))
        finally:
            os.close(fd)

        self._acquired = True
        self._metadata = metadata
        return metadata

    def release(self) -> None:
        """Release the advisory lock.

        Only the process that acquired the lock may release it.  If this
        instance did not acquire the lock, this method is a no-op.

        Raises:
            AdvisoryLockError: If the lock file cannot be removed.

        """
        if not self._acquired:
            return

        try:
            self.lock_path.unlink()
        except FileNotFoundError:
            # Already gone — nothing to do.
            pass
        except OSError as error:
            raise AdvisoryLockError(
                f"Failed to release advisory lock {self.lock_path}: {error}"
            ) from error
        finally:
            self._acquired = False
            self._metadata = None

    def read_metadata(self) -> AdvisoryLockMetadata | None:
        """Read the metadata from an existing lock file.

        Returns:
            :class:`AdvisoryLockMetadata` if the lock file exists and is
            parseable, ``None`` otherwise.

        """
        if not self.lock_path.exists():
            return None
        try:
            with open(self.lock_path) as handle:
                data = yaml.safe_load(handle) or {}
        except (yaml.YAMLError, OSError):
            return None
        if not isinstance(data, dict) or "pid" not in data:
            return None
        try:
            return AdvisoryLockMetadata.from_dict(data)
        except (KeyError, TypeError, ValueError):
            return None

    def is_stale(self, max_age_seconds: float = 3600.0) -> bool:
        """Check whether the current lock is stale.

        A lock is considered stale if:

        * the lock file does not exist (no lock to check), or
        * the owning PID is no longer running on this host, or
        * the lock age exceeds ``max_age_seconds``.

        This method does **not** remove the lock.  Use :meth:`clear_stale`
        to remove a confirmed-stale lock.

        Args:
            max_age_seconds: Maximum age in seconds before a lock is
                considered stale regardless of PID liveness.  Defaults
                to 3600 (one hour).

        Returns:
            True if the lock is stale or absent, False if it appears live.

        """
        metadata = self.read_metadata()
        if metadata is None:
            return True  # No lock file — vacuously stale.

        # Check PID liveness.
        if not _pid_is_alive(metadata.pid):
            return True

        # Check age.
        try:
            acquired = datetime.fromisoformat(metadata.acquired_at)
            age = (datetime.now(timezone.utc) - acquired).total_seconds()
            if age > max_age_seconds:
                return True
        except (ValueError, TypeError):
            # Unparseable timestamp — treat as stale.
            return True

        return False

    def clear_stale(self, max_age_seconds: float = 3600.0) -> bool:
        """Remove the lock file if it is confirmed stale.

        This method checks PID liveness and age before removing.  If the
        owning process is still alive and the lock is within the age
        threshold, the lock is **not** removed and this method returns
        False.

        Args:
            max_age_seconds: Maximum age before a lock is considered stale.

        Returns:
            True if the lock was removed, False if it was not stale.

        Raises:
            AdvisoryLockError: If the lock file cannot be removed.

        """
        if not self.is_stale(max_age_seconds=max_age_seconds):
            return False

        try:
            self.lock_path.unlink()
        except FileNotFoundError:
            return True  # Already gone.
        except OSError as error:
            raise AdvisoryLockError(
                f"Failed to clear stale advisory lock {self.lock_path}: {error}"
            ) from error

        # If this instance held the lock, mark it released.
        self._acquired = False
        self._metadata = None
        return True

    def __enter__(self) -> "AdvisoryLock":
        self.acquire()
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.release()


def _pid_is_alive(pid: int) -> bool:
    """Check whether a process with the given PID is currently running.

    Uses ``os.kill(pid, 0)`` which does not send a signal but checks
    whether the process exists and we have permission to signal it.

    Returns:
        True if the process is alive, False otherwise.

    """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we cannot signal it — still alive.
        return True
    except OSError:
        return False
    return True
