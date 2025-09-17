"""Consolidated tests for system commands.

This file consolidates all system command tests following DRY principles.
Replaces: test_system_commands.py, test_system_commands_comprehensive.py,
test_system_commands_complete.py and related duplicates.
"""
import subprocess
from unittest.mock import Mock, patch

import pytest

from quickscale.commands.system_commands import CheckCommand
from tests.base_test_classes import CommandTestMixin


class TestCheckCommand(CommandTestMixin):
    """Consolidated tests for CheckCommand."""

    def setup_method(self):
        """Set up test environment."""
        self.command = CheckCommand()

    def test_check_command_initialization(self):
        """Test CheckCommand initialization and basic functionality."""
        self.assert_command_initialized(self.command)

    @patch('shutil.which')
    def test_check_tool_available(self, mock_which):
        """Test tool availability check when tool is available."""
        mock_which.return_value = "/usr/bin/docker"
        
        result = self.command._check_tool("docker")
        assert result is True

    @patch('shutil.which')
    def test_check_tool_unavailable(self, mock_which):
        """Test tool availability check when tool is not available."""
        mock_which.return_value = None
        
        result = self.command._check_tool("docker")
        assert result is False

    @patch('shutil.which')
    @patch('subprocess.run')
    @patch('builtins.print')
    def test_check_tool_with_print_info_docker(self, mock_print, mock_run, mock_which):
        """Test tool check with print info for Docker."""
        mock_which.return_value = "/usr/bin/docker"
        mock_run.return_value = Mock(stdout="Docker version 20.10.0", returncode=0)
        
        result = self.command._check_tool("docker", print_info=True)
        assert result is True

    def test_check_docker_compose_found(self):
        """Test _check_docker_compose when found in PATH."""
        with patch('shutil.which', return_value='/usr/bin/docker-compose'), \
             patch('subprocess.run') as mock_run:
            # Mock successful version check
            mock_run.return_value.stdout = 'docker-compose version 1.29.2'
            mock_run.return_value.check_returncode.return_value = None
            
            result = self.command._check_docker_compose(print_info=True)
            
            assert result is True
            mock_run.assert_called_once()

    def test_check_docker_compose_not_found_but_compose_v2_found(self):
        """Test _check_docker_compose when docker-compose not found but docker compose v2 exists."""
        with patch('shutil.which', side_effect=[None, '/usr/bin/docker']), \
             patch('subprocess.run') as mock_run:
            # Mock successful docker compose v2 version check
            mock_run.return_value.stdout = 'Docker Compose version v2.10.0'
            
            result = self.command._check_docker_compose(print_info=True)
            
            assert result is True
            # First call should be for version check, second for printing info
            assert mock_run.call_count == 2

    def test_check_docker_compose_not_found(self):
        """Test _check_docker_compose when neither docker-compose nor docker compose v2 exist."""
        with patch('shutil.which', return_value=None):
            result = self.command._check_docker_compose()
            
            assert result is False

    @patch('subprocess.run')
    def test_check_docker_daemon_running(self, mock_run):
        """Test Docker daemon check when daemon is running."""
        mock_run.return_value = Mock(returncode=0)
        
        result = self.command._check_docker_daemon()
        assert result is True

    @patch('subprocess.run')
    def test_check_docker_daemon_not_running(self, mock_run):
        """Test Docker daemon check when daemon is not running."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "docker ps")
        
        result = self.command._check_docker_daemon()
        assert result is False

    @patch('subprocess.run')
    def test_execute_docker_daemon_not_running(self, mock_run):
        """Test execute when Docker daemon is not running."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "docker ps")
        
        with pytest.raises(SystemExit):
            self.command.execute()

    @patch('shutil.which')
    @patch('subprocess.run') 
    def test_execute_all_tools_available(self, mock_run, mock_which):
        """Test execute when all tools are available."""
        # Mock all tools as available
        mock_which.return_value = "/usr/bin/tool"
        mock_run.return_value = Mock(returncode=0, stdout="version info")
        
        # Should not raise SystemExit
        self.command.execute()

    @patch('shutil.which')
    @patch('subprocess.run')
    def test_version_output_parsing(self, mock_run, mock_which):
        """Test version output parsing for different tools."""
        mock_which.return_value = "/usr/bin/docker"
        mock_run.return_value = Mock(stdout="Docker version 20.10.0", returncode=0)
        
        result = self.command._check_tool("docker", print_info=True)
        assert result is True
        mock_run.assert_called()

    def test_error_propagation_hierarchy(self):
        """Test error propagation through command hierarchy."""
        with patch.object(self.command, '_check_docker_daemon', return_value=False):
            with pytest.raises(SystemExit):
                self.command.execute()

    @patch('quickscale.utils.message_manager.MessageManager')
    def test_message_manager_integration(self, mock_msg_manager):
        """Test integration with message manager."""
        with patch.object(self.command, '_check_docker_daemon', return_value=False):
            with pytest.raises(SystemExit):
                self.command.execute()
            mock_msg_manager.error.assert_called()

    @patch('subprocess.run')
    def test_timeout_handling(self, mock_run):
        """Test timeout handling for subprocess calls."""
        mock_run.side_effect = subprocess.TimeoutExpired("docker ps", 30)
        
        result = self.command._check_docker_daemon()
        assert result is False
