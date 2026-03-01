"""
Full end-to-end tests for QuickScale project generation workflow.

These tests verify the complete lifecycle:
1. Generate Django project
2. Install dependencies with Poetry
3. Run migrations against real PostgreSQL
4. Execute Django management commands
5. Start development server
6. Test frontend with Playwright browser automation
7. Verify Docker and docker-compose setup

Run with: pytest -m e2e
"""

import os
import shlex
import shutil
import subprocess
import time
from pathlib import Path

import pytest


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
    except Exception as exc:  # pragma: no cover - environment-dependent
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
        """Verify docker-compose.yml is valid and can be parsed."""
        from quickscale_core.generator import ProjectGenerator

        generator = ProjectGenerator(theme="showcase_html")
        project_name = "docker_test"
        project_path = tmp_path / project_name

        generator.generate(project_name, project_path)

        # Verify docker-compose file exists
        docker_compose_file = project_path / "docker-compose.yml"
        assert docker_compose_file.exists()

        # Verify docker-compose config is valid
        result = subprocess.run(
            ["docker-compose", "config"],
            cwd=project_path,
            capture_output=True,
            text=True,
        )

        # Should successfully parse the config
        assert result.returncode == 0, f"docker-compose config failed: {result.stderr}"

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
        """Install and build React frontend assets for generated project."""
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

        settings_content = f'''"""E2E test settings - uses test PostgreSQL."""
from .base import *

DATABASES = {{
    'default': {{
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'test_db',
        'USER': 'test_user',
        'PASSWORD': 'test_password',
        'HOST': '{postgres_url.split("@")[1].split(":")[0]}',
        'PORT': '{postgres_url.split(":")[-1].split("/")[0]}',
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
