"""Focused regressions for the generated start.sh and predeploy.sh launchers."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

import quickscale_core
from quickscale_core.generator.runtime_database import runtime_db_template_context


def _render(template_name: str) -> str:
    """Render a generated launcher template with the minimal required context."""
    core_dir = Path(quickscale_core.__file__).resolve().parent
    template_dir = core_dir / "generator" / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    return env.get_template(template_name).render(
        {
            "package_name": "testproject",
            **runtime_db_template_context("testproject"),
        }
    )


def _render_start_sh() -> str:
    return _render("start.sh.j2")


def _render_predeploy_sh() -> str:
    return _render("predeploy.sh.j2")


def test_start_sh_logs_env_status_without_values() -> None:
    """The environment check must report presence without leaking secret values."""
    output = _render_start_sh()

    assert "env | grep" not in output
    assert (
        "critical_vars=(DATABASE_URL SECRET_KEY DEBUG DJANGO_SETTINGS_MODULE "
        "ALLOWED_HOSTS PORT RUNTIME_DATABASE_URL)" in output
    )
    assert 'echo "${var_name}: set"' in output
    assert 'echo "${var_name}: MISSING"' in output


def test_start_sh_keeps_missing_var_warning_path() -> None:
    """The informational warning for missing vars should remain in place."""
    output = _render_start_sh()

    assert "missing_critical_var=0" in output
    assert "missing_critical_var=1" in output
    assert 'echo "⚠️  Some variables may be missing"' in output


def test_start_sh_never_runs_schema_work() -> None:
    """Migrations and the cache table belong to the pre-deploy step."""
    output = _render_start_sh()

    assert "python manage.py migrate" not in output
    assert "python manage.py createcachetable" not in output
    assert "QUICKSCALE_PRIVILEGED_COMMAND" not in output
    assert "predeploy.sh" in output


def test_predeploy_runs_createcachetable_after_migrate() -> None:
    """The pre-deploy script applies migrations before creating the cache table."""
    output = _render_predeploy_sh()

    assert "createcachetable" in output, "predeploy.sh must include createcachetable"

    migrate_index = output.index("python manage.py migrate")
    createcachetable_index = output.index("python manage.py createcachetable")
    assert createcachetable_index > migrate_index, (
        "createcachetable must run after migrate"
    )

    createcachetable_line = next(
        line
        for line in output.splitlines()
        if "python manage.py createcachetable" in line
    )
    assert "QUICKSCALE_PRIVILEGED_COMMAND=createcachetable" in createcachetable_line
    assert 'RUNTIME_DATABASE_URL=""' in createcachetable_line

    migrate_line = next(
        line for line in output.splitlines() if "python manage.py migrate" in line
    )
    assert "QUICKSCALE_PRIVILEGED_COMMAND=migrate" in migrate_line


def test_predeploy_createcachetable_conditional_on_redis() -> None:
    """createcachetable runs only when REDIS_URL is unset (CR-SA34-002)."""
    output = _render_predeploy_sh()

    assert "REDIS_URL:-" in output or 'if [[ -z "${REDIS_URL' in output
    assert "skipping database cache table" in output.lower()
    assert "database cache table via superuser DATABASE_URL" in output


def test_predeploy_createcachetable_sets_privileged_command() -> None:
    """createcachetable selects the superuser URL through the facade contract."""
    output = _render_predeploy_sh()

    createcachetable_line = next(
        line
        for line in output.splitlines()
        if "python manage.py createcachetable" in line
    )
    assert "QUICKSCALE_PRIVILEGED_COMMAND=createcachetable" in createcachetable_line
    assert 'RUNTIME_DATABASE_URL=""' in createcachetable_line
