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


FAKE_DOCKER = r"""#!/usr/bin/env python3
import os
import sys


args = sys.argv[1:]
if os.environ.get("FAKE_E2E_DOCKER_LOG"):
    with open(os.environ["FAKE_E2E_DOCKER_LOG"], "a", encoding="utf-8") as stream:
        stream.write(f"DOCKER|{' '.join(args)}|{os.environ.get('QS_E2E_LANE', '')}\n")


def image_records():
    state_path = os.environ.get("FAKE_E2E_IMAGE_STATE")
    if not state_path or not os.path.exists(state_path):
        return []
    records = []
    with open(state_path, encoding="utf-8") as stream:
        for line in stream:
            fields = line.rstrip("\n").split("|")
            if len(fields) == 7:
                records.append(fields)
    return records


def save_image_records(records):
    state_path = os.environ["FAKE_E2E_IMAGE_STATE"]
    with open(state_path, "w", encoding="utf-8") as stream:
        for record in records:
            stream.write("|".join(record) + "\n")


if args[:1] == ["info"]:
    raise SystemExit(0)

if args[:3] == ["image", "ls", "-aq"]:
    requested_scope = next(
        (
            value.removeprefix("label=com.quickscale.scope=")
            for value in args
            if value.startswith("label=com.quickscale.scope=")
        ),
        None,
    )
    for (
        image_id,
        owner,
        lifecycle,
        listed_scope,
        _inspect_scope,
        _image_contract,
        tagged,
    ) in image_records():
        if (
            owner == "quickscale"
            and lifecycle == "e2e"
            and listed_scope == requested_scope
            and ("dangling=false" not in args or tagged == "1")
        ):
            print(image_id)
    raise SystemExit(0)

if args[:2] == ["image", "inspect"]:
    image_id = args[-1]
    for record in image_records():
        if record[0] == image_id:
            print("|".join((record[1], record[2], record[4])))
            raise SystemExit(0)
    raise SystemExit(1)

if args[:2] == ["image", "rm"]:
    removed_ids = set(args[2:])
    remaining = [record for record in image_records() if record[0] not in removed_ids]
    save_image_records(remaining)
    raise SystemExit(0)

# The runner tests only need non-image resources to enumerate as empty.
raise SystemExit(0)
"""


def _fake_environment(tmp_path: Path, *, failure: str = "") -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, content in (("poetry", FAKE_POETRY), ("docker", FAKE_DOCKER)):
        executable = bin_dir / name
        executable.write_text(content, encoding="utf-8")
        executable.chmod(0o755)

    environment = os.environ.copy()
    # This helper defines the baseline for runner self-tests.  Do not let an
    # outer acceptance campaign silently force its serial lane/worker settings
    # into tests that are meant to exercise the runner defaults.  Individual
    # tests can still opt into either setting through _run() overrides.
    environment.pop("QS_E2E_PARALLEL", None)
    environment.pop("QS_E2E_XDIST_WORKERS", None)
    environment["PATH"] = f"{bin_dir}:{environment['PATH']}"
    environment["FAKE_E2E_EVENT_LOG"] = str(tmp_path / "events.log")
    environment["FAKE_E2E_DOCKER_LOG"] = str(tmp_path / "docker.log")
    environment["FAKE_E2E_FAILURE"] = failure
    environment["FAKE_E2E_DELAY"] = "0.2"
    # The low-memory preflight would flip concurrent lanes to serial on a
    # memory-tight host, breaking the concurrency assertions below.  Disable it
    # so lane scheduling is deterministic regardless of the runner's free RAM.
    environment["QS_E2E_NO_MEMORY_GUARD"] = "1"
    return environment


def test_fake_environment_ignores_outer_lane_and_worker_controls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An outer serial campaign cannot contaminate runner-default tests."""
    monkeypatch.setenv("QS_E2E_PARALLEL", "0")
    monkeypatch.setenv("QS_E2E_XDIST_WORKERS", "1")

    environment = _fake_environment(tmp_path)

    assert "QS_E2E_PARALLEL" not in environment
    assert "QS_E2E_XDIST_WORKERS" not in environment


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


def test_memory_guard_falls_back_to_serial_when_headroom_is_low(tmp_path: Path) -> None:
    """Low resting RAM headroom downshifts lanes and xdist workers to serial."""
    # Re-enable the guard (the fake env disables it) and set an unsatisfiable
    # available-RAM floor so the preflight always trips on any host.
    result = _run(
        tmp_path,
        QS_E2E_NO_MEMORY_GUARD="0",
        QS_E2E_MIN_AVAIL_MB="999999999",
        QS_E2E_XDIST_WORKERS="4",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert _max_active(_events(tmp_path)) == 1
    assert "Lane mode: serial" in result.stdout
    assert "Xdist: serial" in result.stdout
    calls = [event for event in _events(tmp_path) if event.startswith("CALL|")]
    assert all(" -n " not in event for event in calls)
    assert all("--dist" not in event for event in calls)
    assert "Low memory headroom" in result.stderr
    assert "pytest will run serially in each lane" in result.stderr


def test_memory_guard_can_be_disabled(tmp_path: Path) -> None:
    """The opt-out keeps lanes concurrent and preserves explicit xdist workers."""
    result = _run(
        tmp_path,
        QS_E2E_NO_MEMORY_GUARD="1",
        QS_E2E_MIN_AVAIL_MB="999999999",
        QS_E2E_XDIST_WORKERS="4",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert _max_active(_events(tmp_path)) == 2
    assert "Xdist: 4 per lane" in result.stdout
    calls = [event for event in _events(tmp_path) if event.startswith("CALL|")]
    assert all(" -n 4 " in event for event in calls)
    assert all("--dist loadscope" in event for event in calls)
    assert "Low memory headroom" not in result.stderr


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
    assert not any("compose" in event and " down " in event for event in docker_events)
    assert any("label=com.quickscale.owner=quickscale" in event for event in docker_events)
    assert not any("--remove-orphans" in event or "name=" in event for event in docker_events)


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


def test_two_scope_cleanup_isolates_tagged_images(tmp_path: Path) -> None:
    """Cleaning one exact scope leaves another and foreign images untouched."""
    state = tmp_path / "images.state"
    state.write_text(
        "image-a|quickscale|e2e|scope-a|scope-a|sa142|1\n"
        "image-b|quickscale|e2e|scope-b|scope-b|sa142|1\n"
        "foreign|other-owner|e2e|scope-b|scope-b|foreign|1\n",
        encoding="utf-8",
    )
    scope_b_dir = tmp_path / "scope-b"
    scope_b_dir.mkdir()
    result_b = _run(
        scope_b_dir,
        "--cleanup-scope",
        "scope-b",
        FAKE_E2E_IMAGE_STATE=str(state),
        QUICKSCALE_BACKEND_IMAGE_DIGEST="foreign-digest",
    )

    assert result_b.returncode == 0, result_b.stdout + result_b.stderr
    assert state.read_text(encoding="utf-8"), "fake image state unexpectedly vanished"
    remaining_after_b = state.read_text(encoding="utf-8").splitlines()
    assert remaining_after_b == [
        "image-a|quickscale|e2e|scope-a|scope-a|sa142|1",
        "foreign|other-owner|e2e|scope-b|scope-b|foreign|1",
    ]
    docker_events = (scope_b_dir / "docker.log").read_text(encoding="utf-8").splitlines()
    image_list_events = [event for event in docker_events if "image ls -aq" in event]
    assert image_list_events
    assert all(
        "label=com.quickscale.owner=quickscale" in event
        and "label=com.quickscale.lifecycle=e2e" in event
        and "label=com.quickscale.scope=scope-b" in event
        and "dangling=false" in event
        and "label!=com.quickscale.image-contract=sa142" not in event
        for event in image_list_events
    )
    assert not any("label=com.quickscale.image-digest=" in event for event in docker_events)
    assert any("image inspect" in event and "image-b" in event for event in docker_events)
    assert any("image rm image-b" in event for event in docker_events)
    assert not any("image-a" in event and "image rm" in event for event in docker_events)
    inspect_index = next(
        index
        for index, event in enumerate(docker_events)
        if "image inspect" in event and "image-b" in event
    )
    remove_index = next(
        index for index, event in enumerate(docker_events) if "image rm image-b" in event
    )
    assert inspect_index < remove_index

    scope_a_dir = tmp_path / "scope-a"
    scope_a_dir.mkdir()
    result_a = _run(
        scope_a_dir,
        "--cleanup-scope",
        "scope-a",
        FAKE_E2E_IMAGE_STATE=str(state),
    )
    assert result_a.returncode == 0, result_a.stdout + result_a.stderr
    assert state.read_text(encoding="utf-8").splitlines() == [
        "foreign|other-owner|e2e|scope-b|scope-b|foreign|1",
    ]


def test_cleanup_refuses_image_label_mismatch(tmp_path: Path) -> None:
    """A filter hit with changed labels is never deleted."""
    state = tmp_path / "images.state"
    original = "mismatch|quickscale|e2e|scope-a|scope-other|sa142|1"
    state.write_text(original + "\n", encoding="utf-8")
    mismatch_dir = tmp_path / "mismatch"
    mismatch_dir.mkdir()

    result = _run(
        mismatch_dir,
        "--cleanup-scope",
        "scope-a",
        FAKE_E2E_IMAGE_STATE=str(state),
    )

    assert result.returncode != 0
    assert "failed label reinspection" in result.stderr
    assert state.read_text(encoding="utf-8").splitlines() == [original]


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
