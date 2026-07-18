"""Focused behavioural tests for TP1 static-gate parallelism."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("check_ci_locally.sh")


FAKE_MAKE = r"""#!/usr/bin/env python3
import os
import sys
import time
from pathlib import Path

args = sys.argv[1:]
target = next(argument for argument in args if argument != "--" and not argument.startswith("-"))
event_log = Path(os.environ["FAKE_CI_EVENT_LOG"])
failures = set(filter(None, os.environ.get("FAKE_CI_FAILURES", "").split(",")))
delay_name = f"FAKE_CI_DELAY_{target.replace('-', '_').upper()}"
delay = float(os.environ.get(delay_name, os.environ.get("FAKE_CI_DELAY", "0.2")))

with event_log.open("a", encoding="utf-8") as stream:
    stream.write(f"CALL {target} {' '.join(args)}\n")
    stream.write(f"START {target} {os.getpid()}\n")
    stream.flush()
time.sleep(delay)
with event_log.open("a", encoding="utf-8") as stream:
    stream.write(f"END {target} {os.getpid()}\n")
sys.exit(1 if target in failures else 0)
"""


def _fake_environment(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make = bin_dir / "make"
    make.write_text(FAKE_MAKE, encoding="utf-8")
    make.chmod(0o755)
    poetry = bin_dir / "poetry"
    poetry.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    poetry.chmod(0o755)
    pg_isready = bin_dir / "pg_isready"
    pg_isready.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
    pg_isready.chmod(0o755)

    environment = os.environ.copy()
    environment["PATH"] = f"{bin_dir}:{environment['PATH']}"
    environment["FAKE_CI_EVENT_LOG"] = str(tmp_path / "events.log")
    return bin_dir, environment


def _run_ci(
    tmp_path: Path,
    *,
    parallel: str | None = None,
    failures: str = "",
) -> subprocess.CompletedProcess[str]:
    _, environment = _fake_environment(tmp_path)
    environment["FAKE_CI_FAILURES"] = failures
    environment["FAKE_CI_DELAY"] = "0.2"
    if parallel is not None:
        environment["QS_CI_PARALLEL"] = parallel
    else:
        environment.pop("QS_CI_PARALLEL", None)
    return subprocess.run(
        [str(SCRIPT)],
        cwd=SCRIPT.parents[1],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _events(tmp_path: Path) -> list[str]:
    return (tmp_path / "events.log").read_text(encoding="utf-8").splitlines()


def _wait_for_pid_file(path: Path, timeout: float = 10) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return int(path.read_text(encoding="utf-8"))
        time.sleep(0.05)
    raise AssertionError(f"Timed out waiting for PID file {path}")


def _max_active(events: list[str]) -> int:
    active = 0
    maximum = 0
    for event in events:
        if event.startswith("START "):
            active += 1
            maximum = max(maximum, active)
        elif event.startswith("END "):
            active -= 1
    return maximum


def _wait_for_event(tmp_path: Path, marker: str, timeout: float = 10) -> list[str]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if (tmp_path / "events.log").exists():
            events = _events(tmp_path)
            if any(event.startswith(marker) for event in events):
                return events
        time.sleep(0.05)
    raise AssertionError(f"Timed out waiting for {marker!r}")


def _assert_pids_dead(events: list[str], *, target: str | None = None) -> None:
    for event in events:
        if not event.startswith("START "):
            continue
        parts = event.split()
        if target is not None and parts[1] != target:
            continue
        pid = int(parts[-1])
        with subprocess.Popen(["kill", "-0", str(pid)]) as probe:
            assert probe.wait() != 0, f"{target or 'worker'} {pid} was left running"


def test_parallel_replay_and_aggregate_failures(tmp_path: Path) -> None:
    """All static gates run, replay in order, and report multiple failures."""
    result = _run_ci(
        tmp_path,
        failures="lint,typecheck,check-manifest-sync",
    )
    assert result.returncode != 0
    assert "database-dependent stages will not run" in result.stdout
    assert "Linting (exit 1)" in result.stdout
    assert "Type Checks (exit 1)" in result.stdout
    assert "Manifest Sync Gate (exit 1)" in result.stdout
    assert "[10/" not in result.stdout

    # Every declared static worker started before the replay, and at least two
    # overlapped.  This also proves the worker-pool stage-9 harness was kept.
    events = _events(tmp_path)
    assert sum(event.startswith("START ") for event in events) == 9
    assert _max_active(events) > 1

    replay_markers = [
        "[2/11] Running linters",
        "[3/11] Running module-vs-core",
        "[4/11] Running module-core",
        "[5/11] Running manifest",
        "[6/11] Running org-context",
        "[7/11] Running CSRF",
        "[8/11] Running type checks",
        "[9/11] Running coverage policy",
        "[9/11] Running worker pool",
    ]
    positions = [result.stdout.index(marker) for marker in replay_markers]
    assert positions == sorted(positions)

    # The existing section flags remain arguments to their Make targets.
    calls = "\n".join(event for event in events if event.startswith("CALL "))
    assert "CALL lint lint -- --core --cli --modules" in calls
    assert "CALL typecheck typecheck -- --core --cli --modules" in calls


def test_serial_opt_out_has_no_overlap_and_stops_before_db_stages(tmp_path: Path) -> None:
    """QS_CI_PARALLEL=0 retains serial short-circuit behaviour."""
    result = _run_ci(tmp_path, parallel="0", failures="check-manifest-sync")
    assert result.returncode != 0
    assert "[2/11] Running linters" in result.stdout
    assert "[5/11] Running manifest sync gate" in result.stdout
    assert "[6/11]" not in result.stdout
    assert "[10/" not in result.stdout
    assert _max_active(_events(tmp_path)) == 1


@pytest.mark.parametrize(
    ("signum", "expected"),
    [
        (signal.SIGTERM, 143),
        (signal.SIGINT, 130),
        (signal.SIGHUP, 129),
    ],
    ids=["TERM", "INT", "HUP"],
)
def test_signals_terminate_static_workers(
    tmp_path: Path, signum: signal.Signals, expected: int
) -> None:
    """Static TERM/INT/HUP cleanup reaps every tracked worker tree."""
    _, environment = _fake_environment(tmp_path)
    environment.pop("QS_CI_PARALLEL", None)
    environment["FAKE_CI_DELAY"] = "10"
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
                line.startswith("START ") for line in _events(tmp_path)
            ) == 9:
                break
            time.sleep(0.05)
        assert sum(line.startswith("START ") for line in _events(tmp_path)) == 9
        process.send_signal(signum)
        stdout, stderr = process.communicate(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()

    assert process.returncode == expected, (stdout, stderr)
    assert "static gate workers" in stderr
    _assert_pids_dead(_events(tmp_path))


@pytest.mark.parametrize(
    "signum",
    [signal.SIGTERM, signal.SIGINT, signal.SIGHUP],
    ids=["TERM", "INT", "HUP"],
)
def test_reap_boundary_signal_skips_unrelated_pid_and_kills_active_workers(
    tmp_path: Path, signum: signal.Signals
) -> None:
    """A reap-boundary signal skips a stale/reused PID value."""
    _, environment = _fake_environment(tmp_path)
    environment["FAKE_CI_DELAY"] = "10"
    environment["FAKE_CI_DELAY_LINT"] = "0.05"
    unrelated_pid_file = tmp_path / "unrelated.pid"
    bash_env = tmp_path / "bash_env"
    bash_env.write_text(
        """wait() {
    builtin wait "$@"
        if [[ -z "${FAKE_CI_REAP_BOUNDARY_INJECTED:-}" ]]; then
            FAKE_CI_REAP_BOUNDARY_INJECTED=1
        nohup sleep 10 >/dev/null 2>&1 &
        unrelated_pid=$!
        disown "$unrelated_pid"
        printf '%s\\n' "$unrelated_pid" > "$FAKE_CI_UNRELATED_PID_FILE"
        WORKER_PIDS[0]="$unrelated_pid"
        kill "-$FAKE_CI_SIGNAL_NAME" "$$"
    fi
}
""",
        encoding="utf-8",
    )
    environment["BASH_ENV"] = str(bash_env)
    environment["FAKE_CI_REAP_BOUNDARY_INJECTED"] = ""
    environment["FAKE_CI_SIGNAL_NAME"] = signum.name.removeprefix("SIG")
    environment["FAKE_CI_UNRELATED_PID_FILE"] = str(unrelated_pid_file)
    process = subprocess.Popen(
        [str(SCRIPT)],
        cwd=SCRIPT.parents[1],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    unrelated_pid: int | None = None
    try:
        unrelated_pid = _wait_for_pid_file(unrelated_pid_file)
        stdout, stderr = process.communicate(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()

    try:
        assert (
            process.returncode
            == {
                signal.SIGTERM: 143,
                signal.SIGINT: 130,
                signal.SIGHUP: 129,
            }[signum]
        ), (stdout, stderr)
        assert "static gate workers" in stderr
        events = _events(tmp_path)
        _assert_pids_dead(events)
        assert unrelated_pid is not None
        try:
            os.kill(unrelated_pid, 0)
        except ProcessLookupError as error:
            raise AssertionError("unrelated PID was signaled at the reap boundary") from error
    finally:
        if unrelated_pid is not None:
            try:
                os.kill(unrelated_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


@pytest.mark.parametrize(
    ("signum", "expected"),
    [
        (signal.SIGTERM, -signal.SIGTERM),
        (signal.SIGINT, -signal.SIGINT),
        (signal.SIGHUP, -signal.SIGHUP),
    ],
    ids=["TERM", "INT", "HUP"],
)
def test_signals_in_serial_foreground_mode_do_not_use_worker_trap(
    tmp_path: Path, signum: signal.Signals, expected: int
) -> None:
    """Serial foreground commands use native process-group signal handling."""
    _, environment = _fake_environment(tmp_path)
    environment["QS_CI_PARALLEL"] = "0"
    environment["FAKE_CI_DELAY_LINT"] = "10"
    process = subprocess.Popen(
        [str(SCRIPT)],
        cwd=SCRIPT.parents[1],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        _wait_for_event(tmp_path, "START lint ")
        os.killpg(process.pid, signum)
        stdout, stderr = process.communicate(timeout=10)
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()

    assert process.returncode == expected, (stdout, stderr)
    assert "static gate workers" not in stderr
    _assert_pids_dead(_events(tmp_path), target="lint")


@pytest.mark.parametrize(
    ("signum", "expected"),
    [
        (signal.SIGTERM, -signal.SIGTERM),
        (signal.SIGINT, -signal.SIGINT),
        (signal.SIGHUP, -signal.SIGHUP),
    ],
    ids=["TERM", "INT", "HUP"],
)
def test_signals_after_static_fanout_use_foreground_semantics(
    tmp_path: Path, signum: signal.Signals, expected: int
) -> None:
    """Post-static commands cannot target stale, already-reaped worker PIDs."""
    _, environment = _fake_environment(tmp_path)
    environment.pop("QS_CI_PARALLEL", None)
    environment["FAKE_CI_DELAY"] = "0.05"
    environment["FAKE_CI_DELAY_TEST_COV"] = "10"
    process = subprocess.Popen(
        [str(SCRIPT)],
        cwd=SCRIPT.parents[1],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        events = _wait_for_event(tmp_path, "START test-cov ", timeout=20)
        assert sum(event.startswith("END ") for event in events) >= 9
        os.killpg(process.pid, signum)
        stdout, stderr = process.communicate(timeout=10)
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()

    assert process.returncode == expected, (stdout, stderr)
    assert "static gate workers" not in stderr
    events = _events(tmp_path)
    _assert_pids_dead(events)
    _assert_pids_dead(events, target="test-cov")
