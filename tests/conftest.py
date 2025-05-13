"""Pytest configuration and fixtures for testing."""
import os
import sys
import time
import subprocess
import shutil
import pytest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
import django
from django.test.testcases import LiveServerTestCase
from typing import Optional

# Add tests directory to Python path to make tests/core and tests/users importable
tests_dir = os.path.dirname(os.path.abspath(__file__))
if tests_dir not in sys.path:
    sys.path.insert(0, tests_dir)

# Maximum wait time for services to be ready (seconds)
SERVICE_TIMEOUT = 30
# Polling interval for checking service readiness (seconds)
POLL_INTERVAL = 0.5

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.core.settings")
django.setup()

@pytest.fixture(scope="session", autouse=True)
def patch_django_for_bytes_path():
    """
    Patch Django's StaticFilesHandler and LiveServerTestCase classes to handle bytes paths correctly.
    
    This fixes the issue where bytes paths from WSGI are compared with string paths using startswith(),
    resulting in a TypeError. The issue occurs specifically in Django's StaticFilesHandler._should_handle
    method which is used by LiveServerTestCase.
    """
    # Import the relevant classes
    from django.contrib.staticfiles.handlers import StaticFilesHandler
    from django.core.handlers.wsgi import WSGIHandler, get_path_info
    
    # Patch 1: Fix the get_path_info function to always return a string
    original_get_path_info = get_path_info
    
    def patched_get_path_info(environ):
        """Return the path info as a string, not bytes."""
        path = original_get_path_info(environ)
        if isinstance(path, bytes):
            path = path.decode('utf-8')
        return path
    
    # Patch 2: Fix StaticFilesHandler._should_handle to handle bytes
    if hasattr(StaticFilesHandler, '_should_handle'):
        original_should_handle = StaticFilesHandler._should_handle
        
        def patched_should_handle(self, path):
            """Handle both string and bytes paths."""
            if isinstance(path, bytes):
                path = path.decode('utf-8')
            return original_should_handle(self, path)
        
        # Apply patches
        with patch('django.core.handlers.wsgi.get_path_info', patched_get_path_info):
            with patch.object(StaticFilesHandler, '_should_handle', patched_should_handle):
                yield
    else:
        # If the method doesn't exist (Django version difference), just patch get_path_info
        with patch('django.core.handlers.wsgi.get_path_info', patched_get_path_info):
            yield

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup global test environment that's used for all tests."""
    # Store original environment
    original_env = os.environ.copy()
    original_dir = os.getcwd()
    
    # Setup test-specific environment variables
    os.environ["QUICKSCALE_TEST_MODE"] = "1"
    os.environ["QUICKSCALE_NO_ANALYTICS"] = "1"
    
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)
    os.chdir(original_dir)

@contextmanager
def chdir(path):
    """Context manager for changing directory with safe return to previous dir."""
    old_dir = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(old_dir)

@pytest.fixture
def cli_runner(monkeypatch, tmp_path):
    """Fixture for testing CLI commands with isolated filesystem."""
    with chdir(tmp_path):
        # Create a test project structure
        test_project = tmp_path / "test_project"
        test_project.mkdir()
        
        yield tmp_path
        
        # Clean up any Docker containers that might have been started
        try:
            subprocess.run(
                ['docker', 'ps', '-q', '--filter', 'name=test_project_'], 
                stdout=subprocess.PIPE, 
                check=True, 
                text=True
            )
            subprocess.run(
                ['docker', 'rm', '-f', '$(docker ps -q --filter name=test_project_)'],
                shell=True,
                stderr=subprocess.PIPE,
                check=False
            )
        except (subprocess.SubprocessError, FileNotFoundError):
            # Ignore errors during cleanup
            pass

@pytest.fixture
def mock_config_file(tmp_path):
    """Create a mock configuration file for testing."""
    config_file = tmp_path / "quickscale.yaml"
    config_file.write_text(
        "project:\n"
        "  name: test_project\n"
        "  path: ./test_project\n"
        "services:\n"
        "  web:\n"
        "    image: python:3.9-slim\n"
        "    ports:\n"
        "      - '8000:8000'\n"
        "  db:\n"
        "    image: postgres:13\n"
        "    environment:\n"
        "      POSTGRES_PASSWORD: password\n"
    )
    return config_file

@pytest.fixture
def wait_for_service():
    """Return a function that waits for a service to be ready."""
    def _wait_for(check_func, timeout=SERVICE_TIMEOUT, interval=POLL_INTERVAL, message="Service"):
        """Wait for a service to be ready based on check_func returning True."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                if check_func():
                    return True
            except Exception:
                pass
            time.sleep(interval)
        
        pytest.fail(f"{message} not ready after {timeout} seconds")
    
    return _wait_for

def _cleanup_previous_instances(project_name: str) -> None:
    """Clean up any previous test instances with the same project name."""
    try:
        # Try to clean up any potential previous instances
        subprocess.run(
            ['docker', 'rm', '-f', f"{project_name}_web", f"{project_name}_db", f"{project_name}-web-1", f"{project_name}-db-1"],
            capture_output=True,
            check=False,
            timeout=30
        )
        
        # Also remove any networks
        subprocess.run(
            ['docker', 'network', 'rm', f"{project_name}_default", f"{project_name.replace('_', '-')}_default"],
            capture_output=True,
            check=False,
            timeout=10
        )
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        print(f"Cleanup of previous instances warning (safe to ignore): {e}")

def _initialize_test_project(project_name: str, tmp_path: Path) -> Optional[Path]:
    """Initialize a new QuickScale test project and return its directory."""
    try:
        print(f"\nCreating test project: {project_name} in {tmp_path}")
        build_result = subprocess.run(
            ['quickscale', 'init', project_name],
            capture_output=True, 
            text=True,
            check=False,
            timeout=180  # Increased timeout to 3 minutes
        )
        
        if build_result.returncode != 0:
            print(f"Project initialization failed: {build_result.stderr}")
            print(f"Initialization stdout: {build_result.stdout}")
            pytest.skip(f"Project initialization failed with returncode {build_result.returncode}")
            return None
            
        return tmp_path / project_name
    except subprocess.SubprocessError as e:
        print(f"Build failed with exception: {e}")
        pytest.skip(f"Build failed: {e}")
        return None

def _start_project_services(project_dir: Path, web_port: int) -> bool:
    """Start the QuickScale project services and verify they're running."""
    with chdir(project_dir):
        print(f"Starting services from project directory: {project_dir}")
        # Start services
        up_result = subprocess.run(
            ['quickscale', 'up'],
            capture_output=True,
            text=True,
            check=False,
            timeout=60
        )
        
        if up_result.returncode != 0:
            print(f"Service startup failed: {up_result.stderr}")
            print(f"Service startup stdout: {up_result.stdout}")
            return False
        
        print("Services started successfully")
        
        # Wait a bit for services to fully start
        time.sleep(5)

        # Wait for the web port to be open
        from tests.utils import wait_for_port
        
        print(f"Waiting for web service to be ready on port {web_port}...")
        web_ready = wait_for_port('127.0.0.1', web_port, timeout=60)
        
        if not web_ready:
            print(f"Web service on port {web_port} not ready after 60 seconds.")
            _get_web_container_logs(project_dir.name)
            pytest.skip(f"Web service on port {web_port} not ready.")
            return False
        
        print(f"Web service on port {web_port} is ready.")
        return True

def _get_web_container_logs(project_name: str) -> None:
    """Get and print logs from the web container."""
    print("Attempting to fetch web container logs...")
    container_logs = ""  # Placeholder
    # Try potential container names
    web_container_names = [f"{project_name}_web", f"{project_name}-web-1"]
    
    from tests.utils import get_container_logs
    for name in web_container_names:
        logs = get_container_logs(name)
        if logs:
            container_logs += f"\n--- Logs for {name} ---\n{logs}"

    if container_logs:
        print("--- START WEB CONTAINER LOGS ---")
        print(container_logs)
        print("--- END WEB CONTAINER LOGS ---")
    else:
        print("Could not retrieve web container logs.")

def _verify_containers_running(project_name: str) -> bool:
    """Verify that the required containers are running."""
    # Check if containers are running
    check_result = subprocess.run(
        ['docker', 'ps', '--format', '{{.Names}}'],
        capture_output=True,
        text=True,
        check=False,
        timeout=10
    )
    
    print(f"Docker containers after build: {check_result.stdout}")
    
    # Verify web container is running
    web_running = False
    web_container_names = [f"{project_name}_web", f"{project_name}-web-1"]
    
    for name in web_container_names:
        if name in check_result.stdout:
            web_running = True
            print(f"Found running web container: {name}")
            break
            
    if not web_running:
        print(f"Web container not running after build. Checking Docker logs...")
        # Get logs from container
        for name in web_container_names:
            try:
                log_result = subprocess.run(
                    ['docker', 'logs', name],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=10
                )
                print(f"Logs for {name}: {log_result.stdout}")
            except (subprocess.SubprocessError, FileNotFoundError):
                pass
    
    return web_running

def _cleanup_project(project_dir: Path) -> None:
    """Clean up the project directory and associated Docker resources."""
    project_name = project_dir.name
    
    if project_dir and project_dir.exists():
        with chdir(project_dir):
            try:
                # Try to stop any running containers
                print(f"Cleaning up from project directory: {project_dir}")
                subprocess.run(
                    ['quickscale', 'down'], 
                    capture_output=True,
                    check=False,
                    timeout=30
                )
            except (subprocess.SubprocessError, FileNotFoundError) as e:
                print(f"Cleanup warning (safe to ignore): {e}")
        
        # Also cleanup using Docker commands directly
        try:
            # Try to remove containers directly
            subprocess.run(
                ['docker', 'rm', '-f', f"{project_name}_web", f"{project_name}_db", f"{project_name}-web-1", f"{project_name}-db-1"],
                capture_output=True,
                check=False,
                timeout=30
            )
            
            # Also remove any networks
            subprocess.run(
                ['docker', 'network', 'rm', f"{project_name}_default", f"{project_name.replace('_', '-')}_default"],
                capture_output=True,
                check=False,
                timeout=10
            )
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            print(f"Docker cleanup warning (safe to ignore): {e}")
        
        # Remove the project directory
        try:
            shutil.rmtree(project_dir)
        except (OSError, PermissionError) as e:
            print(f"Warning: Failed to clean up {project_dir}: {e}")

@pytest.fixture(scope="module")
def real_project_fixture(tmp_path_factory):
    """Create a real QuickScale project fixture that's properly cleaned up."""
    from tests.utils import find_available_ports
    
    tmp_path = tmp_path_factory.mktemp("quickscale_real_test")
    project_dir = None
    
    with chdir(tmp_path):
        project_name = "real_test_project"
        
        # Clean up any previous instances
        _cleanup_previous_instances(project_name)
        
        # Find available ports for the web and db services
        ports = find_available_ports(count=2, start_port=8000, end_port=9000)
        if not ports:
            pytest.skip("Could not find available ports for test containers")
            yield None
            return
            
        web_port, db_port = ports
        print(f"Using web port {web_port} and database port {db_port} for tests")
        
        # Set environment variables for port configuration
        os.environ["PORT"] = str(web_port)
        os.environ["PG_PORT"] = str(db_port)
        
        # Initialize the test project
        project_dir = _initialize_test_project(project_name, tmp_path)
        if not project_dir:
            yield None
            return
            
        # Start services and verify they're running
        services_started = _start_project_services(project_dir, web_port)
        if not services_started:
            yield None
            return
            
        # Verify containers are running
        _verify_containers_running(project_name)
        
        # Yield the project directory for tests to use
        yield project_dir
        
    # Clean up after tests are done
    if project_dir:
        _cleanup_project(project_dir)

@pytest.fixture
def mock_docker():
    """Mock Docker-related functions for testing without Docker dependencies."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "mock docker output"
        yield mock_run

@pytest.fixture
def retry(request):
    """Retry a test multiple times until it passes."""
    retries = getattr(request.node, "retries", 3)
    
    def _retry_wrapper(func):
        def _wrapper(*args, **kwargs):
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == retries - 1:
                        raise
                    time.sleep(1)  # Wait between retries
        return _wrapper
    
    return _retry_wrapper

@pytest.fixture(scope="session", autouse=True)
def check_docker_dependency(request):
    """Check if Docker is available and working properly."""
    # Only run this check if we're running integration tests
    if "integration" in request.node.nodeid or "real_project_fixture" in request.fixturenames:
        from tests.utils import check_docker_health
        
        healthy, issues = check_docker_health()
        
        if not healthy:
            issues_str = "\n- ".join([""] + issues)
            print("\n\033[31m" + "=" * 80 + "\033[0m")
            print("\033[31mWARNING: Docker is not running or has issues!\033[0m")
            print(f"\033[31mDocker health check identified issues:{issues_str}\033[0m")
            print("\033[31mPlease fix Docker before running these tests.\033[0m")
            print("\033[31mTests will continue but may fail due to Docker issues.\033[0m")
            print("\033[31m" + "=" * 80 + "\033[0m\n")
            
            # Don't skip, but mark so tests can check this later
            request.config.cache.set("docker_healthy", "false")
        else:
            print("\n\033[32mDocker health check passed! Docker is running properly.\033[0m\n")
            request.config.cache.set("docker_healthy", "true")
    
    yield

@pytest.fixture(scope="session")
def docker_ready(request):
    """Return whether Docker is ready for testing."""
    docker_status = request.config.cache.get("docker_healthy", "unknown")
    if docker_status == "true":
        return True
    elif docker_status == "false":
        return False
    else:
        # If unknown, perform a quick check
        from tests.utils import is_docker_available
        return is_docker_available()

@pytest.fixture
def mock_stripe_disabled():
    """Mock environment with Stripe disabled."""
    with patch.dict(os.environ, {'STRIPE_ENABLED': 'false'}):
        yield

@pytest.fixture
def mock_stripe_enabled():
    """Mock environment with Stripe enabled."""
    with patch.dict(os.environ, {'STRIPE_ENABLED': 'true'}):
        yield

@pytest.fixture
def mock_stripe_unavailable():
    """Mock the Stripe module as unavailable."""
    with patch.dict('sys.modules', {'djstripe': None}):
        yield