"""Focused regressions for the start.sh template environment logging."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

import quickscale_core


def _render_start_sh() -> str:
    """Render the generated start.sh template with the minimal required context."""
    core_dir = Path(quickscale_core.__file__).resolve().parent
    template_dir = core_dir / "generator" / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    return env.get_template("start.sh.j2").render({"package_name": "testproject"})


def test_start_sh_logs_env_status_without_values() -> None:
    """The environment check must report presence without leaking secret values."""
    output = _render_start_sh()

    assert "env | grep" not in output
    assert (
        "critical_vars=(DATABASE_URL SECRET_KEY DEBUG DJANGO_SETTINGS_MODULE ALLOWED_HOSTS PORT)"
        in output
    )
    assert 'echo "${var_name}: set"' in output
    assert 'echo "${var_name}: MISSING"' in output


def test_start_sh_keeps_missing_var_warning_path() -> None:
    """The informational warning for missing vars should remain in place."""
    output = _render_start_sh()

    assert "missing_critical_var=0" in output
    assert "missing_critical_var=1" in output
    assert 'echo "⚠️  Some variables may be missing"' in output


def test_start_sh_has_createcachetable_after_migrate() -> None:
    """The deploy script must run createcachetable after migrate (SA34).

    SA21.1 added a DatabaseCache fallback when REDIS_URL is unset, but
    ``migrate`` does not create the cache table — on a Redis-less
    deployment the first throttled request raises ``ProgrammingError``.
    SA34 adds ``python manage.py createcachetable`` to the deploy script
    only for DatabaseCache deployments.
    """
    output = _render_start_sh()

    assert "createcachetable" in output, "start.sh must include createcachetable"

    # The createcachetable step must appear after the migrate step
    migrate_index = output.index("python manage.py migrate")
    createcachetable_index = output.index("python manage.py createcachetable")
    assert createcachetable_index > migrate_index, (
        "createcachetable must run after migrate"
    )

    # QUICKSCALE_PRIVILEGED_COMMAND must be set and RUNTIME_DATABASE_URL
    # cleared so the superuser DATABASE_URL is used (the runtime role
    # cannot run DDL)
    createcachetable_line = next(
        line
        for line in output.splitlines()
        if "python manage.py createcachetable" in line
    )
    assert "QUICKSCALE_PRIVILEGED_COMMAND=createcachetable" in createcachetable_line, (
        "createcachetable must be invoked with QUICKSCALE_PRIVILEGED_COMMAND=createcachetable"
    )
    assert 'RUNTIME_DATABASE_URL=""' in createcachetable_line, (
        "createcachetable must be invoked with RUNTIME_DATABASE_URL cleared"
    )

    # The migrate step must also set QUICKSCALE_PRIVILEGED_COMMAND
    migrate_line = next(
        line for line in output.splitlines() if "python manage.py migrate" in line
    )
    assert "QUICKSCALE_PRIVILEGED_COMMAND=migrate" in migrate_line, (
        "migrate must be invoked with QUICKSCALE_PRIVILEGED_COMMAND=migrate"
    )


def test_start_sh_createcachetable_conditional_on_redis() -> None:
    """createcachetable must only run when REDIS_URL is unset (CR-SA34-002).

    When REDIS_URL is set the cache backend is Redis (which manages its
    own tables), so the database cache table is not needed.
    """
    output = _render_start_sh()

    # The Redis guard must be present
    assert "REDIS_URL:-" in output or 'if [[ -z "${REDIS_URL' in output, (
        "start.sh must guard createcachetable behind a REDIS_URL check"
    )

    # When REDIS is set, describe the skip
    assert "skipping database cache table" in output.lower(), (
        "start.sh must describe skipping when REDIS_URL is set"
    )

    # When REDIS is unset, describe the DatabaseCache path
    assert "database cache table via superuser DATABASE_URL" in output, (
        "start.sh must describe the DatabaseCache createcachetable path"
    )


def test_start_sh_createcachetable_sets_privileged_command() -> None:
    """createcachetable must include QUICKSCALE_PRIVILEGED_COMMAND=createcachetable
    alongside RUNTIME_DATABASE_URL=\"\" so the production settings seam selects
    the superuser DATABASE_URL (SA68 Phase 1)."""
    output = _render_start_sh()

    createcachetable_line = next(
        line
        for line in output.splitlines()
        if "python manage.py createcachetable" in line
    )
    assert "QUICKSCALE_PRIVILEGED_COMMAND=createcachetable" in createcachetable_line, (
        "createcachetable must be invoked with QUICKSCALE_PRIVILEGED_COMMAND=createcachetable"
    )
    assert 'RUNTIME_DATABASE_URL=""' in createcachetable_line, (
        "createcachetable must still clear RUNTIME_DATABASE_URL"
    )
