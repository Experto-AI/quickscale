"""Focused behavioural tests for TP1 static-gate parallelism."""

from __future__ import annotations

import os
import re
import signal
import subprocess
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("check_ci_locally.sh")


EXPECTED_CI_COMMANDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        ".github/workflows/ci.yml",
        (
            "make lint -- --core --cli --modules --devtools",
            "make typecheck -- --core --cli --modules --devtools",
            "make lint -- --cli --devtools",
            "make typecheck -- --cli --devtools",
        ),
    ),
    (
        ".github/workflows/publish.yml",
        (
            "make lint -- --core --cli --modules --devtools",
            "make typecheck -- --core --cli --modules --devtools",
        ),
    ),
    (
        "scripts/check_ci_locally.sh",
        (
            "make lint -- --core --cli --modules --devtools",
            "make typecheck -- --core --cli --modules --devtools",
            "make lint -- --core --cli --modules --devtools",
            "make typecheck -- --core --cli --modules --devtools",
        ),
    ),
)

FRONTEND_WORKFLOWS = (".github/workflows/ci.yml", ".github/workflows/publish.yml")


def _make_lint_typecheck_commands(path: Path) -> list[str]:
    command_pattern = re.compile(r"\bmake (?:lint|typecheck) --[ \t]+[^\r\n#]+")
    return [
        " ".join(match.group(0).split())
        for line in path.read_text(encoding="utf-8").splitlines()
        if (match := command_pattern.search(line))
    ]


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


def _fake_environment(
    tmp_path: Path, *, missing_tools: tuple[str, ...] = ()
) -> tuple[Path, dict[str, str]]:
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
    for executable in ("node", "pnpm"):
        if executable in missing_tools:
            continue
        tool = bin_dir / executable
        tool.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        tool.chmod(0o755)

    environment = os.environ.copy()
    runtime_bin = tmp_path / "runtime-bin"
    runtime_bin.mkdir()
    available_names = {entry.name for entry in bin_dir.iterdir()}
    for path_entry in environment["PATH"].split(os.pathsep):
        if not path_entry:
            continue
        source_dir = Path(path_entry)
        if not source_dir.is_dir():
            continue
        for source in source_dir.iterdir():
            if source.name in available_names or source.name in missing_tools:
                continue
            if source.is_file() and os.access(source, os.X_OK):
                (runtime_bin / source.name).symlink_to(source)
                available_names.add(source.name)
    environment["PATH"] = os.pathsep.join((str(bin_dir), str(runtime_bin)))
    environment["FAKE_CI_EVENT_LOG"] = str(tmp_path / "events.log")
    return bin_dir, environment


def _run_ci(
    tmp_path: Path,
    *,
    parallel: str | None = None,
    failures: str = "",
    missing_tools: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    _, environment = _fake_environment(tmp_path, missing_tools=missing_tools)
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


def test_ci_lint_typecheck_sites_require_devtools() -> None:
    """Every authoritative CI/local-CI command explicitly covers devtools."""
    repository_root = SCRIPT.parents[1]
    all_commands: list[str] = []

    for relative_path, expected_commands in EXPECTED_CI_COMMANDS:
        actual_commands = _make_lint_typecheck_commands(repository_root / relative_path)
        assert actual_commands == list(expected_commands), relative_path
        all_commands.extend(actual_commands)

    assert len(all_commands) == 10
    assert all(command.endswith(" --devtools") for command in all_commands)


def test_frontend_workflows_match_maintained_toolchain_pattern() -> None:
    """Frontend jobs use the maintained Node/pnpm majors and store cache shape."""
    repository_root = SCRIPT.parents[1]

    for relative_path in FRONTEND_WORKFLOWS:
        content = (repository_root / relative_path).read_text(encoding="utf-8")
        node_setup = content.index("uses: actions/setup-node@v6")
        pnpm_setup = content.index("uses: pnpm/action-setup@v5")

        assert node_setup < pnpm_setup
        assert 'node-version: "24"' in content
        assert "version: 11.0.9" in content
        assert 'echo "STORE_PATH=$(pnpm store path --silent)" >> $GITHUB_ENV' in content
        assert "uses: actions/cache@v5" in content
        assert "path: ${{ env.STORE_PATH }}" in content
        assert (
            "hashFiles('quickscale_core/src/quickscale_core/generator/"
            "templates/themes/showcase_react/package.json.j2')" in content
        )
        assert "runner.os }}-pnpm-store-" in content


def test_parallel_replay_and_aggregate_failures(tmp_path: Path) -> None:
    """All static gates run, replay in order, and report multiple failures."""
    result = _run_ci(
        tmp_path,
        failures="lint,typecheck,check-manifest-sync,lint-frontend",
    )
    assert result.returncode != 0
    assert "database-dependent stages will not run" in result.stdout
    assert "Linting (exit 1)" in result.stdout
    assert "Type Checks (exit 1)" in result.stdout
    assert "Manifest Sync Gate (exit 1)" in result.stdout
    assert "Frontend Lint (exit 1)" in result.stdout
    assert "[10/" not in result.stdout

    # Every declared static worker started before the replay, and at least two
    # overlapped.  This also proves the worker-pool stage-9 harness was kept.
    events = _events(tmp_path)
    assert sum(event.startswith("START ") for event in events) == 10
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
        "[9/11] Running rendered frontend",
    ]
    positions = [result.stdout.index(marker) for marker in replay_markers]
    assert positions == sorted(positions)

    # The existing section flags remain arguments to their Make targets.
    calls = [event for event in events if event.startswith("CALL ")]
    assert "CALL lint lint -- --core --cli --modules --devtools" in calls
    assert "CALL typecheck typecheck -- --core --cli --modules --devtools" in calls


def test_serial_opt_out_has_no_overlap_and_stops_before_db_stages(tmp_path: Path) -> None:
    """QS_CI_PARALLEL=0 retains serial short-circuit behaviour."""
    result = _run_ci(tmp_path, parallel="0", failures="check-manifest-sync")
    assert result.returncode != 0
    assert "[2/11] Running linters" in result.stdout
    assert "[5/11] Running manifest sync gate" in result.stdout
    assert "[6/11]" not in result.stdout
    assert "[10/" not in result.stdout
    assert _max_active(_events(tmp_path)) == 1


def test_frontend_lint_skips_when_node_is_absent(tmp_path: Path) -> None:
    """Missing Node skips only the optional rendered frontend lint stage."""
    result = _run_ci(tmp_path, missing_tools=("node",))

    assert result.returncode != 0  # PostgreSQL is intentionally unavailable here.
    assert "Skipping rendered frontend lint (Node.js is not available)." in result.stdout
    assert "Frontend Lint Failed" not in result.stdout
    assert "[10/11] Running coverage checks" in result.stdout


def test_frontend_lint_skips_when_pnpm_is_absent(tmp_path: Path) -> None:
    """Missing pnpm skips only the optional rendered frontend lint stage."""
    result = _run_ci(tmp_path, missing_tools=("pnpm",))

    assert result.returncode != 0  # PostgreSQL is intentionally unavailable here.
    assert "Skipping rendered frontend lint (pnpm is not available)." in result.stdout
    assert "Frontend Lint Failed" not in result.stdout
    assert "[10/11] Running coverage checks" in result.stdout


def test_serial_frontend_lint_failure_blocks_before_database_stages(tmp_path: Path) -> None:
    """An actual frontend lint failure is not treated as a missing-tool skip."""
    result = _run_ci(tmp_path, parallel="0", failures="lint-frontend")

    assert result.returncode != 0
    assert "[9/11] Running rendered frontend lint" in result.stdout
    assert "Frontend Lint Failed" in result.stdout
    assert "Skipping rendered frontend lint" not in result.stdout
    assert "[10/11] Running coverage checks" not in result.stdout


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
            if (tmp_path / "events.log").exists():
                events = _events(tmp_path)
                if sum(line.startswith("START ") for line in events) >= 10:
                    break
            time.sleep(0.05)
        events = _events(tmp_path)
        assert sum(line.startswith("START ") for line in events) == 10
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
