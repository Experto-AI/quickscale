import os
import pytest
import logging
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path

from quickscale.commands.project_commands import BuildProjectCommand

class TestBuildProjectCommand:
    
    @pytest.fixture
    def build_command(self):
        cmd = BuildProjectCommand()
        cmd.logger = logging.getLogger("test_logger")
        cmd.current_uid = 1000
        cmd.current_gid = 1000
        cmd.port = 8000
        cmd.pg_port = 5432
        cmd.templates_dir = Path("templates")
        return cmd
    
    def test_validate_environment_success(self, build_command):
        # Setup successful environment
        build_command.variables = {
            'pg_user': 'validuser',
            'pg_password': 'password',
            'SECRET_KEY': 'secret',
            'port': '8000',
            'pg_port': '5432',
            'DOCKER_UID': '1000',
            'DOCKER_GID': '1000'
        }
        build_command.env_vars = {
            'DOCKER_UID': '1000',
            'DOCKER_GID': '1000'
        }
        
        # Run validation
        result = build_command.validate_environment()
        
        # Assert validation passed
        assert result is True
    
    def test_validate_environment_missing_required_vars(self, build_command):
        # Setup environment with missing required variables
        build_command.variables = {
            'pg_user': 'validuser',
            # Missing pg_password
            'SECRET_KEY': 'secret',
            # Missing port
            'pg_port': '5432'
        }
        build_command.env_vars = {}
        
        # Run validation
        result = build_command.validate_environment()
        
        # Assert validation failed
        assert result is False
    
    def test_validate_environment_root_pg_user(self, build_command):
        # Setup environment with root as pg_user
        build_command.variables = {
            'pg_user': 'root',
            'pg_password': 'password',
            'SECRET_KEY': 'secret',
            'port': '8000',
            'pg_port': '5432',
        }
        build_command.env_vars = {}
        
        # Run validation
        result = build_command.validate_environment()
        
        # Assert validation failed due to root user
        assert result is False
    
    @patch('quickscale.commands.project_commands.wait_for_postgres')
    def test_verify_database_connectivity_validates_pg_user(self, mock_wait, build_command):
        # Setup
        build_command.variables = {
            'pg_user': 'root',
            'pg_password': 'password'
        }
        mock_wait.return_value = False
        
        # Run verification
        result = build_command._verify_database_connectivity("test_project")
        
        # Assert
        assert result is False
        # Should fail validation before attempting connection
        mock_wait.assert_not_called()
    
    @patch('subprocess.run')
    def test_script_validates_db_config(self, mock_run, build_command):
        # Setup
        build_command.variables = {
            'pg_user': 'validuser',
            'pg_password': 'password'
        }
        mock_process = MagicMock()
        mock_process.stdout = "All migrations applied"
        mock_process.returncode = 0
        mock_run.return_value = mock_process
        
        # Execute the _verify_migrations method
        build_command._verify_migrations()
        
        # Verify that subprocess.run was called with the showmigrations command
        mock_run.assert_called()
        # Check that the first call contains the showmigrations command
        assert "showmigrations" in str(mock_run.call_args_list[0]) 