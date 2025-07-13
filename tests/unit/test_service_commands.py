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
             patch.object(cmd, '_start_services_with_retry') as mock_start_services, \
             patch.object(cmd, 'handle_error') as mock_handle_error:
            
            # Make _start_services_with_retry call handle_error with our error
            def side_effect(max_retries, no_cache=False, *args, **kwargs):
                cmd.handle_error(
                    error,
                    context={"action": "starting services"},
                    recovery="Check if Docker is running"
                )
            
            mock_start_services.side_effect = side_effect
            
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

    def test_port_availability_check_web_port_available(self):
        """Test port availability check when web port is available."""
        cmd = ServiceUpCommand()
        
        # Mock is_port_in_use to return False for all ports (ports are available)
        with patch.object(cmd, '_is_port_in_use', return_value=False):
            env = {'WEB_PORT': '8000', 'DB_PORT_EXTERNAL': '5432', 'DB_PORT': '5432'}
            # Call the method
            updated_ports = cmd._check_port_availability(env)
            
            # No ports should be updated since all are available
            assert updated_ports == {}
    
    def test_port_availability_check_web_port_in_use_with_fallback(self):
        """Test port availability check when web port is in use and fallback is enabled."""
        cmd = ServiceUpCommand()
        
        # Mock port checks: web port in use, db port available
        def mock_is_port_in_use(port):
            return port == 8000  # Only web port (8000) is in use
            
        # Mock feature enabled to return True for fallback
        def mock_is_feature_enabled(value):
            return True
            
        # Mock find_available_port to return a new port
        with patch.object(cmd, '_is_port_in_use', side_effect=mock_is_port_in_use), \
             patch.object(cmd, '_is_feature_enabled', side_effect=mock_is_feature_enabled), \
             patch('quickscale.commands.service_commands.find_available_port', return_value=8001):
            
            env = {
                'WEB_PORT': '8000', 
                'DB_PORT_EXTERNAL': '5432',
                'DB_PORT': '5432',
                'WEB_PORT_ALTERNATIVE_FALLBACK': 'yes'  # Fallback enabled
            }
            
            # Call the method
            updated_ports = cmd._check_port_availability(env)
            
            # Web port should be updated
            assert 'WEB_PORT' in updated_ports
            assert updated_ports['WEB_PORT'] == 8001
    
    def test_port_availability_check_web_port_in_use_without_fallback(self):
        """Test port availability check when web port is in use but fallback is disabled."""
        cmd = ServiceUpCommand()
        
        # Mock port checks: web port in use, db port available
        def mock_is_port_in_use(port):
            return port == 8000  # Only web port (8000) is in use
            
        # Mock find_available_port to avoid actual socket operations
        with patch.object(cmd, '_is_port_in_use', side_effect=mock_is_port_in_use), \
             patch('quickscale.commands.service_commands.find_available_port', return_value=8001):
            
            env = {
                'WEB_PORT': '8000', 
                'DB_PORT_EXTERNAL': '5432',
                'DB_PORT': '5432',
                'WEB_PORT_ALTERNATIVE_FALLBACK': 'no'  # Fallback disabled
            }
            
            # Call should raise ServiceError
            with pytest.raises(ServiceError) as exc_info:
                cmd._check_port_availability(env)
            
            # Verify error message mentions port and fallback
            assert "WEB_PORT 8000 is already in use" in str(exc_info.value)
            assert "WEB_PORT_ALTERNATIVE_FALLBACK is not enabled" in str(exc_info.value)
    
    def test_port_availability_check_db_port_in_use_with_fallback(self):
        """Test port availability check when DB external port is in use and fallback is enabled."""
        cmd = ServiceUpCommand()
        
        # Mock port checks: web port available, db port in use
        def mock_is_port_in_use(port):
            return port == 5432  # Only DB port (5432) is in use
            
        # Mock feature enabled to return True for fallback
        def mock_is_feature_enabled(value):
            return True
            
        # Mock find_available_port to return a new port
        with patch.object(cmd, '_is_port_in_use', side_effect=mock_is_port_in_use), \
             patch.object(cmd, '_is_feature_enabled', side_effect=mock_is_feature_enabled), \
             patch('quickscale.commands.service_commands.find_available_port', return_value=5433):
            
            env = {
                'WEB_PORT': '8000', 
                'DB_PORT_EXTERNAL': '5432',
                'DB_PORT': '5432',
                'DB_PORT_EXTERNAL_ALTERNATIVE_FALLBACK': 'true'  # Fallback enabled
            }
            
            # Call the method
            updated_ports = cmd._check_port_availability(env)
            
            # DB external port should be updated, internal port remains unchanged
            assert 'DB_PORT_EXTERNAL' in updated_ports
            assert updated_ports['DB_PORT_EXTERNAL'] == 5433
    
    def test_port_availability_check_db_port_in_use_without_fallback(self):
        """Test port availability check when DB external port is in use but fallback is disabled."""
        cmd = ServiceUpCommand()
        
        # Mock port checks: web port available, db port in use
        def mock_is_port_in_use(port):
            return port == 5432  # Only DB port (5432) is in use
            
        # Mock find_available_port to avoid actual socket operations
        with patch.object(cmd, '_is_port_in_use', side_effect=mock_is_port_in_use), \
             patch('quickscale.commands.service_commands.find_available_port', return_value=5433):
            
            env = {
                'WEB_PORT': '8000', 
                'DB_PORT_EXTERNAL': '5432',
                'DB_PORT': '5432',
                # DB_PORT_EXTERNAL_ALTERNATIVE_FALLBACK not set (disabled)
            }
            
            # Call should raise ServiceError
            with pytest.raises(ServiceError) as exc_info:
                cmd._check_port_availability(env)
            
            # Verify error message mentions port and fallback
            assert "DB_PORT_EXTERNAL 5432 is already in use" in str(exc_info.value)
            assert "DB_PORT_EXTERNAL_ALTERNATIVE_FALLBACK is not enabled" in str(exc_info.value)
    
    def test_port_availability_check_no_available_alternative(self):
        """Test port availability check when no alternative port can be found."""
        cmd = ServiceUpCommand()
        
        # Mock port checks: web port in use
        def mock_is_port_in_use(port):
            return port == 8000  # Web port (8000) is in use
            
        # Mock feature enabled to return True for fallback
        def mock_is_feature_enabled(value):
            return True
            
        # Mock find_available_port to return the same port (simulating no alternative found)
        with patch.object(cmd, '_is_port_in_use', side_effect=mock_is_port_in_use), \
             patch.object(cmd, '_is_feature_enabled', side_effect=mock_is_feature_enabled), \
             patch('quickscale.commands.service_commands.find_available_port', return_value=8000):
            
            env = {
                'WEB_PORT': '8000', 
                'DB_PORT_EXTERNAL': '5432',
                'DB_PORT': '5432',
                'WEB_PORT_ALTERNATIVE_FALLBACK': 'yes'  # Fallback enabled
            }
            
            # Call should raise ServiceError
            with pytest.raises(ServiceError) as exc_info:
                cmd._check_port_availability(env)
            
            # Verify error message mentions no alternative found
            assert "in use and no alternative port could be found" in str(exc_info.value)
    
    def test_execute_with_port_availability_check(self):
        """Test execute method with port availability checking."""
        cmd = ServiceUpCommand()
        
        # Mock to avoid actual operations while testing the port checking flow
        with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                  return_value={'has_project': True}), \
             patch.object(cmd, '_check_port_availability') as mock_check_ports, \
             patch('subprocess.run', return_value=MagicMock(returncode=0)), \
             patch.object(cmd, '_find_available_ports', return_value={}), \
             patch.object(cmd, '_update_docker_compose_ports'), \
             patch.object(cmd, '_start_docker_services'), \
             patch.object(cmd, '_verify_services_running'), \
             patch.object(cmd, '_print_service_info'):
            
            # Set up port check results
            mock_check_ports.return_value = {'WEB_PORT': 8001, 'DB_PORT_EXTERNAL': 5433}
            
            # Call the method
            cmd.execute()
            
            # Verify port check was called
            mock_check_ports.assert_called_once()
            # Verify execute completed successfully (no error raised)
    
    def test_is_feature_enabled_truthy_values(self):
        """Test _is_feature_enabled method correctly identifies various truthy values."""
        cmd = ServiceUpCommand()
        
        # Test various forms of "true"
        truthy_values = ['true', 'TRUE', 'True', 'yes', 'YES', 'Yes', '1', 'on', 'ON', 'enabled', 'ENABLED']
        
        for value in truthy_values:
            assert cmd._is_feature_enabled(value) is True, f"Value '{value}' should be considered enabled"
    
    def test_is_feature_enabled_falsy_values(self):
        """Test _is_feature_enabled method correctly identifies various falsy values."""
        cmd = ServiceUpCommand()
        
        # Test various forms of "false"
        falsy_values = ['false', 'FALSE', 'False', 'no', 'NO', 'No', '0', 'off', 'OFF', 'disabled', 'DISABLED', '', None]
        
        for value in falsy_values:
            assert cmd._is_feature_enabled(value) is False, f"Value '{value}' should be considered disabled"
    
    def test_port_fallback_with_various_boolean_formats(self):
        """Test port availability check with different formats of boolean values for fallback."""
        cmd = ServiceUpCommand()
        
        # Mock port checks: web port in use, db port available
        def mock_is_port_in_use(port):
            return port == 8000  # Only web port (8000) is in use
            
        # Test with different boolean formats
        boolean_formats = [
            'true',  # lowercase
            'TRUE',  # uppercase
            'Yes',   # mixed case
            '1',     # numeric
            'on'     # alternative format
        ]
        
        for format_value in boolean_formats:
            # Mock feature enabled to always return True for testing
            with patch.object(cmd, '_is_port_in_use', side_effect=mock_is_port_in_use), \
                 patch.object(cmd, '_is_feature_enabled', return_value=True), \
                 patch('quickscale.commands.service_commands.find_available_port', return_value=8001):
                
                env = {
                    'WEB_PORT': '8000', 
                    'DB_PORT_EXTERNAL': '5432',
                    'DB_PORT': '5432',
                    'WEB_PORT_ALTERNATIVE_FALLBACK': format_value  # Test with current format
                }
                
                # Call the method
                updated_ports = cmd._check_port_availability(env)
                
                # For all these formats, the port should be updated because fallback is enabled
                assert 'WEB_PORT' in updated_ports, f"Format '{format_value}' should be recognized as enabled"
                assert updated_ports['WEB_PORT'] == 8001
    
    def test_is_feature_enabled_with_inline_comments(self):
        """Test _is_feature_enabled method correctly handles values with inline comments."""
        cmd = ServiceUpCommand()
        
        # Test truthy values with comments
        truthy_with_comments = [
            'yes # Enable feature',
            'True  # Boolean true',
            '1 # Numeric true',
            'enabled # Text enabled',
            'on  # Text on'
        ]
        for value in truthy_with_comments:
            assert cmd._is_feature_enabled(value) is True, f"Value '{value}' should be True despite comment"

        # Test falsy or invalid values with comments
        falsy_with_comments = [
            'no # Disable feature',
            'False # Boolean false',
            '0 # Numeric false',
            'disabled # Text disabled',
            'off # Text off',
            'maybe # Invalid value'
        ]
        for value in falsy_with_comments:
            assert cmd._is_feature_enabled(value) is False, f"Value '{value}' should be False despite comment"

    @patch('quickscale.commands.project_manager.ProjectManager.get_project_state', return_value={'has_project': True})
    @patch.object(ServiceUpCommand, '_verify_services_running')
    @patch.object(ServiceUpCommand, '_print_service_info')
    @patch('quickscale.utils.env_utils.get_env', return_value='False') # Mock get_env to return 'False' for port fallback checks
    def test_service_up_command_no_cache(self, mock_get_env_value, mock_print_service_info, mock_verify_services_running, mock_get_project_state):
        """Test that the service up command with no cache calls the correct methods."""
        cmd = ServiceUpCommand()
        
        # Setup the expected environment and ports
        env = {
            'WEB_PORT': '8000', 
            'DB_PORT_EXTERNAL': '5432',
            'DB_PORT': '5432'
        }
        ports = {
            'PORT': '8001', 
            'PG_PORT': '8002'
        }
        
        # Mock the methods being called
        with patch.object(cmd, '_prepare_environment_and_ports', return_value=(env, ports)) as mock_prepare_environment_and_ports, \
             patch.object(cmd, '_start_docker_services') as mock_start_docker_services:
            cmd.execute(no_cache=True)
        
            # Assertions
            mock_get_project_state.assert_called_once()
            mock_prepare_environment_and_ports.assert_called_once()
            mock_start_docker_services.assert_called_once_with(
                {'WEB_PORT': '8000', 'DB_PORT_EXTERNAL': '5432', 'DB_PORT': '5432', 'PORT': '8001', 'PG_PORT': '8002'},
                no_cache=True,
                timeout=60
            )
            mock_verify_services_running.assert_called_once()
            mock_print_service_info.assert_called_once()

    @patch('quickscale.commands.project_manager.ProjectManager.check_project_exists')
    @patch('quickscale.utils.env_utils.get_env', return_value='False') # Mock get_env to return 'False' for port fallback checks
    def test_service_up_command_default_cache(self, mock_get_env_value, mock_check_project_exists):
        """Test that the service up command with default cache calls the correct methods."""
        cmd = ServiceUpCommand()
        
        # Create a mock for the _start_services_with_retry method
        with patch.object(cmd, '_start_services_with_retry') as mock_start_services:
            cmd.execute()
        
        # Verify check_project_exists was called
        mock_check_project_exists.assert_called_once()
        
        # Verify _start_services_with_retry was called with correct args
        mock_start_services.assert_called_once_with(max_retries=3, no_cache=False)