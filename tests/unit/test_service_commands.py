"""Unit tests for service command error handling."""
import os
import subprocess
from unittest.mock import patch, MagicMock
import pytest

from quickscale.commands.service_commands import (
    ServiceUpCommand, ServiceDownCommand, ServiceLogsCommand, ServiceStatusCommand
)
from quickscale.utils.error_manager import ServiceError


class TestServiceCommandErrorHandling:
    """Tests for service command error handling."""
    
    def test_service_up_command_error_handling(self):
        """Verify error handling in ServiceUpCommand.execute."""
        cmd = ServiceUpCommand()
        
        # Mock subprocess.run to raise an error
        error = subprocess.SubprocessError("Mock error")
        
        with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                  return_value={'has_project': True}), \
             patch('subprocess.run', side_effect=error), \
             patch.object(cmd, 'handle_error') as mock_handle_error:
            
            cmd.execute()
            
            # Verify error was handled with context
            mock_handle_error.assert_called_once()
            args, kwargs = mock_handle_error.call_args
            assert args[0] == error
            assert "context" in kwargs
            assert kwargs["context"]["action"] == "starting services"
    
    def test_service_down_command_error_handling(self):
        """Verify error handling in ServiceDownCommand.execute."""
        cmd = ServiceDownCommand()
        
        error = subprocess.SubprocessError("Mock error")
        
        with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                  return_value={'has_project': True}), \
             patch('subprocess.run', side_effect=error), \
             patch.object(cmd, 'handle_error') as mock_handle_error:
            
            cmd.execute()
            
            # Verify error was handled with context
            mock_handle_error.assert_called_once()
            assert "context" in mock_handle_error.call_args[1]
    
    def test_service_logs_command_error_handling(self):
        """Verify error handling in ServiceLogsCommand.execute."""
        cmd = ServiceLogsCommand()
        
        error = subprocess.SubprocessError("Mock error")
        
        with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                  return_value={'has_project': True}), \
             patch('subprocess.run', side_effect=error), \
             patch.object(cmd, 'handle_error') as mock_handle_error:
            
            cmd.execute(service="web", follow=True)
            
            # Verify error was handled with context including service and follow
            mock_handle_error.assert_called_once()
            args, kwargs = mock_handle_error.call_args
            assert args[0] == error
            assert kwargs["context"]["service"] == "web"
            assert kwargs["context"]["follow"] is True
    
    def test_service_status_command_error_handling(self):
        """Verify error handling in ServiceStatusCommand.execute."""
        cmd = ServiceStatusCommand()
        
        error = subprocess.SubprocessError("Mock error")
        
        with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                  return_value={'has_project': True}), \
             patch('subprocess.run', side_effect=error), \
             patch.object(cmd, 'handle_error') as mock_handle_error:
            
            cmd.execute()
            
            # Verify error was handled with context
            mock_handle_error.assert_called_once()
            assert "context" in mock_handle_error.call_args[1]
    
    def test_env_file_port_update_error_handling(self):
        """Verify error handling when updating port in .env file."""
        cmd = ServiceUpCommand()
        
        # Create a test environment where file operations will fail
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', side_effect=PermissionError("Permission denied")), \
             patch.object(cmd, 'handle_error') as mock_handle_error:
            
            result = cmd._update_env_file_ports()
            
            # Verify error was handled with context and without exiting
            mock_handle_error.assert_called_once()
            args, kwargs = mock_handle_error.call_args
            assert isinstance(args[0], PermissionError)
            assert kwargs["context"]["file"] == ".env"
            assert kwargs["exit_on_error"] is False
            assert result == {}