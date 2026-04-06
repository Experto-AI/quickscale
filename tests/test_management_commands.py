"""Tests for backups module management commands."""

from __future__ import annotations

import json
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from quickscale_modules_backups.services import BackupError


def test_backups_create_command_reports_created_artifact() -> None:
    stdout = StringIO()
    snapshot_token = object()
    report = {
        "snapshot_id": "snap-123",
        "status": "ready",
        "local_root_path": "/tmp/backups/snap-123",
        "failure_note": "",
    }

    with (
        patch(
            "quickscale_modules_backups.management.commands.backups_create.create_backup",
            return_value=SimpleNamespace(
                filename="db-20260402.dump",
                pk=42,
                local_path="/tmp/db-20260402.dump",
                remote_key="ops/backups/db-20260402.dump",
                authoritative_snapshot=snapshot_token,
            ),
        ) as mocked_create,
        patch(
            "quickscale_modules_backups.management.commands.backups_create.build_backup_snapshot_report",
            return_value=report,
        ) as mocked_report,
    ):
        call_command("backups_create", stdout=stdout, stderr=StringIO())

    mocked_create.assert_called_once_with(trigger="manual")
    mocked_report.assert_called_once_with(snapshot_token)
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
    snapshot_token = object()
    report = {
        "snapshot_id": "snap-777",
        "status": "ready",
        "local_root_path": "/tmp/backups/snap-777",
        "failure_note": "",
    }

    with (
        patch(
            "quickscale_modules_backups.management.commands.backups_create.create_backup",
            return_value=SimpleNamespace(
                filename="db-20260402.dump",
                pk=7,
                local_path="/tmp/db-20260402.dump",
                remote_key="",
                authoritative_snapshot=snapshot_token,
            ),
        ) as mocked_create,
        patch(
            "quickscale_modules_backups.management.commands.backups_create.build_backup_snapshot_report",
            return_value=report,
        ) as mocked_report,
    ):
        call_command(
            "backups_create",
            "--scheduled",
            stdout=stdout,
            stderr=StringIO(),
        )

    mocked_create.assert_called_once_with(trigger="scheduled")
    mocked_report.assert_called_once_with(snapshot_token)
    assert stdout.getvalue() == (
        "Created backup db-20260402.dump\n"
        "Artifact id: 7\n"
        "Snapshot id: snap-777\n"
        "Snapshot status: ready\n"
        "Snapshot root: /tmp/backups/snap-777\n"
        "Local path: /tmp/db-20260402.dump\n"
    )


def test_backups_create_command_routes_resume_snapshot_id() -> None:
    stdout = StringIO()
    snapshot_token = object()
    report = {
        "snapshot_id": "snap-resume",
        "status": "ready",
        "local_root_path": "/tmp/backups/snap-resume",
        "failure_note": "",
    }

    with (
        patch(
            "quickscale_modules_backups.management.commands.backups_create.create_backup",
            return_value=SimpleNamespace(
                filename="db-20260402.dump",
                pk=17,
                local_path="/tmp/db-20260402.dump",
                remote_key="",
                authoritative_snapshot=snapshot_token,
            ),
        ) as mocked_create,
        patch(
            "quickscale_modules_backups.management.commands.backups_create.build_backup_snapshot_report",
            return_value=report,
        ) as mocked_report,
    ):
        call_command(
            "backups_create",
            "--resume",
            "snap-resume",
            stdout=stdout,
            stderr=StringIO(),
        )

    mocked_create.assert_called_once_with(
        trigger="manual",
        resume_snapshot_id="snap-resume",
    )
    mocked_report.assert_called_once_with(snapshot_token)
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
    snapshot_token = object()
    report = {
        "snapshot_id": "snap-json",
        "status": "ready",
        "local_root_path": "/tmp/backups/snap-json",
        "failure_note": "",
        "authoritative_dump": {"artifact_id": 9, "filename": "db.dump"},
    }

    with (
        patch(
            "quickscale_modules_backups.management.commands.backups_create.create_backup",
            return_value=SimpleNamespace(
                filename="db.dump",
                pk=9,
                local_path="/tmp/db.dump",
                remote_key="",
                authoritative_snapshot=snapshot_token,
            ),
        ),
        patch(
            "quickscale_modules_backups.management.commands.backups_create.build_backup_snapshot_report",
            return_value=report,
        ),
    ):
        call_command("backups_create", "--json", stdout=stdout, stderr=StringIO())

    assert json.loads(stdout.getvalue()) == report


def test_backups_create_command_wraps_backup_errors() -> None:
    with patch(
        "quickscale_modules_backups.management.commands.backups_create.create_backup",
        side_effect=BackupError("pg_dump exploded"),
    ):
        with pytest.raises(CommandError, match="pg_dump exploded"):
            call_command("backups_create", stdout=StringIO(), stderr=StringIO())


def test_backups_prune_command_reports_deleted_count() -> None:
    stdout = StringIO()

    with patch(
        "quickscale_modules_backups.management.commands.backups_prune.prune_expired_backups",
        return_value=3,
    ) as mocked_prune:
        call_command("backups_prune", stdout=stdout, stderr=StringIO())

    mocked_prune.assert_called_once_with()
    assert stdout.getvalue() == "Pruned 3 expired backup artifact(s)\n"


@pytest.mark.django_db
def test_backups_validate_command_requires_existing_artifact() -> None:
    with pytest.raises(CommandError, match="Backup artifact not found"):
        call_command("backups_validate", "999999", stdout=StringIO(), stderr=StringIO())


@pytest.mark.django_db
def test_backups_validate_command_reports_validation_issues(
    backup_artifact,
) -> None:
    with patch(
        "quickscale_modules_backups.management.commands.backups_validate.validate_backup_artifact",
        return_value=["checksum mismatch detected", "size mismatch detected"],
    ) as mocked_validate:
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

    mocked_validate.assert_called_once_with(backup_artifact)


@pytest.mark.django_db
def test_backups_validate_command_reports_success(backup_artifact) -> None:
    stdout = StringIO()

    with patch(
        "quickscale_modules_backups.management.commands.backups_validate.validate_backup_artifact",
        return_value=[],
    ) as mocked_validate:
        call_command(
            "backups_validate",
            str(backup_artifact.pk),
            stdout=stdout,
            stderr=StringIO(),
        )

    mocked_validate.assert_called_once_with(backup_artifact)
    assert stdout.getvalue() == f"Validated {backup_artifact.filename}\n"


def test_backups_report_command_renders_snapshot_summary() -> None:
    stdout = StringIO()

    with patch(
        "quickscale_modules_backups.management.commands.backups_report.report_backup_snapshot",
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
        },
    ) as mocked_report:
        call_command("backups_report", "snap-report", stdout=stdout, stderr=StringIO())

    mocked_report.assert_called_once_with("snap-report")
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

    with patch(
        "quickscale_modules_backups.management.commands.backups_pin.set_backup_snapshot_rollback_pin",
        return_value={
            "snapshot_id": "snap-pin",
            "rollback_pin": {
                "active": True,
                "expires_at": "2026-04-06T18:00:00+00:00",
                "reason": "production rollback window",
            },
        },
    ) as mocked_pin:
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

    mocked_pin.assert_called_once_with(
        "snap-pin",
        ttl_hours=6,
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

    with patch(
        "quickscale_modules_backups.management.commands.backups_pin.clear_backup_snapshot_rollback_pin",
        return_value={
            "snapshot_id": "snap-pin",
            "rollback_pin": {
                "active": False,
                "expires_at": None,
                "reason": "",
            },
        },
    ) as mocked_clear:
        call_command(
            "backups_pin",
            "snap-pin",
            "--clear",
            stdout=stdout,
            stderr=StringIO(),
        )

    mocked_clear.assert_called_once_with("snap-pin")
    assert stdout.getvalue() == (
        "Cleared rollback pin for snapshot snap-pin\n"
        "Rollback pin active: false\n"
        "Rollback pin expires at: none\n"
        "Rollback pin reason: none\n"
    )
