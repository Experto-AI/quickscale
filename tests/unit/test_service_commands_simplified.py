"""Simplified unit tests for service commands without retry logic."""
import os
import subprocess
from unittest.mock import patch, MagicMock
import pytest

from quickscale.commands.service_commands import ServiceUpCommand
from quickscale.utils.error_manager import ServiceError, CommandError


class TestServiceUpCommandSimplified:
    """Simplified tests for service startup without retry logic."""
    
    def test_port_validation_success(self):
        """Test successful port validation."""
        cmd = ServiceUpCommand()
        
        # Mock port availability check to return success
        with patch.object(cmd, '_is_port_in_use', return_value=False):
            result = cmd._check_port_availability({'WEB_PORT': '8000', 'DB_PORT_EXTERNAL': '5432'})
            
            # Should return empty dict when ports are available
            assert result == {}
    
    def test_port_validation_web_port_failure(self):
        """Test port validation failure for web port with clear error."""
        cmd = ServiceUpCommand()
        
        # Mock web port as in use
        with patch.object(cmd, '_is_port_in_use', side_effect=[True, False]):
            with pytest.raises(ServiceError, match="Web port 8000 is already in use"):
                cmd._check_port_availability({'WEB_PORT': '8000', 'DB_PORT_EXTERNAL': '5432'})
    
    def test_port_validation_db_port_failure(self):
        """Test port validation failure for database port with clear error."""
        cmd = ServiceUpCommand()
        
        # Mock database port as in use
        with patch.object(cmd, '_is_port_in_use', side_effect=[False, True]):
            with pytest.raises(ServiceError, match="Database port 5432 is already in use"):
                cmd._check_port_availability({'WEB_PORT': '8000', 'DB_PORT_EXTERNAL': '5432'})
    
    def test_docker_startup_success(self):
        """Test successful Docker service startup."""
        cmd = ServiceUpCommand()
        
        # Mock successful Docker startup
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            
            # Should not raise any exception
            cmd._start_docker_services({'WEB_PORT': '8000'})
            
            # Verify docker-compose up was called
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert 'up' in call_args
            assert '--build' in call_args
            assert '-d' in call_args
    
    def test_docker_startup_failure(self):
        """Test Docker startup failure with clear error message."""
        cmd = ServiceUpCommand()
        
        # Mock Docker startup failure
        error = subprocess.CalledProcessError(1, "docker-compose up")
        error.stdout = b"Error output"
        error.stderr = b"Error details"
        
        with patch('subprocess.run', side_effect=error):
            with pytest.raises(ServiceError, match="Docker services failed to start"):
                cmd._start_docker_services({'WEB_PORT': '8000'})
    
    def test_docker_startup_timeout(self):
        """Test Docker startup timeout handling."""
        cmd = ServiceUpCommand()
        
        # Mock timeout
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired("docker-compose up", 60)):
            with pytest.raises(ServiceError, match="Docker services startup timed out"):
                cmd._start_docker_services({'WEB_PORT': '8000'})
    
    def test_service_verification_success(self):
        """Test successful service verification."""
        cmd = ServiceUpCommand()
        
        # Mock successful service verification
        mock_result = MagicMock()
        mock_result.stdout = "db  Up"
        mock_result.returncode = 0
        
        with patch('subprocess.run', return_value=mock_result):
            # Should not raise any exception
            cmd._verify_services_running({'WEB_PORT': '8000'})
    
    def test_service_verification_missing_db(self):
        """Test service verification when database is not running."""
        cmd = ServiceUpCommand()
        
        # Mock service verification without database
        mock_result = MagicMock()
        mock_result.stdout = "web  Up"  # No db service
        mock_result.returncode = 0
        
        with patch('subprocess.run', return_value=mock_result):
            # Should log warning but not raise exception
            with patch.object(cmd.logger, 'warning') as mock_warning:
                cmd._verify_services_running({'WEB_PORT': '8000'})
                mock_warning.assert_called()
    
    def test_execute_success(self):
        """Test successful service startup execution."""
        cmd = ServiceUpCommand()
        
        # Mock all components for success
        with patch.object(cmd, '_prepare_environment_and_ports', return_value=({}, {})), \
             patch.object(cmd, '_start_docker_services'), \
             patch.object(cmd, '_verify_services_running'), \
             patch.object(cmd, '_print_service_info'):
            
            # Should complete successfully
            cmd.execute()
    
    def test_execute_port_validation_failure(self):
        """Test execution failure due to port validation."""
        cmd = ServiceUpCommand()
        
        # Mock port validation failure
        with patch.object(cmd, '_prepare_environment_and_ports', 
                         side_effect=ServiceError("Port error", recovery="Fix ports")):
            
            # Should raise SystemExit due to handle_command_error
            with pytest.raises(SystemExit):
                cmd.execute()
    
    def test_execute_docker_failure(self):
        """Test execution failure due to Docker startup failure."""
        cmd = ServiceUpCommand()
        
        # Mock Docker startup failure
        with patch.object(cmd, '_prepare_environment_and_ports', return_value=({}, {})), \
             patch.object(cmd, '_start_docker_services', 
                         side_effect=ServiceError("Docker failed", recovery="Check Docker")):
            
            # Should raise SystemExit due to handle_command_error
            with pytest.raises(SystemExit):
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
    
    def test_prepare_environment_and_ports_success(self):
        """Test successful environment preparation."""
        cmd = ServiceUpCommand()
        
        # Mock successful port validation
        with patch.object(cmd, '_check_port_availability', return_value={}):
            env, updated_ports = cmd._prepare_environment_and_ports()
            
            assert isinstance(env, dict)
            assert isinstance(updated_ports, dict)
    
    def test_prepare_environment_and_ports_failure(self):
        """Test environment preparation failure."""
        cmd = ServiceUpCommand()
        
        # Mock port validation failure
        with patch.object(cmd, '_check_port_availability', 
                         side_effect=ServiceError("Port error", recovery="Fix ports")):
            
            with pytest.raises(ServiceError, match="Port error"):
                cmd._prepare_environment_and_ports() 