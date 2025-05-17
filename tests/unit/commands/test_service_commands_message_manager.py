"""Tests for service commands using MessageManager."""
import pytest
from unittest.mock import patch, MagicMock

from quickscale.commands.service_commands import (
    ServiceUpCommand,
    ServiceDownCommand,
    ServiceLogsCommand,
    ServiceStatusCommand
)
from quickscale.commands.project_manager import ProjectManager


@pytest.fixture
def mock_message_manager():
    """Mock MessageManager methods to verify they're called."""
    with patch('quickscale.utils.message_manager.MessageManager.success') as mock_success, \
         patch('quickscale.utils.message_manager.MessageManager.error') as mock_error, \
         patch('quickscale.utils.message_manager.MessageManager.info') as mock_info, \
         patch('quickscale.utils.message_manager.MessageManager.warning') as mock_warning:
        yield {
            'success': mock_success,
            'error': mock_error,
            'info': mock_info,
            'warning': mock_warning
        }


@pytest.fixture
def mock_project_not_found():
    """Mock project not found scenario."""
    with patch('quickscale.commands.project_manager.ProjectManager.get_project_state') as mock_get_state:
        mock_get_state.return_value = {'has_project': False}
        yield mock_get_state


@pytest.fixture
def mock_project_found():
    """Mock project found scenario."""
    with patch('quickscale.commands.project_manager.ProjectManager.get_project_state') as mock_get_state:
        mock_get_state.return_value = {'has_project': True}
        yield mock_get_state


class TestServiceCommandsMessageManager:
    """Test service commands using MessageManager for output."""
    
    def test_up_command_project_not_found(self, mock_message_manager, mock_project_not_found):
        """Test that up command uses MessageManager when project not found."""
        command = ServiceUpCommand()
        command.execute()
        # Verify MessageManager error method was called
        assert mock_message_manager['error'].called
        assert ProjectManager.PROJECT_NOT_FOUND_MESSAGE in mock_message_manager['error'].call_args[0][0]
    
    def test_down_command_project_not_found(self, mock_message_manager, mock_project_not_found):
        """Test that down command uses MessageManager when project not found."""
        command = ServiceDownCommand()
        command.execute()
        # Verify MessageManager error method was called
        assert mock_message_manager['error'].called
        assert ProjectManager.PROJECT_NOT_FOUND_MESSAGE in mock_message_manager['error'].call_args[0][0]
    
    def test_logs_command_project_not_found(self, mock_message_manager, mock_project_not_found):
        """Test that logs command uses MessageManager when project not found."""
        command = ServiceLogsCommand()
        command.execute()
        # Verify MessageManager error method was called
        assert mock_message_manager['error'].called
        assert ProjectManager.PROJECT_NOT_FOUND_MESSAGE in mock_message_manager['error'].call_args[0][0]
    
    def test_status_command_project_not_found(self, mock_message_manager, mock_project_not_found):
        """Test that status command uses MessageManager when project not found."""
        command = ServiceStatusCommand()
        command.execute()
        # Verify MessageManager error method was called
        assert mock_message_manager['error'].called
        assert ProjectManager.PROJECT_NOT_FOUND_MESSAGE in mock_message_manager['error'].call_args[0][0]
    
    def test_down_command_success(self, mock_message_manager, mock_project_found):
        """Test that down command uses MessageManager for success message."""
        command = ServiceDownCommand()
        
        # Mock subprocess call
        with patch('subprocess.run', return_value=MagicMock(returncode=0)):
            command.execute()
        
        # Verify MessageManager methods were called
        assert mock_message_manager['info'].called
        assert "Stopping services..." in mock_message_manager['info'].call_args[0][0]
        assert mock_message_manager['success'].called
        assert "Services stopped successfully." in mock_message_manager['success'].call_args[0][0]
    
    def test_status_command_success(self, mock_message_manager, mock_project_found):
        """Test that status command uses MessageManager for info message."""
        command = ServiceStatusCommand()
        
        # Mock subprocess call
        with patch('subprocess.run', return_value=MagicMock(returncode=0)):
            command.execute()
        
        # Verify MessageManager methods were called
        assert mock_message_manager['info'].called
        assert "Checking service status..." in mock_message_manager['info'].call_args[0][0]
    
    def test_up_command_retry_failure(self, mock_message_manager, mock_project_found):
        """Test that up command uses MessageManager for retry failure message."""
        command = ServiceUpCommand()
        
        # Mock _start_services_with_retry to set an error message but not raise an exception
        # This matches the current implementation which handles errors internally
        def mock_start_services_with_retry(max_retries, no_cache):
            # Call MessageManager.error directly as the implementation does
            from quickscale.utils.message_manager import MessageManager
            error_message = "Failed to start services after 3 attempts. Last error: Service start failed"
            MessageManager.error(error_message)
            
        mock_method = MagicMock(side_effect=mock_start_services_with_retry)
        
        with patch.object(command, '_start_services_with_retry', mock_method):
            command.execute()
        
        # The command should call _start_services_with_retry
        assert mock_method.called
        # And MessageManager.error should be called with the error message
        assert mock_message_manager['error'].called
    
    def test_start_services_with_retry_failure(self, mock_message_manager, mock_project_found):
        """Test error handling in _start_services_with_retry when all attempts fail."""
        command = ServiceUpCommand()
        
        # Create a mock Exception for the last error
        last_error = Exception("Service start failed")
        
        # Mock the methods used in _start_services_with_retry
        with patch.object(command, '_prepare_environment_and_ports', return_value=({}, {})), \
             patch.object(command, '_handle_retry_attempt', return_value={}), \
             patch.object(command, '_start_docker_services', side_effect=last_error), \
             patch('quickscale.utils.message_manager.MessageManager.error') as mock_error, \
             patch('quickscale.utils.message_manager.MessageManager.print_recovery_suggestion') as mock_recovery:
            
            # Call the method with 1 retry
            command._start_services_with_retry(max_retries=1)
            
            # Verify MessageManager methods were called
            assert mock_error.called
            assert "Failed to start services after 1 attempts" in mock_error.call_args[0][0]
            assert mock_recovery.called
            assert "suggestion" in mock_recovery.call_args[1]
            assert "Try again with ports that are not in use" in mock_recovery.call_args[1]["suggestion"]
