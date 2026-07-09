"""Focused tests for the dr_adapter_call management command bridge.

SA31 stdin transport coverage is also provided by the standalone tests at
``quickscale_cli/tests/commands/test_dr_adapter_call_standalone.py``.
This file requires a full Django app setup.  The circular-import blocker
(``quickscale_core.runtime`` → ``quickscale_modules_social.adapter`` during
Django app setup) has been resolved — both test suites can run cleanly.
"""

from __future__ import annotations

import json
import sys
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


# ============================================================================
# SA31 — stdin transport path
# ============================================================================


def test_dr_adapter_call_reads_json_from_stdin() -> None:
    """SA31: valid JSON piped via stdin is parsed and dispatched to the adapter."""
    stdout = StringIO()
    mock_adapter = MagicMock(
        return_value={"snapshot_id": "snap-stdin", "status": "ready"},
    )
    stdin_payload = json.dumps({"snapshot_id": "snap-stdin", "dry_run": False})

    with (
        patch.dict(
            "quickscale_modules_backups.management.commands.dr_adapter_call."
            "ADAPTER_FUNCTIONS",
            {"capture_snapshot": mock_adapter},
            clear=True,
        ),
        patch.object(sys, "stdin", StringIO(stdin_payload)),
    ):
        call_command(
            "dr_adapter_call",
            "capture_snapshot",
            stdout=stdout,
            stderr=StringIO(),
        )

    mock_adapter.assert_called_once_with(snapshot_id="snap-stdin", dry_run=False)
    assert json.loads(stdout.getvalue())["status"] == "ready"


def test_dr_adapter_call_stdin_empty_raises_command_error() -> None:
    """SA31: empty stdin without --args-json raises CommandError."""
    with patch.object(sys, "stdin", StringIO("")):
        with pytest.raises(CommandError, match="No JSON input provided"):
            call_command(
                "dr_adapter_call",
                "capture_snapshot",
                stdout=StringIO(),
                stderr=StringIO(),
            )


def test_dr_adapter_call_stdin_whitespace_only_raises_command_error() -> None:
    """SA31: whitespace-only stdin raises CommandError."""
    with patch.object(sys, "stdin", StringIO("   \n  \n  ")):
        with pytest.raises(CommandError, match="No JSON input provided"):
            call_command(
                "dr_adapter_call",
                "capture_snapshot",
                stdout=StringIO(),
                stderr=StringIO(),
            )


def test_dr_adapter_call_stdin_invalid_json_raises_command_error() -> None:
    """SA31: invalid JSON on stdin raises CommandError."""
    with patch.object(sys, "stdin", StringIO("not-json")):
        with pytest.raises(CommandError, match="stdin input must be valid JSON"):
            call_command(
                "dr_adapter_call",
                "capture_snapshot",
                stdout=StringIO(),
                stderr=StringIO(),
            )


def test_dr_adapter_call_stdin_non_dict_raises_command_error() -> None:
    """SA31: non-dict JSON on stdin raises CommandError."""
    with patch.object(sys, "stdin", StringIO("[1, 2, 3]")):
        with pytest.raises(CommandError, match="stdin input must be a JSON object"):
            call_command(
                "dr_adapter_call",
                "capture_snapshot",
                stdout=StringIO(),
                stderr=StringIO(),
            )


def test_dr_adapter_call_stdin_with_unknown_function() -> None:
    """SA31: stdin transport with an unknown function name still errors."""
    with patch.dict(
        "quickscale_modules_backups.management.commands.dr_adapter_call."
        "ADAPTER_FUNCTIONS",
        {"capture_snapshot": MagicMock()},
        clear=True,
    ):
        with patch.object(sys, "stdin", StringIO("{}")):
            with pytest.raises(
                CommandError,
                match="Unknown DR adapter function 'missing_function'",
            ):
                call_command(
                    "dr_adapter_call",
                    "missing_function",
                    stdout=StringIO(),
                    stderr=StringIO(),
                )
