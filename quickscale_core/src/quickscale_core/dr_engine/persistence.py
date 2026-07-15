"""Django-free DR persistence contracts and registration boundary.

This module defines the core persistence seams used to decouple DR contracts
from Django-backed implementations.  Callers register concrete persistence
implementations during bootstrap and then call the module-level getters to
resolve artifacts, snapshots, or policy snapshots.

SA89b Phase 1 expands the two-provider registry to cover all executable
backups-model ORM lifecycle edges: artifact CRUD, snapshot CRUD, and
policy introspection.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Any, Protocol

from quickscale_core.dr_engine.primitives import (
    BackupConfigurationError,
    BackupPolicySnapshot,
)
from quickscale_core.dr_engine.recovery import (
    ArtifactLike,
    RestoreWarning,
)

__all__ = [
    "BackupArtifactPersistence",
    "BackupPolicyPersistence",
    "PersistedBackupArtifact",
    "PersistedBackupPolicy",
    "PersistedBackupSnapshot",
    "create_artifact",
    "create_snapshot",
    "ensure_default_policy",
    "get_backup_artifact",
    "get_authoritative_snapshot_for_artifact",
    "get_backup_snapshot",
    "has_any_policy",
    "iter_expired_snapshots",
    "iter_expired_unlinked_artifacts",
    "load_default_policy",
    "refresh_snapshot",
    "register_backup_persistence",
    "resolve_admin_uploaded_restore_artifact",
    "save_artifact",
    "save_default_policy",
    "save_snapshot",
    "update_artifact_after_restore",
]


# ---------------------------------------------------------------------------
# Protocols — persisted shapes
# ---------------------------------------------------------------------------


class PersistedBackupArtifact(ArtifactLike, Protocol):
    """Protocol for a persisted artifact known to the DR persistence layer.

    The protocol adds restore-state metadata and the common fields accessed
    by DR engine orchestration and adapters.
    """

    pk: int
    status: str
    filename: str
    local_path: str | None
    remote_key: str
    checksum_sha256: str
    size_bytes: int
    backup_format: str
    database_engine: str
    database_name: str
    database_server_major: int | None
    dump_client_major: int | None
    metadata_json: dict[str, Any]
    validation_notes: str
    validated_at: datetime | None
    remote_bucket_name: str
    remote_endpoint_url: str
    remote_region_name: str
    storage_target: str
    restore_started_at: datetime | None
    deleted_at: datetime | None
    restored_at: datetime | None
    initiated_by: Any
    trigger: str
    created_at: datetime
    updated_at: datetime

    def effective_restore_scope(self) -> str: ...
    def restore_scope_label(self) -> str: ...
    def is_export_only(self) -> bool: ...


class PersistedBackupSnapshot(Protocol):
    """Protocol for a persisted snapshot known to the DR persistence layer."""

    snapshot_id: str
    status: str
    source_environment: str
    local_root_path: str
    remote_root_key: str
    child_descriptors_json: dict[str, Any] | str
    authoritative_dump: PersistedBackupArtifact | None
    failure_note: str
    created_at: datetime
    updated_at: datetime
    rollback_pin_expires_at: datetime | None
    rollback_pin_reason: str

    def has_active_rollback_pin(self, now: datetime | None = None) -> bool: ...


class PersistedBackupPolicy(Protocol):
    """Protocol for a persisted backup policy database record.

    SA89b Phase 1 structural protocol that replaces ``Any`` on the
    ``ensure_default_policy`` return contract.  The backups module's
    ``BackupPolicy`` model satisfies this protocol structurally.
    """

    pk: int
    key: str
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
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Provider protocols
# ---------------------------------------------------------------------------


class BackupArtifactPersistence(Protocol):
    """Persistence contract for backup artifact and snapshot CRUD.

    SA89b Phase 1 expands the original upload-resolution seam to cover
    all executable ORM lifecycle edges.
    """

    # --- Artifact operations ---

    def get_backup_artifact(self, artifact_id: int) -> PersistedBackupArtifact: ...

    def resolve_admin_uploaded_restore_artifact(
        self,
        checksum_sha256: str,
        size_bytes: int,
    ) -> PersistedBackupArtifact: ...

    def create_artifact(self, **kwargs: Any) -> PersistedBackupArtifact: ...

    def save_artifact(
        self,
        artifact: PersistedBackupArtifact,
        update_fields: list[str],
    ) -> None: ...

    def update_artifact_after_restore(
        self,
        artifact: PersistedBackupArtifact,
        restored_at: datetime,
    ) -> tuple[RestoreWarning, ...]: ...

    def iter_expired_unlinked_artifacts(
        self,
        cutoff: datetime,
    ) -> Iterator[PersistedBackupArtifact]: ...

    # --- Snapshot operations ---

    def get_authoritative_snapshot_for_artifact(
        self,
        artifact: PersistedBackupArtifact,
    ) -> PersistedBackupSnapshot | None: ...

    def get_backup_snapshot(self, snapshot_id: str) -> PersistedBackupSnapshot: ...

    def create_snapshot(self, **kwargs: Any) -> PersistedBackupSnapshot: ...

    def save_snapshot(
        self,
        snapshot: PersistedBackupSnapshot,
        update_fields: list[str],
    ) -> None: ...

    def refresh_snapshot(
        self,
        snapshot: PersistedBackupSnapshot,
    ) -> None: ...

    def iter_expired_snapshots(
        self,
        cutoff: datetime,
    ) -> Iterator[PersistedBackupSnapshot]: ...


class BackupPolicyPersistence(Protocol):
    """Persistence contract for backup-policy configuration snapshots.

    SA89b Phase 1 adds has_any_policy and ensure_default_policy for policy
    introspection without direct ORM access.
    """

    def load_default_policy(self) -> BackupPolicySnapshot: ...

    def save_default_policy(self, policy: BackupPolicySnapshot) -> None: ...

    def has_any_policy(self) -> bool: ...

    def ensure_default_policy(self) -> PersistedBackupPolicy: ...


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


# ---------------------------------------------------------------------------
# Artifact module-level wrappers
# ---------------------------------------------------------------------------


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


def get_backup_artifact(artifact_id: int) -> PersistedBackupArtifact:
    """Return one persisted backup artifact by primary key.

    Raises
    ------
    BackupError
        When no artifact exists for the given id.
    """
    return _get_artifact_persistence().get_backup_artifact(artifact_id)


def create_artifact(**kwargs: Any) -> PersistedBackupArtifact:
    """Create and return a new persisted backup artifact.

    All keyword arguments are passed through to the underlying provider.
    """
    return _get_artifact_persistence().create_artifact(**kwargs)


def save_artifact(
    artifact: PersistedBackupArtifact,
    update_fields: list[str],
) -> None:
    """Save changes to an existing persisted backup artifact."""
    _get_artifact_persistence().save_artifact(artifact, update_fields)


def update_artifact_after_restore(
    artifact: PersistedBackupArtifact,
    restored_at: datetime,
) -> tuple[RestoreWarning, ...]:
    """Persist restore metadata after a successful restore execution."""
    return _get_artifact_persistence().update_artifact_after_restore(
        artifact,
        restored_at=restored_at,
    )


def iter_expired_unlinked_artifacts(
    cutoff: datetime,
) -> Iterator[PersistedBackupArtifact]:
    """Yield expired artifacts that have no linked authoritative snapshot."""
    return _get_artifact_persistence().iter_expired_unlinked_artifacts(cutoff)


# ---------------------------------------------------------------------------
# Snapshot module-level wrappers
# ---------------------------------------------------------------------------


def get_authoritative_snapshot_for_artifact(
    artifact: PersistedBackupArtifact,
) -> PersistedBackupSnapshot | None:
    """Return the linked snapshot for a dump artifact if one exists."""
    return _get_artifact_persistence().get_authoritative_snapshot_for_artifact(artifact)


def get_backup_snapshot(snapshot_id: str) -> PersistedBackupSnapshot:
    """Return one stored snapshot addressed by the public snapshot locator.

    Raises
    ------
    BackupError
        When no snapshot exists for the given id.
    """
    return _get_artifact_persistence().get_backup_snapshot(snapshot_id)


def create_snapshot(**kwargs: Any) -> PersistedBackupSnapshot:
    """Create and return a new persisted backup snapshot.

    All keyword arguments are passed through to the underlying provider.
    """
    return _get_artifact_persistence().create_snapshot(**kwargs)


def save_snapshot(
    snapshot: PersistedBackupSnapshot,
    update_fields: list[str],
) -> None:
    """Save changes to an existing persisted backup snapshot."""
    _get_artifact_persistence().save_snapshot(snapshot, update_fields)


def refresh_snapshot(snapshot: PersistedBackupSnapshot) -> None:
    """Refresh a snapshot instance from the database."""
    _get_artifact_persistence().refresh_snapshot(snapshot)


def iter_expired_snapshots(
    cutoff: datetime,
) -> Iterator[PersistedBackupSnapshot]:
    """Yield expired snapshots that have not yet been deleted."""
    return _get_artifact_persistence().iter_expired_snapshots(cutoff)


# ---------------------------------------------------------------------------
# Policy module-level wrappers
# ---------------------------------------------------------------------------


def load_default_policy() -> BackupPolicySnapshot:
    """Load the default policy snapshot from configured persistence."""

    persistence = _get_policy_persistence()
    return persistence.load_default_policy()


def save_default_policy(policy: BackupPolicySnapshot) -> None:
    """Persist the default policy snapshot through configured persistence."""

    persistence = _get_policy_persistence()
    persistence.save_default_policy(policy)


def has_any_policy() -> bool:
    """Return whether at least one policy record exists in persistence."""
    return _get_policy_persistence().has_any_policy()


def ensure_default_policy() -> PersistedBackupPolicy:
    """Ensure a default policy row exists, creating one from settings if needed.

    Returns the persisted policy record through the injected provider contract.
    """
    return _get_policy_persistence().ensure_default_policy()


def _reset_backup_persistence_for_tests() -> None:
    """Reset registered providers for test isolation.

    This is intentionally private and should not be exported via runtime
    ``quickscale_core.runtime``.
    """

    global _artifact_persistence, _policy_persistence
    _artifact_persistence = None
    _policy_persistence = None
