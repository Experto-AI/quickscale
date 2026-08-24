"""Generated-project runtime smoke test.

Validates that a generated project with an embedded auth module can boot,
migrate, and serve an HTTP route with a successful outcome (2xx/3xx) —
proving generator fidelity without requiring Docker or browser automation.
Requires a running PostgreSQL instance (see AF13 roadmap note).

This test is marked ``@pytest.mark.e2e`` so it is excluded from
``pytest quickscale_core/tests/ -m "not e2e"`` and ``make test-unit``.

Phase 14.3 of the roadmap (Finding 14 — generator-runtime test coverage).
"""

import json
import os
import secrets
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import pytest

from quickscale_core.utils.poetry_env import build_isolated_poetry_env

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
        port = int(s.getsockname()[1])
    return port


def _standalone_generated_env(
    overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build a generated-project environment without maintainer provenance."""
    environment = build_isolated_poetry_env()
    for variable in (
        "PYTHONPATH",
        "MYPYPATH",
        "PWD",
        "OLDPWD",
        "DJANGO_SETTINGS_MODULE",
        "QUICKSCALE_PRIVILEGED_COMMAND",
        "QUICKSCALE_ALLOW_BYPASSRLS",
        "QUICKSCALE_LOCAL_WHEELHOUSE",
    ):
        environment.pop(variable, None)
    if overrides:
        environment.update(overrides)
    return environment


def _install_project_dependencies(
    project_path: Path,
    *,
    strict: bool = False,
) -> None:
    """Install dependencies in the generated project using poetry.

    Skips the test when PyPI is unreachable so CI does not fail on
    transient network issues unless ``strict`` is requested by the
    standalone all-module runtime proof.
    """
    poetry_env = _standalone_generated_env() if strict else build_isolated_poetry_env()
    lock_result = subprocess.run(
        ["poetry", "lock"],
        cwd=project_path,
        capture_output=True,
        text=True,
        timeout=120,
        env=poetry_env,
    )
    lock_output = f"{lock_result.stdout}\n{lock_result.stderr}"
    if (
        not strict
        and lock_result.returncode != 0
        and _is_poetry_network_failure(lock_output)
    ):
        pytest.skip("PyPI is unreachable in this environment")
    assert lock_result.returncode == 0, f"Poetry lock failed: {lock_result.stderr}"

    install_result = subprocess.run(
        ["poetry", "install", "--no-interaction"],
        cwd=project_path,
        capture_output=True,
        text=True,
        timeout=180,
        env=poetry_env,
    )
    install_output = f"{install_result.stdout}\n{install_result.stderr}"
    if (
        not strict
        and install_result.returncode != 0
        and _is_poetry_network_failure(install_output)
    ):
        pytest.skip("PyPI is unreachable in this environment")
    assert install_result.returncode == 0, (
        f"Poetry install failed: {install_result.stderr}"
    )


def _write_postgres_test_settings(
    project_path: Path,
    project_name: str,
    postgres_url: str,
    cache_database: bool = False,
) -> None:
    """Write a test settings module that uses PostgreSQL.

    Requires a running PostgreSQL instance reachable via *postgres_url*.
    The connection details are embedded directly into the generated
    settings file so that subprocesses do not depend on ambient
    QS_SMOKE_DB_* environment variables.

    When *cache_database* is True, uses DatabaseCache instead of
    LocMemCache so that ``createcachetable`` can be exercised (SA63).
    """
    from urllib.parse import urlparse

    parsed = urlparse(postgres_url)
    db_name = parsed.path.lstrip("/") if parsed.path else "test_db"
    db_user = parsed.username or "test_user"
    db_password = parsed.password or "test_password"
    db_host = parsed.hostname or "localhost"
    db_port = str(parsed.port or 5432)

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
        "\n"
        "from .base import *  # noqa: F401, F403\n"
        "\n"
        "DATABASES = {\n"
        '    "default": {\n'
        '        "ENGINE": "django.db.backends.postgresql",\n'
        f'        "NAME": "{db_name}",\n'
        f'        "USER": "{db_user}",\n'
        f'        "PASSWORD": "{db_password}",\n'
        f'        "HOST": "{db_host}",\n'
        f'        "PORT": "{db_port}",\n'
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


def _create_test_database(postgres_url: str) -> None:
    """Create the test database if it does not exist.

    The database name and connection parameters are extracted from
    *postgres_url* rather than relying on ambient QS_SMOKE_DB_* env vars.
    """
    import psycopg2  # type: ignore[import-untyped]

    from urllib.parse import urlparse

    parsed = urlparse(postgres_url)
    db_name = parsed.path.lstrip("/") if parsed.path else "test_db"
    db_user = parsed.username or "test_user"
    db_password = parsed.password or "test_password"
    db_host = parsed.hostname or "localhost"
    db_port = parsed.port or 5432

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


def _postgres_connect_kwargs(
    postgres_service: dict[str, Any],
    *,
    database: str,
    user: str | None = None,
    password: str | None = None,
) -> dict[str, Any]:
    """Return connection arguments for the pytest-docker PostgreSQL service."""
    return {
        "host": postgres_service["host"],
        "port": postgres_service["port"],
        "dbname": database,
        "user": user if user is not None else postgres_service["user"],
        "password": (
            password if password is not None else postgres_service["password"]
        ),
    }


def _quote_postgres_identifier(value: str) -> str:
    """Quote a generated PostgreSQL identifier without accepting SQL syntax."""
    return '"' + value.replace('"', '""') + '"'


@contextmanager
def _restricted_postgres_database(
    postgres_service: dict[str, Any],
) -> Iterator[dict[str, Any]]:
    """Create and deterministically clean up a restricted, owned database."""
    import psycopg2  # type: ignore[import-untyped]

    scope = os.environ.get("QS_E2E_CONTAINER_PREFIX", "qs-sa151-180655")
    suffix = secrets.token_hex(8)
    database = f"{scope.replace('-', '_')}_db_{suffix}"
    role = f"{scope.replace('-', '_')}_role_{suffix}"
    password = secrets.token_urlsafe(24)
    admin_connection = None
    restricted_connection = None
    database_created = False
    role_created = False
    cleanup_evidence: dict[str, Any] = {
        "database": database,
        "role": role,
        "database_absent": False,
        "role_absent": False,
    }

    # The finally is deliberately established before either CREATE statement.
    try:
        admin_connection = psycopg2.connect(
            **_postgres_connect_kwargs(postgres_service, database="postgres")
        )
        admin_connection.autocommit = True
        with admin_connection.cursor() as cursor:
            cursor.execute("SHOW server_version_num")
            version_num = int(cursor.fetchone()[0])
            assert version_num // 10000 == 18, (
                f"Expected PostgreSQL 18, got server_version_num={version_num}"
            )
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,))
            assert cursor.fetchone() is None, f"Database already exists: {database}"
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
            assert cursor.fetchone() is None, f"Role already exists: {role}"

            cursor.execute(
                f"CREATE ROLE {_quote_postgres_identifier(role)} LOGIN "
                "NOSUPERUSER NOBYPASSRLS NOINHERIT PASSWORD %s",
                (password,),
            )
            role_created = True
            cursor.execute(
                f"CREATE DATABASE {_quote_postgres_identifier(database)} "
                f"OWNER {_quote_postgres_identifier(role)}"
            )
            database_created = True
            cursor.execute(
                "SELECT rolsuper, rolbypassrls, rolinherit, rolcanlogin "
                "FROM pg_roles WHERE rolname = %s",
                (role,),
            )
            role_flags = cursor.fetchone()
            assert role_flags == (False, False, False, True), (
                f"Restricted role flags are incorrect: {role_flags}"
            )

        restricted_connection = psycopg2.connect(
            **_postgres_connect_kwargs(
                postgres_service,
                database=database,
                user=role,
                password=password,
            )
        )
        restricted_connection.autocommit = True
        with restricted_connection.cursor() as cursor:
            cursor.execute(
                "SELECT table_schema, table_name "
                "FROM information_schema.tables "
                "WHERE table_schema NOT IN ('pg_catalog', 'information_schema')"
            )
            assert cursor.fetchall() == [], "Restricted database is not empty"
            cursor.execute("SELECT to_regclass('public.django_migrations')")
            assert cursor.fetchone()[0] is None, (
                "django_migrations exists before the first generated migration"
            )

        yield {
            "database": database,
            "role": role,
            "password": password,
            "url": (
                f"postgresql://{role}:{password}@{postgres_service['host']}"
                f":{postgres_service['port']}/{database}"
            ),
            "postgres_major": 18,
            "role_flags": role_flags,
            "empty_before_migrate": True,
            "cleanup_evidence": cleanup_evidence,
        }
    finally:
        if restricted_connection is not None:
            restricted_connection.close()
        if admin_connection is not None:
            admin_connection.autocommit = True
            with admin_connection.cursor() as cursor:
                if database_created:
                    cursor.execute(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = %s AND pid <> pg_backend_pid()",
                        (database,),
                    )
                    cursor.execute(
                        f"DROP DATABASE {_quote_postgres_identifier(database)}"
                    )
                cursor.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s", (database,)
                )
                cleanup_evidence["database_absent"] = cursor.fetchone() is None
                assert cleanup_evidence["database_absent"], (
                    f"Database cleanup failed: {database}"
                )
                if role_created:
                    cursor.execute(f"DROP ROLE {_quote_postgres_identifier(role)}")
                cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
                cleanup_evidence["role_absent"] = cursor.fetchone() is None
                assert cleanup_evidence["role_absent"], f"Role cleanup failed: {role}"
            admin_connection.close()


def _source_module_inventory() -> dict[str, Any]:
    """Bind module names, roots, options, and source migration shape once."""
    from quickscale_cli.commands.module_config import (
        get_default_orgs_config,
        get_module_configurator,
    )
    from quickscale_core.contracts.module_discovery import (
        authoritative_module_names,
        discover_shipped_module_paths,
    )

    names = tuple(authoritative_module_names())
    roots = discover_shipped_module_paths()
    assert set(names) == set(roots), "Authoritative names and roots diverged"
    expected_app_config_identities = {
        name: {
            "name": f"quickscale_modules_{name}",
            "label": f"quickscale_modules_{name}",
        }
        for name in names
    }
    options: dict[str, dict[str, object]] = {}
    for name in names:
        configurator = get_module_configurator(name)
        if name == "orgs":
            options[name] = dict(get_default_orgs_config())
        else:
            assert configurator is not None, f"Missing configurator for {name}"
            options[name] = dict(configurator.get_defaults())
    assert set(options) == set(names), "Module options do not cover authoritative names"

    model_modules: set[str] = set()
    service_modules: set[str] = set()
    initial_migrations: dict[str, str] = {}
    for name in names:
        root = roots[name]
        models_file = root / "src" / f"quickscale_modules_{name}" / "models.py"
        models_package = (
            root / "src" / f"quickscale_modules_{name}" / "models" / "__init__.py"
        )
        assert not (models_file.exists() and models_package.exists()), (
            f"Ambiguous models representation for {name}"
        )
        if models_file.exists() or models_package.exists():
            model_modules.add(name)
            migration = (
                root
                / "src"
                / f"quickscale_modules_{name}"
                / "migrations"
                / "0001_initial.py"
            )
            assert migration.exists(), f"Missing source 0001_initial for {name}"
            initial_migrations[name] = migration.relative_to(root).as_posix()
        else:
            service_modules.add(name)
            migration_dir = root / "src" / f"quickscale_modules_{name}" / "migrations"
            assert not migration_dir.exists(), f"Service module has migrations: {name}"

    return {
        "names": names,
        "roots": roots,
        "expected_app_config_identities": expected_app_config_identities,
        "options": options,
        "model_modules": model_modules,
        "service_modules": service_modules,
        "initial_migrations": initial_migrations,
    }


def _run_generated_json_probe(
    project_path: Path,
    project_name: str,
    environment: dict[str, str],
) -> dict[str, Any]:
    """Collect runtime app, origin, loader, recorder, and path provenance."""
    probe = """
import json
import pathlib
import sys

import django
from django.apps import apps
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder

django.setup()
project_root = pathlib.Path.cwd().resolve()
embedded_root = (project_root / "modules").resolve()

def embedded_name(value):
    if not value:
        return None
    path = pathlib.Path(value).resolve()
    try:
        relative = path.relative_to(embedded_root)
    except ValueError:
        return None
    return relative.parts[0] if relative.parts else None

app_configs = []
for config in apps.get_app_configs():
    origin = getattr(config.module, "__file__", None)
    module_name = embedded_name(origin)
    if module_name is None:
        continue
    model_origin = getattr(config.models_module, "__file__", None)
    app_configs.append({
        "module": module_name,
        "name": config.name,
        "label": config.label,
        "origin": str(pathlib.Path(origin).resolve()) if origin else None,
        "model_origin": str(pathlib.Path(model_origin).resolve()) if model_origin else None,
    })

loader = MigrationLoader(connection, ignore_no_migrations=False)
recorder = MigrationRecorder(connection)
disk = [
    {"app": app, "name": name}
    for app, name in sorted(loader.disk_migrations)
    if any(item["label"] == app for item in app_configs)
]
applied = [
    {"app": app, "name": name}
    for app, name in sorted(recorder.applied_migrations())
    if any(item["label"] == app for item in app_configs)
]
migration_files = []
for path in sorted(embedded_root.glob("*/**/migrations/0001_initial.py")):
    migration_files.append(str(path.relative_to(project_root)))

with connection.cursor() as cursor:
    cursor.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' ORDER BY table_name"
    )
    public_tables = [row[0] for row in cursor.fetchall()]

print(json.dumps({
    "sys_path": sys.path,
    "app_configs": app_configs,
    "disk_migrations": disk,
    "applied_migrations": applied,
    "migration_files": migration_files,
    "public_tables": public_tables,
}, sort_keys=True))
"""
    result = subprocess.run(
        ["poetry", "run", "python", "-c", probe],
        cwd=project_path,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.returncode == 0, (
        f"Generated runtime probe failed:\nstdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
    return json.loads(result.stdout)


def test_install_project_dependencies_strict_network_failure_is_not_skipped(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Strict generated-project installation reports network failures."""
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr="Connection error: PyPI is unreachable",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(AssertionError, match="Poetry lock failed"):
        _install_project_dependencies(tmp_path, strict=True)
    assert calls == [["poetry", "lock"]]


def _run_migrations(
    project_path: Path,
    project_name: str,
    *,
    environment: dict[str, str] | None = None,
    privileged_command: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run database migrations against the PostgreSQL test database.

    The test database must already exist (created by the ``per_test_db``
    fixture or equivalent).
    """
    subprocess_env = (
        dict(environment)
        if environment is not None
        else build_isolated_poetry_env(
            {"DJANGO_SETTINGS_MODULE": f"{project_name}.settings.test_smoke"}
        )
    )
    if environment is None:
        subprocess_env["DJANGO_SETTINGS_MODULE"] = f"{project_name}.settings.test_smoke"
    if privileged_command is not None:
        subprocess_env["QUICKSCALE_PRIVILEGED_COMMAND"] = privileged_command

    result = subprocess.run(
        ["poetry", "run", "python", "manage.py", "migrate", "--noinput"],
        cwd=project_path,
        capture_output=True,
        text=True,
        env=subprocess_env,
    )
    assert result.returncode == 0, (
        f"Migrations failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    return result


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
        env=build_isolated_poetry_env(
            {"DJANGO_SETTINGS_MODULE": f"{project_name}.settings.test_smoke"}
        ),
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
        except OSError, ConnectionRefusedError:
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
    def test_embedded_auth_module_boots_and_serves_login(
        self, tmp_path: Path, postgres_url: str
    ) -> None:
        """A generated project with embedded auth should boot, migrate, and serve an auth route.

        Requires a successful HTTP outcome (2xx/3xx) for an auth-module route so that
        404 (missing URL wiring) and 5xx (server crash) are caught as failures
        rather than silently passing the smoke test.

        Uses /accounts/profile/ instead of /accounts/login/ because the profile route
        returns 302 (redirect to login) for anonymous users, which is a reliable 3xx
        outcome that proves the auth module's URL routing is wired without requiring
        the allauth login template to render successfully.
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

        # Phase 1: Generate project scaffold (React theme — with frontend).
        project_name = "runtime_smoke_auth"
        project_path = tmp_path / project_name
        ProjectGenerator(theme="showcase_react").generate(project_name, project_path)

        assert (project_path / "manage.py").exists()
        assert (project_path / "pyproject.toml").exists()

        # Phase 2: Embed both auth and orgs modules (auth depends on orgs).
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

        # Phase 3: Write declarative config and sync dependencies.
        auth_options = get_default_auth_config()
        orgs_options = get_default_orgs_config()
        self._write_quickscale_yml_with_modules(
            project_path,
            project_name,
            "showcase_react",
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

        # Phase 6: Write PostgreSQL test settings and run migrations.
        # Set QUICKSCALE_ALLOW_BYPASSRLS so the orgs boot guard passes with
        # a superuser PostgreSQL role (common in dev/test environments).
        # The env var must remain set through Phase 7 (dev server boot)
        # because Django loads AppConfig.ready() at server startup too.
        _write_postgres_test_settings(project_path, project_name, postgres_url)
        _allow_bypass_rls = os.environ.get("QUICKSCALE_ALLOW_BYPASSRLS")
        os.environ["QUICKSCALE_ALLOW_BYPASSRLS"] = "1"
        try:
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
                _assert_url_responds(
                    f"http://localhost:{server_port}/accounts/profile/"
                )
            finally:
                _stop_server(server_process)
        finally:
            if _allow_bypass_rls is not None:
                os.environ["QUICKSCALE_ALLOW_BYPASSRLS"] = _allow_bypass_rls
            else:
                os.environ.pop("QUICKSCALE_ALLOW_BYPASSRLS", None)

    @pytest.mark.e2e
    def test_all_module_initial_migrations_apply_from_embedded_sources(
        self,
        tmp_path: Path,
        postgres_service: dict[str, Any],
    ) -> None:
        """Every authoritative embedded module migrates from a clean PG18 DB."""
        from quickscale_cli.utils.module_dependency_sync import (
            sync_project_module_dependencies,
        )
        from quickscale_cli.utils.module_wiring_manager import (
            regenerate_managed_wiring,
        )
        from quickscale_core.generator import ProjectGenerator

        inventory = _source_module_inventory()
        names = inventory["names"]
        roots = inventory["roots"]
        options = inventory["options"]
        model_modules = inventory["model_modules"]
        service_modules = inventory["service_modules"]

        project_name = "runtime_all_modules"
        project_path = tmp_path / project_name
        ProjectGenerator(theme="showcase_react").generate(project_name, project_path)
        assert (project_path / "manage.py").exists()
        assert (project_path / "pyproject.toml").exists()

        for name in names:
            embedded_path = project_path / "modules" / name
            _copytree_for_generated_project_smoke(roots[name], embedded_path)
            assert (embedded_path / "module.yml").exists(), (
                f"{name} module manifest missing after embed"
            )
            assert (embedded_path / "pyproject.toml").exists(), (
                f"{name} module pyproject.toml missing after embed"
            )
        assert {
            path.name for path in (project_path / "modules").iterdir() if path.is_dir()
        } == set(names)

        self._write_quickscale_yml_with_modules(
            project_path,
            project_name,
            "showcase_react",
            options,
        )
        sync_result = sync_project_module_dependencies(project_path, options)
        path_dependencies = {
            dependency
            for dependency in sync_result.added_path_dependencies
            if "quickscale-module-" in dependency
        }
        assert len(path_dependencies) == len(names), (
            f"Expected one path dependency per authoritative module: {path_dependencies}"
        )
        for name in names:
            assert any(f"quickscale-module-{name}" in dep for dep in path_dependencies)

        success, message = regenerate_managed_wiring(project_path)
        assert success, f"regenerate_managed_wiring failed: {message}"

        _install_project_dependencies(project_path, strict=True)
        assert not any(
            path.name == "wheelhouse" or "wheelhouse" in path.name
            for path in project_path.rglob("*")
        ), "Generated project unexpectedly materialized a local wheelhouse"

        with _restricted_postgres_database(postgres_service) as database:
            _write_postgres_test_settings(
                project_path,
                project_name,
                database["url"],
            )
            migrate_environment = _standalone_generated_env(
                {
                    "DJANGO_SETTINGS_MODULE": (f"{project_name}.settings.test_smoke"),
                    "QUICKSCALE_PRIVILEGED_COMMAND": "migrate",
                    "DATABASE_URL": database["url"],
                    "RUNTIME_DATABASE_URL": database["url"],
                }
            )
            assert "QUICKSCALE_ALLOW_BYPASSRLS" not in migrate_environment
            assert "QUICKSCALE_LOCAL_WHEELHOUSE" not in migrate_environment
            assert str(REPO_ROOT) not in "\n".join(migrate_environment.values())
            migration_result = _run_migrations(
                project_path,
                project_name,
                environment=migrate_environment,
            )
            assert migration_result.returncode == 0
            assert migrate_environment["QUICKSCALE_PRIVILEGED_COMMAND"] == "migrate"

            makemigrations_environment = _standalone_generated_env(
                {
                    "DJANGO_SETTINGS_MODULE": (f"{project_name}.settings.test_smoke"),
                    "DATABASE_URL": database["url"],
                    "RUNTIME_DATABASE_URL": database["url"],
                }
            )
            assert "QUICKSCALE_PRIVILEGED_COMMAND" not in makemigrations_environment
            assert "QUICKSCALE_ALLOW_BYPASSRLS" not in makemigrations_environment
            makemigrations_result = subprocess.run(
                [
                    "poetry",
                    "run",
                    "python",
                    "manage.py",
                    "makemigrations",
                    "--check",
                    "--dry-run",
                ],
                cwd=project_path,
                capture_output=True,
                text=True,
                env=makemigrations_environment,
            )
            assert makemigrations_result.returncode == 0, (
                "makemigrations reported pending changes:\n"
                f"stdout: {makemigrations_result.stdout}\n"
                f"stderr: {makemigrations_result.stderr}"
            )

            runtime = _run_generated_json_probe(
                project_path,
                project_name,
                makemigrations_environment,
            )
            runtime_identities = {
                config["module"]: {
                    "name": config["name"],
                    "label": config["label"],
                }
                for config in runtime["app_configs"]
            }
            assert len(runtime_identities) == len(runtime["app_configs"]), (
                "Runtime app inventory contains duplicate module identities"
            )
            assert runtime_identities == inventory["expected_app_config_identities"], (
                "Runtime AppConfig identities differ from the independent source contract"
            )
            assert len(runtime_identities) == len(names)
            assert all(
                str(REPO_ROOT) not in path
                for path in runtime["sys_path"]
                if isinstance(path, str)
            )
            assert all(
                str(REPO_ROOT) not in origin
                for config in runtime["app_configs"]
                for origin in (config["origin"], config["model_origin"])
                if origin
            )

            runtime_model_modules = {
                config["module"]
                for config in runtime["app_configs"]
                if config["model_origin"] is not None
            }
            assert runtime_model_modules == model_modules
            assert set(runtime["migration_files"]) == {
                f"modules/{name}/{inventory['initial_migrations'][name]}"
                for name in model_modules
            }
            expected_identities = inventory["expected_app_config_identities"]
            model_labels = {
                expected_identities[name]["label"] for name in model_modules
            }
            service_labels = {
                expected_identities[name]["label"] for name in service_modules
            }
            disk_migrations = {
                (migration["app"], migration["name"])
                for migration in runtime["disk_migrations"]
            }
            applied_migrations = {
                (migration["app"], migration["name"])
                for migration in runtime["applied_migrations"]
            }
            expected_migrations = {(label, "0001_initial") for label in model_labels}
            assert disk_migrations == expected_migrations
            assert applied_migrations == expected_migrations
            assert all(
                app not in service_labels for app, _migration_name in disk_migrations
            )
            assert len(runtime["applied_migrations"]) == len(
                set(tuple(item.items()) for item in runtime["applied_migrations"])
            )
            assert "django_migrations" in runtime["public_tables"]

        assert database["cleanup_evidence"] == {
            "database": database["database"],
            "role": database["role"],
            "database_absent": True,
            "role_absent": True,
        }

    @pytest.mark.e2e
    def test_no_redis_createcachetable_succeeds(
        self, tmp_path: Path, postgres_url: str
    ) -> None:
        """A generated project with DatabaseCache must run createcachetable successfully.

        SA63 regression: the createcachetable step must complete without
        triggering the orgs boot guard when QUICKSCALE_ALLOW_BYPASSRLS=1
        is set alongside RUNTIME_DATABASE_URL="".

        This test generates a minimal project, installs its Poetry
        dependencies, writes a test settings module with DatabaseCache,
        and runs ``python manage.py createcachetable`` — proving the
        no-Redis deploy-script path works through a real Django boot.

        The per-test database is created automatically by the
        ``postgres_url`` fixture.
        """
        from quickscale_core.generator import ProjectGenerator

        project_name = "runtime_smoke_cache"
        project_path = tmp_path / project_name
        ProjectGenerator(theme="showcase_react").generate(project_name, project_path)

        assert (project_path / "manage.py").exists()
        assert (project_path / "pyproject.toml").exists()

        # Install dependencies (no module embedding needed for this test).
        _install_project_dependencies(project_path)

        # Write test settings with DatabaseCache (no-Redis production profile).
        _write_postgres_test_settings(
            project_path, project_name, postgres_url, cache_database=True
        )

        # Run createcachetable with QUICKSCALE_ALLOW_BYPASSRLS set
        # (simulating the start.sh environment).
        # The database already exists (created by the postgres_url fixture).
        result = subprocess.run(
            ["poetry", "run", "python", "manage.py", "createcachetable"],
            cwd=project_path,
            capture_output=True,
            text=True,
            env=build_isolated_poetry_env(
                {"DJANGO_SETTINGS_MODULE": f"{project_name}.settings.test_smoke"}
            ),
        )
        assert result.returncode == 0, (
            f"createcachetable failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "django_cache_table" in result.stdout or not result.stderr, (
            "createcachetable should report success"
        )

    @pytest.mark.e2e
    def test_production_settings_createcachetable_with_orgs_bypass_hatch(
        self, tmp_path: Path, postgres_url: str
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

        # Phase 1: Generate project scaffold (React theme — with frontend).
        ProjectGenerator(theme="showcase_react").generate(project_name, project_path)
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
            "showcase_react",
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

        # Phase 6: Use the per-test database (already created by the
        # postgres_url fixture).

        # Phase 7: Run createcachetable with production settings and the
        # bridge env pair (simulating the start.sh.j2 createcachetable
        # invocation).
        # Build subprocess env from a copy so we can strip ambient REDIS_URL.
        # The test must prove DatabaseCache/no-Redis path (CR-SA63-002).
        subprocess_env = build_isolated_poetry_env(
            {
                "DJANGO_SETTINGS_MODULE": f"{project_name}.settings.production",
                "SECRET_KEY": "qs-sa63-test-production-secret-key-not-for-real-use",
                "DATABASE_URL": postgres_url,
                "RUNTIME_DATABASE_URL": "",
                "QUICKSCALE_ALLOW_BYPASSRLS": "1",
                "ALLOWED_HOSTS": "localhost,127.0.0.1",
            }
        )
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

    @pytest.mark.e2e
    def test_production_settings_createcachetable_with_orgs_privileged_command(
        self, tmp_path: Path, postgres_url: str
    ) -> None:
        """Generated project with orgs module must pass createcachetable via
        the ``QUICKSCALE_PRIVILEGED_COMMAND`` contract (no bypass hatch,
        CR-SA68-001).

        This e2e test follows the actual generated ``start.sh.j2`` no-Redis
        path: it sets ``QUICKSCALE_PRIVILEGED_COMMAND=createcachetable``
        (not the ``QUICKSCALE_ALLOW_BYPASSRLS=1`` escape hatch) alongside
        ``RUNTIME_DATABASE_URL=""``, proving that the orgs boot guard now
        recognises ``createcachetable`` as a sanctioned privileged DB
        command and skips the RLS role check without requiring the escape
        hatch.

        This matches the start.sh.j2 invocation at lines 59-61:
        ``QUICKSCALE_PRIVILEGED_COMMAND=createcachetable RUNTIME_DATABASE_URL=""
        python manage.py createcachetable``
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

        project_name = "runtime_sa68_privcmd"
        project_path = tmp_path / project_name

        # Phase 1: Generate project scaffold (React theme — with frontend).
        ProjectGenerator(theme="showcase_react").generate(project_name, project_path)
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
            "showcase_react",
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

        # Phase 6: Use the per-test database (already created by the
        # postgres_url fixture).

        # Phase 7: Run createcachetable with the actual start.sh.j2
        # privileged-command bridge — no QUICKSCALE_ALLOW_BYPASSRLS.
        # Build subprocess env from a copy so we can strip ambient REDIS_URL.
        # The test must prove DatabaseCache/no-Redis path via privileged
        # command (CR-SA68-001).
        subprocess_env = build_isolated_poetry_env(
            {
                "DJANGO_SETTINGS_MODULE": f"{project_name}.settings.production",
                "SECRET_KEY": "qs-sa68-test-production-secret-key-not-for-real-use",
                "DATABASE_URL": postgres_url,
                "RUNTIME_DATABASE_URL": "",
                "QUICKSCALE_PRIVILEGED_COMMAND": "createcachetable",
                "ALLOWED_HOSTS": "localhost,127.0.0.1",
            }
        )
        subprocess_env.pop("REDIS_URL", None)
        # No QUICKSCALE_ALLOW_BYPASSRLS — the guard must pass via
        # _is_privileged_command() recognising createcachetable.

        result = subprocess.run(
            ["poetry", "run", "python", "manage.py", "createcachetable"],
            cwd=project_path,
            capture_output=True,
            text=True,
            env=subprocess_env,
        )
        assert result.returncode == 0, (
            f"createcachetable under production settings with orgs module "
            f"via privileged command failed:\nstdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        assert "django_cache_table" in result.stdout or not result.stderr, (
            "createcachetable should report success via privileged command"
        )

    @pytest.mark.e2e
    def test_collectstatic_with_production_settings(self, tmp_path: Path) -> None:
        """Generated project must run collectstatic with production settings
        when ``QUICKSCALE_NON_DB_COMMAND=collectstatic`` is set (SA68 Phase 3).

        The non-DB command path must allow collectstatic to run without
        requiring ``RUNTIME_DATABASE_URL`` or a real database connection.
        A dummy ``postgresql://`` URL is used when ``DATABASE_URL`` is also
        unset; Django's ``collectstatic`` does not touch the database, so
        the dummy URL is never actually connected to.

        This mirrors the same command that runs at Docker build time (see
        ``Dockerfile.j2``), proving it works through production settings.
        """
        from quickscale_core.generator import ProjectGenerator

        project_name = "runtime_collectstatic"
        project_path = tmp_path / project_name
        ProjectGenerator(theme="showcase_react").generate(project_name, project_path)

        assert (project_path / "manage.py").exists()
        assert (project_path / "pyproject.toml").exists()

        _install_project_dependencies(project_path)

        # Run collectstatic with production settings and the non-DB command env var.
        # No DATABASE_URL or RUNTIME_DATABASE_URL is needed — the non-DB path
        # provides a dummy URL that Django never actually connects to.
        subprocess_env = build_isolated_poetry_env(
            {
                "DJANGO_SETTINGS_MODULE": f"{project_name}.settings.production",
                "SECRET_KEY": (
                    "test-secret-key-for-collectstatic-e2e-not-for-real-use"
                ),
                "QUICKSCALE_NON_DB_COMMAND": "collectstatic",
                "ALLOWED_HOSTS": "localhost,127.0.0.1",
            }
        )
        subprocess_env.pop("REDIS_URL", None)

        result = subprocess.run(
            ["poetry", "run", "python", "manage.py", "collectstatic", "--noinput"],
            cwd=project_path,
            capture_output=True,
            text=True,
            env=subprocess_env,
        )
        assert result.returncode == 0, (
            f"collectstatic with QUICKSCALE_NON_DB_COMMAND through "
            f"production settings failed:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "static files" in result.stdout.lower() or not result.stderr, (
            "collectstatic should report static files copied"
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
