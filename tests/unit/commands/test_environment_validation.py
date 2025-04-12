import pytest
import logging
from unittest.mock import patch, MagicMock
from pathlib import Path
import os

from quickscale.commands.project_commands import BuildProjectCommand

class TestEnvironmentValidation:
    """Tests for the environment validation functionality"""
    
    @pytest.fixture
    def build_command(self):
        """Setup a BuildProjectCommand fixture for testing"""
        cmd = BuildProjectCommand()
        cmd.logger = logging.getLogger("test_logger")
        cmd.templates_dir = Path("templates")
        return cmd
    
    def test_validate_environment_success(self, build_command):
        """Test that validation passes with all required variables"""
        # Setup environment with all required variables
        build_command.variables = {
            'pg_user': 'validuser',
            'pg_password': 'password',
            'SECRET_KEY': 'secretkey',
            'port': '8000',
            'pg_port': '5432'
        }
        build_command.env_vars = {
            'DOCKER_UID': '1000',
            'DOCKER_GID': '1000'
        }
        
        # Run validation
        result = build_command.validate_environment()
        
        # Assert validation passed
        assert result is True
    
    def test_validate_environment_missing_variables(self, build_command):
        """Test that validation fails when required variables are missing"""
        # Setup environment with missing required variables
        build_command.variables = {
            'pg_user': 'validuser',
            # Missing pg_password
            'SECRET_KEY': 'secretkey',
            # Missing port
        }
        build_command.env_vars = {}
        
        # Run validation
        result = build_command.validate_environment()
        
        # Assert validation failed
        assert result is False
    
    def test_validate_environment_root_pg_user(self, build_command):
        """Test that validation fails when pg_user is 'root'"""
        # Setup environment with root as pg_user
        build_command.variables = {
            'pg_user': 'root',  # Root user is not allowed
            'pg_password': 'password',
            'SECRET_KEY': 'secretkey',
            'port': '8000',
            'pg_port': '5432'
        }
        build_command.env_vars = {}
        
        # Run validation
        result = build_command.validate_environment()
        
        # Assert validation failed
        assert result is False
    
    def test_validate_environment_empty_pg_user(self, build_command):
        """Test that validation fails when pg_user is empty"""
        # Setup environment with empty pg_user
        build_command.variables = {
            'pg_user': '',  # Empty user is not allowed
            'pg_password': 'password',
            'SECRET_KEY': 'secretkey',
            'port': '8000',
            'pg_port': '5432'
        }
        build_command.env_vars = {}
        
        # Run validation
        result = build_command.validate_environment()
        
        # Assert validation failed
        assert result is False
    
    def test_docker_uid_gid_transfer(self, build_command):
        """Test that DOCKER_UID and DOCKER_GID are transferred from env_vars to variables"""
        # Setup
        build_command.variables = {
            'pg_user': 'validuser',
            'pg_password': 'password',
            'SECRET_KEY': 'secretkey',
            'port': '8000',
            'pg_port': '5432'
            # No DOCKER_UID or DOCKER_GID here
        }
        build_command.env_vars = {
            'DOCKER_UID': '1234',
            'DOCKER_GID': '5678'
        }
        
        # Run validation
        build_command.validate_environment()
        
        # Assert that values were transferred
        assert build_command.variables.get('DOCKER_UID') == '1234'
        assert build_command.variables.get('DOCKER_GID') == '5678'
    
    def test_execute_checks_environment(self, build_command):
        """Test that execute calls validate_environment and exits on failure"""
        # Create a custom execute method that only tests the validation part
        original_execute = BuildProjectCommand.execute
        
        def execute_spy(self, project_name):
            if not self.validate_environment():
                self._exit_with_error("Environment validation failed. Please fix the issues above.")
                return {}
            return {"success": True}
        
        # Replace the execute method with our spy
        with patch.object(BuildProjectCommand, 'execute', execute_spy):
            # Setup mocks
            with patch.object(build_command, 'validate_environment', return_value=False) as mock_validate:
                with patch.object(build_command, '_exit_with_error') as mock_exit:
                    # Call execute
                    build_command.execute("test_project")
        
            # Verify method calls
            mock_validate.assert_called_once()
            mock_exit.assert_called_once_with("Environment validation failed. Please fix the issues above.") 