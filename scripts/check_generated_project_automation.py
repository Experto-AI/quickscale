#!/usr/bin/env python3
"""
Execute a freshly generated project's own automation (SA253).

The station renders one fresh ``showcase_react`` project offline (the direct
generator API with ``QS_SKIP_POETRY_LOCK=1``, the same path the sibling
generated-project stations use) and then executes the commands its rendered
automation would run:

* the rendered CI's test command (``Run tests with coverage``) with the
  environment the workflow sets,
* the rendered CI's migrate command (``Run migrations``) with its environment,
* the image's rendered ``HEALTHCHECK`` payload against the project booted under
  its generated production settings and a deployment-style ``ALLOWED_HOSTS``.

Each rendered step must declare ``DATABASE_URL`` itself; the station only
redirects the declared endpoint to its provisioned database, so a rendered
workflow that loses the variable fails here instead of being masked.

This is the execution half of ``generated-ci-fails-out-of-box`` and
``docker-healthcheck-always-unhealthy``: text assertions cannot see a missing
``DATABASE_URL``, a settings module that cannot load, or a probe that always
fails.  The ``make`` recipe runs this station inside
``scripts/provision_ci_postgres.sh run --profile restricted``, so the commands
execute against a private ephemeral PostgreSQL 18 database owned by the
NOBYPASSRLS test role, exactly the class of database the generated CI provisions
with its ``postgres`` service.  Each rendered command keeps its workflow's
environment and program; only ``poetry run`` is mapped onto the repository
interpreter, because the generated project is exercised in place, uninstalled
(the repository venv already carries every generated runtime dependency).

The template renders the tenant-isolation step only for the orgs-bearing
selection; executing that command needs an applied project with the orgs module
embedded, which is E2E territory.  This station executes the test, migrate, and
healthcheck commands the ticket names.

Only a local context is registered: the hosted gate jobs have no PostgreSQL
provisioning step, and the provisioning helper refuses its private local
lifecycle on GitHub Actions.  The Make recipe keeps the lifecycle isolation
intact in both enclosing cases: under an outer lifecycle whose lease is still
exported it reuses that validated lease, and inside the static fan-out -- where
``check_ci_locally.sh`` hides the lease but leaves its scope exported -- it
clears ``QS_PROVISION_SCOPE`` so the helper provisions its own scoped
container instead of joining, and then cleaning up, the enclosing lifecycle's
resources.

Exit codes:
    0 - every rendered command executed cleanly
    1 - a rendered command failed, or the rendered automation is unreadable
"""

from __future__ import annotations

import json
import os
import re
import shlex
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path

import yaml

from quickscale_core.generator import ProjectGenerator

SLUG = "generated-automation-probe"
PACKAGE = SLUG.replace("-", "_")

TEST_STEP_NAME = "Run tests with coverage"
MIGRATE_STEP_NAME = "Run migrations"
SERVER_BOOT_TIMEOUT = 60.0
COMMAND_TIMEOUT = 600.0
PROBE_TIMEOUT = 30.0
DESCRIBE_TIMEOUT = 60.0

_ENV_RE = re.compile(r"^ENV\s+(?P<body>.+)$", re.IGNORECASE)
_HEALTHCHECK_RE = re.compile(r'CMD\s+python3?\s+-c\s+"(?P<payload>.*)"\s*$')


class AutomationError(RuntimeError):
    """A failed generated-automation assertion with an actionable diagnostic."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AutomationError(message)


def _generate_project(root: Path) -> Path:
    _require(
        os.environ.get("QS_SKIP_POETRY_LOCK") == "1",
        "generated-automation fixture generation must disable real Poetry lock execution",
    )
    project = root / SLUG
    ProjectGenerator(theme="showcase_react").generate(SLUG, project)
    return project


def _provisioned_description() -> dict[str, object]:
    """Return the provision helper's projection of the active profile."""
    helper = Path(__file__).resolve().parent / "provision_ci_postgres.sh"
    profile = os.environ.get("QUICKSCALE_POSTGRES_PROFILE", "").strip() or "restricted"
    result = _run_command(
        [str(helper), "describe", "--profile", profile, "--format", "json"],
        cwd=helper.parent.parent,
        environment=dict(os.environ),
        timeout=DESCRIBE_TIMEOUT,
    )
    _require(
        result.returncode == 0,
        f"the provision helper's describe failed (exit {result.returncode}):\n{result.stderr}",
    )
    try:
        description = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AutomationError(f"the provision helper's describe output is not JSON: {exc}") from exc
    _require(
        isinstance(description, dict),
        "the provision helper's describe output is not a mapping",
    )
    return description


def _database_url(description: Mapping[str, object] | None = None) -> str:
    """Build the station's database URL from the provisioned profile's smoke cell."""
    if description is None:
        _require(
            bool(os.environ.get("QUICKSCALE_POSTGRES_LEASE_VALIDATED", "").strip()),
            "the PostgreSQL lifecycle is not provisioned; "
            "run this station through its make recipe "
            "(scripts/provision_ci_postgres.sh run --profile restricted)",
        )
        description = _provisioned_description()
    databases = description.get("databases")
    _require(isinstance(databases, list), "the provisioned profile describes no databases")
    smoke = next(
        (entry for entry in databases if isinstance(entry, dict) and entry.get("module") is None),
        None,
    )
    _require(smoke is not None, "the provisioned profile describes no smoke database")
    role = description.get("role")
    role_name = role.get("name") if isinstance(role, dict) else None
    endpoint = description.get("endpoint")
    host = endpoint.get("host") if isinstance(endpoint, dict) else None
    port = endpoint.get("port") if isinstance(endpoint, dict) else None
    name = smoke.get("name")
    for label, value in (
        ("role name", role_name),
        ("host", host),
        ("port", port),
        ("database name", name),
    ):
        _require(
            isinstance(value, str) and bool(value),
            f"the provisioned profile's {label} is missing",
        )
    return f"postgresql://{role_name}@{host}:{port}/{name}"


def _load_rendered_workflow(project: Path) -> dict[str, object]:
    """Return the rendered CI workflow's ``test`` job mapping."""
    path = project / ".github" / "workflows" / "ci.yml"
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise AutomationError(f"cannot read the rendered CI workflow: {exc}") from exc
    _require(isinstance(document, dict), "the rendered CI workflow is not a mapping")
    jobs = document.get("jobs")
    _require(isinstance(jobs, dict), "the rendered CI workflow declares no jobs")
    job = jobs.get("test")
    _require(isinstance(job, dict), "the rendered CI workflow declares no test job")
    return job


def _rendered_step(job: dict[str, object], name: str) -> tuple[str, dict[str, str]]:
    """Return one rendered step's command and environment by step name."""
    steps = job.get("steps")
    _require(isinstance(steps, list), "the rendered test job declares no steps")
    for step in steps:
        if not isinstance(step, dict) or step.get("name") != name:
            continue
        run = step.get("run")
        _require(
            isinstance(run, str) and bool(run.strip()),
            f"the rendered step {name!r} carries no run command",
        )
        environment = step.get("env") or {}
        _require(
            isinstance(environment, dict),
            f"the rendered step {name!r} environment is not a mapping",
        )
        return run.strip(), {str(key): str(value) for key, value in environment.items()}
    raise AutomationError(f"the rendered CI workflow has no {name!r} step")


def _poetry_run_command(command: str) -> list[str]:
    """Map one rendered ``poetry run`` command onto the repository interpreter."""
    tokens = shlex.split(command)
    _require(
        tokens[:2] == ["poetry", "run"],
        f"the rendered command is not a poetry-run command: {command!r}",
    )
    rest = tokens[2:]
    _require(bool(rest), f"the rendered command has no program: {command!r}")
    if rest[0] in {"python", "python3"}:
        return [sys.executable, *rest[1:]]
    if rest[0] == "pytest":
        return [sys.executable, "-m", "pytest", *rest[1:]]
    raise AutomationError(f"the rendered command program is unsupported: {rest[0]!r}")


def _run_command(
    argv: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    timeout: float,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise AutomationError(f"could not run {argv[0]!r}: {exc}") from exc


def _step_environment(
    project: Path, step_environment: dict[str, str], database_url: str
) -> dict[str, str]:
    """Merge one rendered step's environment onto this station's environment."""
    environment = dict(os.environ)
    environment.update(step_environment)
    environment["DATABASE_URL"] = database_url
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(project), environment.get("PYTHONPATH")) if part
    )
    return environment


def _execute_rendered_step(
    project: Path,
    *,
    label: str,
    command: str,
    step_environment: dict[str, str],
    database_url: str,
) -> None:
    argv = _poetry_run_command(command)
    # The rendered step must declare its database connection itself; the
    # station only redirects that endpoint to its provisioned database. If it
    # supplied a missing DATABASE_URL, a rendered-workflow regression that
    # drops the variable would pass here while a fresh checkout failed.
    _require(
        bool(step_environment.get("DATABASE_URL", "").strip()),
        f"the rendered CI {label} step declares no DATABASE_URL; a fresh checkout "
        "would fail loading the generated settings, and this station must not mask that",
    )
    result = _run_command(
        argv,
        cwd=project,
        environment=_step_environment(project, step_environment, database_url),
        timeout=COMMAND_TIMEOUT,
    )
    _require(
        result.returncode == 0,
        f"the rendered CI {label} command failed (exit {result.returncode}): {command}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
    )
    print(f"✓ Rendered CI {label} command executed cleanly: {command}")


def _logical_stage_lines(dockerfile_text: str) -> list[str]:
    """Return the Dockerfile's final stage as joined logical lines."""
    stages: list[list[str]] = []
    current = ""
    for line in dockerfile_text.splitlines():
        if not current and (not line.strip() or line.strip().startswith("#")):
            continue
        if line.rstrip().endswith("\\"):
            current += line.rstrip()[:-1]
            continue
        current += line
        if current.strip().upper().startswith("FROM "):
            stages.append([])
        if not stages:
            stages.append([])
        stages[-1].append(current)
        current = ""
    _require(bool(stages), "the rendered Dockerfile has no FROM stage")
    return stages[-1]


def _final_stage_environment(dockerfile_text: str) -> dict[str, str]:
    """Return the ENV assignments the image's final stage exports."""
    environment: dict[str, str] = {}
    for line in _logical_stage_lines(dockerfile_text):
        match = _ENV_RE.match(line.strip())
        if match is None:
            continue
        tokens = shlex.split(match.group("body"))
        if not tokens:
            continue
        legacy_key = None
        if "=" not in tokens[0]:
            legacy_key = tokens[0]
            tokens = tokens[1:]
        for token in tokens:
            key, separator, value = token.partition("=")
            if not separator and legacy_key is not None:
                environment[legacy_key] = token
                legacy_key = None
                continue
            if separator:
                environment[key] = value
    return environment


def _healthcheck_payload(dockerfile_text: str) -> str:
    """Return the rendered image HEALTHCHECK's python payload, shell-unescaped."""
    for line in _logical_stage_lines(dockerfile_text):
        match = _HEALTHCHECK_RE.search(line.strip())
        if match is not None:
            return match.group("payload").replace('\\"', '"')
    raise AutomationError("the rendered Dockerfile has no CMD python -c healthcheck payload")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _wait_for_server(port: int, server: subprocess.Popen[str], log_path: Path) -> None:
    """Wait until the booted server accepts connections or proves it died."""
    deadline = time.monotonic() + SERVER_BOOT_TIMEOUT
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise AutomationError(
                "the generated project's server exited before serving:\n"
                f"{log_path.read_text(encoding='utf-8')}"
            )
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.25)
    raise AutomationError(
        "the generated project's server did not accept connections within "
        f"{SERVER_BOOT_TIMEOUT:.0f}s:\n{log_path.read_text(encoding='utf-8')}"
    )


def _verify_healthcheck(project: Path, database_url: str) -> None:
    """Boot the project under its production settings and run the rendered probe."""
    dockerfile = (project / "Dockerfile").read_text(encoding="utf-8")
    payload = _healthcheck_payload(dockerfile)
    port = _free_port()
    environment = dict(os.environ)
    environment.update(_final_stage_environment(dockerfile))
    environment.update(
        {
            "PORT": str(port),
            "SECRET_KEY": "generated-automation-probe-secret-0123456789abcdefghijklmnopqrstuvwxyz",
            # Simulate the deployment environment the shipped deploy command
            # writes (a public domain only): the probe must stay healthy
            # without a loopback ALLOWED_HOSTS entry.
            "ALLOWED_HOSTS": "probe.example.com",
            # Serve under the provisioned restricted role: production settings
            # refuse QUICKSCALE_ALLOW_BYPASSRLS while serving.
            "RUNTIME_DATABASE_URL": database_url,
            "DATABASE_URL": database_url,
            # The probe boots a test deployment without object storage; it
            # explicitly accepts container-local media.
            "QUICKSCALE_ALLOW_LOCAL_MEDIA": "1",
            "PYTHONPATH": str(project),
        }
    )
    log_path = project.parent / "server.log"
    with log_path.open("w", encoding="utf-8") as log:
        server = subprocess.Popen(
            [sys.executable, "manage.py", "runserver", f"127.0.0.1:{port}", "--noreload"],
            cwd=project,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
    try:
        _wait_for_server(port, server, log_path)
        probe = _run_command(
            [sys.executable, "-c", payload],
            cwd=project,
            environment=environment,
            timeout=PROBE_TIMEOUT,
        )
        _require(
            probe.returncode == 0,
            "the rendered image HEALTHCHECK payload failed against the booted project "
            f"(exit {probe.returncode}): {payload}\n"
            f"stdout:\n{probe.stdout}\nstderr:\n{probe.stderr}",
        )
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=10)
    print(f"✓ Rendered image HEALTHCHECK payload executed cleanly: {payload}")


def main() -> int:
    """Render a project, execute its automation, and return the exit code."""
    previous_skip = os.environ.get("QS_SKIP_POETRY_LOCK")
    os.environ["QS_SKIP_POETRY_LOCK"] = "1"
    try:
        with tempfile.TemporaryDirectory(prefix="quickscale-generated-automation-") as temp_name:
            project = _generate_project(Path(temp_name))
            database_url = _database_url()
            job = _load_rendered_workflow(project)
            test_command, test_environment = _rendered_step(job, TEST_STEP_NAME)
            migrate_command, migrate_environment = _rendered_step(job, MIGRATE_STEP_NAME)
            _execute_rendered_step(
                project,
                label="test",
                command=test_command,
                step_environment=test_environment,
                database_url=database_url,
            )
            _execute_rendered_step(
                project,
                label="migrate",
                command=migrate_command,
                step_environment=migrate_environment,
                database_url=database_url,
            )
            _verify_healthcheck(project, database_url)
        print("✓ Generated-project CI test, CI migrate, and image healthcheck are clean")
        return 0
    except (
        AutomationError,
        OSError,
        subprocess.SubprocessError,
        ValueError,
        yaml.YAMLError,
    ) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    finally:
        if previous_skip is None:
            os.environ.pop("QS_SKIP_POETRY_LOCK", None)
        else:
            os.environ["QS_SKIP_POETRY_LOCK"] = previous_skip


if __name__ == "__main__":
    raise SystemExit(main())
