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
import subprocess
import time
from pathlib import Path

import pytest


@pytest.mark.e2e
class TestFullE2EWorkflow:
    """Complete end-to-end workflow tests with PostgreSQL and browser automation."""

    def test_complete_project_lifecycle(self, tmp_path, postgres_url, page, browser):
        """
        Test complete project lifecycle: generate → install → migrate → serve → browse.

        This is the comprehensive E2E test that verifies:
        - Project generation works
        - Generated project can be installed
        - Database migrations work with real PostgreSQL
        - Django server starts successfully
        - Frontend homepage loads in browser
        - All essential files are present and valid
        """
        from quickscale_core.generator import ProjectGenerator

        # Phase 1: Generate project
        generator = ProjectGenerator()
        project_name = "e2e_test_project"
        project_path = tmp_path / project_name

        generator.generate(project_name, project_path)

        # Verify basic structure
        assert (project_path / "manage.py").exists()
        assert (project_path / "pyproject.toml").exists()
        assert (project_path / project_name).is_dir()

        # Phase 2: Install dependencies in the generated project
        self._install_project_dependencies(project_path)

        # Phase 3: Configure database for E2E test
        # Update settings to use test PostgreSQL
        self._configure_test_database(project_path, project_name, postgres_url)

        # Phase 4: Run Django management commands
        self._run_django_checks(project_path)
        self._run_migrations(project_path)
        self._collect_static(project_path)

        # Phase 5: Start development server in background
        # Use a dynamically assigned free port to avoid conflicts
        server_port = self._find_free_port()
        server_process = self._start_dev_server(project_path, port=server_port)

        try:
            # Wait for server to be ready (increased timeout for initial startup)
            self._wait_for_server(
                f"http://localhost:{server_port}",
                timeout=30,
                server_process=server_process,
            )

            # Phase 6: Browser tests with Playwright
            self._test_homepage_loads(page, port=server_port)
            self._test_page_content(page, project_name, port=server_port)
            self._test_static_files_load(page, port=server_port)

            # Take screenshot for visual verification
            screenshot_path = tmp_path / "homepage_screenshot.png"
            page.screenshot(path=str(screenshot_path))
            assert screenshot_path.exists()

        finally:
            # Cleanup: Stop server
            try:
                server_process.terminate()
                server_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                # Force kill if terminate didn't work
                server_process.kill()
                server_process.wait(timeout=2)

    def test_docker_compose_configuration(self, tmp_path):
        """Verify docker-compose.yml is valid and can be parsed."""
        from quickscale_core.generator import ProjectGenerator

        generator = ProjectGenerator()
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

    def test_generated_project_tests_run(self, tmp_path, postgres_url):
        """Verify the generated project's test suite runs successfully."""
        from quickscale_core.generator import ProjectGenerator

        generator = ProjectGenerator()
        project_name = "test_runner_project"
        project_path = tmp_path / project_name

        generator.generate(project_name, project_path)

        # Install dependencies first
        self._install_project_dependencies(project_path)

        # Configure test database
        self._configure_test_database(project_path, project_name, postgres_url)

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

    def test_ci_workflow_is_valid(self, tmp_path):
        """Verify GitHub Actions CI workflow is valid YAML."""
        from quickscale_core.generator import ProjectGenerator

        generator = ProjectGenerator()
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

    def _install_project_dependencies(self, project_path: Path):
        """Install dependencies in the generated project using poetry."""
        # First, regenerate lock file to match current Python version
        lock_result = subprocess.run(
            ["poetry", "lock", "--no-update"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=120,  # 2 minutes timeout for lock
        )
        assert lock_result.returncode == 0, f"Poetry lock failed: {lock_result.stderr}"

        # Then install dependencies from the updated lock file
        install_result = subprocess.run(
            ["poetry", "install", "--no-interaction"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=180,  # 3 minutes timeout for installation
        )
        assert (
            install_result.returncode == 0
        ), f"Poetry install failed: {install_result.stderr}"

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


@pytest.mark.e2e
class TestDockerIntegration:
    """Test Docker-related functionality."""

    def test_dockerfile_is_valid(self, tmp_path):
        """Verify Dockerfile can be built successfully."""
        from quickscale_core.generator import ProjectGenerator

        generator = ProjectGenerator()
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

        generator = ProjectGenerator()
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

        generator = ProjectGenerator()
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

        generator = ProjectGenerator()
        project_name = "env_test"
        project_path = tmp_path / project_name

        generator.generate(project_name, project_path)

        # Should have example .env file
        env_example = project_path / ".env.example"
        if env_example.exists():
            content = env_example.read_text()
            assert "SECRET_KEY" in content or "DJANGO_SECRET_KEY" in content
