"""Tests for backups module migrations."""

from __future__ import annotations

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

pytestmark = pytest.mark.django_db(transaction=True)


def _create_legacy_artifact(
    backup_artifact_model,
    *,
    filename: str,
    backup_format: str,
    metadata_json: dict[str, object],
) -> None:
    database_engine = (
        "django.db.backends.postgresql"
        if backup_format == "pg_dump_custom"
        else "django.db.backends.sqlite3"
    )
    backup_artifact_model.objects.create(
        filename=filename,
        checksum_sha256="abc123",
        size_bytes=1,
        backup_format=backup_format,
        database_engine=database_engine,
        database_name="quickscale_test",
        metadata_json=metadata_json,
    )


def test_backfill_restore_scope_and_version_fields_for_legacy_artifacts() -> None:
    migrate_from = (
        "quickscale_modules_backups",
        "0002_backupartifact_remote_storage_context",
    )
    migrate_to = (
        "quickscale_modules_backups",
        "0003_backupartifact_restore_scope_and_versions",
    )

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_from])
    old_apps = executor.loader.project_state([migrate_from]).apps
    legacy_backup_artifact = old_apps.get_model(
        "quickscale_modules_backups", "BackupArtifact"
    )

    _create_legacy_artifact(
        legacy_backup_artifact,
        filename="legacy-export.json",
        backup_format="json",
        metadata_json={"database_server_version": "3.45.1"},
    )
    _create_legacy_artifact(
        legacy_backup_artifact,
        filename="legacy-local.dump",
        backup_format="pg_dump_custom",
        metadata_json={
            "database_server_version": "18.3 (Debian 18.3-1)",
            "pg_dump_version": "18.1 (PostgreSQL)",
        },
    )
    _create_legacy_artifact(
        legacy_backup_artifact,
        filename="legacy-runtime-shaped.dump",
        backup_format="pg_dump_custom",
        metadata_json={
            "database_server_version": "18.3 (Debian 18.3-1)",
            "pg_dump_version": "pg_dump (PostgreSQL) 18.4 (Debian 18.4-1)",
        },
    )
    _create_legacy_artifact(
        legacy_backup_artifact,
        filename="legacy-uncertain.dump",
        backup_format="pg_dump_custom",
        metadata_json={
            "database_server_version": "server major unavailable",
            "pg_dump_version": "pg_dump (PostgreSQL)",
        },
    )

    executor = MigrationExecutor(connection)
    executor.migrate([migrate_to])
    new_apps = executor.loader.project_state([migrate_to]).apps
    migrated_backup_artifact = new_apps.get_model(
        "quickscale_modules_backups", "BackupArtifact"
    )

    export_artifact = migrated_backup_artifact.objects.get(
        filename="legacy-export.json"
    )
    local_artifact = migrated_backup_artifact.objects.get(filename="legacy-local.dump")
    runtime_shaped_artifact = migrated_backup_artifact.objects.get(
        filename="legacy-runtime-shaped.dump"
    )
    uncertain_artifact = migrated_backup_artifact.objects.get(
        filename="legacy-uncertain.dump"
    )

    assert export_artifact.restore_scope == "export_only"
    assert export_artifact.database_server_major == 3
    assert export_artifact.dump_client_major is None

    assert local_artifact.restore_scope == "local_only"
    assert local_artifact.database_server_major == 18
    assert local_artifact.dump_client_major == 18

    assert runtime_shaped_artifact.restore_scope == "local_only"
    assert runtime_shaped_artifact.database_server_major == 18
    assert runtime_shaped_artifact.dump_client_major == 18

    assert uncertain_artifact.restore_scope == "local_only"
    assert uncertain_artifact.database_server_major is None
    assert uncertain_artifact.dump_client_major is None
