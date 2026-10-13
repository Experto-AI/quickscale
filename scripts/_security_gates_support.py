"""
Shared process and JSON support for the security gate facade and its siblings.

This module owns the gate error types, the fail-closed command runner, the
strict JSON decoder, the temporary-directory registry, and the process
cleanup path.  Every private sibling resolves those collaborators here at
call time, so a test's seam is the module that defines the name
(decisions.md, Split-Facade Seams).
"""

from __future__ import annotations

import atexit
import json
import os
import shutil
import signal
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COMMAND_TIMEOUT = 180.0


class GateError(RuntimeError):
    """An expected gate failure, reported as infrastructure exit 2."""


class FindingsError(GateError):
    """The scanner returned findings which were not accountable."""


@dataclass(frozen=True)
class Completed:
    returncode: int
    stdout: str
    stderr: str


_temporary_paths: list[Path] = []
_active_processes: set[subprocess.Popen[str]] = set()
_cleanup_started = False


def _terminate_process_group(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=2)
    except ProcessLookupError, subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=2)
        except ProcessLookupError, subprocess.TimeoutExpired:
            pass


def _cleanup() -> None:
    global _cleanup_started
    if _cleanup_started:
        return
    _cleanup_started = True
    for process in tuple(_active_processes):
        _terminate_process_group(process)
    _active_processes.clear()
    for path in reversed(_temporary_paths):
        shutil.rmtree(path, ignore_errors=True)
    _temporary_paths.clear()


def _signal_handler(signum: int, _frame: Any) -> None:
    _cleanup()
    raise SystemExit(128 + signum)


atexit.register(_cleanup)
for _signal in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
    signal.signal(_signal, _signal_handler)


def run_command(
    argv: list[str], *, cwd: Path | None = None, timeout: float = COMMAND_TIMEOUT
) -> Completed:
    """Run a command in its own process group and fail closed on timeout."""
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
            close_fds=True,
        )
        _active_processes.add(process)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            _terminate_process_group(process)
            raise GateError(f"command timed out after {timeout:g}s: {' '.join(argv)}") from exc
        return Completed(process.returncode, stdout, stderr)
    except OSError as exc:
        raise GateError(f"could not execute {' '.join(argv)}: {exc}") from exc
    finally:
        if process is not None:
            _active_processes.discard(process)


def strict_json(text: str, *, source: str) -> Any:
    """Decode JSON while rejecting duplicate object keys and trailing data."""

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise GateError(f"duplicate JSON key {key!r} in {source}")
            result[key] = value
        return result

    try:
        return json.loads(text, object_pairs_hook=reject_duplicates)
    except (json.JSONDecodeError, TypeError) as exc:
        raise GateError(f"malformed JSON from {source}: {exc}") from exc


def _new_temp_dir(prefix: str) -> Path:
    path = Path(tempfile.mkdtemp(prefix=prefix))
    _temporary_paths.append(path)
    return path
