"""Focused tests for DR-oriented backups management commands."""

from __future__ import annotations

import json
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from quickscale_core.runtime import BackupError


def test_backups_report_command_requests_sidecar_payloads() -> None:
    stdout = StringIO()
    mock_report = MagicMock(
        return_value={
            "snapshot_id": "snap-report",
            "status": "ready",
            "source_environment": "local",
            "confirmation_value": "db.dump",
            "local_root_path": "/tmp/backups/snap-report",
            "remote_root_key": "",
            "failure_note": "",
            "authoritative_dump": {"artifact_id": 1, "filename": "db.dump"},
            "rollback_pin": {"active": False, "expires_at": None, "reason": ""},
            "sidecar_summary": {},
            "sidecar_payloads": {"promotion-verification.json": {"reports": []}},
            "sidecar_payload_errors": {},
        }
    )

    with patch.dict(
        "quickscale_core.runtime.ADAPTER_FUNCTIONS",
        {"fetch_snapshot_report": mock_report},
    ):
        call_command(
            "backups_report",
            "snap-report",
            "--json",
            "--sidecar-payload",
            "promotion-verification.json",
            stdout=stdout,
            stderr=StringIO(),
        )

    mock_report.assert_called_once_with(
        "snap-report",
        sidecar_payloads=["promotion-verification.json"],
    )
    assert json.loads(stdout.getvalue())["sidecar_payloads"][
        "promotion-verification.json"
    ] == {"reports": []}


def test_backups_record_verification_command_records_route_report() -> None:
    stdout = StringIO()
    mock_record = MagicMock(return_value={"snapshot_id": "snap-verify"})

    with patch.dict(
        "quickscale_core.runtime.ADAPTER_FUNCTIONS",
        {"record_verification": mock_record},
    ):
        call_command(
            "backups_record_verification",
            "snap-verify",
            "--route",
            "local-to-railway-develop",
            "--phase",
            "plan",
            "--status",
            "ready",
            "--payload-json",
            '{"database": {"status": "ready"}}',
            stdout=stdout,
            stderr=StringIO(),
        )

    mock_record.assert_called_once_with(
        snapshot_id="snap-verify",
        route="local-to-railway-develop",
        phase="plan",
        status="ready",
        payload={"database": {"status": "ready"}},
    )
    assert stdout.getvalue() == (
        "Recorded plan verification for snapshot snap-verify\n"
        "Status: ready\n"
        "Route: local-to-railway-develop\n"
    )


def test_backups_sync_media_command_outputs_json_result() -> None:
    stdout = StringIO()
    mock_sync = MagicMock(
        return_value={
            "snapshot_id": "snap-media",
            "status": "ready",
            "strategy": "local_to_s3",
            "planned_count": 3,
            "copied_count": 0,
            "missing_paths": [],
        }
    )

    with patch.dict(
        "quickscale_core.runtime.ADAPTER_FUNCTIONS",
        {"sync_media": mock_sync},
    ):
        call_command(
            "backups_sync_media",
            "snap-media",
            "--dry-run",
            "--json",
            stdout=stdout,
            stderr=StringIO(),
        )

    mock_sync.assert_called_once_with(
        "snap-media", dry_run=True, target_runtime_settings={}
    )
    assert json.loads(stdout.getvalue())["strategy"] == "local_to_s3"


@pytest.mark.parametrize(
    ("command_args", "message"),
    [
        (("snap-pin",), "--hours is required when setting a rollback pin."),
        (
            ("snap-pin", "--hours", "6"),
            "--reason is required when setting a rollback pin.",
        ),
        (
            ("snap-pin", "--clear", "--hours", "6"),
            "--clear cannot be combined with --hours or --reason.",
        ),
    ],
)
def test_backups_pin_command_validates_arguments(
    command_args: tuple[str, ...],
    message: str,
) -> None:
    with pytest.raises(CommandError, match=message):
        call_command(
            "backups_pin",
            *command_args,
            stdout=StringIO(),
            stderr=StringIO(),
        )


def test_backups_pin_command_outputs_json_report() -> None:
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
            "--json",
            stdout=stdout,
            stderr=StringIO(),
        )

    mock_pin.assert_called_once_with(
        snapshot_id="snap-pin",
        hours=6,
        reason="production rollback window",
    )
    assert json.loads(stdout.getvalue()) == {
        "snapshot_id": "snap-pin",
        "rollback_pin": {
            "active": True,
            "expires_at": "2026-04-06T18:00:00+00:00",
            "reason": "production rollback window",
        },
    }


def test_backups_pin_command_wraps_service_errors() -> None:
    mock_clear = MagicMock(side_effect=BackupError("clear exploded"))
    with patch.dict(
        "quickscale_core.runtime.ADAPTER_FUNCTIONS",
        {"clear_rollback_pin": mock_clear},
    ):
        with pytest.raises(CommandError, match="clear exploded"):
            call_command(
                "backups_pin",
                "snap-pin",
                "--clear",
                stdout=StringIO(),
                stderr=StringIO(),
            )

    mock_set = MagicMock(side_effect=BackupError("set exploded"))
    with patch.dict(
        "quickscale_core.runtime.ADAPTER_FUNCTIONS",
        {"set_rollback_pin": mock_set},
    ):
        with pytest.raises(CommandError, match="set exploded"):
            call_command(
                "backups_pin",
                "snap-pin",
                "--hours",
                "6",
                "--reason",
                "production rollback window",
                stdout=StringIO(),
                stderr=StringIO(),
            )


@pytest.mark.parametrize("payload_json", ["not-json", "[]"])
def test_backups_record_verification_command_rejects_non_object_payload(
    payload_json: str,
) -> None:
    with pytest.raises(CommandError, match="--payload-json must be a JSON object."):
        call_command(
            "backups_record_verification",
            "snap-verify",
            "--route",
            "local-to-railway-develop",
            "--phase",
            "plan",
            "--status",
            "ready",
            "--payload-json",
            payload_json,
            stdout=StringIO(),
            stderr=StringIO(),
        )


def test_backups_record_verification_command_outputs_json_report() -> None:
    stdout = StringIO()
    mock_record = MagicMock(
        return_value={
            "snapshot_id": "snap-verify",
            "status": "ready",
            "sidecar_payloads": {"promotion-verification.json": {"reports": []}},
        }
    )

    with patch.dict(
        "quickscale_core.runtime.ADAPTER_FUNCTIONS",
        {"record_verification": mock_record},
    ):
        call_command(
            "backups_record_verification",
            "snap-verify",
            "--route",
            "local-to-railway-develop",
            "--phase",
            "execute",
            "--status",
            "completed",
            "--payload-json",
            '{"media": {"status": "completed"}}',
            "--json",
            stdout=stdout,
            stderr=StringIO(),
        )

    mock_record.assert_called_once_with(
        snapshot_id="snap-verify",
        route="local-to-railway-develop",
        phase="execute",
        status="completed",
        payload={"media": {"status": "completed"}},
    )
    assert json.loads(stdout.getvalue()) == {
        "snapshot_id": "snap-verify",
        "status": "ready",
        "sidecar_payloads": {"promotion-verification.json": {"reports": []}},
    }


def test_backups_record_verification_command_wraps_service_errors() -> None:
    mock_record = MagicMock(side_effect=BackupError("verification exploded"))
    with patch.dict(
        "quickscale_core.runtime.ADAPTER_FUNCTIONS",
        {"record_verification": mock_record},
    ):
        with pytest.raises(CommandError, match="verification exploded"):
            call_command(
                "backups_record_verification",
                "snap-verify",
                "--route",
                "local-to-railway-develop",
                "--phase",
                "plan",
                "--status",
                "ready",
                "--payload-json",
                '{"database": {"status": "ready"}}',
                stdout=StringIO(),
                stderr=StringIO(),
            )


@pytest.mark.parametrize(
    ("command_args", "result_payload", "expected_output"),
    [
        (
            ("--dry-run",),
            {
                "snapshot_id": "snap-media",
                "status": "ready",
                "strategy": "local_to_local",
                "planned_count": 3,
                "copied_count": 0,
                "missing_paths": [],
            },
            (
                "Validated media for snapshot snap-media\n"
                "Status: ready\n"
                "Strategy: local_to_local\n"
                "Planned count: 3\n"
                "Copied count: 0\n"
                "Missing paths: 0\n"
            ),
        ),
        (
            tuple(),
            {
                "snapshot_id": "snap-media",
                "status": "completed",
                "strategy": "local_to_local",
                "planned_count": 3,
                "copied_count": 3,
                "missing_paths": [],
            },
            (
                "Synced media for snapshot snap-media\n"
                "Status: completed\n"
                "Strategy: local_to_local\n"
                "Planned count: 3\n"
                "Copied count: 3\n"
                "Missing paths: 0\n"
            ),
        ),
    ],
)
def test_backups_sync_media_command_renders_summary(
    command_args: tuple[str, ...],
    result_payload: dict[str, object],
    expected_output: str,
) -> None:
    stdout = StringIO()
    mock_sync = MagicMock(return_value=result_payload)

    with patch.dict(
        "quickscale_core.runtime.ADAPTER_FUNCTIONS",
        {"sync_media": mock_sync},
    ):
        call_command(
            "backups_sync_media",
            "snap-media",
            *command_args,
            stdout=stdout,
            stderr=StringIO(),
        )

    mock_sync.assert_called_once_with(
        "snap-media",
        dry_run="--dry-run" in command_args,
        target_runtime_settings={},
    )
    assert stdout.getvalue() == expected_output


def test_backups_sync_media_command_wraps_service_errors() -> None:
    mock_sync = MagicMock(side_effect=BackupError("media sync exploded"))
    with patch.dict(
        "quickscale_core.runtime.ADAPTER_FUNCTIONS",
        {"sync_media": mock_sync},
    ):
        with pytest.raises(CommandError, match="media sync exploded"):
            call_command(
                "backups_sync_media",
                "snap-media",
                "--dry-run",
                stdout=StringIO(),
                stderr=StringIO(),
            )
