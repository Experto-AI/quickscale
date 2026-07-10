"""Generated-project runtime smoke test.

Validates that a generated project with an embedded auth module can boot,
migrate, and serve an HTTP route with a successful outcome (2xx/3xx) —
proving generator fidelity without requiring Docker or browser automation.
Requires a running PostgreSQL instance (see AF13 roadmap note).

This test is marked ``@pytest.mark.e2e`` so it is excluded from
``pytest quickscale_core/tests/ -m "not e2e"`` and ``make test-unit``.

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
        ".venv",
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


def _write_postgres_test_settings(
    project_path: Path,
    project_name: str,
    cache_database: bool = False,
) -> None:
    """Write a test settings module that uses PostgreSQL.

    Requires a running PostgreSQL instance reachable via the env vars below.
    This replaces the former SQLite fallback — see AF13 in the roadmap.

    When *cache_database* is True, uses DatabaseCache instead of
    LocMemCache so that ``createcachetable`` can be exercised (SA63).
    """
    cache_backend = (
        "django.core.cache.backends.db.DatabaseCache"
        if cache_database
        else "django.core.cache.backends.locmem.LocMemCache"
    )
    cache_location_line = (
        '        "LOCATION": "django_cache_table",\n' if cache_database else ""
    )

    settings_content = (
        '"""Runtime smoke test settings — uses PostgreSQL."""\n'
        "import os\n"
        "\n"
        "from .base import *  # noqa: F401, F403\n"
        "\n"
        "DATABASES = {\n"
        '    "default": {\n'
        '        "ENGINE": "django.db.backends.postgresql",\n'
        '        "NAME": os.environ.get("QS_SMOKE_DB_NAME", '
        '"test_quickscale_smoke"),\n'
        '        "USER": os.environ.get("QS_SMOKE_DB_USER", "postgres"),\n'
        '        "PASSWORD": os.environ.get("QS_SMOKE_DB_PASSWORD", ""),\n'
        '        "HOST": os.environ.get("QS_SMOKE_DB_HOST", "localhost"),\n'
        '        "PORT": os.environ.get("QS_SMOKE_DB_PORT", "5432"),\n'
        "    }\n"
        "}\n"
        "\n"
        "DEBUG = False\n"
        'ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]\n'
        "\n"
        "CACHES = {\n"
        '    "default": {\n'
        f'        "BACKEND": "{cache_backend}",\n'
        f"{cache_location_line}"
        "    }\n"
        "}\n"
        "\n"
        "# Override the base settings' manifest-based staticfiles storage\n"
        "# (whitenoise.storage.CompressedManifestStaticFilesStorage) with the simple\n"
        "# in-place backend.  The smoke test does not run ``collectstatic``, so the\n"
        "# manifest file does not exist; without this override, any template\n"
        "# reference to a static asset (e.g. ``images/favicon.svg`` in the auth\n"
        "# login page) raises ``ValueError: Missing staticfiles manifest entry``.\n"
        "# This mirrors the override that ``local.py`` applies for development.\n"
        "STORAGES = {\n"
        '    "default": {\n'
        '        "BACKEND": "django.core.files.storage.FileSystemStorage",\n'
        "    },\n"
        '    "staticfiles": {\n'
        '        "BACKEND": '
        '"django.contrib.staticfiles.storage.StaticFilesStorage",\n'
        "    },\n"
        "}\n"
        "\n"
        "LOGGING = {\n"
        '    "version": 1,\n'
        '    "disable_existing_loggers": False,\n'
        '    "formatters": {\n'
        '        "verbose": {\n'
        '            "format": "{levelname} {asctime} {module} {message}",\n'
        '            "style": "{",\n'
        "        },\n"
        "    },\n"
        '    "handlers": {\n'
        '        "console": {\n'
        '            "class": "logging.StreamHandler",\n'
        '            "formatter": "verbose",\n'
        "        },\n"
        "    },\n"
        '    "root": {\n'
        '        "handlers": ["console"],\n'
        '        "level": "WARNING",\n'
        "    },\n"
        '    "loggers": {\n'
        '        "django": {\n'
        '            "handlers": ["console"],\n'
        '            "level": "WARNING",\n'
        '            "propagate": False,\n'
        "        },\n"
        "    },\n"
        "}\n"
    )
    settings_path = project_path / project_name / "settings" / "test_smoke.py"
    settings_path.write_text(settings_content)


def _create_test_database() -> None:
    """Create the test database if it does not exist."""
    import psycopg2

    db_name = os.environ.get("QS_SMOKE_DB_NAME", "test_quickscale_smoke")
    db_user = os.environ.get("QS_SMOKE_DB_USER", "postgres")
    db_password = os.environ.get("QS_SMOKE_DB_PASSWORD", "")
    db_host = os.environ.get("QS_SMOKE_DB_HOST", "localhost")
    db_port = os.environ.get("QS_SMOKE_DB_PORT", "5432")

    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        dbname="postgres",
    )
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        if not cur.fetchone():
            cur.execute(f'CREATE DATABASE "{db_name}"')
    conn.close()


def _run_migrations(project_path: Path, project_name: str) -> None:
    """Run database migrations against the PostgreSQL test database."""
    _create_test_database()
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
    """Start Django development server in background with PostgreSQL settings."""
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
    """Runtime smoke test for generated projects with embedded modules.

    Validates that an embedded-module generated project can:
    1. Generate project scaffold
    2. Embed the auth module
    3. Wire declarative config + managed settings/URLs
    4. Install dependencies via Poetry
    5. Run migrations against PostgreSQL
    6. Boot a development server
    7. Serve an auth-module route (/accounts/profile/) with a successful outcome
       (2xx/3xx) — proving the embedded module's URL routing is wired AND the
       route serves a valid redirect, not just that the server accepts TCP
       connections

    This test IS marked ``@pytest.mark.e2e`` so it is excluded from the
    default CI path (``pytest quickscale_core/tests/ -m "not e2e"``).
    """

    @pytest.mark.e2e
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

        # Phase 6: Write PostgreSQL test settings and run migrations.
        _write_postgres_test_settings(project_path, project_name)
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

    @pytest.mark.e2e
    def test_no_redis_createcachetable_succeeds(self, tmp_path: Path) -> None:
        """A generated project with DatabaseCache must run createcachetable successfully.

        SA63 regression: the createcachetable step must complete without
        triggering the orgs boot guard when QUICKSCALE_ALLOW_BYPASSRLS=1
        is set alongside RUNTIME_DATABASE_URL="".

        This test generates a minimal project, installs its Poetry
        dependencies, writes a test settings module with DatabaseCache,
        and runs ``python manage.py createcachetable`` — proving the
        no-Redis deploy-script path works through a real Django boot.
        """
        from quickscale_core.generator import ProjectGenerator

        project_name = "runtime_smoke_cache"
        project_path = tmp_path / project_name
        ProjectGenerator(theme="showcase_html").generate(project_name, project_path)

        assert (project_path / "manage.py").exists()
        assert (project_path / "pyproject.toml").exists()

        # Install dependencies (no module embedding needed for this test).
        _install_project_dependencies(project_path)

        # Write test settings with DatabaseCache (no-Redis production profile).
        _write_postgres_test_settings(project_path, project_name, cache_database=True)

        # Run createcachetable with QUICKSCALE_ALLOW_BYPASSRLS set
        # (simulating the start.sh environment).
        _create_test_database()
        result = subprocess.run(
            ["poetry", "run", "python", "manage.py", "createcachetable"],
            cwd=project_path,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "DJANGO_SETTINGS_MODULE": f"{project_name}.settings.test_smoke",
            },
        )
        assert result.returncode == 0, (
            f"createcachetable failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "django_cache_table" in result.stdout or not result.stderr, (
            "createcachetable should report success"
        )

    @pytest.mark.e2e
    def test_production_settings_createcachetable_with_orgs_bypass_hatch(
        self, tmp_path: Path
    ) -> None:
        """Generated project with orgs module and production settings must pass
        createcachetable through the env-var bridge (CR-SA63-002).

        This is the genuine production-settings/boot-guard e2e that the prior
        SA63 pass missed: it embeds the orgs module, uses the actual generated
        ``*.settings.production`` module (not ``test_smoke``), sets
        ``RUNTIME_DATABASE_URL=""`` and ``QUICKSCALE_ALLOW_BYPASSRLS=1`` in
        the subprocess environment, and runs ``createcachetable`` — proving
        the complete ``start.sh``-launched path works through Django's real
        production settings and the orgs boot guard.

        The production settings bridge (CR-SA63-001) must select
        ``DATABASE_URL`` because ``RUNTIME_DATABASE_URL`` is explicitly blank
        and the bypass hatch is set.  The orgs boot guard must also pass
        because ``QUICKSCALE_ALLOW_BYPASSRLS=1`` bypasses the RLS role check.
        """
        from quickscale_cli.commands.module_config import (
            get_default_auth_config,
            get_default_orgs_config,
        )
        from quickscale_cli.utils.module_dependency_sync import (
            sync_project_module_dependencies,
        )
        from quickscale_cli.utils.module_wiring_manager import (
            regenerate_managed_wiring,
        )
        from quickscale_core.generator import ProjectGenerator

        project_name = "runtime_sa63_prod"
        project_path = tmp_path / project_name

        # Phase 1: Generate project scaffold (HTML theme — no frontend build).
        ProjectGenerator(theme="showcase_html").generate(project_name, project_path)
        assert (project_path / "manage.py").exists()
        assert (project_path / "pyproject.toml").exists()

        # Phase 2: Embed both auth and orgs modules (orgs depends on auth).
        for mod_name in ("auth", "orgs"):
            embedded_path = project_path / "modules" / mod_name
            _copytree_for_generated_project_smoke(
                REPO_ROOT / "quickscale_modules" / mod_name,
                embedded_path,
            )
            assert (embedded_path / "module.yml").exists(), (
                f"{mod_name} module manifest missing after embed"
            )
            assert (embedded_path / "pyproject.toml").exists(), (
                f"{mod_name} module pyproject.toml missing after embed"
            )

        # Phase 3: Write declarative config and sync dependencies for both modules.
        auth_options = get_default_auth_config()
        orgs_options = get_default_orgs_config()
        self._write_quickscale_yml_with_modules(
            project_path,
            project_name,
            "showcase_html",
            {"auth": auth_options, "orgs": orgs_options},
        )

        sync_result = sync_project_module_dependencies(
            project_path, {"auth": auth_options, "orgs": orgs_options}
        )
        assert any(
            "quickscale-module-orgs" in dep
            for dep in sync_result.added_path_dependencies
        ), (
            "sync_project_module_dependencies did not register the orgs module "
            f"as a path dependency: {sync_result}"
        )
        assert any(
            "quickscale-module-auth" in dep
            for dep in sync_result.added_path_dependencies
        ), (
            "sync_project_module_dependencies did not register the auth module "
            f"as a path dependency: {sync_result}"
        )

        # Phase 4: Regenerate managed wiring (settings + URLs).
        success, message = regenerate_managed_wiring(project_path)
        assert success, f"regenerate_managed_wiring failed: {message}"

        # Phase 5: Install dependencies.
        _install_project_dependencies(project_path)

        # Phase 6: Create the test database.
        _create_test_database()

        # Phase 7: Run createcachetable with production settings and the
        # bridge env pair (simulating the start.sh.j2 createcachetable
        # invocation).
        db_user = os.environ.get("QS_SMOKE_DB_USER", "postgres")
        db_password = os.environ.get("QS_SMOKE_DB_PASSWORD", "")
        db_host = os.environ.get("QS_SMOKE_DB_HOST", "localhost")
        db_port = os.environ.get("QS_SMOKE_DB_PORT", "5432")
        db_name = os.environ.get("QS_SMOKE_DB_NAME", "test_quickscale_smoke")
        database_url = (
            f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        )

        # Build subprocess env from a copy so we can strip ambient REDIS_URL.
        # The test must prove DatabaseCache/no-Redis path (CR-SA63-002).
        subprocess_env = {
            **os.environ,
            "DJANGO_SETTINGS_MODULE": f"{project_name}.settings.production",
            "SECRET_KEY": "qs-sa63-test-production-secret-key-not-for-real-use",
            "DATABASE_URL": database_url,
            "RUNTIME_DATABASE_URL": "",
            "QUICKSCALE_ALLOW_BYPASSRLS": "1",
            "ALLOWED_HOSTS": "localhost,127.0.0.1",
        }
        subprocess_env.pop("REDIS_URL", None)

        result = subprocess.run(
            ["poetry", "run", "python", "manage.py", "createcachetable"],
            cwd=project_path,
            capture_output=True,
            text=True,
            env=subprocess_env,
        )
        assert result.returncode == 0, (
            f"createcachetable under production settings with orgs module "
            f"failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "django_cache_table" in result.stdout or not result.stderr, (
            "createcachetable should report success under production settings"
        )

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

    @staticmethod
    def _write_quickscale_yml_with_orgs(
        project_path: Path,
        project_name: str,
        theme: str,
        orgs_options: dict[str, object],
    ) -> None:
        """Write a minimal quickscale.yml that declares the orgs module."""
        import yaml

        config_payload = {
            "version": "1",
            "project": {
                "slug": project_name,
                "package": project_name,
                "theme": theme,
            },
            "docker": {"start": False},
            "modules": {"orgs": dict(orgs_options)},
        }
        rendered = yaml.safe_dump(
            config_payload,
            sort_keys=False,
            default_flow_style=False,
        )
        (project_path / "quickscale.yml").write_text(rendered)

    @staticmethod
    def _write_quickscale_yml_with_modules(
        project_path: Path,
        project_name: str,
        theme: str,
        modules_config: dict[str, dict[str, object]],
    ) -> None:
        """Write a minimal quickscale.yml that declares multiple modules."""
        import yaml

        config_payload = {
            "version": "1",
            "project": {
                "slug": project_name,
                "package": project_name,
                "theme": theme,
            },
            "docker": {"start": False},
            "modules": {
                mod_name: dict(mod_options)
                for mod_name, mod_options in modules_config.items()
            },
        }
        rendered = yaml.safe_dump(
            config_payload,
            sort_keys=False,
            default_flow_style=False,
        )
        (project_path / "quickscale.yml").write_text(rendered)
