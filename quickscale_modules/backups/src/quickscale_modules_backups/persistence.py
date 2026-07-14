"""
Django-backed persistence providers for the DR persistence seam.

Implements ``BackupArtifactPersistence`` and ``BackupPolicyPersistence`` using
the backups module models.  Module-level singleton instances are registered
during ``AppConfig.ready()``.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from quickscale_core.dr_engine.recovery import BackupRestoreBlocked

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
    from quickscale_modules_backups.models import BackupArtifact, BackupSnapshot

    if artifact.status == BackupArtifact.STATUS_DELETED:
        return "matching recorded artifact has been deleted"
    if artifact.is_export_only() or artifact.backup_format != "pg_dump_custom":
        return (
            "matching recorded artifact is not a PostgreSQL custom-format "
            "restore candidate"
        )
    if artifact.effective_restore_scope() not in {
        BackupArtifact.RESTORE_SCOPE_LOCAL_ONLY,
        BackupArtifact.RESTORE_SCOPE_PORTABLE,
    }:
        return (
            "matching recorded artifact is not classified as an eligible "
            "restore candidate"
        )

    from quickscale_core.dr_engine.orchestration import (
        _build_snapshot_full_backup_contract,
        _get_authoritative_snapshot_for_artifact,
    )

    snapshot = _get_authoritative_snapshot_for_artifact(artifact)
    if snapshot is None:
        return "matching recorded artifact is not linked to an authoritative snapshot"
    if snapshot.status == BackupSnapshot.STATUS_DELETED:
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
    """Django-backed artifact persistence — queries ``BackupArtifact``."""

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


# ---------------------------------------------------------------------------
# Policy persistence provider
# ---------------------------------------------------------------------------


class _BackupPolicyPersistenceProvider:
    """Django-backed policy persistence — reads/writes ``BackupPolicy``."""

    def load_default_policy(self) -> Any:
        """Load the default policy snapshot from the database or settings.

        Returns a ``BackupPolicySnapshot`` built from the default policy row.
        Falls back to Django settings defaults when no row exists.
        """
        from quickscale_modules_backups.models import BackupPolicy
        from quickscale_core.dr_engine.orchestration import (
            _build_policy_snapshot_from_model,
            _build_policy_snapshot_from_settings,
        )

        policy = BackupPolicy.objects.filter(key="default").first()
        if policy is None:
            return _build_policy_snapshot_from_settings()
        return _build_policy_snapshot_from_model(policy)

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


# ---------------------------------------------------------------------------
# Module-level singletons — registered in AppConfig.ready()
# ---------------------------------------------------------------------------

artifact_persistence = _BackupArtifactPersistenceProvider()
policy_persistence = _BackupPolicyPersistenceProvider()
