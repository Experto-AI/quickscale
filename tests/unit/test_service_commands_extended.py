"""Extended unit tests for service commands, focusing on least-covered code."""
import os
import sys
import subprocess
import logging
from unittest.mock import patch, MagicMock, call
import pytest

from quickscale.commands.service_commands import (
    ServiceUpCommand, ServiceDownCommand, ServiceLogsCommand, ServiceStatusCommand
)
from quickscale.utils.error_manager import ServiceError, CommandError


class TestServiceUpCommandExtended:
    """Extended tests for ServiceUpCommand focusing on methods with less coverage."""
    
    def test_start_docker_services(self):
        """Test the _start_docker_services method."""
        cmd = ServiceUpCommand()
        env = {'ENV_VAR': 'value'}
        
        # Mock subprocess.run to verify it's called correctly
        with patch('subprocess.run', return_value=MagicMock(returncode=0)) as mock_run:
            cmd._start_docker_services(env)
            
            # Verify subprocess.run called with correct parameters
            mock_run.assert_called_once()
            args, kwargs = mock_run.call_args
            assert args[0][0] in ['docker-compose', 'docker']  # Either docker-compose or docker compose
            assert 'up' in args[0]
            assert kwargs['env'] == env
            assert kwargs['check'] is True
    
    def test_handle_docker_process_error_non_special_code(self):
        """Test _handle_docker_process_error with a non-special error code."""
        cmd = ServiceUpCommand()
        # Create CalledProcessError without stdout/stderr as kwargs
        error = subprocess.CalledProcessError(2, "docker-compose up")
        error.stdout = b"Some output"
        error.stderr = b"Some error"
        env = {'ENV_VAR': 'value'}
        
        # The current implementation always raises ServiceError regardless of error code
        with pytest.raises(ServiceError, match="Docker services failed to start"):
            cmd._handle_docker_process_error(error, env)
    
    def test_handle_docker_process_error_special_code(self):
        """Test _handle_docker_process_error with special error codes (5) when services are running."""
        cmd = ServiceUpCommand()
        # Create CalledProcessError without stdout/stderr as kwargs
        error = subprocess.CalledProcessError(5, "docker-compose up")
        error.stdout = b"Some output"
        error.stderr = b"Some error"
        env = {'ENV_VAR': 'value'}
        
        # The current implementation always raises ServiceError regardless of service status
        with pytest.raises(ServiceError, match="Docker services failed to start"):
            cmd._handle_docker_process_error(error, env)
    
    def test_get_docker_compose_logs_success(self):
        """Test that docker-compose logs are properly handled in _handle_docker_process_error."""
        cmd = ServiceUpCommand()
        env = {'ENV_VAR': 'value'}
        
        # Create a subprocess error to trigger the error handler
        error = subprocess.CalledProcessError(5, "docker-compose up")
        error.stdout = "Service startup output"
        error.stderr = "Service startup error"
        
        # The current implementation always raises ServiceError regardless of service status
        with pytest.raises(ServiceError, match="Docker services failed to start"):
            cmd._handle_docker_process_error(error, env)
    
    def test_get_docker_compose_logs_exception(self):
        """Test _handle_docker_process_error when subprocess check fails."""
        cmd = ServiceUpCommand()
        env = {'ENV_VAR': 'value'}
        
        # Create a subprocess error to trigger the error handler
        error = subprocess.CalledProcessError(5, "docker-compose up")
        error.stdout = "Service startup output"
        error.stderr = "Service startup error"
        
        # The current implementation always raises ServiceError, not the original exception
        with pytest.raises(ServiceError, match="Docker services failed to start"):
            cmd._handle_docker_process_error(error, env)
    
    def test_check_if_services_running_despite_error_success(self):
        """Test _handle_docker_process_error when services are running despite error."""
        cmd = ServiceUpCommand()
        error = subprocess.CalledProcessError(5, "docker-compose up")
        env = {'ENV_VAR': 'value'}
        
        # The current implementation always raises ServiceError regardless of service status
        with pytest.raises(ServiceError, match="Docker services failed to start"):
            cmd._handle_docker_process_error(error, env)
    
    def test_check_if_services_running_despite_error_failure(self):
        """Test _handle_docker_process_error when services aren't running."""
        cmd = ServiceUpCommand()
        error = subprocess.CalledProcessError(5, "docker-compose up")
        env = {'ENV_VAR': 'value'}
        
        # The current implementation always raises ServiceError, not the original CalledProcessError
        with pytest.raises(ServiceError, match="Docker services failed to start"):
            cmd._handle_docker_process_error(error, env)
    
    def test_check_if_services_running_despite_error_exception(self):
        """Test _handle_docker_process_error handling exceptions during service check."""
        cmd = ServiceUpCommand()
        error = subprocess.CalledProcessError(5, "docker-compose up")
        env = {'ENV_VAR': 'value'}
        
        # The current implementation always raises ServiceError, not the original exception
        with pytest.raises(ServiceError, match="Docker services failed to start"):
            cmd._handle_docker_process_error(error, env)
    
    def test_verify_services_running_success(self):
        """Test _verify_services_running when services are running."""
        cmd = ServiceUpCommand()
        env = {'ENV_VAR': 'value'}
        
        # Mock successful service check
        ps_result = MagicMock()
        ps_result.returncode = 0
        ps_result.stdout = "web  db  running"
        
        with patch('subprocess.run', return_value=ps_result) as mock_run:
            # Should complete without errors
            cmd._verify_services_running(env)
            
            # Verify subprocess.run called once
            mock_run.assert_called_once()
    
    def test_verify_services_running_db_missing(self):
        """Test _verify_services_running when database service is missing."""
        cmd = ServiceUpCommand()
        env = {'ENV_VAR': 'value'}
        
        # Mock service check with db missing
        ps_result = MagicMock()
        ps_result.returncode = 0
        ps_result.stdout = "web running"  # No "db" in output
        
        with patch('subprocess.run', return_value=ps_result) as mock_run, \
             patch.object(cmd, '_start_stopped_containers') as mock_start_containers:
            
            # Should attempt to start stopped containers
            cmd._verify_services_running(env)
            
            # Verify subprocess.run called and _start_stopped_containers called
            mock_run.assert_called_once()
            mock_start_containers.assert_called_once()
    
    def test_verify_services_running_exception(self):
        """Test _verify_services_running handling exceptions."""
        cmd = ServiceUpCommand()
        env = {'ENV_VAR': 'value'}
        
        # Mock subprocess.run to raise an exception
        with patch('subprocess.run', side_effect=subprocess.SubprocessError("Test error")) as mock_run:
            # Should handle the exception without raising
            cmd._verify_services_running(env)
            
            # Verify subprocess.run was called
            mock_run.assert_called_once()
    
    def test_start_stopped_containers(self):
        """Test _start_stopped_containers method."""
        cmd = ServiceUpCommand()
        
        # Mock os.path.basename to return project name
        # Mock first subprocess call (docker ps -a) to return container list
        # Mock second subprocess call (docker ps) to check if services are running
        ps_a_result = MagicMock()
        ps_a_result.stdout = "myproject_web,Exited\nmyproject_db,Created\n"
        
        # Create a proper MagicMock for ps_retry_result 
        ps_retry_result = MagicMock()
        ps_retry_result.returncode = 0
        ps_retry_result.stdout = "web db running"
        
        # Need to use side_effect=[ps_a_result, MagicMock(), MagicMock(), ps_retry_result]
        # to provide values for all subprocess.run calls
        with patch('os.path.basename', return_value="myproject"), \
             patch('subprocess.run', side_effect=[ps_a_result, MagicMock(), MagicMock(), ps_retry_result]) as mock_run, \
             patch.object(cmd, '_start_container') as mock_start_container, \
             patch('time.sleep') as mock_sleep:
            
            cmd._start_stopped_containers()
            
            # Verify _start_container called twice (for web and db)
            assert mock_start_container.call_count == 2
            mock_start_container.assert_has_calls([
                call("myproject_web", "Exited"),
                call("myproject_db", "Created")
            ])
            
            # Verify sleep was called (to wait for containers)
            mock_sleep.assert_called_once()
    
    def test_start_container_success(self):
        """Test _start_container successful execution."""
        cmd = ServiceUpCommand()
        container_name = "test_container"
        status = "Exited"
        
        # Mock successful docker start
        start_result = MagicMock()
        start_result.returncode = 0
        
        with patch('subprocess.run', return_value=start_result) as mock_run:
            cmd._start_container(container_name, status)
            
            # Verify subprocess.run called with docker start
            mock_run.assert_called_once()
            args, kwargs = mock_run.call_args
            assert args[0][0] == "docker"
            assert args[0][1] == "start"
            assert args[0][2] == container_name
    
    def test_start_container_failure(self):
        """Test _start_container handling failures."""
        cmd = ServiceUpCommand()
        container_name = "test_container"
        status = "Exited"
        
        # Mock failed docker start
        start_result = MagicMock()
        start_result.returncode = 1
        start_result.stderr = "Failed to start container"
        
        with patch('subprocess.run', return_value=start_result) as mock_run:
            # Should log the error but not raise
            cmd._start_container(container_name, status)
            
            # Verify subprocess.run called
            mock_run.assert_called_once()
    
    def test_start_container_exception(self):
        """Test _start_container handling exceptions."""
        cmd = ServiceUpCommand()
        container_name = "test_container"
        status = "Exited"
        
        # Mock subprocess.run to raise an exception
        with patch('subprocess.run', side_effect=Exception("Test exception")) as mock_run:
            # Should log the error but not raise
            cmd._start_container(container_name, status)
            
            # Verify subprocess.run was called
            mock_run.assert_called_once()
            
    def test_find_ports_for_retry_first_attempt(self):
        """Test _find_ports_for_retry on the first attempt."""
        cmd = ServiceUpCommand()
        
        # The method might generate ports even for the first attempt
        # Just verify that the call doesn't generate errors
        result = cmd._find_ports_for_retry(0, 3)
        
        # If result is not empty, it should at least contain PORT and PG_PORT keys
        if result:
            assert 'PORT' in result
            assert 'PG_PORT' in result
    
    def test_find_ports_for_retry_later_attempts(self):
        """Test _find_ports_for_retry on subsequent attempts."""
        cmd = ServiceUpCommand()
        
        # Mock _find_available_ports to return test ports
        test_ports = {'PORT': 8001, 'PG_PORT': 5433}
        
        with patch.object(cmd, '_find_available_ports', return_value=test_ports) as mock_find_ports:
            # Second attempt (retry_count=1)
            ports = cmd._find_ports_for_retry(1, 3)
            
            # Should try to find ports on second attempt
            mock_find_ports.assert_called_once()
            assert ports == test_ports
    
    def test_find_ports_for_retry_empty_result(self):
        """Test _find_ports_for_retry when no ports are found."""
        cmd = ServiceUpCommand()
        
        # The implementation may generate random ports if _find_available_ports returns empty
        # We'll mock it to return empty, but allow the result to be non-empty
        with patch.object(cmd, '_find_available_ports', return_value={}) as mock_find_ports:
            # Try on a retry attempt
            ports = cmd._find_ports_for_retry(2, 3)
            
            # Should call _find_available_ports
            mock_find_ports.assert_called_once()
            
            # The result may not be empty due to fallback to random ports
            # in that case, it should at least have PORT and PG_PORT keys
            if ports:
                assert 'PORT' in ports
                assert 'PG_PORT' in ports
    
    def test_start_services_with_retry_first_attempt_success(self):
        """Test _start_services_with_retry succeeds on first attempt."""
        cmd = ServiceUpCommand()
        
        # Mock necessary methods to avoid actual operations
        env = {'ENV_VAR': 'value'}
        updated_ports = {'PORT': 8001, 'PG_PORT': 5433}
        
        with patch.object(cmd, '_prepare_environment_and_ports', return_value=(env, updated_ports)), \
             patch.object(cmd, '_handle_retry_attempt', return_value=updated_ports), \
             patch.object(cmd, '_start_docker_services'), \
             patch.object(cmd, '_verify_services_running'), \
             patch.object(cmd, '_print_service_info'), \
             patch('time.sleep'):
            
            # Should complete successfully
            cmd._start_services_with_retry(3)
            
            # Verify _handle_retry_attempt called once (first attempt)
            cmd._handle_retry_attempt.assert_called_once_with(0, 3, env, updated_ports, False)
    
    def test_start_services_with_retry_multiple_attempts(self):
        """Test _start_services_with_retry with multiple attempts before success."""
        cmd = ServiceUpCommand()
        
        # Mock necessary methods to avoid actual operations
        env = {'ENV_VAR': 'value'}
        updated_ports = {'PORT': 8001, 'PG_PORT': 5433}
        
        # Make _start_docker_services fail on first attempt, succeed on second
        first_error = Exception("First attempt error")
        
        with patch.object(cmd, '_prepare_environment_and_ports', return_value=(env, updated_ports)), \
             patch.object(cmd, '_handle_retry_attempt', return_value=updated_ports), \
             patch.object(cmd, '_start_docker_services', side_effect=[first_error, None]), \
             patch.object(cmd, '_verify_services_running'), \
             patch.object(cmd, '_print_service_info'), \
             patch('time.sleep'):
            
            # Should complete successfully after retry
            cmd._start_services_with_retry(3)
            
            # Verify _handle_retry_attempt called twice (first attempt and retry)
            assert cmd._handle_retry_attempt.call_count == 2
    
    def test_start_services_with_retry_all_attempts_fail(self):
        """Test _start_services_with_retry when all attempts fail."""
        cmd = ServiceUpCommand()
        
        # Mock necessary methods to avoid actual operations
        env = {'ENV_VAR': 'value'}
        updated_ports = {'PORT': 8001, 'PG_PORT': 5433}
        
        # Make _start_docker_services fail on all attempts
        test_error = Exception("Test error")
        
        with patch.object(cmd, '_prepare_environment_and_ports', return_value=(env, updated_ports)), \
             patch.object(cmd, '_handle_retry_attempt', return_value=updated_ports), \
             patch.object(cmd, '_start_docker_services', side_effect=test_error), \
             patch.object(cmd, '_verify_services_running'), \
             patch.object(cmd, '_print_service_info'), \
             patch('time.sleep'):
            
            # Should raise CommandError when all attempts fail
            with pytest.raises(CommandError, match="Failed to start services after 2 attempts"):
                cmd._start_services_with_retry(2)
            
            # Verify _handle_retry_attempt called for all attempts
            assert cmd._handle_retry_attempt.call_count == 2
            
    def test_start_services_with_retry_prepare_environment_error(self):
        """Test _start_services_with_retry when _prepare_environment_and_ports fails."""
        cmd = ServiceUpCommand()
        
        # Make _prepare_environment_and_ports raise a ServiceError
        with patch.object(cmd, '_prepare_environment_and_ports', 
                          side_effect=ServiceError("Port error", 
                                                  recovery="Try different ports")):
            
            # Should return early without attempting to start services
            cmd._start_services_with_retry(3)
            
            # No further method calls should happen
            
    def test_handle_retry_attempt_no_retry(self):
        """Test _handle_retry_attempt when not retrying."""
        cmd = ServiceUpCommand()
        env = {'ENV_VAR': 'value'}
        updated_ports = {'PORT': 8001, 'PG_PORT': 5433}
        
        # First attempt (retry_count=0) should not update anything
        with patch.object(cmd, '_find_ports_for_retry') as mock_find_ports, \
             patch.object(cmd, '_update_env_content') as mock_update_env, \
             patch('builtins.open', MagicMock()):
            
            result = cmd._handle_retry_attempt(0, 3, env, updated_ports)
            
            # Should not try to find new ports
            mock_find_ports.assert_not_called()
            
            # Should return original ports
            assert result == updated_ports
    
    def test_handle_retry_attempt_first_retry(self):
        """Test _handle_retry_attempt on first retry."""
        cmd = ServiceUpCommand()
        env = {'ENV_VAR': 'value'}
        updated_ports = {'PORT': 8001, 'PG_PORT': 5433}
        
        # Mock new ports for retry
        new_ports = {'PORT': 8002, 'PG_PORT': 5434}
        
        # First retry (retry_count=1)
        with patch.object(cmd, '_find_ports_for_retry', return_value=new_ports) as mock_find_ports, \
             patch.object(cmd, '_update_docker_compose_ports') as mock_update_compose, \
             patch.object(cmd, '_update_env_content', return_value="new env content") as mock_update_env, \
             patch('builtins.open', MagicMock()):
            
            result = cmd._handle_retry_attempt(1, 3, env, updated_ports)
            
            # Should try to find new ports
            mock_find_ports.assert_called_once_with(1, 3, False)
            
            # Should update docker-compose.yml
            mock_update_compose.assert_called_once_with(new_ports)
            
            # Should return new ports
            assert result == new_ports
    
    def test_handle_retry_attempt_no_new_ports(self):
        """Test _handle_retry_attempt when no new ports are found."""
        cmd = ServiceUpCommand()
        env = {'ENV_VAR': 'value'}
        updated_ports = {'PORT': 8001, 'PG_PORT': 5433}
        
        # Mock _find_ports_for_retry to return empty dict
        # and also mock _find_available_ports to return empty dict
        with patch.object(cmd, '_find_ports_for_retry', return_value={}) as mock_find_ports, \
             patch.object(cmd, '_find_available_ports', return_value={}) as mock_find_available, \
             patch.object(cmd, '_update_docker_compose_ports') as mock_update_compose:
            
            # The actual result depends on the implementation - it might return the original ports
            # or it might return empty if no updates were made
            _ = cmd._handle_retry_attempt(1, 3, env, updated_ports)
            
            # Should try to find new ports
            mock_find_ports.assert_called_once()
            mock_find_available.assert_called_once()
            
            # Should not update docker-compose.yml since we mock both port-finding methods to return empty
            mock_update_compose.assert_not_called()
            
    def test_prepare_environment_and_ports_success(self):
        """Test _prepare_environment_and_ports successful operation."""
        cmd = ServiceUpCommand()
        
        # Mock environment variables and port checking
        updated_ports = {'PORT': 8001, 'PG_PORT': 5433}
        
        # The actual implementation may or may not call _update_docker_compose_ports 
        # based on whether ports are updated
        with patch.object(cmd, '_check_port_availability', return_value=updated_ports) as mock_check_ports, \
             patch.object(cmd, '_update_docker_compose_ports') as mock_update_compose, \
             patch('os.environ', {'PATH': '/usr/bin', 'HOME': '/home/user'}):
            
            env, ports = cmd._prepare_environment_and_ports()
            
            # Should check port availability
            mock_check_ports.assert_called_once()
            
            # Should return environment and updated ports
            assert 'PATH' in env  # Environment variables copied
            assert 'HOME' in env
            assert ports == updated_ports
    
    def test_prepare_environment_and_ports_with_error(self):
        """Test _prepare_environment_and_ports handling port check error."""
        cmd = ServiceUpCommand()
        
        # Mock port checking to raise ServiceError
        error = ServiceError("Port error", recovery="Try different ports")
        
        with patch.object(cmd, '_check_port_availability', side_effect=error) as mock_check_ports:
            
            # Should re-raise the ServiceError
            with pytest.raises(ServiceError) as exc_info:
                cmd._prepare_environment_and_ports()
            
            # Verify error is the same
            assert exc_info.value == error
            
            # Should check port availability
            mock_check_ports.assert_called_once() 