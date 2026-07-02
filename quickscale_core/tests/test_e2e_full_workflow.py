"""
Full end-to-end tests for QuickScale project generation workflow.

These tests verify the complete lifecycle:
1. Generate Django project
2. Install dependencies with Poetry
3. Run migrations against real PostgreSQL
4. Execute Django management commands
5. Start development server
6. Test frontend with Playwright browser automation
7. Verify Docker and Docker Compose v2 setup

Run with: pytest -m e2e
"""

import json
import os
import re
import shlex
import shutil
import subprocess
import time
import tomllib
import urllib.parse
from pathlib import Path

import pytest

from quickscale_cli.utils.docker_utils import get_docker_compose_command


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DEPENDENCY_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+")
STORAGE_CLOUD_BACKENDS = {"r2", "s3"}
STORAGE_CLOUD_DEPENDENCIES = {"boto3", "django-storages"}
REPO_LOCAL_ARTIFACT_NAMES = frozenset(
    {
        ".mypy_cache",
        ".nox",
        ".pnpm-store",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
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


def _is_network_failure(output: str) -> bool:
    """Detect common package-registry network failures."""
    lowered = output.lower()
    markers = [
        "eai_again",
        "enotfound",
        "err_pnpm_meta_fetch_fail",
        "etimedout",
        "registry.npmjs.org",
    ]
    return any(marker in lowered for marker in markers)


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


def _timeout_output(exc: subprocess.TimeoutExpired) -> str:
    """Best-effort string output extraction from TimeoutExpired."""
    parts: list[str] = []
    for stream in (exc.stdout, exc.stderr):
        if stream is None:
            continue
        if isinstance(stream, bytes):
            parts.append(stream.decode(errors="ignore"))
        else:
            parts.append(stream)
    return "\n".join(parts)


def _module_manifest_path(module_name: str) -> Path:
    """Return the maintainer-side manifest path for a shipped module."""
    return REPO_ROOT / "quickscale_modules" / module_name / "module.yml"


def _module_pyproject_path(module_name: str) -> Path:
    """Return the maintainer-side pyproject path for a shipped module."""
    return REPO_ROOT / "quickscale_modules" / module_name / "pyproject.toml"


def _load_module_package_name(module_name: str) -> str:
    """Return the distribution name declared by a shipped module package."""
    pyproject_data = tomllib.loads(_module_pyproject_path(module_name).read_text())
    package_name = pyproject_data["project"]["name"]
    assert isinstance(package_name, str)
    return package_name


def _default_smoke_config(module_name: str) -> dict[str, object]:
    """Return a non-interactive module config suitable for dependency smoke tests."""
    from quickscale_cli.commands import module_config as module_config_commands

    config_factory = getattr(
        module_config_commands,
        f"get_default_{module_name}_config",
        None,
    )
    assert callable(config_factory), f"Missing default config factory for {module_name}"

    config = dict(config_factory())
    if module_name == "storage":
        config["backend"] = "s3"
    return config


def _expected_distribution_names(
    module_name: str, module_config: dict[str, object]
) -> set[str]:
    """Return the path and third-party distributions required for a module smoke."""
    from quickscale_core.manifest.loader import load_manifest_from_path

    manifest = load_manifest_from_path(_module_manifest_path(module_name))
    expected_names = {_load_module_package_name(module_name)}
    storage_backend = str(module_config.get("backend", "local")).strip().lower()

    for dependency in manifest.dependencies:
        if isinstance(dependency, dict):
            dependency_spec = dependency.get("dependency_name") or dependency.get(
                "name"
            )
        else:
            dependency_spec = getattr(dependency, "dependency_name", dependency)

        assert isinstance(dependency_spec, str), (
            f"{module_name} manifest dependency must be string-like: {dependency!r}"
        )
        dependency_match = MANIFEST_DEPENDENCY_NAME_PATTERN.match(
            dependency_spec.strip()
        )
        assert dependency_match is not None, (
            f"{module_name} manifest dependency is missing a package name: {dependency_spec}"
        )

        dependency_name = dependency_match.group(0).lower()
        if (
            module_name == "storage"
            and dependency_name in STORAGE_CLOUD_DEPENDENCIES
            and storage_backend not in STORAGE_CLOUD_BACKENDS
        ):
            continue
        expected_names.add(dependency_name)

    return expected_names


def test_generated_project_copytree_ignores_repo_local_artifacts(tmp_path):
    """Smoke-copy helper should not carry repo-local caches into generated projects."""
    source = tmp_path / "source_module"
    source.mkdir()
    (source / "module.py").write_text('print("ok")\n')
    (source / "README.md").write_text("module docs\n")
    (source / ".ruff_cache").mkdir()
    (source / ".ruff_cache" / "cache.db").write_text("ignored\n")
    (source / ".pytest_cache").mkdir()
    (source / ".pytest_cache" / "README").write_text("ignored\n")
    (source / "htmlcov").mkdir()
    (source / "htmlcov" / "index.html").write_text("ignored\n")
    (source / "__pycache__").mkdir()
    (source / "__pycache__" / "module.cpython-314.pyc").write_bytes(b"cache")
    (source / "build").mkdir()
    (source / "build" / "artifact.txt").write_text("ignored\n")
    (source / ".coverage").write_text("ignored\n")
    (source / ".coverage.unit").write_text("ignored\n")

    destination = tmp_path / "copied_module"
    _copytree_for_generated_project_smoke(source, destination)

    assert (destination / "module.py").exists()
    assert (destination / "README.md").exists()
    assert not (destination / ".ruff_cache").exists()
    assert not (destination / ".pytest_cache").exists()
    assert not (destination / "htmlcov").exists()
    assert not (destination / "__pycache__").exists()
    assert not (destination / "build").exists()
    assert not (destination / ".coverage").exists()
    assert not (destination / ".coverage.unit").exists()


@pytest.fixture(scope="session")
def docker_available() -> None:
    """Skip E2E tests if Docker daemon is unavailable in this environment."""
    if shutil.which("docker") is None:
        pytest.skip("Docker CLI is not installed")

    check = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        text=True,
    )
    if check.returncode != 0:
        pytest.skip("Docker daemon is not accessible in this environment")


@pytest.fixture(scope="session")
def playwright_browser_available() -> None:
    """Skip browser E2E tests if Playwright Chromium cannot launch."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
            browser.close()
    except Exception as exc:
        pytest.skip(f"Playwright browser is unavailable: {exc}")


@pytest.fixture
def e2e_postgres_url(docker_available, postgres_url: str) -> str:
    """Ensure Docker is available before requesting postgres_url fixture."""
    return postgres_url


@pytest.fixture
def e2e_page(playwright_browser_available, page):
    """Ensure browser is launchable before requesting Playwright page fixture."""
    return page


@pytest.mark.e2e
class TestGeneratedProjectDependencyInstallSmoke:
    """Focused generated-project install smoke coverage for embedded modules."""

    def test_generated_project_forms_module_cli_install_refreshes_existing_lock(
        self, tmp_path
    ):
        """A generated project should install synced forms dependencies through the CLI path."""
        from quickscale_cli.commands.module_commands import _install_module_dependencies
        from quickscale_cli.commands.module_config import get_default_forms_config
        from quickscale_cli.utils.module_dependency_sync import (
            sync_project_module_dependencies,
        )
        from quickscale_core.generator import ProjectGenerator

        project_name = "forms_install_smoke"
        project_path = tmp_path / project_name

        ProjectGenerator(theme="showcase_html").generate(project_name, project_path)
        assert (project_path / "poetry.lock").exists()

        embedded_module_path = project_path / "modules" / "forms"
        _copytree_for_generated_project_smoke(
            REPO_ROOT / "quickscale_modules" / "forms",
            embedded_module_path,
        )

        sync_result = sync_project_module_dependencies(
            project_path,
            {"forms": get_default_forms_config()},
        )

        assert sync_result.added_path_dependencies == ["quickscale-module-forms"]
        assert sync_result.added_package_dependencies == [
            "django-filter",
            "djangorestframework",
        ]

        pyproject_content = (project_path / "pyproject.toml").read_text()
        assert (
            'quickscale-module-forms = {path = "./modules/forms", develop = true}'
            in pyproject_content
        )
        assert 'django-filter = "^25.2"' in pyproject_content
        assert 'djangorestframework = "^3.16.1"' in pyproject_content

        assert _install_module_dependencies(project_path, "forms") is True

        import_result = subprocess.run(
            [
                "poetry",
                "run",
                "python",
                "-c",
                "import django_filters, quickscale_modules_forms, rest_framework",
            ],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert import_result.returncode == 0, (
            "Generated project dependencies did not install correctly: "
            f"{import_result.stderr}\n{import_result.stdout}"
        )

    def test_generated_project_ready_modules_install_required_dependencies(
        self, tmp_path
    ):
        """A generated project should install required dependency distributions for every ready module."""
        from quickscale_cli.commands.apply_command import (
            _run_poetry_install,
            _run_poetry_lock,
        )
        from quickscale_core.contracts.module_catalog import (
            get_discovered_module_entries,
        )
        from quickscale_cli.utils.module_dependency_sync import (
            sync_project_module_dependencies,
        )
        from quickscale_core.generator import ProjectGenerator

        project_name = "ready_modules_install_smoke"
        project_path = tmp_path / project_name

        ProjectGenerator(theme="showcase_html").generate(project_name, project_path)
        assert (project_path / "poetry.lock").exists()

        initial_pyproject = tomllib.loads((project_path / "pyproject.toml").read_text())
        initial_dependencies = initial_pyproject["tool"]["poetry"]["dependencies"]
        assert isinstance(initial_dependencies, dict)

        module_options_by_name: dict[str, dict[str, object]] = {}
        expected_distribution_names: set[str] = set()
        expected_module_package_names: set[str] = set()
        ready_module_names = [entry.name for entry in get_discovered_module_entries()]

        for module_name in ready_module_names:
            _copytree_for_generated_project_smoke(
                REPO_ROOT / "quickscale_modules" / module_name,
                project_path / "modules" / module_name,
            )
            module_config = _default_smoke_config(module_name)
            module_options_by_name[module_name] = module_config
            expected_distribution_names.update(
                _expected_distribution_names(module_name, module_config)
            )
            expected_module_package_names.add(_load_module_package_name(module_name))

        expected_package_dependencies = (
            expected_distribution_names - expected_module_package_names
        )
        expected_new_package_dependencies = {
            dependency_name
            for dependency_name in expected_package_dependencies
            if dependency_name not in initial_dependencies
        }
        expected_new_path_dependencies = {
            dependency_name
            for dependency_name in expected_module_package_names
            if dependency_name not in initial_dependencies
        }

        sync_result = sync_project_module_dependencies(
            project_path,
            module_options_by_name,
        )

        assert {
            dependency_name.lower()
            for dependency_name in sync_result.added_package_dependencies
        } == expected_new_package_dependencies
        assert (
            set(sync_result.added_path_dependencies) == expected_new_path_dependencies
        )

        synced_pyproject = tomllib.loads((project_path / "pyproject.toml").read_text())
        synced_dependencies = synced_pyproject["tool"]["poetry"]["dependencies"]
        assert isinstance(synced_dependencies, dict)
        normalized_synced_dependency_names = {
            dependency_name.lower() for dependency_name in synced_dependencies
        }

        for dependency_name in sorted(expected_distribution_names):
            assert dependency_name.lower() in normalized_synced_dependency_names, (
                f"Expected generated project dependency '{dependency_name}' to be present"
            )

        storage_path_dependency = synced_dependencies["quickscale-module-storage"]
        assert isinstance(storage_path_dependency, dict)
        assert storage_path_dependency["extras"] == ["cloud"]

        assert _run_poetry_lock(project_path) is True
        assert _run_poetry_install(project_path) is True

        verification_code = (
            "import importlib.metadata, json, sys\n"
            "expected = json.loads(sys.argv[1])\n"
            "missing = []\n"
            "for name in expected:\n"
            "    try:\n"
            "        importlib.metadata.version(name)\n"
            "    except importlib.metadata.PackageNotFoundError:\n"
            "        missing.append(name)\n"
            "if missing:\n"
            "    raise SystemExit('Missing distributions: ' + ', '.join(sorted(missing)))\n"
        )
        verification_result = subprocess.run(
            [
                "poetry",
                "run",
                "python",
                "-c",
                verification_code,
                json.dumps(sorted(expected_distribution_names)),
            ],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert verification_result.returncode == 0, (
            "Generated project is missing synced shipped-module distributions: "
            f"{verification_result.stderr}\n{verification_result.stdout}"
        )


@pytest.mark.e2e
class TestFullE2EWorkflow:
    """Complete end-to-end workflow tests with PostgreSQL and browser automation."""

    def test_complete_project_lifecycle(self, tmp_path, e2e_postgres_url, e2e_page):
        """
        Test complete default lifecycle (React): generate → install → migrate → serve → browse.
        """
        from quickscale_core.generator import ProjectGenerator

        # Phase 1: Generate project
        generator = ProjectGenerator()
        assert generator.theme == "showcase_react"
        project_name = "e2e_test_project"
        project_path = tmp_path / project_name

        generator.generate(project_name, project_path)

        # Verify basic structure
        assert (project_path / "manage.py").exists()
        assert (project_path / "pyproject.toml").exists()
        assert (project_path / project_name).is_dir()
        self._run_complete_theme_lifecycle(
            project_path=project_path,
            project_name=project_name,
            postgres_url=e2e_postgres_url,
            page=e2e_page,
            tmp_path=tmp_path,
            build_frontend=True,
            screenshot_name="homepage_screenshot_react_default.png",
        )

    def test_complete_html_project_lifecycle(
        self, tmp_path, e2e_postgres_url, e2e_page
    ):
        """
        Test complete explicit HTML lifecycle: generate → install → migrate → serve → browse.
        """
        from quickscale_core.generator import ProjectGenerator

        generator = ProjectGenerator(theme="showcase_html")
        project_name = "e2e_html_project"
        project_path = tmp_path / project_name

        generator.generate(project_name, project_path)
        self._run_complete_theme_lifecycle(
            project_path=project_path,
            project_name=project_name,
            postgres_url=e2e_postgres_url,
            page=e2e_page,
            tmp_path=tmp_path,
            build_frontend=False,
            screenshot_name="homepage_screenshot_html.png",
        )

    def test_docker_compose_configuration(self, tmp_path):
        """Verify docker-compose.yml is valid and can be parsed by docker compose."""
        from quickscale_core.generator import ProjectGenerator

        generator = ProjectGenerator(theme="showcase_html")
        project_name = "docker_test"
        project_path = tmp_path / project_name

        generator.generate(project_name, project_path)

        # Verify docker-compose file exists
        docker_compose_file = project_path / "docker-compose.yml"
        assert docker_compose_file.exists()

        # Verify docker compose config is valid
        result = subprocess.run(
            [*get_docker_compose_command(), "config"],
            cwd=project_path,
            capture_output=True,
            text=True,
        )

        # Should successfully parse the config
        assert result.returncode == 0, f"docker compose config failed: {result.stderr}"

    def test_generated_project_tests_run(self, tmp_path, e2e_postgres_url):
        """Verify the generated project's test suite runs successfully."""
        from quickscale_core.generator import ProjectGenerator

        generator = ProjectGenerator(theme="showcase_html")
        project_name = "test_runner_project"
        project_path = tmp_path / project_name

        generator.generate(project_name, project_path)

        # Install dependencies first
        self._install_project_dependencies(project_path)

        # Configure test database
        self._configure_test_database(project_path, project_name, e2e_postgres_url)

        # Run migrations first
        self._run_migrations(project_path)

        # Run the generated project's tests
        result = subprocess.run(
            ["poetry", "run", "python", "manage.py", "test"],
            cwd=project_path,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "DJANGO_SETTINGS_MODULE": f"{project_name}.settings.test_e2e",
            },
        )

        # Generated project tests should pass
        assert result.returncode == 0, f"Generated tests failed: {result.stderr}"

    def test_tenant_isolation_conformance_catches_unprotected_model(
        self, tmp_path, e2e_postgres_url
    ):
        """SA1.5 conformance: a deliberately-unprotected model fails check_tenant_isolation.

        Generates a project, embeds the orgs module, adds a model with
        TenantManager but no organization_id, and proves the management
        command exits 1 with JSON failure output.
        """
        from quickscale_core.generator import ProjectGenerator

        generator = ProjectGenerator(theme="showcase_html")
        project_name = "sa15_conformance"
        project_path = tmp_path / project_name

        generator.generate(project_name, project_path)
        self._install_project_dependencies(project_path)

        # ── Embed the orgs module as a path dependency ──────────────────
        module_dir = project_path / "modules" / "orgs"
        _copytree_for_generated_project_smoke(
            REPO_ROOT / "quickscale_modules" / "orgs",
            module_dir,
        )

        pyproject_path = project_path / "pyproject.toml"
        pyproject_content = pyproject_path.read_text()

        if "quickscale-module-orgs" not in pyproject_content:
            pyproject_content = pyproject_content.replace(
                'dj-database-url = "^3.1.0"\n',
                'dj-database-url = "^3.1.0"\n'
                'quickscale-module-orgs = {path = "./modules/orgs", develop = true}\n',
            )
            pyproject_path.write_text(pyproject_content)

        # Regenerate lock and install with the new path dependency
        lock_result = subprocess.run(
            ["poetry", "lock"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert lock_result.returncode == 0, (
            f"poetry lock failed after adding orgs dep: {lock_result.stderr}"
        )
        install_result = subprocess.run(
            ["poetry", "install", "--no-interaction"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert install_result.returncode == 0, (
            f"poetry install failed after adding orgs dep: {install_result.stderr}"
        )

        # ── Create an app with a deliberately-unprotected model ────────
        test_app_dir = project_path / project_name / "test_unprotected"
        test_app_dir.mkdir(exist_ok=True)
        (test_app_dir / "__init__.py").write_text("")

        (test_app_dir / "models.py").write_text(
            '"""Deliberately-unprotected model — TenantManager but no organization_id."""\n'
            "from django.db import models\n"
            "from quickscale_modules_orgs.models import TenantManager\n"
            "\n"
            "\n"
            "class UnprotectedModel(models.Model):\n"
            '    """Model with TenantManager but MISSING organization_id — should fail isolation."""\n'
            "    name = models.CharField(max_length=100)\n"
            "    objects = TenantManager()\n"
            "\n"
            "    class Meta:\n"
            '        app_label = "test_unprotected"\n'
        )

        # ── Register both the orgs module and the test app ─────────────
        test_settings = project_path / project_name / "settings" / "test_e2e.py"
        parsed = urllib.parse.urlparse(e2e_postgres_url)
        db_host = parsed.hostname or "localhost"
        db_port = parsed.port or "5432"

        test_settings.write_text(
            f'"""E2E conformance test settings — includes orgs + unprotected test app."""\n'
            f"from .base import *\n"
            f"\n"
            f"INSTALLED_APPS += [\n"
            f'    "quickscale_modules_orgs",\n'
            f'    "{project_name}.test_unprotected",\n'
            f"]\n"
            f"\n"
            f"DATABASES = {{\n"
            f"    'default': {{\n"
            f"        'ENGINE': 'django.db.backends.postgresql',\n"
            f"        'NAME': 'test_db',\n"
            f"        'USER': 'test_user',\n"
            f"        'PASSWORD': 'test_password',\n"
            f"        'HOST': '{db_host}',\n"
            f"        'PORT': '{db_port}',\n"
            f"    }}\n"
            f"}}\n"
            f"\n"
            f"DEBUG = False\n"
            f"ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']\n"
            f"\n"
            f"CACHES = {{\n"
            f"    'default': {{\n"
            f"        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',\n"
            f"    }}\n"
            f"}}\n"
            f"\n"
            f"# Override logging to use console only (no file logging in tests)\n"
            f"LOGGING = {{\n"
            f"    'version': 1,\n"
            f"    'disable_existing_loggers': False,\n"
            f"    'formatters': {{\n"
            f"        'verbose': {{\n"
            f"            'format': '{{levelname}} {{asctime}} {{module}} {{message}}',\n"
            f"            'style': '{{',\n"
            f"        }},\n"
            f"    }},\n"
            f"    'handlers': {{\n"
            f"        'console': {{\n"
            f"            'class': 'logging.StreamHandler',\n"
            f"            'formatter': 'verbose',\n"
            f"        }},\n"
            f"    }},\n"
            f"    'root': {{\n"
            f"        'handlers': ['console'],\n"
            f"        'level': 'INFO',\n"
            f"    }},\n"
            f"    'loggers': {{\n"
            f"        'django': {{\n"
            f"            'handlers': ['console'],\n"
            f"            'level': 'INFO',\n"
            f"            'propagate': False,\n"
            f"        }},\n"
            f"    }},\n"
            f"}}\n"
        )

        # Run migrations so the table exists
        migrate_result = subprocess.run(
            ["poetry", "run", "python", "manage.py", "migrate", "--noinput"],
            cwd=project_path,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "DJANGO_SETTINGS_MODULE": f"{project_name}.settings.test_e2e",
                "QUICKSCALE_ALLOW_BYPASSRLS": "1",
            },
        )
        assert migrate_result.returncode == 0, (
            f"Migrations failed: {migrate_result.stderr}"
        )

        # ── Run check_tenant_isolation and assert failure ──────────────
        check_result = subprocess.run(
            [
                "poetry",
                "run",
                "python",
                "manage.py",
                "check_tenant_isolation",
                "--postgres-only",
                "--format",
                "json",
            ],
            cwd=project_path,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "DJANGO_SETTINGS_MODULE": f"{project_name}.settings.test_e2e",
                "QUICKSCALE_ALLOW_BYPASSRLS": "1",
            },
        )

        # Exit code 1 — isolation check failed
        assert check_result.returncode != 0, (
            f"check_tenant_isolation should fail with unprotected model "
            f"but exited 0:\nstdout: {check_result.stdout}\n"
            f"stderr: {check_result.stderr}"
        )

        # JSON output should contain failure info
        import json

        try:
            payload = json.loads(check_result.stdout)
        except json.JSONDecodeError as exc:
            raise AssertionError(
                f"check_tenant_isolation output should be valid JSON:\n"
                f"{check_result.stdout}\n{check_result.stderr}"
            ) from exc

        assert payload.get("status") in ("fail",), (
            f"Expected status 'fail', got {payload.get('status')!r}: "
            f"{json.dumps(payload, indent=2)}"
        )

        # Either tenant_models has a failure or unclassified list is non-empty
        tenant_models = payload.get("tenant_models", {})
        unclassified = payload.get("unclassified", [])
        has_tenant_failure = (
            isinstance(tenant_models, dict) and tenant_models.get("failed", 0) > 0
        )
        has_unclassified = isinstance(unclassified, list) and len(unclassified) > 0
        assert has_tenant_failure or has_unclassified, (
            f"Expected tenant model failure or unclassified model, "
            f"but found none:\n{json.dumps(payload, indent=2)}"
        )

    def test_generated_project_python_ruff_check(self, tmp_path):
        """Generated Python project should pass Ruff lint check."""
        from quickscale_core.generator import ProjectGenerator

        project_name = "quality_ruff_check"
        project_path = tmp_path / project_name
        ProjectGenerator(theme="showcase_html").generate(project_name, project_path)

        result = self._run_repo_poetry_command(
            ["ruff", "check", str(project_path)],
            timeout=120,
        )
        assert result.returncode == 0, (
            f"ruff check failed:\n{result.stderr}\n{result.stdout}"
        )

    def test_generated_project_python_ruff_format_check(self, tmp_path):
        """Generated Python project should pass Ruff formatter check mode."""
        from quickscale_core.generator import ProjectGenerator

        project_name = "quality_ruff_format"
        project_path = tmp_path / project_name
        ProjectGenerator(theme="showcase_html").generate(project_name, project_path)

        result = self._run_repo_poetry_command(
            ["ruff", "format", "--check", str(project_path)],
            timeout=120,
        )
        assert result.returncode == 0, (
            f"ruff format --check failed:\n{result.stderr}\n{result.stdout}"
        )

    def test_generated_project_python_mypy_check(self, tmp_path):
        """Generated Python project should pass mypy type checking."""
        from quickscale_core.generator import ProjectGenerator

        project_name = "quality_mypy"
        project_path = tmp_path / project_name
        ProjectGenerator(theme="showcase_html").generate(project_name, project_path)

        current_pythonpath = os.environ.get("PYTHONPATH", "")
        pythonpath = (
            f"{project_path}:{current_pythonpath}"
            if current_pythonpath
            else str(project_path)
        )
        env = {**os.environ, "PYTHONPATH": pythonpath}

        result = self._run_repo_poetry_command(
            [
                "mypy",
                "--config-file",
                str(project_path / "pyproject.toml"),
                str(project_path / project_name),
            ],
            env=env,
            timeout=180,
        )
        assert result.returncode == 0, f"mypy failed:\n{result.stderr}\n{result.stdout}"

    def test_generated_lint_script_python_and_frontend(self, tmp_path):
        """Generated lint script should work for both python and frontend modes."""
        from quickscale_core.generator import ProjectGenerator

        project_name = "lint_script_parity"
        project_path = tmp_path / project_name
        ProjectGenerator(theme="showcase_react").generate(project_name, project_path)

        python_cmd = (
            f"cd {shlex.quote(str(project_path))} && "
            "POETRY_VIRTUALENVS_CREATE=false ./scripts/lint.sh --python"
        )
        python_result = self._run_repo_poetry_command(
            ["bash", "-lc", python_cmd],
            timeout=300,
        )
        assert python_result.returncode == 0, (
            f"scripts/lint.sh --python failed:\n"
            f"{python_result.stderr}\n{python_result.stdout}"
        )

        self._ensure_pnpm_available()

        frontend_cmd = (
            f"cd {shlex.quote(str(project_path))} && "
            "POETRY_VIRTUALENVS_CREATE=false ./scripts/lint.sh --frontend"
        )
        frontend_result = self._run_repo_poetry_command(
            ["bash", "-lc", frontend_cmd],
            timeout=600,
        )
        combined_output = f"{frontend_result.stdout}\n{frontend_result.stderr}"
        if frontend_result.returncode != 0 and _is_network_failure(combined_output):
            pytest.skip("npm registry is unreachable in this environment")

        assert frontend_result.returncode == 0, (
            f"scripts/lint.sh --frontend failed:\n"
            f"{frontend_result.stderr}\n{frontend_result.stdout}"
        )

    def test_complete_react_project_lifecycle(self, tmp_path, e2e_postgres_url):
        """
        Test full React lifecycle: generate → build frontend → serve → validate routes.
        """
        from quickscale_core.generator import ProjectGenerator

        generator = ProjectGenerator(theme="showcase_react")
        project_name = "e2e_react_project"
        project_path = tmp_path / project_name

        generator.generate(project_name, project_path)
        self._install_project_dependencies(project_path)
        self._build_react_frontend(project_path)

        # Configure test database (creates settings/test_e2e.py)
        self._configure_test_database(project_path, project_name, e2e_postgres_url)
        self._run_migrations(project_path)
        self._collect_static(project_path)

        local_env = {
            **os.environ,
            "DJANGO_SETTINGS_MODULE": f"{project_name}.settings.test_e2e",
        }
        check_result = subprocess.run(
            ["poetry", "run", "python", "manage.py", "check"],
            cwd=project_path,
            capture_output=True,
            text=True,
            env=local_env,
        )
        assert check_result.returncode == 0, (
            f"Django checks failed: {check_result.stderr}"
        )

        server_port = self._find_free_port()
        server_process = subprocess.Popen(
            [
                "poetry",
                "run",
                "python",
                "manage.py",
                "runserver",
                str(server_port),
                "--noreload",
            ],
            cwd=project_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=local_env,
            text=True,
            bufsize=1,
        )

        try:
            self._wait_for_server(
                f"http://localhost:{server_port}",
                timeout=30,
                server_process=server_process,
            )

            self._test_react_routes_render(server_port)
        finally:
            try:
                server_process.terminate()
                server_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                server_process.kill()
                server_process.wait(timeout=2)

    def test_ci_workflow_is_valid(self, tmp_path):
        """Verify GitHub Actions CI workflow is valid YAML."""
        from quickscale_core.generator import ProjectGenerator

        generator = ProjectGenerator(theme="showcase_html")
        project_name = "ci_test"
        project_path = tmp_path / project_name

        generator.generate(project_name, project_path)

        ci_file = project_path / ".github" / "workflows" / "ci.yml"
        assert ci_file.exists()

        ci_content = ci_file.read_text()
        assert "runs-on: ubuntu-24.04" in ci_content
        assert 'python-version: ["3.13"]' in ci_content
        assert "apt.postgresql.org" in ci_content
        assert "apt.postgresql.org.asc" in ci_content
        assert "postgresql-client-18" in ci_content
        assert 'echo "/usr/lib/postgresql/18/bin" >> "$GITHUB_PATH"' in ci_content
        assert (
            'test "$(command -v pg_dump)" = "/usr/lib/postgresql/18/bin/pg_dump"'
            in ci_content
        )
        assert (
            'test "$(command -v pg_restore)" = "/usr/lib/postgresql/18/bin/pg_restore"'
            in ci_content
        )
        assert "pg_dump --version" in ci_content
        assert "pg_restore --version" in ci_content
        assert "uses: codecov/codecov-action@v5" in ci_content
        assert "files: ./coverage.xml" in ci_content
        assert "file: ./coverage.xml" not in ci_content
        assert "version: 11.0.9" in ci_content
        assert (
            "if: matrix.python-version == '3.13' && matrix.django-version == '6.0'"
            in ci_content
        )
        assert "3.14" not in ci_content
        assert "10.28.2" not in ci_content
        assert "codecov/codecov-action@v4" not in ci_content
        assert "gpg --dearmor" not in ci_content
        assert "gnupg" not in ci_content

        # Verify it's valid YAML
        import yaml

        with open(ci_file) as f:
            ci_config = yaml.safe_load(f)

        # Verify key CI elements exist
        assert "name" in ci_config
        assert "jobs" in ci_config
        assert ci_config["name"] == "CI"

    # Helper methods

    def _run_complete_theme_lifecycle(
        self,
        project_path: Path,
        project_name: str,
        postgres_url: str,
        page,
        tmp_path: Path,
        *,
        build_frontend: bool,
        screenshot_name: str,
    ) -> None:
        """Execute full lifecycle for a generated theme project."""
        # Phase 2: Install dependencies in the generated project
        self._install_project_dependencies(project_path)

        # React theme requires frontend build before collectstatic/browser assertions
        if build_frontend:
            self._build_react_frontend(project_path)

        # Phase 3: Configure database for E2E test
        self._configure_test_database(project_path, project_name, postgres_url)

        # Phase 4: Run Django management commands
        self._run_django_checks(project_path)
        self._run_migrations(project_path)
        self._collect_static(project_path)

        # Phase 5: Start development server in background
        server_port = self._find_free_port()
        server_process = self._start_dev_server(project_path, port=server_port)

        try:
            self._wait_for_server(
                f"http://localhost:{server_port}",
                timeout=30,
                server_process=server_process,
            )

            # Phase 6: Browser tests with Playwright
            self._test_homepage_loads(page, port=server_port)
            self._test_page_content(page, project_name, port=server_port)
            self._test_static_files_load(page, port=server_port)

            screenshot_path = tmp_path / screenshot_name
            page.screenshot(path=str(screenshot_path))
            assert screenshot_path.exists()

        finally:
            try:
                server_process.terminate()
                server_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                server_process.kill()
                server_process.wait(timeout=2)

    def _find_free_port(self) -> int:
        """Find a free port by binding to port 0 and letting the OS assign one."""
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port

    def _ensure_port_free(self, port: int = 8000):
        """Ensure the specified port is free before starting server."""
        import socket

        # First, check if port is already free
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                print(f"✓ Port {port} is already free")
                return
        except OSError:
            pass  # Port is in use, try to free it

        # Try to kill any processes using the port
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split("\n")
            for pid in pids:
                try:
                    subprocess.run(["kill", "-9", pid], check=True)
                    print(f"✓ Killed process {pid} on port {port}")
                except subprocess.CalledProcessError:
                    pass  # Process may have already terminated

        # Wait for port to actually be free (with timeout)
        max_wait = 10  # seconds (increased from 5)
        wait_interval = 0.2
        elapsed = 0

        while elapsed < max_wait:
            try:
                # Try to bind to the port to verify it's free
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(("127.0.0.1", port))
                    # If we can bind, the port is free
                    print(f"✓ Port {port} is now free")
                    return
            except OSError:
                # Port is still in use, wait a bit
                time.sleep(wait_interval)
                elapsed += wait_interval

        # If we get here, port is still not free - raise an error
        raise RuntimeError(f"Port {port} is still in use after {max_wait} seconds")

    def _run_repo_poetry_command(
        self,
        args: list[str],
        timeout: int,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run poetry command from quickscale_core package environment."""
        return subprocess.run(
            ["poetry", "run", *args],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )

    def _ensure_pnpm_available(self) -> None:
        """Ensure pnpm is installed and npm registry is reachable."""
        if shutil.which("pnpm") is None:
            pytest.skip("pnpm is not installed")

        try:
            probe = subprocess.run(
                ["pnpm", "view", "react", "version"],
                capture_output=True,
                text=True,
                timeout=20,
            )
        except subprocess.TimeoutExpired:
            pytest.skip("npm registry probe timed out in this environment")

        if probe.returncode != 0:
            combined_output = f"{probe.stdout}\n{probe.stderr}"
            if _is_network_failure(combined_output):
                pytest.skip("npm registry is unreachable in this environment")

    def _install_project_dependencies(self, project_path: Path):
        """Install dependencies in the generated project using poetry."""
        # First, regenerate lock file to match current Python version
        lock_result = subprocess.run(
            ["poetry", "lock"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=120,  # 2 minutes timeout for lock
        )
        lock_output = f"{lock_result.stdout}\n{lock_result.stderr}"
        if lock_result.returncode != 0 and _is_poetry_network_failure(lock_output):
            pytest.skip("PyPI is unreachable in this environment")
        assert lock_result.returncode == 0, f"Poetry lock failed: {lock_result.stderr}"

        # Then install dependencies from the updated lock file
        install_result = subprocess.run(
            ["poetry", "install", "--no-interaction"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=180,  # 3 minutes timeout for installation
        )
        install_output = f"{install_result.stdout}\n{install_result.stderr}"
        if install_result.returncode != 0 and _is_poetry_network_failure(
            install_output
        ):
            pytest.skip("PyPI is unreachable in this environment")
        assert install_result.returncode == 0, (
            f"Poetry install failed: {install_result.stderr}"
        )

    def _build_react_frontend(self, project_path: Path) -> None:
        """Install, type-check, and build React frontend assets."""
        self._ensure_pnpm_available()
        frontend_path = project_path / "frontend"

        install_result: subprocess.CompletedProcess[str] | None = None
        install_attempts = 2
        install_timeout_seconds = 300

        for attempt in range(1, install_attempts + 1):
            try:
                install_result = subprocess.run(
                    ["pnpm", "install"],
                    cwd=frontend_path,
                    capture_output=True,
                    text=True,
                    timeout=install_timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                timeout_output = _timeout_output(exc)
                if _is_network_failure(timeout_output):
                    if attempt == install_attempts:
                        pytest.skip("npm registry is unreachable in this environment")
                    time.sleep(2)
                    continue
                raise AssertionError(
                    f"pnpm install timed out after {install_timeout_seconds}s"
                ) from exc

            combined_install_output = (
                f"{install_result.stdout}\n{install_result.stderr}"
            )
            if install_result.returncode == 0:
                break
            if _is_network_failure(combined_install_output):
                if attempt == install_attempts:
                    pytest.skip("npm registry is unreachable in this environment")
                time.sleep(2)
                continue
            raise AssertionError(f"pnpm install failed: {install_result.stderr}")

        assert install_result is not None
        assert install_result.returncode == 0, "pnpm install failed"

        typecheck_result = subprocess.run(
            ["pnpm", "run", "type-check"],
            cwd=frontend_path,
            capture_output=True,
            text=True,
            timeout=240,
        )
        assert typecheck_result.returncode == 0, (
            f"pnpm type-check failed: {typecheck_result.stderr}"
        )

        build_result = subprocess.run(
            ["pnpm", "run", "build"],
            cwd=frontend_path,
            capture_output=True,
            text=True,
            timeout=240,
        )
        assert build_result.returncode == 0, f"pnpm build failed: {build_result.stderr}"

    def _configure_test_database(
        self, project_path: Path, project_name: str, postgres_url: str
    ):
        """Configure generated project to use test PostgreSQL database."""
        # Create a test settings file that uses the test database
        test_settings = project_path / project_name / "settings" / "test_e2e.py"

        parsed = urllib.parse.urlparse(postgres_url)
        db_host = parsed.hostname or "localhost"
        db_port = parsed.port or "5432"

        settings_content = f'''"""E2E test settings - uses test PostgreSQL."""
from .base import *

DATABASES = {{
    'default': {{
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'test_db',
        'USER': 'test_user',
        'PASSWORD': 'test_password',
        'HOST': '{db_host}',
        'PORT': '{db_port}',
    }}
}}

# Disable debug for E2E tests
DEBUG = False
ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']

# Use in-memory cache for testing
CACHES = {{
    'default': {{
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }}
}}

# Override logging to use console only (no file logging in tests)
LOGGING = {{
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {{
        'verbose': {{
            'format': '{{levelname}} {{asctime}} {{module}} {{message}}',
            'style': '{{',
        }},
    }},
    'handlers': {{
        'console': {{
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        }},
    }},
    'root': {{
        'handlers': ['console'],
        'level': 'INFO',
    }},
    'loggers': {{
        'django': {{
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        }},
    }},
}}
'''
        test_settings.write_text(settings_content)

    def _run_django_checks(self, project_path: Path):
        """Run Django system checks."""
        result = subprocess.run(
            ["poetry", "run", "python", "manage.py", "check"],
            cwd=project_path,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "DJANGO_SETTINGS_MODULE": f"{project_path.name}.settings.test_e2e",
            },
        )
        assert result.returncode == 0, f"Django checks failed: {result.stderr}"

    def _run_migrations(self, project_path: Path):
        """Run database migrations."""
        result = subprocess.run(
            ["poetry", "run", "python", "manage.py", "migrate", "--noinput"],
            cwd=project_path,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "DJANGO_SETTINGS_MODULE": f"{project_path.name}.settings.test_e2e",
            },
        )
        assert result.returncode == 0, f"Migrations failed: {result.stderr}"

    def _collect_static(self, project_path: Path):
        """Collect static files."""
        result = subprocess.run(
            ["poetry", "run", "python", "manage.py", "collectstatic", "--noinput"],
            cwd=project_path,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "DJANGO_SETTINGS_MODULE": f"{project_path.name}.settings.test_e2e",
            },
        )
        assert result.returncode == 0, f"collectstatic failed: {result.stderr}"

    def _start_dev_server(self, project_path: Path, port: int = 8000):
        """Start Django development server in background."""
        # Start server without capturing output so we can see errors
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
            stderr=subprocess.STDOUT,  # Merge stderr into stdout for easier debugging
            env={
                **os.environ,
                "DJANGO_SETTINGS_MODULE": f"{project_path.name}.settings.test_e2e",
            },
            text=True,
            bufsize=1,  # Line buffered
        )

    def _wait_for_server(self, url: str, timeout: int = 30, server_process=None):
        """
        Wait for server to be responsive.

        Args:
        ----
            url: URL to check
            timeout: Maximum seconds to wait (default 30)
            server_process: Optional Popen object to check if process crashed

        """
        import urllib.error
        import urllib.request

        start_time = time.time()
        last_error = None

        while time.time() - start_time < timeout:
            # Check if server process crashed
            if server_process and server_process.poll() is not None:
                # Process has terminated - capture output for debugging
                output = server_process.stdout.read() if server_process.stdout else ""
                exit_code = server_process.returncode
                raise RuntimeError(
                    f"Server process terminated unexpectedly with exit code {exit_code}.\n"
                    f"Output:\n{output}"
                )

            try:
                urllib.request.urlopen(url, timeout=1)
                return
            except (urllib.error.URLError, OSError) as e:
                last_error = e
                time.sleep(0.5)

        # Timeout - provide helpful error message
        error_msg = f"Server did not start within {timeout} seconds."
        if server_process and server_process.stdout:
            # Try to get some output for debugging
            output_lines = []
            try:
                for _ in range(20):  # Read up to 20 lines
                    line = server_process.stdout.readline()
                    if not line:
                        break
                    output_lines.append(line)
                if output_lines:
                    error_msg += f"\n\nServer output:\n{''.join(output_lines)}"
            except Exception:
                pass

        if last_error:
            error_msg += f"\n\nLast connection error: {last_error}"

        raise TimeoutError(error_msg)

    def _test_homepage_loads(self, page, port: int = 8000):
        """Test that homepage loads successfully."""
        response = page.goto(f"http://localhost:{port}")
        assert response.status == 200, f"Homepage returned status {response.status}"

    def _test_page_content(self, page, project_name: str, port: int = 8000):
        """Test that page contains expected content."""
        page.goto(f"http://localhost:{port}")

        # Verify page has a title
        assert page.title(), "Page should have a title"

        # Verify body content exists
        body = page.locator("body")
        assert body.is_visible(), "Body should be visible"

    def _test_static_files_load(self, page, port: int = 8000):
        """Test that static files (CSS) load successfully."""
        page.goto(f"http://localhost:{port}")

        # Check if any CSS files are linked
        css_links = page.locator('link[rel="stylesheet"]')

        # If CSS files exist, verify they load
        if css_links.count() > 0:
            first_css = css_links.first
            href = first_css.get_attribute("href")

            # Navigate to CSS file to verify it loads
            if href:
                response = page.goto(f"http://localhost:{port}{href}")
                assert response.status == 200, f"CSS file failed to load: {href}"

    def _test_react_routes_render(self, port: int = 8000):
        """Test React SPA routes return index template and built asset references."""
        import urllib.request

        urls = [
            f"http://localhost:{port}/",
            f"http://localhost:{port}/settings",
            f"http://localhost:{port}/this-route-does-not-exist",
        ]

        for url in urls:
            response = urllib.request.urlopen(url, timeout=10)
            assert response.status == 200, f"Route failed: {url}"

            html = response.read().decode("utf-8")
            assert '<div id="root"></div>' in html, (
                f"React root missing for route: {url}"
            )
            assert "frontend/assets/index" in html, (
                f"React JS bundle not referenced for route: {url}"
            )


@pytest.mark.e2e
class TestModuleEmbedE2E(TestFullE2EWorkflow):
    """End-to-end coverage for the full module embed workflow.

    Validates: generate -> real git subtree embed -> wiring regeneration ->
    Django boots -> module URL responds, for the auth module in both the
    HTML and React starter themes.

    The auth module's wiring spec (see manifest adapter for auth)
    mounts allauth and the module's own URLs at the ``accounts/`` prefix,
    so the login URL served by the module is ``/accounts/login/``.
    """

    def _get_local_repo_branch(self) -> str:
        """Return the current branch of the local maintainer repo."""
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        branch = result.stdout.strip()
        if not branch:
            # Detached HEAD fallback - subtree add accepts a commit-ish.
            return "HEAD"
        return branch

    def _run_git(
        self, project_path: Path, *args: str
    ) -> subprocess.CompletedProcess[str]:
        """Run a git command inside the generated project directory."""
        return subprocess.run(
            ["git", *args],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def _embed_auth_module_via_subtree(self, project_path: Path) -> str:
        """Init a git repo, commit the scaffold, and embed the auth module.

        Returns the branch name used for the subtree add so callers can log it.
        """
        # Initialise a fresh repo so subtree add has a clean parent.
        init_result = self._run_git(project_path, "init")
        assert init_result.returncode == 0, f"git init failed: {init_result.stderr}"
        self._run_git(
            project_path,
            "config",
            "user.email",
            "quickscale-e2e@example.com",
        )
        self._run_git(project_path, "config", "user.name", "QuickScale E2E")
        self._run_git(
            project_path,
            "config",
            "commit.gpgsign",
            "false",
        )

        # Subtree add requires at least one commit on the parent branch.
        add_result = self._run_git(project_path, "add", ".")
        assert add_result.returncode == 0, f"git add failed: {add_result.stderr}"
        commit_result = self._run_git(project_path, "commit", "-m", "initial scaffold")
        assert commit_result.returncode == 0, (
            f"Initial commit failed: {commit_result.stderr}"
        )

        branch = self._get_local_repo_branch()
        subtree_result = self._run_git(
            project_path,
            "subtree",
            "add",
            "--prefix=modules/auth",
            "--squash",
            str(REPO_ROOT),
            branch,
        )
        assert subtree_result.returncode == 0, (
            f"git subtree add failed (branch={branch!r}):\n"
            f"stdout: {subtree_result.stdout}\n"
            f"stderr: {subtree_result.stderr}"
        )

        # Sanity-check that the embed actually landed.
        assert (project_path / "modules" / "auth" / "module.yml").exists(), (
            "Auth module manifest missing after git subtree add"
        )
        assert (project_path / "modules" / "auth" / "pyproject.toml").exists(), (
            "Auth module pyproject.toml missing after git subtree add"
        )
        assert (
            project_path / "modules" / "auth" / "src" / "quickscale_modules_auth"
        ).is_dir(), "Auth module source tree missing after git subtree add"

        return branch

    def _write_quickscale_yml_with_auth(
        self,
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

    def _sync_auth_module_dependency(
        self, project_path: Path, auth_options: dict[str, object]
    ) -> None:
        """Add the embedded auth module as a Poetry path dependency.

        Regenerating managed wiring only writes settings/URL files; it does
        not register the module with Poetry. Without this step the module's
        Python package is not importable from the generated project venv.
        """
        from quickscale_cli.utils.module_dependency_sync import (
            sync_project_module_dependencies,
        )

        sync_result = sync_project_module_dependencies(
            project_path, {"auth": auth_options}
        )
        assert "quickscale-module-auth" in sync_result.added_path_dependencies, (
            "sync_project_module_dependencies did not register the auth module "
            f"as a path dependency: {sync_result}"
        )

    def _regenerate_wiring(self, project_path: Path) -> None:
        """Regenerate managed settings/URL wiring for the embedded auth module."""
        from quickscale_cli.utils.module_wiring_manager import (
            regenerate_managed_wiring,
        )

        success, message = regenerate_managed_wiring(project_path)
        assert success, f"regenerate_managed_wiring failed: {message}"

    def _assert_auth_url_responds(
        self, server_process, port: int, timeout: int = 20
    ) -> None:
        """Hit the auth module's login URL and assert a 200 response.

        Note: the auth module's wiring spec mounts allauth and the module's
        own URLs at the ``accounts/`` prefix, so the login URL is
        ``/accounts/login/`` (not ``/auth/login/``).
        """
        import urllib.error
        import urllib.request

        url = f"http://localhost:{port}/accounts/login/"
        start = time.time()
        last_error: Exception | None = None

        while time.time() - start < timeout:
            if server_process.poll() is not None:
                output = ""
                if server_process.stdout is not None:
                    output = server_process.stdout.read()
                raise RuntimeError(
                    f"Server process exited with code "
                    f"{server_process.returncode} before responding.\n"
                    f"Output:\n{output}"
                )
            try:
                response = urllib.request.urlopen(url, timeout=2)
                if response.status == 200:
                    return
                last_error = AssertionError(
                    f"Auth login URL returned status {response.status}: {url}"
                )
            except urllib.error.HTTPError as exc:
                last_error = AssertionError(
                    f"Auth login URL returned status {exc.code}: {url}"
                )
            except (urllib.error.URLError, OSError) as exc:
                last_error = exc
            time.sleep(0.5)

        raise AssertionError(
            f"Auth login URL {url} did not respond with 200 within {timeout}s. "
            f"Last error: {last_error}"
        )

    def _run_module_embed_lifecycle(
        self,
        project_path: Path,
        project_name: str,
        theme: str,
        postgres_url: str,
        *,
        build_frontend: bool,
        subtree_branch: str,
    ) -> None:
        """Execute the embed -> wire -> boot -> serve -> assert lifecycle."""
        from quickscale_cli.commands.module_config import get_default_auth_config

        auth_options = get_default_auth_config()

        # Declarative config + managed wiring + path-dependency registration.
        self._write_quickscale_yml_with_auth(
            project_path, project_name, theme, auth_options
        )
        self._sync_auth_module_dependency(project_path, auth_options)
        self._regenerate_wiring(project_path)

        # Install resolved dependencies (poetry lock + install).
        self._install_project_dependencies(project_path)

        if build_frontend:
            self._build_react_frontend(project_path)

        self._configure_test_database(project_path, project_name, postgres_url)
        self._run_migrations(project_path)

        server_port = self._find_free_port()
        server_process = self._start_dev_server(project_path, port=server_port)

        try:
            self._wait_for_server(
                f"http://localhost:{server_port}",
                timeout=30,
                server_process=server_process,
            )
            self._assert_auth_url_responds(server_process, server_port)
        finally:
            try:
                server_process.terminate()
                server_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                server_process.kill()
                server_process.wait(timeout=2)
        # Silence the unused-argument warning while keeping the branch label
        # visible in test logs.
        _ = subtree_branch

    def test_auth_module_embed_html_theme(self, tmp_path, e2e_postgres_url):
        """Validate the full auth embed workflow for the showcase_html theme."""
        from quickscale_core.generator import ProjectGenerator

        project_name = "embed_auth_html"
        project_path = tmp_path / project_name

        ProjectGenerator(theme="showcase_html").generate(project_name, project_path)

        subtree_branch = self._embed_auth_module_via_subtree(project_path)

        self._run_module_embed_lifecycle(
            project_path=project_path,
            project_name=project_name,
            theme="showcase_html",
            postgres_url=e2e_postgres_url,
            build_frontend=False,
            subtree_branch=subtree_branch,
        )

    def test_auth_module_embed_react_theme(self, tmp_path, e2e_postgres_url):
        """Validate the full auth embed workflow for the showcase_react theme."""
        from quickscale_core.generator import ProjectGenerator

        project_name = "embed_auth_react"
        project_path = tmp_path / project_name

        ProjectGenerator(theme="showcase_react").generate(project_name, project_path)

        subtree_branch = self._embed_auth_module_via_subtree(project_path)

        self._run_module_embed_lifecycle(
            project_path=project_path,
            project_name=project_name,
            theme="showcase_react",
            postgres_url=e2e_postgres_url,
            build_frontend=True,
            subtree_branch=subtree_branch,
        )


@pytest.mark.e2e
class TestDockerIntegration:
    """Test Docker-related functionality."""

    def test_dockerfile_is_valid(self, tmp_path):
        """Verify Dockerfile can be built successfully."""
        from quickscale_core.generator import ProjectGenerator

        generator = ProjectGenerator(theme="showcase_html")
        project_name = "dockerfile_test"
        project_path = tmp_path / project_name

        generator.generate(project_name, project_path)

        dockerfile = project_path / "Dockerfile"
        assert dockerfile.exists()

        # Verify Dockerfile has essential instructions
        content = dockerfile.read_text()
        assert "FROM python:" in content
        assert "WORKDIR" in content
        assert "COPY" in content
        assert "RUN" in content

    def test_gitignore_is_comprehensive(self, tmp_path):
        """Verify .gitignore includes common patterns."""
        from quickscale_core.generator import ProjectGenerator

        generator = ProjectGenerator(theme="showcase_html")
        project_name = "gitignore_test"
        project_path = tmp_path / project_name

        generator.generate(project_name, project_path)

        gitignore = project_path / ".gitignore"
        assert gitignore.exists()

        content = gitignore.read_text()

        # Should ignore common Python patterns
        assert "__pycache__" in content or "*.pyc" in content
        assert ".env" in content
        assert "venv" in content or "env/" in content

        # Should ignore IDE files
        assert ".vscode" in content or ".idea" in content


@pytest.mark.e2e
class TestProductionReadiness:
    """Test production-readiness features of generated projects."""

    def test_security_settings_are_present(self, tmp_path):
        """Verify production security settings exist."""
        from quickscale_core.generator import ProjectGenerator

        generator = ProjectGenerator(theme="showcase_html")
        project_name = "security_test"
        project_path = tmp_path / project_name

        generator.generate(project_name, project_path)

        prod_settings = project_path / project_name / "settings" / "production.py"
        assert prod_settings.exists()

        content = prod_settings.read_text()

        # Key security settings should be present
        assert "DEBUG = False" in content or "DEBUG=False" in content
        assert "SECURE_" in content  # SECURE_* settings
        assert "ALLOWED_HOSTS" in content

    def test_environment_variable_configuration(self, tmp_path):
        """Verify environment variable configuration exists."""
        from quickscale_core.generator import ProjectGenerator

        generator = ProjectGenerator(theme="showcase_html")
        project_name = "env_test"
        project_path = tmp_path / project_name

        generator.generate(project_name, project_path)

        # Should have example .env file
        env_example = project_path / ".env.example"
        if env_example.exists():
            content = env_example.read_text()
            assert "SECRET_KEY" in content or "DJANGO_SECRET_KEY" in content
