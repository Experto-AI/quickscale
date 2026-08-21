"""Tests for the backups module's fresh final-schema migration."""

from __future__ import annotations

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

pytestmark = [
    pytest.mark.bypass_rls,
    pytest.mark.django_db(transaction=True),
]


def test_fresh_initial_contains_the_final_backup_schema() -> None:
    target = ("quickscale_modules_backups", "0001_initial")

    executor = MigrationExecutor(connection)
    executor.migrate([target])
    historical_apps = executor.loader.project_state([target]).apps

    policy = historical_apps.get_model("quickscale_modules_backups", "BackupPolicy")
    artifact = historical_apps.get_model("quickscale_modules_backups", "BackupArtifact")
    snapshot = historical_apps.get_model("quickscale_modules_backups", "BackupSnapshot")

    assert {field.name for field in policy._meta.local_fields} == {
        "id",
        "key",
        "retention_days",
        "naming_prefix",
        "target_mode",
        "local_directory",
        "remote_bucket_name",
        "remote_prefix",
        "remote_endpoint_url",
        "remote_region_name",
        "remote_access_key_id_env_var",
        "remote_secret_access_key_env_var",
        "automation_enabled",
        "schedule",
        "created_at",
        "updated_at",
    }
    assert {field.name for field in artifact._meta.local_fields} == {
        "id",
        "filename",
        "storage_target",
        "local_path",
        "remote_key",
        "remote_bucket_name",
        "remote_endpoint_url",
        "remote_region_name",
        "checksum_sha256",
        "size_bytes",
        "backup_format",
        "restore_scope",
        "database_engine",
        "database_name",
        "database_server_major",
        "dump_client_major",
        "metadata_json",
        "status",
        "trigger",
        "initiated_by",
        "validation_notes",
        "validated_at",
        "restore_started_at",
        "restore_error",
        "restored_at",
        "deleted_at",
        "created_at",
        "updated_at",
    }
    assert {field.name for field in snapshot._meta.local_fields} == {
        "id",
        "snapshot_id",
        "authoritative_dump",
        "status",
        "source_environment",
        "local_root_path",
        "remote_root_key",
        "child_descriptors_json",
        "rollback_pin_expires_at",
        "rollback_pin_reason",
        "failure_note",
        "created_at",
        "updated_at",
    }
    assert artifact._meta.ordering == ["-created_at"]
    assert snapshot._meta.ordering == ["-created_at"]
    assert policy._meta.get_field("key").unique is True
    assert artifact._meta.get_field("filename").unique is True
    assert snapshot._meta.get_field("snapshot_id").unique is True
    assert artifact._meta.get_field("initiated_by").remote_field.on_delete.__name__ == (
        "SET_NULL"
    )
    assert snapshot._meta.get_field("authoritative_dump").unique is True
    assert set(connection.introspection.table_names()) >= {
        "quickscale_modules_backups_policy",
        "quickscale_modules_backups_artifact",
        "quickscale_modules_backups_snapshot",
    }
