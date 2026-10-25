"""Tests for backups module persistence providers.

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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from django.db import connection
from django.test import override_settings

from quickscale_core.dr_engine.primitives import BackupError, BackupPolicySnapshot
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
            "status": BackupSnapshot.Status.READY,
            "relative_path": filename,
            "local_path": str(sidecar_path),
            "size_bytes": sidecar_path.stat().st_size,
            "checksum_sha256": hashlib.sha256(sidecar_path.read_bytes()).hexdigest(),
            "metadata": {"manifest_status": str(payload["status"])},
        }

    return BackupSnapshot.objects.create(
        snapshot_id=snapshot_id,
        authoritative_dump=artifact,
        status=BackupSnapshot.Status.READY,
        source_environment=source_environment,
        local_root_path=str(snapshot_root),
        remote_root_key="",
        child_descriptors_json={
            "database": {
                "kind": "database_dump",
                "status": BackupSnapshot.Status.READY,
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
        postgresql_backup_artifact.status = BackupArtifact.Status.DELETED
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
            restore_scope=BackupArtifact.RestoreScope.LOCAL_ONLY,
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
        snapshot.status = BackupSnapshot.Status.DELETED
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
# Artifact provider — restore metadata and recovery-point queries
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestArtifactProviderRestoreMetadata:
    """A restore re-records the artifact row and relinks its snapshot."""

    def test_recreates_artifact_row_and_relinks_snapshot(
        self,
        artifact_provider: _BackupArtifactPersistenceProvider,
        postgresql_backup_artifact: BackupArtifact,
        tmp_path: Path,
    ) -> None:
        snapshot = _attach_complete_snapshot_contract(
            postgresql_backup_artifact,
            tmp_path,
            snapshot_id="snap-provider-restored",
        )
        artifact_id = postgresql_backup_artifact.pk
        original_created_at = postgresql_backup_artifact.created_at
        snapshot_descriptors = snapshot.child_descriptors_json

        # The dump contains the snapshot row but not the post-dump artifact row.
        BackupArtifact.objects.filter(pk=artifact_id).delete()
        snapshot.refresh_from_db()
        assert snapshot.authoritative_dump_id is None

        restored_at = datetime.now(timezone.utc)
        warnings = artifact_provider.update_artifact_after_restore(
            postgresql_backup_artifact,
            restored_at=restored_at,
            snapshot=snapshot,
        )

        assert warnings == ()
        restored = BackupArtifact.objects.get(
            filename=postgresql_backup_artifact.filename
        )
        assert restored.pk != artifact_id
        assert restored.status == BackupArtifact.Status.RESTORED
        assert restored.restored_at == restored_at
        assert restored.created_at == original_created_at
        snapshot.refresh_from_db()
        assert snapshot.authoritative_dump_id == restored.pk
        assert snapshot.status == BackupSnapshot.Status.READY
        assert snapshot.child_descriptors_json == snapshot_descriptors

    def test_raises_when_the_restored_snapshot_row_is_missing(
        self,
        artifact_provider: _BackupArtifactPersistenceProvider,
        postgresql_backup_artifact: BackupArtifact,
    ) -> None:
        postgresql_backup_artifact.metadata_json = {
            **postgresql_backup_artifact.metadata_json,
            "snapshot_id": "snap-missing-from-dump",
        }

        with pytest.raises(
            BackupError,
            match="does not contain the snapshot row 'snap-missing-from-dump'",
        ):
            artifact_provider.update_artifact_after_restore(
                postgresql_backup_artifact,
                restored_at=datetime.now(timezone.utc),
            )

    @pytest.mark.skipif(
        connection.vendor != "postgresql",
        reason="identity-sequence behavior is PostgreSQL-specific",
    )
    def test_recreation_leaves_the_identity_sequence_usable(
        self,
        artifact_provider: _BackupArtifactPersistenceProvider,
        postgresql_backup_artifact: BackupArtifact,
    ) -> None:
        artifact_id = postgresql_backup_artifact.pk
        table = BackupArtifact._meta.db_table
        quoted_table = connection.ops.quote_name(table)

        # Simulate the dump: the artifact row is absent and the sequence still
        # points at the pre-dump maximum.
        BackupArtifact.objects.filter(pk=artifact_id).delete()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT setval(pg_get_serial_sequence(%s, 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {quoted_table}), 1), "
                f"(SELECT MAX(id) FROM {quoted_table}) IS NOT NULL)",
                [table],
            )

        artifact_provider.update_artifact_after_restore(
            postgresql_backup_artifact,
            restored_at=datetime.now(timezone.utc),
        )
        restored = BackupArtifact.objects.get(
            filename=postgresql_backup_artifact.filename
        )
        created = artifact_provider.create_artifact(
            filename="next-after-restore.dump",
            local_path="/tmp/next-after-restore.dump",
            checksum_sha256="checksum-next",
            size_bytes=4,
            backup_format="pg_dump_custom",
            database_engine="django.db.backends.postgresql",
            database_name="quickscale_test",
            metadata_json={},
        )

        assert created.pk > restored.pk

    def test_newest_live_snapshot_ignores_a_deleted_newer_snapshot(
        self,
        artifact_provider: _BackupArtifactPersistenceProvider,
        postgresql_backup_artifact: BackupArtifact,
        tmp_path: Path,
    ) -> None:
        live = _attach_complete_snapshot_contract(
            postgresql_backup_artifact,
            tmp_path,
            snapshot_id="snap-live",
        )
        deleted_artifact = BackupArtifact.objects.create(
            filename="deleted-newer.dump",
            local_path="/tmp/deleted-newer.dump",
            checksum_sha256="checksum-deleted",
            size_bytes=4,
            backup_format="pg_dump_custom",
            database_engine="django.db.backends.postgresql",
            database_name="quickscale_test",
            metadata_json={},
        )
        BackupSnapshot.objects.create(
            snapshot_id="snap-newer-deleted",
            authoritative_dump=deleted_artifact,
            status=BackupSnapshot.Status.DELETED,
            source_environment="local",
            local_root_path=str(tmp_path / "snap-newer-deleted"),
            child_descriptors_json={},
        )

        assert artifact_provider.get_newest_live_snapshot().pk == live.pk

    def test_newest_live_snapshot_ignores_a_failed_newer_snapshot(
        self,
        artifact_provider: _BackupArtifactPersistenceProvider,
        postgresql_backup_artifact: BackupArtifact,
        tmp_path: Path,
    ) -> None:
        complete = _attach_complete_snapshot_contract(
            postgresql_backup_artifact,
            tmp_path,
            snapshot_id="snap-complete",
        )
        failed_artifact = BackupArtifact.objects.create(
            filename="failed-newer.dump",
            local_path="/tmp/failed-newer.dump",
            checksum_sha256="checksum-failed",
            size_bytes=4,
            backup_format="pg_dump_custom",
            database_engine="django.db.backends.postgresql",
            database_name="quickscale_test",
            metadata_json={},
        )
        BackupSnapshot.objects.create(
            snapshot_id="snap-newer-failed",
            authoritative_dump=failed_artifact,
            status=BackupSnapshot.Status.FAILED,
            source_environment="local",
            local_root_path=str(tmp_path / "snap-newer-failed"),
            child_descriptors_json={},
        )

        assert artifact_provider.get_newest_live_snapshot().pk == complete.pk

    def test_newest_live_snapshot_ignores_a_newer_failed_dump(
        self,
        artifact_provider: _BackupArtifactPersistenceProvider,
        postgresql_backup_artifact: BackupArtifact,
        tmp_path: Path,
    ) -> None:
        complete = _attach_complete_snapshot_contract(
            postgresql_backup_artifact,
            tmp_path,
            snapshot_id="snap-complete-dump",
        )
        invalid_artifact = BackupArtifact.objects.create(
            filename="invalid-newer.dump",
            local_path="/tmp/invalid-newer.dump",
            checksum_sha256="checksum-invalid",
            size_bytes=4,
            backup_format="pg_dump_custom",
            database_engine="django.db.backends.postgresql",
            database_name="quickscale_test",
            metadata_json={},
            status=BackupArtifact.Status.FAILED,
        )
        BackupSnapshot.objects.create(
            snapshot_id="snap-newer-invalid-dump",
            authoritative_dump=invalid_artifact,
            status=BackupSnapshot.Status.READY,
            source_environment="local",
            local_root_path=str(tmp_path / "snap-newer-invalid-dump"),
            child_descriptors_json={},
        )

        assert artifact_provider.get_newest_live_snapshot().pk == complete.pk

    def test_newest_live_artifact_ignores_a_deleted_newer_artifact(
        self,
        artifact_provider: _BackupArtifactPersistenceProvider,
        postgresql_backup_artifact: BackupArtifact,
    ) -> None:
        newer = BackupArtifact.objects.create(
            filename="newer-deleted.dump",
            local_path="/tmp/newer-deleted.dump",
            checksum_sha256="checksum-newer",
            size_bytes=4,
            backup_format="pg_dump_custom",
            database_engine="django.db.backends.postgresql",
            database_name="quickscale_test",
            metadata_json={},
            status=BackupArtifact.Status.DELETED,
            deleted_at=datetime.now(timezone.utc),
        )

        assert (
            artifact_provider.get_newest_live_artifact().pk
            == postgresql_backup_artifact.pk
        )
        assert newer.pk != postgresql_backup_artifact.pk


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
class TestPolicyProviderSettingsSnapshot:
    """settings_policy_snapshot behavior — the engine's settings-derived snapshot."""

    @override_settings(
        QUICKSCALE_BACKUPS_RETENTION_DAYS="7",
        QUICKSCALE_BACKUPS_NAMING_PREFIX=" app ",
        QUICKSCALE_BACKUPS_TARGET_MODE="private_remote",
        QUICKSCALE_BACKUPS_LOCAL_DIRECTORY="backups",
        QUICKSCALE_BACKUPS_REMOTE_BUCKET_NAME="bucket",
        QUICKSCALE_BACKUPS_REMOTE_PREFIX="prefix",
        QUICKSCALE_BACKUPS_REMOTE_ENDPOINT_URL="endpoint",
        QUICKSCALE_BACKUPS_REMOTE_REGION_NAME="",
        QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR="ACCESS",
        QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR="SECRET",
        QUICKSCALE_BACKUPS_AUTOMATION_ENABLED=True,
        QUICKSCALE_BACKUPS_SCHEDULE="schedule",
    )
    def test_settings_snapshot_applies_module_settings_and_coercion(
        self,
        policy_provider: _BackupPolicyPersistenceProvider,
    ) -> None:
        """The provider builds the engine snapshot from backups' own settings."""
        result = policy_provider.settings_policy_snapshot()

        assert result.retention_days == 7
        assert result.naming_prefix == " app "
        assert result.target_mode == "private_remote"
        assert result.local_directory == "backups"
        assert result.remote_bucket_name == "bucket"
        assert result.remote_prefix == "prefix"
        assert result.remote_endpoint_url == "endpoint"
        assert result.remote_region_name == ""
        assert result.remote_access_key_id_env_var == "ACCESS"
        assert result.remote_secret_access_key_env_var == "SECRET"
        assert result.automation_enabled is True
        assert result.schedule == "schedule"

    @override_settings(QUICKSCALE_BACKUPS_RETENTION_DAYS=45)
    def test_settings_snapshot_prefers_settings_over_persisted_row(
        self,
        policy_provider: _BackupPolicyPersistenceProvider,
        backup_policy: BackupPolicy,
    ) -> None:
        """A persisted row does not override the managed settings snapshot."""
        result = policy_provider.settings_policy_snapshot()

        assert result.retention_days == 45
        assert result.retention_days != backup_policy.retention_days


@pytest.mark.django_db
class TestPolicyProviderEnsureDefault:
    """ensure_default_policy behavior — return identity and no-policy cases."""

    def test_creates_and_returns_policy_when_no_row(
        self,
        policy_provider: _BackupPolicyPersistenceProvider,
    ) -> None:
        """With no default policy row, creates one and returns it."""
        BackupPolicy.objects.filter(key="default").delete()

        result = policy_provider.ensure_default_policy()

        assert result is not None
        assert result.key == "default"
        assert result.retention_days == 14
        assert BackupPolicy.objects.filter(key="default").count() == 1

    def test_returns_existing_policy(
        self,
        policy_provider: _BackupPolicyPersistenceProvider,
        backup_policy: BackupPolicy,
    ) -> None:
        """With an existing default policy row, returns the persisted record."""
        result = policy_provider.ensure_default_policy()

        assert result is not None
        assert result.pk == backup_policy.pk
        assert result.key == "default"
        assert result.retention_days == backup_policy.retention_days

    def test_updates_and_returns_when_fields_differ(
        self,
        policy_provider: _BackupPolicyPersistenceProvider,
    ) -> None:
        """When settings fields differ from the persisted row, updates and returns."""
        BackupPolicy.objects.filter(key="default").delete()
        # Create a row with different values than what settings define
        BackupPolicy.objects.create(
            key="default",
            retention_days=999,
            naming_prefix="old-prefix",
            target_mode="local",
            local_directory="/old/path",
        )

        result = policy_provider.ensure_default_policy()

        assert result is not None
        assert result.key == "default"
        # Should have been updated to match settings defaults
        assert result.retention_days == 14


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
