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
             patch.object(cmd, '_prepare_environment_and_ports', return_value=({}, {})), \
             patch.object(cmd, '_start_docker_services', side_effect=error), \
             patch.object(cmd, 'handle_error') as mock_handle_error:
            
            cmd.execute()
            
            # Verify error was handled
            mock_handle_error.assert_called_once()
            args, kwargs = mock_handle_error.call_args
            assert args[0] == error

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
    
    def test_port_availability_check_web_port_available(self):
        """Test port availability check when web port is available."""
        cmd = ServiceUpCommand()
        
        # Mock is_port_in_use to return False for all ports (ports are available)
        with patch.object(cmd, '_is_port_in_use', return_value=False):
            env = {'WEB_PORT': '8000', 'DB_PORT_EXTERNAL': '5432'}
            # Call the method
            updated_ports = cmd._check_port_availability(env)
            
            # No ports should be updated since all are available
            assert updated_ports == {}
    
    def test_port_availability_check_web_port_in_use(self):
        """Test port availability check when web port is in use."""
        cmd = ServiceUpCommand()
        
        # Mock port checks: web port in use, db port available
        def mock_is_port_in_use(port):
            return port == 8000  # Only web port (8000) is in use
            
        with patch.object(cmd, '_is_port_in_use', side_effect=mock_is_port_in_use):
            env = {'WEB_PORT': '8000', 'DB_PORT_EXTERNAL': '5432'}
            
            # Call should raise ServiceError
            with pytest.raises(ServiceError) as exc_info:
                cmd._check_port_availability(env)
            
            # Verify error message mentions port
            assert "Web port 8000 is already in use" in str(exc_info.value)
    
    def test_port_availability_check_db_port_in_use(self):
        """Test port availability check when DB external port is in use."""
        cmd = ServiceUpCommand()
        
        # Mock port checks: web port available, db port in use
        def mock_is_port_in_use(port):
            return port == 5432  # Only DB port (5432) is in use
            
        with patch.object(cmd, '_is_port_in_use', side_effect=mock_is_port_in_use):
            env = {'WEB_PORT': '8000', 'DB_PORT_EXTERNAL': '5432'}
            
            # Call should raise ServiceError
            with pytest.raises(ServiceError) as exc_info:
                cmd._check_port_availability(env)
            
            # Verify error message mentions port
            assert "Database port 5432 is already in use" in str(exc_info.value)
    
    def test_execute_with_port_availability_check(self):
        """Test execute method with port availability check."""
        cmd = ServiceUpCommand()
        
        # Mock successful execution
        with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                  return_value={'has_project': True}), \
             patch.object(cmd, '_prepare_environment_and_ports', return_value=({}, {})), \
             patch.object(cmd, '_start_docker_services'), \
             patch.object(cmd, '_verify_services_running'), \
             patch.object(cmd, '_print_service_info'):
            
            # Should complete successfully
            cmd.execute()
    
    def test_is_port_in_use_true(self):
        """Test port in use detection."""
        cmd = ServiceUpCommand()
        
        # Mock socket bind failure (port in use)
        with patch('socket.socket') as mock_socket:
            mock_socket.return_value.__enter__.return_value.bind.side_effect = OSError("Address already in use")
            
            assert cmd._is_port_in_use(8000) is True
    
    def test_is_port_in_use_false(self):
        """Test port not in use detection."""
        cmd = ServiceUpCommand()
        
        # Mock successful socket bind (port available)
        with patch('socket.socket') as mock_socket:
            mock_socket.return_value.__enter__.return_value.bind.return_value = None
            
            assert cmd._is_port_in_use(8000) is False
    
    @patch('quickscale.commands.project_manager.ProjectManager.get_project_state', return_value={'has_project': True})
    @patch.object(ServiceUpCommand, '_verify_services_running')
    @patch.object(ServiceUpCommand, '_print_service_info')
    def test_service_up_command_no_cache(self, mock_print_service_info, mock_verify_services_running, mock_get_project_state):
        """Test ServiceUpCommand.execute with no_cache=True."""
        cmd = ServiceUpCommand()
        
        # Mock successful execution with no_cache
        with patch.object(cmd, '_prepare_environment_and_ports', return_value=({}, {})), \
             patch.object(cmd, '_start_docker_services') as mock_start_services:
            
            cmd.execute(no_cache=True)
            
            # Verify _start_docker_services was called with no_cache=True
            mock_start_services.assert_called_once()
            call_args = mock_start_services.call_args
            assert call_args[1]['no_cache'] is True
    
    def test_service_up_command_default_cache(self):
        """Test ServiceUpCommand.execute with default cache behavior."""
        cmd = ServiceUpCommand()
        
        # Mock successful execution with default cache, but simulate missing docker-compose
        with patch.object(cmd, '_prepare_environment_and_ports', return_value=({}, {})), \
             patch.object(cmd, '_start_docker_services', side_effect=FileNotFoundError("docker-compose")):
            with pytest.raises(SystemExit):
                cmd.execute()  # Default no_cache=False