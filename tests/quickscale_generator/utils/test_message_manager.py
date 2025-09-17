"""Tests for message_manager module."""
import logging
import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from quickscale.utils.message_manager import MessageManager, MessageType


@pytest.fixture
def mock_stdout():
    """Fixture to capture output to stdout."""
    original_stdout = sys.stdout
    string_io = StringIO()
    sys.stdout = string_io
    yield string_io
    sys.stdout = original_stdout


@pytest.fixture
def mock_logger():
    """Fixture to create a mock logger."""
    logger = MagicMock(spec=logging.Logger)
    # Set isEnabledFor to return True for DEBUG level
    logger.isEnabledFor.return_value = True
    return logger


@pytest.fixture
def mock_color_detection():
    """Mock color detection to always return True for testing."""
    with patch('quickscale.utils.message_manager.MessageManager._use_color', return_value=True):
        yield


class TestMessageManager:
    """Test the MessageManager class functionality."""
    
    def test_get_template(self):
        """Test retrieving templates."""
        # Test with no parameters
        template = MessageManager.get_template("project_not_found")
        assert template == "No QuickScale project found in the current directory."
        
        # Test with parameters
        template = MessageManager.get_template("project_created", project_name="test-project")
        assert template == "Project 'test-project' created successfully."
        
        # Test with invalid template key
        with pytest.raises(ValueError):
            MessageManager.get_template("non_existent_template")
    
    def test_success_message(self, capsys, mock_logger, mock_color_detection):
        """Test printing success messages."""
        # Test single message
        MessageManager.success("Test success message", mock_logger)
        output = capsys.readouterr().out
        # The output includes an emoji prefix (✅) so we use a case-insensitive check
        assert "test success message".lower() in output.lower()
        mock_logger.info.assert_called_with("Test success message")

        # Test multiple messages
        messages = ["First success", "Second success"]
        MessageManager.success(messages, mock_logger)
        output = capsys.readouterr().out
        assert "first success".lower() in output.lower()
        assert "second success".lower() in output.lower()
        assert mock_logger.info.call_count == 3  # 1 from first test + 2 from this call
    
    def test_error_message(self, capsys, mock_logger, mock_color_detection):
        """Test printing error messages."""
        MessageManager.error("Test error message", mock_logger)
        output = capsys.readouterr().out
        assert "test error message".lower() in output.lower()
        mock_logger.error.assert_called_with("Test error message")
    
    def test_info_message(self, capsys, mock_logger, mock_color_detection):
        """Test printing info messages."""
        MessageManager.info("Test info message", mock_logger)
        output = capsys.readouterr().out
        assert "test info message".lower() in output.lower()
        mock_logger.info.assert_called_with("Test info message")
    
    def test_warning_message(self, capsys, mock_logger, mock_color_detection):
        """Test printing warning messages."""
        MessageManager.warning("Test warning message", mock_logger)
        output = capsys.readouterr().out
        assert "test warning message".lower() in output.lower()
        mock_logger.warning.assert_called_with("Test warning message")
    
    def test_debug_message(self, capsys, mock_logger, mock_color_detection):
        """Test printing debug messages."""
        MessageManager.debug("Test debug message", mock_logger)
        output = capsys.readouterr().out
        assert "test debug message".lower() in output.lower()
        mock_logger.debug.assert_called_with("Test debug message")

        # Test with disabled debug logging
        mock_logger.isEnabledFor.return_value = False
        MessageManager.debug("Hidden debug message", mock_logger)
        output = capsys.readouterr().out
        assert output == ""  # No output when debug is disabled
        mock_logger.debug.assert_called_with("Hidden debug message")
    
    def test_template_method(self, capsys, mock_logger, mock_color_detection):
        """Test using templates with different message types."""
        # Test with SUCCESS type
        MessageManager.template("project_created", MessageType.SUCCESS, mock_logger, project_name="test-project")
        output = capsys.readouterr().out
        assert "Project 'test-project' created successfully" in output
        mock_logger.info.assert_called_with("Project 'test-project' created successfully.")

        # Test with ERROR type
        MessageManager.template("command_failed", MessageType.ERROR, mock_logger, error="Test error")
        output = capsys.readouterr().out
        assert "Command failed: Test error" in output
        mock_logger.error.assert_called_with("Command failed: Test error")
    
    def test_print_command_result(self, capsys, mock_color_detection):
        """Test printing command results for different services."""
        # Test web service result
        MessageManager.print_command_result(service="web", port=8000)
        output = capsys.readouterr().out
        assert "Web service is running on port 8000" in output
        assert "Access the application at: http://localhost:8000" in output

        # Test database service result
        MessageManager.print_command_result(service="db", port=5432)
        output = capsys.readouterr().out
        assert "Database service is running" in output
        assert "PostgreSQL database is accessible externally on port 5432" in output

        # Test generic service result
        MessageManager.print_command_result()
        output = capsys.readouterr().out
        assert "Services are running" in output
    
    def test_print_recovery_suggestion(self, capsys, mock_color_detection):
        """Test printing recovery suggestions."""
        MessageManager.print_recovery_suggestion("recovery_port_in_use", port=8000)
        output = capsys.readouterr().out
        assert "Suggestion:" in output
        assert "Either free the port 8000" in output
    
    def test_format_message_without_color(self, mock_stdout):
        """Test message formatting without color (non-TTY)."""
        with patch('quickscale.utils.message_manager.MessageManager._use_color', return_value=False):
            formatted = MessageManager._format_message("Test message", MessageType.INFO)
            assert "Test message" in formatted
            # No color codes should be present
            assert "\033" not in formatted
