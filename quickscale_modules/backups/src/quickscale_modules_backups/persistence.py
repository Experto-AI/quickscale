"""
Django-backed persistence providers for the DR persistence seam.

Implements ``BackupArtifactPersistence`` and ``BackupPolicyPersistence`` using
the backups module models.  Module-level singleton instances are registered
during ``AppConfig.ready()``.

Both providers cover all executable ORM lifecycle
edges: artifact CRUD, snapshot CRUD, and policy introspection.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import asdict
from datetime import datetime
from typing import TYPE_CHECKING, Any

from django.db import DatabaseError, transaction

if TYPE_CHECKING:
    from quickscale_core.runtime import PersistedBackupPolicy

from quickscale_core.runtime import (
    BackupError,
    BackupRestoreBlocked,
    RestoreWarning,
)

# Lazy-imported to break the circular potential with orchestration;
# orchestration imports models at module level, so these are imported
# inside the methods that need them.
#   from quickscale_modules_backups.models import BackupArtifact, BackupPolicy

__all__ = [
    "artifact_persistence",
    "policy_persistence",
]


# ---------------------------------------------------------------------------
# Trust helpers (moved out of orchestration — only used by the provider)
# ---------------------------------------------------------------------------


def _get_admin_uploaded_restore_artifact_trust_issue(
    artifact: Any,
) -> str | None:
    """Return why one checksum-matched artifact is not trusted for admin upload."""
    artifact_issue = _admin_uploaded_artifact_trust_issue(artifact)
    if artifact_issue is not None:
        return artifact_issue
    return _admin_uploaded_snapshot_trust_issue(artifact)


def _admin_uploaded_artifact_trust_issue(artifact: Any) -> str | None:
    """Return why the artifact row itself is not a trusted restore candidate."""
    from quickscale_modules_backups.models import BackupArtifact

    if artifact.status == BackupArtifact.Status.DELETED:
        return "matching recorded artifact has been deleted"
    if artifact.is_export_only() or artifact.backup_format != "pg_dump_custom":
        return (
            "matching recorded artifact is not a PostgreSQL custom-format "
            "restore candidate"
        )
    if artifact.effective_restore_scope() not in {
        BackupArtifact.RestoreScope.LOCAL_ONLY,
        BackupArtifact.RestoreScope.PORTABLE,
    }:
        return (
            "matching recorded artifact is not classified as an eligible "
            "restore candidate"
        )
    return None


def _admin_uploaded_snapshot_trust_issue(artifact: Any) -> str | None:
    """Return why the linked snapshot fails the full-backup trust contract."""
    from quickscale_core.runtime import (
        _build_snapshot_full_backup_contract,
        _get_authoritative_snapshot_for_artifact,
    )
    from quickscale_modules_backups.models import BackupSnapshot

    snapshot = _get_authoritative_snapshot_for_artifact(artifact)
    if snapshot is None:
        return "matching recorded artifact is not linked to an authoritative snapshot"
    if snapshot.status == BackupSnapshot.Status.DELETED:
        return "matching authoritative snapshot has been deleted or pruned"

    full_backup_contract = _build_snapshot_full_backup_contract(snapshot)
    if str(full_backup_contract.get("status", "")).strip() != "complete":
        contract_issues = _summarize_full_backup_contract_issues(full_backup_contract)
        if contract_issues:
            return (
                "matching authoritative snapshot does not satisfy the full-backup "
                f"contract: {contract_issues}"
            )
        return (
            "matching authoritative snapshot does not satisfy the full-backup contract"
        )

    return _admin_uploaded_dump_provenance_trust_issue(artifact, full_backup_contract)


def _admin_uploaded_dump_provenance_trust_issue(
    artifact: Any,
    full_backup_contract: dict[str, Any],
) -> str | None:
    """Return why the snapshot's authoritative-dump metadata does not match."""
    provenance = full_backup_contract.get("provenance", {})
    authoritative_dump = (
        provenance.get("authoritative_dump", {}) if isinstance(provenance, dict) else {}
    )
    if not isinstance(authoritative_dump, dict):
        return (
            "matching authoritative snapshot does not record authoritative "
            "dump metadata"
        )
    if authoritative_dump.get("artifact_id") != artifact.pk:
        return "matching authoritative snapshot does not point back to this artifact"
    if (
        str(authoritative_dump.get("checksum_sha256", "")).strip()
        != artifact.checksum_sha256
    ):
        return (
            "matching authoritative snapshot checksum metadata does not match "
            "the artifact row"
        )
    if authoritative_dump.get("size_bytes") != artifact.size_bytes:
        return (
            "matching authoritative snapshot size metadata does not match "
            "the artifact row"
        )

    return None


def _summarize_full_backup_contract_issues(
    full_backup_contract: dict[str, Any],
) -> str:
    """Flatten completeness and provenance issues from the Phase 1 contract."""
    issues: list[str] = []

    completeness = full_backup_contract.get("completeness", {})
    if isinstance(completeness, dict):
        completeness_issues = completeness.get("issues", [])
        if isinstance(completeness_issues, list):
            issues.extend(
                str(issue).strip()
                for issue in completeness_issues
                if str(issue).strip()
            )

    provenance = full_backup_contract.get("provenance", {})
    if isinstance(provenance, dict):
        provenance_issues = provenance.get("issues", [])
        if isinstance(provenance_issues, list):
            issues.extend(
                str(issue).strip() for issue in provenance_issues if str(issue).strip()
            )

    return "; ".join(dict.fromkeys(issues))


# ---------------------------------------------------------------------------
# Artifact persistence provider
# ---------------------------------------------------------------------------


class _BackupArtifactPersistenceProvider:
    """Django-backed artifact persistence — queries ``BackupArtifact``.

    The artifact provider covers upload resolution to full
    artifact and snapshot CRUD, encapsulating all executable ORM lifecycle
    edges behind the provider seam.
    """

    # ------------------------------------------------------------------
    # Artifact operations
    # ------------------------------------------------------------------

    def get_backup_artifact(self, artifact_id: int) -> Any:
        """Return one backup artifact by primary key.

        Raises ``BackupError`` (via orchestration's get_backup_snapshot
        pattern) when not found.
        """
        from quickscale_modules_backups.models import BackupArtifact

        try:
            return BackupArtifact.objects.get(pk=artifact_id)
        except BackupArtifact.DoesNotExist as exc:
            from quickscale_core.runtime import BackupError

            raise BackupError(f"Backup artifact not found: {artifact_id}") from exc

    def resolve_admin_uploaded_restore_artifact(
        self,
        checksum_sha256: str,
        size_bytes: int,
    ) -> Any:
        """Resolve one upload fingerprint to a trusted persisted backup artifact.

        Implements the same trust chain as the original orchestration-level
        ``_resolve_admin_uploaded_restore_artifact``: normalizes the checksum,
        filters candidates by checksum + size, applies full-backup-contract
        trust checks, and returns a single trusted ``BackupArtifact`` or raises
        ``BackupRestoreBlocked``.

        Returns
        -------
        BackupArtifact
            The single trusted artifact matching the upload fingerprint.

        Raises
        ------
        BackupRestoreBlocked
            When no match, ambiguous match, or trust validation fails.
        """
        from quickscale_modules_backups.models import BackupArtifact

        normalized_checksum = checksum_sha256.strip().lower()
        if not normalized_checksum:
            raise BackupRestoreBlocked(
                "Restore blocked because the uploaded backup file checksum "
                "could not be determined."
            )
        if size_bytes < 1:
            raise BackupRestoreBlocked(
                "Restore blocked because the uploaded backup file is empty."
            )

        candidates = list(
            BackupArtifact.objects.filter(
                checksum_sha256=normalized_checksum,
                size_bytes=size_bytes,
            )
            .select_related("authoritative_snapshot")
            .order_by("pk")
        )
        if not candidates:
            raise BackupRestoreBlocked(
                "Restore blocked because the uploaded backup file does not "
                "match any recorded authoritative backup artifact."
            )

        trusted_candidates: list[Any] = []
        trust_issues: list[str] = []
        for candidate in candidates:
            trust_issue = _get_admin_uploaded_restore_artifact_trust_issue(candidate)
            if trust_issue is None:
                trusted_candidates.append(candidate)
                continue
            trust_issues.append(trust_issue)

        if not trusted_candidates:
            issue_message = (
                trust_issues[0]
                if trust_issues
                else "no trusted metadata match was available"
            )
            raise BackupRestoreBlocked(
                "Restore blocked because the uploaded backup file could not "
                "be resolved to a trusted authoritative backup artifact: "
                f"{issue_message}."
            )

        if len(trusted_candidates) > 1:
            raise BackupRestoreBlocked(
                "Restore blocked because the uploaded backup file matches "
                "multiple trusted authoritative backup artifacts."
            )

        return trusted_candidates[0]

    def create_artifact(self, **kwargs: Any) -> Any:
        """Create and return a new BackupArtifact row."""
        from quickscale_modules_backups.models import BackupArtifact

        return BackupArtifact.objects.create(**kwargs)

    def save_artifact(self, artifact: Any, update_fields: list[str]) -> None:
        """Persist changes to one backup artifact row."""
        artifact.save(update_fields=update_fields)

    def update_artifact_after_restore(
        self,
        artifact: Any,
        restored_at: datetime,
        *,
        snapshot: Any = None,
    ) -> tuple[RestoreWarning, ...]:
        """Re-record one restored artifact and relink its snapshot.

        ``pg_restore`` replaces the database with a dump taken before the
        artifact row existed, so the row is recreated through the restored
        database's identity sequence and the snapshot row is relinked.
        Metadata failures raise a visible ``BackupError``; they are never
        downgraded to a warning on a successful restore.
        """
        from quickscale_modules_backups.models import BackupArtifact

        try:
            with transaction.atomic():
                restored_artifact = self._recreate_restored_artifact(
                    artifact, restored_at
                )
                self._relink_restored_snapshot(restored_artifact, snapshot)
        except DatabaseError as exc:
            raise BackupError(
                "Restore executed, but the backup artifact and snapshot metadata "
                "could not be persisted in the restored database: "
                f"{exc}"
            ) from exc

        artifact.status = BackupArtifact.Status.RESTORED
        artifact.restored_at = restored_at
        return ()

    def _recreate_restored_artifact(
        self,
        artifact: Any,
        restored_at: datetime,
    ) -> Any:
        """Re-record the restored artifact and return its row.

        A missing row is inserted through the restored database's own identity
        sequence, so the next ordinary backup insert cannot reuse the
        artifact's former key after a dump.
        """
        from django.contrib.auth import get_user_model
        from quickscale_modules_backups.models import BackupArtifact

        initiated_by_id = getattr(artifact, "initiated_by_id", None)
        if (
            initiated_by_id is not None
            and not get_user_model()
            ._default_manager.filter(pk=initiated_by_id)
            .exists()
        ):
            initiated_by_id = None

        values = {
            "filename": artifact.filename,
            "storage_target": artifact.storage_target,
            "local_path": artifact.local_path or "",
            "remote_key": artifact.remote_key or "",
            "remote_bucket_name": artifact.remote_bucket_name or "",
            "remote_endpoint_url": artifact.remote_endpoint_url or "",
            "remote_region_name": artifact.remote_region_name or "",
            "checksum_sha256": artifact.checksum_sha256,
            "size_bytes": artifact.size_bytes or 0,
            "backup_format": artifact.backup_format,
            "restore_scope": artifact.restore_scope,
            "database_engine": artifact.database_engine,
            "database_name": artifact.database_name or "",
            "database_server_major": artifact.database_server_major,
            "dump_client_major": artifact.dump_client_major,
            "metadata_json": artifact.metadata_json or {},
            "status": BackupArtifact.Status.RESTORED,
            "trigger": artifact.trigger or "manual",
            "initiated_by_id": initiated_by_id,
            "validation_notes": artifact.validation_notes or "",
            "validated_at": artifact.validated_at,
            "restore_started_at": artifact.restore_started_at,
            "restore_error": "",
            "restored_at": restored_at,
            "deleted_at": artifact.deleted_at,
            "updated_at": restored_at,
        }
        existing = BackupArtifact.objects.filter(pk=artifact.pk).first()
        if existing is not None:
            for field_name, value in values.items():
                setattr(existing, field_name, value)
            existing.save(update_fields=list(values))
            return existing

        row = BackupArtifact.objects.create(**values)
        created_at = getattr(artifact, "created_at", None)
        if created_at is not None:
            BackupArtifact.objects.filter(pk=row.pk).update(created_at=created_at)
        return row

    def _relink_restored_snapshot(
        self,
        restored_artifact: Any,
        snapshot: Any,
    ) -> None:
        """Relink the snapshot row restored from the dump to its artifact."""
        from quickscale_modules_backups.models import BackupSnapshot

        snapshot_id = ""
        if snapshot is not None:
            snapshot_id = str(getattr(snapshot, "snapshot_id", "") or "").strip()
        if not snapshot_id:
            metadata = (
                restored_artifact.metadata_json
                if isinstance(restored_artifact.metadata_json, dict)
                else {}
            )
            snapshot_id = str(metadata.get("snapshot_id") or "").strip()
        if not snapshot_id:
            return

        row = BackupSnapshot.objects.filter(snapshot_id=snapshot_id).first()
        if row is None:
            raise BackupError(
                "Restore executed, but the restored database does not contain "
                f"the snapshot row '{snapshot_id}' for artifact {restored_artifact.pk}."
            )

        row.authoritative_dump = restored_artifact
        update_fields = ["authoritative_dump", "updated_at"]
        if snapshot is not None:
            row.status = snapshot.status
            row.child_descriptors_json = snapshot.child_descriptors_json
            row.failure_note = snapshot.failure_note
            row.remote_root_key = snapshot.remote_root_key
            row.source_environment = snapshot.source_environment
            row.local_root_path = snapshot.local_root_path
            update_fields.extend(
                [
                    "status",
                    "child_descriptors_json",
                    "failure_note",
                    "remote_root_key",
                    "source_environment",
                    "local_root_path",
                ]
            )
        row.save(update_fields=update_fields)

    def iter_expired_unlinked_artifacts(
        self,
        cutoff: datetime,
    ) -> Iterator[Any]:
        """Yield expired artifacts that have no authoritative snapshot link."""
        from quickscale_modules_backups.models import BackupArtifact

        yield from BackupArtifact.objects.filter(
            deleted_at__isnull=True,
            created_at__lt=cutoff,
            authoritative_snapshot__isnull=True,
        )

    def get_newest_live_artifact(self) -> Any | None:
        """Return the newest artifact that still counts as a recovery point."""
        from quickscale_modules_backups.models import BackupArtifact

        return (
            BackupArtifact.objects.filter(deleted_at__isnull=True)
            .exclude(status=BackupArtifact.Status.DELETED)
            .order_by("-created_at", "-pk")
            .first()
        )

    # ------------------------------------------------------------------
    # Snapshot operations
    # ------------------------------------------------------------------

    def get_authoritative_snapshot_for_artifact(
        self,
        artifact: Any,
    ) -> Any | None:
        """Return the linked snapshot for a dump artifact if one exists."""
        from quickscale_modules_backups.models import BackupSnapshot

        try:
            return artifact.authoritative_snapshot  # reverse relation
        except BackupSnapshot.DoesNotExist:
            return None

    def get_backup_snapshot(self, snapshot_id: str) -> Any:
        """Return one stored snapshot by snapshot_id with authoritative_dump."""
        from quickscale_modules_backups.models import BackupSnapshot
        from quickscale_core.runtime import (
            BackupConfigurationError,
            BackupError,
        )

        normalized_snapshot_id = snapshot_id.strip()
        if not normalized_snapshot_id:
            raise BackupConfigurationError("snapshot_id cannot be blank")

        try:
            return BackupSnapshot.objects.select_related("authoritative_dump").get(
                snapshot_id=normalized_snapshot_id
            )
        except BackupSnapshot.DoesNotExist as exc:
            raise BackupError(
                f"Backup snapshot not found: {normalized_snapshot_id}"
            ) from exc

    def create_snapshot(self, **kwargs: Any) -> Any:
        """Create and return a new BackupSnapshot row."""
        from quickscale_modules_backups.models import BackupSnapshot

        return BackupSnapshot.objects.create(**kwargs)

    def save_snapshot(self, snapshot: Any, update_fields: list[str]) -> None:
        """Persist changes to one backup snapshot row."""
        snapshot.save(update_fields=update_fields)

    def refresh_snapshot(self, snapshot: Any) -> None:
        """Refresh a snapshot instance from the database."""
        snapshot.refresh_from_db()

    def iter_expired_snapshots(self, cutoff: datetime) -> Iterator[Any]:
        """Yield expired snapshots that have not yet been deleted."""
        from quickscale_modules_backups.models import BackupSnapshot

        yield from BackupSnapshot.objects.filter(
            created_at__lt=cutoff,
        ).exclude(status=BackupSnapshot.Status.DELETED)

    def get_newest_live_snapshot(self) -> Any | None:
        """Return the newest complete snapshot that counts as a recovery point."""
        from quickscale_modules_backups.models import BackupArtifact, BackupSnapshot

        return (
            BackupSnapshot.objects.filter(
                authoritative_dump__isnull=False,
                authoritative_dump__deleted_at__isnull=True,
                authoritative_dump__status__in=[
                    BackupArtifact.Status.READY,
                    BackupArtifact.Status.VALIDATED,
                    BackupArtifact.Status.RESTORED,
                ],
                status=BackupSnapshot.Status.READY,
            )
            .order_by("-created_at", "-pk")
            .first()
        )


# ---------------------------------------------------------------------------
# Policy persistence provider
# ---------------------------------------------------------------------------


class _BackupPolicyPersistenceProvider:
    """Django-backed policy persistence — reads/writes ``BackupPolicy``.

    The policy provider adds has_any_policy and ensure_default_policy for policy
    introspection without direct ORM access from dr_engine.
    """

    def load_default_policy(self) -> Any:
        """Load the default policy snapshot from the database or settings.

        Returns a ``BackupPolicySnapshot`` built from the default policy row.
        Falls back to backups' own declared settings when no row exists.
        """
        from quickscale_core.runtime import _build_policy_snapshot_from_model
        from quickscale_modules_backups.models import BackupPolicy
        from quickscale_modules_backups._settings import (
            build_policy_snapshot_from_settings,
        )

        policy = BackupPolicy.objects.filter(key="default").first()
        if policy is None:
            return build_policy_snapshot_from_settings()
        return _build_policy_snapshot_from_model(policy)

    def settings_policy_snapshot(self) -> Any:
        """Return the policy snapshot built from backups' own settings.

        The DR engine asks for this through the registered persistence seam,
        so it never names a backups setting or writes a backups default.
        """
        from quickscale_modules_backups._settings import (
            build_policy_snapshot_from_settings,
        )

        return build_policy_snapshot_from_settings()

    def save_default_policy(self, policy: Any) -> None:
        """Persist a policy snapshot to the default ``BackupPolicy`` row.

        Uses ``get_or_create`` to handle the first-save case, then updates
        changed fields.  ORM errors propagate to the caller.
        """
        from quickscale_modules_backups.models import BackupPolicy

        defaults = asdict(policy)
        obj, created = BackupPolicy.objects.get_or_create(
            key="default",
            defaults=defaults,
        )
        if not created:
            updated_fields = [
                field_name
                for field_name, value in defaults.items()
                if getattr(obj, field_name) != value
            ]
            if updated_fields:
                for field_name in updated_fields:
                    setattr(obj, field_name, defaults[field_name])
                obj.save(update_fields=[*updated_fields, "updated_at"])

    def has_any_policy(self) -> bool:
        """Return whether at least one BackupPolicy row exists."""
        from quickscale_modules_backups.models import BackupPolicy

        return BackupPolicy.objects.exists()

    def ensure_default_policy(self) -> PersistedBackupPolicy:
        """Ensure a default policy row exists, creating one from settings.

        Returns the persisted ``BackupPolicy`` row.
        """
        from quickscale_modules_backups.models import BackupPolicy
        from quickscale_modules_backups._settings import (
            build_policy_snapshot_from_settings,
        )

        snapshot = build_policy_snapshot_from_settings()
        defaults = asdict(snapshot)
        policy, _ = BackupPolicy.objects.get_or_create(key="default", defaults=defaults)
        updated_fields = [
            field_name
            for field_name, value in defaults.items()
            if getattr(policy, field_name) != value
        ]
        if updated_fields:
            for field_name in updated_fields:
                setattr(policy, field_name, defaults[field_name])
            policy.save(update_fields=[*updated_fields, "updated_at"])
        return policy


# ---------------------------------------------------------------------------
# Module-level singletons — registered in AppConfig.ready()
# ---------------------------------------------------------------------------

artifact_persistence = _BackupArtifactPersistenceProvider()
policy_persistence = _BackupPolicyPersistenceProvider()
