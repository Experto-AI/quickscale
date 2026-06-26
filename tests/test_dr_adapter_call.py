"""Focused tests for the dr_adapter_call management command bridge."""

from __future__ import annotations

import json
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from quickscale_modules_backups.management.commands.dr_adapter_call import Command


def test_dr_adapter_call_dispatches_registered_function_and_renders_json() -> None:
    stdout = StringIO()
    mock_adapter = MagicMock(
        return_value={
            "route_kind": "local-to-railway-develop",
            "snapshot_id": "snap-123",
            "status": "ready",
        }
    )

    with patch.dict(
        "quickscale_modules_backups.management.commands.dr_adapter_call.ADAPTER_FUNCTIONS",
        {"capture_snapshot": mock_adapter},
        clear=True,
    ):
        call_command(
            "dr_adapter_call",
            "capture_snapshot",
            "--args-json",
            '{"snapshot_id": "snap-123", "dry_run": true}',
            stdout=stdout,
            stderr=StringIO(),
        )

    mock_adapter.assert_called_once_with(snapshot_id="snap-123", dry_run=True)
    assert json.loads(stdout.getvalue()) == {
        "route_kind": "local-to-railway-develop",
        "snapshot_id": "snap-123",
        "status": "ready",
    }


@pytest.mark.parametrize(
    ("args_json", "message"),
    [
        ("not-json", "--args-json must be valid JSON:"),
        ("[]", "--args-json must be a JSON object."),
    ],
)
def test_dr_adapter_call_rejects_invalid_args_json(
    args_json: str,
    message: str,
) -> None:
    with pytest.raises(CommandError, match=message):
        call_command(
            "dr_adapter_call",
            "capture_snapshot",
            "--args-json",
            args_json,
            stdout=StringIO(),
            stderr=StringIO(),
        )


def test_dr_adapter_call_rejects_unknown_function() -> None:
    with patch.dict(
        "quickscale_modules_backups.management.commands.dr_adapter_call.ADAPTER_FUNCTIONS",
        {"capture_snapshot": MagicMock()},
        clear=True,
    ):
        with pytest.raises(
            CommandError,
            match="Unknown DR adapter function 'missing_function'. Available: capture_snapshot",
        ):
            call_command(
                "dr_adapter_call",
                "missing_function",
                "--args-json",
                "{}",
                stdout=StringIO(),
                stderr=StringIO(),
            )


def test_dr_adapter_call_returns_exit_code_one_for_adapter_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with patch.dict(
        "quickscale_modules_backups.management.commands.dr_adapter_call.ADAPTER_FUNCTIONS",
        {"capture_snapshot": MagicMock(side_effect=RuntimeError("adapter exploded"))},
        clear=True,
    ):
        with pytest.raises(SystemExit) as exc_info:
            Command().run_from_argv(
                [
                    "manage.py",
                    "dr_adapter_call",
                    "capture_snapshot",
                    "--args-json",
                    "{}",
                ]
            )

    assert exc_info.value.code == 1
    assert (
        "DR adapter 'capture_snapshot' failed: adapter exploded"
        in capsys.readouterr().err
    )
