"""Integration tests for message manager with actual CLI commands."""
import os
import logging
import pytest
from unittest.mock import patch, MagicMock
import subprocess
import tempfile
import shutil
from pathlib import Path

from quickscale.utils.message_manager import MessageManager, MessageType
from quickscale.commands.service_commands import ServiceStatusCommand, ServiceLogsCommand
from quickscale.commands.project_manager import ProjectManager


@pytest.fixture
def mock_project_exists():
    """Mock project existence check."""
    with patch('quickscale.commands.project_manager.ProjectManager.check_project_exists', return_value=True):
        with patch('pathlib.Path.is_file', return_value=True):  # For docker-compose.yml check
            yield


@pytest.fixture
def mock_subprocess_run():
    """Mock subprocess.run calls."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        yield mock_run


@pytest.fixture
def mock_stdout():
    """Fixture to capture stdout."""
    with patch('quickscale.utils.message_manager.MessageManager.print') as mock_print:
        yield mock_print


class TestMessageManagerIntegration:
    """Integration tests for message manager with CLI commands."""
    
    def test_service_status_command_with_message_manager(self, mock_project_exists, mock_subprocess_run, capfd):
        """Test ServiceStatusCommand with message manager."""
        # Setup
        with patch('quickscale.utils.message_manager.MessageManager._use_color', return_value=False):
            cmd = ServiceStatusCommand()
            
            # Execute
            cmd.execute()
            
            # Verify
            captured = capfd.readouterr()
            assert "Checking service status" in captured.out
    
    def test_service_logs_command_with_message_manager(self, mock_project_exists, mock_subprocess_run, capfd):
        """Test ServiceLogsCommand with message manager."""
        # Setup
        with patch('quickscale.utils.message_manager.MessageManager._use_color', return_value=False):
            cmd = ServiceLogsCommand()
            
            # Execute - all services
            cmd.execute()
            captured = capfd.readouterr()
            assert "Viewing logs for all services" in captured.out
            
            # Execute - specific service
            cmd.execute(service="web")
            captured = capfd.readouterr()
            assert "Viewing logs for web service" in captured.out
    
    def test_project_not_found_message(self, capfd):
        """Test project not found message with message manager."""
        # Setup
        with patch('quickscale.utils.message_manager.MessageManager._use_color', return_value=False):
            with patch('quickscale.commands.project_manager.ProjectManager.check_project_exists', return_value=False):
                cmd = ServiceStatusCommand()
                
                # Execute
                cmd.execute()
                
                # Verify
                captured = capfd.readouterr()
                assert "No active project found" in captured.out
                assert "run 'quickscale init <project_name>'" in captured.out
    
    def test_success_output_format(self, capfd):
        """Test success message format."""
        # Direct test of MessageManager
        with patch('quickscale.utils.message_manager.MessageManager._use_color', return_value=False):
            MessageManager.success("Test success message")
            
            # Verify
            captured = capfd.readouterr()
            assert "✅" in captured.out
            assert "Test success message" in captured.out
    
    def test_error_output_format(self, capfd):
        """Test error message format."""
        # Direct test of MessageManager
        with patch('quickscale.utils.message_manager.MessageManager._use_color', return_value=False):
            MessageManager.error("Test error message")
            
            # Verify
            captured = capfd.readouterr()
            assert "❌" in captured.out
            assert "Test error message" in captured.out
    
    def test_template_based_messages(self, capfd):
        """Test template-based messages."""
        # Direct test of MessageManager
        with patch('quickscale.utils.message_manager.MessageManager._use_color', return_value=False):
            MessageManager.template("project_created", MessageType.SUCCESS, project_name="test-project")
            
            # Verify
            captured = capfd.readouterr()
            assert "Project 'test-project' created successfully" in captured.out
