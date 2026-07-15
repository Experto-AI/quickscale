"""Tests for backups module persistence providers (SA89a Phase 2).

Covers:
* ``_BackupArtifactPersistenceProvider.resolve_admin_uploaded_restore_artifact``
  — trust chain, edge cases, guards.
* ``_BackupPolicyPersistenceProvider.load_default_policy`` — with and without
  a persisted default policy row.
* ``_BackupPolicyPersistenceProvider.save_default_policy`` — create and update.

These tests exercise the provider classes directly to verify the implementation
independent of the registration lifecycle (which is covered by test_apps.py).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from django.test import override_settings

from quickscale_core.dr_engine.primitives import BackupPolicySnapshot
from quickscale_core.dr_engine.recovery import BackupRestoreBlocked
from quickscale_modules_backups.models import (
    BackupArtifact,
    BackupPolicy,
    BackupSnapshot,
)
from quickscale_modules_backups.persistence import (
    _BackupArtifactPersistenceProvider,
    _BackupPolicyPersistenceProvider,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def artifact_provider() -> _BackupArtifactPersistenceProvider:
    """Return a fresh artifact persistence provider instance."""
    return _BackupArtifactPersistenceProvider()


@pytest.fixture
def policy_provider() -> _BackupPolicyPersistenceProvider:
    """Return a fresh policy persistence provider instance."""
    return _BackupPolicyPersistenceProvider()


def _attach_complete_snapshot_contract(
    artifact: BackupArtifact,
    tmp_path: Path,
    *,
    snapshot_id: str,
) -> BackupSnapshot:
    """Attach a complete Phase 1 snapshot contract to one artifact.

    Mirrors the same-named helper in test_services.py.
    """
    snapshot_root = tmp_path / snapshot_id
    snapshot_root.mkdir(parents=True, exist_ok=True)
    captured_at = "2026-05-01T00:00:00+00:00"
    project_slug = "quickscale-test"
    source_environment = "local"
    sidecar_specs = {
        "media-sync-manifest.json": (
            "media_sync_manifest",
            {
                "manifest_version": 1,
                "captured_at": captured_at,
                "project_slug": project_slug,
                "source_environment": source_environment,
                "status": "ready",
                "storage": {"backend": "local"},
                "inventory": [],
            },
        ),
        "env-var-manifest.json": (
            "env_var_manifest",
            {
                "manifest_version": 1,
                "captured_at": captured_at,
                "project_slug": project_slug,
                "source_environment": source_environment,
                "status": "ready",
                "count": 0,
                "names": [],
            },
        ),
        "release-metadata.json": (
            "release_metadata",
            {
                "manifest_version": 1,
                "captured_at": captured_at,
                "project_slug": project_slug,
                "source_environment": source_environment,
                "status": "ready",
                "app_version": "test-app",
                "django_version": "5.1",
                "module_versions": {},
                "git_sha": "abc123",
            },
        ),
        "promotion-verification.json": (
            "promotion_verification",
            {
                "manifest_version": 1,
                "captured_at": captured_at,
                "project_slug": project_slug,
                "source_environment": source_environment,
                "status": "ready",
                "updated_at": captured_at,
                "reports": [],
                "notes": "Reserved for route-specific plan and execute reports.",
                "rollback_pin": {
                    "active": False,
                    "expires_at": None,
                    "reason": "",
                },
            },
        ),
    }

    sidecar_descriptors: dict[str, dict[str, Any]] = {}
    for filename, (_kind, payload) in sidecar_specs.items():
        sidecar_path = snapshot_root / filename
        sidecar_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        sidecar_descriptors[filename] = {
            "kind": _kind,
            "status": BackupSnapshot.STATUS_READY,
            "relative_path": filename,
            "local_path": str(sidecar_path),
            "size_bytes": sidecar_path.stat().st_size,
            "checksum_sha256": hashlib.sha256(sidecar_path.read_bytes()).hexdigest(),
            "metadata": {"manifest_status": str(payload["status"])},
        }

    return BackupSnapshot.objects.create(
        snapshot_id=snapshot_id,
        authoritative_dump=artifact,
        status=BackupSnapshot.STATUS_READY,
        source_environment=source_environment,
        local_root_path=str(snapshot_root),
        remote_root_key="",
        child_descriptors_json={
            "database": {
                "kind": "database_dump",
                "status": BackupSnapshot.STATUS_READY,
                "relative_path": f"database/{artifact.filename}",
                "local_path": artifact.local_path,
                "size_bytes": artifact.size_bytes,
                "checksum_sha256": artifact.checksum_sha256,
                "metadata": {"backup_format": artifact.backup_format},
            },
            "sidecars": sidecar_descriptors,
        },
    )


# ---------------------------------------------------------------------------
# Artifact provider — input guardrails
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestArtifactProviderInputGuardrails:
    """resolve_admin_uploaded_restore_artifact input validations."""

    def test_rejects_empty_checksum(
        self,
        artifact_provider: _BackupArtifactPersistenceProvider,
    ) -> None:
        """Empty checksum raises BackupRestoreBlocked."""
        with pytest.raises(
            BackupRestoreBlocked,
            match="checksum could not be determined",
        ):
            artifact_provider.resolve_admin_uploaded_restore_artifact(
                checksum_sha256="",
                size_bytes=1024,
            )

    def test_rejects_zero_size(
        self,
        artifact_provider: _BackupArtifactPersistenceProvider,
    ) -> None:
        """Zero size raises BackupRestoreBlocked."""
        with pytest.raises(
            BackupRestoreBlocked,
            match="uploaded backup file is empty",
        ):
            artifact_provider.resolve_admin_uploaded_restore_artifact(
                checksum_sha256="abc123",
                size_bytes=0,
            )

    def test_rejects_no_match(
        self,
        artifact_provider: _BackupArtifactPersistenceProvider,
    ) -> None:
        """No matching artifact raises BackupRestoreBlocked."""
        with pytest.raises(
            BackupRestoreBlocked,
            match="does not match any recorded authoritative backup artifact",
        ):
            artifact_provider.resolve_admin_uploaded_restore_artifact(
                checksum_sha256="nonexistentchecksum",
                size_bytes=999,
            )


# ---------------------------------------------------------------------------
# Artifact provider — trust resolution
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestArtifactProviderTrustResolution:
    """Artifact trust checks during resolve."""

    def test_resolves_single_trusted_match(
        self,
        artifact_provider: _BackupArtifactPersistenceProvider,
        postgresql_backup_artifact: BackupArtifact,
        tmp_path: Path,
    ) -> None:
        """Single trusted match returns the artifact."""
        _attach_complete_snapshot_contract(
            postgresql_backup_artifact,
            tmp_path,
            snapshot_id="snap-trusted-match",
        )

        result = artifact_provider.resolve_admin_uploaded_restore_artifact(
            checksum_sha256=postgresql_backup_artifact.checksum_sha256,
            size_bytes=postgresql_backup_artifact.size_bytes,
        )

        assert result.pk == postgresql_backup_artifact.pk
        assert result.filename == postgresql_backup_artifact.filename

    def test_rejects_deleted_artifact(
        self,
        artifact_provider: _BackupArtifactPersistenceProvider,
        postgresql_backup_artifact: BackupArtifact,
        tmp_path: Path,
    ) -> None:
        """Deleted artifact is rejected by trust check."""
        _attach_complete_snapshot_contract(
            postgresql_backup_artifact,
            tmp_path,
            snapshot_id="snap-deleted-artifact",
        )
        postgresql_backup_artifact.status = BackupArtifact.STATUS_DELETED
        postgresql_backup_artifact.save(update_fields=["status", "updated_at"])

        with pytest.raises(
            BackupRestoreBlocked,
            match="matching recorded artifact has been deleted",
        ):
            artifact_provider.resolve_admin_uploaded_restore_artifact(
                checksum_sha256=postgresql_backup_artifact.checksum_sha256,
                size_bytes=postgresql_backup_artifact.size_bytes,
            )

    def test_rejects_export_only_artifact(
        self,
        artifact_provider: _BackupArtifactPersistenceProvider,
        backup_artifact: BackupArtifact,
    ) -> None:
        """Export-only artifact (json format) is rejected by trust check."""
        with pytest.raises(
            BackupRestoreBlocked,
            match="not a PostgreSQL custom-format restore candidate",
        ):
            artifact_provider.resolve_admin_uploaded_restore_artifact(
                checksum_sha256=backup_artifact.checksum_sha256,
                size_bytes=backup_artifact.size_bytes,
            )

    def test_rejects_ambiguous_trusted_matches(
        self,
        artifact_provider: _BackupArtifactPersistenceProvider,
        postgresql_backup_artifact: BackupArtifact,
        tmp_path: Path,
    ) -> None:
        """Multiple trusted matches raises BackupRestoreBlocked."""
        _attach_complete_snapshot_contract(
            postgresql_backup_artifact,
            tmp_path,
            snapshot_id="snap-ambiguous-first",
        )

        # Create a second artifact with same checksum+size
        dup_path = tmp_path / "duplicate.dump"
        original_content = Path(postgresql_backup_artifact.local_path).read_bytes()
        dup_path.write_bytes(original_content)
        duplicate_artifact = BackupArtifact.objects.create(
            filename="duplicate.dump",
            local_path=str(dup_path),
            checksum_sha256=postgresql_backup_artifact.checksum_sha256,
            size_bytes=postgresql_backup_artifact.size_bytes,
            backup_format="pg_dump_custom",
            restore_scope=BackupArtifact.RESTORE_SCOPE_LOCAL_ONLY,
            database_engine=postgresql_backup_artifact.database_engine,
            database_name=postgresql_backup_artifact.database_name,
            database_server_major=postgresql_backup_artifact.database_server_major,
            dump_client_major=postgresql_backup_artifact.dump_client_major,
            metadata_json={"environment": "test"},
        )
        _attach_complete_snapshot_contract(
            duplicate_artifact,
            tmp_path,
            snapshot_id="snap-ambiguous-second",
        )

        with pytest.raises(
            BackupRestoreBlocked,
            match="matches multiple trusted authoritative backup artifacts",
        ):
            artifact_provider.resolve_admin_uploaded_restore_artifact(
                checksum_sha256=postgresql_backup_artifact.checksum_sha256,
                size_bytes=postgresql_backup_artifact.size_bytes,
            )

    def test_rejects_artifact_without_snapshot(
        self,
        artifact_provider: _BackupArtifactPersistenceProvider,
        postgresql_backup_artifact: BackupArtifact,
    ) -> None:
        """Artifact without a snapshot contract is rejected."""
        with pytest.raises(
            BackupRestoreBlocked,
            match="not linked to an authoritative snapshot",
        ):
            artifact_provider.resolve_admin_uploaded_restore_artifact(
                checksum_sha256=postgresql_backup_artifact.checksum_sha256,
                size_bytes=postgresql_backup_artifact.size_bytes,
            )

    def test_rejects_artifact_with_deleted_snapshot(
        self,
        artifact_provider: _BackupArtifactPersistenceProvider,
        postgresql_backup_artifact: BackupArtifact,
        tmp_path: Path,
    ) -> None:
        """Artifact with a deleted snapshot is rejected."""
        snapshot = _attach_complete_snapshot_contract(
            postgresql_backup_artifact,
            tmp_path,
            snapshot_id="snap-deleted-linked",
        )
        snapshot.status = BackupSnapshot.STATUS_DELETED
        snapshot.save(update_fields=["status", "updated_at"])

        with pytest.raises(
            BackupRestoreBlocked,
            match="authoritative snapshot has been deleted or pruned",
        ):
            artifact_provider.resolve_admin_uploaded_restore_artifact(
                checksum_sha256=postgresql_backup_artifact.checksum_sha256,
                size_bytes=postgresql_backup_artifact.size_bytes,
            )

    def test_rejects_incomplete_snapshot_contract(
        self,
        artifact_provider: _BackupArtifactPersistenceProvider,
        postgresql_backup_artifact: BackupArtifact,
        tmp_path: Path,
    ) -> None:
        """Artifact with incomplete snapshot contract is rejected."""
        _attach_complete_snapshot_contract(
            postgresql_backup_artifact,
            tmp_path,
            snapshot_id="snap-incomplete-contract",
        )
        from quickscale_modules_backups.models import BackupSnapshot as BSnapshot

        snapshot = BSnapshot.objects.get(authoritative_dump=postgresql_backup_artifact)
        (Path(snapshot.local_root_path) / "release-metadata.json").unlink()

        with pytest.raises(
            BackupRestoreBlocked,
            match="full-backup contract",
        ):
            artifact_provider.resolve_admin_uploaded_restore_artifact(
                checksum_sha256=postgresql_backup_artifact.checksum_sha256,
                size_bytes=postgresql_backup_artifact.size_bytes,
            )


# ---------------------------------------------------------------------------
# Policy provider
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPolicyProviderLoadDefault:
    """load_default_policy behavior."""

    def test_load_from_settings_when_no_row(
        self,
        policy_provider: _BackupPolicyPersistenceProvider,
    ) -> None:
        """Without a default policy row, return settings-built snapshot."""
        BackupPolicy.objects.filter(key="default").delete()

        snapshot = policy_provider.load_default_policy()

        assert isinstance(snapshot, BackupPolicySnapshot)
        assert snapshot.retention_days == 14
        assert snapshot.target_mode == "local"
        assert snapshot.naming_prefix == "db"

    def test_load_from_model_row(
        self,
        policy_provider: _BackupPolicyPersistenceProvider,
        backup_policy: BackupPolicy,
    ) -> None:
        """With a default policy row, return model-built snapshot."""
        snapshot = policy_provider.load_default_policy()

        assert isinstance(snapshot, BackupPolicySnapshot)
        assert snapshot.retention_days == backup_policy.retention_days
        assert snapshot.target_mode == backup_policy.target_mode
        assert snapshot.local_directory == backup_policy.local_directory

    @override_settings(
        QUICKSCALE_BACKUPS_RETENTION_DAYS=30,
        QUICKSCALE_BACKUPS_TARGET_MODE="private_remote",
        QUICKSCALE_BACKUPS_LOCAL_DIRECTORY=".managed/backups",
        QUICKSCALE_BACKUPS_REMOTE_BUCKET_NAME="managed-bucket",
    )
    def test_load_from_model_prefers_row_over_settings(
        self,
        policy_provider: _BackupPolicyPersistenceProvider,
        backup_policy: BackupPolicy,
    ) -> None:
        """When a row exists, its values are used, not settings overrides."""
        snapshot = policy_provider.load_default_policy()

        assert snapshot.retention_days == backup_policy.retention_days
        assert snapshot.target_mode == backup_policy.target_mode
        assert snapshot.local_directory == backup_policy.local_directory


@pytest.mark.django_db
class TestPolicyProviderSaveDefault:
    """save_default_policy behavior."""

    def test_save_creates_new_row(
        self,
        policy_provider: _BackupPolicyPersistenceProvider,
    ) -> None:
        """Save creates a default policy row when none exists."""
        BackupPolicy.objects.filter(key="default").delete()

        snapshot = BackupPolicySnapshot(
            retention_days=21,
            naming_prefix="custom",
            target_mode="private_remote",
            local_directory="/custom/path",
            remote_bucket_name="custom-bucket",
            remote_prefix="backups/",
            remote_endpoint_url="https://s3.custom.invalid",
            remote_region_name="us-west-2",
            remote_access_key_id_env_var="CUSTOM_ACCESS_KEY",
            remote_secret_access_key_env_var="CUSTOM_SECRET_KEY",
            automation_enabled=True,
            schedule="0 4 * * *",
        )

        policy_provider.save_default_policy(snapshot)

        row = BackupPolicy.objects.get(key="default")
        assert row.retention_days == 21
        assert row.naming_prefix == "custom"
        assert row.target_mode == "private_remote"
        assert row.local_directory == "/custom/path"
        assert row.remote_bucket_name == "custom-bucket"
        assert row.automation_enabled is True
        assert row.schedule == "0 4 * * *"

    def test_save_updates_existing_row(
        self,
        policy_provider: _BackupPolicyPersistenceProvider,
        backup_policy: BackupPolicy,
    ) -> None:
        """Save updates an existing default policy row."""
        snapshot = BackupPolicySnapshot(
            retention_days=90,
            naming_prefix="updated",
            target_mode="private_remote",
            local_directory="/updated/path",
            remote_bucket_name="updated-bucket",
            remote_prefix="updated/prefix",
            remote_endpoint_url="https://updated.invalid",
            remote_region_name="eu-west-1",
            remote_access_key_id_env_var="UPDATED_ACCESS_KEY",
            remote_secret_access_key_env_var="UPDATED_SECRET_KEY",
            automation_enabled=True,
            schedule="0 6 * * *",
        )

        policy_provider.save_default_policy(snapshot)

        backup_policy.refresh_from_db()
        assert backup_policy.retention_days == 90
        assert backup_policy.naming_prefix == "updated"
        assert backup_policy.target_mode == "private_remote"
        assert backup_policy.local_directory == "/updated/path"
        assert backup_policy.remote_bucket_name == "updated-bucket"
        assert backup_policy.remote_prefix == "updated/prefix"
        assert backup_policy.remote_endpoint_url == "https://updated.invalid"
        assert backup_policy.remote_region_name == "eu-west-1"
        assert backup_policy.remote_access_key_id_env_var == "UPDATED_ACCESS_KEY"
        assert backup_policy.remote_secret_access_key_env_var == "UPDATED_SECRET_KEY"
        assert backup_policy.automation_enabled is True
        assert backup_policy.schedule == "0 6 * * *"
        assert BackupPolicy.objects.count() == 1
