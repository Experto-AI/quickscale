"""Unit tests for development command error handling."""
import subprocess
from unittest.mock import patch, MagicMock
import pytest

from quickscale.commands.development_commands import (
    ShellCommand, ManageCommand, DjangoShellCommand
)


class TestDevelopmentCommandErrorHandling:
    """Tests for development command error handling."""
    
    def test_shell_command_error_handling(self):
        """Verify error handling in ShellCommand.execute."""
        cmd = ShellCommand()
        
        # Mock subprocess.run to raise an error
        error = subprocess.SubprocessError("Mock error")
        
        with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                  return_value={'has_project': True}), \
             patch('subprocess.run', side_effect=error), \
             patch.object(cmd, 'handle_error') as mock_handle_error:
            
            cmd.execute(command="echo test")
            
            # Verify error was handled with context
            mock_handle_error.assert_called_once()
            args, kwargs = mock_handle_error.call_args
            assert args[0] == error
            assert kwargs["context"]["command"] == "echo test"
            assert "recovery" in kwargs
    
    def test_django_shell_command_error_handling(self):
        """Verify error handling in DjangoShellCommand.execute."""
        cmd = DjangoShellCommand()
        
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
            assert kwargs["context"]["django_shell"] is True
            assert "recovery" in kwargs
    
    def test_manage_command_error_handling(self):
        """Verify error handling in ManageCommand.execute."""
        cmd = ManageCommand()
        
        # Mock subprocess.run to raise an error
        error = subprocess.SubprocessError("Mock error")
        manage_args = ["runserver", "0.0.0.0:8000"]
        
        with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                  return_value={'has_project': True}), \
             patch('subprocess.run', side_effect=error), \
             patch.object(cmd, 'handle_error') as mock_handle_error:
            
            cmd.execute(manage_args)
            
            # Verify error was handled with context
            mock_handle_error.assert_called_once()
            args, kwargs = mock_handle_error.call_args
            assert args[0] == error
            assert kwargs["context"]["manage_args"] == manage_args
            assert "recovery" in kwargs