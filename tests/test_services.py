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
    RemoteMaterializer,
    RemoteUploader,
    ShellCommandRunner,
    build_backup_filename,
    create_backup,
    load_policy_snapshot,
    prune_expired_backups,
    restore_backup_artifact,
    restore_backup_source,
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
        assert not any(local_backup_settings.iterdir())

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
        assert not any(local_backup_settings.iterdir())

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
        assert not any(local_backup_settings.iterdir())

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
        assert not any(local_backup_settings.iterdir())

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
        assert not any(local_backup_settings.iterdir())

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
