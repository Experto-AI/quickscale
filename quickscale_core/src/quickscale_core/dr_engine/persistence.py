"""Django-free DR persistence contracts and registration boundary.

This module defines the core persistence seams used to decouple DR contracts
from Django-backed implementations.  Callers register concrete persistence
implementations during bootstrap and then call the module-level getters to
resolve artifacts or policy snapshots.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from quickscale_core.dr_engine.primitives import (
    BackupConfigurationError,
    BackupPolicySnapshot,
)
from quickscale_core.dr_engine.recovery import ArtifactLike

__all__ = [
    "BackupArtifactPersistence",
    "BackupPolicyPersistence",
    "PersistedBackupArtifact",
    "load_default_policy",
    "register_backup_persistence",
    "resolve_admin_uploaded_restore_artifact",
    "save_default_policy",
]


class PersistedBackupArtifact(ArtifactLike, Protocol):
    """Protocol for a persisted artifact known to the DR persistence layer.

    The protocol adds restore-state metadata used by restore eligibility checks.
    """

    status: str
    restore_started_at: datetime | None


class BackupArtifactPersistence(Protocol):
    """Persistence contract for backup artifact lookup by upload fingerprint."""

    def resolve_admin_uploaded_restore_artifact(
        self,
        checksum_sha256: str,
        size_bytes: int,
    ) -> PersistedBackupArtifact: ...


class BackupPolicyPersistence(Protocol):
    """Persistence contract for backup-policy configuration snapshots."""

    def load_default_policy(self) -> BackupPolicySnapshot: ...

    def save_default_policy(self, policy: BackupPolicySnapshot) -> None: ...


_artifact_persistence: BackupArtifactPersistence | None = None
_policy_persistence: BackupPolicyPersistence | None = None


def _get_artifact_persistence() -> BackupArtifactPersistence:
    if _artifact_persistence is None:
        raise BackupConfigurationError(
            "Backup artifact persistence is not configured. "
            "Call register_backup_persistence() during bootstrap."
        )
    return _artifact_persistence


def _get_policy_persistence() -> BackupPolicyPersistence:
    if _policy_persistence is None:
        raise BackupConfigurationError(
            "Backup policy persistence is not configured. "
            "Call register_backup_persistence() during bootstrap."
        )
    return _policy_persistence


def register_backup_persistence(
    artifacts: BackupArtifactPersistence,
    policies: BackupPolicyPersistence,
) -> None:
    """Register persistence implementations for backup artifacts and policy.

    Registration is atomic: both implementations are stored together.

    * Re-registering with the same provider *instances* is idempotent.
    * Re-registering with different provider instances fails hard.
    """

    global _artifact_persistence, _policy_persistence

    if _artifact_persistence is None and _policy_persistence is None:
        _artifact_persistence = artifacts
        _policy_persistence = policies
        return

    if _artifact_persistence is artifacts and _policy_persistence is policies:
        return

    raise BackupConfigurationError(
        "Backup persistence is already configured with a different provider "
        "instance and cannot be reconfigured at runtime."
    )


def resolve_admin_uploaded_restore_artifact(
    checksum_sha256: str,
    size_bytes: int,
) -> PersistedBackupArtifact:
    """Resolve one upload fingerprint to a trusted persisted backup artifact."""

    persistence = _get_artifact_persistence()
    return persistence.resolve_admin_uploaded_restore_artifact(
        checksum_sha256=checksum_sha256,
        size_bytes=size_bytes,
    )


def load_default_policy() -> BackupPolicySnapshot:
    """Load the default policy snapshot from configured persistence."""

    persistence = _get_policy_persistence()
    return persistence.load_default_policy()


def save_default_policy(policy: BackupPolicySnapshot) -> None:
    """Persist the default policy snapshot through configured persistence."""

    persistence = _get_policy_persistence()
    persistence.save_default_policy(policy)


def _reset_backup_persistence_for_tests() -> None:
    """Reset registered providers for test isolation.

    This is intentionally private and should not be exported via runtime
    ``quickscale_core.runtime``.
    """

    global _artifact_persistence, _policy_persistence
    _artifact_persistence = None
    _policy_persistence = None
