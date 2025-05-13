"""Unit tests for system commands."""
import subprocess
import shutil
from unittest.mock import patch, MagicMock
import pytest

from quickscale.commands.system_commands import CheckCommand


class TestCheckCommand:
    """Tests for the CheckCommand class."""
    
    def test_check_docker_compose_found(self):
        """Test _check_docker_compose when found in PATH."""
        cmd = CheckCommand()
        
        with patch('shutil.which', return_value='/usr/bin/docker-compose'), \
             patch('subprocess.run') as mock_run:
            # Mock successful version check
            mock_run.return_value.stdout = 'docker-compose version 1.29.2'
            mock_run.return_value.check_returncode.return_value = None
            
            result = cmd._check_docker_compose(print_info=True)
            
            assert result is True
            mock_run.assert_called_once()
    
    def test_check_docker_compose_not_found_but_compose_v2_found(self):
        """Test _check_docker_compose when docker-compose not found but docker compose v2 exists."""
        cmd = CheckCommand()
        
        with patch('shutil.which', side_effect=[None, '/usr/bin/docker']), \
             patch('subprocess.run') as mock_run:
            # Mock successful docker compose v2 version check
            mock_run.return_value.stdout = 'Docker Compose version v2.10.0'
            
            result = cmd._check_docker_compose(print_info=True)
            
            assert result is True
            # First call should be for version check, second for printing info
            assert mock_run.call_count == 2
    
    def test_check_docker_compose_not_found(self):
        """Test _check_docker_compose when neither docker-compose nor docker compose v2 exist."""
        cmd = CheckCommand()
        
        with patch('shutil.which', return_value=None):
            result = cmd._check_docker_compose()
            
            assert result is False
    
    def test_check_docker_compose_v2_errors_on_check(self):
        """Test when docker compose v2 exists but errors on version check."""
        cmd = CheckCommand()
        
        with patch('shutil.which', side_effect=[None, '/usr/bin/docker']), \
             patch('subprocess.run', side_effect=subprocess.SubprocessError()):
            
            result = cmd._check_docker_compose()
            
            assert result is False
    
    def test_check_tool_found_docker(self):
        """Test _check_tool for Docker with successful version check."""
        cmd = CheckCommand()
        
        with patch('shutil.which', return_value='/usr/bin/docker'), \
             patch('subprocess.run') as mock_run:
            # Mock successful version check
            mock_run.return_value.stdout = 'Docker version 20.10.17'
            
            result = cmd._check_tool('docker', print_info=True)
            
            assert result is True
            mock_run.assert_called_once()
    
    def test_check_tool_found_python(self):
        """Test _check_tool for Python with successful version check."""
        cmd = CheckCommand()
        
        with patch('shutil.which', return_value='/usr/bin/python'), \
             patch('subprocess.run') as mock_run:
            # Mock successful version check
            mock_run.return_value.stdout = 'Python 3.10.6'
            
            result = cmd._check_tool('python', print_info=True)
            
            assert result is True
            mock_run.assert_called_once()
    
    def test_check_tool_found_other(self):
        """Test _check_tool for other tools without version check."""
        cmd = CheckCommand()
        
        with patch('shutil.which', return_value='/usr/bin/other-tool'), \
             patch('subprocess.run') as mock_run:
            
            result = cmd._check_tool('other-tool', print_info=True)
            
            assert result is True
            # No subprocess run calls for generic tools
            mock_run.assert_not_called()
    
    def test_check_tool_version_error(self):
        """Test _check_tool when version check fails."""
        cmd = CheckCommand()
        
        with patch('shutil.which', return_value='/usr/bin/docker'), \
             patch('subprocess.run', side_effect=subprocess.SubprocessError()), \
             patch('builtins.print') as mock_print:
            
            result = cmd._check_tool('docker', print_info=True)
            
            assert result is True
            # Should still return True if the tool exists but version check fails
            mock_print.assert_called_once()
    
    def test_check_tool_not_found(self):
        """Test _check_tool when tool doesn't exist."""
        cmd = CheckCommand()
        
        with patch('shutil.which', return_value=None):
            result = cmd._check_tool('nonexistent')
            
            assert result is False
    
    def test_check_docker_daemon_running(self):
        """Test _check_docker_daemon when daemon is running."""
        cmd = CheckCommand()
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.check_returncode.return_value = None
            
            result = cmd._check_docker_daemon(print_info=True)
            
            assert result is True
            mock_run.assert_called_once()
    
    def test_check_docker_daemon_not_running(self):
        """Test _check_docker_daemon when daemon is not running."""
        cmd = CheckCommand()
        
        with patch('subprocess.run', side_effect=subprocess.SubprocessError()):
            result = cmd._check_docker_daemon()
            
            assert result is False
    
    def test_execute_all_requirements_met(self):
        """Test execute when all requirements are met."""
        cmd = CheckCommand()
        
        with patch.object(cmd, '_check_docker_compose', return_value=True), \
             patch.object(cmd, '_check_tool', return_value=True), \
             patch.object(cmd, '_check_docker_daemon', return_value=True):
            
            # Should not raise any exceptions
            cmd.execute(print_info=True)
    
    def test_execute_missing_docker_compose(self):
        """Test execute when docker-compose is missing."""
        cmd = CheckCommand()
        
        with patch.object(cmd, '_check_docker_compose', return_value=False), \
             patch.object(cmd, '_exit_with_error') as mock_exit:
            
            cmd.execute()
            
            mock_exit.assert_called_once()
            assert "docker-compose not found" in mock_exit.call_args[0][0]
    
    def test_execute_missing_docker(self):
        """Test execute when docker is missing."""
        cmd = CheckCommand()
        
        def check_tool_side_effect(tool, *args, **kwargs):
            return tool != "docker"
        
        with patch.object(cmd, '_check_docker_compose', return_value=True), \
             patch.object(cmd, '_check_tool', side_effect=check_tool_side_effect), \
             patch.object(cmd, '_exit_with_error') as mock_exit:
            
            cmd.execute()
            
            mock_exit.assert_called_once()
            assert "docker not found" in mock_exit.call_args[0][0]
    
    def test_execute_missing_python(self):
        """Test execute when python is missing."""
        cmd = CheckCommand()
        
        def check_tool_side_effect(tool, *args, **kwargs):
            return tool != "python"
        
        with patch.object(cmd, '_check_docker_compose', return_value=True), \
             patch.object(cmd, '_check_tool', side_effect=check_tool_side_effect), \
             patch.object(cmd, '_exit_with_error') as mock_exit:
            
            cmd.execute()
            
            mock_exit.assert_called_once()
            assert "python not found" in mock_exit.call_args[0][0]
    
    def test_execute_docker_daemon_not_running(self):
        """Test execute when docker daemon is not running."""
        cmd = CheckCommand()
        
        with patch.object(cmd, '_check_docker_compose', return_value=True), \
             patch.object(cmd, '_check_tool', return_value=True), \
             patch.object(cmd, '_check_docker_daemon', return_value=False), \
             patch.object(cmd, '_exit_with_error') as mock_exit:
            
            cmd.execute()
            
            mock_exit.assert_called_once()
            assert "Docker daemon not running" in mock_exit.call_args[0][0] 