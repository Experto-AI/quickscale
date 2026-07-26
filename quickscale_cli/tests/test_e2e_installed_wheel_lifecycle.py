"""
End-to-end test for the installed-wheel lifecycle (SA112).

Exercises the full lifecycle of a QuickScale installed artifact:

1.  Provision an isolated venv with built wheels from staged source copies
    (never touches source ``pyproject.toml``).
2.  Plan a new project (``sa112proj``) with all modules via the installed
    ``quickscale`` binary.
3.  Apply the project with real Docker containers and database migrations.
4.  Verify running state with ``quickscale ps``.
5.  Run ``manage migrate --noinput`` through the container.
6.  Clean up with ``quickscale down --volumes``.

All commands run via ``subprocess`` against the installed binary (no Click
``CliRunner``) with a sanitized environment (``PYTHONPATH`` and
``PYTHONHOME`` removed).

Run with::

    QUICKSCALE_DEBUG=1 poetry run pytest \\
        quickscale_cli/tests/test_e2e_installed_wheel_lifecycle.py \\
        -o addopts= --tb=long -ra

Requires Docker and Docker Compose v2.
"""

import os
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path

import pytest

# Source-tree root — same parents[2] resolution as conftest.py.
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Timeout constants (seconds).
provisioning600 = 600  # venv + wheel build
plan120 = 120  # quickscale plan
apply1200 = 1200  # quickscale apply (Docker startup + migrations)
ps60 = 60  # quickscale ps
manage300 = 300  # quickscale manage migrate --noinput
down120 = 120  # quickscale down --volumes


# ---------------------------------------------------------------------------
# Session-scoped fixture — provision once, share across the run.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def installed_quickscale() -> Path:
    """Provision an isolated venv with installed QuickScale wheels.

    Builds wheels from per-run staged source copies (never modifies source
    ``pyproject.toml``), installs them into a throwaway venv, and yields the
    absolute path of the installed ``quickscale`` binary.

    The venv directory is always removed after the session completes.
    """
    venv_dir = Path(tempfile.mkdtemp(prefix="qs-iw-venv-"))
    try:
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)

        result = subprocess.run(
            [
                str(_REPO_ROOT / "scripts" / "provision_installed_venv.sh"),
                str(venv_dir),
            ],
            capture_output=True,
            text=True,
            timeout=provisioning600,
            cwd=_REPO_ROOT,
            env=env,
        )
        assert result.returncode == 0, (
            f"Provisioning failed (rc={result.returncode}):\n"
            f"stderr:\n{result.stderr}\n"
            f"stdout:\n{result.stdout}"
        )

        binary_path_str = result.stdout.strip()
        assert binary_path_str, (
            f"Provisioning produced empty stdout (no binary path):\n"
            f"stderr:\n{result.stderr}"
        )
        binary_path = Path(binary_path_str)
        assert binary_path.is_file() and os.access(str(binary_path), os.X_OK), (
            f"Provisioned binary not executable: {binary_path}"
        )
        # Exactly one line on stdout.
        assert result.stdout.count("\n") <= 1, (
            f"Expected exactly one stdout line, got:\n{result.stdout}"
        )

        yield binary_path

    finally:
        shutil.rmtree(venv_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test-level fixtures.
# ---------------------------------------------------------------------------


@pytest.fixture
def ensure_docker_running():
    """Skip the test if Docker or Docker Compose v2 is unavailable."""
    result = subprocess.run(
        ["docker", "info"], capture_output=True, text=True, timeout=10
    )
    if result.returncode != 0:
        pytest.skip("Docker is not running")

    try:
        subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            check=True,
            timeout=5,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        pytest.skip("Docker Compose v2 (docker compose) is not available")


# ---------------------------------------------------------------------------
# Helper — sanitised environment builder for installed-venv subprocesses.
# ---------------------------------------------------------------------------


def _sanitised_env(port: int, container_prefix: str) -> dict[str, str]:
    """Build an environment dict for installed-venv subprocesses.

    Removes ``PYTHONPATH`` and ``PYTHONHOME`` so the installed artifact
    cannot resolve back into the source tree.  Sets ``PORT`` (Docker host
    port) and ``QS_E2E_CONTAINER_PREFIX`` (container-name namespace) for
    lane isolation.
    """
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PORT"] = str(port)
    env["QS_E2E_CONTAINER_PREFIX"] = container_prefix
    return env


# ---------------------------------------------------------------------------
# The test.
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_installed_wheel_lifecycle(
    installed_quickscale: Path,
    ensure_docker_running,
    tmp_path: Path,
) -> None:
    """Full installed-wheel lifecycle: plan, apply, ps, manage, down.

    Every step uses ``subprocess.run`` with ``check=False``,
    ``capture_output=True``, and ``text=True``.  All steps assert
    ``returncode == 0`` and no ``Traceback`` in output.  The final step
    (``down --volumes``) always runs, even when an earlier step fails, so
    that primary failures are preserved while cleanup is still attempted.
    """
    quickscale_bin = str(installed_quickscale)

    # Working directory — outside the source tree, inside pytest's tmp_path.
    workdir = tmp_path / "qs-iw-work"
    workdir.mkdir(parents=True, exist_ok=True)

    project_name = "sa112proj"
    project_dir = workdir / project_name

    # Container prefix (lane isolation).
    container_prefix = os.environ.get("QS_E2E_CONTAINER_PREFIX", "e2e_cli_test")

    # Host port — from QS_E2E_APP_PORT if set, otherwise bind a free socket.
    port_str = os.environ.get("QS_E2E_APP_PORT", "")
    if port_str:
        port = int(port_str)
    else:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]

    env = _sanitised_env(port, container_prefix)

    # ------------------------------------------------------------------
    # Step 1: Plan
    # ------------------------------------------------------------------
    # Prompts: project-type (default), theme (default), modules (all 12),
    #          docker-start? (y), docker-build? (y), superuser? (y), save? (y)
    plan_input = "\n\n1,2,3,4,5,6,7,8,9,10,11,12\ny\ny\ny\ny\n"

    result = subprocess.run(
        [quickscale_bin, "plan", project_name],
        input=plan_input,
        capture_output=True,
        text=True,
        timeout=plan120,
        cwd=workdir,
        env=env,
    )
    assert result.returncode == 0, (
        f"plan failed (rc={result.returncode}):\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert "Traceback" not in result.stdout
    assert "Traceback" not in result.stderr
    assert project_dir.is_dir(), f"Plan did not create project directory: {project_dir}"

    # ------------------------------------------------------------------
    # Steps 2-5 with mandatory cleanup
    # ------------------------------------------------------------------
    primary_exc: BaseException | None = None

    try:
        # Step 2: Apply (Docker startup, migrations)
        # Prompts: show-docker-output? (n), proceed-with-apply? (y),
        #          destructive-confirm? (y)
        apply_input = "n\ny\ny\n"

        result = subprocess.run(
            [quickscale_bin, "apply"],
            input=apply_input,
            capture_output=True,
            text=True,
            timeout=apply1200,
            cwd=project_dir,
            env=env,
        )
        assert result.returncode == 0, (
            f"apply failed (rc={result.returncode}):\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
        # Docker migration path assertions.
        assert "Running migrations (Docker)" in result.stdout, (
            f"Expected Docker migration path:\n{result.stdout}"
        )
        assert 'localhost" (127.0.0.1), port 5432' not in result.stdout, (
            "Apply fell back to local PostgreSQL despite Docker being available:\n"
            f"{result.stdout}"
        )
        assert "Migrations failed" not in result.stdout, (
            f"Migrations reported failure:\n{result.stdout}"
        )
        assert "Traceback" not in result.stdout
        assert "Traceback" not in result.stderr

        # Step 3: Ps
        result = subprocess.run(
            [quickscale_bin, "ps"],
            capture_output=True,
            text=True,
            timeout=ps60,
            cwd=project_dir,
            env=env,
        )
        assert result.returncode == 0, (
            f"ps failed (rc={result.returncode}):\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
        assert "Traceback" not in result.stdout
        assert "Traceback" not in result.stderr

        # Step 4: Manage migrate --noinput
        result = subprocess.run(
            [quickscale_bin, "manage", "migrate", "--noinput"],
            capture_output=True,
            text=True,
            timeout=manage300,
            cwd=project_dir,
            env=env,
        )
        assert result.returncode == 0, (
            f"manage migrate failed (rc={result.returncode}):\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
        assert "Traceback" not in result.stdout
        assert "Traceback" not in result.stderr

    except BaseException as exc:
        primary_exc = exc
        raise

    finally:
        # Step 5: Always down --volumes (cleanup).
        try:
            subprocess.run(
                [quickscale_bin, "down", "--volumes"],
                capture_output=True,
                text=True,
                timeout=down120,
                cwd=project_dir,
                env=env,
            )
        except BaseException as cleanup_exc:
            if primary_exc is None:
                # No primary failure — cleanup failure is the real error.
                raise
            # Primary failure takes precedence; log cleanup failure.
            print(
                f"Cleanup failure (suppressed; primary failure follows): {cleanup_exc}"
            )
