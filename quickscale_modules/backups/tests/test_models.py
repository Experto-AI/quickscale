"""Tests for backups module models."""

from datetime import timedelta

import pytest
from django.utils import timezone as django_timezone

from quickscale_modules_backups.models import (
    BackupArtifact,
    BackupPolicy,
    BackupSnapshot,
)


@pytest.mark.django_db
class TestBackupPolicyModel:
    """Tests for the backup policy model."""

    def test_policy_str_includes_target_mode(self, backup_policy: BackupPolicy) -> None:
        assert "local" in str(backup_policy)

    def test_policy_defaults_are_operator_friendly(self) -> None:
        policy = BackupPolicy.objects.create()
        assert policy.retention_days == 14
        assert policy.naming_prefix == "db"
        assert policy.target_mode == BackupPolicy.TARGET_MODE_LOCAL


@pytest.mark.django_db
class TestBackupArtifactModel:
    """Tests for the backup artifact model."""

    def test_artifact_str_returns_filename(
        self, backup_artifact: BackupArtifact
    ) -> None:
        assert str(backup_artifact) == backup_artifact.filename

    def test_download_path_prefers_local_path(
        self, backup_artifact: BackupArtifact
    ) -> None:
        assert backup_artifact.download_path() == backup_artifact.local_path

    def test_download_path_uses_remote_key_when_local_missing(self) -> None:
        artifact = BackupArtifact.objects.create(
            filename="backup.dump",
            storage_target=BackupArtifact.STORAGE_TARGET_PRIVATE_REMOTE,
            local_path="",
            remote_key="private/backups/backup.dump",
            checksum_sha256="abc123",
            size_bytes=100,
            backup_format="pg_dump_custom",
            database_engine="django.db.backends.postgresql",
            database_name="app",
        )
        assert artifact.download_path() == "private/backups/backup.dump"

    def test_json_artifacts_default_to_export_only_classification(self) -> None:
        artifact = BackupArtifact.objects.create(
            filename="backup.json",
            checksum_sha256="abc123",
            size_bytes=100,
            backup_format="json",
            database_engine="django.db.backends.sqlite3",
            database_name="app",
        )

        assert artifact.restore_scope is None
        assert (
            artifact.effective_restore_scope()
            == BackupArtifact.RESTORE_SCOPE_EXPORT_ONLY
        )
        assert artifact.restore_scope_label() == "Export only"
        assert artifact.is_export_only() is True

    def test_pg_dump_artifacts_default_to_local_only_classification(self) -> None:
        artifact = BackupArtifact.objects.create(
            filename="backup.dump",
            checksum_sha256="abc123",
            size_bytes=100,
            backup_format="pg_dump_custom",
            database_engine="django.db.backends.postgresql",
            database_name="app",
        )

        assert artifact.restore_scope is None
        assert (
            artifact.effective_restore_scope()
            == BackupArtifact.RESTORE_SCOPE_LOCAL_ONLY
        )
        assert artifact.restore_scope_label() == "Local restore only"
        assert artifact.is_local_only() is True

    def test_explicit_portable_classification_takes_precedence(self) -> None:
        artifact = BackupArtifact.objects.create(
            filename="backup-portable.dump",
            checksum_sha256="abc123",
            size_bytes=100,
            backup_format="pg_dump_custom",
            restore_scope=BackupArtifact.RESTORE_SCOPE_PORTABLE,
            database_engine="django.db.backends.postgresql",
            database_name="app",
        )

        assert (
            artifact.effective_restore_scope() == BackupArtifact.RESTORE_SCOPE_PORTABLE
        )
        assert artifact.restore_scope_label() == "Portable restore"
        assert artifact.is_portable() is True
        assert artifact.database_server_major is None
        assert artifact.dump_client_major is None


@pytest.mark.django_db
class TestBackupSnapshotModel:
    """Tests for the internal backup snapshot model."""

    def test_snapshot_str_returns_snapshot_id(self) -> None:
        snapshot = BackupSnapshot.objects.create(
            snapshot_id="snap-abc123",
            local_root_path="/tmp/backups/snap-abc123",
        )

        assert str(snapshot) == "snap-abc123"

    def test_has_active_rollback_pin_uses_expiration_time(self) -> None:
        snapshot = BackupSnapshot.objects.create(
            snapshot_id="snap-pin",
            local_root_path="/tmp/backups/snap-pin",
            rollback_pin_expires_at=django_timezone.now() + timedelta(hours=2),
            rollback_pin_reason="release rollback",
        )

        assert snapshot.has_active_rollback_pin() is True

        snapshot.rollback_pin_expires_at = django_timezone.now() - timedelta(minutes=1)

        assert snapshot.has_active_rollback_pin() is False

    def test_snapshot_id_is_immutable_after_creation(self) -> None:
        snapshot = BackupSnapshot.objects.create(
            snapshot_id="snap-original",
            local_root_path="/tmp/backups/snap-original",
        )

        snapshot.snapshot_id = "snap-updated"

        with pytest.raises(ValueError, match="snapshot_id is immutable"):
            snapshot.save()
