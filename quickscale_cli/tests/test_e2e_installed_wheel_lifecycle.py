"""Installed-wheel ``plan -> apply -> up`` lifecycle acceptance (SA112d)."""

from __future__ import annotations

import os
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import cast, TypeVar

import pytest
import yaml


pytestmark = pytest.mark.e2e

REPO_ROOT = Path(__file__).resolve().parents[2]
PROVISIONER = REPO_ROOT / "scripts" / "provision_installed_venv.sh"
SHIPPED_MODULES = (
    "analytics",
    "auth",
    "backups",
    "billing",
    "blog",
    "crm",
    "forms",
    "listings",
    "notifications",
    "orgs",
    "social",
    "storage",
)
CONTAINER_SUFFIXES = ("backend", "db", "frontend")
VOLUME_SUFFIXES = ("media_volume", "postgres_data", "static_volume")
NETWORK_SUFFIX = "default"
_T = TypeVar("_T")


class LifecycleCleanupError(RuntimeError):
    """Raised when the lifecycle's exact-scope teardown does not succeed."""


def _reap_process_group(process: subprocess.Popen[str]) -> None:
    """Terminate a bounded command and every child in its process group."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        # A group leader can exit before a descendant that inherited its pipes.
        # Drain those pipes rather than returning merely because poll() says the
        # leader exited; the process group can still contain live descendants.
        process.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate(timeout=10)
    else:
        # Descendants can outlive the leader without holding its pipes open.
        # A final exact-group kill closes that race after the TERM grace period.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _run_bounded(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: int,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one command with captured output, a deadline, and process-tree reap."""
    process = subprocess.Popen(
        argv,
        cwd=cwd,
        env=env,
        stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(input=input_text, timeout=timeout)
    except BaseException:
        _reap_process_group(process)
        raise
    return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)


def _require_success(result: subprocess.CompletedProcess[str], phase: str) -> None:
    """Raise a diagnostic-rich command error when a lifecycle phase fails."""
    if result.returncode == 0:
        return
    error = subprocess.CalledProcessError(
        result.returncode,
        result.args,
        output=result.stdout,
        stderr=result.stderr,
    )
    error.add_note(f"SA112d phase failed: {phase}")
    if result.stdout:
        error.add_note(f"stdout:\n{result.stdout[-20_000:]}")
    if result.stderr:
        error.add_note(f"stderr:\n{result.stderr[-20_000:]}")
    raise error


def _run_with_teardown(operation: Callable[[], _T], teardown: Callable[[], None]) -> _T:
    """Run teardown always while preserving the primary lifecycle failure."""
    primary_error: BaseException | None = None
    result: _T | None = None
    try:
        result = operation()
    except BaseException as error:
        primary_error = error

    try:
        teardown()
    except BaseException as cleanup_error:
        if primary_error is None:
            raise
        primary_error.add_note(
            "SA112d teardown also failed without replacing the primary failure: "
            f"{cleanup_error!r}"
        )

    if primary_error is not None:
        raise primary_error.with_traceback(primary_error.__traceback__)
    return cast(_T, result)


def _scoped_name() -> str:
    """Return a Docker-safe project slug tied to this CLI lane and xdist worker."""
    lane = os.environ.get("QS_E2E_LANE", "cli")
    assert lane == "cli", (
        f"installed-wheel lifecycle belongs to the CLI lane, got {lane!r}"
    )
    lane_scope = os.environ.get("QS_E2E_CONTAINER_PREFIX", "qs-e2e-cli")
    worker = os.environ.get("PYTEST_XDIST_WORKER", "serial")
    normalized_scope = re.sub(r"[^a-z0-9]+", "_", lane_scope.lower()).strip("_")
    normalized_worker = re.sub(r"[^a-z0-9]+", "_", worker.lower()).strip("_")
    return f"sa112d_{normalized_scope[:28]}_{normalized_worker[:8]}"


def _free_port() -> int:
    """Reserve and release a candidate loopback port for the generated service."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _installed_environment(
    venv_dir: Path, wheelhouse: Path, project_slug: str, port: int
) -> dict[str, str]:
    """Build a source-free environment for installed CLI subprocesses."""
    env = os.environ.copy()
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    env.pop("POETRY_ACTIVE", None)
    env["PATH"] = os.pathsep.join((str(venv_dir / "bin"), env.get("PATH", "")))
    env["VIRTUAL_ENV"] = str(venv_dir)
    env["PYTHONNOUSERSITE"] = "1"
    env["QUICKSCALE_SKIP_DEPENDENCY_CHECKS"] = "1"
    env["QUICKSCALE_LOCAL_WHEELHOUSE"] = str(wheelhouse)
    env["GIT_AUTHOR_NAME"] = "QuickScale E2E"
    env["GIT_AUTHOR_EMAIL"] = "quickscale-e2e@example.invalid"
    env["GIT_COMMITTER_NAME"] = "QuickScale E2E"
    env["GIT_COMMITTER_EMAIL"] = "quickscale-e2e@example.invalid"
    env["PORT"] = str(port)
    env["COMPOSE_PROJECT_NAME"] = project_slug
    env["QS_E2E_CONTAINER_PREFIX"] = project_slug
    return env


def _wait_for_live_http(port: int, timeout: float = 120.0) -> bytes:
    """Poll the generated project's public HTTP endpoint to a fixed deadline."""
    url = f"http://127.0.0.1:{port}/"
    deadline = time.monotonic() + timeout
    last_error: BaseException | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310
                assert response.status == 200
                return cast(bytes, response.read())
        except (OSError, urllib.error.URLError) as error:
            last_error = error
            time.sleep(1)
    raise TimeoutError(f"HTTP endpoint {url} did not become live: {last_error!r}")


def _exact_docker_cleanup(project_slug: str, cwd: Path, env: dict[str, str]) -> None:
    """Remove and verify only this test's exact Docker resource identities."""
    containers = [f"{project_slug}_{suffix}" for suffix in CONTAINER_SUFFIXES]
    volumes = [f"{project_slug}_{suffix}" for suffix in VOLUME_SUFFIXES]
    network = f"{project_slug}_{NETWORK_SUFFIX}"
    _run_bounded(
        ["docker", "rm", "-f", *containers],
        cwd=cwd,
        env=env,
        timeout=60,
    )
    _run_bounded(
        ["docker", "volume", "rm", "-f", *volumes],
        cwd=cwd,
        env=env,
        timeout=60,
    )
    _run_bounded(
        ["docker", "network", "rm", network],
        cwd=cwd,
        env=env,
        timeout=60,
    )

    leftovers: list[str] = []
    for resource in containers:
        probe = _run_bounded(
            ["docker", "container", "inspect", resource],
            cwd=cwd,
            env=env,
            timeout=20,
        )
        if probe.returncode == 0:
            leftovers.append(f"container:{resource}")
    for resource in volumes:
        probe = _run_bounded(
            ["docker", "volume", "inspect", resource],
            cwd=cwd,
            env=env,
            timeout=20,
        )
        if probe.returncode == 0:
            leftovers.append(f"volume:{resource}")
    network_probe = _run_bounded(
        ["docker", "network", "inspect", network],
        cwd=cwd,
        env=env,
        timeout=20,
    )
    if network_probe.returncode == 0:
        leftovers.append(f"network:{network}")
    if leftovers:
        raise LifecycleCleanupError(f"exact-scope Docker resources remain: {leftovers}")


def _assert_installed_imports(
    venv_dir: Path, work_dir: Path, env: dict[str, str]
) -> None:
    """Prove CLI/core resolve from the disposable venv rather than workspace source."""
    probe = _run_bounded(
        [
            str(venv_dir / "bin" / "python"),
            "-c",
            (
                "import pathlib, quickscale_cli, quickscale_core; "
                "print(pathlib.Path(quickscale_cli.__file__).resolve()); "
                "print(pathlib.Path(quickscale_core.__file__).resolve())"
            ),
        ],
        cwd=work_dir,
        env=env,
        timeout=60,
    )
    _require_success(probe, "installed import probe")
    resolved_paths = [Path(line) for line in probe.stdout.splitlines() if line.strip()]
    assert len(resolved_paths) == 2
    assert all(path.is_relative_to(venv_dir) for path in resolved_paths)
    assert all(not path.is_relative_to(REPO_ROOT) for path in resolved_paths)


def test_installed_wheel_plan_apply_up_all_modules(tmp_path: Path) -> None:
    """Run the all-module lifecycle from a wheel-only external working directory."""
    output_dir = tmp_path / "installed"
    project_slug = _scoped_name()
    project_dir = output_dir / "work" / project_slug
    port = _free_port()
    runtime: dict[str, object] = {}

    def lifecycle() -> None:
        provision_env = os.environ.copy()
        provision = _run_bounded(
            [str(PROVISIONER), str(REPO_ROOT), str(output_dir)],
            cwd=tmp_path,
            env=provision_env,
            timeout=900,
        )
        _require_success(provision, "installed-wheel provisioning")
        assert provision.stdout == f"{output_dir}\n"

        venv_dir = output_dir / "venv"
        wheelhouse = output_dir / "wheels"
        work_dir = output_dir / "work"
        assert not work_dir.is_relative_to(REPO_ROOT)
        assert len(tuple(wheelhouse.glob("*.whl"))) == 3
        env = _installed_environment(venv_dir, wheelhouse, project_slug, port)
        runtime.update({"venv_dir": venv_dir, "work_dir": work_dir, "env": env})
        _assert_installed_imports(venv_dir, work_dir, env)

        quickscale = str(venv_dir / "bin" / "quickscale")
        module_selection = ",".join(SHIPPED_MODULES)
        plan_input = f"1\n{module_selection}\ny\ny\nn\ny\n"
        plan = _run_bounded(
            [quickscale, "plan", project_slug, "--package", project_slug],
            cwd=work_dir,
            env=env,
            timeout=180,
            input_text=plan_input,
        )
        _require_success(plan, "installed external-cwd plan")

        config = yaml.safe_load((project_dir / "quickscale.yml").read_text())
        assert set(config["modules"]) == set(SHIPPED_MODULES)
        assert len(config["modules"]) == 12

        apply = _run_bounded(
            [quickscale, "apply", "--no-docker"],
            cwd=project_dir,
            env=env,
            timeout=1800,
            input_text="y\ny\n",
        )
        _require_success(apply, "installed external-cwd apply")
        assert {path.name for path in (project_dir / "modules").iterdir()} == set(
            SHIPPED_MODULES
        )

        up = _run_bounded([quickscale, "up"], cwd=project_dir, env=env, timeout=1800)
        _require_success(up, "installed external-cwd up")
        runtime["started"] = True

        ps = _run_bounded([quickscale, "ps"], cwd=project_dir, env=env, timeout=120)
        _require_success(ps, "installed external-cwd ps")
        assert f"{project_slug}_backend" in ps.stdout

        migrate = _run_bounded(
            [quickscale, "manage", "migrate", "--noinput"],
            cwd=project_dir,
            env=env,
            timeout=300,
        )
        _require_success(migrate, "installed external-cwd manage migrate")
        assert _wait_for_live_http(port)

    def teardown() -> None:
        env = runtime.get("env")
        work_dir = runtime.get("work_dir")
        venv_dir = runtime.get("venv_dir")
        teardown_error: BaseException | None = None
        if (
            runtime.get("started")
            and isinstance(env, dict)
            and isinstance(venv_dir, Path)
            and project_dir.is_dir()
        ):
            down = _run_bounded(
                [str(venv_dir / "bin" / "quickscale"), "down", "--volumes"],
                cwd=project_dir,
                env=env,
                timeout=180,
            )
            if down.returncode != 0:
                teardown_error = subprocess.CalledProcessError(
                    down.returncode, down.args, output=down.stdout, stderr=down.stderr
                )
        if isinstance(env, dict) and isinstance(work_dir, Path):
            _exact_docker_cleanup(project_slug, work_dir, env)
        if teardown_error is not None:
            raise teardown_error

    _run_with_teardown(lifecycle, teardown)


class _SetupFailure(RuntimeError):
    pass


class _OperationFailure(RuntimeError):
    pass


class _TeardownFailure(RuntimeError):
    pass


@pytest.mark.parametrize(
    "primary_error",
    [
        _SetupFailure("setup failed"),
        subprocess.TimeoutExpired(["quickscale", "apply"], 1),
        _OperationFailure("operation failed"),
    ],
    ids=["setup-failure", "timeout", "exception"],
)
def test_cleanup_failure_does_not_mask_primary_error(
    primary_error: BaseException,
) -> None:
    """Setup, timeout, and operation failures retain precedence over teardown."""

    def fail_operation() -> None:
        raise primary_error

    def fail_teardown() -> None:
        raise _TeardownFailure("teardown failed")

    with pytest.raises(
        type(primary_error), match=re.escape(str(primary_error))
    ) as caught:
        _run_with_teardown(fail_operation, fail_teardown)
    assert any("teardown also failed" in note for note in caught.value.__notes__)


def test_nonzero_teardown_is_reported_after_successful_operation() -> None:
    """A nonzero teardown becomes the failure when no earlier phase failed."""

    def fail_teardown() -> None:
        raise subprocess.CalledProcessError(23, ["quickscale", "down", "--volumes"])

    with pytest.raises(subprocess.CalledProcessError) as caught:
        _run_with_teardown(lambda: None, fail_teardown)
    assert caught.value.returncode == 23


def test_bounded_timeout_reaps_descendant_after_group_leader_exits(
    tmp_path: Path,
) -> None:
    """A timed-out command reaps a child even after its group leader exits."""
    child_pid_file = tmp_path / "child.pid"
    script = (
        "import pathlib, subprocess, sys; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
        f"pathlib.Path({str(child_pid_file)!r}).write_text(str(child.pid)); "
        "sys.exit(0)"
    )

    with pytest.raises(subprocess.TimeoutExpired):
        _run_bounded(
            [sys.executable, "-c", script],
            cwd=tmp_path,
            env=os.environ.copy(),
            timeout=1,
        )

    child_pid = int(child_pid_file.read_text())
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        pytest.fail(f"timed-out descendant process {child_pid} is still present")


def test_exact_cleanup_includes_compose_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failure cleanup removes and verifies the exact Compose network too."""
    calls: list[list[str]] = []

    def fake_run_bounded(
        argv: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        timeout: int,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        del cwd, env, timeout, input_text
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 1, "", "not found")

    monkeypatch.setattr(sys.modules[__name__], "_run_bounded", fake_run_bounded)

    _exact_docker_cleanup("sa112d_scope", tmp_path, os.environ.copy())

    assert ["docker", "network", "rm", "sa112d_scope_default"] in calls
    assert ["docker", "network", "inspect", "sa112d_scope_default"] in calls
