"""Comprehensive unit tests for development commands."""
import os
import subprocess
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List

from quickscale.commands.development_commands import (
    ShellCommand, ManageCommand, DjangoShellCommand
)
from quickscale.utils.error_manager import error_manager
from tests.base_test_classes import CommandTestMixin, CommandErrorHandlingTestMixin


class TestShellCommand(CommandTestMixin, CommandErrorHandlingTestMixin):
    """Tests for ShellCommand class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.command = ShellCommand()
    
    def test_initialization(self):
        """Test ShellCommand initialization."""
        self.assert_command_initialized(self.command)
    
    @patch('subprocess.run')
    @patch('quickscale.commands.development_commands.ProjectManager')
    def test_execute_interactive_shell(self, mock_project_manager, mock_run):
        """Test executing interactive shell."""
        mock_pm_instance = Mock()
        mock_project_manager.return_value = mock_pm_instance
        mock_pm_instance.is_project_directory.return_value = True
        
        mock_run.return_value = Mock(returncode=0)
        
        self.command.execute()
        
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert 'docker-compose' in args or 'docker' in str(args)
        assert 'exec' in args
        assert 'web' in args
        assert 'bash' in args
    
    @patch('subprocess.run')
    @patch('quickscale.commands.development_commands.ProjectManager')
    def test_execute_with_command(self, mock_project_manager, mock_run):
        """Test executing shell with specific command."""
        mock_pm_instance = Mock()
        mock_project_manager.return_value = mock_pm_instance
        mock_pm_instance.is_project_directory.return_value = True
        
        mock_run.return_value = Mock(returncode=0)
        
        self.command.execute(command='ls -la')
        
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert 'ls -la' in args
    
    @patch('quickscale.commands.development_commands.ProjectManager')
    def test_execute_not_in_project(self, mock_project_manager):
        """Test executing shell when not in project directory."""
        self.assert_execute_not_in_project(mock_project_manager, self.command)
    
    @patch('subprocess.run')
    @patch('quickscale.commands.development_commands.ProjectManager')
    def test_execute_subprocess_error(self, mock_project_manager, mock_run):
        """Test executing shell with subprocess error."""
        self.assert_execute_subprocess_error(mock_run, mock_project_manager, self.command)
    
    @patch('subprocess.run')
    @patch('quickscale.commands.development_commands.ProjectManager')
    def test_execute_file_not_found(self, mock_project_manager, mock_run):
        """Test executing shell when Docker is not available."""
        self.assert_execute_file_not_found(mock_run, mock_project_manager, self.command)
    
    @patch('subprocess.run')
    @patch('quickscale.commands.development_commands.ProjectManager')
    def test_execute_keyboard_interrupt(self, mock_project_manager, mock_run):
        """Test executing shell with keyboard interrupt."""
        self.assert_execute_keyboard_interrupt(mock_run, mock_project_manager, self.command)


class TestManageCommand(CommandTestMixin, CommandErrorHandlingTestMixin):
    """Tests for ManageCommand class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.command = ManageCommand()
    
    def test_initialization(self):
        """Test ManageCommand initialization."""
        self.assert_command_initialized(self.command)
    
    @patch('subprocess.run')
    @patch('quickscale.commands.development_commands.ProjectManager')
    def test_execute_migrate(self, mock_project_manager, mock_run):
        """Test executing Django migrate command."""
        mock_pm_instance = Mock()
        mock_project_manager.return_value = mock_pm_instance
        mock_pm_instance.is_project_directory.return_value = True
        
        mock_run.return_value = Mock(returncode=0)
        
        self.command.execute(['migrate'])
        
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert 'docker-compose' in args
        assert 'exec' in args
        assert 'web' in args
        assert 'python' in args
        assert 'manage.py' in args
        assert 'migrate' in args
    
    @patch('subprocess.run')
    @patch('quickscale.commands.development_commands.ProjectManager')
    def test_execute_with_multiple_args(self, mock_project_manager, mock_run):
        """Test executing Django command with multiple arguments."""
        mock_pm_instance = Mock()
        mock_project_manager.return_value = mock_pm_instance
        mock_pm_instance.is_project_directory.return_value = True
        
        mock_run.return_value = Mock(returncode=0)
        
        self.command.execute(['migrate', '--fake', 'app_name'])
        
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert 'migrate' in args
        assert '--fake' in args
        assert 'app_name' in args
    
    @patch('subprocess.run')
    @patch('quickscale.commands.development_commands.ProjectManager')
    def test_execute_empty_args(self, mock_project_manager, mock_run):
        """Test executing manage command with empty arguments."""
        mock_pm_instance = Mock()
        mock_project_manager.return_value = mock_pm_instance
        mock_pm_instance.is_project_directory.return_value = True
        
        mock_run.return_value = Mock(returncode=0)
        
        # Should exit with error when no Django command is provided
        with pytest.raises(SystemExit):
            self.command.execute([])
    
    @patch('quickscale.commands.development_commands.ProjectManager')
    def test_execute_not_in_project(self, mock_project_manager):
        """Test executing manage command when not in project directory."""
        mock_project_manager.get_project_state.return_value = {'has_project': False}
        
        with pytest.raises(SystemExit):
            self.command.execute(['migrate'])
    
    @patch('subprocess.run')
    @patch('quickscale.commands.development_commands.ProjectManager')
    def test_execute_subprocess_error(self, mock_project_manager, mock_run):
        """Test executing manage command with subprocess error."""
        mock_pm_instance = Mock()
        mock_project_manager.return_value = mock_pm_instance
        mock_pm_instance.is_project_directory.return_value = True
        
        mock_run.side_effect = subprocess.CalledProcessError(1, 'docker', stderr="Error")
        
        with pytest.raises(SystemExit):
            self.command.execute(['migrate'])
    
    @patch('subprocess.run')
    @patch('quickscale.commands.development_commands.ProjectManager')
    def test_execute_file_not_found(self, mock_project_manager, mock_run):
        """Test executing manage command when Docker is not available."""
        mock_pm_instance = Mock()
        mock_project_manager.return_value = mock_pm_instance
        mock_pm_instance.is_project_directory.return_value = True
        
        mock_run.side_effect = FileNotFoundError("docker not found")
        
        # This should be handled by the FileNotFoundError catch we added
        self.command.execute(['migrate'])
    
    @patch('subprocess.run')
    @patch('quickscale.commands.development_commands.ProjectManager')
    def test_execute_keyboard_interrupt(self, mock_project_manager, mock_run):
        """Test executing manage command with keyboard interrupt."""
        mock_pm_instance = Mock()
        mock_project_manager.return_value = mock_pm_instance
        mock_pm_instance.is_project_directory.return_value = True
        
        mock_run.side_effect = KeyboardInterrupt()
        
        # Should handle gracefully without raising
        self.command.execute(['migrate'])
        
        mock_run.assert_called_once()


class TestDjangoShellCommand(CommandTestMixin):
    """Tests for DjangoShellCommand class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.command = DjangoShellCommand()
    
    def test_initialization(self):
        """Test DjangoShellCommand initialization."""
        self.assert_command_initialized(self.command)
    
    @patch('subprocess.run')
    @patch('quickscale.commands.development_commands.ProjectManager')
    def test_execute_django_shell(self, mock_project_manager, mock_run):
        """Test executing Django shell."""
        mock_pm_instance = Mock()
        mock_project_manager.return_value = mock_pm_instance
        mock_pm_instance.is_project_directory.return_value = True
        
        mock_run.return_value = Mock(returncode=0)
        
        self.command.execute()
        
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        # DOCKER_COMPOSE_COMMAND is now a list (e.g., ['docker', 'compose'] or ['docker-compose'])
        # Check that docker-related commands are in the args
        assert any('docker' in str(arg) for arg in args), f"Expected docker-related command in {args}"
        assert 'exec' in args
        assert 'web' in args
        assert 'python' in args
        assert 'manage.py' in args
        assert 'shell' in args
    
    @patch('quickscale.commands.development_commands.ProjectManager')
    def test_execute_not_in_project(self, mock_project_manager):
        """Test executing Django shell when not in project directory."""
        mock_project_manager.get_project_state.return_value = {'has_project': False}
        
        with pytest.raises(SystemExit):
            self.command.execute()
    
    @patch('subprocess.run')
    @patch('quickscale.commands.development_commands.ProjectManager')
    def test_execute_subprocess_error(self, mock_project_manager, mock_run):
        """Test executing Django shell with subprocess error."""
        mock_pm_instance = Mock()
        mock_project_manager.return_value = mock_pm_instance
        mock_pm_instance.is_project_directory.return_value = True
        
        mock_run.side_effect = subprocess.CalledProcessError(1, 'docker', stderr="Error")
        
        with pytest.raises(SystemExit):
            self.command.execute()
    
    @patch('subprocess.run')
    @patch('quickscale.commands.development_commands.ProjectManager')
    def test_execute_file_not_found(self, mock_project_manager, mock_run):
        """Test executing Django shell when Docker is not available."""
        mock_pm_instance = Mock()
        mock_project_manager.return_value = mock_pm_instance
        mock_pm_instance.is_project_directory.return_value = True
        
        mock_run.side_effect = FileNotFoundError("docker not found")
        
        with pytest.raises(SystemExit):
            self.command.execute()
    
    @patch('subprocess.run')
    @patch('quickscale.commands.development_commands.ProjectManager')
    def test_execute_keyboard_interrupt(self, mock_project_manager, mock_run):
        """Test executing Django shell with keyboard interrupt."""
        mock_pm_instance = Mock()
        mock_project_manager.return_value = mock_pm_instance
        mock_pm_instance.is_project_directory.return_value = True
        
        mock_run.side_effect = KeyboardInterrupt()
        
        # Should handle gracefully without raising
        self.command.execute()
        
        mock_run.assert_called_once()


class TestDevelopmentCommandsIntegration:
    """Integration tests for development commands."""
    
    @patch('subprocess.run')
    @patch('quickscale.commands.development_commands.ProjectManager')
    def test_shell_vs_manage_vs_django_shell(self, mock_project_manager, mock_run):
        """Test differences between shell, manage, and django-shell commands."""
        mock_pm_instance = Mock()
        mock_project_manager.return_value = mock_pm_instance
        mock_pm_instance.is_project_directory.return_value = True
        mock_run.return_value = Mock(returncode=0)
        
        # Test shell command
        shell_cmd = ShellCommand()
        shell_cmd.execute()
        shell_args = mock_run.call_args[0][0]
        
        mock_run.reset_mock()
        
        # Test manage command
        manage_cmd = ManageCommand()
        manage_cmd.execute(['shell'])
        manage_args = mock_run.call_args[0][0]
        
        mock_run.reset_mock()
        
        # Test django-shell command
        django_shell_cmd = DjangoShellCommand()
        django_shell_cmd.execute()
        django_shell_args = mock_run.call_args[0][0]
        
        # Verify differences
        assert 'bash' in shell_args  # Regular shell uses bash
        assert 'manage.py' in manage_args  # Manage command uses manage.py
        assert 'manage.py' in django_shell_args  # Django shell also uses manage.py
        assert 'shell' in django_shell_args  # But specifically the shell command
    
    @patch('quickscale.commands.development_commands.ProjectManager')
    def test_all_commands_check_project_directory(self, mock_project_manager):
        """Test that all development commands check for project directory."""
        # Mock the get_project_state to return no project
        mock_project_manager.get_project_state.return_value = {'has_project': False}
        
        # Shell command should return early (show help) when not in project directory
        shell_command = ShellCommand()
        shell_command.execute()  # Should not raise an exception, just return early
        
        # ManageCommand and DjangoShellCommand should call sys.exit()
        commands_that_should_exit = [
            (ManageCommand(), ['migrate']),
            (DjangoShellCommand(), [])
        ]
        
        for command, args in commands_that_should_exit:
            with pytest.raises(SystemExit):
                if args:
                    command.execute(args)
                else:
                    command.execute()
    
    def test_command_error_handling_consistency(self):
        """Test that all commands handle errors consistently."""
        commands = [
            (ShellCommand(), []),
            (ManageCommand(), [['migrate']]),
            (DjangoShellCommand(), [])
        ]
        
        for command, args in commands:
            # Test that they all inherit from the same base and have consistent error handling
            assert hasattr(command, 'logger')
            assert hasattr(command, 'execute')
            assert callable(command.execute)
