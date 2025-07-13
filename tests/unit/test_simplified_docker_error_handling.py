"""
Unit tests for simplified Docker error handling.

Tests the simplified error handling that trusts Docker exit codes
and provides clear, actionable error messages.
"""

import pytest
import subprocess
from unittest.mock import Mock, patch
from quickscale.utils.error_manager import ServiceError
from quickscale.commands.service_commands import ServiceUpCommand


class TestSimplifiedDockerErrorHandling:
    """Test simplified Docker error handling behavior."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service_command = ServiceUpCommand()
    
    def test_handle_docker_process_error_raises_service_error(self):
        """Test that Docker process errors raise ServiceError with clear message."""
        # Create a mock CalledProcessError
        mock_error = subprocess.CalledProcessError(
            returncode=1,
            cmd=["docker", "compose", "up", "--build", "-d"]
        )
        # Set stdout and stderr attributes manually
        mock_error.stdout = "Some output"
        mock_error.stderr = "Error: port already in use"
        
        # Mock environment
        env = {"DOCKER_COMPOSE_COMMAND": "docker compose"}
        
        # Test that the error handler raises ServiceError
        with pytest.raises(ServiceError) as exc_info:
            self.service_command._handle_docker_process_error(mock_error, env)
        
        # Verify the error message is clear and actionable
        error = exc_info.value
        assert "Docker services failed to start" in str(error)
        assert "exit code: 1" in str(error)
        assert "Check Docker logs with 'quickscale logs'" in error.recovery
    
    def test_handle_docker_process_error_logs_error_details(self):
        """Test that error details are properly logged."""
        mock_error = subprocess.CalledProcessError(
            returncode=2,
            cmd=["docker", "compose", "up"]
        )
        # Set stdout and stderr attributes manually
        mock_error.stdout = "stdout content"
        mock_error.stderr = "stderr content"
        
        env = {"DOCKER_COMPOSE_COMMAND": "docker compose"}
        
        # Mock logger to capture log calls
        with patch.object(self.service_command, 'logger') as mock_logger:
            with pytest.raises(ServiceError):
                self.service_command._handle_docker_process_error(mock_error, env)
            
            # Verify error logging - check all calls
            mock_logger.error.assert_any_call("Docker Compose failed with exit code 2")
            mock_logger.info.assert_called_with("Docker Compose stdout:\nstdout content")
            mock_logger.error.assert_any_call("Docker Compose stderr:\nstderr content")
    
    def test_handle_docker_process_error_with_no_output(self):
        """Test error handling when there's no stdout/stderr output."""
        mock_error = subprocess.CalledProcessError(
            returncode=1,
            cmd=["docker", "compose", "up"]
        )
        # Set stdout and stderr attributes manually
        mock_error.stdout = ""
        mock_error.stderr = ""
        
        env = {"DOCKER_COMPOSE_COMMAND": "docker compose"}
        
        with patch.object(self.service_command, 'logger') as mock_logger:
            with pytest.raises(ServiceError):
                self.service_command._handle_docker_process_error(mock_error, env)
            
            # Should still log the error but not the empty output
            mock_logger.error.assert_called_with("Docker Compose failed with exit code 1")
    
    def test_handle_docker_process_error_trusts_exit_codes(self):
        """Test that the error handler trusts Docker exit codes without fallback logic."""
        mock_error = subprocess.CalledProcessError(
            returncode=1,
            cmd=["docker", "compose", "up"]
        )
        # Set stdout and stderr attributes manually
        mock_error.stdout = ""
        mock_error.stderr = ""
        
        env = {"DOCKER_COMPOSE_COMMAND": "docker compose"}
        
        # Mock subprocess.run to ensure it's not called (no fallback logic)
        with patch('subprocess.run') as mock_run:
            with pytest.raises(ServiceError):
                self.service_command._handle_docker_process_error(mock_error, env)
            
            # Verify that no additional subprocess calls are made
            # (the old logic would call docker compose ps to check if services are running)
            mock_run.assert_not_called()
    
    def test_start_docker_services_uses_timeout_constant(self):
        """Test that Docker service startup uses the timeout constant."""
        with patch('subprocess.run') as mock_run:
            # Mock successful execution
            mock_run.return_value = Mock(returncode=0)
            
            env = {"DOCKER_COMPOSE_COMMAND": "docker compose"}
            
            # Call the method
            self.service_command._start_docker_services(env)
            
            # Verify timeout constant is used
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[1]['timeout'] == 60  # DOCKER_SERVICE_STARTUP_TIMEOUT
    
    def test_start_docker_services_timeout_expired_raises_service_error(self):
        """Test that timeout expired raises ServiceError with clear message."""
        with patch('subprocess.run') as mock_run:
            # Mock timeout expired
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["docker", "compose", "up"],
                timeout=300
            )
            
            env = {"DOCKER_COMPOSE_COMMAND": "docker compose"}
            
            with pytest.raises(ServiceError) as exc_info:
                self.service_command._start_docker_services(env)
            
            error = exc_info.value
            assert "Docker services startup timed out after 60 seconds" in str(error)
            assert "Try increasing the timeout" in error.recovery
    
    def test_verify_services_running_uses_timeout_constant(self):
        """Test that service verification uses the timeout constant."""
        with patch('subprocess.run') as mock_run:
            # Mock successful ps command
            mock_run.return_value = Mock(returncode=0, stdout="db web")
            
            env = {"DOCKER_COMPOSE_COMMAND": "docker compose"}
            
            # Call the method
            self.service_command._verify_services_running(env)
            
            # Verify timeout constant is used
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[1]['timeout'] == 20  # DOCKER_PS_CHECK_TIMEOUT
    
    def test_start_container_uses_timeout_constant(self):
        """Test that container start uses the timeout constant."""
        with patch('subprocess.run') as mock_run:
            # Mock successful container start
            mock_run.return_value = Mock(returncode=0)
            
            # Call the method
            self.service_command._start_container("test-container", "Exited")
            
            # Verify timeout constant is used
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[1]['timeout'] == 30  # DOCKER_CONTAINER_START_TIMEOUT
    
    def test_retry_logic_uses_delay_constants(self):
        """Test that retry logic uses the delay constants."""
        with patch('time.sleep') as mock_sleep:
            with patch.object(self.service_command, '_start_docker_services') as mock_start:
                # Mock successful startup
                mock_start.return_value = None
                
                with patch.object(self.service_command, '_verify_services_running'):
                    with patch.object(self.service_command, '_print_service_info'):
                        # Mock environment preparation
                        with patch.object(self.service_command, '_prepare_environment_and_ports') as mock_prep:
                            mock_prep.return_value = ({}, {})
                            
                            # Call the retry method with required env parameter
                            self.service_command._start_services_with_retry(max_retries=1)
                            
                            # Verify stabilization delay is used
                            mock_sleep.assert_called_with(15)  # SERVICE_STABILIZATION_DELAY
    
    def test_error_messages_are_actionable(self):
        """Test that error messages provide actionable guidance."""
        mock_error = subprocess.CalledProcessError(
            returncode=1,
            cmd=["docker", "compose", "up"]
        )
        # Set stdout and stderr attributes manually
        mock_error.stdout = ""
        mock_error.stderr = "Error: port 8000 is already in use"
        
        env = {"DOCKER_COMPOSE_COMMAND": "docker compose"}
        
        with pytest.raises(ServiceError) as exc_info:
            self.service_command._handle_docker_process_error(mock_error, env)
        
        error = exc_info.value
        # Verify the recovery message provides specific guidance
        assert "quickscale logs" in error.recovery
        assert "Check Docker logs" in error.recovery 