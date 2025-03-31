"""Real-life integration tests for the QuickScale CLI command lifecycle."""
import os
import shutil
import subprocess
import time
import pytest
from pathlib import Path
from contextlib import contextmanager

from tests.utils import (
    wait_for_docker_service,
    wait_for_port,
    wait_for_container_health,
    get_container_logs,
    run_quickscale_command,
    is_docker_available
)

# Instead of skipping tests when Docker isn't available,
# let tests run but they'll fail with better error messages

class TestRealLifecycle:
    """End-to-end tests for the QuickScale CLI using a real project build."""
    
    @pytest.fixture(scope="module", autouse=True)
    def check_docker(self):
        """Check if Docker is available before running any tests."""
        # is_docker_available now prints a warning but always returns True
        is_docker_available()
    
    @pytest.fixture(scope="module")
    def real_project(self, tmp_path_factory, real_project_fixture, docker_ready):
        """Use the global real project fixture."""
        if not docker_ready:
            pytest.fail(
                "Docker is not available or not running properly! "
                "All integration tests will fail until Docker is fixed. "
                "Please start Docker service and try again."
            )
        
        if not real_project_fixture:
            pytest.fail("Project build failed - check Docker is running and properly configured")
        return real_project_fixture
    
    @contextmanager
    def in_project_dir(self, project_dir):
        """Context manager to temporarily change directory to the project directory."""
        old_dir = os.getcwd()
        try:
            os.chdir(project_dir)
            print(f"Changed directory to: {os.getcwd()}")
            yield
        finally:
            os.chdir(old_dir)
    
    @pytest.mark.order(1)
    def test_01_project_up(self, real_project):
        """Test starting the services with 'up' command."""
        # Change to project directory before running commands
        with self.in_project_dir(real_project):
            # Run the up command with proper timeout
            result = run_quickscale_command('up', timeout=120)
            
            # Verify command succeeded
            assert result.returncode == 0, f"Command failed: {result.stdout}\n{result.stderr}"
            print("\nServices started successfully")
            
            # Wait for web service to be running using dynamic waiting
            project_name = real_project.name
            
            # Handle both naming conventions: underscores (Docker Compose v1) and hyphens (Docker Compose v2)
            web_container = f"{project_name}_web"
            web_container_alt = f"{project_name}-web-1"
            
            # Check if Docker service is running, try both container naming patterns
            success = wait_for_docker_service(web_container, timeout=30)
            if not success:
                # Try alternative name format
                success = wait_for_docker_service(web_container_alt, timeout=30)
            
            if not success:
                # Get and print container logs to help debugging
                container_names = [web_container, web_container_alt]
                for container_name in container_names:
                    try:
                        logs = get_container_logs(container_name)
                        print(f"Logs for {container_name}:\n{logs[:500]}")  # Print first 500 chars
                    except:
                        print(f"Failed to get logs for {container_name}")
                
                pytest.fail(
                    f"Docker container {web_container} or {web_container_alt} failed to start. "
                    "Ensure Docker daemon is running and properly configured."
                )
            
            # Check if port is available, with a clear error message
            if not wait_for_port('localhost', 8000, timeout=10):
                pytest.fail(
                    f"Web service port 8000 is not accessible. "
                    "Check for port conflicts or Docker network issues."
                )
    
    @pytest.mark.order(2)  
    def test_02_project_ps(self, real_project):
        """Test checking service status with 'ps' command."""
        # Change to project directory before running commands
        with self.in_project_dir(real_project):
            # Dynamic wait for the service to be ready
            project_name = real_project.name
            
            # Handle both naming conventions
            web_container = f"{project_name}_web"
            web_container_alt = f"{project_name}-web-1"
            db_container = f"{project_name}_db"
            db_container_alt = f"{project_name}-db-1"
            
            # Ensure services are running with better failure messages
            web_running = wait_for_docker_service(web_container, timeout=10)
            if not web_running:
                web_running = wait_for_docker_service(web_container_alt, timeout=10)
            
            if not web_running:
                container_names = [web_container, web_container_alt]
                for container_name in container_names:
                    try:
                        logs = get_container_logs(container_name)
                        print(f"Logs for {container_name}:\n{logs[:500]}")
                    except:
                        pass
                
                pytest.fail(
                    f"Web service container {web_container} or {web_container_alt} is not running. "
                    "Docker may not be running properly or the container failed to start."
                )
            
            db_running = wait_for_docker_service(db_container, timeout=10)
            if not db_running:
                db_running = wait_for_docker_service(db_container_alt, timeout=10)
            
            if not db_running:
                pytest.fail(
                    f"Database service container {db_container} or {db_container_alt} is not running. "
                    "Docker may not be running properly or the container failed to start."
                )
            
            # Run the ps command
            result = run_quickscale_command('ps')
            
            # Verify command succeeded
            assert result.returncode == 0, f"Command failed: {result.stdout}\n{result.stderr}"
            
            # Verify that services are listed
            output = result.stdout
            print(f"\nService status: \n{output}")
            assert "web" in output, "Web service not found in ps output"
            assert "db" in output, "Database service not found in ps output"
            
            # Check for either "running" or "up" status (depending on Docker Compose version)
            assert any(status in output.lower() for status in ["running", "up"]), \
                "Services should be reported as running (status should contain 'running' or 'up')"
    
    @pytest.mark.order(3)
    def test_03_project_logs(self, real_project):
        """Test viewing logs with 'logs' command."""
        # Change to project directory before running commands
        with self.in_project_dir(real_project):
            # Ensure container is ready
            project_name = real_project.name
            
            # Handle both naming conventions
            web_container = f"{project_name}_web"
            web_container_alt = f"{project_name}-web-1"
            
            # Check if Docker container is running with clear error message if not
            web_running = wait_for_docker_service(web_container, timeout=10)
            if not web_running:
                web_running = wait_for_docker_service(web_container_alt, timeout=10)
            
            if not web_running:
                pytest.fail(
                    f"Web service container {web_container} or {web_container_alt} is not running. "
                    "Cannot get logs from a non-running container."
                )
                
            # Run the logs command with a timeout to avoid hanging
            try:
                result = run_quickscale_command('logs', timeout=30)
                
                # Verify command succeeded
                assert result.returncode == 0, f"Command failed: {result.stdout}\n{result.stderr}"
                
                # Print limited logs
                log_lines = result.stdout.splitlines()[:20] if result.stdout else []
                print(f"\nService logs (truncated): \n" + "\n".join(log_lines))
                
                # Test logs for a specific service
                service_result = run_quickscale_command('logs', ['web'], timeout=30)
                assert service_result.returncode == 0, "Web logs command failed"
                assert len(service_result.stdout) > 0, "No logs were returned for web service"
                
            except TimeoutError:
                pytest.fail("Logs command timed out - check Docker performance or resource constraints")
    
    @pytest.mark.order(4)
    def test_04_project_shell(self, real_project):
        """Test running a simple command in the container shell."""
        # Change to project directory before running commands
        with self.in_project_dir(real_project):
            # Ensure container is ready
            project_name = real_project.name
            
            # Handle both naming conventions
            web_container = f"{project_name}_web"
            web_container_alt = f"{project_name}-web-1"
            
            # Check if Docker container is running with clear error message
            web_running = wait_for_docker_service(web_container, timeout=10)
            if not web_running:
                web_running = wait_for_docker_service(web_container_alt, timeout=10)
            
            if not web_running:
                pytest.fail(
                    f"Web service container {web_container} or {web_container_alt} is not running. "
                    "Cannot execute shell commands in a non-running container."
                )
                
            # Run a simple command in the shell (ls)
            result = run_quickscale_command('shell', ['--cmd', 'ls -la /app'])
            
            # Verify command succeeded
            assert result.returncode == 0, f"Command failed: {result.stdout}\n{result.stderr}"
            
            # Verify expected output contains typical project files
            output = result.stdout
            print(f"\nShell command output: \n{output}")
            
            # Check for expected files
            if "manage.py" not in output:
                pytest.fail("manage.py not found in project - container may be misconfigured")
            
            # Try another simple command to verify shell functionality
            result = run_quickscale_command('shell', ['--cmd', 'pwd'])
            assert result.returncode == 0, "Shell pwd command failed"
            assert "/app" in result.stdout, "Shell is not in the expected directory"
    
    @pytest.mark.order(5)
    def test_05_django_manage(self, real_project):
        """Test running Django management commands."""
        # Change to project directory before running commands
        with self.in_project_dir(real_project):
            # Ensure container is ready
            project_name = real_project.name
            
            # Handle both naming conventions
            web_container = f"{project_name}_web"
            web_container_alt = f"{project_name}-web-1"
            
            # Check if Docker container is running with clear error message
            web_running = wait_for_docker_service(web_container, timeout=10)
            if not web_running:
                web_running = wait_for_docker_service(web_container_alt, timeout=10)
            
            if not web_running:
                pytest.fail(
                    f"Web service container {web_container} or {web_container_alt} is not running. "
                    "Cannot run Django management commands in a non-running container."
                )
                
            # Run Django check command
            result = run_quickscale_command('manage', ['check'])
            
            # Verify command succeeded with better diagnostics
            if result.returncode != 0:
                pytest.fail(
                    f"Django check command failed: {result.stderr}\n"
                    "This could indicate a Django configuration issue or database connectivity problem."
                )
                
            print(f"\nDjango check output: \n{result.stdout}")
            
            # Test another manage command
            result = run_quickscale_command('manage', ['--help'], timeout=30)
            if result.returncode != 0:
                pytest.fail(
                    f"Django help command failed: {result.stderr}\n"
                    "This could indicate a Django installation issue in the container."
                )
    
    @pytest.mark.order(6)
    def test_06_project_down(self, real_project):
        """Test stopping the services with 'down' command."""
        # Change to project directory before running commands
        with self.in_project_dir(real_project):
            # Run the down command with a reasonable timeout
            result = run_quickscale_command('down', timeout=60)
            
            # Verify command succeeded
            assert result.returncode == 0, (
                f"Down command failed: {result.stdout}\n{result.stderr}\n"
                "This could indicate issues with Docker service or permissions."
            )
            print("\nServices stopped successfully")
            
            # Verify services are down - wait briefly to ensure Docker has time to stop containers
            time.sleep(2)
            
            # Try to verify containers are actually stopped
            project_name = real_project.name
            
            # Handle both naming conventions
            web_container = f"{project_name}_web"
            web_container_alt = f"{project_name}-web-1"
            db_container = f"{project_name}_db"
            db_container_alt = f"{project_name}-db-1"
            
            # Check if the docker service is still running (it shouldn't be)
            web_running = wait_for_docker_service(web_container, timeout=5, interval=1)
            if not web_running:
                web_running = wait_for_docker_service(web_container_alt, timeout=5, interval=1)
            
            db_running = wait_for_docker_service(db_container, timeout=5, interval=1)
            if not db_running:
                db_running = wait_for_docker_service(db_container_alt, timeout=5, interval=1)
            
            if web_running:
                pytest.fail(f"Web service {web_container} or {web_container_alt} is still running after down command")
            if db_running:
                pytest.fail(f"DB service {db_container} or {db_container_alt} is still running after down command")
            
            # Also check with the quickscale ps command
            ps_result = run_quickscale_command('ps')
            if not ("not running" in ps_result.stdout.lower() or 
                    not ("running" in ps_result.stdout.lower()) or
                    "no containers" in ps_result.stdout.lower()):
                pytest.fail(
                    "Services still shown as running after down command according to ps output:\n"
                    f"{ps_result.stdout}"
                ) 