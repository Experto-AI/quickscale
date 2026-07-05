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
