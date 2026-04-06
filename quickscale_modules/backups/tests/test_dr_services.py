"""Focused tests for DR-oriented backup snapshot services."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from django.conf import settings

from quickscale_modules_backups.models import BackupPolicy
from quickscale_modules_backups.services import (
    BackupConfigurationError,
    create_backup,
    record_backup_snapshot_verification,
    report_backup_snapshot,
    sync_backup_snapshot_media,
)


def test_report_backup_snapshot_includes_requested_sidecar_payloads(
    django_user_model: type[Any],
    backup_policy: BackupPolicy,
    local_backup_settings: Path,
) -> None:
    backup_policy.local_directory = str(local_backup_settings)
    backup_policy.save(update_fields=["local_directory", "updated_at"])
    superuser = django_user_model.objects.create_superuser(
        username="backup-admin",
        email="admin@example.com",
        password="password123",
    )

    artifact = create_backup(initiated_by=superuser, trigger="manual")
    snapshot = artifact.authoritative_snapshot

    report = report_backup_snapshot(
        snapshot.snapshot_id,
        sidecar_payloads=["promotion-verification.json"],
    )

    assert report["sidecar_payloads"]["promotion-verification.json"]["reports"] == []
    assert report["sidecar_payload_errors"] == {}


def test_record_backup_snapshot_verification_appends_route_report(
    django_user_model: type[Any],
    backup_policy: BackupPolicy,
    local_backup_settings: Path,
) -> None:
    backup_policy.local_directory = str(local_backup_settings)
    backup_policy.save(update_fields=["local_directory", "updated_at"])
    superuser = django_user_model.objects.create_superuser(
        username="backup-verify",
        email="verify@example.com",
        password="password123",
    )

    artifact = create_backup(initiated_by=superuser, trigger="manual")
    snapshot = artifact.authoritative_snapshot

    report = record_backup_snapshot_verification(
        snapshot.snapshot_id,
        route="local-to-railway-develop",
        phase="plan",
        status="manual_required",
        payload={"database": {"status": "ready"}},
    )

    verification_payload = json.loads(
        (Path(snapshot.local_root_path) / "promotion-verification.json").read_text(
            encoding="utf-8"
        )
    )

    assert verification_payload["status"] == "manual_required"
    assert verification_payload["reports"][-1]["route"] == "local-to-railway-develop"
    assert verification_payload["reports"][-1]["phase"] == "plan"
    assert (
        verification_payload["reports"][-1]["payload"]["database"]["status"] == "ready"
    )
    assert (
        report["sidecar_payloads"]["promotion-verification.json"]["reports"][-1][
            "status"
        ]
        == "manual_required"
    )


def test_sync_backup_snapshot_media_supports_local_to_local_dry_run_and_execute(
    django_user_model: type[Any],
    backup_policy: BackupPolicy,
    local_backup_settings: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    backup_policy.local_directory = str(local_backup_settings)
    backup_policy.save(update_fields=["local_directory", "updated_at"])

    source_media_root = tmp_path / "source-media"
    source_media_root.mkdir(parents=True, exist_ok=True)
    relative_path = "blog/uploads/hero.png"
    source_file = source_media_root / relative_path
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_bytes(b"image-bytes")

    monkeypatch.setattr(settings, "MEDIA_ROOT", str(source_media_root))
    monkeypatch.setenv("QUICKSCALE_STORAGE_BACKEND", "local")

    superuser = django_user_model.objects.create_superuser(
        username="backup-media",
        email="media@example.com",
        password="password123",
    )
    artifact = create_backup(initiated_by=superuser, trigger="manual")
    snapshot = artifact.authoritative_snapshot

    target_media_root = tmp_path / "target-media"
    monkeypatch.setenv("QUICKSCALE_DR_TARGET_QUICKSCALE_STORAGE_BACKEND", "local")
    monkeypatch.setenv("QUICKSCALE_DR_TARGET_MEDIA_ROOT", str(target_media_root))

    dry_run_result = sync_backup_snapshot_media(snapshot.snapshot_id, dry_run=True)
    execute_result = sync_backup_snapshot_media(snapshot.snapshot_id, dry_run=False)

    assert dry_run_result["status"] == "ready"
    assert dry_run_result["planned_count"] == 1
    assert dry_run_result["strategy"] == "local_to_local"
    assert execute_result["status"] == "completed"
    assert execute_result["copied_count"] == 1
    assert (target_media_root / relative_path).read_bytes() == b"image-bytes"


@pytest.mark.parametrize("dry_run", [True, False])
def test_sync_backup_snapshot_media_rejects_railway_target_local_backend(
    dry_run: bool,
    django_user_model: type[Any],
    backup_policy: BackupPolicy,
    local_backup_settings: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    backup_policy.local_directory = str(local_backup_settings)
    backup_policy.save(update_fields=["local_directory", "updated_at"])

    source_media_root = tmp_path / "source-media"
    source_media_root.mkdir(parents=True, exist_ok=True)
    relative_path = "blog/uploads/hero.png"
    source_file = source_media_root / relative_path
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_bytes(b"image-bytes")

    monkeypatch.setattr(settings, "MEDIA_ROOT", str(source_media_root))
    monkeypatch.setenv("QUICKSCALE_STORAGE_BACKEND", "local")

    superuser = django_user_model.objects.create_superuser(
        username=f"backup-media-railway-{int(dry_run)}",
        email=f"media-railway-{int(dry_run)}@example.com",
        password="password123",
    )
    artifact = create_backup(initiated_by=superuser, trigger="manual")
    snapshot = artifact.authoritative_snapshot

    target_media_root = tmp_path / f"target-media-{int(dry_run)}"
    target_media_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("QUICKSCALE_DR_TARGET_ROUTE_KIND", "railway")
    monkeypatch.setenv("QUICKSCALE_DR_TARGET_QUICKSCALE_STORAGE_BACKEND", "local")
    monkeypatch.setenv("QUICKSCALE_DR_TARGET_MEDIA_ROOT", str(target_media_root))

    with pytest.raises(
        BackupConfigurationError,
        match=(
            "Railway-target media sync requires an s3-compatible target media backend"
        ),
    ):
        sync_backup_snapshot_media(snapshot.snapshot_id, dry_run=dry_run)
