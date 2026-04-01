"""Shared pytest fixtures for the backups module."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import TYPE_CHECKING

import django
import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")
django.setup()

if TYPE_CHECKING:
    from quickscale_modules_backups.models import BackupArtifact, BackupPolicy


@pytest.fixture
def superuser(db):
    """Return a superuser for admin and service tests."""
    user_model = get_user_model()
    return user_model.objects.create_superuser(
        username="backups-admin",
        email="backups-admin@example.com",
        password="adminpass123",
    )


@pytest.fixture
def admin_client(superuser) -> Client:
    """Return an authenticated Django test client for admin tests."""
    client = Client()
    client.force_login(superuser)
    return client


@pytest.fixture
def backup_policy(db) -> "BackupPolicy":
    """Return the default backup policy row."""
    from quickscale_modules_backups.models import BackupPolicy

    return BackupPolicy.objects.create(
        retention_days=14,
        naming_prefix="db",
        target_mode=BackupPolicy.TARGET_MODE_LOCAL,
        local_directory=".quickscale/backups",
        automation_enabled=False,
        schedule="0 2 * * *",
    )


@pytest.fixture
def artifact_file(tmp_path: Path) -> Path:
    """Return a filesystem path with sample artifact content."""
    path = tmp_path / "sample-backup.json"
    path.write_text("[]", encoding="utf-8")
    return path


@pytest.fixture
def postgresql_artifact_file(tmp_path: Path) -> Path:
    """Return a filesystem path with sample pg_dump-style artifact content."""
    path = tmp_path / "sample-backup.dump"
    path.write_bytes(b"pg_dump_custom_artifact")
    return path


@pytest.fixture
def backup_artifact(db, artifact_file: Path, superuser) -> "BackupArtifact":
    """Return a backup artifact pointing at a real local file."""
    from quickscale_modules_backups.models import BackupArtifact

    return BackupArtifact.objects.create(
        filename=artifact_file.name,
        local_path=str(artifact_file),
        checksum_sha256=hashlib.sha256(artifact_file.read_bytes()).hexdigest(),
        size_bytes=artifact_file.stat().st_size,
        backup_format="json",
        database_engine="django.db.backends.sqlite3",
        database_name="test.sqlite3",
        metadata_json={"environment": "test"},
        initiated_by=superuser,
    )


@pytest.fixture
def postgresql_backup_artifact(
    db,
    postgresql_artifact_file: Path,
    superuser,
) -> "BackupArtifact":
    """Return a PostgreSQL custom-format artifact pointing at a real local file."""
    from quickscale_modules_backups.models import BackupArtifact

    return BackupArtifact.objects.create(
        filename=postgresql_artifact_file.name,
        local_path=str(postgresql_artifact_file),
        checksum_sha256=hashlib.sha256(
            postgresql_artifact_file.read_bytes()
        ).hexdigest(),
        size_bytes=postgresql_artifact_file.stat().st_size,
        backup_format="pg_dump_custom",
        restore_scope=BackupArtifact.RESTORE_SCOPE_LOCAL_ONLY,
        database_engine="django.db.backends.postgresql",
        database_name="quickscale_test",
        database_server_major=18,
        dump_client_major=18,
        metadata_json={
            "environment": "test",
            "database_server_version": "18.3 (Debian 18.3-1)",
            "database_server_major": 18,
            "pg_dump_version": "pg_dump (PostgreSQL) 18.4",
            "dump_client_major": 18,
        },
        initiated_by=superuser,
    )


@pytest.fixture
def local_backup_settings(tmp_path: Path):
    """Override backup settings so services write into a temporary directory."""
    backup_dir = tmp_path / "private-backups"
    with override_settings(
        BASE_DIR=tmp_path,
        QUICKSCALE_BACKUPS_LOCAL_DIRECTORY=str(backup_dir),
        QUICKSCALE_BACKUPS_TARGET_MODE="local",
    ):
        yield backup_dir
