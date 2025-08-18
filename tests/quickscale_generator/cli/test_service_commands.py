"""Consolidated tests for service commands.

This file consolidates all service command tests following DRY principles.
Replaces: test_service_commands_comprehensive.py, test_service_commands_complete.py,
test_service_up_command.py and related duplicates.
"""
import os
import pytest
import subprocess
import socket
from unittest.mock import Mock, patch, mock_open
from pathlib import Path

from quickscale.commands.service_commands import (
    ServiceUpCommand, ServiceDownCommand, ServiceLogsCommand,
    handle_service_error
)
from quickscale.utils.error_manager import error_manager
from tests.base_test_classes import ServiceCommandTestMixin


def mock_open_env_file():
    """Mock env file content for testing."""
    return mock_open(read_data="PG_PORT=5432\nPORT=8000\nOTHER=value")


class TestHandleServiceError:
    """Tests for handle_service_error function."""
    
    def test_handle_service_error(self):
        """Test handle_service_error function."""
        error = subprocess.CalledProcessError(1, "docker compose up")
        
        with pytest.raises(SystemExit):
            handle_service_error(error, "testing")


class TestServiceUpCommand(ServiceCommandTestMixin):
    """Consolidated tests for ServiceUpCommand."""

    def setup_method(self):
        """Set up test environment."""
        self.command = ServiceUpCommand()

    def test_extract_port_values_defaults(self):
        """Test extracting port values with defaults."""
        env_content = "OTHER=value"
        pg_port, web_port = self.command._extract_port_values(env_content)
        assert pg_port == 5432
        assert web_port == 8000

    def test_is_port_in_use_true(self):
        """Test port checking when port is in use."""
        with patch('socket.socket') as mock_socket:
            mock_sock = Mock()
            mock_socket.return_value.__enter__.return_value = mock_sock
            mock_sock.bind.side_effect = OSError("Port in use")
            
            result = self.command._is_port_in_use(8000)
            assert result is True

    def test_is_port_in_use_false(self):
        """Test port checking when port is free."""
        with patch('socket.socket') as mock_socket:
            mock_sock = Mock()
            mock_socket.return_value.__enter__.return_value = mock_sock
            mock_sock.bind.return_value = None  # Port is free
            
            result = self.command._is_port_in_use(8000)
            assert result is False

    @patch('quickscale.commands.service_commands.ProjectManager')
    def test_prepare_environment_and_ports_success(self, mock_project_manager):
        """Test successful environment and port preparation."""
        mock_project_manager.get_project_state.return_value = {'has_project': True}
        
        with patch.object(self.command, '_check_port_availability', return_value={}):
            env, updated_ports = self.command._prepare_environment_and_ports()
            assert isinstance(env, dict)
            assert isinstance(updated_ports, dict)

    @patch('subprocess.run')
    def test_start_docker_services_success(self, mock_run):
        """Test successful Docker service startup."""
        mock_run.return_value = Mock(returncode=0)
        
        env = {}
        self.command._start_docker_services(env)
        
        mock_run.assert_called()

    @patch('subprocess.run')
    def test_verify_services_running_success(self, mock_run):
        """Test successful service verification."""
        mock_run.return_value = Mock(returncode=0, stdout="web\ndb\n")
        
        env = {}
        self.command._verify_services_running(env)

    def test_print_service_info_success(self):
        """Test service info printing."""
        with patch('quickscale.utils.message_manager.MessageManager') as mock_msg:
            updated_ports = {'PORT': '8000'}
            elapsed_time = 45.0
            self.command._print_service_info(updated_ports, elapsed_time)
            mock_msg.info.assert_called()


class TestServiceDownCommand(ServiceCommandTestMixin):
    """Consolidated tests for ServiceDownCommand."""

    def setup_method(self):
        """Set up test environment."""
        self.command = ServiceDownCommand()

    @patch('quickscale.commands.service_commands.ProjectManager')
    @patch('subprocess.run')
    def test_execute_success(self, mock_run, mock_project_manager):
        """Test successful service shutdown."""
        self.assert_service_command_execution(mock_run, mock_project_manager, self.command)


class TestServiceLogsCommand(ServiceCommandTestMixin):
    """Consolidated tests for ServiceLogsCommand."""

    def setup_method(self):
        """Set up test environment."""
        self.command = ServiceLogsCommand()

    @patch('quickscale.commands.service_commands.ProjectManager')
    @patch('subprocess.run')
    def test_execute_success(self, mock_run, mock_project_manager):
        """Test successful logs display."""
        self.assert_service_command_execution(mock_run, mock_project_manager, self.command)

    @patch('quickscale.commands.service_commands.ProjectManager')
    @patch('subprocess.run')
    def test_execute_with_follow(self, mock_run, mock_project_manager):
        """Test execution with follow parameter."""
        mock_project_manager.get_project_state.return_value = {'has_project': True}
        mock_run.return_value = Mock(returncode=0)
        
        self.command.execute(follow=True)
        
        args, kwargs = mock_run.call_args
        assert '-f' in args[0]

    @patch('quickscale.commands.service_commands.ProjectManager')
    @patch('subprocess.run')
    def test_execute_with_since(self, mock_run, mock_project_manager):
        """Test execution with since parameter."""
        mock_project_manager.get_project_state.return_value = {'has_project': True}
        mock_run.return_value = Mock(returncode=0)
        
        self.command.execute(since="1h")
        
        args, kwargs = mock_run.call_args
        assert '--since' in args[0]
        assert '1h' in args[0]

    @patch('quickscale.commands.service_commands.ProjectManager')
    @patch('subprocess.run')
    def test_execute_with_timestamps(self, mock_run, mock_project_manager):
        """Test execution with timestamps flag."""
        mock_project_manager.get_project_state.return_value = {'has_project': True}
        mock_run.return_value = Mock(returncode=0)
        
        self.command.execute(timestamps=True)
        
        args, kwargs = mock_run.call_args
        assert '-t' in args[0]
