"""Standalone direct-evidence tests for the dr_adapter_call bridge.

Covers both the SA31 stdin transport and the legacy ``--args-json`` path.
The existing Django-based test suite (``quickscale_modules/backups/tests/
test_dr_adapter_call.py``) has comprehensive coverage but is blocked by a
pre-existing circular import (``quickscale_core.runtime`` →
``quickscale_modules_social.adapter`` during Django app setup).  This file
provides equivalent direct execution evidence by patching the import-time
adapter initialization before importing the management command class.

This file does NOT require Django to be fully set up — the Command class is
imported and exercised in isolation with mocked ``ADAPTER_FUNCTIONS``.
"""

from __future__ import annotations

import json
import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Safe import of the management Command class
# ---------------------------------------------------------------------------
# ``quickscale_core.manifest.entry_point`` triggers ``refresh_managed_adapters``
# at import time, which imports module adapters that may circular-import back
# into ``quickscale_core.runtime``.  We patch around that by pre-setting the
# initialization flag so the refresh is a no-op.
# pylint: disable=wrong-import-position

import quickscale_core.manifest.entry_point as _ep  # noqa: E402

_ep._ADAPTERS_INITIALIZED = True  # noqa: SLF001
_ep._initialize_managed_adapters_at_import = lambda: None  # type: ignore[method-assign]  # noqa: E501

from quickscale_modules_backups.management.commands.dr_adapter_call import (  # noqa: E402
    Command,
)
from django.core.management.base import CommandError  # noqa: E402

# Re-enable lint for the rest of the file
# pylint: enable=wrong-import-position


@pytest.fixture
def command() -> Command:
    """Return a bare Command instance for unit-level method tests."""
    return Command()


# ============================================================================
# _read_kwargs — legacy --args-json path
# ============================================================================


class TestReadKwargsArgsJson:
    """Tests for _read_kwargs with the legacy --args-json argument."""

    def test_valid_json_object(self, command: Command) -> None:
        """Happy path: valid JSON object via --args-json."""
        result = command._read_kwargs('{"key": "value", "count": 42}')
        assert result == {"key": "value", "count": 42}

    def test_empty_object(self, command: Command) -> None:
        """Empty JSON object via --args-json."""
        result = command._read_kwargs("{}")
        assert result == {}

    def test_invalid_json_raises(self, command: Command) -> None:
        """Invalid JSON string raises CommandError."""
        with pytest.raises(CommandError, match="--args-json must be valid JSON"):
            command._read_kwargs("not-json")

    def test_non_dict_json_raises(self, command: Command) -> None:
        """Non-dict JSON (array) raises CommandError."""
        with pytest.raises(CommandError, match="--args-json must be a JSON object"):
            command._read_kwargs("[1, 2, 3]")

    def test_non_dict_json_string_raises(self, command: Command) -> None:
        """Non-dict JSON (string) raises CommandError."""
        with pytest.raises(CommandError, match="--args-json must be a JSON object"):
            command._read_kwargs('"a-string"')


# ============================================================================
# _read_kwargs — SA31 stdin transport
# ============================================================================


class TestReadKwargsStdin:
    """Tests for _read_kwargs reading from stdin (SA31 transport)."""

    def test_reads_json_from_stdin(self, command: Command) -> None:
        """SA31: valid JSON piped via stdin is parsed and returned."""
        payload = json.dumps({"snapshot_id": "snap-456", "dry_run": False})
        with patch.object(sys, "stdin", StringIO(payload)):
            result = command._read_kwargs(None)
        assert result == {"snapshot_id": "snap-456", "dry_run": False}

    def test_stdin_empty_raises(self, command: Command) -> None:
        """SA31: empty stdin without --args-json raises CommandError."""
        with patch.object(sys, "stdin", StringIO("")):
            with pytest.raises(CommandError, match="No JSON input provided"):
                command._read_kwargs(None)

    def test_stdin_whitespace_only_raises(self, command: Command) -> None:
        """SA31: whitespace-only stdin raises CommandError."""
        with patch.object(sys, "stdin", StringIO("   \n  \n  ")):
            with pytest.raises(CommandError, match="No JSON input provided"):
                command._read_kwargs(None)

    def test_stdin_invalid_json_raises(self, command: Command) -> None:
        """SA31: invalid JSON on stdin raises CommandError."""
        with patch.object(sys, "stdin", StringIO("not-json")):
            with pytest.raises(CommandError, match="stdin input must be valid JSON"):
                command._read_kwargs(None)

    def test_stdin_non_dict_raises(self, command: Command) -> None:
        """SA31: non-dict JSON on stdin raises CommandError."""
        with patch.object(sys, "stdin", StringIO("[1, 2, 3]")):
            with pytest.raises(CommandError, match="stdin input must be a JSON object"):
                command._read_kwargs(None)

    def test_args_json_still_supported_when_both_paths_available(
        self, command: Command
    ) -> None:
        """SA31: explicit --args-json takes precedence over stdin."""
        payload = json.dumps({"from_stdin": True})
        with patch.object(sys, "stdin", StringIO(payload)):
            result = command._read_kwargs('{"from_args": true}')
        # When args_json is provided, stdin is NOT read
        assert result == {"from_args": True}


# ============================================================================
# handle() — dispatch to ADAPTER_FUNCTIONS
# ============================================================================


class TestHandleDispatch:
    """Tests for Command.handle() dispatching to ADAPTER_FUNCTIONS."""

    @staticmethod
    def _run_handle(
        command: Command,
        *,
        function_name: str,
        args_json: str | None,
        stdout: StringIO | None = None,
    ) -> StringIO:
        """Run command.handle() with a fresh stdout StringIO."""
        if stdout is None:
            stdout = StringIO()
        # BaseCommand.handle() reads from self.stdout — set it directly.
        command.stdout = stdout
        command.handle(
            function_name=function_name,
            args_json=args_json,
            stderr=StringIO(),
        )
        return stdout

    def test_dispatches_registered_function(self, command: Command) -> None:
        """Happy path: registered function receives kwargs and result is JSON."""
        mock_adapter = MagicMock(
            return_value={
                "route_kind": "local-to-railway-develop",
                "snapshot_id": "snap-123",
                "status": "ready",
            }
        )

        with patch.dict(
            "quickscale_modules_backups.management.commands.dr_adapter_call."
            "ADAPTER_FUNCTIONS",
            {"capture_snapshot": mock_adapter},
            clear=True,
        ):
            stdout = self._run_handle(
                command,
                function_name="capture_snapshot",
                args_json=json.dumps({"snapshot_id": "snap-123", "dry_run": True}),
            )

        mock_adapter.assert_called_once_with(snapshot_id="snap-123", dry_run=True)
        assert json.loads(stdout.getvalue()) == {
            "route_kind": "local-to-railway-develop",
            "snapshot_id": "snap-123",
            "status": "ready",
        }

    def test_dispatches_with_stdin_input(self, command: Command) -> None:
        """SA31: kwargs piped via stdin reach the adapter function."""
        mock_adapter = MagicMock(
            return_value={"status": "ready", "snapshot_id": "snap-456"}
        )
        stdin_payload = json.dumps({"snapshot_id": "snap-456", "dry_run": False})

        with (
            patch.dict(
                "quickscale_modules_backups.management.commands."
                "dr_adapter_call.ADAPTER_FUNCTIONS",
                {"capture_snapshot": mock_adapter},
                clear=True,
            ),
            patch.object(sys, "stdin", StringIO(stdin_payload)),
        ):
            stdout = self._run_handle(
                command,
                function_name="capture_snapshot",
                args_json=None,
            )

        mock_adapter.assert_called_once_with(snapshot_id="snap-456", dry_run=False)
        assert json.loads(stdout.getvalue()) == {
            "status": "ready",
            "snapshot_id": "snap-456",
        }

    def test_unknown_function_raises(self, command: Command) -> None:
        """Unknown function name raises CommandError listing available."""
        with patch.dict(
            "quickscale_modules_backups.management.commands."
            "dr_adapter_call.ADAPTER_FUNCTIONS",
            {"capture_snapshot": MagicMock()},
            clear=True,
        ):
            with pytest.raises(
                CommandError,
                match="Unknown DR adapter function 'missing_func'",
            ):
                command.handle(
                    function_name="missing_func",
                    args_json="{}",
                    stdout=StringIO(),
                    stderr=StringIO(),
                )

    def test_adapter_exception_becomes_command_error(self, command: Command) -> None:
        """Adapter raising an exception surfaces as CommandError."""
        with patch.dict(
            "quickscale_modules_backups.management.commands."
            "dr_adapter_call.ADAPTER_FUNCTIONS",
            {
                "capture_snapshot": MagicMock(
                    side_effect=RuntimeError("adapter exploded")
                )
            },
            clear=True,
        ):
            with pytest.raises(
                CommandError,
                match="DR adapter 'capture_snapshot' failed: adapter exploded",
            ):
                command.handle(
                    function_name="capture_snapshot",
                    args_json="{}",
                    stdout=StringIO(),
                    stderr=StringIO(),
                )

    def test_args_json_backward_compatible(self, command: Command) -> None:
        """SA31: --args-json legacy path still works."""
        mock_adapter = MagicMock(
            return_value={"status": "ok", "snapshot_id": "snap-789"}
        )

        with patch.dict(
            "quickscale_modules_backups.management.commands."
            "dr_adapter_call.ADAPTER_FUNCTIONS",
            {"capture_snapshot": mock_adapter},
            clear=True,
        ):
            stdout = self._run_handle(
                command,
                function_name="capture_snapshot",
                args_json=json.dumps({"snapshot_id": "snap-789"}),
            )

        mock_adapter.assert_called_once_with(snapshot_id="snap-789")
        assert json.loads(stdout.getvalue())["snapshot_id"] == "snap-789"
