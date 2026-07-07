"""Tests for backups module management commands."""

from __future__ import annotations

import json
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from quickscale_modules_backups.models import BackupArtifact
from quickscale_core.runtime import BackupError


def test_backups_create_command_reports_created_artifact() -> None:
    stdout = StringIO()
    report = {
        "snapshot_id": "snap-123",
        "status": "ready",
        "local_root_path": "/tmp/backups/snap-123",
        "failure_note": "",
        "authoritative_dump": {
            "artifact_id": 42,
            "filename": "db-20260402.dump",
            "local_path": "/tmp/db-20260402.dump",
            "remote_key": "ops/backups/db-20260402.dump",
        },
    }
    mock_capture = MagicMock(return_value=report)

    with patch.dict(
        "quickscale_core.runtime.ADAPTER_FUNCTIONS",
        {"capture_snapshot": mock_capture},
    ):
        call_command("backups_create", stdout=stdout, stderr=StringIO())

    mock_capture.assert_called_once_with(trigger="manual")
    assert stdout.getvalue() == (
        "Created backup db-20260402.dump\n"
        "Artifact id: 42\n"
        "Snapshot id: snap-123\n"
        "Snapshot status: ready\n"
        "Snapshot root: /tmp/backups/snap-123\n"
        "Local path: /tmp/db-20260402.dump\n"
        "Remote key: ops/backups/db-20260402.dump\n"
    )


def test_backups_create_command_routes_scheduled_trigger() -> None:
    stdout = StringIO()
    report = {
        "snapshot_id": "snap-777",
        "status": "ready",
        "local_root_path": "/tmp/backups/snap-777",
        "failure_note": "",
        "authoritative_dump": {
            "artifact_id": 7,
            "filename": "db-20260402.dump",
            "local_path": "/tmp/db-20260402.dump",
            "remote_key": "",
        },
    }
    mock_capture = MagicMock(return_value=report)

    with patch.dict(
        "quickscale_core.runtime.ADAPTER_FUNCTIONS",
        {"capture_snapshot": mock_capture},
    ):
        call_command(
            "backups_create",
            "--scheduled",
            stdout=stdout,
            stderr=StringIO(),
        )

    mock_capture.assert_called_once_with(trigger="scheduled")
    assert stdout.getvalue() == (
        "Created backup db-20260402.dump\n"
        "Artifact id: 7\n"
        "Snapshot id: snap-777\n"
        "Snapshot status: ready\n"
        "Snapshot root: /tmp/backups/snap-777\n"
        "Local path: /tmp/db-20260402.dump\n"
    )


# ---------------------------------------------------------------------------
# CR-SA37-001: regression — async admin dispatching must preserve
# trigger="admin" instead of falling back to "manual"
# ---------------------------------------------------------------------------


def test_backups_create_command_routes_admin_trigger() -> None:
    """``backups_create --trigger admin`` preserves admin provenance.

    CR-SA37-001: ``dispatch_background_create(trigger="admin")`` spawns
    ``backups_create --trigger admin``.  The management command must pass
    ``trigger="admin"`` through to the adapter so the resulting artifact
    records admin provenance instead of silently falling back to
    ``"manual"``.
    """
    stdout = StringIO()
    report = {
        "snapshot_id": "snap-admin",
        "status": "ready",
        "local_root_path": "/tmp/backups/snap-admin",
        "failure_note": "",
        "authoritative_dump": {
            "artifact_id": 99,
            "filename": "db-admin-trigger.dump",
            "local_path": "/tmp/db-admin-trigger.dump",
            "remote_key": "",
        },
    }
    mock_capture = MagicMock(return_value=report)

    with patch.dict(
        "quickscale_core.runtime.ADAPTER_FUNCTIONS",
        {"capture_snapshot": mock_capture},
    ):
        call_command(
            "backups_create",
            "--trigger",
            "admin",
            stdout=stdout,
            stderr=StringIO(),
        )

    mock_capture.assert_called_once_with(trigger="admin")
    assert stdout.getvalue() == (
        "Created backup db-admin-trigger.dump\n"
        "Artifact id: 99\n"
        "Snapshot id: snap-admin\n"
        "Snapshot status: ready\n"
        "Snapshot root: /tmp/backups/snap-admin\n"
        "Local path: /tmp/db-admin-trigger.dump\n"
    )


def test_backups_create_command_routes_resume_snapshot_id() -> None:
    stdout = StringIO()
    report = {
        "snapshot_id": "snap-resume",
        "status": "ready",
        "local_root_path": "/tmp/backups/snap-resume",
        "failure_note": "",
        "authoritative_dump": {
            "artifact_id": 17,
            "filename": "db-20260402.dump",
            "local_path": "/tmp/db-20260402.dump",
            "remote_key": "",
        },
    }
    mock_capture = MagicMock(return_value=report)

    with patch.dict(
        "quickscale_core.runtime.ADAPTER_FUNCTIONS",
        {"capture_snapshot": mock_capture},
    ):
        call_command(
            "backups_create",
            "--resume",
            "snap-resume",
            stdout=stdout,
            stderr=StringIO(),
        )

    mock_capture.assert_called_once_with(
        trigger="manual",
        resume_snapshot_id="snap-resume",
    )
    assert stdout.getvalue() == (
        "Resumed backup db-20260402.dump\n"
        "Artifact id: 17\n"
        "Snapshot id: snap-resume\n"
        "Snapshot status: ready\n"
        "Snapshot root: /tmp/backups/snap-resume\n"
        "Local path: /tmp/db-20260402.dump\n"
    )


def test_backups_create_command_outputs_json_report() -> None:
    stdout = StringIO()
    report = {
        "snapshot_id": "snap-json",
        "status": "ready",
        "local_root_path": "/tmp/backups/snap-json",
        "failure_note": "",
        "authoritative_dump": {"artifact_id": 9, "filename": "db.dump"},
    }
    mock_capture = MagicMock(return_value=report)

    with patch.dict(
        "quickscale_core.runtime.ADAPTER_FUNCTIONS",
        {"capture_snapshot": mock_capture},
    ):
        call_command("backups_create", "--json", stdout=stdout, stderr=StringIO())

    assert json.loads(stdout.getvalue()) == report


def test_backups_create_command_wraps_backup_errors() -> None:
    mock_capture = MagicMock(side_effect=BackupError("pg_dump exploded"))

    with patch.dict(
        "quickscale_core.runtime.ADAPTER_FUNCTIONS",
        {"capture_snapshot": mock_capture},
    ):
        with pytest.raises(CommandError, match="pg_dump exploded"):
            call_command("backups_create", stdout=StringIO(), stderr=StringIO())


def test_backups_prune_command_reports_deleted_count() -> None:
    stdout = StringIO()
    mock_prune = MagicMock(return_value={"deleted_count": 3})

    with patch.dict(
        "quickscale_core.runtime.ADAPTER_FUNCTIONS",
        {"prune_backups": mock_prune},
    ):
        call_command("backups_prune", stdout=stdout, stderr=StringIO())

    mock_prune.assert_called_once_with()
    assert stdout.getvalue() == "Pruned 3 expired backup artifact(s)\n"


def test_backups_prune_command_wraps_backup_errors() -> None:
    mock_prune = MagicMock(side_effect=BackupError("prune backend unavailable"))

    with patch.dict(
        "quickscale_core.runtime.ADAPTER_FUNCTIONS",
        {"prune_backups": mock_prune},
    ):
        with pytest.raises(CommandError, match="prune backend unavailable"):
            call_command("backups_prune", stdout=StringIO(), stderr=StringIO())


@pytest.mark.django_db
def test_backups_validate_command_requires_existing_artifact() -> None:
    mock_validate = MagicMock(
        side_effect=BackupError("Backup artifact not found: 999999")
    )
    with patch.dict(
        "quickscale_core.runtime.ADAPTER_FUNCTIONS",
        {"validate_artifact": mock_validate},
    ):
        with pytest.raises(CommandError, match="Backup artifact not found"):
            call_command(
                "backups_validate", "999999", stdout=StringIO(), stderr=StringIO()
            )


@pytest.mark.django_db
def test_backups_validate_command_reports_validation_issues(
    backup_artifact: BackupArtifact,
) -> None:
    mock_validate = MagicMock(
        return_value={
            "artifact_id": backup_artifact.pk,
            "issues": ["checksum mismatch detected", "size mismatch detected"],
            "valid": False,
        }
    )
    with patch.dict(
        "quickscale_core.runtime.ADAPTER_FUNCTIONS",
        {"validate_artifact": mock_validate},
    ):
        with pytest.raises(
            CommandError,
            match="checksum mismatch detected; size mismatch detected",
        ):
            call_command(
                "backups_validate",
                str(backup_artifact.pk),
                stdout=StringIO(),
                stderr=StringIO(),
            )

    mock_validate.assert_called_once_with(artifact_id=backup_artifact.pk)


@pytest.mark.django_db
def test_backups_validate_command_reports_success(
    backup_artifact: BackupArtifact,
) -> None:
    stdout = StringIO()
    mock_validate = MagicMock(
        return_value={
            "artifact_id": backup_artifact.pk,
            "issues": [],
            "valid": True,
        }
    )
    with patch.dict(
        "quickscale_core.runtime.ADAPTER_FUNCTIONS",
        {"validate_artifact": mock_validate},
    ):
        call_command(
            "backups_validate",
            str(backup_artifact.pk),
            stdout=stdout,
            stderr=StringIO(),
        )

    mock_validate.assert_called_once_with(artifact_id=backup_artifact.pk)
    assert stdout.getvalue() == f"Validated artifact {backup_artifact.pk}\n"


def test_backups_report_command_renders_snapshot_summary() -> None:
    stdout = StringIO()
    mock_report = MagicMock(
        return_value={
            "snapshot_id": "snap-report",
            "status": "ready",
            "source_environment": "local",
            "confirmation_value": "db-20260402.dump",
            "local_root_path": "/tmp/backups/snap-report",
            "remote_root_key": "ops/backups/snapshots/snap-report",
            "failure_note": "",
            "authoritative_dump": {
                "artifact_id": 12,
                "filename": "db-20260402.dump",
            },
            "rollback_pin": {
                "active": True,
                "expires_at": "2026-04-06T18:00:00+00:00",
                "reason": "production rollback window",
            },
            "sidecar_summary": {
                "media-sync-manifest.json": {
                    "kind": "media_sync_manifest",
                    "status": "ready",
                    "manifest_status": "ready",
                }
            },
        }
    )

    with patch.dict(
        "quickscale_core.runtime.ADAPTER_FUNCTIONS",
        {"fetch_snapshot_report": mock_report},
    ):
        call_command("backups_report", "snap-report", stdout=stdout, stderr=StringIO())

    mock_report.assert_called_once_with("snap-report", sidecar_payloads=[])
    assert stdout.getvalue() == (
        "Snapshot id: snap-report\n"
        "Status: ready\n"
        "Source environment: local\n"
        "Artifact id: 12\n"
        "Filename: db-20260402.dump\n"
        "Confirmation value: db-20260402.dump\n"
        "Local root: /tmp/backups/snap-report\n"
        "Remote root: ops/backups/snapshots/snap-report\n"
        "Rollback pin active: true\n"
        "Rollback pin expires at: 2026-04-06T18:00:00+00:00\n"
        "Rollback pin reason: production rollback window\n"
        "Sidecar media-sync-manifest.json: ready (ready)\n"
    )


def test_backups_pin_command_sets_rollback_pin() -> None:
    stdout = StringIO()
    mock_pin = MagicMock(
        return_value={
            "snapshot_id": "snap-pin",
            "rollback_pin": {
                "active": True,
                "expires_at": "2026-04-06T18:00:00+00:00",
                "reason": "production rollback window",
            },
        }
    )

    with patch.dict(
        "quickscale_core.runtime.ADAPTER_FUNCTIONS",
        {"set_rollback_pin": mock_pin},
    ):
        call_command(
            "backups_pin",
            "snap-pin",
            "--hours",
            "6",
            "--reason",
            "production rollback window",
            stdout=stdout,
            stderr=StringIO(),
        )

    mock_pin.assert_called_once_with(
        snapshot_id="snap-pin",
        hours=6,
        reason="production rollback window",
    )
    assert stdout.getvalue() == (
        "Pinned snapshot snap-pin\n"
        "Rollback pin active: true\n"
        "Rollback pin expires at: 2026-04-06T18:00:00+00:00\n"
        "Rollback pin reason: production rollback window\n"
    )


def test_backups_pin_command_clears_rollback_pin() -> None:
    stdout = StringIO()
    mock_clear = MagicMock(
        return_value={
            "snapshot_id": "snap-pin",
            "rollback_pin": {
                "active": False,
                "expires_at": None,
                "reason": "",
            },
        }
    )

    with patch.dict(
        "quickscale_core.runtime.ADAPTER_FUNCTIONS",
        {"clear_rollback_pin": mock_clear},
    ):
        call_command(
            "backups_pin",
            "snap-pin",
            "--clear",
            stdout=stdout,
            stderr=StringIO(),
        )

    mock_clear.assert_called_once_with(snapshot_id="snap-pin")
    assert stdout.getvalue() == (
        "Cleared rollback pin for snapshot snap-pin\n"
        "Rollback pin active: false\n"
        "Rollback pin expires at: none\n"
        "Rollback pin reason: none\n"
    )
