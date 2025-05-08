"""End-to-end tests for Django management commands in a QuickScale project."""
import os
import subprocess
import pytest
from pathlib import Path
from contextlib import contextmanager
import time
import re

from tests.utils import (
    wait_for_docker_service,
    run_quickscale_command,
    is_docker_available,
    create_test_project_structure,
    find_available_ports
)

@pytest.mark.e2e
class TestDjangoCommands:
    """End-to-end tests for Django management commands in a QuickScale project.
    
    Tests that critical Django commands work properly in a generated project:
    1. Create a test project
    2. Start services
    3. Run Django management commands (test, check, etc.)
    4. Verify they execute without errors
    5. Clean up
    """
    
    @pytest.fixture(scope="class", autouse=True)
    def check_docker(self):
        """Check if Docker is available before running any tests."""
        is_docker_available()
    
    @pytest.fixture(scope="class")
    def test_project(self, tmp_path_factory):
        """Create a test project for e2e testing Django commands."""
        # Use class-scoped tmp_path to maintain the project across all tests
        tmp_path = tmp_path_factory.mktemp("quickscale_django_test")
        
        # Check if Docker is running - REMOVED direct docker info check
        # try:
        #     docker_check = subprocess.run(
        #         ['docker', 'info'], 
        #         capture_output=True, 
        #         check=False, 
        #         timeout=15
        #     )
        #     if docker_check.returncode != 0:
        #         pytest.skip(f"Docker is not running properly: {docker_check.stderr}")
        #         return None
        # except Exception as e:
        #     pytest.skip(f"Error checking Docker status: {e}")
        #     return None

        # Find available ports for web and db
        ports = find_available_ports(count=2, start_port=9000, end_port=10000)
        if not ports:
            pytest.skip("Could not find available ports for e2e tests")
            return None
            
        web_port, db_port = ports
        
        os.chdir(tmp_path)
        
        # Create a test project structure
        project_name = "django_test_project"
        project_dir = create_test_project_structure(tmp_path, project_name)
        
        # Create a .env file with the appropriate port settings
        env_content = f"""
            DEBUG=True
            SECRET_KEY=test_secret_key
            DATABASE_URL=postgresql://postgres:password@db:5432/postgres
            PORT={web_port}
            PG_PORT={db_port}
            WEB_PORT={web_port}
            DB_PORT_EXTERNAL={db_port}
            WEB_PORT_ALTERNATIVE_FALLBACK=yes
            DB_PORT_EXTERNAL_ALTERNATIVE_FALLBACK=yes
        """
        (project_dir / ".env").write_text(env_content)
        
        # Update docker-compose.yml with appropriate ports
        dc_path = project_dir / "docker-compose.yml"
        dc_content = dc_path.read_text()
        dc_content = dc_content.replace("8000:8000", f"{web_port}:8000")
        dc_content = dc_content.replace("5432:5432", f"{db_port}:5432")
        dc_path.write_text(dc_content)
        
        # Try to validate docker-compose configuration - REMOVED direct docker-compose config check
        # with self.in_project_dir(project_dir):
        #     try:
        #         validate_result = subprocess.run(
        #             ['docker-compose', 'config'], 
        #             capture_output=True, 
        #             text=True, 
        #             check=False, 
        #             timeout=10
        #         )
        #         if validate_result.returncode != 0:
        #             print(f"Docker Compose validation failed: {validate_result.stderr}")
        #             print("This might cause issues with service startup")
        #     except Exception as e:
        #         print(f"Error validating docker-compose.yml: {e}")
        
        # Try to start services
        with self.in_project_dir(project_dir):
            print(f"Starting services for project: {project_name} with ports web={web_port}, db={db_port}")
            
            # First make sure any previous services are stopped
            try:
                down_result = run_quickscale_command('down', timeout=30, check=False)
                if down_result.returncode != 0:
                    print(f"Warning: Pre-startup cleanup failed: {down_result.stderr}")
            except Exception as e:
                print(f"Error during pre-startup cleanup: {e}")
            
            # Attempt to start services once and assert success
            try:
                print(f"Starting services...")
                # Use check=True to fail immediately if 'up' command fails
                result = run_quickscale_command('up', ['-d'], timeout=180, check=True)
                print("Services started successfully via 'quickscale up'.")
            except Exception as e:
                # If 'up' fails, fail the fixture setup
                pytest.fail(f"Failed to start services with 'quickscale up': {e}")

            # Check if services are running using quickscale ps and assert
            try:
                print("Checking if services are running using quickscale ps...")
                # Wait a bit for services to initialize completely
                print("Waiting for services to initialize...")
                time.sleep(15)
                
                ps_result = run_quickscale_command('ps', check=True, timeout=10)
                ps_output = ps_result.stdout
                
                # Assert that key services are running
                assert re.search(r'web.*(Up|running)', ps_output, re.IGNORECASE), \
                    f"Web service not found or not running in 'quickscale ps' output:\n{ps_output}"
                assert re.search(r'db.*(Up|running)', ps_output, re.IGNORECASE), \
                    f"DB service not found or not running in 'quickscale ps' output:\n{ps_output}"
                print(f"Services for {project_name} confirmed running via 'quickscale ps'.")

            except Exception as e:
                # If 'ps' check fails, fail the fixture setup
                pytest.fail(f"Failed to verify running services with 'quickscale ps': {e}")
        
        yield {
            "dir": project_dir,
            "name": project_name,
            "web_port": web_port,
            "db_port": db_port
        }
        
        # Clean up after tests (keep check=False for cleanup)
        with self.in_project_dir(project_dir):
            print("Cleaning up test project...")
            run_quickscale_command('down', timeout=30, check=False)
    
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
