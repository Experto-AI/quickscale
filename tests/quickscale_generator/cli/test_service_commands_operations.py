"""Unit tests for service operations in service commands."""
import subprocess
from unittest.mock import patch

from quickscale.commands.project_manager import ProjectManager
from quickscale.commands.service_commands import (
    ServiceDownCommand,
    ServiceLogsCommand,
    ServiceStatusCommand,
)


class TestServiceOperations:
    """Tests for service operation commands."""
    
    def test_service_down_execute(self):
        """Test ServiceDownCommand.execute method."""
        cmd = ServiceDownCommand()
        
        # Mock subprocess.run to return success
        with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                  return_value={'has_project': True}), \
             patch('subprocess.run') as mock_run:
            
            # Call execute
            cmd.execute()
            
            # Verify subprocess.run was called with docker-compose down
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "docker-compose" in args
            assert "down" in args
    
    def test_service_down_execute_no_project(self):
        """Test ServiceDownCommand.execute with no project."""
        cmd = ServiceDownCommand()
        
        # Mock project state to return no project
        with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                  return_value={'has_project': False}), \
             patch('builtins.print') as mock_print:
            
            # Call execute
            cmd.execute()
            
            # Verify error was printed
            mock_print.assert_called_with(f"❌ {ProjectManager.PROJECT_NOT_FOUND_MESSAGE}", flush=True)
            assert mock_print.call_count > 0
    
    def test_service_logs_execute_no_params(self):
        """Test ServiceLogsCommand.execute with default parameters."""
        cmd = ServiceLogsCommand()
        
        # Mock subprocess.run to return success
        with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                  return_value={'has_project': True}), \
             patch('subprocess.run') as mock_run:
            
            # Call execute with default parameters
            cmd.execute()
            
            # Verify subprocess.run was called with docker-compose logs and default params
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "docker-compose" in args
            assert "logs" in args
            assert "--tail=100" in args  # Default lines parameter
    
    def test_service_logs_execute_with_params(self):
        """Test ServiceLogsCommand.execute with custom parameters."""
        cmd = ServiceLogsCommand()
        
        # Mock subprocess.run to return success
        with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                  return_value={'has_project': True}), \
             patch('subprocess.run') as mock_run:
            
            # Call execute with custom parameters
            cmd.execute(
                service="web",
                follow=True,
                since="1h",
                lines=50,
                timestamps=True
            )
            
            # Verify subprocess.run was called with correct parameters
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "docker-compose" in args
            assert "logs" in args
            assert "-f" in args  # Note: -f is used instead of --follow
            assert "--since" in args
            assert "1h" in args
            assert "--tail=50" in args
            assert any(arg == "--timestamps" or arg == "-t" for arg in args)
            assert "web" in args  # Service name at the end
    
    def test_service_logs_execute_no_project(self):
        """Test ServiceLogsCommand.execute with no project."""
        cmd = ServiceLogsCommand()
        
        # Mock project state to return no project
        with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                  return_value={'has_project': False}), \
             patch('builtins.print') as mock_print:
            
            # Call execute
            cmd.execute()
            
            # Verify error was printed
            mock_print.assert_called_with(f"❌ {ProjectManager.PROJECT_NOT_FOUND_MESSAGE}", flush=True)
            assert mock_print.call_count > 0
    
    def test_service_status_execute(self):
        """Test ServiceStatusCommand.execute method."""
        cmd = ServiceStatusCommand()
        
        # Mock subprocess.run to return success
        with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                  return_value={'has_project': True}), \
             patch('subprocess.run') as mock_run:
            
            # Call execute
            cmd.execute()
            
            # Verify subprocess.run was called with docker compose ps
            # The actual implementation uses DOCKER_COMPOSE_COMMAND.split() + ["ps"]
            # which results in either ["docker-compose", "ps"] or ["docker", "compose", "ps"]
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "docker-compose" in args or "docker" in args
            assert "ps" in args
    
    def test_service_status_execute_no_project(self):
        """Test ServiceStatusCommand.execute with no project."""
        cmd = ServiceStatusCommand()
        
        # Mock project state to return no project
        with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                  return_value={'has_project': False}), \
             patch('builtins.print') as mock_print:
            
            # Call execute
            cmd.execute()
            
            # Verify error was printed
            mock_print.assert_called_with(f"❌ {ProjectManager.PROJECT_NOT_FOUND_MESSAGE}", flush=True)
            assert mock_print.call_count > 0
    
    def test_service_status_execute_with_error(self):
        """Test ServiceStatusCommand.execute with subprocess error."""
        cmd = ServiceStatusCommand()
        
        # Create a subprocess error
        error = subprocess.CalledProcessError(1, "docker-compose ps")
        error.stdout = b"Error output"
        error.stderr = b"Error details"
        
        # Mock project state and subprocess.run
        with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                  return_value={'has_project': True}), \
             patch('subprocess.run', side_effect=error), \
             patch.object(cmd, 'handle_error') as mock_handle_error:
            
            # Call execute
            cmd.execute()
            
            # Verify error was handled with context
            mock_handle_error.assert_called_once()
            assert mock_handle_error.call_args[0][0] == error
            assert "context" in mock_handle_error.call_args[1]
            assert "action" in mock_handle_error.call_args[1]["context"]
    
    def test_service_logs_execute_with_error(self):
        """Test ServiceLogsCommand.execute with subprocess error."""
        cmd = ServiceLogsCommand()
        
        # Create a subprocess error
        error = subprocess.CalledProcessError(1, "docker-compose logs")
        error.stdout = b"Error output"
        error.stderr = b"Error details"
        
        # Mock project state and subprocess.run
        with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                  return_value={'has_project': True}), \
             patch('subprocess.run', side_effect=error), \
             patch.object(cmd, 'handle_error') as mock_handle_error:
            
            # Call execute with parameters to ensure they're included in context
            cmd.execute(service="web", follow=True)
            
            # Verify error was handled with detailed context
            mock_handle_error.assert_called_once()
            assert mock_handle_error.call_args[0][0] == error
            assert "context" in mock_handle_error.call_args[1]
            context = mock_handle_error.call_args[1]["context"]
            assert context["service"] == "web"
            assert context["follow"] is True 
