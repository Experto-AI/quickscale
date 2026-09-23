#!/usr/bin/env python3
"""
Run Django's deployment checks against a freshly generated project (SA200).

The station renders one fresh ``showcase_react`` project and runs the real
``manage.py check --deploy`` in both forwarding cells the generated production
settings support:

* ``USE_X_FORWARDED_FOR=True`` — the proxied deployment default, and
* ``USE_X_FORWARDED_FOR=False`` — the single-host deployment.

Any deploy warning outside the recorded baseline fails the gate, so a
settings-template regression that changes the deployment posture is caught
before it ships.  The single-host cell additionally asserts the invariant
Django's own checks do not cover: ``SECURE_PROXY_SSL_HEADER`` must be unset
when forwarding trust is off, so a client-supplied ``X-Forwarded-Proto``
cannot suppress the HTTPS redirect or set secure cookies on a plaintext
response.

The maintainer venv does not lock ``dj-database-url`` (only generated projects
declare it), so the gate renders a minimal ``parse`` shim for the generated
settings import and runs the generated ``manage.py`` under the repository
interpreter.  The shim is a gate fixture, never deployment code: the check
command and the settings it loads are the real generated artifacts.

Exit codes:
    0 - both forwarding cells are clean
    1 - a deploy warning, a check failure, or a posture invariant failed
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from quickscale_core.generator import ProjectGenerator

SLUG = "deploy-posture-probe"
PACKAGE = SLUG.replace("-", "_")

# Fresh generated projects currently emit no deploy-tagged warnings.  An entry
# belongs here only with a recorded reason; a template change that introduces a
# new warning fails the gate until this baseline is deliberately amended.
ALLOWED_DEPLOY_WARNINGS: frozenset[str] = frozenset()

# Cell name -> the USE_X_FORWARDED_FOR value the generated production settings
# read from the environment.
FORWARDING_CELLS: tuple[tuple[str, str], ...] = (
    ("forwarded", "True"),
    ("single-host", "False"),
)

_WARNING_LINE = re.compile(r"^\?: \(([\w.]+)\)", re.MULTILINE)
_PROXY_HEADER_EXPECTED = ("HTTP_X_FORWARDED_PROTO", "https")

_DJ_DATABASE_URL_SHIM = '''"""Minimal dj_database_url stand-in for the deploy-posture gate."""

from urllib.parse import urlsplit


def parse(url, conn_max_age=0, conn_health_checks=False, engine=None, **kwargs):
    """Parse a database URL the way generated settings consume it."""
    parts = urlsplit(url)
    return {
        "ENGINE": engine or "django.db.backends.postgresql",
        "NAME": (parts.path or "/").lstrip("/"),
        "USER": parts.username or "",
        "PASSWORD": parts.password or "",
        "HOST": parts.hostname or "",
        "PORT": str(parts.port or ""),
        "CONN_MAX_AGE": conn_max_age,
        "CONN_HEALTH_CHECKS": conn_health_checks,
    }
'''


class DeployPostureError(RuntimeError):
    """A failed deploy-posture assertion with an actionable diagnostic."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DeployPostureError(message)


def _generate_project(root: Path) -> Path:
    _require(
        os.environ.get("QS_SKIP_POETRY_LOCK") == "1",
        "deploy-posture fixture generation must disable real Poetry lock execution",
    )
    project = root / SLUG
    ProjectGenerator(theme="showcase_react").generate(SLUG, project)
    # STATICFILES_DIRS points at <project>/static; creating the empty directory
    # keeps the staticfiles.W004 warning out of the baseline so every warning
    # observed by the check is a new one.
    (project / "static").mkdir(exist_ok=True)
    return project


def _install_dj_database_url_shim(root: Path) -> Path:
    shim_dir = root / "dj-database-url-shim"
    shim_dir.mkdir()
    (shim_dir / "dj_database_url.py").write_text(_DJ_DATABASE_URL_SHIM, encoding="utf-8")
    return shim_dir


def _cell_environment(project: Path, shim_dir: Path, *, use_x_forwarded_for: str) -> dict[str, str]:
    environment = dict(os.environ)
    for variable in (
        "QUICKSCALE_PRIVILEGED_COMMAND",
        "QUICKSCALE_NON_DB_COMMAND",
        "QUICKSCALE_ALLOW_BYPASSRLS",
    ):
        environment.pop(variable, None)
    environment.update(
        {
            "ALLOWED_HOSTS": "example.com",
            "DJANGO_SETTINGS_MODULE": f"{PACKAGE}.settings.production",
            "SECRET_KEY": ("deploy-posture-probe-secret-0123456789abcdefghijklmnopqrstuvwxyz"),
            "RUNTIME_DATABASE_URL": "postgresql://probe:probe@localhost:5432/probe",
            "USE_X_FORWARDED_FOR": use_x_forwarded_for,
        }
    )
    # The shim comes first so the station behaves identically whether or not an
    # ad-hoc ``dj_database_url`` install happens to exist in the venv.
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(shim_dir), str(project), environment.get("PYTHONPATH")) if part
    )
    return environment


def _run_deploy_check(project: Path, environment: dict[str, str]) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, "manage.py", "check", "--deploy"],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    return result.returncode, f"{result.stdout}\n{result.stderr}"


def _deploy_warning_ids(output: str) -> set[str]:
    return set(_WARNING_LINE.findall(output))


def _assert_proxy_header_cell(
    project: Path, environment: dict[str, str], *, expected_trusted: bool
) -> None:
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from importlib import import_module; "
                f"settings = import_module('{PACKAGE}.settings.production'); "
                "print(repr(settings.SECURE_PROXY_SSL_HEADER)); "
                "print(repr(settings.USE_X_FORWARDED_FOR))"
            ),
        ],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    _require(
        probe.returncode == 0,
        "generated production settings failed an isolated import probe:\n"
        f"stdout:\n{probe.stdout}\nstderr:\n{probe.stderr}",
    )
    header_line, _, forwarding_line = probe.stdout.strip().partition("\n")
    header = ast.literal_eval(header_line)
    expected_header = _PROXY_HEADER_EXPECTED if expected_trusted else None
    _require(
        header == expected_header,
        "SECURE_PROXY_SSL_HEADER deploy posture is wrong: "
        f"expected {expected_header!r} with forwarding trust "
        f"{'enabled' if expected_trusted else 'disabled'}, got {header!r}",
    )
    _require(
        forwarding_line == ("True" if expected_trusted else "False"),
        f"USE_X_FORWARDED_FOR cell did not take effect: got {forwarding_line!r}",
    )


def main() -> int:
    previous_skip = os.environ.get("QS_SKIP_POETRY_LOCK")
    os.environ["QS_SKIP_POETRY_LOCK"] = "1"
    try:
        with tempfile.TemporaryDirectory(prefix="quickscale-deploy-posture-") as temp_name:
            root = Path(temp_name)
            project = _generate_project(root)
            shim_dir = _install_dj_database_url_shim(root)
            for cell_name, use_x_forwarded_for in FORWARDING_CELLS:
                environment = _cell_environment(
                    project, shim_dir, use_x_forwarded_for=use_x_forwarded_for
                )
                returncode, output = _run_deploy_check(project, environment)
                _require(
                    returncode == 0,
                    f"[{cell_name}] manage.py check --deploy exited {returncode}:\n{output}",
                )
                warning_ids = _deploy_warning_ids(output)
                _require(
                    not ("WARNINGS:" in output and not warning_ids),
                    f"[{cell_name}] deploy-check warnings were reported in an "
                    f"unrecognized format, so the baseline cannot be trusted:\n{output}",
                )
                unexpected = sorted(warning_ids - ALLOWED_DEPLOY_WARNINGS)
                _require(
                    not unexpected,
                    f"[{cell_name}] new Django deploy warning(s) {unexpected}:\n{output}",
                )
                _assert_proxy_header_cell(
                    project,
                    environment,
                    expected_trusted=use_x_forwarded_for == "True",
                )
                print(
                    "✓ Generated deploy posture clean in the "
                    f"{cell_name} cell (USE_X_FORWARDED_FOR={use_x_forwarded_for})"
                )
        print("✓ Generated-project deploy posture is clean in both forwarding cells")
        return 0
    except (
        DeployPostureError,
        OSError,
        SyntaxError,
        subprocess.SubprocessError,
        ValueError,
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
