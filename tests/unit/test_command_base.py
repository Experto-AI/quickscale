"""Unit tests for command base functionality."""
import sys
import logging
from unittest.mock import patch, MagicMock
import pytest

from quickscale.commands.command_base import Command
from quickscale.utils.error_manager import CommandError, ValidationError


class CommandForTesting(Command):
    """Test implementation of Command for testing."""
    
    def execute(self, *args, **kwargs):
        """Execute the command."""
        return args, kwargs
        
    def raise_exception(self, exception):
        """Raise the given exception for testing error handling."""
        raise exception


class TestCommandBase:
    """Tests for the Command base class."""
    
    def test_handle_error_with_string(self):
        """Verify handling errors provided as strings."""
        cmd = CommandForTesting()
        
        with patch('quickscale.commands.command_base.handle_command_error') as mock_handle:
            cmd.handle_error("Test error message")
            
            # Verify the error was correctly created and passed to handler
            args = mock_handle.call_args[0]
            error = args[0]
            assert isinstance(error, CommandError)
            assert error.message == "Test error message"
    
    def test_handle_error_with_exception(self):
        """Verify handling errors provided as exceptions."""
        cmd = CommandForTesting()
        exception = ValueError("Test value error")
        
        with patch('quickscale.commands.command_base.handle_command_error') as mock_handle:
            cmd.handle_error(exception)
            
            # Verify the exception was correctly converted and passed to handler
            args = mock_handle.call_args[0]
            error = args[0]
            assert isinstance(error, CommandError)
            assert "Test value error" in error.message
    
    def test_handle_error_with_recovery(self):
        """Verify handling errors with recovery suggestions."""
        cmd = CommandForTesting()
        recovery = "Try this to fix the problem"
        
        with patch('quickscale.commands.command_base.handle_command_error') as mock_handle:
            cmd.handle_error("Test error", recovery=recovery)
            
            # Verify the recovery was correctly added to the error
            args = mock_handle.call_args[0]
            error = args[0]
            assert error.recovery == recovery
    
    def test_handle_error_with_context(self):
        """Verify handling errors with context information."""
        cmd = CommandForTesting()
        context = {"file": "test.txt", "line": 42}
        
        with patch('quickscale.commands.command_base.handle_command_error') as mock_handle:
            cmd.handle_error("Test error", context=context)
            
            # Verify the context was correctly added to the error details
            args = mock_handle.call_args[0]
            error = args[0]
            assert error.details is not None
            assert "file=test.txt" in error.details
            assert "line=42" in error.details
    
    def test_safe_execute(self):
        """Verify the safe execution wrapper."""
        cmd = CommandForTesting()
        
        # Test successful execution
        result = cmd.safe_execute("arg1", kwarg1="value1")
        assert result == (("arg1",), {"kwarg1": "value1"})
        
        # Test with exception
        with patch.object(cmd, 'handle_error') as mock_handle:
            cmd.execute = MagicMock(side_effect=ValueError("Test error"))
            cmd.safe_execute("arg1")
            mock_handle.assert_called_once()
    
    def test_exit_with_error(self):
        """Verify the legacy error exit method."""
        cmd = CommandForTesting()
        cmd.logger = logging.getLogger("test")
        
        with patch('builtins.print') as mock_print, \
             patch('sys.exit') as mock_exit, \
             patch.object(cmd.logger, 'error') as mock_log, \
             patch('quickscale.utils.message_manager.MessageManager.error') as mock_manager_error:
             
            cmd._exit_with_error("Test error message")
            
            # Verify error was logged, printed, and sys.exit was called
            mock_log.assert_called_once_with("Test error message")
            mock_manager_error.assert_called_once_with("Test error message", cmd.logger)
            mock_exit.assert_called_once_with(1)