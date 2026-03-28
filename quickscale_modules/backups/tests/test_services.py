"""Tests for backups module services."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from typing import Any, cast

import pytest
from django.contrib.auth.base_user import AbstractBaseUser
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connections
from django.test import override_settings

import quickscale_modules_backups.services as backup_services
from quickscale_modules_backups.models import BackupArtifact, BackupPolicy
from quickscale_modules_backups.services import (
    BackupError,
    BackupConfigurationError,
    BackupLockError,
    BackupPolicySnapshot,
    BackupRestoreBlocked,
    RemoteDeleter,
    RemoteUploader,
    ShellCommandRunner,
    build_backup_filename,
    create_backup,
    load_policy_snapshot,
    prune_expired_backups,
    restore_backup_artifact,
    validate_backup_artifact,
    validate_policy_snapshot,
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

    def test_create_backup_uses_json_fallback_for_sqlite(
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
        payload = json.loads(Path(artifact.local_path).read_text(encoding="utf-8"))
        assert isinstance(payload, list)

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
        uploaded: list[tuple[str, str, str, str]] = []

        def fake_uploader(
            local_path: Path, resolved_policy: BackupPolicySnapshot
        ) -> str:
            uploaded.append(
                (
                    local_path.name,
                    resolved_policy.remote_bucket_name,
                    resolved_policy.resolve_remote_access_key_id(),
                    resolved_policy.resolve_remote_secret_access_key(),
                )
            )
            return f"ops/backups/{local_path.name}"

        artifact = create_backup(
            initiated_by=superuser,
            trigger="admin",
            policy=policy,
            remote_uploader=cast(RemoteUploader, fake_uploader),
        )

        assert artifact.storage_target == BackupArtifact.STORAGE_TARGET_PRIVATE_REMOTE
        assert artifact.remote_key.startswith("ops/backups/")
        assert uploaded == [
            (artifact.filename, "private-backups", "key-id", "secret-key")
        ]
        assert Path(artifact.local_path).exists()
        assert artifact.remote_bucket_name == "private-backups"
        assert artifact.remote_endpoint_url == "https://example.invalid"
        assert artifact.remote_region_name == "auto"
        assert not hasattr(artifact, "remote_access_key_id")
        assert not hasattr(artifact, "remote_secret_access_key")

    def test_create_backup_marks_remote_upload_failure_and_cleans_local_file(
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
        assert artifact.status == BackupArtifact.STATUS_FAILED
        assert artifact.remote_key == ""
        assert artifact.local_path == ""
        assert "remote upload failed" in artifact.validation_notes
        assert not any(local_backup_settings.iterdir())

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
            del resolved_policy
            return f"ops/backups/{local_path.name}"

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

        assert deleted_remote_keys == [
            (f"ops/backups/{artifact.filename}", "private-backups")
        ]
        assert artifact.remote_key == ""
        assert artifact.local_path
        assert Path(artifact.local_path).exists()
        assert f"'{artifact.filename}'" not in str(exc_info.value)
        assert f"ops/backups/{artifact.filename}" in str(exc_info.value)

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
        assert not any(local_backup_settings.iterdir())

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
        BackupArtifact.objects.filter(pk=artifact.pk).update(
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

        assert deleted_count == 1
        assert deletion_calls == [
            (
                artifact.remote_key,
                "original-bucket",
                "https://original.example.invalid",
                "auto",
                "current-key",
                "current-secret",
            )
        ]

    @override_settings(DEBUG=False)
    def test_restore_requires_environment_guard(
        self,
        backup_artifact: BackupArtifact,
    ) -> None:
        with pytest.raises(BackupRestoreBlocked):
            restore_backup_artifact(
                backup_artifact,
                confirmation=backup_artifact.filename,
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
        backup_artifact: BackupArtifact,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("QUICKSCALE_BACKUPS_ALLOW_RESTORE", raising=False)

        with pytest.raises(
            BackupRestoreBlocked,
            match="QUICKSCALE_BACKUPS_ALLOW_RESTORE=true",
        ) as exc_info:
            restore_backup_artifact(
                backup_artifact,
                confirmation=backup_artifact.filename,
                dry_run=False,
                allow_production=True,
            )

        assert "does not bypass this environment gate" in str(exc_info.value)

    @override_settings(DEBUG=False)
    def test_restore_command_allow_production_still_requires_environment_guard(
        self,
        backup_artifact: BackupArtifact,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("QUICKSCALE_BACKUPS_ALLOW_RESTORE", raising=False)

        with pytest.raises(
            CommandError,
            match="QUICKSCALE_BACKUPS_ALLOW_RESTORE=true",
        ):
            call_command(
                "backups_restore",
                str(backup_artifact.pk),
                "--confirm",
                backup_artifact.filename,
                "--allow-production",
                stdout=StringIO(),
                stderr=StringIO(),
            )

    def test_restore_dry_run_succeeds_for_json_backup(
        self,
        backup_artifact: BackupArtifact,
    ) -> None:
        result = restore_backup_artifact(
            backup_artifact,
            confirmation=backup_artifact.filename,
            dry_run=True,
        )

        assert result.executed is False
        assert result.dry_run is True

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
            match="Executable restore is only supported for PostgreSQL custom-format",
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
        backup_artifact: BackupArtifact,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setitem(
            connections["default"].settings_dict,
            "ENGINE",
            "django.db.backends.postgresql",
        )

        with pytest.raises(
            BackupRestoreBlocked,
            match="artifact compatibility validation failed",
        ) as exc_info:
            restore_backup_artifact(
                backup_artifact,
                confirmation=backup_artifact.filename,
                dry_run=True,
            )

        assert "artifact database engine" in str(exc_info.value)
        assert "artifact backup format 'json'" in str(exc_info.value)
