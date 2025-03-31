"""Unit tests for error manager functionality."""
import sys
import subprocess
import logging
from unittest.mock import patch, MagicMock
import pytest

from quickscale.utils.error_manager import (
    CommandError, ServiceError, ValidationError, ProjectError,
    DatabaseError, handle_command_error, convert_exception
)


class TestErrorConversion:
    """Tests for error conversion functionality."""
    
    def test_convert_subprocess_error(self):
        """Verify conversion of subprocess errors to appropriate error types."""
        # Create a mock subprocess error with docker command
        cmd = ["docker", "compose", "up", "-d"]
        error = subprocess.CalledProcessError(returncode=1, cmd=cmd, output=b"Error")
        
        # Convert the error
        result = convert_exception(error)
        
        # Check it's properly converted to a ServiceError
        assert isinstance(result, ServiceError)
        assert "Docker command failed" in result.message
        assert result.recovery is not None

    def test_convert_database_error(self):
        """Verify conversion of database related subprocess errors."""
        cmd = ["psql", "-U", "postgres"]
        error = subprocess.CalledProcessError(returncode=1, cmd=cmd, output=b"Error")
        
        result = convert_exception(error)
        
        assert isinstance(result, DatabaseError)
        assert "Database command failed" in result.message
        assert result.recovery is not None
    
    def test_convert_file_not_found(self):
        """Verify conversion of file not found errors."""
        error = FileNotFoundError("file.txt")
        result = convert_exception(error)
        
        assert isinstance(result, ProjectError)
        assert "File not found" in result.message
        
    def test_convert_permission_error(self):
        """Verify conversion of permission errors."""
        error = PermissionError("Permission denied")
        result = convert_exception(error)
        
        assert "Permission denied" in result.message
        assert result.recovery is not None
        
    def test_convert_unknown_error(self):
        """Verify conversion of unregistered error types."""
        error = ValueError("Custom error")
        result = convert_exception(error)
        
        assert isinstance(result, CommandError)
        assert "An error occurred" in result.message
        assert str(error) in result.message


class TestErrorHandling:
    """Tests for error handling functionality."""
    
    @patch("builtins.print")
    @patch("sys.exit")
    def test_handle_command_error(self, mock_exit, mock_print):
        """Verify error handling with exiting."""
        error = CommandError("Test error", 
                            details="Test details", 
                            recovery="Test recovery")
        handle_command_error(error)
        
        mock_print.assert_any_call("\nError: Test error")
        mock_print.assert_any_call("\nSuggestion: Test recovery")
        mock_exit.assert_called_once_with(error.exit_code)
    
    @patch("builtins.print")
    def test_handle_error_no_exit(self, mock_print):
        """Verify error handling without exiting."""
        error = CommandError("Test error", recovery="Test recovery")
        result = handle_command_error(error, exit_on_error=False)
        
        mock_print.assert_any_call("\nError: Test error")
        assert result is None

    def test_error_hierarchy(self):
        """Verify error class hierarchy relationships."""
        service_error = ServiceError("Service failed")
        database_error = DatabaseError("Database failed")
        
        assert isinstance(service_error, CommandError)
        assert isinstance(database_error, ServiceError)
        assert isinstance(database_error, CommandError)


class TestCommandErrorProperties:
    """Tests for CommandError and subclass properties."""
    
    def test_exit_codes(self):
        """Verify exit codes are set correctly for different error types."""
        assert CommandError("error").exit_code == 1
        assert ValidationError("error").exit_code == 7
        assert DatabaseError("error").exit_code == 9
    
    def test_error_details(self):
        """Verify error details storage."""
        error = CommandError("message", details="details", recovery="recovery")
        assert error.message == "message"
        assert error.details == "details"
        assert error.recovery == "recovery"