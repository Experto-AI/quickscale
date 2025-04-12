import os
import pytest
import logging
import subprocess
from unittest.mock import patch, MagicMock, call

from quickscale.commands.project_commands import BuildProjectCommand

class TestMigrationVerification:
    
    @pytest.fixture
    def build_command(self):
        cmd = BuildProjectCommand()
        cmd.logger = logging.getLogger("test_logger")
        return cmd
    
    @patch('subprocess.run')
    def test_verify_migrations_all_applied(self, mock_run):
        # Setup subprocess.run to return successful migration state
        process_mock = MagicMock()
        process_mock.stdout = "[X] 0001_initial\n[X] 0002_user_fields\n"
        process_mock.returncode = 0
        mock_run.return_value = process_mock
        
        # Execute verification
        build_command = BuildProjectCommand()
        build_command.logger = logging.getLogger("test_logger")
        build_command._verify_migrations()
        
        # Assert subprocess was called with correct command
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "showmigrations" in call_args
        
        # Should not attempt any additional migrations since all are applied
        assert mock_run.call_count == 1
    
    @patch('subprocess.run')
    def test_verify_migrations_pending(self, mock_run):
        # Setup first call to show pending migrations
        process1 = MagicMock()
        process1.stdout = "[X] 0001_initial\n[ ] 0002_user_fields\n"
        process1.returncode = 0
        
        # Setup second call (check) to indicate model changes
        process2 = MagicMock()
        process2.stdout = "Your models in app(s) users have changes"
        process2.returncode = 1
        
        # Setup remaining calls for app-specific migrations
        process_success = MagicMock()
        process_success.stdout = "OK"
        process_success.returncode = 0
        
        # Set return values for successive calls - ensure we have enough mocks for all call attempts
        # Mock at least 10 calls to cover all the app-specific migrations
        all_mocks = [process1, process2] + [process_success] * 10
        mock_run.side_effect = all_mocks
        
        # Execute verification
        build_command = BuildProjectCommand()
        build_command.logger = logging.getLogger("test_logger")
        build_command._verify_migrations()
        
        # Assert
        # Verify the first two calls
        assert mock_run.call_count >= 2
        calls = mock_run.call_args_list
        assert "showmigrations" in str(calls[0])
        assert "check" in str(calls[1])
    
    @patch('subprocess.run')
    def test_verify_migrations_error_handling(self, mock_run):
        # Setup mock to raise a SubprocessError (which is actually handled)
        mock_run.side_effect = subprocess.SubprocessError("Migration command failed")
        
        # Execute verification - should not raise exception
        build_command = BuildProjectCommand()
        build_command.logger = logging.getLogger("test_logger")
        
        # The method should handle the SubprocessError without raising
        build_command._verify_migrations()
        
        # If we got here, the test passes
        # Assert that mock_run was called
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_verify_migrations_timeout(self, mock_run):
        # Setup subprocess to raise timeout for the first call only
        mock_run.side_effect = [subprocess.TimeoutExpired(cmd="test", timeout=30)]
        
        # Execute verification - should not raise exception
        build_command = BuildProjectCommand()
        build_command.logger = logging.getLogger("test_logger")
        build_command._verify_migrations()
        
        # Assert that the method was called and handled the exception
        mock_run.assert_called_once() 