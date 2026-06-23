"""Focused tests for DR-oriented backup snapshot services."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from django.conf import settings

from quickscale_modules_backups.models import (
    BackupArtifact,
    BackupPolicy,
    BackupSnapshot,
)
from quickscale_modules_backups.services import (
    BackupConfigurationError,
    create_backup,
    record_backup_snapshot_verification,
    report_backup_snapshot,
    sync_backup_snapshot_media,
)


def _get_authoritative_snapshot(artifact: BackupArtifact) -> BackupSnapshot:
    """Load the snapshot linked to one authoritative dump artifact."""
    return BackupSnapshot.objects.get(authoritative_dump=artifact)


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
    snapshot = _get_authoritative_snapshot(artifact)

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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backup_policy.local_directory = str(local_backup_settings)
    backup_policy.save(update_fields=["local_directory", "updated_at"])
    media_root = local_backup_settings.parent / "media-root"
    media_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "MEDIA_ROOT", str(media_root))
    superuser = django_user_model.objects.create_superuser(
        username="backup-verify",
        email="verify@example.com",
        password="password123",
    )

    artifact = create_backup(initiated_by=superuser, trigger="manual")
    snapshot = _get_authoritative_snapshot(artifact)

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
    assert verification_payload["full_backup"]["status"] == "complete"
    assert (
        verification_payload["full_backup"]["provenance"]["source_environment"]
        == "local"
    )
    assert verification_payload["reports"][-1]["route"] == "local-to-railway-develop"
    assert verification_payload["reports"][-1]["phase"] == "plan"
    assert verification_payload["reports"][-1]["full_backup"]["status"] == "complete"
    assert (
        verification_payload["reports"][-1]["payload"]["database"]["status"] == "ready"
    )
    assert (
        report["sidecar_payloads"]["promotion-verification.json"]["reports"][-1][
            "status"
        ]
        == "manual_required"
    )
    assert report["full_backup"]["status"] == "complete"


def test_record_backup_snapshot_verification_reports_incomplete_full_backup_contract(
    django_user_model: type[Any],
    backup_policy: BackupPolicy,
    local_backup_settings: Path,
) -> None:
    backup_policy.local_directory = str(local_backup_settings)
    backup_policy.save(update_fields=["local_directory", "updated_at"])
    superuser = django_user_model.objects.create_superuser(
        username="backup-verify-incomplete",
        email="verify-incomplete@example.com",
        password="password123",
    )

    artifact = create_backup(initiated_by=superuser, trigger="manual")
    snapshot = _get_authoritative_snapshot(artifact)
    release_metadata_path = Path(snapshot.local_root_path) / "release-metadata.json"
    release_metadata_path.unlink()

    report = record_backup_snapshot_verification(
        snapshot.snapshot_id,
        route="local-to-railway-develop",
        phase="execute",
        status="manual_required",
        payload={"database": {"status": "ready"}},
    )

    verification_payload = json.loads(
        (Path(snapshot.local_root_path) / "promotion-verification.json").read_text(
            encoding="utf-8"
        )
    )

    assert verification_payload["full_backup"]["status"] == "incomplete"
    assert verification_payload["full_backup"]["completeness"]["status"] == (
        "incomplete"
    )
    assert any(
        "release-metadata.json" in issue
        for issue in verification_payload["full_backup"]["completeness"]["issues"]
    )
    assert verification_payload["full_backup"]["provenance"]["status"] == (
        "inconsistent"
    )
    assert any(
        "release-metadata.json" in issue
        for issue in verification_payload["full_backup"]["provenance"]["issues"]
    )
    assert verification_payload["reports"][-1]["full_backup"]["status"] == (
        "incomplete"
    )
    assert report["full_backup"]["status"] == "incomplete"


def test_sync_backup_snapshot_media_rejects_railway_target_via_explicit_settings(
    django_user_model: type[Any],
    backup_policy: BackupPolicy,
    local_backup_settings: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Regression test for CR-001: adapter path must preserve Railway-target guard.

    When ``target_runtime_settings`` is passed explicitly (adapter path)
    with ``ROUTE_KIND=railway`` but a local target backend, the service
    must still fail closed.
    """
    backup_policy.local_directory = str(local_backup_settings)
    backup_policy.save(update_fields=["local_directory", "updated_at"])

    source_media_root = tmp_path / "source-media"
    source_media_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "MEDIA_ROOT", str(source_media_root))
    monkeypatch.setenv("QUICKSCALE_STORAGE_BACKEND", "local")

    superuser = django_user_model.objects.create_superuser(
        username="backup-media-adapter",
        email="media-adapter@example.com",
        password="password123",
    )
    artifact = create_backup(initiated_by=superuser, trigger="manual")
    snapshot = _get_authoritative_snapshot(artifact)

    target_media_root = tmp_path / "target-media-adapter"
    target_media_root.mkdir(parents=True, exist_ok=True)

    with pytest.raises(
        BackupConfigurationError,
        match=(
            "Railway-target media sync requires an s3-compatible target media backend"
        ),
    ):
        sync_backup_snapshot_media(
            snapshot.snapshot_id,
            dry_run=True,
            target_runtime_settings={
                "ROUTE_KIND": "railway",
                "QUICKSCALE_STORAGE_BACKEND": "local",
                "MEDIA_ROOT": str(target_media_root),
            },
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
    snapshot = _get_authoritative_snapshot(artifact)

    target_media_root = tmp_path / "target-media"
    target_settings = {
        "QUICKSCALE_STORAGE_BACKEND": "local",
        "MEDIA_ROOT": str(target_media_root),
    }

    dry_run_result = sync_backup_snapshot_media(
        snapshot.snapshot_id, dry_run=True, target_runtime_settings=target_settings
    )
    execute_result = sync_backup_snapshot_media(
        snapshot.snapshot_id, dry_run=False, target_runtime_settings=target_settings
    )

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
    snapshot = _get_authoritative_snapshot(artifact)

    target_media_root = tmp_path / f"target-media-{int(dry_run)}"
    target_media_root.mkdir(parents=True, exist_ok=True)
    target_settings = {
        "ROUTE_KIND": "railway",
        "QUICKSCALE_STORAGE_BACKEND": "local",
        "MEDIA_ROOT": str(target_media_root),
    }

    with pytest.raises(
        BackupConfigurationError,
        match=(
            "Railway-target media sync requires an s3-compatible target media backend"
        ),
    ):
        sync_backup_snapshot_media(
            snapshot.snapshot_id,
            dry_run=dry_run,
            target_runtime_settings=target_settings,
        )
