"""Consolidated tests for command base functionality.

This file consolidates all command base tests following DRY principles.
Replaces: test_command_base.py and test_command_base_complete.py.
"""
import sys
import logging
from unittest.mock import patch, Mock, MagicMock
import pytest

from quickscale.commands.command_base import Command
from quickscale.utils.error_manager import CommandError, ValidationError
from tests.base_test_classes import CommandTestMixin


class ConcreteTestCommand(Command):
    """Concrete implementation of Command for testing."""
    
    def execute(self, *args, **kwargs):
        """Test execute method."""
        if kwargs.get('fail'):
            raise ValueError("Test execution error")
        return "success"
        
    def raise_exception(self, exception):
        """Raise the given exception for testing error handling."""
        raise exception


class TestCommandBase(CommandTestMixin):
    """Consolidated tests for the Command base class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.command = ConcreteTestCommand()
    
    def test_initialization(self):
        """Test Command initialization."""
        self.assert_command_initialized(self.command)
    
    def test_abstract_execute_enforcement(self):
        """Test that Command.execute is abstract."""
        with pytest.raises(TypeError):
            Command()
    
    def test_handle_error_with_string(self):
        """Test handling errors provided as strings."""
        cmd = ConcreteTestCommand()
        
        with patch('quickscale.commands.command_base.handle_command_error') as mock_handle:
            cmd.handle_error("Test error message")
            
            # Verify the error was correctly created and passed to handler
            args = mock_handle.call_args[0]
            error = args[0]
            assert isinstance(error, CommandError)
            assert error.message == "Test error message"
    
    def test_handle_error_with_exception(self):
        """Test handling errors provided as exceptions."""
        cmd = ConcreteTestCommand()
        exception = ValueError("Test value error")
        
        with patch('quickscale.commands.command_base.handle_command_error') as mock_handle:
            cmd.handle_error(exception)
            
            # Verify the exception was correctly converted and passed to handler
            args = mock_handle.call_args[0]
            error = args[0]
            assert isinstance(error, CommandError)
    
    def test_handle_error_with_recovery(self):
        """Test error handling with recovery suggestions."""
        cmd = ConcreteTestCommand()
        
        with patch('quickscale.commands.command_base.handle_command_error') as mock_handle:
            cmd.handle_error("Error message", recovery="Try again")
            
            args = mock_handle.call_args[0]
            error = args[0]
            assert isinstance(error, CommandError)
            assert error.message == "Error message"
    
    def test_handle_error_with_context(self):
        """Test error handling with additional context."""
        cmd = ConcreteTestCommand()
        
        with patch('quickscale.commands.command_base.handle_command_error') as mock_handle:
            cmd.handle_error("Error message", context={"key": "value"})
            
            args = mock_handle.call_args[0]
            error = args[0]
            assert isinstance(error, CommandError)
    
    @patch('quickscale.utils.message_manager.MessageManager')
    @patch('sys.exit')
    def test_exit_with_error(self, mock_exit, mock_message_manager):
        """Test _exit_with_error method."""
        command = ConcreteTestCommand()
        message = "Test error message"
        
        command._exit_with_error(message)
        
        mock_message_manager.error.assert_called_once_with(message, command.logger)
        mock_exit.assert_called_once_with(1)
    
    def test_logger_configuration(self):
        """Test that logger is properly configured."""
        cmd = ConcreteTestCommand()
        assert cmd.logger is not None
        assert isinstance(cmd.logger, logging.Logger)
        assert cmd.logger.name == 'quickscale.commands'
    
    def test_command_execution_success(self):
        """Test successful command execution."""
        cmd = ConcreteTestCommand()
        result = cmd.execute()
        assert result == "success"
    
    def test_command_execution_failure(self):
        """Test command execution with failure."""
        cmd = ConcreteTestCommand()
        with pytest.raises(ValueError):
            cmd.execute(fail=True)
    
    def test_error_context_preservation(self):
        """Test that error context is preserved."""
        cmd = ConcreteTestCommand()
        original_error = ValidationError("Original error")
        
        with patch('quickscale.commands.command_base.handle_command_error') as mock_handle:
            cmd.handle_error(original_error)
            
            args = mock_handle.call_args[0]
            error = args[0]
            # Should maintain the original error type information
            assert isinstance(error, CommandError)
    
    def test_multiple_error_handling_calls(self):
        """Test multiple consecutive error handling calls."""
        cmd = ConcreteTestCommand()
        
        with patch('quickscale.commands.command_base.handle_command_error') as mock_handle:
            cmd.handle_error("First error")
            cmd.handle_error("Second error")
            
            assert mock_handle.call_count == 2
    
    @patch('quickscale.utils.message_manager.MessageManager')
    def test_error_message_formatting(self, mock_message_manager):
        """Test error message formatting."""
        cmd = ConcreteTestCommand()
        
        with patch('sys.exit'):
            cmd._exit_with_error("Test message with {placeholder}")
            
            mock_message_manager.error.assert_called_once()
    
    def test_command_inheritance_properties(self):
        """Test that command inheritance works correctly."""
        cmd = ConcreteTestCommand()
        
        # Should have inherited properties from Command
        assert hasattr(cmd, 'logger')
        assert hasattr(cmd, 'handle_error')
        assert hasattr(cmd, '_exit_with_error')
        
        # Should have implemented abstract method
        assert hasattr(cmd, 'execute')
        assert callable(cmd.execute)
