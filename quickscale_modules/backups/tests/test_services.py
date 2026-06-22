"""Tests for backups module services."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timedelta, timezone
from io import BytesIO, StringIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, connections
from django.test import override_settings

import quickscale_modules_backups.services as backup_services
from quickscale_modules_backups.models import (
    BackupArtifact,
    BackupPolicy,
    BackupSnapshot,
)
from quickscale_modules_backups.services import (
    BackupError,
    BackupConfigurationError,
    BackupLockError,
    BackupPolicySnapshot,
    BackupRestoreBlocked,
    clear_backup_snapshot_rollback_pin,
    RemoteDeleter,
    RemoteMaterializer,
    RemoteUploader,
    RestoreResult,
    RestoreSourceResolutionMode,
    ShellCommandRunner,
    build_backup_filename,
    create_backup,
    load_policy_snapshot,
    prune_expired_backups,
    report_backup_snapshot,
    restore_admin_uploaded_backup,
    restore_backup_artifact,
    restore_backup_source,
    set_backup_snapshot_rollback_pin,
    validate_backup_artifact,
    validate_policy_snapshot,
)


def _set_postgresql_default_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the default connection look like a PostgreSQL runtime for service tests."""
    monkeypatch.setitem(
        connections["default"].settings_dict,
        "ENGINE",
        "django.db.backends.postgresql",
    )
    monkeypatch.setitem(
        connections["default"].settings_dict,
        "NAME",
        "quickscale_test",
    )


def _mock_postgresql_18_contract(
    monkeypatch: pytest.MonkeyPatch,
    *,
    server_version: str = "18.3 (Debian 18.3-1)",
    tool_versions: dict[str, str] | None = None,
) -> None:
    """Mock PostgreSQL server and tool discovery for PG18 contract checks."""
    resolved_tool_versions = {
        "pg_dump": "pg_dump (PostgreSQL) 18.4",
        "pg_restore": "pg_restore (PostgreSQL) 18.4",
    }
    if tool_versions is not None:
        resolved_tool_versions.update(tool_versions)

    def fake_get_database_server_version(_engine: str) -> str:
        return server_version

    def fake_get_postgresql_tool_version(executable: str) -> str:
        return resolved_tool_versions[executable]

    monkeypatch.setattr(
        backup_services,
        "_get_database_server_version",
        fake_get_database_server_version,
    )
    monkeypatch.setattr(
        backup_services,
        "_get_postgresql_tool_version",
        fake_get_postgresql_tool_version,
    )


def _private_remote_policy_snapshot(
    *,
    local_directory: str = ".quickscale/backups",
) -> BackupPolicySnapshot:
    return BackupPolicySnapshot(
        retention_days=14,
        naming_prefix="db",
        target_mode=BackupPolicy.TARGET_MODE_PRIVATE_REMOTE,
        local_directory=local_directory,
        remote_bucket_name="private-backups",
        remote_prefix="ops/backups",
        remote_endpoint_url="https://object-storage.example.invalid",
        remote_region_name="us-east-1",
        remote_access_key_id_env_var="TEST_BACKUPS_ACCESS_KEY",
        remote_secret_access_key_env_var="TEST_BACKUPS_SECRET_KEY",
        automation_enabled=False,
        schedule="0 2 * * *",
    )


def _get_authoritative_snapshot(artifact: BackupArtifact) -> BackupSnapshot:
    """Load the snapshot linked to one authoritative dump artifact."""
    return BackupSnapshot.objects.get(authoritative_dump=artifact)


def _attach_complete_snapshot_contract(
    artifact: BackupArtifact,
    tmp_path: Path,
    *,
    snapshot_id: str,
) -> BackupSnapshot:
    """Attach a complete Phase 1 snapshot contract to one artifact."""
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
                "rollback_pin": {"active": False, "expires_at": None, "reason": ""},
            },
        ),
    }

    sidecar_descriptors: dict[str, dict[str, Any]] = {}
    for filename, (kind, payload) in sidecar_specs.items():
        sidecar_path = snapshot_root / filename
        sidecar_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        sidecar_descriptors[filename] = {
            "kind": kind,
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


@pytest.mark.django_db
class TestPolicyValidation:
    """Tests for policy snapshot validation."""

    def test_private_remote_requires_bucket_and_credentials(self) -> None:
        snapshot = BackupPolicySnapshot(
            retention_days=14,
            naming_prefix="db",
            target_mode=BackupPolicy.TARGET_MODE_PRIVATE_REMOTE,
            local_directory=".quickscale/backups",
            remote_bucket_name="",
            remote_prefix="backups/private",
            remote_endpoint_url="",
            remote_region_name="",
            remote_access_key_id_env_var="",
            remote_secret_access_key_env_var="",
            automation_enabled=False,
            schedule="0 2 * * *",
        )

        issues = validate_policy_snapshot(snapshot)

        assert (
            "remote_bucket_name is required when target_mode is private_remote"
            in issues
        )
        assert (
            "remote_access_key_id_env_var is required when target_mode is private_remote"
            in issues
        )
        assert (
            "remote_secret_access_key_env_var is required when target_mode is private_remote"
            in issues
        )

    def test_retention_days_below_one_is_invalid(self) -> None:
        snapshot = BackupPolicySnapshot(
            retention_days=0,
            naming_prefix="db",
            target_mode=BackupPolicy.TARGET_MODE_LOCAL,
            local_directory=".quickscale/backups",
            remote_bucket_name="",
            remote_prefix="backups/private",
            remote_endpoint_url="",
            remote_region_name="",
            remote_access_key_id_env_var="",
            remote_secret_access_key_env_var="",
            automation_enabled=False,
            schedule="0 2 * * *",
        )
        issues = validate_policy_snapshot(snapshot)
        assert "retention_days must be at least 1 day" in issues

    def test_blank_naming_prefix_is_invalid(self) -> None:
        snapshot = BackupPolicySnapshot(
            retention_days=14,
            naming_prefix="   ",
            target_mode=BackupPolicy.TARGET_MODE_LOCAL,
            local_directory=".quickscale/backups",
            remote_bucket_name="",
            remote_prefix="backups/private",
            remote_endpoint_url="",
            remote_region_name="",
            remote_access_key_id_env_var="",
            remote_secret_access_key_env_var="",
            automation_enabled=False,
            schedule="0 2 * * *",
        )
        issues = validate_policy_snapshot(snapshot)
        assert "naming_prefix cannot be blank" in issues

    def test_invalid_target_mode_is_rejected(self) -> None:
        snapshot = BackupPolicySnapshot(
            retention_days=14,
            naming_prefix="db",
            target_mode="ftp",
            local_directory=".quickscale/backups",
            remote_bucket_name="",
            remote_prefix="backups/private",
            remote_endpoint_url="",
            remote_region_name="",
            remote_access_key_id_env_var="",
            remote_secret_access_key_env_var="",
            automation_enabled=False,
            schedule="0 2 * * *",
        )
        issues = validate_policy_snapshot(snapshot)
        assert "target_mode must be 'local' or 'private_remote'" in issues

    def test_blank_local_directory_is_invalid(self) -> None:
        snapshot = BackupPolicySnapshot(
            retention_days=14,
            naming_prefix="db",
            target_mode=BackupPolicy.TARGET_MODE_LOCAL,
            local_directory="   ",
            remote_bucket_name="",
            remote_prefix="backups/private",
            remote_endpoint_url="",
            remote_region_name="",
            remote_access_key_id_env_var="",
            remote_secret_access_key_env_var="",
            automation_enabled=False,
            schedule="0 2 * * *",
        )
        issues = validate_policy_snapshot(snapshot)
        assert "local_directory cannot be blank" in issues

    def test_automation_enabled_without_schedule_is_invalid(self) -> None:
        snapshot = BackupPolicySnapshot(
            retention_days=14,
            naming_prefix="db",
            target_mode=BackupPolicy.TARGET_MODE_LOCAL,
            local_directory=".quickscale/backups",
            remote_bucket_name="",
            remote_prefix="backups/private",
            remote_endpoint_url="",
            remote_region_name="",
            remote_access_key_id_env_var="",
            remote_secret_access_key_env_var="",
            automation_enabled=True,
            schedule="",
        )
        issues = validate_policy_snapshot(snapshot)
        assert "schedule is required when automation_enabled is true" in issues

    def test_build_backup_filename_uses_prefix_slug_and_timestamp(self) -> None:
        snapshot = BackupPolicySnapshot.from_settings()
        filename = build_backup_filename(
            snapshot,
            now=datetime(2026, 3, 26, 12, 0, tzinfo=timezone.utc),
            suffix="json",
        )

        assert filename.startswith("db-")
        assert filename.endswith("20260326T120000Z.json")

    @override_settings(
        QUICKSCALE_BACKUPS_RETENTION_DAYS=30,
        QUICKSCALE_BACKUPS_TARGET_MODE=BackupPolicy.TARGET_MODE_PRIVATE_REMOTE,
        QUICKSCALE_BACKUPS_LOCAL_DIRECTORY=".managed/backups",
        QUICKSCALE_BACKUPS_REMOTE_BUCKET_NAME="managed-bucket",
        QUICKSCALE_BACKUPS_REMOTE_REGION_NAME="us-east-1",
        QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR="OPS_BACKUPS_ACCESS_KEY_ID",
        QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR="OPS_BACKUPS_SECRET_ACCESS_KEY",
    )
    def test_load_policy_snapshot_prefers_managed_settings_over_stale_policy_row(
        self,
        backup_policy: BackupPolicy,
    ) -> None:
        backup_policy.retention_days = 7
        backup_policy.target_mode = BackupPolicy.TARGET_MODE_LOCAL
        backup_policy.local_directory = ".stale/backups"
        backup_policy.remote_bucket_name = "stale-bucket"
        backup_policy.remote_region_name = ""
        backup_policy.remote_access_key_id_env_var = "STALE_ACCESS_KEY"
        backup_policy.remote_secret_access_key_env_var = "STALE_SECRET_KEY"
        backup_policy.save()

        snapshot = load_policy_snapshot()

        assert snapshot.retention_days == 30
        assert snapshot.target_mode == BackupPolicy.TARGET_MODE_PRIVATE_REMOTE
        assert snapshot.local_directory == ".managed/backups"
        assert snapshot.remote_bucket_name == "managed-bucket"
        assert snapshot.remote_region_name == "us-east-1"
        assert snapshot.remote_access_key_id_env_var == "OPS_BACKUPS_ACCESS_KEY_ID"
        assert (
            snapshot.remote_secret_access_key_env_var == "OPS_BACKUPS_SECRET_ACCESS_KEY"
        )

        backup_policy.refresh_from_db()
        assert backup_policy.retention_days == 30
        assert backup_policy.target_mode == BackupPolicy.TARGET_MODE_PRIVATE_REMOTE
        assert backup_policy.local_directory == ".managed/backups"
        assert backup_policy.remote_bucket_name == "managed-bucket"


@pytest.mark.django_db
class TestBackupLifecycle:
    """Tests for backup creation, validation, pruning, and restore guardrails."""

    def test_create_backup_uses_json_export_for_sqlite(
        self,
        superuser: AbstractBaseUser,
        backup_policy: BackupPolicy,
        local_backup_settings: Path,
    ) -> None:
        backup_policy.local_directory = str(local_backup_settings)
        backup_policy.save(update_fields=["local_directory", "updated_at"])

        artifact = create_backup(initiated_by=superuser, trigger="manual")

        assert artifact.backup_format == "json"
        assert artifact.storage_target == BackupArtifact.STORAGE_TARGET_LOCAL
        assert artifact.local_path.startswith(str(local_backup_settings))
        assert Path(artifact.local_path).exists()
        assert artifact.checksum_sha256
        assert artifact.size_bytes > 0
        assert artifact.metadata_json["database_engine"] == "django.db.backends.sqlite3"
        assert artifact.metadata_json["database_server_version"]
        assert artifact.database_server_major is None
        assert artifact.dump_client_major is None
        payload = json.loads(Path(artifact.local_path).read_text(encoding="utf-8"))
        assert isinstance(payload, list)

        snapshot = _get_authoritative_snapshot(artifact)
        snapshot_root = local_backup_settings / "snapshots" / snapshot.snapshot_id
        assert snapshot is not None
        assert len(snapshot.snapshot_id) == 32
        assert Path(snapshot.local_root_path) == snapshot_root
        assert snapshot.status == BackupSnapshot.STATUS_READY
        assert snapshot.source_environment == "local"
        assert (
            Path(artifact.local_path) == snapshot_root / "database" / artifact.filename
        )
        assert snapshot.child_descriptors_json["database"]["relative_path"] == (
            f"database/{artifact.filename}"
        )
        assert sorted(snapshot.child_descriptors_json["sidecars"]) == [
            "env-var-manifest.json",
            "media-sync-manifest.json",
            "promotion-verification.json",
            "release-metadata.json",
        ]
        assert (snapshot_root / "env-var-manifest.json").exists()
        assert (snapshot_root / "media-sync-manifest.json").exists()
        assert (snapshot_root / "promotion-verification.json").exists()
        assert (snapshot_root / "release-metadata.json").exists()
        media_manifest = json.loads(
            (snapshot_root / "media-sync-manifest.json").read_text(encoding="utf-8")
        )
        release_metadata = json.loads(
            (snapshot_root / "release-metadata.json").read_text(encoding="utf-8")
        )
        env_manifest = json.loads(
            (snapshot_root / "env-var-manifest.json").read_text(encoding="utf-8")
        )
        assert media_manifest["status"] == "missing_media_root"
        assert release_metadata["app_version"] == "test-app"
        assert release_metadata["project_slug"] == local_backup_settings.parent.name
        assert env_manifest["count"] == len(env_manifest["names"])

    @override_settings(
        QUICKSCALE_STORAGE_BACKEND="s3",
        AWS_STORAGE_BUCKET_NAME="media-bucket",
        AWS_S3_ENDPOINT_URL="https://objects.example.invalid",
        AWS_S3_REGION_NAME="auto",
        AWS_ACCESS_KEY_ID="media-access-key",
        AWS_SECRET_ACCESS_KEY="media-secret-key",
        AWS_QUERYSTRING_AUTH=False,
    )
    def test_create_backup_captures_s3_compatible_media_inventory(
        self,
        superuser: AbstractBaseUser,
        backup_policy: BackupPolicy,
        local_backup_settings: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import quickscale_modules_storage.helpers as storage_helpers  # type: ignore[import-untyped]

        backup_policy.local_directory = str(local_backup_settings)
        backup_policy.save(update_fields=["local_directory", "updated_at"])
        expected_inventory = [
            {
                "relative_path": "blog/uploads/hero.png",
                "storage_key": "media/blog/uploads/hero.png",
                "size_bytes": 128,
                "provider_etag": "etag-123",
                "modified_at": "2026-04-06T12:30:00+00:00",
            }
        ]

        def fake_inventory(_settings_obj: object) -> list[dict[str, Any]]:
            return expected_inventory

        monkeypatch.setattr(
            storage_helpers,
            "list_s3_compatible_media_inventory",
            fake_inventory,
        )

        artifact = create_backup(initiated_by=superuser, trigger="manual")

        snapshot = _get_authoritative_snapshot(artifact)
        media_manifest = json.loads(
            (Path(snapshot.local_root_path) / "media-sync-manifest.json").read_text(
                encoding="utf-8"
            )
        )

        assert snapshot is not None
        assert media_manifest["status"] == "ready"
        assert media_manifest["inventory"] == expected_inventory
        assert media_manifest["storage"]["bucket_name"] == "media-bucket"
        assert media_manifest["storage"]["access_key_id_configured"] is True
        assert media_manifest["storage"]["secret_access_key_configured"] is True
        assert "media-access-key" not in json.dumps(media_manifest)

    def test_create_backup_persists_postgresql_18_contract_metadata(
        self,
        superuser: AbstractBaseUser,
        local_backup_settings: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        policy = BackupPolicySnapshot(
            retention_days=14,
            naming_prefix="db",
            target_mode=BackupPolicy.TARGET_MODE_LOCAL,
            local_directory=str(local_backup_settings),
            remote_bucket_name="",
            remote_prefix="backups/private",
            remote_endpoint_url="",
            remote_region_name="",
            remote_access_key_id_env_var="",
            remote_secret_access_key_env_var="",
            automation_enabled=False,
            schedule="0 2 * * *",
        )
        _set_postgresql_default_connection(monkeypatch)
        _mock_postgresql_18_contract(monkeypatch)

        def successful_runner(
            command: list[str], *, env: dict[str, str] | None = None
        ) -> None:
            del env
            local_path = Path(command[command.index("--file") + 1])
            local_path.write_bytes(b"pg_dump_custom_data")

        artifact = create_backup(
            initiated_by=superuser,
            trigger="manual",
            policy=policy,
            shell_runner=cast(ShellCommandRunner, successful_runner),
        )

        assert artifact.backup_format == "pg_dump_custom"
        assert Path(artifact.local_path).exists()
        assert artifact.database_server_major == 18
        assert artifact.dump_client_major == 18
        assert (
            artifact.metadata_json["database_server_version"] == "18.3 (Debian 18.3-1)"
        )
        assert artifact.metadata_json["database_server_major"] == 18
        assert artifact.metadata_json["pg_dump_version"] == "pg_dump (PostgreSQL) 18.4"
        assert artifact.metadata_json["dump_client_major"] == 18

    def test_create_backup_private_remote_calls_uploader(
        self,
        superuser: AbstractBaseUser,
        local_backup_settings: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("TEST_BACKUPS_ACCESS_KEY", "key-id")
        monkeypatch.setenv("TEST_BACKUPS_SECRET_KEY", "secret-key")
        policy = BackupPolicySnapshot(
            retention_days=14,
            naming_prefix="db",
            target_mode=BackupPolicy.TARGET_MODE_PRIVATE_REMOTE,
            local_directory=str(local_backup_settings),
            remote_bucket_name="private-backups",
            remote_prefix="ops/backups",
            remote_endpoint_url="https://example.invalid",
            remote_region_name="auto",
            remote_access_key_id_env_var="TEST_BACKUPS_ACCESS_KEY",
            remote_secret_access_key_env_var="TEST_BACKUPS_SECRET_KEY",
            automation_enabled=False,
            schedule="0 2 * * *",
        )
        uploaded: list[tuple[str, str, str, str, str]] = []

        def fake_uploader(
            local_path: Path, resolved_policy: BackupPolicySnapshot
        ) -> str:
            uploaded.append(
                (
                    local_path.name,
                    resolved_policy.remote_bucket_name,
                    resolved_policy.remote_prefix,
                    resolved_policy.resolve_remote_access_key_id(),
                    resolved_policy.resolve_remote_secret_access_key(),
                )
            )
            return f"{resolved_policy.remote_prefix}/{local_path.name}"

        artifact = create_backup(
            initiated_by=superuser,
            trigger="admin",
            policy=policy,
            remote_uploader=cast(RemoteUploader, fake_uploader),
        )

        snapshot = _get_authoritative_snapshot(artifact)
        assert snapshot is not None
        snapshot_prefix = f"ops/backups/snapshots/{snapshot.snapshot_id}"

        assert artifact.storage_target == BackupArtifact.STORAGE_TARGET_PRIVATE_REMOTE
        assert artifact.remote_key == f"{snapshot_prefix}/database/{artifact.filename}"
        assert uploaded == [
            (
                artifact.filename,
                "private-backups",
                f"{snapshot_prefix}/database",
                "key-id",
                "secret-key",
            ),
            (
                "media-sync-manifest.json",
                "private-backups",
                snapshot_prefix,
                "key-id",
                "secret-key",
            ),
            (
                "env-var-manifest.json",
                "private-backups",
                snapshot_prefix,
                "key-id",
                "secret-key",
            ),
            (
                "release-metadata.json",
                "private-backups",
                snapshot_prefix,
                "key-id",
                "secret-key",
            ),
            (
                "promotion-verification.json",
                "private-backups",
                snapshot_prefix,
                "key-id",
                "secret-key",
            ),
        ]
        assert Path(artifact.local_path).exists()
        assert artifact.remote_bucket_name == "private-backups"
        assert artifact.remote_endpoint_url == "https://example.invalid"
        assert artifact.remote_region_name == "auto"
        assert snapshot.status == BackupSnapshot.STATUS_READY
        assert snapshot.child_descriptors_json["database"]["remote_key"] == (
            artifact.remote_key
        )
        for descriptor in snapshot.child_descriptors_json["sidecars"].values():
            assert descriptor["remote_key"].startswith(snapshot_prefix)
        assert not hasattr(artifact, "remote_access_key_id")
        assert not hasattr(artifact, "remote_secret_access_key")

    def test_create_backup_marks_remote_upload_failure_and_preserves_local_dump_for_resume(
        self,
        superuser: AbstractBaseUser,
        local_backup_settings: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("TEST_BACKUPS_ACCESS_KEY", "key-id")
        monkeypatch.setenv("TEST_BACKUPS_SECRET_KEY", "secret-key")
        policy = BackupPolicySnapshot(
            retention_days=14,
            naming_prefix="db",
            target_mode=BackupPolicy.TARGET_MODE_PRIVATE_REMOTE,
            local_directory=str(local_backup_settings),
            remote_bucket_name="private-backups",
            remote_prefix="ops/backups",
            remote_endpoint_url="https://example.invalid",
            remote_region_name="auto",
            remote_access_key_id_env_var="TEST_BACKUPS_ACCESS_KEY",
            remote_secret_access_key_env_var="TEST_BACKUPS_SECRET_KEY",
            automation_enabled=False,
            schedule="0 2 * * *",
        )

        def failing_uploader(
            local_path: Path, resolved_policy: BackupPolicySnapshot
        ) -> str:
            del local_path, resolved_policy
            raise RuntimeError("upload exploded")

        with pytest.raises(BackupError, match="Private remote upload failed"):
            create_backup(
                initiated_by=superuser,
                trigger="admin",
                policy=policy,
                remote_uploader=cast(RemoteUploader, failing_uploader),
            )

        artifact = BackupArtifact.objects.get()
        snapshot = BackupSnapshot.objects.get()
        assert artifact.status == BackupArtifact.STATUS_FAILED
        assert artifact.remote_key == ""
        assert artifact.local_path
        assert Path(artifact.local_path).exists()
        assert "remote upload failed" in artifact.validation_notes
        assert snapshot.status == BackupSnapshot.STATUS_FAILED
        assert "database dump remote upload failed" in snapshot.failure_note
        assert snapshot.child_descriptors_json["database"]["status"] == (
            BackupSnapshot.STATUS_FAILED
        )
        assert Path(snapshot.local_root_path).exists()

    def test_create_backup_resume_retries_private_remote_upload_on_same_snapshot(
        self,
        superuser: AbstractBaseUser,
        local_backup_settings: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("TEST_BACKUPS_ACCESS_KEY", "key-id")
        monkeypatch.setenv("TEST_BACKUPS_SECRET_KEY", "secret-key")
        policy = BackupPolicySnapshot(
            retention_days=14,
            naming_prefix="db",
            target_mode=BackupPolicy.TARGET_MODE_PRIVATE_REMOTE,
            local_directory=str(local_backup_settings),
            remote_bucket_name="private-backups",
            remote_prefix="ops/backups",
            remote_endpoint_url="https://example.invalid",
            remote_region_name="auto",
            remote_access_key_id_env_var="TEST_BACKUPS_ACCESS_KEY",
            remote_secret_access_key_env_var="TEST_BACKUPS_SECRET_KEY",
            automation_enabled=False,
            schedule="0 2 * * *",
        )

        def failing_uploader(
            local_path: Path, resolved_policy: BackupPolicySnapshot
        ) -> str:
            del local_path, resolved_policy
            raise RuntimeError("upload exploded")

        with pytest.raises(BackupError, match="Private remote upload failed"):
            create_backup(
                initiated_by=superuser,
                trigger="admin",
                policy=policy,
                remote_uploader=cast(RemoteUploader, failing_uploader),
            )

        snapshot = BackupSnapshot.objects.get()
        failed_artifact = snapshot.authoritative_dump
        assert failed_artifact is not None
        original_artifact_id = failed_artifact.pk
        uploaded: list[tuple[str, str]] = []

        def successful_uploader(
            local_path: Path, resolved_policy: BackupPolicySnapshot
        ) -> str:
            uploaded.append((local_path.name, resolved_policy.remote_prefix))
            return f"{resolved_policy.remote_prefix}/{local_path.name}"

        artifact = create_backup(
            initiated_by=superuser,
            trigger="admin",
            policy=policy,
            remote_uploader=cast(RemoteUploader, successful_uploader),
            resume_snapshot_id=snapshot.snapshot_id,
        )

        snapshot.refresh_from_db()
        artifact.refresh_from_db()
        snapshot_prefix = f"ops/backups/snapshots/{snapshot.snapshot_id}"

        assert artifact.pk == original_artifact_id
        assert snapshot.status == BackupSnapshot.STATUS_READY
        assert snapshot.failure_note == ""
        assert artifact.remote_key == f"{snapshot_prefix}/database/{artifact.filename}"
        assert artifact.status == BackupArtifact.STATUS_READY
        assert BackupSnapshot.objects.count() == 1
        assert BackupArtifact.objects.count() == 1
        assert uploaded == [
            (artifact.filename, f"{snapshot_prefix}/database"),
            ("media-sync-manifest.json", snapshot_prefix),
            ("env-var-manifest.json", snapshot_prefix),
            ("release-metadata.json", snapshot_prefix),
            ("promotion-verification.json", snapshot_prefix),
        ]

    def test_create_backup_resume_uses_persisted_remote_location_after_settings_drift(
        self,
        superuser: AbstractBaseUser,
        local_backup_settings: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("TEST_BACKUPS_ACCESS_KEY", "key-id")
        monkeypatch.setenv("TEST_BACKUPS_SECRET_KEY", "secret-key")
        base_remote_settings = {
            "QUICKSCALE_BACKUPS_TARGET_MODE": BackupPolicy.TARGET_MODE_PRIVATE_REMOTE,
            "QUICKSCALE_BACKUPS_LOCAL_DIRECTORY": str(local_backup_settings),
            "QUICKSCALE_BACKUPS_REMOTE_PREFIX": "ops/backups",
            "QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR": (
                "TEST_BACKUPS_ACCESS_KEY"
            ),
            "QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR": (
                "TEST_BACKUPS_SECRET_KEY"
            ),
        }
        initial_remote_settings = {
            **base_remote_settings,
            "QUICKSCALE_BACKUPS_REMOTE_BUCKET_NAME": "original-bucket",
            "QUICKSCALE_BACKUPS_REMOTE_ENDPOINT_URL": (
                "https://original.example.invalid"
            ),
            "QUICKSCALE_BACKUPS_REMOTE_REGION_NAME": "original-region",
        }
        drifted_remote_settings = {
            **base_remote_settings,
            "QUICKSCALE_BACKUPS_REMOTE_BUCKET_NAME": "drifted-bucket",
            "QUICKSCALE_BACKUPS_REMOTE_ENDPOINT_URL": (
                "https://drifted.example.invalid"
            ),
            "QUICKSCALE_BACKUPS_REMOTE_REGION_NAME": "drifted-region",
        }

        def failing_uploader(
            local_path: Path, resolved_policy: BackupPolicySnapshot
        ) -> str:
            del local_path, resolved_policy
            raise RuntimeError("upload exploded")

        with override_settings(**initial_remote_settings):
            with pytest.raises(BackupError, match="Private remote upload failed"):
                create_backup(
                    initiated_by=superuser,
                    trigger="admin",
                    remote_uploader=cast(RemoteUploader, failing_uploader),
                )

        snapshot = BackupSnapshot.objects.get()
        failed_artifact = snapshot.authoritative_dump
        assert failed_artifact is not None
        assert failed_artifact.remote_bucket_name == "original-bucket"
        assert failed_artifact.remote_endpoint_url == "https://original.example.invalid"
        assert failed_artifact.remote_region_name == "original-region"

        uploaded: list[tuple[str, str, str, str, str]] = []

        def successful_uploader(
            local_path: Path, resolved_policy: BackupPolicySnapshot
        ) -> str:
            uploaded.append(
                (
                    local_path.name,
                    resolved_policy.remote_bucket_name,
                    resolved_policy.remote_endpoint_url,
                    resolved_policy.remote_region_name,
                    resolved_policy.remote_prefix,
                )
            )
            return f"{resolved_policy.remote_prefix}/{local_path.name}"

        with override_settings(**drifted_remote_settings):
            artifact = create_backup(
                initiated_by=superuser,
                trigger="admin",
                remote_uploader=cast(RemoteUploader, successful_uploader),
                resume_snapshot_id=snapshot.snapshot_id,
            )

        snapshot.refresh_from_db()
        artifact.refresh_from_db()
        snapshot_prefix = f"ops/backups/snapshots/{snapshot.snapshot_id}"

        assert uploaded == [
            (
                artifact.filename,
                "original-bucket",
                "https://original.example.invalid",
                "original-region",
                f"{snapshot_prefix}/database",
            ),
            (
                "media-sync-manifest.json",
                "original-bucket",
                "https://original.example.invalid",
                "original-region",
                snapshot_prefix,
            ),
            (
                "env-var-manifest.json",
                "original-bucket",
                "https://original.example.invalid",
                "original-region",
                snapshot_prefix,
            ),
            (
                "release-metadata.json",
                "original-bucket",
                "https://original.example.invalid",
                "original-region",
                snapshot_prefix,
            ),
            (
                "promotion-verification.json",
                "original-bucket",
                "https://original.example.invalid",
                "original-region",
                snapshot_prefix,
            ),
        ]
        assert artifact.remote_bucket_name == "original-bucket"
        assert artifact.remote_endpoint_url == "https://original.example.invalid"
        assert artifact.remote_region_name == "original-region"

    def test_create_backup_resume_rejects_missing_authoritative_dump_file(
        self,
        superuser: AbstractBaseUser,
        local_backup_settings: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("TEST_BACKUPS_ACCESS_KEY", "key-id")
        monkeypatch.setenv("TEST_BACKUPS_SECRET_KEY", "secret-key")
        policy = BackupPolicySnapshot(
            retention_days=14,
            naming_prefix="db",
            target_mode=BackupPolicy.TARGET_MODE_PRIVATE_REMOTE,
            local_directory=str(local_backup_settings),
            remote_bucket_name="private-backups",
            remote_prefix="ops/backups",
            remote_endpoint_url="https://example.invalid",
            remote_region_name="auto",
            remote_access_key_id_env_var="TEST_BACKUPS_ACCESS_KEY",
            remote_secret_access_key_env_var="TEST_BACKUPS_SECRET_KEY",
            automation_enabled=False,
            schedule="0 2 * * *",
        )

        def failing_uploader(
            local_path: Path, resolved_policy: BackupPolicySnapshot
        ) -> str:
            del local_path, resolved_policy
            raise RuntimeError("upload exploded")

        with pytest.raises(BackupError, match="Private remote upload failed"):
            create_backup(
                initiated_by=superuser,
                trigger="admin",
                policy=policy,
                remote_uploader=cast(RemoteUploader, failing_uploader),
            )

        snapshot = BackupSnapshot.objects.get()
        artifact = snapshot.authoritative_dump
        assert artifact is not None
        Path(artifact.local_path).unlink()

        with pytest.raises(
            BackupError,
            match="original authoritative dump file is missing",
        ):
            create_backup(
                initiated_by=superuser,
                trigger="admin",
                policy=policy,
                resume_snapshot_id=snapshot.snapshot_id,
            )

    def test_create_backup_rolls_back_uploaded_remote_object_when_remote_key_save_fails(
        self,
        superuser: AbstractBaseUser,
        local_backup_settings: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("TEST_BACKUPS_ACCESS_KEY", "key-id")
        monkeypatch.setenv("TEST_BACKUPS_SECRET_KEY", "secret-key")
        policy = BackupPolicySnapshot(
            retention_days=14,
            naming_prefix="db",
            target_mode=BackupPolicy.TARGET_MODE_PRIVATE_REMOTE,
            local_directory=str(local_backup_settings),
            remote_bucket_name="private-backups",
            remote_prefix="ops/backups",
            remote_endpoint_url="https://example.invalid",
            remote_region_name="auto",
            remote_access_key_id_env_var="TEST_BACKUPS_ACCESS_KEY",
            remote_secret_access_key_env_var="TEST_BACKUPS_SECRET_KEY",
            automation_enabled=False,
            schedule="0 2 * * *",
        )
        deleted_remote_keys: list[tuple[str, str]] = []

        def fake_uploader(
            local_path: Path, resolved_policy: BackupPolicySnapshot
        ) -> str:
            return f"{resolved_policy.remote_prefix}/{local_path.name}"

        def fake_remote_deleter(
            remote_key: str,
            resolved_policy: BackupPolicySnapshot,
        ) -> None:
            deleted_remote_keys.append((remote_key, resolved_policy.remote_bucket_name))

        original_save = BackupArtifact.save

        def failing_save(self: BackupArtifact, *args: Any, **kwargs: Any) -> None:
            if kwargs.get("update_fields") == ["remote_key", "updated_at"]:
                raise RuntimeError("db save exploded")
            original_save(self, *args, **kwargs)

        monkeypatch.setattr(BackupArtifact, "save", failing_save)

        with pytest.raises(
            BackupError,
            match="Private remote metadata persistence failed",
        ) as exc_info:
            create_backup(
                initiated_by=superuser,
                trigger="admin",
                policy=policy,
                remote_uploader=cast(RemoteUploader, fake_uploader),
                remote_deleter=cast(RemoteDeleter, fake_remote_deleter),
            )

        artifact = BackupArtifact.objects.get()
        snapshot = BackupSnapshot.objects.get()
        expected_remote_key = (
            f"ops/backups/snapshots/{snapshot.snapshot_id}/database/{artifact.filename}"
        )

        assert deleted_remote_keys == [(expected_remote_key, "private-backups")]
        assert artifact.remote_key == ""
        assert artifact.local_path
        assert Path(artifact.local_path).exists()
        assert snapshot.status == BackupSnapshot.STATUS_FAILED
        assert f"'{artifact.filename}'" not in str(exc_info.value)
        assert expected_remote_key in str(exc_info.value)

    def test_create_backup_keeps_successful_artifact_when_prune_fails(
        self,
        superuser: AbstractBaseUser,
        backup_policy: BackupPolicy,
        local_backup_settings: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        backup_policy.local_directory = str(local_backup_settings)
        backup_policy.save(update_fields=["local_directory", "updated_at"])

        def failing_prune(**kwargs: object) -> int:
            del kwargs
            raise BackupError("prune exploded")

        monkeypatch.setattr(
            backup_services,
            "prune_expired_backups",
            failing_prune,
        )

        artifact = create_backup(initiated_by=superuser, trigger="manual")

        artifact.refresh_from_db()
        assert artifact.status == BackupArtifact.STATUS_READY
        assert Path(artifact.local_path).exists()
        assert "prune failed after backup creation" in artifact.validation_notes
        assert artifact.metadata_json["prune_error"] == "prune exploded"

    def test_create_backup_marks_snapshot_failed_when_sidecar_capture_fails_but_keeps_dump_artifact(
        self,
        superuser: AbstractBaseUser,
        backup_policy: BackupPolicy,
        local_backup_settings: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        backup_policy.local_directory = str(local_backup_settings)
        backup_policy.save(update_fields=["local_directory", "updated_at"])

        def failing_release_metadata(*, captured_at: datetime) -> dict[str, Any]:
            del captured_at
            raise BackupError("release metadata exploded")

        monkeypatch.setattr(
            backup_services,
            "_build_release_metadata",
            failing_release_metadata,
        )

        artifact = create_backup(initiated_by=superuser, trigger="manual")

        snapshot = _get_authoritative_snapshot(artifact)
        snapshot_root = Path(snapshot.local_root_path)
        artifact.refresh_from_db()
        snapshot.refresh_from_db()

        assert snapshot is not None
        assert artifact.status == BackupArtifact.STATUS_READY
        assert Path(artifact.local_path).exists()
        assert snapshot.status == BackupSnapshot.STATUS_FAILED
        assert "release-metadata.json" in snapshot.failure_note
        assert "release metadata exploded" in snapshot.failure_note
        assert artifact.metadata_json["snapshot_status"] == BackupSnapshot.STATUS_FAILED
        assert "snapshot sidecar capture failed" in artifact.validation_notes
        assert not (snapshot_root / "release-metadata.json").exists()
        assert (snapshot_root / "env-var-manifest.json").exists()

    def test_create_backup_resume_recaptures_failed_sidecars_on_same_snapshot(
        self,
        superuser: AbstractBaseUser,
        backup_policy: BackupPolicy,
        local_backup_settings: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        backup_policy.local_directory = str(local_backup_settings)
        backup_policy.save(update_fields=["local_directory", "updated_at"])
        original_builder = backup_services._build_release_metadata
        call_count = 0

        def flaky_release_metadata(*, captured_at: datetime) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise BackupError("release metadata exploded")
            return original_builder(captured_at=captured_at)

        monkeypatch.setattr(
            backup_services,
            "_build_release_metadata",
            flaky_release_metadata,
        )

        artifact = create_backup(initiated_by=superuser, trigger="manual")

        snapshot = _get_authoritative_snapshot(artifact)
        original_artifact_id = artifact.pk
        assert snapshot is not None
        assert snapshot.status == BackupSnapshot.STATUS_FAILED

        resumed_artifact = create_backup(
            initiated_by=superuser,
            trigger="manual",
            resume_snapshot_id=snapshot.snapshot_id,
        )

        snapshot.refresh_from_db()
        resumed_artifact.refresh_from_db()
        assert resumed_artifact.pk == original_artifact_id
        assert snapshot.status == BackupSnapshot.STATUS_READY
        assert snapshot.failure_note == ""
        assert not resumed_artifact.validation_notes
        assert (Path(snapshot.local_root_path) / "release-metadata.json").exists()

    def test_create_backup_cleans_partial_file_when_dump_generation_fails(
        self,
        superuser: AbstractBaseUser,
        local_backup_settings: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        policy = BackupPolicySnapshot(
            retention_days=14,
            naming_prefix="db",
            target_mode=BackupPolicy.TARGET_MODE_LOCAL,
            local_directory=str(local_backup_settings),
            remote_bucket_name="",
            remote_prefix="backups/private",
            remote_endpoint_url="",
            remote_region_name="",
            remote_access_key_id_env_var="",
            remote_secret_access_key_env_var="",
            automation_enabled=False,
            schedule="0 2 * * *",
        )
        _set_postgresql_default_connection(monkeypatch)
        _mock_postgresql_18_contract(monkeypatch)

        def failing_runner(
            command: list[str], *, env: dict[str, str] | None = None
        ) -> None:
            del env
            local_path = Path(command[command.index("--file") + 1])
            local_path.write_bytes(b"partial dump")
            raise BackupError("pg_dump exploded")

        with pytest.raises(BackupError, match="pg_dump exploded"):
            create_backup(
                initiated_by=superuser,
                trigger="manual",
                policy=policy,
                shell_runner=cast(ShellCommandRunner, failing_runner),
            )

        assert BackupArtifact.objects.count() == 0
        snapshot = BackupSnapshot.objects.get()
        assert snapshot.status == BackupSnapshot.STATUS_FAILED
        assert not any(path.is_file() for path in local_backup_settings.rglob("*"))

    @override_settings(DEBUG=True)
    def test_create_backup_reports_missing_pg_dump_as_backup_error_in_debug(
        self,
        superuser: AbstractBaseUser,
        local_backup_settings: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        policy = BackupPolicySnapshot(
            retention_days=14,
            naming_prefix="db",
            target_mode=BackupPolicy.TARGET_MODE_LOCAL,
            local_directory=str(local_backup_settings),
            remote_bucket_name="",
            remote_prefix="backups/private",
            remote_endpoint_url="",
            remote_region_name="",
            remote_access_key_id_env_var="",
            remote_secret_access_key_env_var="",
            automation_enabled=False,
            schedule="0 2 * * *",
        )
        _set_postgresql_default_connection(monkeypatch)

        def fake_get_database_server_version(_engine: str) -> str:
            return "18.3 (Debian 18.3-1)"

        monkeypatch.setattr(
            backup_services,
            "_get_database_server_version",
            fake_get_database_server_version,
        )

        def missing_pg_dump(*args: Any, **kwargs: Any) -> None:
            del args, kwargs
            raise FileNotFoundError("pg_dump")

        monkeypatch.setattr(backup_services.subprocess, "run", missing_pg_dump)

        with pytest.raises(
            BackupError,
            match="Required executable 'pg_dump' is not installed in this runtime",
        ) as exc_info:
            create_backup(
                initiated_by=superuser,
                trigger="manual",
                policy=policy,
            )

        assert "PGDG apt repository" in str(exc_info.value)
        assert "postgresql-client-18" in str(exc_info.value)
        assert BackupArtifact.objects.count() == 0
        snapshot = BackupSnapshot.objects.get()
        assert snapshot.status == BackupSnapshot.STATUS_FAILED
        assert not any(path.is_file() for path in local_backup_settings.rglob("*"))

    @override_settings(DEBUG=True)
    def test_create_backup_rejects_non_18_postgresql_server_in_debug(
        self,
        superuser: AbstractBaseUser,
        local_backup_settings: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        policy = BackupPolicySnapshot(
            retention_days=14,
            naming_prefix="db",
            target_mode=BackupPolicy.TARGET_MODE_LOCAL,
            local_directory=str(local_backup_settings),
            remote_bucket_name="",
            remote_prefix="backups/private",
            remote_endpoint_url="",
            remote_region_name="",
            remote_access_key_id_env_var="",
            remote_secret_access_key_env_var="",
            automation_enabled=False,
            schedule="0 2 * * *",
        )
        _set_postgresql_default_connection(monkeypatch)
        _mock_postgresql_18_contract(
            monkeypatch,
            server_version="17.9 (Debian 17.9-1)",
        )

        with pytest.raises(
            BackupError,
            match="requires a PostgreSQL 18 server",
        ):
            create_backup(
                initiated_by=superuser,
                trigger="manual",
                policy=policy,
            )

        assert BackupArtifact.objects.count() == 0
        snapshot = BackupSnapshot.objects.get()
        assert snapshot.status == BackupSnapshot.STATUS_FAILED
        assert not any(path.is_file() for path in local_backup_settings.rglob("*"))

    @override_settings(DEBUG=False)
    def test_create_backup_rejects_non_18_pg_dump_tooling_outside_debug(
        self,
        superuser: AbstractBaseUser,
        local_backup_settings: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        policy = BackupPolicySnapshot(
            retention_days=14,
            naming_prefix="db",
            target_mode=BackupPolicy.TARGET_MODE_LOCAL,
            local_directory=str(local_backup_settings),
            remote_bucket_name="",
            remote_prefix="backups/private",
            remote_endpoint_url="",
            remote_region_name="",
            remote_access_key_id_env_var="",
            remote_secret_access_key_env_var="",
            automation_enabled=False,
            schedule="0 2 * * *",
        )
        _set_postgresql_default_connection(monkeypatch)
        _mock_postgresql_18_contract(
            monkeypatch,
            tool_versions={"pg_dump": "pg_dump (PostgreSQL) 17.9"},
        )

        with pytest.raises(
            BackupError,
            match="requires PostgreSQL 18 pg_dump tooling",
        ) as exc_info:
            create_backup(
                initiated_by=superuser,
                trigger="manual",
                policy=policy,
            )

        assert "postgresql-client-18" in str(exc_info.value)
        assert "quickscale apply does not rewrite user-owned files" in str(
            exc_info.value
        )
        assert BackupArtifact.objects.count() == 0
        snapshot = BackupSnapshot.objects.get()
        assert snapshot.status == BackupSnapshot.STATUS_FAILED
        assert not any(path.is_file() for path in local_backup_settings.rglob("*"))

    @override_settings(DEBUG=False)
    def test_create_backup_reports_missing_pg_dump_as_backup_error_on_railway(
        self,
        superuser: AbstractBaseUser,
        local_backup_settings: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        policy = BackupPolicySnapshot(
            retention_days=14,
            naming_prefix="db",
            target_mode=BackupPolicy.TARGET_MODE_LOCAL,
            local_directory=str(local_backup_settings),
            remote_bucket_name="",
            remote_prefix="backups/private",
            remote_endpoint_url="",
            remote_region_name="",
            remote_access_key_id_env_var="",
            remote_secret_access_key_env_var="",
            automation_enabled=False,
            schedule="0 2 * * *",
        )
        _set_postgresql_default_connection(monkeypatch)

        def fake_get_database_server_version(_engine: str) -> str:
            return "18.3 (Debian 18.3-1)"

        monkeypatch.setattr(
            backup_services,
            "_get_database_server_version",
            fake_get_database_server_version,
        )
        monkeypatch.setenv("RAILWAY_ENVIRONMENT_ID", "env-local-test")

        def missing_pg_dump(*args: Any, **kwargs: Any) -> None:
            del args, kwargs
            raise FileNotFoundError("pg_dump")

        monkeypatch.setattr(backup_services.subprocess, "run", missing_pg_dump)

        with pytest.raises(
            BackupError,
            match="Required executable 'pg_dump' is not installed in this runtime",
        ):
            create_backup(
                initiated_by=superuser,
                trigger="manual",
                policy=policy,
            )

        assert BackupArtifact.objects.count() == 0
        snapshot = BackupSnapshot.objects.get()
        assert snapshot.status == BackupSnapshot.STATUS_FAILED
        assert not any(path.is_file() for path in local_backup_settings.rglob("*"))

    @override_settings(DEBUG=False)
    def test_create_backup_reports_missing_pg_dump_as_backup_error_outside_debug(
        self,
        superuser: AbstractBaseUser,
        local_backup_settings: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        policy = BackupPolicySnapshot(
            retention_days=14,
            naming_prefix="db",
            target_mode=BackupPolicy.TARGET_MODE_LOCAL,
            local_directory=str(local_backup_settings),
            remote_bucket_name="",
            remote_prefix="backups/private",
            remote_endpoint_url="",
            remote_region_name="",
            remote_access_key_id_env_var="",
            remote_secret_access_key_env_var="",
            automation_enabled=False,
            schedule="0 2 * * *",
        )
        _set_postgresql_default_connection(monkeypatch)

        def fake_get_database_server_version(_engine: str) -> str:
            return "18.3 (Debian 18.3-1)"

        monkeypatch.setattr(
            backup_services,
            "_get_database_server_version",
            fake_get_database_server_version,
        )

        def missing_pg_dump(*args: Any, **kwargs: Any) -> None:
            del args, kwargs
            raise FileNotFoundError("pg_dump")

        monkeypatch.setattr(backup_services.subprocess, "run", missing_pg_dump)

        with pytest.raises(
            BackupError,
            match="Required executable 'pg_dump' is not installed in this runtime",
        ):
            create_backup(
                initiated_by=superuser,
                trigger="manual",
                policy=policy,
            )

        assert BackupArtifact.objects.count() == 0
        snapshot = BackupSnapshot.objects.get()
        assert snapshot.status == BackupSnapshot.STATUS_FAILED
        assert not any(path.is_file() for path in local_backup_settings.rglob("*"))

    def test_create_backup_rejects_existing_filesystem_lock(
        self,
        superuser: AbstractBaseUser,
        backup_policy: BackupPolicy,
        local_backup_settings: Path,
    ) -> None:
        backup_policy.local_directory = str(local_backup_settings)
        backup_policy.save(update_fields=["local_directory", "updated_at"])
        local_backup_settings.mkdir(parents=True, exist_ok=True)
        (local_backup_settings / ".quickscale-backup-create.lock").write_text(
            "{}",
            encoding="utf-8",
        )

        with pytest.raises(BackupLockError):
            create_backup(initiated_by=superuser, trigger="scheduled")

    def test_create_backup_rejects_invalid_remote_policy(
        self,
        superuser: AbstractBaseUser,
    ) -> None:
        policy = BackupPolicySnapshot(
            retention_days=14,
            naming_prefix="db",
            target_mode=BackupPolicy.TARGET_MODE_PRIVATE_REMOTE,
            local_directory=".quickscale/backups",
            remote_bucket_name="",
            remote_prefix="ops/backups",
            remote_endpoint_url="",
            remote_region_name="",
            remote_access_key_id_env_var="",
            remote_secret_access_key_env_var="",
            automation_enabled=False,
            schedule="0 2 * * *",
        )

        with pytest.raises(BackupConfigurationError):
            create_backup(initiated_by=superuser, policy=policy)

    def test_validate_backup_artifact_detects_checksum_mismatch(
        self,
        backup_artifact: BackupArtifact,
        artifact_file: Path,
    ) -> None:
        artifact_file.write_text("[1, 2, 3]", encoding="utf-8")

        issues = validate_backup_artifact(backup_artifact)

        assert "checksum mismatch detected" in issues
        backup_artifact.refresh_from_db()
        assert backup_artifact.status == BackupArtifact.STATUS_FAILED

    def test_validate_backup_artifact_detects_invalid_json_payload(
        self,
        backup_artifact: BackupArtifact,
        artifact_file: Path,
    ) -> None:
        artifact_file.write_text("{not-json", encoding="utf-8")
        backup_artifact.checksum_sha256 = hashlib.sha256(
            artifact_file.read_bytes()
        ).hexdigest()
        backup_artifact.size_bytes = artifact_file.stat().st_size
        backup_artifact.save(
            update_fields=["checksum_sha256", "size_bytes", "updated_at"]
        )

        issues = validate_backup_artifact(backup_artifact)

        assert issues == ["json backup payload is not valid JSON"]
        backup_artifact.refresh_from_db()
        assert backup_artifact.status == BackupArtifact.STATUS_FAILED

    def test_validate_backup_artifact_detects_corrupt_json_bytes(
        self,
        backup_artifact: BackupArtifact,
        artifact_file: Path,
    ) -> None:
        artifact_file.write_bytes(b"\xff\xfe\x00\x81")
        backup_artifact.checksum_sha256 = hashlib.sha256(
            artifact_file.read_bytes()
        ).hexdigest()
        backup_artifact.size_bytes = artifact_file.stat().st_size
        backup_artifact.save(
            update_fields=["checksum_sha256", "size_bytes", "updated_at"]
        )

        issues = validate_backup_artifact(backup_artifact)

        assert issues == ["json backup payload is not valid JSON"]
        backup_artifact.refresh_from_db()
        assert backup_artifact.status == BackupArtifact.STATUS_FAILED

    def test_prune_expired_backups_deletes_old_local_files(
        self,
        db: Any,
        superuser: AbstractBaseUser,
        tmp_path: Path,
    ) -> None:
        del db
        local_path = tmp_path / "old-backup.json"
        local_path.write_text("[]", encoding="utf-8")
        checksum = hashlib.sha256(local_path.read_bytes()).hexdigest()
        artifact = BackupArtifact.objects.create(
            filename=local_path.name,
            local_path=str(local_path),
            checksum_sha256=checksum,
            size_bytes=local_path.stat().st_size,
            backup_format="json",
            database_engine="django.db.backends.sqlite3",
            database_name="test.sqlite3",
            metadata_json={},
            initiated_by=superuser,
        )
        BackupArtifact.objects.filter(pk=artifact.pk).update(
            created_at=datetime.now(timezone.utc) - timedelta(days=30)
        )

        deleted_count = prune_expired_backups(
            policy=BackupPolicySnapshot.from_settings(),
            now=datetime.now(timezone.utc),
        )

        assert deleted_count >= 1
        artifact.refresh_from_db()
        assert artifact.status == BackupArtifact.STATUS_DELETED
        assert not local_path.exists()

    def test_prune_expired_backups_uses_artifact_location_and_current_credentials(
        self,
        superuser: AbstractBaseUser,
        local_backup_settings: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("ORIGINAL_BACKUPS_ACCESS_KEY", "original-key")
        monkeypatch.setenv("ORIGINAL_BACKUPS_SECRET_KEY", "original-secret")
        original_policy = BackupPolicySnapshot(
            retention_days=14,
            naming_prefix="db",
            target_mode=BackupPolicy.TARGET_MODE_PRIVATE_REMOTE,
            local_directory=str(local_backup_settings),
            remote_bucket_name="original-bucket",
            remote_prefix="ops/backups",
            remote_endpoint_url="https://original.example.invalid",
            remote_region_name="auto",
            remote_access_key_id_env_var="ORIGINAL_BACKUPS_ACCESS_KEY",
            remote_secret_access_key_env_var="ORIGINAL_BACKUPS_SECRET_KEY",
            automation_enabled=False,
            schedule="0 2 * * *",
        )
        remote_uploader = cast(
            RemoteUploader,
            lambda local_path, resolved_policy: (  # noqa: ARG005
                f"ops/backups/{local_path.name}"
            ),
        )

        artifact = create_backup(
            initiated_by=superuser,
            trigger="scheduled",
            policy=original_policy,
            remote_uploader=remote_uploader,
        )
        snapshot = _get_authoritative_snapshot(artifact)
        assert snapshot is not None
        BackupArtifact.objects.filter(pk=artifact.pk).update(
            created_at=datetime.now(timezone.utc) - timedelta(days=30)
        )
        BackupSnapshot.objects.filter(pk=snapshot.pk).update(
            created_at=datetime.now(timezone.utc) - timedelta(days=30)
        )

        monkeypatch.setenv("CURRENT_BACKUPS_ACCESS_KEY", "current-key")
        monkeypatch.setenv("CURRENT_BACKUPS_SECRET_KEY", "current-secret")
        deletion_calls: list[tuple[str, str, str, str, str, str]] = []
        current_policy = BackupPolicySnapshot(
            retention_days=1,
            naming_prefix="db",
            target_mode=BackupPolicy.TARGET_MODE_PRIVATE_REMOTE,
            local_directory=str(local_backup_settings),
            remote_bucket_name="current-bucket",
            remote_prefix="changed/prefix",
            remote_endpoint_url="https://current.example.invalid",
            remote_region_name="us-east-1",
            remote_access_key_id_env_var="CURRENT_BACKUPS_ACCESS_KEY",
            remote_secret_access_key_env_var="CURRENT_BACKUPS_SECRET_KEY",
            automation_enabled=False,
            schedule="0 2 * * *",
        )

        def fake_remote_deleter(
            remote_key: str,
            resolved_policy: BackupPolicySnapshot,
        ) -> None:
            deletion_calls.append(
                (
                    remote_key,
                    resolved_policy.remote_bucket_name,
                    resolved_policy.remote_endpoint_url,
                    resolved_policy.remote_region_name,
                    resolved_policy.resolve_remote_access_key_id(),
                    resolved_policy.resolve_remote_secret_access_key(),
                )
            )

        deleted_count = prune_expired_backups(
            policy=current_policy,
            now=datetime.now(timezone.utc),
            remote_deleter=cast(RemoteDeleter, fake_remote_deleter),
        )

        expected_remote_keys = {
            artifact.remote_key,
            *{
                str(descriptor["remote_key"])
                for descriptor in snapshot.child_descriptors_json["sidecars"].values()
            },
        }

        assert deleted_count == 1
        assert {
            (
                remote_key,
                bucket_name,
                endpoint_url,
                region_name,
                access_key,
                secret_key,
            )
            for (
                remote_key,
                bucket_name,
                endpoint_url,
                region_name,
                access_key,
                secret_key,
            ) in deletion_calls
        } == {
            (
                remote_key,
                "original-bucket",
                "https://original.example.invalid",
                "auto",
                "current-key",
                "current-secret",
            )
            for remote_key in expected_remote_keys
        }

    def test_prune_expired_backups_skips_snapshot_with_active_rollback_pin(
        self,
        superuser: AbstractBaseUser,
        backup_policy: BackupPolicy,
        local_backup_settings: Path,
    ) -> None:
        backup_policy.local_directory = str(local_backup_settings)
        backup_policy.save(update_fields=["local_directory", "updated_at"])

        artifact = create_backup(initiated_by=superuser, trigger="manual")
        snapshot = _get_authoritative_snapshot(artifact)
        assert snapshot is not None

        expired_created_at = datetime.now(timezone.utc) - timedelta(days=30)
        BackupSnapshot.objects.filter(pk=snapshot.pk).update(
            created_at=expired_created_at,
            rollback_pin_expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
            rollback_pin_reason="production rollback window",
        )

        deleted_count = prune_expired_backups(
            policy=BackupPolicySnapshot.from_settings(),
            now=datetime.now(timezone.utc),
        )

        artifact.refresh_from_db()
        snapshot.refresh_from_db()
        assert deleted_count == 0
        assert snapshot.status == BackupSnapshot.STATUS_READY
        assert Path(artifact.local_path).exists()

        BackupSnapshot.objects.filter(pk=snapshot.pk).update(
            rollback_pin_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )

        deleted_count = prune_expired_backups(
            policy=BackupPolicySnapshot.from_settings(),
            now=datetime.now(timezone.utc),
        )

        artifact.refresh_from_db()
        snapshot.refresh_from_db()
        assert deleted_count == 1
        assert snapshot.status == BackupSnapshot.STATUS_DELETED
        assert artifact.status == BackupArtifact.STATUS_DELETED
        assert not Path(snapshot.local_root_path).exists()

    def test_report_backup_snapshot_returns_structured_snapshot_view(
        self,
        superuser: AbstractBaseUser,
        backup_policy: BackupPolicy,
        local_backup_settings: Path,
    ) -> None:
        backup_policy.local_directory = str(local_backup_settings)
        backup_policy.save(update_fields=["local_directory", "updated_at"])

        artifact = create_backup(initiated_by=superuser, trigger="manual")
        snapshot = _get_authoritative_snapshot(artifact)

        report = report_backup_snapshot(snapshot.snapshot_id)

        assert snapshot is not None
        assert report["snapshot_id"] == snapshot.snapshot_id
        assert report["confirmation_value"] == artifact.filename
        assert report["authoritative_dump"]["artifact_id"] == artifact.pk
        assert (
            report["sidecar_summary"]["media-sync-manifest.json"]["manifest_status"]
            == "missing_media_root"
        )
        assert report["rollback_pin"]["active"] is False

    def test_report_backup_snapshot_uses_snapshot_full_backup_contract_not_artifact_metadata(
        self,
        superuser: AbstractBaseUser,
        backup_policy: BackupPolicy,
        local_backup_settings: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        backup_policy.local_directory = str(local_backup_settings)
        backup_policy.save(update_fields=["local_directory", "updated_at"])
        media_root = local_backup_settings.parent / "media-root"
        media_root.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(settings, "MEDIA_ROOT", str(media_root))

        artifact = create_backup(initiated_by=superuser, trigger="manual")
        snapshot = _get_authoritative_snapshot(artifact)
        artifact.metadata_json = {
            **artifact.metadata_json,
            "full_backup": {
                "status": "artifact-shadow",
                "provenance": {"source_environment": "tampered-env"},
            },
        }
        artifact.save(update_fields=["metadata_json", "updated_at"])

        report = report_backup_snapshot(snapshot.snapshot_id)

        assert report["full_backup"]["status"] == "complete"
        assert report["full_backup"]["completeness"]["status"] == "complete"
        assert report["full_backup"]["completeness"]["issues"] == []
        assert report["full_backup"]["provenance"]["status"] == "consistent"
        assert (
            report["full_backup"]["provenance"]["project_slug"]
            == local_backup_settings.parent.name
        )
        assert report["full_backup"]["provenance"]["source_environment"] == "local"
        assert (
            report["full_backup"]["provenance"]["authoritative_dump"]["artifact_id"]
            == artifact.pk
        )
        assert (
            report["full_backup"]["provenance"]["release"]["app_version"] == "test-app"
        )

    def test_set_and_clear_backup_snapshot_rollback_pin_update_snapshot_report(
        self,
        superuser: AbstractBaseUser,
        backup_policy: BackupPolicy,
        local_backup_settings: Path,
    ) -> None:
        backup_policy.local_directory = str(local_backup_settings)
        backup_policy.save(update_fields=["local_directory", "updated_at"])

        artifact = create_backup(initiated_by=superuser, trigger="manual")
        snapshot = _get_authoritative_snapshot(artifact)
        assert snapshot is not None

        pinned_report = set_backup_snapshot_rollback_pin(
            snapshot.snapshot_id,
            ttl_hours=6,
            reason="production rollback window",
        )

        snapshot.refresh_from_db()
        assert pinned_report["rollback_pin"]["active"] is True
        assert pinned_report["rollback_pin"]["reason"] == "production rollback window"
        assert snapshot.rollback_pin_expires_at is not None

        cleared_report = clear_backup_snapshot_rollback_pin(snapshot.snapshot_id)

        snapshot.refresh_from_db()
        assert cleared_report["rollback_pin"]["active"] is False
        assert cleared_report["rollback_pin"]["expires_at"] is None
        assert snapshot.rollback_pin_expires_at is None
        assert snapshot.rollback_pin_reason == ""

    def test_restore_snapshot_id_resolves_authoritative_dump(
        self,
        postgresql_backup_artifact: BackupArtifact,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _set_postgresql_default_connection(monkeypatch)
        _mock_postgresql_18_contract(monkeypatch)
        snapshot = BackupSnapshot.objects.create(
            snapshot_id="snap-restore-123",
            authoritative_dump=postgresql_backup_artifact,
            status=BackupSnapshot.STATUS_READY,
            source_environment="local",
            local_root_path=str(Path(postgresql_backup_artifact.local_path).parent),
            child_descriptors_json={
                "database": {
                    "kind": "database_dump",
                    "status": BackupSnapshot.STATUS_READY,
                    "relative_path": postgresql_backup_artifact.filename,
                },
                "sidecars": {},
            },
        )

        result = restore_backup_source(
            snapshot_id=snapshot.snapshot_id,
            confirmation=postgresql_backup_artifact.filename,
            dry_run=True,
        )

        assert result.executed is False
        assert result.dry_run is True

    def test_restore_admin_uploaded_backup_rejects_unmatched_upload(self) -> None:
        uploaded_file = SimpleUploadedFile(
            "unmatched.dump",
            b"PGDMP\x01\x0e\x00unmatched upload bytes",
        )

        with pytest.raises(
            BackupRestoreBlocked,
            match="does not match any recorded authoritative backup artifact",
        ):
            restore_admin_uploaded_backup(
                uploaded_file,
                confirmation="missing-authoritative.dump",
                dry_run=True,
            )

    def test_restore_admin_uploaded_backup_requires_complete_snapshot_contract(
        self,
        postgresql_backup_artifact: BackupArtifact,
        tmp_path: Path,
    ) -> None:
        snapshot = _attach_complete_snapshot_contract(
            postgresql_backup_artifact,
            tmp_path,
            snapshot_id="snap-admin-upload-incomplete",
        )
        (Path(snapshot.local_root_path) / "release-metadata.json").unlink()
        uploaded_file = SimpleUploadedFile(
            "operator-upload.dump",
            Path(postgresql_backup_artifact.local_path).read_bytes(),
        )

        with pytest.raises(
            BackupRestoreBlocked,
            match="full-backup contract",
        ):
            restore_admin_uploaded_backup(
                uploaded_file,
                confirmation=postgresql_backup_artifact.filename,
                dry_run=True,
            )

    def test_restore_admin_uploaded_backup_rejects_ambiguous_trusted_match(
        self,
        postgresql_backup_artifact: BackupArtifact,
        tmp_path: Path,
    ) -> None:
        original_payload = Path(postgresql_backup_artifact.local_path).read_bytes()
        _attach_complete_snapshot_contract(
            postgresql_backup_artifact,
            tmp_path,
            snapshot_id="snap-admin-upload-first",
        )

        duplicate_path = tmp_path / "duplicate-artifact.dump"
        duplicate_path.write_bytes(original_payload)
        duplicate_artifact = BackupArtifact.objects.create(
            filename="duplicate-artifact.dump",
            local_path=str(duplicate_path),
            checksum_sha256=hashlib.sha256(original_payload).hexdigest(),
            size_bytes=duplicate_path.stat().st_size,
            backup_format="pg_dump_custom",
            restore_scope=BackupArtifact.RESTORE_SCOPE_LOCAL_ONLY,
            database_engine=postgresql_backup_artifact.database_engine,
            database_name=postgresql_backup_artifact.database_name,
            database_server_major=postgresql_backup_artifact.database_server_major,
            dump_client_major=postgresql_backup_artifact.dump_client_major,
            metadata_json={"environment": "local"},
        )
        _attach_complete_snapshot_contract(
            duplicate_artifact,
            tmp_path,
            snapshot_id="snap-admin-upload-second",
        )

        uploaded_file = SimpleUploadedFile("duplicate-match.dump", original_payload)

        with pytest.raises(
            BackupRestoreBlocked,
            match="matches multiple trusted authoritative backup artifacts",
        ):
            restore_admin_uploaded_backup(
                uploaded_file,
                confirmation=postgresql_backup_artifact.filename,
                dry_run=True,
            )

    def test_restore_admin_uploaded_backup_routes_through_shared_restore_pipeline(
        self,
        postgresql_backup_artifact: BackupArtifact,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _attach_complete_snapshot_contract(
            postgresql_backup_artifact,
            tmp_path,
            snapshot_id="snap-admin-upload-success",
        )
        original_path = Path(postgresql_backup_artifact.local_path)
        staged_paths: list[Path] = []

        def fake_execute(
            restore_source: backup_services.ResolvedRestoreSource,
            *,
            confirmation: str,
            dry_run: bool,
            allow_production: bool,
            shell_runner: ShellCommandRunner | None,
        ) -> RestoreResult:
            staged_paths.append(restore_source.local_path)
            assert restore_source.artifact == postgresql_backup_artifact
            assert (
                restore_source.confirmation_value == postgresql_backup_artifact.filename
            )
            assert restore_source.local_path != original_path
            assert restore_source.local_path.exists()
            assert restore_source.local_path.read_bytes() == original_path.read_bytes()
            assert confirmation == postgresql_backup_artifact.filename
            assert dry_run is True
            assert allow_production is False
            assert shell_runner is None
            return RestoreResult(
                executed=False,
                dry_run=True,
                message="Restore validation completed successfully (dry run).",
            )

        monkeypatch.setattr(
            backup_services,
            "_execute_restore_for_resolved_source",
            fake_execute,
        )

        result = restore_admin_uploaded_backup(
            SimpleUploadedFile("operator-upload.dump", original_path.read_bytes()),
            confirmation=postgresql_backup_artifact.filename,
            dry_run=True,
        )

        assert result.executed is False
        assert result.dry_run is True
        assert staged_paths and not staged_paths[0].exists()

    def test_restore_admin_uploaded_backup_warns_when_quarantine_cleanup_fails(
        self,
        postgresql_backup_artifact: BackupArtifact,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _attach_complete_snapshot_contract(
            postgresql_backup_artifact,
            tmp_path,
            snapshot_id="snap-admin-upload-cleanup-warning",
        )
        original_path = Path(postgresql_backup_artifact.local_path)
        staged_paths: list[Path] = []

        def fake_execute(
            restore_source: backup_services.ResolvedRestoreSource,
            *,
            confirmation: str,
            dry_run: bool,
            allow_production: bool,
            shell_runner: ShellCommandRunner | None,
        ) -> RestoreResult:
            del confirmation, dry_run, allow_production, shell_runner
            staged_paths.append(restore_source.local_path)
            return RestoreResult(
                executed=False,
                dry_run=True,
                message="Restore validation completed successfully (dry run).",
            )

        def failing_rmtree(path: str | Path) -> None:
            del path
            raise OSError("device busy")

        original_rmtree = shutil.rmtree
        monkeypatch.setattr(
            backup_services,
            "_execute_restore_for_resolved_source",
            fake_execute,
        )
        monkeypatch.setattr(backup_services.shutil, "rmtree", failing_rmtree)

        result = restore_admin_uploaded_backup(
            SimpleUploadedFile("operator-upload.dump", original_path.read_bytes()),
            confirmation=postgresql_backup_artifact.filename,
            dry_run=True,
        )

        assert result.executed is False
        assert result.dry_run is True
        assert [warning.code for warning in result.warnings] == [
            "admin_restore_upload_cleanup_failed"
        ]
        assert result.warnings[0].details == {
            "staging_directory": str(staged_paths[0].parent),
            "error": "device busy",
        }
        original_rmtree(staged_paths[0].parent, ignore_errors=True)

    @override_settings(DEBUG=False)
    def test_restore_requires_environment_guard(
        self,
        postgresql_backup_artifact: BackupArtifact,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _set_postgresql_default_connection(monkeypatch)

        with pytest.raises(BackupRestoreBlocked):
            restore_backup_artifact(
                postgresql_backup_artifact,
                confirmation=postgresql_backup_artifact.filename,
                dry_run=False,
            )

    def test_restore_rejects_confirmation_mismatch(
        self,
        backup_artifact: BackupArtifact,
    ) -> None:
        with pytest.raises(
            BackupRestoreBlocked,
            match="Confirmation must exactly match the backup filename",
        ):
            restore_backup_artifact(
                backup_artifact,
                confirmation=f"{backup_artifact.filename}-wrong",
                dry_run=True,
            )

    @override_settings(DEBUG=False)
    def test_restore_allow_production_still_requires_environment_guard(
        self,
        postgresql_backup_artifact: BackupArtifact,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _set_postgresql_default_connection(monkeypatch)
        monkeypatch.delenv("QUICKSCALE_BACKUPS_ALLOW_RESTORE", raising=False)

        with pytest.raises(
            BackupRestoreBlocked,
            match="QUICKSCALE_BACKUPS_ALLOW_RESTORE=true",
        ) as exc_info:
            restore_backup_artifact(
                postgresql_backup_artifact,
                confirmation=postgresql_backup_artifact.filename,
                dry_run=False,
                allow_production=True,
            )

        assert "does not bypass this environment gate" in str(exc_info.value)

    @override_settings(DEBUG=False)
    def test_restore_command_allow_production_still_requires_environment_guard(
        self,
        postgresql_backup_artifact: BackupArtifact,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _set_postgresql_default_connection(monkeypatch)
        monkeypatch.delenv("QUICKSCALE_BACKUPS_ALLOW_RESTORE", raising=False)

        with pytest.raises(
            CommandError,
            match="QUICKSCALE_BACKUPS_ALLOW_RESTORE=true",
        ):
            call_command(
                "backups_restore",
                str(postgresql_backup_artifact.pk),
                "--confirm",
                postgresql_backup_artifact.filename,
                "--allow-production",
                stdout=StringIO(),
                stderr=StringIO(),
            )

    def test_restore_dry_run_rejects_export_only_backup(
        self,
        backup_artifact: BackupArtifact,
    ) -> None:
        with pytest.raises(
            BackupRestoreBlocked,
            match="export_only artifacts are not a supported restore input",
        ):
            restore_backup_artifact(
                backup_artifact,
                confirmation=backup_artifact.filename,
                dry_run=True,
            )

    def test_restore_execution_rejects_json_backup_even_when_restore_gate_is_open(
        self,
        backup_artifact: BackupArtifact,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        runner_calls: list[tuple[list[str], dict[str, str] | None]] = []

        def fake_runner(
            command: list[str], *, env: dict[str, str] | None = None
        ) -> None:
            runner_calls.append((command, env))

        monkeypatch.setenv("QUICKSCALE_BACKUPS_ALLOW_RESTORE", "true")

        with pytest.raises(
            BackupRestoreBlocked,
            match="export_only artifacts are not a supported restore input",
        ):
            restore_backup_artifact(
                backup_artifact,
                confirmation=backup_artifact.filename,
                dry_run=False,
                shell_runner=cast(ShellCommandRunner, fake_runner),
            )

        assert runner_calls == []

    def test_restore_dry_run_rejects_incompatible_engine_and_format(
        self,
        postgresql_backup_artifact: BackupArtifact,
    ) -> None:
        with pytest.raises(
            BackupRestoreBlocked,
            match="artifact compatibility validation failed",
        ) as exc_info:
            restore_backup_artifact(
                postgresql_backup_artifact,
                confirmation=postgresql_backup_artifact.filename,
                dry_run=True,
            )

        assert "artifact database engine" in str(exc_info.value)
        assert "artifact backup format 'pg_dump_custom'" in str(exc_info.value)

    def test_restore_dry_run_requires_postgresql_18_server(
        self,
        postgresql_backup_artifact: BackupArtifact,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _set_postgresql_default_connection(monkeypatch)
        _mock_postgresql_18_contract(
            monkeypatch,
            server_version="17.9 (Debian 17.9-1)",
        )

        with pytest.raises(
            BackupRestoreBlocked,
            match="requires a PostgreSQL 18 server",
        ):
            restore_backup_artifact(
                postgresql_backup_artifact,
                confirmation=postgresql_backup_artifact.filename,
                dry_run=True,
            )

    def test_restore_dry_run_requires_pg_restore_18_tooling(
        self,
        postgresql_backup_artifact: BackupArtifact,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _set_postgresql_default_connection(monkeypatch)
        _mock_postgresql_18_contract(
            monkeypatch,
            tool_versions={"pg_restore": "pg_restore (PostgreSQL) 17.9"},
        )

        with pytest.raises(
            BackupRestoreBlocked,
            match="requires PostgreSQL 18 pg_restore tooling",
        ) as exc_info:
            restore_backup_artifact(
                postgresql_backup_artifact,
                confirmation=postgresql_backup_artifact.filename,
                dry_run=True,
            )

        assert "PGDG apt repository" in str(exc_info.value)
        assert "postgresql-client-18" in str(exc_info.value)

    def test_restore_dry_run_allows_legacy_local_only_artifact_without_normalized_majors(
        self,
        postgresql_backup_artifact: BackupArtifact,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _set_postgresql_default_connection(monkeypatch)
        _mock_postgresql_18_contract(monkeypatch)
        postgresql_backup_artifact.database_server_major = None
        postgresql_backup_artifact.dump_client_major = None
        postgresql_backup_artifact.save(
            update_fields=["database_server_major", "dump_client_major", "updated_at"]
        )

        result = restore_backup_artifact(
            postgresql_backup_artifact,
            confirmation=postgresql_backup_artifact.filename,
            dry_run=True,
        )

        assert result.executed is False
        assert result.dry_run is True

    def test_restore_local_only_resolution_rejects_remote_materialization(
        self,
        postgresql_backup_artifact: BackupArtifact,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _set_postgresql_default_connection(monkeypatch)
        _mock_postgresql_18_contract(monkeypatch)
        Path(postgresql_backup_artifact.local_path).unlink()
        postgresql_backup_artifact.storage_target = (
            BackupArtifact.STORAGE_TARGET_PRIVATE_REMOTE
        )
        postgresql_backup_artifact.remote_key = "private/backups/remote-artifact.dump"
        postgresql_backup_artifact.remote_bucket_name = "artifact-bucket"
        postgresql_backup_artifact.remote_endpoint_url = (
            "https://artifact.example.invalid"
        )
        postgresql_backup_artifact.remote_region_name = "artifact-region"
        postgresql_backup_artifact.save(
            update_fields=[
                "storage_target",
                "remote_key",
                "remote_bucket_name",
                "remote_endpoint_url",
                "remote_region_name",
                "updated_at",
            ]
        )
        materializer_calls: list[tuple[str, str]] = []

        def fake_materializer(
            remote_key: str,
            resolved_policy: BackupPolicySnapshot,
            destination: Path,
        ) -> None:
            del resolved_policy, destination
            materializer_calls.append((remote_key, postgresql_backup_artifact.filename))

        with pytest.raises(
            BackupRestoreBlocked,
            match="resolution mode does not allow private remote materialization",
        ):
            restore_backup_artifact(
                postgresql_backup_artifact,
                confirmation=postgresql_backup_artifact.filename,
                dry_run=True,
                resolution_mode=RestoreSourceResolutionMode.LOCAL_ONLY,
                remote_materializer=cast(RemoteMaterializer, fake_materializer),
            )

        assert materializer_calls == []

    @pytest.mark.parametrize(
        ("field_name", "field_value", "expected_fragment"),
        [
            (
                "database_server_major",
                17,
                "artifact database server major '17'",
            ),
            (
                "dump_client_major",
                17,
                "artifact dump client major '17'",
            ),
        ],
    )
    def test_restore_dry_run_rejects_recorded_non_18_postgresql_metadata(
        self,
        postgresql_backup_artifact: BackupArtifact,
        monkeypatch: pytest.MonkeyPatch,
        field_name: str,
        field_value: int,
        expected_fragment: str,
    ) -> None:
        _set_postgresql_default_connection(monkeypatch)
        _mock_postgresql_18_contract(monkeypatch)
        setattr(postgresql_backup_artifact, field_name, field_value)
        postgresql_backup_artifact.save(update_fields=[field_name, "updated_at"])

        with pytest.raises(
            BackupRestoreBlocked,
            match="artifact compatibility validation failed",
        ) as exc_info:
            restore_backup_artifact(
                postgresql_backup_artifact,
                confirmation=postgresql_backup_artifact.filename,
                dry_run=True,
            )

        assert expected_fragment in str(exc_info.value)

    def test_restore_execution_warns_when_metadata_persistence_raises_database_error(
        self,
        postgresql_backup_artifact: BackupArtifact,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _set_postgresql_default_connection(monkeypatch)
        _mock_postgresql_18_contract(monkeypatch)
        monkeypatch.setenv("QUICKSCALE_BACKUPS_ALLOW_RESTORE", "true")
        runner_calls: list[tuple[list[str], dict[str, str] | None]] = []

        def fake_runner(
            command: list[str], *, env: dict[str, str] | None = None
        ) -> None:
            runner_calls.append((command, env))

        class ExplodingUpdateQuerySet:
            def update(self, **kwargs: Any) -> int:
                del kwargs
                raise DatabaseError("restored database no longer matches row state")

        with patch.object(
            BackupArtifact._default_manager,
            "filter",
            return_value=ExplodingUpdateQuerySet(),
        ):
            result = restore_backup_artifact(
                postgresql_backup_artifact,
                confirmation=postgresql_backup_artifact.filename,
                dry_run=False,
                shell_runner=cast(ShellCommandRunner, fake_runner),
            )

        postgresql_backup_artifact.refresh_from_db()
        assert result.executed is True
        assert result.dry_run is False
        assert (
            result.message
            == f"Restore executed for {postgresql_backup_artifact.filename}."
        )
        assert runner_calls
        assert len(result.warnings) == 1
        warning = result.warnings[0]
        assert warning.code == "artifact_metadata_not_persisted_after_restore"
        assert (
            warning.message
            == "Restore executed, but backup artifact metadata could not be persisted after the restored database changed."
        )
        assert warning.details == {
            "artifact_id": str(postgresql_backup_artifact.pk),
            "error_type": "DatabaseError",
            "filename": postgresql_backup_artifact.filename,
        }
        assert postgresql_backup_artifact.status == BackupArtifact.STATUS_READY
        assert postgresql_backup_artifact.restored_at is None

    def test_restore_execution_warns_when_artifact_row_is_missing_after_restore(
        self,
        postgresql_backup_artifact: BackupArtifact,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _set_postgresql_default_connection(monkeypatch)
        _mock_postgresql_18_contract(monkeypatch)
        monkeypatch.setenv("QUICKSCALE_BACKUPS_ALLOW_RESTORE", "true")
        runner_calls: list[tuple[list[str], dict[str, str] | None]] = []
        artifact_id = postgresql_backup_artifact.pk
        assert artifact_id is not None

        def fake_runner(
            command: list[str], *, env: dict[str, str] | None = None
        ) -> None:
            runner_calls.append((command, env))

        class MissingRowUpdateQuerySet:
            def update(self, **kwargs: Any) -> int:
                del kwargs
                return 0

        with patch.object(
            BackupArtifact._default_manager,
            "filter",
            return_value=MissingRowUpdateQuerySet(),
        ):
            result = restore_backup_artifact(
                postgresql_backup_artifact,
                confirmation=postgresql_backup_artifact.filename,
                dry_run=False,
                shell_runner=cast(ShellCommandRunner, fake_runner),
            )

        postgresql_backup_artifact.refresh_from_db()

        assert result.executed is True
        assert result.dry_run is False
        assert (
            result.message
            == f"Restore executed for {postgresql_backup_artifact.filename}."
        )
        assert runner_calls
        assert len(result.warnings) == 1
        warning = result.warnings[0]
        assert warning.code == "artifact_row_missing_after_restore"
        assert (
            warning.message
            == "Restore executed, but the original backup artifact row no longer exists in the restored database."
        )
        assert warning.details == {
            "artifact_id": str(artifact_id),
            "filename": postgresql_backup_artifact.filename,
        }
        assert postgresql_backup_artifact.status == BackupArtifact.STATUS_READY
        assert postgresql_backup_artifact.restored_at is None

    def test_restore_dry_run_materializes_private_remote_artifact_when_local_file_is_missing(
        self,
        postgresql_backup_artifact: BackupArtifact,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _set_postgresql_default_connection(monkeypatch)
        _mock_postgresql_18_contract(monkeypatch)
        original_local_path = Path(postgresql_backup_artifact.local_path)
        original_payload = original_local_path.read_bytes()
        original_local_path.unlink()
        postgresql_backup_artifact.storage_target = (
            BackupArtifact.STORAGE_TARGET_PRIVATE_REMOTE
        )
        postgresql_backup_artifact.remote_key = "private/backups/remote-artifact.dump"
        postgresql_backup_artifact.remote_bucket_name = "artifact-bucket"
        postgresql_backup_artifact.remote_endpoint_url = (
            "https://artifact.example.invalid"
        )
        postgresql_backup_artifact.remote_region_name = "artifact-region"
        postgresql_backup_artifact.save(
            update_fields=[
                "storage_target",
                "remote_key",
                "remote_bucket_name",
                "remote_endpoint_url",
                "remote_region_name",
                "updated_at",
            ]
        )

        monkeypatch.setenv("CURRENT_RESTORE_ACCESS_KEY", "current-key")
        monkeypatch.setenv("CURRENT_RESTORE_SECRET_KEY", "current-secret")
        policy = BackupPolicySnapshot(
            retention_days=14,
            naming_prefix="db",
            target_mode=BackupPolicy.TARGET_MODE_PRIVATE_REMOTE,
            local_directory=".quickscale/backups",
            remote_bucket_name="ignored-policy-bucket",
            remote_prefix="ops/backups",
            remote_endpoint_url="https://policy.example.invalid",
            remote_region_name="policy-region",
            remote_access_key_id_env_var="CURRENT_RESTORE_ACCESS_KEY",
            remote_secret_access_key_env_var="CURRENT_RESTORE_SECRET_KEY",
            automation_enabled=False,
            schedule="0 2 * * *",
        )
        materialization_calls: list[tuple[str, str, str, str, str, str]] = []
        temp_paths: list[Path] = []

        def fake_materializer(
            remote_key: str,
            resolved_policy: BackupPolicySnapshot,
            destination: Path,
        ) -> None:
            materialization_calls.append(
                (
                    remote_key,
                    resolved_policy.remote_bucket_name,
                    resolved_policy.remote_endpoint_url,
                    resolved_policy.remote_region_name,
                    resolved_policy.resolve_remote_access_key_id(),
                    resolved_policy.resolve_remote_secret_access_key(),
                )
            )
            temp_paths.append(destination)
            destination.write_bytes(original_payload)

        result = restore_backup_artifact(
            postgresql_backup_artifact,
            confirmation=postgresql_backup_artifact.filename,
            dry_run=True,
            policy=policy,
            remote_materializer=cast(RemoteMaterializer, fake_materializer),
        )

        postgresql_backup_artifact.refresh_from_db()
        assert result.executed is False
        assert result.dry_run is True
        assert materialization_calls == [
            (
                "private/backups/remote-artifact.dump",
                "artifact-bucket",
                "https://artifact.example.invalid",
                "artifact-region",
                "current-key",
                "current-secret",
            )
        ]
        assert postgresql_backup_artifact.local_path == str(original_local_path)
        assert postgresql_backup_artifact.status == BackupArtifact.STATUS_READY
        assert temp_paths and not temp_paths[0].exists()

    def test_restore_execute_materialized_private_remote_artifact_cleans_temp_file(
        self,
        postgresql_backup_artifact: BackupArtifact,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _set_postgresql_default_connection(monkeypatch)
        _mock_postgresql_18_contract(monkeypatch)
        original_local_path = Path(postgresql_backup_artifact.local_path)
        original_payload = original_local_path.read_bytes()
        original_local_path.unlink()
        postgresql_backup_artifact.storage_target = (
            BackupArtifact.STORAGE_TARGET_PRIVATE_REMOTE
        )
        postgresql_backup_artifact.remote_key = "private/backups/remote-artifact.dump"
        postgresql_backup_artifact.remote_bucket_name = "artifact-bucket"
        postgresql_backup_artifact.remote_endpoint_url = (
            "https://artifact.example.invalid"
        )
        postgresql_backup_artifact.remote_region_name = "artifact-region"
        postgresql_backup_artifact.save(
            update_fields=[
                "storage_target",
                "remote_key",
                "remote_bucket_name",
                "remote_endpoint_url",
                "remote_region_name",
                "updated_at",
            ]
        )

        monkeypatch.setenv("QUICKSCALE_BACKUPS_ALLOW_RESTORE", "true")
        monkeypatch.setenv("CURRENT_RESTORE_ACCESS_KEY", "current-key")
        monkeypatch.setenv("CURRENT_RESTORE_SECRET_KEY", "current-secret")
        policy = BackupPolicySnapshot(
            retention_days=14,
            naming_prefix="db",
            target_mode=BackupPolicy.TARGET_MODE_PRIVATE_REMOTE,
            local_directory=".quickscale/backups",
            remote_bucket_name="ignored-policy-bucket",
            remote_prefix="ops/backups",
            remote_endpoint_url="https://policy.example.invalid",
            remote_region_name="policy-region",
            remote_access_key_id_env_var="CURRENT_RESTORE_ACCESS_KEY",
            remote_secret_access_key_env_var="CURRENT_RESTORE_SECRET_KEY",
            automation_enabled=False,
            schedule="0 2 * * *",
        )
        temp_paths: list[Path] = []
        runner_calls: list[tuple[list[str], dict[str, str] | None]] = []

        def fake_materializer(
            remote_key: str,
            resolved_policy: BackupPolicySnapshot,
            destination: Path,
        ) -> None:
            del remote_key, resolved_policy
            temp_paths.append(destination)
            destination.write_bytes(original_payload)

        def fake_runner(
            command: list[str], *, env: dict[str, str] | None = None
        ) -> None:
            runner_calls.append((command, env))
            restore_path = Path(command[-1])
            assert restore_path.exists()
            assert restore_path.read_bytes() == original_payload

        result = restore_backup_artifact(
            postgresql_backup_artifact,
            confirmation=postgresql_backup_artifact.filename,
            dry_run=False,
            shell_runner=cast(ShellCommandRunner, fake_runner),
            policy=policy,
            remote_materializer=cast(RemoteMaterializer, fake_materializer),
        )

        postgresql_backup_artifact.refresh_from_db()
        assert result.executed is True
        assert (
            result.message
            == f"Restore executed for {postgresql_backup_artifact.filename}."
        )
        assert runner_calls
        assert postgresql_backup_artifact.local_path == str(original_local_path)
        assert postgresql_backup_artifact.status == BackupArtifact.STATUS_RESTORED
        assert temp_paths and not temp_paths[0].exists()

    def test_restore_runner_failure_cleans_materialized_private_remote_file(
        self,
        postgresql_backup_artifact: BackupArtifact,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _set_postgresql_default_connection(monkeypatch)
        _mock_postgresql_18_contract(monkeypatch)
        original_local_path = Path(postgresql_backup_artifact.local_path)
        original_payload = original_local_path.read_bytes()
        original_local_path.unlink()
        postgresql_backup_artifact.storage_target = (
            BackupArtifact.STORAGE_TARGET_PRIVATE_REMOTE
        )
        postgresql_backup_artifact.remote_key = "private/backups/remote-artifact.dump"
        postgresql_backup_artifact.remote_bucket_name = "artifact-bucket"
        postgresql_backup_artifact.remote_endpoint_url = (
            "https://artifact.example.invalid"
        )
        postgresql_backup_artifact.remote_region_name = "artifact-region"
        postgresql_backup_artifact.save(
            update_fields=[
                "storage_target",
                "remote_key",
                "remote_bucket_name",
                "remote_endpoint_url",
                "remote_region_name",
                "updated_at",
            ]
        )

        monkeypatch.setenv("QUICKSCALE_BACKUPS_ALLOW_RESTORE", "true")
        monkeypatch.setenv("CURRENT_RESTORE_ACCESS_KEY", "current-key")
        monkeypatch.setenv("CURRENT_RESTORE_SECRET_KEY", "current-secret")
        policy = BackupPolicySnapshot(
            retention_days=14,
            naming_prefix="db",
            target_mode=BackupPolicy.TARGET_MODE_PRIVATE_REMOTE,
            local_directory=".quickscale/backups",
            remote_bucket_name="ignored-policy-bucket",
            remote_prefix="ops/backups",
            remote_endpoint_url="https://policy.example.invalid",
            remote_region_name="policy-region",
            remote_access_key_id_env_var="CURRENT_RESTORE_ACCESS_KEY",
            remote_secret_access_key_env_var="CURRENT_RESTORE_SECRET_KEY",
            automation_enabled=False,
            schedule="0 2 * * *",
        )
        temp_paths: list[Path] = []

        def fake_materializer(
            remote_key: str,
            resolved_policy: BackupPolicySnapshot,
            destination: Path,
        ) -> None:
            del remote_key, resolved_policy
            temp_paths.append(destination)
            destination.write_bytes(original_payload)

        def failing_runner(
            command: list[str], *, env: dict[str, str] | None = None
        ) -> None:
            del command, env
            raise BackupError("pg_restore exploded")

        with pytest.raises(BackupError, match="pg_restore exploded"):
            restore_backup_artifact(
                postgresql_backup_artifact,
                confirmation=postgresql_backup_artifact.filename,
                dry_run=False,
                shell_runner=cast(ShellCommandRunner, failing_runner),
                policy=policy,
                remote_materializer=cast(RemoteMaterializer, fake_materializer),
            )

        postgresql_backup_artifact.refresh_from_db()
        assert postgresql_backup_artifact.local_path == str(original_local_path)
        assert postgresql_backup_artifact.status == BackupArtifact.STATUS_READY
        assert temp_paths and not temp_paths[0].exists()

    @pytest.mark.parametrize("dry_run", [True, False])
    def test_restore_file_mode_rejects_json_input(
        self,
        artifact_file: Path,
        dry_run: bool,
    ) -> None:
        with pytest.raises(
            BackupRestoreBlocked,
            match="JSON file inputs are not a supported restore input",
        ):
            restore_backup_source(
                file_path=artifact_file,
                confirmation=artifact_file.name,
                dry_run=dry_run,
            )

    def test_restore_file_mode_requires_basename_confirmation(
        self,
        postgresql_artifact_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _set_postgresql_default_connection(monkeypatch)
        _mock_postgresql_18_contract(monkeypatch)

        with pytest.raises(
            BackupRestoreBlocked,
            match="Confirmation must exactly match the backup filename",
        ):
            restore_backup_source(
                file_path=postgresql_artifact_file,
                confirmation=f"wrong-{postgresql_artifact_file.name}",
                dry_run=True,
            )

    def test_restore_file_mode_dry_run_rejects_non_archive_input(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _set_postgresql_default_connection(monkeypatch)
        _mock_postgresql_18_contract(monkeypatch)
        invalid_file = tmp_path / "not-a-backup.dump"
        invalid_file.write_text(
            "plain text instead of a PostgreSQL archive", encoding="utf-8"
        )

        with pytest.raises(
            BackupRestoreBlocked,
            match="operator-supplied file is not a valid PostgreSQL custom archive",
        ):
            restore_backup_source(
                file_path=invalid_file,
                confirmation=invalid_file.name,
                dry_run=True,
            )

    def test_restore_file_mode_executes_pg_restore_for_operator_dump(
        self,
        postgresql_artifact_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _set_postgresql_default_connection(monkeypatch)
        _mock_postgresql_18_contract(monkeypatch)
        monkeypatch.setenv("QUICKSCALE_BACKUPS_ALLOW_RESTORE", "true")
        postgresql_artifact_file.write_bytes(b"PGDMP\x01\x0e\x00sample archive bytes")
        runner_calls: list[tuple[list[str], dict[str, str] | None]] = []

        def fake_runner(
            command: list[str], *, env: dict[str, str] | None = None
        ) -> None:
            runner_calls.append((command, env))

        result = restore_backup_source(
            file_path=postgresql_artifact_file,
            confirmation=postgresql_artifact_file.name,
            dry_run=False,
            shell_runner=cast(ShellCommandRunner, fake_runner),
        )

        assert result.executed is True
        assert (
            result.message == f"Restore executed for {postgresql_artifact_file.name}."
        )
        assert runner_calls == [
            (
                ["pg_restore", "--list", str(postgresql_artifact_file)],
                None,
            ),
            (
                [
                    "pg_restore",
                    "--clean",
                    "--if-exists",
                    "--no-owner",
                    "--dbname",
                    "quickscale_test",
                    str(postgresql_artifact_file),
                ],
                None,
            ),
        ]

    def test_restore_file_mode_rejects_non_postgresql_target_runtime(
        self,
        postgresql_artifact_file: Path,
    ) -> None:
        with pytest.raises(
            BackupRestoreBlocked,
            match="operator-supplied restore files require a PostgreSQL target database",
        ):
            restore_backup_source(
                file_path=postgresql_artifact_file,
                confirmation=postgresql_artifact_file.name,
                dry_run=True,
            )


class TestBackupServiceHelpers:
    """Focused tests for helper branches that underpin coverage policy enforcement."""

    def test_build_media_sync_manifest_fails_closed_for_malformed_storage_helpers(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            backup_services,
            "import_module",
            lambda _module_name: SimpleNamespace(
                list_s3_compatible_media_inventory=lambda _settings_obj: []
            ),
        )

        manifest = backup_services._build_media_sync_manifest(
            captured_at=datetime(2026, 4, 30, tzinfo=timezone.utc)
        )

        assert manifest["status"] == "unsupported"
        assert manifest["reason"] == "storage helper is unavailable in this runtime"
        assert manifest["error_type"] == "AttributeError"
        assert manifest["inventory"] == []

    def test_collect_local_backup_validation_issues_and_restore_source_checks(
        self,
        tmp_path: Path,
    ) -> None:
        missing_issues = backup_services._collect_local_backup_validation_issues(
            None,
            backup_format="json",
        )
        assert missing_issues == ["local backup artifact is missing"]

        missing_source = backup_services.ResolvedRestoreSource(
            confirmation_value="missing.dump",
            local_path=tmp_path / "missing.dump",
            backup_format="pg_dump_custom",
        )
        assert backup_services._get_restore_source_validation_issues(
            missing_source
        ) == [f"restore file not found: {missing_source.local_path}"]

        directory_source = backup_services.ResolvedRestoreSource(
            confirmation_value=tmp_path.name,
            local_path=tmp_path,
            backup_format="pg_dump_custom",
        )
        assert backup_services._get_restore_source_validation_issues(
            directory_source
        ) == [f"restore file is not a regular file: {tmp_path}"]

    def test_build_pg_commands_include_optional_connection_settings(
        self,
        tmp_path: Path,
    ) -> None:
        local_path = tmp_path / "backup.dump"
        connection_settings = {
            "HOST": "db.internal",
            "PORT": "5432",
            "USER": "backup-user",
            "NAME": "quickscale",
            "PASSWORD": "top-secret",
        }

        dump_command, dump_env = backup_services._build_pg_dump_command(
            local_path,
            connection_settings,
        )
        restore_command, restore_env = backup_services._build_pg_restore_command(
            local_path,
            connection_settings,
        )

        assert dump_command == [
            "pg_dump",
            "--format=c",
            "--file",
            str(local_path),
            "--host",
            "db.internal",
            "--port",
            "5432",
            "--username",
            "backup-user",
            "quickscale",
        ]
        assert dump_env == {"PGPASSWORD": "top-secret"}
        assert restore_command == [
            "pg_restore",
            "--clean",
            "--if-exists",
            "--no-owner",
            "--host",
            "db.internal",
            "--port",
            "5432",
            "--username",
            "backup-user",
            "--dbname",
            "quickscale",
            str(local_path),
        ]
        assert restore_env == {"PGPASSWORD": "top-secret"}

    def test_pg_commands_require_database_name(self, tmp_path: Path) -> None:
        local_path = tmp_path / "backup.dump"

        with pytest.raises(
            BackupConfigurationError,
            match=r"DATABASES\['default'\]\['NAME'\] is required",
        ):
            backup_services._build_pg_dump_command(local_path, {"NAME": ""})

        with pytest.raises(
            BackupConfigurationError,
            match=r"DATABASES\['default'\]\['NAME'\] is required",
        ):
            backup_services._build_pg_restore_command(local_path, {"NAME": ""})

    def test_run_shell_command_merges_env_and_wraps_failures(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        recorded_envs: list[dict[str, str]] = []

        def successful_run(*args: Any, **kwargs: Any) -> SimpleNamespace:
            del args
            recorded_envs.append(cast(dict[str, str], kwargs["env"]))
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(backup_services.subprocess, "run", successful_run)
        backup_services._run_shell_command(["echo", "ok"], env={"PGPASSWORD": "pw"})
        assert recorded_envs and recorded_envs[0]["PGPASSWORD"] == "pw"

        def failing_run(*args: Any, **kwargs: Any) -> SimpleNamespace:
            del args, kwargs
            return SimpleNamespace(returncode=1, stdout="boom", stderr="")

        monkeypatch.setattr(backup_services.subprocess, "run", failing_run)
        with pytest.raises(BackupError, match="Command failed: echo ok :: boom"):
            backup_services._run_shell_command(["echo", "ok"])

    def test_run_shell_command_wraps_missing_pg_restore_binary(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def missing_binary(*args: Any, **kwargs: Any) -> None:
            del args, kwargs
            raise FileNotFoundError("pg_restore")

        monkeypatch.setattr(backup_services.subprocess, "run", missing_binary)

        with pytest.raises(
            BackupError,
            match="Required executable 'pg_restore' is not installed in this runtime",
        ) as exc_info:
            backup_services._run_shell_command(["pg_restore", "--version"])

        assert "postgresql-client-18" in str(exc_info.value)

    def test_resolve_private_remote_credentials_requires_configured_env_values(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        policy = _private_remote_policy_snapshot()
        monkeypatch.delenv("TEST_BACKUPS_ACCESS_KEY", raising=False)
        monkeypatch.delenv("TEST_BACKUPS_SECRET_KEY", raising=False)

        with pytest.raises(
            BackupConfigurationError,
            match="TEST_BACKUPS_ACCESS_KEY",
        ):
            backup_services._resolve_private_remote_credentials(policy)

        monkeypatch.setenv("TEST_BACKUPS_ACCESS_KEY", "access-key")
        with pytest.raises(
            BackupConfigurationError,
            match="TEST_BACKUPS_SECRET_KEY",
        ):
            backup_services._resolve_private_remote_credentials(policy)

    def test_private_remote_storage_helpers_use_resolved_credentials(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("TEST_BACKUPS_ACCESS_KEY", "access-key")
        monkeypatch.setenv("TEST_BACKUPS_SECRET_KEY", "secret-key")
        policy = _private_remote_policy_snapshot(local_directory=str(tmp_path))
        local_path = tmp_path / "artifact.dump"
        local_path.write_bytes(b"backup-bytes")
        destination = tmp_path / "materialized" / "artifact.dump"

        uploaded: list[tuple[dict[str, object], str, bytes]] = []
        deleted: list[tuple[dict[str, object], str]] = []
        remote_payloads = {"ops/backups/artifact.dump": b"remote-artifact"}

        class FakeStorage:
            def __init__(self, **options: object) -> None:
                self.options = options

            def save(self, remote_key: str, handle: Any) -> str:
                uploaded.append((self.options, remote_key, handle.read()))
                return remote_key

            def open(self, remote_key: str, mode: str = "rb") -> BytesIO:
                assert mode == "rb"
                return BytesIO(remote_payloads[remote_key])

            def delete(self, remote_key: str) -> None:
                deleted.append((self.options, remote_key))

        with patch("storages.backends.s3.S3Storage", FakeStorage):
            remote_key = backup_services._upload_to_private_remote(local_path, policy)
            backup_services._materialize_private_remote_key(
                remote_key,
                policy,
                destination,
            )
            backup_services._delete_private_remote_key(remote_key, policy)

        expected_options = {
            "bucket_name": "private-backups",
            "querystring_auth": True,
            "default_acl": "",
            "endpoint_url": "https://object-storage.example.invalid",
            "region_name": "us-east-1",
            "access_key": "access-key",
            "secret_key": "secret-key",
        }
        assert remote_key == "ops/backups/artifact.dump"
        assert uploaded == [(expected_options, remote_key, b"backup-bytes")]
        assert destination.read_bytes() == b"remote-artifact"
        assert deleted == [(expected_options, remote_key)]

    def test_download_backup_path_allows_current_authoritative_root(
        self,
        superuser: AbstractBaseUser,
        local_backup_settings: Path,
    ) -> None:
        local_backup_settings.mkdir(parents=True, exist_ok=True)
        artifact_path = local_backup_settings / "downloadable-backup.json"
        artifact_path.write_text("[]", encoding="utf-8")
        artifact = BackupArtifact.objects.create(
            filename=artifact_path.name,
            local_path=str(artifact_path),
            checksum_sha256=hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
            size_bytes=artifact_path.stat().st_size,
            backup_format="json",
            database_engine="django.db.backends.sqlite3",
            database_name="test.sqlite3",
            metadata_json={"environment": "test"},
            initiated_by=superuser,
        )

        resolved_path = backup_services.download_backup_path(artifact)

        assert resolved_path == artifact_path.resolve()

    def test_download_backup_path_allows_authoritative_snapshot_root_after_settings_drift(
        self,
        superuser: AbstractBaseUser,
        backup_policy: BackupPolicy,
        local_backup_settings: Path,
    ) -> None:
        backup_policy.local_directory = str(local_backup_settings)
        backup_policy.save(update_fields=["local_directory", "updated_at"])
        artifact = create_backup(initiated_by=superuser, trigger="manual")
        original_path = Path(artifact.local_path)

        with override_settings(
            BASE_DIR=local_backup_settings.parent,
            QUICKSCALE_BACKUPS_LOCAL_DIRECTORY=str(
                local_backup_settings.parent / "drifted-private-backups"
            ),
        ):
            resolved_path = backup_services.download_backup_path(artifact)

        assert resolved_path == original_path.resolve()

    def test_download_backup_path_rejects_out_of_tree_tampered_row(
        self,
        superuser: AbstractBaseUser,
        local_backup_settings: Path,
        tmp_path: Path,
    ) -> None:
        outside_path = tmp_path / "tampered-backup.json"
        outside_path.write_text("[]", encoding="utf-8")
        artifact = BackupArtifact.objects.create(
            filename=outside_path.name,
            local_path=str(outside_path),
            checksum_sha256=hashlib.sha256(outside_path.read_bytes()).hexdigest(),
            size_bytes=outside_path.stat().st_size,
            backup_format="json",
            database_engine="django.db.backends.sqlite3",
            database_name="test.sqlite3",
            metadata_json={"environment": "test"},
            initiated_by=superuser,
        )

        with pytest.raises(
            BackupError,
            match="authoritative backup roots",
        ):
            backup_services.download_backup_path(artifact)

    def test_download_backup_path_rejects_symlink_escape_within_authoritative_root(
        self,
        superuser: AbstractBaseUser,
        local_backup_settings: Path,
        tmp_path: Path,
    ) -> None:
        escape_target = tmp_path / "outside-root.json"
        escape_target.write_text("[]", encoding="utf-8")
        symlink_path = local_backup_settings / "database" / "linked-backup.json"
        symlink_path.parent.mkdir(parents=True, exist_ok=True)
        symlink_path.symlink_to(escape_target)
        artifact = BackupArtifact.objects.create(
            filename=symlink_path.name,
            local_path=str(symlink_path),
            checksum_sha256=hashlib.sha256(escape_target.read_bytes()).hexdigest(),
            size_bytes=escape_target.stat().st_size,
            backup_format="json",
            database_engine="django.db.backends.sqlite3",
            database_name="test.sqlite3",
            metadata_json={"environment": "test"},
            initiated_by=superuser,
        )

        with pytest.raises(BackupError, match="cannot use symlinks"):
            backup_services.download_backup_path(artifact)

    def test_restore_execution_allowed_honors_debug_and_env(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        with override_settings(DEBUG=True):
            assert backup_services._restore_execution_allowed() is True

        with override_settings(DEBUG=False):
            monkeypatch.setenv("QUICKSCALE_BACKUPS_ALLOW_RESTORE", "true")
            assert backup_services._restore_execution_allowed() is True

            monkeypatch.setenv("QUICKSCALE_BACKUPS_ALLOW_RESTORE", "false")
            assert backup_services._restore_execution_allowed() is False

    def test_postgresql_tool_version_reports_errors_and_query_branches(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def failing_run(*args: Any, **kwargs: Any) -> SimpleNamespace:
            del args, kwargs
            return SimpleNamespace(
                returncode=1,
                stdout="",
                stderr="version probe failed",
            )

        monkeypatch.setattr(backup_services.subprocess, "run", failing_run)
        with pytest.raises(BackupError, match="version probe failed"):
            backup_services._get_postgresql_tool_version("pg_dump")

        def empty_run(*args: Any, **kwargs: Any) -> SimpleNamespace:
            del args, kwargs
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(backup_services.subprocess, "run", empty_run)
        with pytest.raises(BackupError, match="command returned no output"):
            backup_services._get_postgresql_tool_version("pg_restore")

        assert (
            backup_services._database_server_version_query("django.db.backends.sqlite3")
            == "SELECT sqlite_version()"
        )
        assert (
            backup_services._database_server_version_query("django.db.backends.mysql")
            is None
        )

    def test_operator_archive_validation_wraps_io_and_pg_restore_failures(
        self,
        tmp_path: Path,
    ) -> None:
        missing_source = backup_services.ResolvedRestoreSource(
            confirmation_value="missing.dump",
            local_path=tmp_path / "missing.dump",
            backup_format="pg_dump_custom",
        )
        with pytest.raises(BackupRestoreBlocked, match="could not be inspected"):
            backup_services._ensure_operator_supplied_custom_archive_valid(
                missing_source
            )

        archive_path = tmp_path / "operator.dump"
        archive_path.write_bytes(b"PGDMP\x01\x0e\x00archive bytes")
        archive_source = backup_services.ResolvedRestoreSource(
            confirmation_value=archive_path.name,
            local_path=archive_path,
            backup_format="pg_dump_custom",
        )

        def failing_runner(
            command: list[str], *, env: dict[str, str] | None = None
        ) -> None:
            del command, env
            raise BackupError("corrupt archive")

        with pytest.raises(
            BackupRestoreBlocked,
            match="not a valid PostgreSQL custom archive: corrupt archive",
        ):
            backup_services._ensure_operator_supplied_custom_archive_valid(
                archive_source,
                shell_runner=cast(ShellCommandRunner, failing_runner),
            )

    def test_resolve_restore_source_blocks_invalid_remote_fallback_paths(
        self,
        backup_artifact: BackupArtifact,
        tmp_path: Path,
    ) -> None:
        with pytest.raises(
            BackupRestoreBlocked, match="Choose exactly one restore source"
        ):
            with backup_services._resolve_restore_source(
                artifact=backup_artifact,
                file_path="artifact.dump",
                snapshot_id=None,
                resolution_mode=RestoreSourceResolutionMode.REMOTE_FALLBACK,
                policy=None,
                remote_materializer=None,
            ):
                pytest.fail("restore source resolution should have failed")

        Path(backup_artifact.local_path).unlink()

        with pytest.raises(
            BackupRestoreBlocked,
            match="does not allow private remote materialization",
        ):
            with backup_services._resolve_restore_source(
                artifact=backup_artifact,
                file_path=None,
                snapshot_id=None,
                resolution_mode=RestoreSourceResolutionMode.LOCAL_ONLY,
                policy=None,
                remote_materializer=None,
            ):
                pytest.fail("local-only restore should not materialize remotely")

        with pytest.raises(
            BackupRestoreBlocked,
            match="no private remote artifact is available",
        ):
            with backup_services._resolve_restore_source(
                artifact=backup_artifact,
                file_path=None,
                snapshot_id=None,
                resolution_mode=RestoreSourceResolutionMode.REMOTE_FALLBACK,
                policy=None,
                remote_materializer=None,
            ):
                pytest.fail("missing remote key should block restore")

        backup_artifact.remote_key = "private/backups/sample.dump"
        policy = _private_remote_policy_snapshot(local_directory=str(tmp_path))

        def exploding_materializer(
            remote_key: str,
            resolved_policy: BackupPolicySnapshot,
            destination: Path,
        ) -> None:
            del remote_key, resolved_policy, destination
            raise RuntimeError("object storage offline")

        with pytest.raises(
            BackupRestoreBlocked,
            match="private remote materialization failed.*object storage offline",
        ):
            with backup_services._resolve_restore_source(
                artifact=backup_artifact,
                file_path=None,
                snapshot_id=None,
                resolution_mode=RestoreSourceResolutionMode.REMOTE_FALLBACK,
                policy=policy,
                remote_materializer=cast(RemoteMaterializer, exploding_materializer),
            ):
                pytest.fail("materializer failures should block restore")

        def noop_materializer(
            remote_key: str,
            resolved_policy: BackupPolicySnapshot,
            destination: Path,
        ) -> None:
            del remote_key, resolved_policy, destination

        with pytest.raises(
            BackupRestoreBlocked,
            match="did not produce a local file",
        ):
            with backup_services._resolve_restore_source(
                artifact=backup_artifact,
                file_path=None,
                snapshot_id=None,
                resolution_mode=RestoreSourceResolutionMode.REMOTE_FALLBACK,
                policy=policy,
                remote_materializer=cast(RemoteMaterializer, noop_materializer),
            ):
                pytest.fail("missing materialized files should block restore")

    def test_restore_runtime_and_engine_helpers_cover_non_default_branches(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def failing_contract(**kwargs: Any) -> tuple[str, int, str, int]:
            del kwargs
            raise BackupError("pg_restore 18 tooling missing")

        monkeypatch.setattr(
            backup_services,
            "_require_postgresql_18_contract",
            failing_contract,
        )

        with pytest.raises(BackupRestoreBlocked, match="pg_restore 18 tooling missing"):
            backup_services._ensure_postgresql_18_restore_runtime(
                "django.db.backends.postgresql"
            )

        backup_services._ensure_postgresql_18_restore_runtime(
            "django.db.backends.sqlite3"
        )
        assert (
            backup_services._database_engine_family("custom.database.backend")
            == "custom.database.backend"
        )
        assert (
            backup_services._expected_backup_format_for_engine(
                "django.db.backends.sqlite3"
            )
            == "json"
        )


class TestBackupServiceUtilities:
    """Targeted tests for private utility functions to raise per-file coverage."""

    def test_get_source_environment(self) -> None:
        """_get_source_environment returns 'local' without env override."""
        result = backup_services._get_source_environment()
        assert result == "local"

    def test_get_source_environment_with_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_get_source_environment returns the env var when set."""
        monkeypatch.setenv("QUICKSCALE_ENVIRONMENT", "production")
        result = backup_services._get_source_environment()
        assert result == "production"

    def test_build_snapshot_local_root(self) -> None:
        """_build_snapshot_local_root resolves snapshot local directory."""
        policy = BackupPolicySnapshot.from_settings()
        result = backup_services._build_snapshot_local_root(policy, "snap-123")
        assert result.name == "snap-123"
        assert result.parent.name == "snapshots"

    def test_build_snapshot_remote_root_with_prefix(self) -> None:
        """_build_snapshot_remote_root includes remote_prefix when set."""
        policy = BackupPolicySnapshot(
            retention_days=14,
            naming_prefix="db",
            target_mode=BackupPolicy.TARGET_MODE_PRIVATE_REMOTE,
            local_directory=".quickscale/backups",
            remote_bucket_name="bucket",
            remote_prefix="ops/backups",
            remote_endpoint_url="",
            remote_region_name="",
            remote_access_key_id_env_var="",
            remote_secret_access_key_env_var="",
            automation_enabled=False,
            schedule="0 2 * * *",
        )
        result = backup_services._build_snapshot_remote_root(policy, "snap-abc")
        assert result.startswith("ops/backups/snapshots/snap-abc")

    def test_build_snapshot_remote_root_without_prefix(self) -> None:
        """_build_snapshot_remote_root returns bare path when remote_prefix is empty."""
        policy = BackupPolicySnapshot(
            retention_days=14,
            naming_prefix="db",
            target_mode=BackupPolicy.TARGET_MODE_LOCAL,
            local_directory=".quickscale/backups",
            remote_bucket_name="",
            remote_prefix="",
            remote_endpoint_url="",
            remote_region_name="",
            remote_access_key_id_env_var="",
            remote_secret_access_key_env_var="",
            automation_enabled=False,
            schedule="0 2 * * *",
        )
        result = backup_services._build_snapshot_remote_root(policy, "snap-xyz")
        assert result == "snapshots/snap-xyz"

    def test_replace_policy_remote_prefix(self) -> None:
        """_replace_policy_remote_prefix returns a copy with new prefix."""
        policy = BackupPolicySnapshot.from_settings()
        updated = backup_services._replace_policy_remote_prefix(policy, "new/prefix")
        assert updated.remote_prefix == "new/prefix"
        assert policy.remote_prefix != "new/prefix"

    def test_read_setting_value_dict(self) -> None:
        """_read_setting_value returns value from dict when settings_obj is a dict."""
        result = backup_services._read_setting_value({"key": "val"}, "key", "default")
        assert result == "val"

    def test_read_setting_value_dict_default(self) -> None:
        """_read_setting_value returns default when key is missing from dict."""
        result = backup_services._read_setting_value({}, "missing", "fallback")
        assert result == "fallback"

    def test_snapshot_sidecar_path(self, tmp_path: Path) -> None:
        """_snapshot_sidecar_path resolves sidecar file under snapshot root."""
        from quickscale_modules_backups.models import BackupSnapshot

        snapshot = BackupSnapshot(
            local_root_path=str(tmp_path / "snapshot-root"),
            status=BackupSnapshot.STATUS_READY,
        )
        result = backup_services._snapshot_sidecar_path(
            snapshot, "release-metadata.json"
        )
        assert result == tmp_path / "snapshot-root" / "release-metadata.json"
