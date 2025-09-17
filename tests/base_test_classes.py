"""Base test classes for common test patterns across QuickScale tests.

This module provides reusable base classes to reduce code duplication in tests,
following DRY principles.
"""
import unittest
from unittest.mock import Mock

import pytest


class CommandTestMixin:
    """Mixin for testing command initialization and basic functionality.
    
    This mixin provides common test methods for command classes that have
    standard initialization patterns.
    """
    
    def assert_command_initialized(self, command):
        """Assert that a command is properly initialized."""
        assert command is not None
        assert hasattr(command, 'logger')


class DjangoAppTestMixin:
    """Mixin for testing Django app structure and configuration.
    
    This mixin provides common test methods for Django app tests.
    """
    
    def assert_app_files_exist(self, app_path, required_files=None):
        """Assert that required Django app files exist."""
        if required_files is None:
            required_files = ['apps.py', 'models.py', 'views.py', 'urls.py', 'admin.py']
        
        for file_name in required_files:
            file_path = app_path / file_name
            assert file_path.exists(), f"{file_name} not found at {file_path}"


class TemplateTestMixin:
    """Mixin for testing template structure and content.
    
    This mixin provides common test methods for template validation.
    """
    
    def assert_template_contains(self, template_path, expected_content):
        """Assert that a template contains expected content."""
        assert template_path.exists(), f"Template not found at {template_path}"
        
        with open(template_path, 'r') as f:
            content = f.read()
        
        if isinstance(expected_content, list):
            for item in expected_content:
                assert item in content, f"Expected content '{item}' not found in template"
        else:
            assert expected_content in content, f"Expected content '{expected_content}' not found in template"


class ServiceCommandTestMixin:
    """Mixin for testing service command execution patterns.
    
    This mixin provides common test methods for service commands that follow
    similar execution patterns.
    """
    
    def assert_service_command_execution(self, mock_run, mock_project_manager, command):
        """Assert that a service command executes successfully."""
        mock_project_manager.get_project_state.return_value = {'has_project': True}
        mock_run.return_value = Mock(returncode=0)
        
        command.execute()
        
        mock_run.assert_called()


class CommandErrorHandlingTestMixin:
    """Mixin for testing common command error handling patterns.
    
    This mixin provides common test methods for commands that follow
    similar error handling patterns.
    """
    
    def assert_execute_not_in_project(self, mock_project_manager, command):
        """Assert that command exits when not in project directory."""
        mock_project_manager.return_value.is_project_directory.return_value = False
        
        with pytest.raises(SystemExit, match="5"):
            command.execute()
    
    def assert_execute_subprocess_error(self, mock_run, mock_project_manager, command):
        """Assert that command handles subprocess errors properly by exiting."""
        import subprocess
        
        mock_project_manager.return_value.is_project_directory.return_value = True
        mock_run.side_effect = subprocess.CalledProcessError(1, 'docker-compose')
        
        with pytest.raises(SystemExit, match="5"):
            command.execute()
    
    def assert_execute_file_not_found(self, mock_run, mock_project_manager, command):
        """Assert that command handles file not found errors properly by exiting."""
        
        mock_project_manager.return_value.is_project_directory.return_value = True
        mock_run.side_effect = FileNotFoundError("docker-compose not found")
        
        with pytest.raises(SystemExit, match="6"):
            command.execute()
    
    def assert_execute_keyboard_interrupt(self, mock_run, mock_project_manager, command):
        """Assert that command handles keyboard interrupts properly."""
        mock_project_manager.return_value.is_project_directory.return_value = True
        mock_run.side_effect = KeyboardInterrupt()
        
        # Should not raise exception, should handle gracefully
        command.execute()  # Should return without error


# Legacy unittest base classes for backwards compatibility
class BaseCommandTest(unittest.TestCase, CommandTestMixin):
    """Base class for unittest-based command tests."""
    
    def test_base_command_initialization(self):
        """Test command initialization."""
        if hasattr(self, 'command'):
            self.assert_command_initialized(self.command)
        else:
            self.skipTest("No command attribute set - override this test in subclass")


class BaseDjangoAppTest(unittest.TestCase, DjangoAppTestMixin):
    """Base class for unittest-based Django app tests."""
    pass


class BaseTemplateTest(unittest.TestCase, TemplateTestMixin):
    """Base class for unittest-based template tests."""
    pass
