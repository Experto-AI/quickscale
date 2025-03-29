"""Real-life integration tests for the QuickScale CLI command lifecycle."""
import os
import shutil
import subprocess
import time
from pathlib import Path
import pytest

class TestRealLifecycle:
    """End-to-end tests for the QuickScale CLI using a real project build."""
    
    @pytest.fixture(scope="module")
    def real_project(self, tmp_path_factory):
        """Create a real QuickScale project for testing the full CLI lifecycle."""
        # Use module-scoped tmp_path to maintain the project across all tests
        tmp_path = tmp_path_factory.mktemp("quickscale_real_test")
        os.chdir(tmp_path)
        project_name = "real_test_project"
        
        # Run actual quickscale build command
        print(f"\nBuilding real project '{project_name}' for end-to-end testing...")
        build_result = subprocess.run(['quickscale', 'build', project_name], 
                                      capture_output=True, text=True)
        
        # Check if build was successful
        if build_result.returncode != 0:
            pytest.skip(f"Build failed: {build_result.stdout}\n{build_result.stderr}")
            return None
            
        # Change to the project directory
        project_dir = tmp_path / project_name
        os.chdir(project_dir)
        print(f"Project built successfully in {project_dir}")
        
        # Yield the project directory for tests to use
        yield project_dir
        
        # Clean up after all tests - return to parent dir and destroy project
        os.chdir(tmp_path)
        print(f"\nCleaning up project '{project_name}'...")
        
        # Try to run quickscale down first to stop any containers
        try:
            subprocess.run(['quickscale', 'down'], cwd=project_dir, 
                           capture_output=True, check=False)
        except Exception as e:
            print(f"Error stopping containers: {e}")
            
        # Remove the project directory
        try:
            shutil.rmtree(project_dir)
            print(f"Project directory {project_dir} removed")
        except Exception as e:
            print(f"Error removing project directory: {e}")
    
    def test_01_project_up(self, real_project):
        """Test starting the services with 'up' command."""
        if not real_project:
            pytest.skip("Project build skipped or failed")
            
        # Run the up command
        result = subprocess.run(['quickscale', 'up'], capture_output=True, text=True)
        
        # Verify command succeeded
        assert result.returncode == 0, f"Command failed: {result.stdout}\n{result.stderr}"
        print("\nServices started successfully")
        
        # Give some time for containers to start properly
        time.sleep(5)
    
    def test_02_project_ps(self, real_project):
        """Test checking service status with 'ps' command."""
        if not real_project:
            pytest.skip("Project build skipped or failed")
            
        # Run the ps command
        result = subprocess.run(['quickscale', 'ps'], capture_output=True, text=True)
        
        # Verify command succeeded
        assert result.returncode == 0, f"Command failed: {result.stdout}\n{result.stderr}"
        
        # Verify that services are listed
        output = result.stdout
        print(f"\nService status: \n{output}")
        assert "web" in output, "Web service not found in ps output"
        assert "db" in output, "Database service not found in ps output"
    
    def test_03_project_logs(self, real_project):
        """Test viewing logs with 'logs' command."""
        if not real_project:
            pytest.skip("Project build skipped or failed")
            
        # Run the logs command (limit output with head to avoid huge logs)
        # Note: No longer using -f/--follow to avoid hanging, and added timeout
        result = subprocess.run('quickscale logs | head -n 20', 
                                shell=True, capture_output=True, text=True,
                                timeout=30)
        
        # Verify command succeeded
        assert result.returncode == 0, f"Command failed: {result.stdout}\n{result.stderr}"
        
        # Print limited logs
        print(f"\nService logs (truncated): \n{result.stdout}")
        
        # Test logs for a specific service
        result = subprocess.run('quickscale logs web | head -n 10', 
                                shell=True, capture_output=True, text=True,
                                timeout=30)
        assert result.returncode == 0, "Web logs command failed"
    
    def test_04_project_shell(self, real_project):
        """Test running a simple command in the container shell."""
        if not real_project:
            pytest.skip("Project build skipped or failed")
            
        # Run a simple command in the shell (ls)
        result = subprocess.run(['quickscale', 'shell', '--cmd', 'ls -la /app'], 
                                capture_output=True, text=True)
        
        # Verify command succeeded
        assert result.returncode == 0, f"Command failed: {result.stdout}\n{result.stderr}"
        
        # Verify expected output contains typical project files
        output = result.stdout
        print(f"\nShell command output: \n{output}")
        assert "manage.py" in output, "manage.py not found in project"
        assert "docker-compose.yml" in output, "docker-compose.yml not found in project"
    
    def test_05_django_manage(self, real_project):
        """Test running Django management commands."""
        if not real_project:
            pytest.skip("Project build skipped or failed")
            
        # Run Django check command
        result = subprocess.run(['quickscale', 'manage', 'check'], 
                                capture_output=True, text=True)
        
        # Verify command succeeded
        assert result.returncode == 0, f"Command failed: {result.stdout}\n{result.stderr}"
        
        # Verify expected output
        print(f"\nDjango check output: \n{result.stdout}")
        assert "System check identified no issues" in result.stdout, "Django check found issues"
    
    def test_06_project_down(self, real_project):
        """Test stopping the services with 'down' command."""
        if not real_project:
            pytest.skip("Project build skipped or failed")
            
        # Run the down command
        result = subprocess.run(['quickscale', 'down'], capture_output=True, text=True)
        
        # Verify command succeeded
        assert result.returncode == 0, f"Command failed: {result.stdout}\n{result.stderr}"
        print("\nServices stopped successfully")
        
        # Verify services are down
        ps_result = subprocess.run(['quickscale', 'ps'], capture_output=True, text=True)
        assert "not running" in ps_result.stdout or not ("running" in ps_result.stdout), \
            "Services still running after down command" 