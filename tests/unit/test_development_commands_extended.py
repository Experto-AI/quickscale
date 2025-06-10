"""Extended unit tests for development commands, focusing on the least-covered code."""
import sys
import subprocess
from unittest.mock import patch, MagicMock, call
import pytest

from quickscale.commands.development_commands import (
    ShellCommand, ManageCommand, DjangoShellCommand
)
from quickscale.commands.project_manager import ProjectManager


class TestShellCommandExtended:
    """Extended tests for ShellCommand focusing on methods with less coverage."""
    
    def test_shell_command_without_project(self):
        """Test ShellCommand.execute when no project exists."""
        cmd = ShellCommand()
        
        with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                  return_value={'has_project': False}), \
             patch('builtins.print') as mock_print:
            
            cmd.execute()
            
            # Verify help was printed
            assert mock_print.call_count >= 3
            mock_print.assert_any_call("usage: quickscale shell [options]")
    
    def test_shell_command_help_mode(self):
        """Test ShellCommand.execute in help mode."""
        cmd = ShellCommand()
        
        with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                  return_value={'has_project': True}), \
             patch('builtins.print') as mock_print:
            
            cmd.execute(command='--help')
            
            # Verify help was printed
            assert mock_print.call_count >= 3
            mock_print.assert_any_call("usage: quickscale shell [options]")
    
    def test_shell_command_success(self):
        """Test ShellCommand.execute successfully running bash."""
        cmd = ShellCommand()
        
        with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                  return_value={'has_project': True}), \
             patch('subprocess.run', return_value=MagicMock(returncode=0)) as mock_run, \
             patch('builtins.print') as mock_print:
            
            cmd.execute()
            
            # Verify subprocess.run was called correctly
            mock_print.assert_called_with("Starting bash shell...")
            mock_run.assert_called_once()
            args, kwargs = mock_run.call_args
            assert "bash" in args[0]
            assert kwargs["check"] is True
    
    def test_shell_command_with_command_success(self):
        """Test ShellCommand.execute successfully running a specific command."""
        cmd = ShellCommand()
        test_command = "ls -la"
        
        with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                  return_value={'has_project': True}), \
             patch('subprocess.run', return_value=MagicMock(returncode=0)) as mock_run, \
             patch('builtins.print') as mock_print:
            
            cmd.execute(command=test_command)
            
            # Verify subprocess.run was called correctly
            mock_print.assert_called_with(f"Running command: {test_command}")
            mock_run.assert_called_once()
            args, kwargs = mock_run.call_args
            assert "bash" in args[0]
            assert test_command in args[0]
            assert kwargs["check"] is True
    
    def test_shell_command_keyboard_interrupt(self):
        """Test ShellCommand handling keyboard interrupt gracefully."""
        cmd = ShellCommand()
        
        with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                  return_value={'has_project': True}), \
             patch('subprocess.run', side_effect=KeyboardInterrupt()), \
             patch('builtins.print') as mock_print:
            
            cmd.execute()
            
            # Verify proper exit message
            mock_print.assert_any_call("\nExited shell.")


class TestDjangoShellCommandExtended:
    """Extended tests for DjangoShellCommand."""
    
    def test_django_shell_command_help_mode(self):
        """Test DjangoShellCommand.execute in help mode."""
        cmd = DjangoShellCommand()
        
        with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                  return_value={'has_project': False}), \
             patch('builtins.print') as mock_print:
            
            cmd.execute()
            
            # Verify django shell help was printed
            assert mock_print.call_count >= 2
            mock_print.assert_any_call("usage: quickscale django-shell")
    
    def test_django_shell_command_success(self):
        """Test DjangoShellCommand.execute successfully running Django shell."""
        cmd = DjangoShellCommand()
        
        with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                  return_value={'has_project': True}), \
             patch('subprocess.run', return_value=MagicMock(returncode=0)) as mock_run, \
             patch('builtins.print') as mock_print:
            
            cmd.execute()
            
            # Verify subprocess.run was called correctly
            mock_print.assert_called_with("Starting Django shell...")
            mock_run.assert_called_once()
            args, kwargs = mock_run.call_args
            assert "python" in args[0]
            assert "manage.py" in args[0]
            assert "shell" in args[0]
            assert kwargs["check"] is True

    def test_django_shell_command_keyboard_interrupt(self):
        """Test DjangoShellCommand handling keyboard interrupt gracefully."""
        cmd = DjangoShellCommand()
        
        with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                  return_value={'has_project': True}), \
             patch('subprocess.run', side_effect=KeyboardInterrupt()), \
             patch('builtins.print') as mock_print:
            
            cmd.execute()
            
            # Verify proper exit message
            mock_print.assert_any_call("\nExited Django shell.")


class TestManageCommandExtended:
    """Extended tests for ManageCommand focusing on methods with less coverage."""
    
    def test_manage_command_without_project(self):
        """Test ManageCommand.execute when no project exists."""
        cmd = ManageCommand()
        PROJECT_NOT_FOUND_MESSAGE = "No QuickScale project found in the current directory"
        
        # Using pytest.raises to catch SystemExit
        with pytest.raises(SystemExit):
            with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                      return_value={'has_project': False}), \
                 patch('quickscale.commands.project_manager.ProjectManager.PROJECT_NOT_FOUND_MESSAGE', 
                      PROJECT_NOT_FOUND_MESSAGE), \
                 patch('builtins.print') as mock_print:
                
                # The function will call sys.exit so we use pytest.raises
                cmd.execute(["runserver"])
                
                # Verify error message was printed
                assert mock_print.call_count >= 2
                # Check expected message
                mock_print.assert_any_call(f"Error: {PROJECT_NOT_FOUND_MESSAGE}")
    
    def test_manage_command_no_args(self):
        """Test ManageCommand.execute with no Django command arguments."""
        cmd = ManageCommand()
        
        with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                  return_value={'has_project': True}), \
             patch('builtins.print') as mock_print, \
             patch('sys.exit', side_effect=SystemExit) as mock_exit:
            
            # Using pytest.raises to catch the SystemExit that would be raised
            with pytest.raises(SystemExit):
                cmd.execute([])
            
            # Verify error message was printed
            assert mock_print.call_count >= 1
            mock_print.assert_any_call("Error: No Django management command specified")
            # Verify sys.exit was called
            mock_exit.assert_called_once_with(1)
    
    def test_manage_command_success(self):
        """Test ManageCommand.execute successfully running a Django command."""
        cmd = ManageCommand()
        test_args = ["runserver", "0.0.0.0:8000"]
        
        with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                  return_value={'has_project': True}), \
             patch('subprocess.run', return_value=MagicMock(returncode=0)) as mock_run:
            
            cmd.execute(test_args)
            
            # Verify subprocess.run was called correctly
            mock_run.assert_called_once()
            args, kwargs = mock_run.call_args
            assert "python" in args[0]
            assert "manage.py" in args[0]
            assert args[0] + test_args == args[0] + ["runserver", "0.0.0.0:8000"]
            assert kwargs["check"] is True 