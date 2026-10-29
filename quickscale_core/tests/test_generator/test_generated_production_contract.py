"""Generated production deployment contract (SA321).

The generated project's production topology is an artifact, not prose:
Railway is the supported production path, schema work runs in ``predeploy.sh``
before the deployment starts, readiness and liveness are separate probes, and
production serving refuses container-local media unless an explicit
development flag permits it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

import quickscale_core
from quickscale_core.generator.runtime_database import runtime_db_template_context
from quickscale_core.generator.runtime_pins import (
    DJANGO_CI_MATRIX_VERSION,
    DJANGO_CONSTRAINT,
    POSTGRES_PATCH_VERSION,
    POSTGRES_VERSION,
    PYTHON_CONSTRAINT,
    PYTHON_DOCKER_TAG,
    PYTHON_PATCH_VERSION,
    PYTHON_VERSION,
    QUICKSCALE_CORE_PIN,
)

_TEMPLATE_DIR = (
    Path(quickscale_core.__file__).resolve().parent / "generator" / "templates"
)


def _render(template_name: str, **overrides: object) -> str:
    """Render one generated-project template with the generator's sample context."""
    environment = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        keep_trailing_newline=True,
    )
    context: dict[str, object] = {
        "project_name": "testproject",
        "package_name": "testproject",
        "theme": "showcase_react",
        "python_version": PYTHON_VERSION,
        "python_patch_version": PYTHON_PATCH_VERSION,
        "python_constraint": PYTHON_CONSTRAINT,
        "python_docker_tag": PYTHON_DOCKER_TAG,
        "django_constraint": DJANGO_CONSTRAINT,
        "django_ci_version": DJANGO_CI_MATRIX_VERSION,
        "postgres_version": POSTGRES_VERSION,
        "postgres_patch_version": POSTGRES_PATCH_VERSION,
        "quickscale_core_pin": QUICKSCALE_CORE_PIN,
        **runtime_db_template_context("testproject"),
        "selected_modules": None,
    }
    context.update(overrides)
    return environment.get_template(template_name).render(context)


def test_railway_config_runs_migrations_pre_deploy() -> None:
    """Railway's pre-deploy step is the artifact's schema gate."""
    config = json.loads(_render("railway.json.j2"))
    deploy = config["deploy"]

    assert deploy["preDeployCommand"] == ["./predeploy.sh"]
    assert deploy["startCommand"] == "./start.sh"
    assert deploy["healthcheckPath"] == "/ready/"


def test_start_sh_leaves_schema_work_to_the_pre_deploy_script() -> None:
    """The serving launcher never mutates the schema at boot."""
    output = _render("start.sh.j2")

    assert "python manage.py migrate" not in output
    assert "python manage.py createcachetable" not in output
    assert "QUICKSCALE_PRIVILEGED_COMMAND" not in output
    assert "predeploy.sh" in output


def test_predeploy_runs_migrate_then_cache_table_as_privileged_commands() -> None:
    """The pre-deploy script owns both schema commands and their order."""
    output = _render("predeploy.sh.j2")

    migrate_index = output.index("python manage.py migrate")
    cache_index = output.index("python manage.py createcachetable")
    assert migrate_index < cache_index

    migrate_line = next(
        line for line in output.splitlines() if "python manage.py migrate" in line
    )
    assert "QUICKSCALE_PRIVILEGED_COMMAND=migrate" in migrate_line
    assert 'RUNTIME_DATABASE_URL=""' in migrate_line

    cache_line = next(
        line
        for line in output.splitlines()
        if "python manage.py createcachetable" in line
    )
    assert "QUICKSCALE_PRIVILEGED_COMMAND=createcachetable" in cache_line
    assert 'RUNTIME_DATABASE_URL=""' in cache_line

    assert "REDIS_URL:-" in output
    assert "skipping database cache table" in output.lower()


def test_dockerfile_keeps_liveness_and_delegates_readiness_to_railway() -> None:
    """Docker probes liveness; Railway gates the deployment on readiness."""
    dockerfile = _render("Dockerfile.j2")

    assert "/healthcheck/" in dockerfile
    assert "chmod +x /app/start.sh /app/predeploy.sh" in dockerfile
    assert 'CMD ["./start.sh"]' in dockerfile


def test_production_settings_exempt_both_probes() -> None:
    """Both probe paths bypass the HTTPS redirect used by monitors."""
    production = _render("project_name/settings/production.py.j2")

    assert 'SECURE_REDIRECT_EXEMPT = [r"^healthcheck/$", r"^ready/$"]' in production
    assert "require_production_media_backend(" in production
    assert 'config("QUICKSCALE_ALLOW_LOCAL_MEDIA", default=False, cast=bool)' in (
        production
    )


def test_readiness_checks_the_database_and_pending_migrations() -> None:
    """Readiness is not a second liveness probe."""
    urls = _render("project_name/urls.py.j2")

    assert "def readiness(" in urls
    assert "MigrationExecutor(connection)" in urls
    assert "pending_plan" in urls
    assert 'path("ready/", readiness, name="readiness")' in urls
    # Liveness stays DB-free.
    healthcheck_body = urls.split("def healthcheck(", 1)[1].split("def readiness(", 1)[
        0
    ]
    assert "connections" not in healthcheck_body
    assert "MigrationExecutor" not in healthcheck_body


def test_rendered_project_test_example_covers_readiness() -> None:
    """A fresh project's own suite pins the readiness response."""
    example = _render("tests/test_example.py.j2")

    assert 'client.get("/ready/")' in example
    assert 'client.get("/healthcheck/")' in example


def test_generated_project_names_one_production_path() -> None:
    """README and OPERATIONS state Railway-only production and the probes."""
    readme = _render("README.md.j2")
    operations = _render("OPERATIONS.md.j2")

    assert "Railway is the supported production path." in readme
    assert "Self-hosted production Compose is not a supported path" in readme
    assert "production serving refuses container-local" in readme.lower()
    assert "predeploy.sh" in readme
    assert "/ready/" in operations
    assert "/healthcheck/" in operations
    assert "predeploy.sh" in operations


def _generate_project(tmp_path: Path) -> tuple[str, Path]:
    """Generate a fresh project without the network-bound lock step."""
    from quickscale_core.generator import ProjectGenerator

    project_name = "deploy_contract_project"
    project_path = tmp_path / project_name
    ProjectGenerator(theme="showcase_react").generate(project_name, project_path)
    (project_path / "logs").mkdir(exist_ok=True)
    return project_name, project_path


def _boot_environment(project_name: str, **overrides: str) -> dict[str, str]:
    """Build a production boot environment with no ambient command modes."""
    environment = dict(os.environ)
    for variable in (
        "PYTHONPATH",
        "MYPYPATH",
        "PWD",
        "OLDPWD",
        "DJANGO_SETTINGS_MODULE",
        "QUICKSCALE_PRIVILEGED_COMMAND",
        "QUICKSCALE_NON_DB_COMMAND",
        "QUICKSCALE_ALLOW_BYPASSRLS",
        "QUICKSCALE_ALLOW_LOCAL_MEDIA",
        "REDIS_URL",
    ):
        environment.pop(variable, None)
    environment.update(
        {
            "ALLOWED_HOSTS": "localhost,127.0.0.1",
            "DATABASE_URL": "postgresql://user:pass@localhost:5432/app",
            "RUNTIME_DATABASE_URL": "postgresql://runtime:pass@localhost:5432/app",
            "SECRET_KEY": "deploy-contract-secret-0123456789abcdefghijklmnopqrstuvwxyz",
            "DJANGO_SETTINGS_MODULE": f"{project_name}.settings.production",
            **overrides,
        }
    )
    return environment


def _boot(
    project_path: Path, environment: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "manage.py", "check"],
        cwd=project_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def test_generated_deployment_refuses_local_media_without_the_flag(
    tmp_path: Path,
) -> None:
    """A production serving boot fails hard on container-local media."""
    project_name, project_path = _generate_project(tmp_path)

    refused = _boot(project_path, _boot_environment(project_name))
    assert refused.returncode != 0, refused.stdout + refused.stderr
    assert "FileSystemStorage" in refused.stdout + refused.stderr

    allowed = _boot(
        project_path,
        _boot_environment(project_name, QUICKSCALE_ALLOW_LOCAL_MEDIA="1"),
    )
    assert allowed.returncode == 0, allowed.stdout + allowed.stderr


def test_generated_deployment_bootstrap_modes_are_exempt_from_the_media_guard(
    tmp_path: Path,
) -> None:
    """Pre-deploy and image-build modes never serve, so local media is fine."""
    project_name, project_path = _generate_project(tmp_path)

    predeploy = _boot(
        project_path,
        _boot_environment(
            project_name,
            QUICKSCALE_PRIVILEGED_COMMAND="migrate",
            RUNTIME_DATABASE_URL="",
        ),
    )
    assert predeploy.returncode == 0, predeploy.stdout + predeploy.stderr

    build = _boot(
        project_path,
        _boot_environment(project_name, QUICKSCALE_NON_DB_COMMAND="collectstatic"),
    )
    assert build.returncode == 0, build.stdout + build.stderr


def test_predeploy_rejects_argv_modes(tmp_path: Path) -> None:
    """The pre-deploy launcher exposes no command modes through argv."""
    rendered = _render("predeploy.sh.j2")
    launcher = tmp_path / "predeploy.sh"
    launcher.write_text(rendered)

    result = subprocess.run(
        ["bash", str(launcher), "some_unsupported_command"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == (
        "ERROR: unsupported predeploy.sh command: some_unsupported_command\n"
    )
