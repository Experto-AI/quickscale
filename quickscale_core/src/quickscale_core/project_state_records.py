"""Typed records for the unified project-state surface.

``ManagedFileHash`` is the legacy managed-file ledger record and
``VersionDriftWarning`` reports one module-version disagreement between
``state.yml`` and ``config.yml``. Both were previously defined in
``project_state.py``; the unified owner stays importable there.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ManagedFileHash:
    """Hash of a managed file captured at a known timestamp.

    Attributes:
        path: Repo-relative path of the managed file (forward slashes).
        hash: SHA-256 hex digest of the file contents at capture time.
        applied_at: ISO-8601 timestamp when the hash was recorded.

    """

    path: str
    hash: str
    applied_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, str]:
        """Return a YAML-friendly dictionary representation."""
        return {
            "path": self.path,
            "hash": self.hash,
            "applied_at": self.applied_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "ManagedFileHash":
        """Build a :class:`ManagedFileHash` from a YAML mapping."""
        return cls(
            path=str(data["path"]),
            hash=str(data["hash"]),
            applied_at=str(data.get("applied_at", datetime.now().isoformat())),
        )


@dataclass
class VersionDriftWarning:
    """A single module version disagreement between state and config.

    The two sources are:
    * ``state_version`` — ``state.modules[module].version``
    * ``config_version`` — ``config.modules[module].installed_version``

    Only modules present in both sources are considered; modules present in
    only one source are reported separately through the existing
    ``StateManager.verify_filesystem`` drift channel.
    """

    module: str
    state_version: str | None
    config_version: str | None

    @property
    def message(self) -> str:
        """Human-readable drift description."""
        return (
            f"Module '{self.module}': state version is "
            f"{self.state_version!r} but config version is "
            f"{self.config_version!r}"
        )
