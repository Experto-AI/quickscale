"""Focused behavioural tests for the Core/CLI E2E lane runner."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("test_e2e.sh")


FAKE_POETRY = r"""#!/usr/bin/env python3
import os
import signal
import sys
import time
from pathlib import Path

args = sys.argv[1:]
if args[:3] == ["run", "playwright", "install"]:
    raise SystemExit(0)

assert args[:2] == ["run", "pytest"], args
lane = os.environ["QS_E2E_LANE"]
event_log = Path(os.environ["FAKE_E2E_EVENT_LOG"])


def handle_signal(signum, _frame):
    with event_log.open("a", encoding="utf-8") as stream:
        stream.write(f"SIGNAL|{lane}|{os.getpid()}|{signum}\n")
        stream.flush()
    raise SystemExit(128 + signum)


for signal_number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
    signal.signal(signal_number, handle_signal)

delay = float(
    os.environ.get(f"FAKE_E2E_DELAY_{lane.upper()}", os.environ.get("FAKE_E2E_DELAY", "0.2"))
)
failure = os.environ.get("FAKE_E2E_FAILURE", "") == lane

with event_log.open("a", encoding="utf-8") as stream:
    stream.write(f"CALL|{lane}|{' '.join(args[2:])}\n")
    stream.write(f"START|{lane}|{os.getpid()}\n")
    stream.flush()
time.sleep(delay)
with event_log.open("a", encoding="utf-8") as stream:
    stream.write(f"END|{lane}|{os.getpid()}\n")
    stream.flush()
raise SystemExit(1 if failure else 0)
"""


FAKE_DOCKER = r"""#!/usr/bin/env bash
if [ -n "${FAKE_E2E_DOCKER_LOG:-}" ]; then
    printf 'DOCKER|%s|%s\n' "$*" "${QS_E2E_LANE:-}" >> "$FAKE_E2E_DOCKER_LOG"
fi
if [ "${1:-}" = "info" ]; then
    exit 0
fi
exit 0
"""


def _fake_environment(tmp_path: Path, *, failure: str = "") -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, content in (("poetry", FAKE_POETRY), ("docker", FAKE_DOCKER)):
        executable = bin_dir / name
        executable.write_text(content, encoding="utf-8")
        executable.chmod(0o755)

    environment = os.environ.copy()
    environment["PATH"] = f"{bin_dir}:{environment['PATH']}"
    environment["FAKE_E2E_EVENT_LOG"] = str(tmp_path / "events.log")
    environment["FAKE_E2E_DOCKER_LOG"] = str(tmp_path / "docker.log")
    environment["FAKE_E2E_FAILURE"] = failure
    environment["FAKE_E2E_DELAY"] = "0.2"
    return environment


def _run(
    tmp_path: Path, *args: str, failure: str = "", **environment: str
) -> subprocess.CompletedProcess[str]:
    child_environment = _fake_environment(tmp_path, failure=failure)
    child_environment.update(environment)
    return subprocess.run(
        [str(SCRIPT), *args],
        cwd=SCRIPT.parents[1],
        env=child_environment,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _events(tmp_path: Path) -> list[str]:
    return (tmp_path / "events.log").read_text(encoding="utf-8").splitlines()


def _max_active(events: list[str]) -> int:
    active = 0
    maximum = 0
    for event in events:
        if event.startswith("START|"):
            active += 1
            maximum = max(maximum, active)
        elif event.startswith("END|"):
            active -= 1
    return maximum


def test_parallel_lanes_overlap_and_replay_in_lane_order(tmp_path: Path) -> None:
    """The default launches both lanes and replays Core before CLI."""
    result = _run(tmp_path, FAKE_E2E_DELAY_CORE="0.2", FAKE_E2E_DELAY_CLI="0.05")

    assert result.returncode == 0, result.stdout + result.stderr
    events = _events(tmp_path)
    assert _max_active(events) == 2
    starts = [event for event in events if event.startswith("START|")]
    assert {event.split("|", 2)[1] for event in starts} == {"core", "cli"}
    lane_lines = [line for line in result.stdout.splitlines() if "App host port:" in line]
    assert len(lane_lines) == 2
    assert len({line.rsplit(":", 1)[1].strip() for line in lane_lines}) == 2
    core_start = next(event for event in events if event.startswith("START|core"))
    core_end = next(event for event in events if event.startswith("END|core"))
    assert events.index(core_start) < events.index(core_end)
    assert result.stdout.index("[Core] Lane:") < result.stdout.index("[CLI] Lane:")
    assert "All E2E Tests Passed" in result.stdout


def test_serial_opt_out_forwards_flags_and_preserves_cleanup_mode(tmp_path: Path) -> None:
    """The opt-out is serial and command flags reach the intended lane."""
    result = _run(
        tmp_path,
        "--headed",
        "--no-cleanup",
        "--full",
        "-k",
        "smoke",
        QS_E2E_PARALLEL="0",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    events = _events(tmp_path)
    assert _max_active(events) == 1
    calls = [event for event in events if event.startswith("CALL|")]
    assert any(
        "CALL|core|" in event and "--headed" in event and "-k smoke" in event for event in calls
    )
    assert any("CALL|cli|" in event and "-k smoke" in event for event in calls)
    assert all(" -q" not in event for event in calls)
    assert result.stdout.count("Skipping cleanup (--no-cleanup specified)") == 2


def test_cli_only_failure_is_attributed_and_nonzero(tmp_path: Path) -> None:
    """A CLI failure cannot be hidden by a successful Core lane."""
    result = _run(tmp_path, failure="cli")

    assert result.returncode != 0
    assert "[Core] ✓ Core E2E tests passed" in result.stdout
    assert "[CLI] ✗ CLI E2E tests failed" in result.stdout
    assert "E2E failure attribution:" in result.stdout
    assert "✗ CLI E2E tests (exit 1)" in result.stdout
    assert "All E2E Tests Passed" not in result.stdout


@pytest.mark.parametrize(
    ("signal_number", "exit_code"),
    ((signal.SIGTERM, 143), (signal.SIGINT, 130), (signal.SIGHUP, 129)),
)
def test_signal_stops_both_lane_workers_and_cleans_up(
    tmp_path: Path, signal_number: signal.Signals, exit_code: int
) -> None:
    """Parent signals stop lanes and every lane performs its own cleanup."""
    environment = _fake_environment(tmp_path)
    environment["FAKE_E2E_DELAY"] = "10"
    process = subprocess.Popen(
        [str(SCRIPT)],
        cwd=SCRIPT.parents[1],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if (tmp_path / "events.log").exists() and sum(
                event.startswith("START|") for event in _events(tmp_path)
            ) == 2:
                break
            time.sleep(0.05)
        assert sum(event.startswith("START|") for event in _events(tmp_path)) == 2
        process.send_signal(signal_number)
        stdout, stderr = process.communicate(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()

    assert process.returncode == exit_code, (stdout, stderr)
    assert "terminating worker subprocesses" in stderr
    for event in _events(tmp_path):
        if event.startswith("START|"):
            pid = int(event.rsplit("|", 1)[1])
            with subprocess.Popen(["kill", "-0", str(pid)]) as probe:
                assert probe.wait() != 0, f"lane worker {pid} was left running"
    docker_events = (tmp_path / "docker.log").read_text(encoding="utf-8").splitlines()
    assert sum("compose" in event and " down " in event for event in docker_events) == 2


def test_signal_after_core_lane_completes_only_targets_active_lane(tmp_path: Path) -> None:
    """A completed lane is not signal-visible while the other lane joins."""
    environment = _fake_environment(tmp_path)
    environment["FAKE_E2E_DELAY_CORE"] = "0.05"
    environment["FAKE_E2E_DELAY_CLI"] = "10"
    process = subprocess.Popen(
        [str(SCRIPT)],
        cwd=SCRIPT.parents[1],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if (tmp_path / "events.log").exists() and any(
                event.startswith("END|core|") for event in _events(tmp_path)
            ):
                break
            time.sleep(0.05)
        assert any(event.startswith("END|core|") for event in _events(tmp_path))
        process.send_signal(signal.SIGTERM)
        stdout, stderr = process.communicate(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()

    assert process.returncode == 143, (stdout, stderr)
    events = _events(tmp_path)
    assert any(event.startswith("SIGNAL|cli|") for event in events)
    assert not any(event.startswith("SIGNAL|core|") for event in events)


# ── QS_E2E_XDIST_WORKERS (Phase 2) ──────────────────────────────────────


def test_xdist_default_resolves(tmp_path: Path) -> None:
    """The default QS_E2E_XDIST_WORKERS heuristic resolves and banners correctly."""
    result = _run(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    xdist_lines = [line for line in result.stdout.splitlines() if "Xdist:" in line]
    assert len(xdist_lines) == 1
    xdist_line = xdist_lines[0]

    events = _events(tmp_path)
    calls = [e for e in events if e.startswith("CALL|")]
    assert len(calls) == 2

    if "serial" in xdist_line:
        assert all(" -n " not in c for c in calls)
        assert all("--dist" not in c for c in calls)
    else:
        assert "per lane" in xdist_line
        assert all(" -n " in c for c in calls)
        assert all("--dist loadscope" in c for c in calls)


def test_xdist_serial_when_zero(tmp_path: Path) -> None:
    """QS_E2E_XDIST_WORKERS=0 runs without -n/--dist on every lane."""
    result = _run(tmp_path, QS_E2E_XDIST_WORKERS="0")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Xdist: serial" in result.stdout
    events = _events(tmp_path)
    calls = [e for e in events if e.startswith("CALL|")]
    assert all(" -n " not in c for c in calls)
    assert all("--dist" not in c for c in calls)


def test_xdist_serial_when_one(tmp_path: Path) -> None:
    """QS_E2E_XDIST_WORKERS=1 also runs without -n/--dist on every lane."""
    result = _run(tmp_path, QS_E2E_XDIST_WORKERS="1")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Xdist: serial" in result.stdout
    events = _events(tmp_path)
    calls = [e for e in events if e.startswith("CALL|")]
    assert all(" -n " not in c for c in calls)
    assert all("--dist" not in c for c in calls)


def test_xdist_explicit_workers(tmp_path: Path) -> None:
    """QS_E2E_XDIST_WORKERS=4 adds -n 4 --dist loadscope to each lane."""
    result = _run(tmp_path, QS_E2E_XDIST_WORKERS="4")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Xdist: 4 per lane" in result.stdout
    assert "total 8 across 2 lanes" in result.stdout
    events = _events(tmp_path)
    calls = [e for e in events if e.startswith("CALL|")]
    for call in calls:
        assert " -n 4 " in call
        assert "--dist loadscope" in call


def test_xdist_malformed_non_numeric(tmp_path: Path) -> None:
    """A non-numeric QS_E2E_XDIST_WORKERS fails early."""
    result = _run(tmp_path, QS_E2E_XDIST_WORKERS="abc")

    assert result.returncode != 0
    assert "must be a non-negative integer" in result.stderr


def test_xdist_malformed_negative(tmp_path: Path) -> None:
    """A negative QS_E2E_XDIST_WORKERS fails early."""
    result = _run(tmp_path, QS_E2E_XDIST_WORKERS="-1")

    assert result.returncode != 0
    assert "must be a non-negative integer" in result.stderr
