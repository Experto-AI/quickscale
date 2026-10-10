"""
Hermetic contracts for the generated-project automation station (SA253).

The station's parse, translation, and environment helpers are exercised
directly on synthetic rendered files.  The full render-execute cycle belongs to
the registered gate itself, which runs inside the provisioned PostgreSQL
environment, not to this suite.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import scripts.check_generated_project_automation as station


def test_make_recipe_keeps_lifecycle_isolation() -> None:
    """The recipe reuses an exported lease and provisions privately otherwise."""
    scripts_dir = Path(__file__).resolve().parent
    registry = json.loads((scripts_dir / "gate_registry.json").read_text(encoding="utf-8"))
    gate = next(
        entry for entry in registry["gates"] if entry["id"] == "check-generated-project-automation"
    )
    recipe = "\n".join(gate["make_recipe"])
    assert '[ -n "$${QUICKSCALE_POSTGRES_LEASE:-}" ]' in recipe
    assert "QS_PROVISION_SCOPE= scripts/provision_ci_postgres.sh run" in recipe
    gates_mk = (scripts_dir / "gates.mk").read_text(encoding="utf-8")
    assert "QS_PROVISION_SCOPE= scripts/provision_ci_postgres.sh run" in gates_mk


def test_poetry_run_command_maps_rendered_programs() -> None:
    """``poetry run`` maps onto this interpreter for python and pytest commands."""
    assert station._poetry_run_command("poetry run pytest --cov=probe") == [
        sys.executable,
        "-m",
        "pytest",
        "--cov=probe",
    ]
    assert station._poetry_run_command("poetry run python manage.py migrate --noinput") == [
        sys.executable,
        "manage.py",
        "migrate",
        "--noinput",
    ]


def test_poetry_run_command_fails_closed() -> None:
    """A command the station cannot faithfully execute is rejected, never guessed."""
    with pytest.raises(station.AutomationError, match="not a poetry-run"):
        station._poetry_run_command("pytest --cov=probe")
    with pytest.raises(station.AutomationError, match="program is unsupported"):
        station._poetry_run_command("poetry run ruff check .")


def test_rendered_step_returns_command_and_environment() -> None:
    """A named step yields its command and environment mapping."""
    job: dict[str, object] = {
        "steps": [
            {"uses": "actions/checkout@v6"},
            {
                "name": "Run tests with coverage",
                "run": "poetry run pytest --cov=probe\n",
                "env": {"DATABASE_URL": "postgres://postgres@localhost/postgres"},
            },
        ]
    }
    command, environment = station._rendered_step(job, "Run tests with coverage")
    assert command == "poetry run pytest --cov=probe"
    assert environment == {"DATABASE_URL": "postgres://postgres@localhost/postgres"}


def test_rendered_step_fails_closed_on_a_missing_step() -> None:
    """A rendering that drops the named step is an error, not a silent pass."""
    with pytest.raises(station.AutomationError, match="no 'Run migrations' step"):
        station._rendered_step({"steps": []}, "Run migrations")


def test_database_url_requires_the_provisioned_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the provisioning lease the station names its make recipe."""
    monkeypatch.delenv("QUICKSCALE_POSTGRES_LEASE_VALIDATED", raising=False)
    with pytest.raises(station.AutomationError, match="make recipe"):
        station._database_url()


DESCRIPTION_FIXTURE: dict[str, object] = {
    "databases": [
        {"key": "smoke", "module": None, "name": "test_qs_restricted_local_1_smoke"},
        {"key": "auth", "module": "auth", "name": "test_qs_restricted_local_1_auth"},
    ],
    "role": {"name": "quickscale_test_role"},
    "endpoint": {"host": "localhost", "port": "49152"},
}


def test_database_url_reads_the_smoke_cell() -> None:
    """The URL comes from the smoke database, the role, and the dynamic endpoint."""
    assert station._database_url(DESCRIPTION_FIXTURE) == (
        "postgresql://quickscale_test_role@localhost:49152/test_qs_restricted_local_1_smoke"
    )


def test_database_url_fails_without_a_smoke_cell() -> None:
    """A projection without the smoke database is an error, never a guessed name."""
    description = dict(DESCRIPTION_FIXTURE)
    description["databases"] = [{"key": "auth", "module": "auth", "name": "x"}]
    with pytest.raises(station.AutomationError, match="no smoke database"):
        station._database_url(description)


def test_provisioned_description_rejects_a_broken_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A describe run that fails or emits non-JSON fails the station closed."""
    failed = subprocess.CompletedProcess(args=[], returncode=2, stdout="", stderr="boom")
    monkeypatch.setattr(station, "_run_command", lambda *a, **k: failed)
    with pytest.raises(station.AutomationError, match="describe failed"):
        station._provisioned_description()

    broken = subprocess.CompletedProcess(args=[], returncode=0, stdout="not json", stderr="")
    monkeypatch.setattr(station, "_run_command", lambda *a, **k: broken)
    with pytest.raises(station.AutomationError, match="not JSON"):
        station._provisioned_description()


DOCKERFILE_FIXTURE = (
    "# syntax=docker/dockerfile:1\n"
    "FROM python:3.14-slim as builder\n"
    "ENV PYTHONUNBUFFERED=1 \\\n"
    "    BUILDER_ONLY=yes\n"
    'RUN echo "build"\n'
    "FROM python:3.14-slim\n"
    "ENV PYTHONUNBUFFERED=1 \\\n"
    "    PYTHONDONTWRITEBYTECODE=1 \\\n"
    "    DJANGO_SETTINGS_MODULE=probe.settings.production\n"
    "ARG PORT=8000\n"
    "ENV PORT=${PORT}\n"
    "HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \\\n"
    '    CMD python -c "import os, urllib.request; urllib.request.urlopen('
    "urllib.request.Request('http://127.0.0.1:%s/healthcheck/' % "
    "os.environ.get('PORT', '8000'), headers={'Host': 'healthcheck.railway.app'}), "
    'timeout=5)"\n'
    'CMD ["./start.sh"]\n'
)


def test_final_stage_environment_reads_only_the_final_stage() -> None:
    """Builder-stage ENV assignments never leak into the runtime-stage view."""
    environment = station._final_stage_environment(DOCKERFILE_FIXTURE)
    assert "BUILDER_ONLY" not in environment
    assert environment["DJANGO_SETTINGS_MODULE"] == "probe.settings.production"
    assert environment["PORT"] == "${PORT}"
    assert environment["PYTHONDONTWRITEBYTECODE"] == "1"


def test_healthcheck_payload_is_returned_verbatim() -> None:
    """The rendered payload carries the always-admitted Host header intact."""
    payload = station._healthcheck_payload(DOCKERFILE_FIXTURE)
    assert payload == (
        "import os, urllib.request; urllib.request.urlopen("
        "urllib.request.Request('http://127.0.0.1:%s/healthcheck/' % "
        "os.environ.get('PORT', '8000'), headers={'Host': 'healthcheck.railway.app'}), "
        "timeout=5)"
    )


def test_healthcheck_payload_unescapes_shell_quotes() -> None:
    """A payload quoted through the shell keeps its embedded quotes."""
    payload = station._healthcheck_payload(
        "FROM python:3.14-slim\n"
        "HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \\\n"
        '    CMD python -c "import urllib.request; urllib.request.urlopen('
        '\\"http://x/\\", timeout=1)"\n'
    )
    assert payload == ('import urllib.request; urllib.request.urlopen("http://x/", timeout=1)')


def test_healthcheck_payload_fails_closed_without_one() -> None:
    """A Dockerfile that lost its healthcheck fails the station, never passes."""
    with pytest.raises(station.AutomationError, match="no CMD python -c healthcheck"):
        station._healthcheck_payload('FROM python:3.14-slim\nCMD ["./start.sh"]\n')


def test_rendered_step_must_declare_its_database_url(tmp_path: Path) -> None:
    """The station refuses to supply the DATABASE_URL a rendered step must declare."""
    with pytest.raises(station.AutomationError, match="declares no DATABASE_URL"):
        station._execute_rendered_step(
            tmp_path,
            label="test",
            command="poetry run pytest",
            step_environment={},
            database_url="postgresql://role@localhost:49152/smoke",
        )


def test_step_environment_overrides_the_database_and_extends_pythonpath(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The rendered step's variables win, and the project is importable in place."""
    monkeypatch.setenv("PYTHONPATH", "/existing")
    environment = station._step_environment(
        tmp_path,
        {
            "DATABASE_URL": "postgres://placeholder",
            "DJANGO_SETTINGS_MODULE": "probe.settings.local",
        },
        "postgresql://role@localhost:49152/smoke",
    )
    assert environment["DATABASE_URL"] == "postgresql://role@localhost:49152/smoke"
    assert environment["DJANGO_SETTINGS_MODULE"] == "probe.settings.local"
    assert environment["PYTHONPATH"] == f"{tmp_path}{os.pathsep}/existing"
