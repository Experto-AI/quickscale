"""Installed-wheel ``plan -> apply -> up`` lifecycle acceptance (SA112d)."""

from __future__ import annotations

import json
import os
import re
import shutil
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
QUICKSCALE_REMOTE = "https://github.com/Experto-AI/quickscale.git"
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
OWNER_LABEL = "com.quickscale.owner"
LIFECYCLE_LABEL = "com.quickscale.lifecycle"
SCOPE_LABEL = "com.quickscale.scope"
IMAGE_CONTRACT_LABEL = "com.quickscale.image-contract"
IMAGE_DIGEST_LABEL = "com.quickscale.image-digest"
_T = TypeVar("_T")


class LifecycleCleanupError(RuntimeError):
    """Raised when the lifecycle's exact-scope teardown does not succeed."""


def _diagnostic_retention_enabled() -> bool:
    """Return whether fixture teardown must retain resources for diagnosis."""
    return os.environ.get("QS_E2E_NO_CLEANUP", "0") == "1"


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
    """Return stable project inputs; resources carry worker isolation separately."""
    lane = os.environ.get("QS_E2E_LANE", "cli")
    assert lane == "cli", (
        f"installed-wheel lifecycle belongs to the CLI lane, got {lane!r}"
    )
    return "sa112d_cli"


def _free_port() -> int:
    """Reserve and release a candidate loopback port for the generated service."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _installed_environment(
    venv_dir: Path,
    wheelhouse: Path,
    project_slug: str,
    port: int,
    resource_prefix: str | None = None,
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
    resource_prefix = resource_prefix or os.environ.get(
        "QS_E2E_RESOURCE_SCOPE", project_slug
    )
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if worker:
        normalized_worker = re.sub(r"[^a-z0-9]+", "_", worker.lower()).strip("_")
        resource_prefix = f"{resource_prefix}-{normalized_worker}"[:63]
    env["COMPOSE_PROJECT_NAME"] = resource_prefix
    env["QS_E2E_CONTAINER_PREFIX"] = resource_prefix
    env["QUICKSCALE_RESOURCE_PREFIX"] = resource_prefix
    env["QS_E2E_PROJECT_SLUG"] = project_slug
    env["QS_E2E_NO_CLEANUP"] = os.environ.get("QS_E2E_NO_CLEANUP", "0")
    return env


def _run_artifact_git(argv: list[str], cwd: Path) -> str:
    """Run one bounded Git command while constructing the local artifact remote."""
    result = _run_bounded(
        ["git", *argv],
        cwd=cwd,
        env=os.environ.copy(),
        timeout=120,
    )
    _require_success(result, f"current-module artifact Git {' '.join(argv)}")
    return result.stdout.strip()


def _ignore_module_build_artifacts(_directory: str, names: list[str]) -> list[str]:
    """Exclude repository-local caches and build outputs from staged modules."""
    ignored_names = {
        ".coverage",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "htmlcov",
    }
    return [
        name
        for name in names
        if name in ignored_names
        or name.startswith(".coverage.")
        or name.endswith((".egg-info", ".pyc", ".pyo"))
    ]


def _stage_current_module_artifacts(output_dir: Path) -> tuple[Path, dict[str, str]]:
    """Build a hermetic Git remote whose split refs contain current module bytes."""
    artifact_repo = output_dir / "module-artifacts"
    artifact_repo.mkdir(parents=True)
    _run_artifact_git(["init", "--initial-branch=artifact-staging"], artifact_repo)
    _run_artifact_git(["config", "user.name", "QuickScale E2E"], artifact_repo)
    _run_artifact_git(
        ["config", "user.email", "quickscale-e2e@example.invalid"], artifact_repo
    )

    split_refs: dict[str, str] = {}
    for module_name in SHIPPED_MODULES:
        for entry in artifact_repo.iterdir():
            if entry.name == ".git":
                continue
            if entry.is_dir() and not entry.is_symlink():
                shutil.rmtree(entry)
            else:
                entry.unlink()

        shutil.copytree(
            REPO_ROOT / "quickscale_modules" / module_name,
            artifact_repo,
            dirs_exist_ok=True,
            ignore=_ignore_module_build_artifacts,
        )
        split_ref = f"e2e/current/{module_name}"
        _run_artifact_git(["add", "-A"], artifact_repo)
        _run_artifact_git(
            ["commit", "--allow-empty", "-m", f"Stage current {module_name} module"],
            artifact_repo,
        )
        _run_artifact_git(["branch", "--force", split_ref, "HEAD"], artifact_repo)
        split_refs[module_name] = split_ref

    assert tuple(split_refs) == SHIPPED_MODULES
    return artifact_repo, split_refs


def _redirect_quickscale_remote(
    env: dict[str, str], artifact_repo: Path
) -> dict[str, str]:
    """Redirect only the canonical QuickScale remote to the local artifact repo."""
    redirected = dict(env)
    for key in list(redirected):
        if key == "GIT_CONFIG_COUNT" or key.startswith(
            ("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")
        ):
            redirected.pop(key, None)
    redirected["GIT_CONFIG_COUNT"] = "2"
    redirected["GIT_CONFIG_KEY_0"] = f"url.{artifact_repo.resolve().as_uri()}.insteadOf"
    redirected["GIT_CONFIG_VALUE_0"] = QUICKSCALE_REMOTE
    redirected["GIT_CONFIG_KEY_1"] = "protocol.file.allow"
    redirected["GIT_CONFIG_VALUE_1"] = "always"
    return redirected


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


def _label_filters(scope: str) -> list[str]:
    """Return the complete fixed owner/lifecycle/scope selector tuple."""
    return [
        "--filter",
        f"label={OWNER_LABEL}=quickscale",
        "--filter",
        f"label={LIFECYCLE_LABEL}=e2e",
        "--filter",
        f"label={SCOPE_LABEL}={scope}",
    ]


def _resource_ids(
    resource_type: str, scope: str, cwd: Path, env: dict[str, str]
) -> list[str]:
    commands = {
        "container": ["docker", "ps", "-aq"],
        "volume": ["docker", "volume", "ls", "-q"],
        "network": ["docker", "network", "ls", "-q"],
    }
    result = _run_bounded(
        [*commands[resource_type], *_label_filters(scope)],
        cwd=cwd,
        env=env,
        timeout=60,
    )
    if result.returncode != 0:
        raise LifecycleCleanupError(
            f"cannot enumerate labelled {resource_type} resources: {result.stderr}"
        )
    return result.stdout.split()


def _inspect_labels(
    resource_type: str, resource_id: str, cwd: Path, env: dict[str, str]
) -> dict[str, str]:
    inspect_command = {
        "container": ["docker", "container", "inspect"],
        "volume": ["docker", "volume", "inspect"],
        "network": ["docker", "network", "inspect"],
    }[resource_type]
    result = _run_bounded(
        [
            *inspect_command,
            "--format",
            "{{json .Config.Labels}}"
            if resource_type == "container"
            else "{{json .Labels}}",
            resource_id,
        ],
        cwd=cwd,
        env=env,
        timeout=20,
    )
    if result.returncode != 0:
        raise LifecycleCleanupError(
            f"cannot reinspect {resource_type} {resource_id}: {result.stderr}"
        )
    try:
        labels = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise LifecycleCleanupError(
            f"invalid labels for {resource_type} {resource_id}"
        ) from error
    if not isinstance(labels, dict):
        raise LifecycleCleanupError(f"missing labels for {resource_type} {resource_id}")
    return {str(key): str(value) for key, value in labels.items()}


def _exact_docker_cleanup(scope: str, cwd: Path, env: dict[str, str]) -> None:
    """Remove only fully re-inspected QuickScale resources in one scope."""
    if re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", scope) is None:
        raise LifecycleCleanupError(f"invalid Docker resource scope: {scope!r}")
    resource_ids = {
        resource_type: _resource_ids(resource_type, scope, cwd, env)
        for resource_type in ("container", "volume", "network")
    }
    expected = {OWNER_LABEL: "quickscale", LIFECYCLE_LABEL: "e2e", SCOPE_LABEL: scope}
    for resource_type, ids in resource_ids.items():
        for resource_id in ids:
            labels = _inspect_labels(resource_type, resource_id, cwd, env)
            if any(labels.get(key) != value for key, value in expected.items()):
                raise LifecycleCleanupError(
                    f"refusing mismatched {resource_type} {resource_id}: {labels}"
                )

    removal_commands = {
        "container": ["docker", "rm", "-f"],
        "volume": ["docker", "volume", "rm", "-f"],
        "network": ["docker", "network", "rm"],
    }
    for resource_type in ("container", "volume", "network"):
        ids = resource_ids[resource_type]
        if not ids:
            continue
        result = _run_bounded(
            [*removal_commands[resource_type], *ids],
            cwd=cwd,
            env=env,
            timeout=60,
        )
        if result.returncode != 0:
            raise LifecycleCleanupError(
                f"failed removing {resource_type} resources: {result.stderr}"
            )

    leftovers = {
        resource_type: _resource_ids(resource_type, scope, cwd, env)
        for resource_type in ("container", "volume", "network")
    }
    remaining = [
        f"{resource_type}:{ids}" for resource_type, ids in leftovers.items() if ids
    ]
    if remaining:
        raise LifecycleCleanupError(f"labelled Docker resources remain: {remaining}")


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
        artifact_repo, split_refs = _stage_current_module_artifacts(output_dir)
        env = _redirect_quickscale_remote(
            _installed_environment(venv_dir, wheelhouse, project_slug, port),
            artifact_repo,
        )
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

        apply_argv = [quickscale, "apply", "--no-docker"]
        for module_name in SHIPPED_MODULES:
            apply_argv.extend(
                ["--split-ref", f"{module_name}={split_refs[module_name]}"]
            )
        apply = _run_bounded(
            apply_argv,
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
        resource_prefix = str(env["QUICKSCALE_RESOURCE_PREFIX"])
        assert f"{resource_prefix}_backend" in ps.stdout

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
            not _diagnostic_retention_enabled()
            and runtime.get("started")
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
        if (
            not _diagnostic_retention_enabled()
            and isinstance(env, dict)
            and isinstance(work_dir, Path)
        ):
            resource_scope = str(env["QUICKSCALE_RESOURCE_PREFIX"])
            _exact_docker_cleanup(resource_scope, work_dir, env)
        if teardown_error is not None:
            raise teardown_error

    _run_with_teardown(lifecycle, teardown)


def test_sa142_installed_fixture_retention_toggle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No-cleanup skips both fixture down and exact final destruction."""
    monkeypatch.setenv("QS_E2E_NO_CLEANUP", "1")
    assert _diagnostic_retention_enabled()
    monkeypatch.setenv("QS_E2E_NO_CLEANUP", "0")
    assert not _diagnostic_retention_enabled()


def test_sa142_worker_resources_do_not_change_project_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Worker resource suffixes isolate Docker without changing the slug."""
    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw0")
    monkeypatch.setenv("QS_E2E_RESOURCE_SCOPE", "run-scope")
    assert _scoped_name() == "sa112d_cli"
    environment = _installed_environment(
        Path("/venv"), Path("/wheels"), _scoped_name(), 8123
    )
    assert environment["QUICKSCALE_RESOURCE_PREFIX"] == "run-scope-gw0"
    assert f"{environment['QUICKSCALE_RESOURCE_PREFIX']}_backend" == (
        "run-scope-gw0_backend"
    )


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
    """Label cleanup removes all resource kinds and rechecks their absence."""
    calls: list[list[str]] = []
    remaining = {"container": ["c1"], "volume": ["v1"], "network": ["n1"]}
    labels = {
        OWNER_LABEL: "quickscale",
        LIFECYCLE_LABEL: "e2e",
        SCOPE_LABEL: "sa112d_scope",
    }

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
        if argv[:3] == ["docker", "ps", "-aq"]:
            output = "\n".join(remaining["container"])
        elif argv[:4] == ["docker", "volume", "ls", "-q"]:
            output = "\n".join(remaining["volume"])
        elif argv[:4] == ["docker", "network", "ls", "-q"]:
            output = "\n".join(remaining["network"])
        elif argv[:3] == ["docker", "container", "inspect"]:
            output = json.dumps(labels)
        elif argv[:3] == ["docker", "volume", "inspect"]:
            output = json.dumps(labels)
        elif argv[:3] == ["docker", "network", "inspect"]:
            output = json.dumps(labels)
        elif argv[:3] == ["docker", "rm", "-f"]:
            remaining["container"] = []
            output = ""
        elif argv[:4] == ["docker", "volume", "rm", "-f"]:
            remaining["volume"] = []
            output = ""
        elif argv[:3] == ["docker", "network", "rm"]:
            remaining["network"] = []
            output = ""
        else:
            raise AssertionError(argv)
        return subprocess.CompletedProcess(argv, 0, output, "")

    monkeypatch.setattr(sys.modules[__name__], "_run_bounded", fake_run_bounded)

    _exact_docker_cleanup("sa112d_scope", tmp_path, os.environ.copy())

    assert ["docker", "rm", "-f", "c1"] in calls
    assert ["docker", "volume", "rm", "-f", "v1"] in calls
    assert ["docker", "network", "rm", "n1"] in calls


def test_sa142_label_cleanup_collision_survives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A same-name/unlabelled collision is never selected for removal."""
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
        if argv[:3] == ["docker", "ps", "-aq"]:
            return subprocess.CompletedProcess(argv, 0, "owned\n", "")
        if argv[:4] in (
            ["docker", "volume", "ls", "-q"],
            ["docker", "network", "ls", "-q"],
        ):
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[:3] == ["docker", "container", "inspect"]:
            return subprocess.CompletedProcess(
                argv,
                0,
                json.dumps(
                    {
                        OWNER_LABEL: "not-quickscale",
                        LIFECYCLE_LABEL: "e2e",
                        SCOPE_LABEL: "scope",
                    }
                ),
                "",
            )
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(sys.modules[__name__], "_run_bounded", fake_run_bounded)
    with pytest.raises(LifecycleCleanupError, match="refusing mismatched"):
        _exact_docker_cleanup("scope", tmp_path, os.environ.copy())
    assert not any(argv[:3] == ["docker", "rm", "-f"] for argv in calls)
