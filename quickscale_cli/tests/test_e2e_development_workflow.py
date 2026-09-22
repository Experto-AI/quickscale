"""
End-to-end tests for QuickScale CLI development commands.

These tests verify the complete development workflow with real Docker containers:
1. Generate Django project
2. Start services with 'quickscale up'
3. Verify containers with 'quickscale ps'
4. Run Django commands with 'quickscale manage'
5. Access shell with 'quickscale shell'
6. View logs with 'quickscale logs'
7. Stop services with 'quickscale down'

Run with: pytest -m e2e
Note: Requires Docker to be running
"""

from collections.abc import Callable
import json
import os
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
from unittest.mock import Mock, call

import pytest
from click.testing import CliRunner

from quickscale_cli.main import cli
from quickscale_cli.utils.docker_utils import (
    ContainerStatus,
    DockerContainerStatusError,
    DockerComposePluginRequiredError,
    get_container_status,
    get_docker_compose_command,
    wait_for_port_release,
)
from quickscale_core.generator import ProjectGenerator

# Bypass the apply command's destructive/remote confirmation gate so
# that E2E tests do not require interactive input for that prompt.
# Docker and migration steps still execute normally after bypass.
import quickscale_cli.commands.apply_command as _apply_mod

_apply_mod._AF5_DESTRUCTIVE_CONFIRM_BYPASS = True


def _retain_e2e_resources() -> bool:
    """Return whether diagnostics intentionally retain Docker resources."""
    return os.environ.get("QS_E2E_NO_CLEANUP", "0") == "1"


def _stable_test_project_slug() -> str:
    """Return stable generated-project input independent of run resources."""
    return os.environ.get("QS_E2E_PROJECT_SLUG", "e2e_cli_test")


def _worker_resource_scope() -> str:
    """Derive a worker-specific resource scope without changing project inputs."""
    base = os.environ.get(
        "QS_E2E_RESOURCE_SCOPE",
        os.environ.get("QS_E2E_CONTAINER_PREFIX", "e2e_cli_test"),
    )
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if worker:
        return f"{base}-{worker}"[:63]
    return base


def _e2e_host_ports(find_free_port: Callable[[], int]) -> tuple[str, str]:
    """Return distinct parent-reserved app/frontend ports for one E2E lane."""
    app_port = os.environ.get("QS_E2E_APP_PORT") or str(find_free_port())
    configured_frontend_port = os.environ.get("QS_E2E_FRONTEND_PORT")
    frontend_port = configured_frontend_port or str(find_free_port())
    if configured_frontend_port and frontend_port == app_port:
        raise ValueError("QS_E2E_FRONTEND_PORT must differ from QS_E2E_APP_PORT")
    while frontend_port == app_port:
        frontend_port = str(find_free_port())
    return app_port, frontend_port


def _cleanup_labelled_resources(scope: str) -> None:
    """Fail-closed cleanup for one exact QuickScale owner/lifecycle/scope tuple."""
    if re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", scope) is None:
        raise ValueError(f"invalid Docker resource scope: {scope!r}")
    selectors = [
        "--filter",
        "label=com.quickscale.owner=quickscale",
        "--filter",
        "label=com.quickscale.lifecycle=e2e",
        "--filter",
        f"label=com.quickscale.scope={scope}",
    ]
    resources = {
        "container": (
            ["docker", "ps", "-aq", *selectors],
            ["docker", "container", "inspect"],
        ),
        "volume": (
            ["docker", "volume", "ls", "-q", *selectors],
            ["docker", "volume", "inspect"],
        ),
        "network": (
            ["docker", "network", "ls", "-q", *selectors],
            ["docker", "network", "inspect"],
        ),
    }
    selected: dict[str, list[str]] = {}
    expected = {
        "com.quickscale.owner": "quickscale",
        "com.quickscale.lifecycle": "e2e",
        "com.quickscale.scope": scope,
    }
    for resource_type, (list_argv, inspect_argv) in resources.items():
        listed = subprocess.run(list_argv, capture_output=True, text=True, check=True)
        ids = listed.stdout.split()
        selected[resource_type] = ids
        for resource_id in ids:
            inspected = subprocess.run(
                [
                    *inspect_argv,
                    "--format",
                    "{{json .Config.Labels}}"
                    if resource_type == "container"
                    else "{{json .Labels}}",
                    resource_id,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            labels = json.loads(inspected.stdout)
            if any(labels.get(key) != value for key, value in expected.items()):
                raise RuntimeError(f"refusing mismatched {resource_type} {resource_id}")
    remove_argv = {
        "container": ["docker", "rm", "-f"],
        "volume": ["docker", "volume", "rm", "-f"],
        "network": ["docker", "network", "rm"],
    }
    for resource_type in ("container", "volume", "network"):
        if selected[resource_type]:
            subprocess.run(
                [*remove_argv[resource_type], *selected[resource_type]],
                check=True,
                capture_output=True,
                text=True,
            )
    for resource_type, (list_argv, _inspect_argv) in resources.items():
        leftovers = subprocess.run(
            list_argv,
            capture_output=True,
            text=True,
            check=True,
        )
        if leftovers.stdout.split():
            raise RuntimeError(
                f"labelled {resource_type} resources remain in scope {scope}"
            )


def _prepare_e2e_resource_scope(scope: str, port: int) -> None:
    """Remove prior-test resources even when the next failure will be retained."""
    _cleanup_labelled_resources(scope)
    wait_for_port_release(port, timeout=5.0)


def _last_container_logs(container_name: str) -> str:
    """Return the last twenty log lines, retaining a useful failure fallback."""
    try:
        result = subprocess.run(
            ["docker", "logs", "--tail", "20", container_name],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (subprocess.SubprocessError, FileNotFoundError) as error:
        return f"<unable to read container logs: {error}>"
    if result.returncode == 0:
        logs = "\n".join(
            stream.strip()
            for stream in (result.stdout, result.stderr)
            if stream.strip()
        )
        return logs or "<no container logs>"
    detail = result.stderr.strip() or f"docker logs exited with {result.returncode}"
    return f"<unable to read container logs: {detail}>"


@pytest.mark.e2e
def test_wait_for_container_running_diagnostics_include_stderr(monkeypatch):
    """Successful Docker log capture retains both container output streams."""
    monkeypatch.setattr(
        subprocess,
        "run",
        Mock(
            return_value=subprocess.CompletedProcess(
                ["docker", "logs"],
                0,
                stdout="ordinary output\n",
                stderr="traceback output\n",
            )
        ),
    )

    logs = _last_container_logs("backend")

    assert logs == "ordinary output\ntraceback output"


@pytest.mark.e2e
def test_wait_for_container_running_exited_state_fails_immediately(monkeypatch):
    """A crashed container reports its code/logs without another poll or sleep."""
    status = ContainerStatus(
        "exited", exit_code=1, display_status="Exited (1) 3 seconds ago"
    )
    statuses = [status]
    monkeypatch.setattr(
        __name__ + ".get_container_status",
        lambda _name: statuses.pop(0),
    )
    monkeypatch.setattr(
        __name__ + "._last_container_logs",
        lambda _name: "backend failed to start",
    )
    monkeypatch.setattr(
        __name__ + ".time.sleep",
        lambda _interval: (_ for _ in ()).throw(
            AssertionError("sleep must not follow an exited state")
        ),
    )

    with pytest.raises(RuntimeError, match="exited with code 1") as error:
        TestDevelopmentCommandsE2E._wait_for_container_running("backend")

    assert "backend failed to start" in str(error.value)
    assert statuses == []


@pytest.mark.e2e
def test_wait_for_container_running_query_failure_fails_immediately(monkeypatch):
    """A Docker query error is surfaced without treating it as an absent state."""
    monkeypatch.setattr(
        __name__ + ".get_container_status",
        Mock(side_effect=DockerContainerStatusError("daemon unavailable")),
    )
    monkeypatch.setattr(
        __name__ + ".time.sleep",
        lambda _interval: (_ for _ in ()).throw(
            AssertionError("sleep must not follow a query failure")
        ),
    )

    with pytest.raises(RuntimeError, match="status query failed"):
        TestDevelopmentCommandsE2E._wait_for_container_running("backend")


@pytest.mark.e2e
def test_wait_for_container_running_timeout_reports_last_structured_state(
    monkeypatch, capsys
):
    """A timeout reports the last state while retaining bounded polling behavior."""
    get_status = Mock(return_value=ContainerStatus("created", display_status="Created"))
    sleep = Mock()
    monkeypatch.setattr(
        __name__ + ".get_container_status",
        get_status,
    )
    monkeypatch.setattr(__name__ + ".time.sleep", sleep)
    assert not TestDevelopmentCommandsE2E._wait_for_container_running(
        "backend", timeout=2.0, interval=1.0
    )

    assert get_status.call_count == 2
    assert sleep.call_count == 2
    assert "last observed state: created" in capsys.readouterr().out


def test_emit_container_diagnostics_includes_frontend_logs(monkeypatch, tmp_path):
    """Diagnostics request bounded logs for both generated services."""
    workflow = TestDevelopmentCommandsE2E()
    run = Mock()
    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(workflow, "_container_prefix", lambda: "diagnostics-scope")
    monkeypatch.setattr(
        __name__ + ".get_docker_compose_command", lambda: ["docker", "compose"]
    )

    workflow._emit_container_diagnostics(str(tmp_path), 43123)

    assert run.call_args_list == [
        call(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                "name=diagnostics-scope",
                "--format",
                "table {{.Names}}\t{{.Status}}\t{{.Ports}}",
            ],
            check=False,
            timeout=5,
        ),
        call(
            ["docker", "compose", "ps"],
            cwd=str(tmp_path),
            check=False,
            timeout=5,
        ),
        call(
            ["docker", "logs", "--tail", "20", "diagnostics-scope_backend"],
            check=False,
            timeout=5,
        ),
        call(
            ["docker", "logs", "--tail", "20", "diagnostics-scope_frontend"],
            check=False,
            timeout=5,
        ),
    ]


def test_emit_container_diagnostics_continues_after_probe_timeout(
    monkeypatch, tmp_path, capsys
):
    """One unavailable probe must not suppress the remaining diagnostics."""
    workflow = TestDevelopmentCommandsE2E()
    run = Mock(
        side_effect=[
            subprocess.TimeoutExpired(["docker", "ps"], 5),
            None,
            None,
            None,
        ]
    )
    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(workflow, "_container_prefix", lambda: "diagnostics-scope")
    monkeypatch.setattr(
        __name__ + ".get_docker_compose_command", lambda: ["docker", "compose"]
    )

    workflow._emit_container_diagnostics(str(tmp_path), 43123)

    assert run.call_count == 4
    assert run.call_args_list[-1] == call(
        ["docker", "logs", "--tail", "20", "diagnostics-scope_frontend"],
        check=False,
        timeout=5,
    )
    assert "diagnostic command failed" in capsys.readouterr().out


def test_emit_container_diagnostics_continues_when_compose_unavailable(
    monkeypatch, tmp_path, capsys
):
    """Unavailable Compose diagnostics must not mask the failed-up assertion."""

    class FakeRunner:
        def invoke(self, _command, _args, env):
            return Mock(exit_code=1, output="up failed")

    workflow = TestDevelopmentCommandsE2E()
    run = Mock()
    get_compose_command = Mock(
        side_effect=DockerComposePluginRequiredError("compose unavailable")
    )
    monkeypatch.setattr(__name__ + ".CliRunner", FakeRunner)
    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(workflow, "_container_prefix", lambda: "diagnostics-scope")
    monkeypatch.setattr(__name__ + ".get_docker_compose_command", get_compose_command)

    with pytest.raises(AssertionError, match="up failed"):
        workflow.test_full_development_workflow(
            tmp_path,
            object(),
            {"PORT": "43123"},
        )

    get_compose_command.assert_called_once_with()
    assert run.call_args_list == [
        call(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                "name=diagnostics-scope",
                "--format",
                "table {{.Names}}\t{{.Status}}\t{{.Ports}}",
            ],
            check=False,
            timeout=5,
        ),
        call(
            ["docker", "logs", "--tail", "20", "diagnostics-scope_backend"],
            check=False,
            timeout=5,
        ),
        call(
            ["docker", "logs", "--tail", "20", "diagnostics-scope_frontend"],
            check=False,
            timeout=5,
        ),
    ]
    assert (
        "<compose diagnostics unavailable: compose unavailable>"
        in capsys.readouterr().out
    )


def test_full_development_workflow_emits_diagnostics_before_up_assertion(
    monkeypatch, tmp_path
):
    """A failed ``up`` records diagnostics before the failure assertion runs."""
    events: list[tuple[str, object]] = []

    class FakeRunner:
        def invoke(self, _command, args, env):
            events.append(("invoke", args))
            return Mock(exit_code=1, output="up failed")

    workflow = TestDevelopmentCommandsE2E()
    monkeypatch.setattr(__name__ + ".CliRunner", FakeRunner)
    monkeypatch.setattr(
        workflow,
        "_emit_container_diagnostics",
        lambda project_path, port: events.append(("diagnostics", (project_path, port))),
    )

    with pytest.raises(AssertionError, match="up failed"):
        workflow.test_full_development_workflow(
            tmp_path,
            object(),
            {"PORT": "43123"},
        )

    assert events == [
        ("invoke", ["up"]),
        ("diagnostics", (str(tmp_path), 43123)),
    ]


def test_full_development_workflow_skips_diagnostics_after_successful_up(
    monkeypatch, tmp_path
):
    """A successful ``up`` advances without failure-only diagnostics."""
    events: list[tuple[str, object]] = []

    class StopAfterUp(RuntimeError):
        pass

    class FakeRunner:
        def invoke(self, _command, args, env):
            events.append(("invoke", args))
            return Mock(exit_code=0, output="Services started successfully!")

    workflow = TestDevelopmentCommandsE2E()
    diagnostics = Mock()
    wait_for_running = Mock(side_effect=StopAfterUp)
    monkeypatch.setattr(__name__ + ".CliRunner", FakeRunner)
    monkeypatch.setattr(workflow, "_container_prefix", lambda: "diagnostics-scope")
    monkeypatch.setattr(workflow, "_emit_container_diagnostics", diagnostics)
    monkeypatch.setattr(workflow, "_wait_for_container_running", wait_for_running)

    with pytest.raises(StopAfterUp):
        workflow.test_full_development_workflow(
            tmp_path,
            object(),
            {"PORT": "43123"},
        )

    assert events == [("invoke", ["up"])]
    diagnostics.assert_not_called()
    wait_for_running.assert_called_once_with("diagnostics-scope_backend", timeout=40.0)


@pytest.mark.e2e
def test_retention_mode_still_precleans_prior_test_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Diagnostic retention must not feed one successful test's state to the next."""
    cleanup = Mock()
    wait = Mock()
    monkeypatch.setenv("QS_E2E_NO_CLEANUP", "1")
    monkeypatch.setattr(__name__ + "._cleanup_labelled_resources", cleanup)
    monkeypatch.setattr(__name__ + ".wait_for_port_release", wait)

    _prepare_e2e_resource_scope("run-scope-gw0", 43123)

    assert _retain_e2e_resources()
    cleanup.assert_called_once_with("run-scope-gw0")
    wait.assert_called_once_with(43123, timeout=5.0)


def test_e2e_host_ports_preserve_parent_reservations_under_xdist(monkeypatch):
    """Workers must not discard the collision-free ports assigned by the runner."""
    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw1")
    monkeypatch.setenv("QS_E2E_APP_PORT", "41001")
    monkeypatch.setenv("QS_E2E_FRONTEND_PORT", "41002")

    def unexpected_allocation() -> int:
        raise AssertionError("parent-reserved ports must not be replaced")

    assert _e2e_host_ports(unexpected_allocation) == ("41001", "41002")


def test_e2e_host_ports_retry_a_duplicate_fallback(monkeypatch):
    """Direct pytest runs allocate distinct app and frontend ports."""
    monkeypatch.delenv("QS_E2E_APP_PORT", raising=False)
    monkeypatch.delenv("QS_E2E_FRONTEND_PORT", raising=False)
    ports = iter((43123, 43123, 45173))

    assert _e2e_host_ports(lambda: next(ports)) == ("43123", "45173")


@pytest.mark.e2e
class TestDevelopmentCommandsE2E:
    """End-to-end tests for development commands with real Docker containers."""

    @staticmethod
    def _get_free_port() -> int:
        """Return an available host port for isolated e2e runs."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    @staticmethod
    def _wait_for_container_running(
        container_name: str, timeout: float = 30.0, interval: float = 1.0
    ) -> bool:
        """Wait for running state, failing promptly on an actionable failure."""
        elapsed = 0.0
        last_status: ContainerStatus | None = None
        while elapsed < timeout:
            try:
                status = get_container_status(container_name)
            except DockerContainerStatusError as error:
                raise RuntimeError(
                    f"Container {container_name!r} status query failed: {error}"
                ) from error
            last_status = status
            if status.state == "running":
                return True
            if status.state == "exited":
                logs = _last_container_logs(container_name)
                raise RuntimeError(
                    f"Container {container_name!r} exited with code {status.exit_code}. "
                    f"Last 20 log lines:\n{logs}"
                )
            time.sleep(interval)
            elapsed += interval
        observed = last_status.state if last_status is not None else "absent"
        print(
            f"Container {container_name!r} did not become running within {timeout:g}s; "
            f"last observed state: {observed}",
            flush=True,
        )
        return False

    @staticmethod
    def _wait_for_http_text(
        url: str, timeout: float = 30.0, interval: float = 1.0
    ) -> str:
        """Return one generated-project response after a bounded readiness poll."""
        elapsed = 0.0
        last_error: Exception | None = None
        while elapsed < timeout:
            try:
                with urllib.request.urlopen(url, timeout=5.0) as response:
                    assert response.status == 200
                    return response.read().decode()
            except (AssertionError, OSError, urllib.error.URLError) as error:
                last_error = error
            time.sleep(interval)
            elapsed += interval
        raise RuntimeError(f"{url} did not return HTTP 200: {last_error}")

    @staticmethod
    def _container_prefix() -> str:
        """Return the per-lane resource prefix for this E2E run."""
        return _worker_resource_scope()

    def _backend_container_name(self) -> str:
        """Return the generated backend container name for this E2E lane."""
        return f"{self._container_prefix()}_backend"

    def _frontend_container_name(self) -> str:
        """Return the generated frontend container name for this E2E lane."""
        return f"{self._container_prefix()}_frontend"

    @staticmethod
    def _run_diagnostic_command(command: list[str], *, cwd: str | None = None) -> None:
        """Run one bounded best-effort diagnostic without masking test failure."""
        try:
            if cwd is None:
                subprocess.run(command, check=False, timeout=5)
            else:
                subprocess.run(command, cwd=cwd, check=False, timeout=5)
        except (OSError, subprocess.SubprocessError) as error:
            print(f"<diagnostic command failed: {error}>", flush=True)

    def _emit_container_diagnostics(
        self, project_path: str, port: int | None = None
    ) -> None:
        """Emit container/compose status and service logs for debugging."""
        container_prefix = self._container_prefix()

        print(f"\n--- Container diagnostics (PORT={port}) ---", flush=True)
        # Show all containers for this project
        self._run_diagnostic_command(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                f"name={container_prefix}",
                "--format",
                "table {{.Names}}\t{{.Status}}\t{{.Ports}}",
            ],
        )
        # Show docker compose ps if project path is given
        if os.path.isdir(project_path):
            try:
                self._run_diagnostic_command(
                    [*get_docker_compose_command(), "ps"],
                    cwd=project_path,
                )
            except DockerComposePluginRequiredError as error:
                print(f"<compose diagnostics unavailable: {error}>", flush=True)
        # Show backend logs (last 20 lines)
        self._run_diagnostic_command(
            ["docker", "logs", "--tail", "20", self._backend_container_name()],
        )
        # Show frontend logs (last 20 lines)
        self._run_diagnostic_command(
            ["docker", "logs", "--tail", "20", self._frontend_container_name()],
        )
        print("--- End diagnostics ---\n", flush=True)

    @pytest.fixture(autouse=True)
    def cleanup_before_test(self, request: pytest.FixtureRequest):
        """Ensure this lane's containers are stopped before each test."""
        if request.node.name.startswith("test_sa142"):
            return
        container_prefix = self._container_prefix()
        try:
            _prepare_e2e_resource_scope(
                container_prefix,
                int(os.environ.get("QS_E2E_APP_PORT", "8000")),
            )
        except Exception as error:
            raise RuntimeError(f"labelled pre-test cleanup failed: {error}") from error

    @pytest.fixture
    def test_project(self, tmp_path):
        """Generate a test project and return its path."""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = _stable_test_project_slug()
        project_path = tmp_path / project_name

        generator.generate(project_name, project_path)

        # Verify project was created
        assert (project_path / "manage.py").exists()
        assert (project_path / "docker-compose.yml").exists()

        yield project_path

        # Cleanup: ensure containers are stopped
        if _retain_e2e_resources():
            return
        try:
            _cleanup_labelled_resources(self._container_prefix())
        except Exception as error:
            raise RuntimeError(f"labelled fixture cleanup failed: {error}") from error

    @pytest.fixture
    def ensure_docker_running(self):
        """Ensure Docker is running before tests."""
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            pytest.skip("Docker is not running")

        try:
            get_docker_compose_command()
        except DockerComposePluginRequiredError as error:
            pytest.skip(str(error))

    @pytest.fixture
    def docker_env(self) -> dict[str, str]:
        """Provide isolated environment for Docker e2e commands"""
        app_port, frontend_port = _e2e_host_ports(self._get_free_port)
        return {
            "PORT": app_port,
            "QUICKSCALE_FRONTEND_HOST_PORT": frontend_port,
            "QUICKSCALE_FRONTEND_ORIGIN": f"http://127.0.0.1:{frontend_port}",
            "QS_E2E_CONTAINER_PREFIX": self._container_prefix(),
            "QS_E2E_RESOURCE_SCOPE": self._container_prefix(),
            "QUICKSCALE_RESOURCE_PREFIX": self._container_prefix(),
            "COMPOSE_PROJECT_NAME": self._container_prefix(),
            "QS_E2E_PROJECT_SLUG": _stable_test_project_slug(),
        }

    def test_sa142_stable_project_inputs_and_retention_mode(self, monkeypatch):
        """Synthetic SA142 proof separates project inputs from retained resources."""
        monkeypatch.setenv("QS_E2E_PROJECT_SLUG", "stable-e2e-project")
        monkeypatch.setenv("QS_E2E_RESOURCE_SCOPE", "run-scope")
        monkeypatch.setenv("QS_E2E_NO_CLEANUP", "1")
        assert _stable_test_project_slug() == "stable-e2e-project"
        worker = os.environ.get("PYTEST_XDIST_WORKER")
        expected_scope = f"run-scope-{worker}" if worker else "run-scope"
        assert self._container_prefix() == expected_scope
        assert _retain_e2e_resources()
        monkeypatch.setenv("QS_E2E_NO_CLEANUP", "0")
        assert not _retain_e2e_resources()

    def test_full_development_workflow(
        self, test_project, ensure_docker_running, docker_env
    ):
        """
        Test complete development workflow end-to-end.

        This test verifies:
        - quickscale up starts containers
        - quickscale ps shows running containers
        - quickscale manage runs Django commands (migrate, test)
        - quickscale shell executes commands in container
        - quickscale logs retrieves service logs
        - quickscale down stops containers
        """
        runner = CliRunner()
        project_path = test_project

        # Change to project directory for commands
        import os

        original_cwd = os.getcwd()
        os.chdir(project_path)

        try:
            # Step 1: Start services
            result = runner.invoke(cli, ["up"], env=docker_env)
            if result.exit_code != 0:
                self._emit_container_diagnostics(
                    str(project_path), int(docker_env["PORT"])
                )
            assert result.exit_code == 0, f"up failed: {result.output}"
            assert "Services started successfully!" in result.output

            # Wait for backend container to be running (bounded poll)
            if not self._wait_for_container_running(
                self._backend_container_name(), timeout=40.0
            ):
                self._emit_container_diagnostics(str(project_path))
                assert False, "Backend container did not become running within 40s"

            # The frontend service must build the SPA JavaScript before it starts Vite.
            # Prove the Django entrypoint uses the live token source and both compiled
            # assets remain available for production.
            app_url = f"http://127.0.0.1:{docker_env['PORT']}"
            root_html = self._wait_for_http_text(f"{app_url}/")
            assert 'id="root"' in root_html
            assert "frontend/assets/index.js" in root_html
            assert self._wait_for_http_text(
                f"{app_url}/static/frontend/assets/index.css"
            )
            assert self._wait_for_http_text(
                f"{app_url}/static/frontend/assets/index.js"
            )

            live_token_url = (
                f"{docker_env['QUICKSCALE_FRONTEND_ORIGIN']}"
                "/static/frontend/src/index.css"
            )
            assert live_token_url in root_html
            token_css = self._wait_for_http_text(live_token_url)
            assert "--primary:" in token_css

            token_probe = "--quickscale-live-token-probe: 192 100% 50%;"
            token_source = project_path / "frontend" / "src" / "index.css"
            token_source.write_text(
                f"{token_source.read_text()}\n:root {{ {token_probe} }}\n"
            )
            assert token_probe in self._wait_for_http_text(live_token_url)

            rendered_shell = runner.invoke(
                cli,
                [
                    "manage",
                    "shell",
                    "-c",
                    (
                        "from django.conf import settings; "
                        "from django.template.loader import render_to_string; "
                        "print(render_to_string('base.html', {'settings': settings}))"
                    ),
                ],
                env=docker_env,
            )
            assert rendered_shell.exit_code == 0, rendered_shell.output
            assert live_token_url in rendered_shell.output

            # Step 2: Check service status
            result = runner.invoke(cli, ["ps"], env=docker_env)
            assert result.exit_code == 0, f"ps failed: {result.output}"

            # Step 3: Run migrations (backend + compose already waited for db health)
            result = runner.invoke(
                cli, ["manage", "migrate", "--noinput"], env=docker_env
            )
            assert result.exit_code == 0, f"manage migrate failed: {result.output}"

            # Step 4: Run generated project tests (verifies pytest is available)
            result = runner.invoke(cli, ["manage", "test"], env=docker_env)
            assert result.exit_code == 0, f"manage test failed: {result.output}"
            # Verify test command ran (generated project may not have tests yet)
            assert (
                "passed" in result.output.lower()
                or "ok" in result.output.lower()
                or "ran 0 tests" in result.output.lower()
            ), f"Test command didn't run properly: {result.output}"

            # Step 5: Execute shell command
            result = runner.invoke(
                cli, ["shell", "-c", "echo 'E2E test'"], env=docker_env
            )
            assert result.exit_code == 0, f"shell failed: {result.output}"

            # Step 6: Retrieve logs
            result = runner.invoke(cli, ["logs", "--tail", "10"], env=docker_env)
            assert result.exit_code == 0, f"logs failed: {result.output}"

            # Step 7: Stop services
            result = runner.invoke(cli, ["down"], env=docker_env)
            assert result.exit_code == 0, f"down failed: {result.output}"
            assert "Services stopped successfully!" in result.output

        finally:
            # Restore original directory
            os.chdir(original_cwd)

    def test_apply_with_docker_runs_migrations_in_container(
        self, tmp_path, ensure_docker_running
    ):
        """Apply with Docker auto-start should run migrations via backend container."""
        runner = CliRunner()
        project_name = f"{self._container_prefix()}_apply_{int(time.time())}"
        port, frontend_port = _e2e_host_ports(self._get_free_port)
        resource_scope = self._container_prefix()
        env = {
            "PORT": port,
            "QUICKSCALE_FRONTEND_HOST_PORT": frontend_port,
            "QS_E2E_CONTAINER_PREFIX": resource_scope,
            "QS_E2E_RESOURCE_SCOPE": resource_scope,
            "QUICKSCALE_RESOURCE_PREFIX": resource_scope,
            "COMPOSE_PROJECT_NAME": resource_scope,
        }
        env["QUICKSCALE_FRONTEND_ORIGIN"] = (
            f"http://127.0.0.1:{env['QUICKSCALE_FRONTEND_HOST_PORT']}"
        )

        with runner.isolated_filesystem(temp_dir=tmp_path):
            # package(default) -> theme=1(showcase_react) -> modules(skip)
            # -> docker.start=Y -> docker.build=Y -> create_superuser=Y -> save=Y
            plan_input = "\n1\n\nY\nY\nY\nY\n"
            result = runner.invoke(cli, ["plan", project_name], input=plan_input)
            assert result.exit_code == 0, f"plan failed: {result.output}"

            original_cwd = os.getcwd()
            os.chdir(project_name)

            try:
                # show_docker_output=N -> proceed=Y
                apply_input = "n\ny\n"
                result = runner.invoke(
                    cli,
                    ["apply"],
                    input=apply_input,
                    env=env,
                )

                assert result.exit_code == 0, f"apply failed: {result.output}"
                assert "Running migrations (Docker)" in result.output
                assert 'localhost" (127.0.0.1), port 5432' not in result.output
                assert "Migrations failed" not in result.output

            finally:
                if not _retain_e2e_resources():
                    runner.invoke(cli, ["down", "--volumes"], env=env)
                os.chdir(original_cwd)

    def test_up_down_lifecycle(self, test_project, ensure_docker_running, docker_env):
        """Test container lifecycle: up → down → up again."""
        runner = CliRunner()
        project_path = test_project

        import os

        original_cwd = os.getcwd()
        os.chdir(project_path)

        try:
            # First up
            result = runner.invoke(cli, ["up"], env=docker_env)
            assert result.exit_code == 0
            # Bounded poll instead of fixed sleep
            if not self._wait_for_container_running(
                self._backend_container_name(), timeout=40.0
            ):
                self._emit_container_diagnostics(str(project_path))
                assert False, "Backend container did not become running within 40s"

            # Down
            result = runner.invoke(cli, ["down"], env=docker_env)
            assert result.exit_code == 0
            wait_for_port_release(int(docker_env.get("PORT", "8000")), timeout=5.0)

            # Second up (verify can restart)
            result = runner.invoke(cli, ["up"], env=docker_env)
            assert result.exit_code == 0
            if not self._wait_for_container_running(
                self._backend_container_name(), timeout=40.0
            ):
                self._emit_container_diagnostics(str(project_path))
                assert False, "Backend container (2nd up) did not become running"

            # Final cleanup (retained in no-cleanup mode)
            if not _retain_e2e_resources():
                result = runner.invoke(cli, ["down"], env=docker_env)
                assert result.exit_code == 0

        finally:
            os.chdir(original_cwd)

    def test_up_with_build_flag(self, test_project, ensure_docker_running, docker_env):
        """Test up command with --build flag."""
        runner = CliRunner()
        project_path = test_project

        import os

        original_cwd = os.getcwd()
        os.chdir(project_path)

        try:
            # Up with build
            result = runner.invoke(cli, ["up", "--build"], env=docker_env)
            assert result.exit_code == 0
            assert "Services started successfully!" in result.output
            if not self._wait_for_container_running(
                self._backend_container_name(), timeout=40.0
            ):
                self._emit_container_diagnostics(str(project_path))
                assert False, "Backend container did not become running within 40s"

            # Cleanup (retained in no-cleanup mode)
            if not _retain_e2e_resources():
                runner.invoke(cli, ["down"], env=docker_env)

        finally:
            os.chdir(original_cwd)

    def test_down_with_volumes(self, test_project, ensure_docker_running, docker_env):
        """Test down command with --volumes flag."""
        runner = CliRunner()
        project_path = test_project

        import os

        original_cwd = os.getcwd()
        os.chdir(project_path)

        try:
            # Start services
            runner.invoke(cli, ["up"], env=docker_env)
            if not self._wait_for_container_running(
                self._backend_container_name(), timeout=40.0
            ):
                self._emit_container_diagnostics(str(project_path))
                assert False, "Backend container did not become running within 40s"

            # Down with volumes
            result = runner.invoke(cli, ["down", "--volumes"], env=docker_env)
            assert result.exit_code == 0
            assert "Services stopped successfully!" in result.output

        finally:
            os.chdir(original_cwd)

    def test_logs_with_options(self, test_project, ensure_docker_running, docker_env):
        """Test logs command with various options."""
        runner = CliRunner()
        project_path = test_project

        import os

        original_cwd = os.getcwd()
        os.chdir(project_path)

        try:
            # Start services
            runner.invoke(cli, ["up"], env=docker_env)
            if not self._wait_for_container_running(
                self._backend_container_name(), timeout=40.0
            ):
                self._emit_container_diagnostics(str(project_path))
                assert False, "Backend container did not become running within 40s"

            # Test logs with tail
            result = runner.invoke(cli, ["logs", "--tail", "5"], env=docker_env)
            assert result.exit_code == 0

            # Test logs with timestamps
            result = runner.invoke(cli, ["logs", "--timestamps"], env=docker_env)
            assert result.exit_code == 0

            # Test logs for specific service
            result = runner.invoke(cli, ["logs", "backend"], env=docker_env)
            assert result.exit_code == 0

            # Cleanup (retained in no-cleanup mode)
            if not _retain_e2e_resources():
                runner.invoke(cli, ["down"], env=docker_env)

        finally:
            os.chdir(original_cwd)

    def test_error_when_not_in_project(self, tmp_path):
        """Test commands fail gracefully when not in a QuickScale project."""
        runner = CliRunner()

        import os

        original_cwd = os.getcwd()
        os.chdir(tmp_path)  # Empty directory, not a project

        try:
            # All development commands should fail with helpful error
            commands = [
                ["up"],
                ["down"],
                ["ps"],
                ["shell"],
                ["manage", "help"],
                ["logs"],
            ]

            for cmd in commands:
                result = runner.invoke(cli, cmd)
                assert result.exit_code == 1
                assert "Not in a QuickScale project directory" in result.output

        finally:
            os.chdir(original_cwd)

    def test_manage_command_no_args(self, test_project, ensure_docker_running):
        """Test manage command fails with helpful error when no args provided."""
        runner = CliRunner()
        project_path = test_project

        import os

        original_cwd = os.getcwd()
        os.chdir(project_path)

        try:
            result = runner.invoke(cli, ["manage"])
            assert result.exit_code == 1
            assert "No Django management command specified" in result.output

        finally:
            os.chdir(original_cwd)

    def test_manage_test_command(self, test_project, ensure_docker_running, docker_env):
        """Test that generated project tests can run (verifies pytest is installed)."""
        runner = CliRunner()
        project_path = test_project

        import os

        original_cwd = os.getcwd()
        os.chdir(project_path)

        try:
            # Start services
            result = runner.invoke(cli, ["up"], env=docker_env)
            assert result.exit_code == 0

            # Wait for backend container to be running (bounded poll)
            if not self._wait_for_container_running(
                self._backend_container_name(), timeout=40.0
            ):
                self._emit_container_diagnostics(str(test_project))
                assert False, "Backend container did not become running within 40s"

            # Run migrations first (up already ran initial migrate, but
            # this verifies the manage command can apply pending migrations)
            result = runner.invoke(
                cli, ["manage", "migrate", "--noinput"], env=docker_env
            )
            assert result.exit_code == 0

            # Run the generated project's tests
            result = runner.invoke(cli, ["manage", "test"], env=docker_env)
            assert result.exit_code == 0, f"Tests failed: {result.output}"
            # Verify test command ran (generated project may not have tests yet)
            assert (
                "pytest" in result.output.lower()
                or "passed" in result.output.lower()
                or "ran 0 tests" in result.output.lower()
            ), f"Test command didn't run properly: {result.output}"

            # Cleanup (retained in no-cleanup mode)
            if not _retain_e2e_resources():
                runner.invoke(cli, ["down"], env=docker_env)

        finally:
            os.chdir(original_cwd)


@pytest.mark.e2e
class TestDevelopmentCommandsIntegration:
    """Integration tests for development commands with Docker."""

    @pytest.fixture
    def generated_project(self, tmp_path):
        """Generate and prepare a project for testing."""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "integration_test"
        project_path = tmp_path / project_name

        generator.generate(project_name, project_path)
        yield project_path

        # Cleanup
        if _retain_e2e_resources():
            return
        try:
            _cleanup_labelled_resources(_worker_resource_scope())
        except Exception as error:
            raise RuntimeError(
                f"labelled integration cleanup failed: {error}"
            ) from error

    def test_docker_compose_configuration_valid(self, generated_project):
        """Verify docker-compose.yml is valid and parseable."""
        result = subprocess.run(
            [*get_docker_compose_command(), "config"],
            cwd=generated_project,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"docker compose config invalid: {result.stderr}"

    def test_project_structure_supports_docker_workflow(self, generated_project):
        """Verify project has all files needed for Docker workflow."""
        required_files = [
            "docker-compose.yml",
            "Dockerfile",
            ".dockerignore",
            "manage.py",
        ]

        for file in required_files:
            assert (generated_project / file).exists(), f"Missing required file: {file}"

    def test_environment_files_present(self, generated_project):
        """Verify environment configuration files exist."""
        # Should have example env file
        env_example = generated_project / ".env.example"
        if env_example.exists():
            content = env_example.read_text()
            # Should have essential config
            assert len(content) > 0
