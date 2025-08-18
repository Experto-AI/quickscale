"""Unit tests for error manager functionality."""
import sys
import subprocess
import logging
from unittest.mock import patch, MagicMock
import pytest

from quickscale.utils.error_manager import error_manager


class TestErrorConversion:
    """Tests for error conversion functionality."""
    
    def test_convert_subprocess_error(self):
        """Verify conversion of subprocess errors to appropriate error types."""
        # Create a mock subprocess error with docker command
        cmd = ["docker", "compose", "up", "-d"]
        error = subprocess.CalledProcessError(returncode=1, cmd=cmd, output=b"Error")
        
        # Convert the error
        result = error_manager.convert_exception(error)
        
        # Check it's properly converted to a ServiceError
        assert isinstance(result, error_manager.ServiceError)
        assert "Docker command failed" in result.message
        assert result.recovery is not None

    def test_convert_database_error(self):
        """Verify conversion of database related subprocess errors."""
        cmd = ["psql", "-U", "postgres"]
        error = subprocess.CalledProcessError(returncode=1, cmd=cmd, output=b"Error")
        
        result = error_manager.convert_exception(error)
        
        assert isinstance(result, error_manager.DatabaseError)
        assert "Database command failed" in result.message
        assert result.recovery is not None
    
    def test_convert_file_not_found(self):
        """Verify conversion of file not found errors."""
        error = FileNotFoundError("file.txt")
        result = error_manager.convert_exception(error)
        
        assert isinstance(result, error_manager.ProjectError)
        assert "File not found" in result.message
        
    def test_convert_permission_error(self):
        """Verify conversion of permission errors."""
        error = PermissionError("Permission denied")
        result = error_manager.convert_exception(error)
        
        assert "Permission denied" in result.message
        assert result.recovery is not None
        
    def test_convert_unknown_error(self):
        """Verify conversion of unregistered error types."""
        error = ValueError("Custom error")
        result = error_manager.convert_exception(error)
        
        assert isinstance(result, error_manager.CommandError)
        assert "An error occurred" in result.message
        assert str(error) in result.message


class TestErrorHandling:
    """Tests for error handling functionality."""
    
    @patch("quickscale.utils.message_manager.MessageManager.error")
    @patch("quickscale.utils.message_manager.MessageManager.print_recovery_suggestion")
    @patch("sys.exit")
    def test_handle_command_error(self, mock_exit, mock_recovery, mock_error):
        """Verify error handling with exiting."""
        error = error_manager.CommandError("Test error", 
                            details="Test details", 
                            recovery="Test recovery")
        error_manager.handle_command_error(error)
        
        mock_error.assert_called_once_with("Test error", None)
        mock_recovery.assert_called_once_with("custom", suggestion="Test recovery")
        mock_exit.assert_called_once_with(error.exit_code)
    
    @patch("quickscale.utils.message_manager.MessageManager.error")
    @patch("quickscale.utils.message_manager.MessageManager.print_recovery_suggestion")
    def test_handle_error_no_exit(self, mock_recovery, mock_error):
        """Verify error handling without exiting."""
        error = error_manager.CommandError("Test error", recovery="Test recovery")
        result = error_manager.handle_command_error(error, exit_on_error=False)
        
        mock_error.assert_called_once_with("Test error", None)
        mock_recovery.assert_called_once_with("custom", suggestion="Test recovery")
        assert result is None

    def test_error_hierarchy(self):
        """Verify error class hierarchy relationships."""
        service_error = error_manager.ServiceError("Service failed")
        database_error = error_manager.DatabaseError("Database failed")
        
        assert isinstance(service_error, error_manager.CommandError)
        assert isinstance(database_error, error_manager.ServiceError)
        assert isinstance(database_error, error_manager.CommandError)


class TestCommandErrorProperties:
    """Tests for CommandError and subclass properties."""
    
    def test_exit_codes(self):
        """Verify exit codes are set correctly for different error types."""
        assert error_manager.CommandError("error").exit_code == 1
        assert error_manager.ValidationError("error").exit_code == 7
        assert error_manager.DatabaseError("error").exit_code == 9
    
    def test_error_details(self):
        """Verify error details storage."""
        error = error_manager.CommandError("message", details="details", recovery="recovery")
        assert error.message == "message"
        assert error.details == "details"
        assert error.recovery == "recovery"