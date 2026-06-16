"""Docker-free generated-project runtime smoke test.

Validates that a generated project with an embedded auth module can boot,
migrate, and serve an HTTP route with a successful outcome (2xx/3xx) —
proving generator fidelity without requiring Docker, PostgreSQL, or browser
automation.

This test is collected by the default CI path (``pytest quickscale_core/tests/
-m "not e2e"``) so generator regressions surface in daily PR feedback.

Phase 14.3 of the roadmap (Finding 14 — generator-runtime test coverage).
"""

import os
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_LOCAL_ARTIFACT_NAMES = frozenset(
    {
        ".mypy_cache",
        ".pnpm-store",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "build",
        "coverage.json",
        "coverage.xml",
        "dist",
        "htmlcov",
        "node_modules",
    }
)
REPO_LOCAL_ARTIFACT_SUFFIXES = (".egg-info", ".pyc", ".pyo")


def _is_repo_local_artifact(entry_name: str) -> bool:
    """Return whether a copied repo entry is a local-only artifact."""
    return (
        entry_name in REPO_LOCAL_ARTIFACT_NAMES
        or entry_name == ".coverage"
        or entry_name.startswith(".coverage.")
        or entry_name.endswith(REPO_LOCAL_ARTIFACT_SUFFIXES)
    )


def _ignore_repo_local_artifacts(_directory: str, entries: list[str]) -> list[str]:
    """Filter repo-local caches and coverage artifacts out of smoke-test copies."""
    return [entry for entry in entries if _is_repo_local_artifact(entry)]


def _copytree_for_generated_project_smoke(source: Path, destination: Path) -> None:
    """Copy shipped module content without repo-local test and cache artifacts."""
    shutil.copytree(
        source,
        destination,
        ignore=_ignore_repo_local_artifacts,
    )


def _is_poetry_network_failure(output: str) -> bool:
    """Detect Poetry/PyPI connectivity failures."""
    lowered = output.lower()
    markers = [
        "all attempts to connect to pypi.org failed",
        "hostname cannot be resolved by your dns",
        "your network is not connected to the internet",
        "nameresolutionerror",
        "connection error",
    ]
    return any(marker in lowered for marker in markers)


def _find_free_port() -> int:
    """Find a free port by binding to port 0 and letting the OS assign one."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


def _install_project_dependencies(project_path: Path) -> None:
    """Install dependencies in the generated project using poetry.

    Skips the test when PyPI is unreachable so CI does not fail on
    transient network issues.
    """
    lock_result = subprocess.run(
        ["poetry", "lock"],
        cwd=project_path,
        capture_output=True,
        text=True,
        timeout=120,
    )
    lock_output = f"{lock_result.stdout}\n{lock_result.stderr}"
    if lock_result.returncode != 0 and _is_poetry_network_failure(lock_output):
        pytest.skip("PyPI is unreachable in this environment")
    assert lock_result.returncode == 0, f"Poetry lock failed: {lock_result.stderr}"

    install_result = subprocess.run(
        ["poetry", "install", "--no-interaction"],
        cwd=project_path,
        capture_output=True,
        text=True,
        timeout=180,
    )
    install_output = f"{install_result.stdout}\n{install_result.stderr}"
    if install_result.returncode != 0 and _is_poetry_network_failure(install_output):
        pytest.skip("PyPI is unreachable in this environment")
    assert install_result.returncode == 0, (
        f"Poetry install failed: {install_result.stderr}"
    )


def _write_sqlite_test_settings(project_path: Path, project_name: str) -> None:
    """Write a test settings module that uses SQLite instead of PostgreSQL."""
    settings_content = '''"""Runtime smoke test settings — uses SQLite (no Docker required)."""
from .base import *  # noqa: F401, F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test_smoke.db",  # noqa: F405
    }
}

DEBUG = False
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Override the base settings' manifest-based staticfiles storage
# (whitenoise.storage.CompressedManifestStaticFilesStorage) with the simple
# in-place backend.  The smoke test does not run ``collectstatic``, so the
# manifest file does not exist; without this override, any template
# reference to a static asset (e.g. ``images/favicon.svg`` in the auth
# login page) raises ``ValueError: Missing staticfiles manifest entry``.
# This mirrors the override that ``local.py`` applies for development.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
'''
    settings_path = project_path / project_name / "settings" / "test_smoke.py"
    settings_path.write_text(settings_content)


def _run_migrations(project_path: Path, project_name: str) -> None:
    """Run database migrations against the SQLite test database."""
    result = subprocess.run(
        ["poetry", "run", "python", "manage.py", "migrate", "--noinput"],
        cwd=project_path,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "DJANGO_SETTINGS_MODULE": f"{project_name}.settings.test_smoke",
        },
    )
    assert result.returncode == 0, (
        f"Migrations failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


def _start_dev_server(
    project_path: Path, project_name: str, port: int
) -> subprocess.Popen[str]:
    """Start Django development server in background with SQLite settings."""
    return subprocess.Popen(
        [
            "poetry",
            "run",
            "python",
            "manage.py",
            "runserver",
            str(port),
            "--noreload",
        ],
        cwd=project_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env={
            **os.environ,
            "DJANGO_SETTINGS_MODULE": f"{project_name}.settings.test_smoke",
        },
        text=True,
        bufsize=1,
    )


def _wait_for_server(
    url: str, timeout: int = 30, server_process: subprocess.Popen[str] | None = None
) -> None:
    """Wait for the development server to accept TCP connections.

    This checks TCP connectivity only (not HTTP status), so it succeeds even
    when the root URL returns a non-200 response. The actual route assertion
    is handled separately by ``_assert_url_responds``.
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80

    start_time = time.time()

    while time.time() - start_time < timeout:
        if server_process is not None and server_process.poll() is not None:
            output = server_process.stdout.read() if server_process.stdout else ""
            raise RuntimeError(
                f"Server process exited with code {server_process.returncode}.\n"
                f"Output:\n{output}"
            )
        try:
            with socket.create_connection((host, port), timeout=2):
                return
        except (OSError, ConnectionRefusedError):
            time.sleep(0.5)

    error_msg = f"Server did not start within {timeout} seconds."
    if server_process is not None and server_process.stdout:
        output_lines: list[str] = []
        try:
            for _ in range(20):
                line = server_process.stdout.readline()
                if not line:
                    break
                output_lines.append(line)
            if output_lines:
                error_msg += f"\n\nServer output:\n{''.join(output_lines)}"
        except Exception:
            pass
    raise TimeoutError(error_msg)


def _assert_url_responds(url: str, timeout: int = 15) -> None:
    """Assert that a URL responds with a successful HTTP status (2xx/3xx).

    Requires the embedded module's route to return a successful outcome —
    a 2xx or 3xx response — proving that the URL routing is wired **and**
    the route serves a valid page or redirect.  4xx and 5xx responses are
    treated as failures so that missing routes or server crashes are caught
    rather than silently passing the smoke test.
    """
    start = time.time()
    last_error: Exception | None = None

    while time.time() - start < timeout:
        try:
            response = urllib.request.urlopen(url, timeout=2)
            status = response.getcode()
            if 200 <= status < 400:
                return
            last_error = AssertionError(
                f"URL {url} returned unexpected status {status}"
            )
        except urllib.error.HTTPError as exc:
            # 4xx/5xx means the server is up but the route is broken —
            # do not treat this as success.
            last_error = AssertionError(
                f"URL {url} returned HTTP {exc.code}: {exc.reason}"
            )
            break
        except (urllib.error.URLError, OSError) as exc:
            last_error = exc
        time.sleep(0.5)

    raise AssertionError(
        f"URL {url} did not respond successfully within {timeout}s. "
        f"Last error: {last_error}"
    )


def _stop_server(server_process: subprocess.Popen[str]) -> None:
    """Terminate the development server process."""
    try:
        server_process.terminate()
        server_process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        server_process.kill()
        server_process.wait(timeout=2)


class TestGeneratedProjectRuntimeSmoke:
    """Docker-free runtime smoke test for generated projects with embedded modules.

    Validates that an embedded-module generated project can:
    1. Generate project scaffold
    2. Embed the auth module
    3. Wire declarative config + managed settings/URLs
    4. Install dependencies via Poetry
    5. Run migrations against SQLite
    6. Boot a development server
    7. Serve an auth-module route (/accounts/profile/) with a successful outcome
       (2xx/3xx) — proving the embedded module's URL routing is wired AND the
       route serves a valid redirect, not just that the server accepts TCP
       connections

    This test is NOT marked ``@pytest.mark.e2e`` so it is collected by the
    default CI path (``pytest quickscale_core/tests/ -m "not e2e"``).
    """

    def test_embedded_auth_module_boots_and_serves_login(self, tmp_path: Path) -> None:
        """A generated project with embedded auth should boot, migrate, and serve an auth route.

        Requires a successful HTTP outcome (2xx/3xx) for an auth-module route so that
        404 (missing URL wiring) and 5xx (server crash) are caught as failures
        rather than silently passing the smoke test.

        Uses /accounts/profile/ instead of /accounts/login/ because the profile route
        returns 302 (redirect to login) for anonymous users, which is a reliable 3xx
        outcome that proves the auth module's URL routing is wired without requiring
        the allauth login template to render successfully.
        """
        from quickscale_cli.commands.module_config import get_default_auth_config
        from quickscale_cli.utils.module_dependency_sync import (
            sync_project_module_dependencies,
        )
        from quickscale_cli.utils.module_wiring_manager import (
            regenerate_managed_wiring,
        )
        from quickscale_core.generator import ProjectGenerator

        # Phase 1: Generate project scaffold (HTML theme — no frontend build).
        project_name = "runtime_smoke_auth"
        project_path = tmp_path / project_name
        ProjectGenerator(theme="showcase_html").generate(project_name, project_path)

        assert (project_path / "manage.py").exists()
        assert (project_path / "pyproject.toml").exists()

        # Phase 2: Embed the auth module via direct copy (no git subtree needed).
        embedded_auth_path = project_path / "modules" / "auth"
        _copytree_for_generated_project_smoke(
            REPO_ROOT / "quickscale_modules" / "auth",
            embedded_auth_path,
        )
        assert (embedded_auth_path / "module.yml").exists(), (
            "Auth module manifest missing after embed"
        )
        assert (embedded_auth_path / "pyproject.toml").exists(), (
            "Auth module pyproject.toml missing after embed"
        )

        # Phase 3: Write declarative config and sync dependencies.
        auth_options = get_default_auth_config()
        self._write_quickscale_yml_with_auth(
            project_path, project_name, "showcase_html", auth_options
        )

        sync_result = sync_project_module_dependencies(
            project_path, {"auth": auth_options}
        )
        assert "quickscale-module-auth" in sync_result.added_path_dependencies, (
            "sync_project_module_dependencies did not register the auth module "
            f"as a path dependency: {sync_result}"
        )

        # Phase 4: Regenerate managed wiring (settings + URLs).
        success, message = regenerate_managed_wiring(project_path)
        assert success, f"regenerate_managed_wiring failed: {message}"

        # Phase 5: Install dependencies.
        _install_project_dependencies(project_path)

        # Phase 6: Write SQLite test settings and run migrations.
        _write_sqlite_test_settings(project_path, project_name)
        _run_migrations(project_path, project_name)

        # Phase 7: Boot development server and assert HTTP route.
        server_port = _find_free_port()
        server_process = _start_dev_server(project_path, project_name, server_port)

        try:
            _wait_for_server(
                f"http://localhost:{server_port}",
                timeout=30,
                server_process=server_process,
            )
            _assert_url_responds(f"http://localhost:{server_port}/accounts/profile/")
        finally:
            _stop_server(server_process)

    @staticmethod
    def _write_quickscale_yml_with_auth(
        project_path: Path,
        project_name: str,
        theme: str,
        auth_options: dict[str, object],
    ) -> None:
        """Write a minimal quickscale.yml that declares the auth module."""
        import yaml

        config_payload = {
            "version": "1",
            "project": {
                "slug": project_name,
                "package": project_name,
                "theme": theme,
            },
            "docker": {"start": False},
            "modules": {"auth": dict(auth_options)},
        }
        rendered = yaml.safe_dump(
            config_payload,
            sort_keys=False,
            default_flow_style=False,
        )
        (project_path / "quickscale.yml").write_text(rendered)
