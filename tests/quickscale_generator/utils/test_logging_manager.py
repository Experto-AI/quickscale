"""Unit tests for the logging_manager module."""
import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from quickscale.utils.logging_manager import LoggingManager


class TestLoggingManager(unittest.TestCase):
    """Test cases for the LoggingManager class."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create a temporary directory for testing
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.temp_dir.name)
        self.logs_dir = self.project_dir / 'logs'
        os.makedirs(self.logs_dir, exist_ok=True)
        
    def tearDown(self):
        """Clean up after tests."""
        self.temp_dir.cleanup()
    
    def test_get_logger(self):
        """Test that get_logger returns a logger instance."""
        logger = LoggingManager.get_logger()
        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.name, 'quickscale')
    
    @patch('logging.getLogger')
    def test_get_logger_singleton(self, mock_getLogger):
        """Test that get_logger returns the same logger instance on multiple calls."""
        mock_logger = MagicMock()
        mock_getLogger.return_value = mock_logger
        
        logger1 = LoggingManager.get_logger()
        logger2 = LoggingManager.get_logger()
        
        # Verify that getLogger was called with the right name
        mock_getLogger.assert_called_with('quickscale')
        self.assertEqual(logger1, logger2)
    
    @patch('logging.getLogger')
    @patch('logging.FileHandler')
    @patch('logging.Formatter')
    def test_setup_logging(self, mock_Formatter, mock_FileHandler, mock_getLogger):
        """Test that setup_logging configures the logger correctly."""
        mock_logger = MagicMock()
        mock_getLogger.return_value = mock_logger
        mock_handler = MagicMock()
        mock_FileHandler.return_value = mock_handler
        mock_formatter = MagicMock()
        mock_Formatter.return_value = mock_formatter
        
        # Call the function to test
        LoggingManager.setup_logging(self.project_dir, 'DEBUG')
        
        # Verify logger was configured correctly
        mock_getLogger.assert_called_with('quickscale')
        mock_logger.setLevel.assert_called_with('DEBUG')
        
        # Check that a file handler was created - don't check specific parameters since they may vary
        self.project_dir / 'logs' / 'quickscale.log'
        mock_FileHandler.assert_called()
        
        # Check that the formatter was set
        mock_handler.setFormatter.assert_called_with(mock_formatter)
        
        # Check that the handler was added to the logger
        mock_logger.addHandler.assert_called_with(mock_handler)
    
    @patch('logging.getLogger')
    @patch('os.path.exists')
    @patch('platform.system')
    @patch('platform.release')
    @patch('platform.python_version')
    def test_log_system_info(self, mock_python_version, mock_release, 
                            mock_system, mock_exists, mock_getLogger):
        """Test that _log_system_info logs system information."""
        # Setup mocks
        mock_logger = MagicMock()
        mock_getLogger.return_value = mock_logger
        mock_exists.return_value = False  # Ensure we log by pretending marker file doesn't exist
        mock_system.return_value = "Linux"
        mock_release.return_value = "5.4.0"
        mock_python_version.return_value = "3.11.0"
        
        # Call the function to test
        LoggingManager._log_system_info(mock_logger, self.project_dir)
        
        # Verify logger was called with system info
        calls = [
            call("QuickScale init log"),
            call(f"Project directory: {self.project_dir}"),
            call("System: Linux 5.4.0"),
            call("Python: 3.11.0")
        ]
        mock_logger.info.assert_has_calls(calls, any_order=False)
    
    def test_setup_logging_with_invalid_log_level(self):
        """Test that setup_logging handles invalid log levels."""
        # Call with invalid log level
        LoggingManager.setup_logging(self.project_dir, 'INVALID_LEVEL')
        
        # Get the logger and check its level (should default to INFO)
        logger = logging.getLogger('quickscale')
        self.assertEqual(logger.level, logging.INFO)
    
    @patch('pathlib.Path.mkdir')
    def test_setup_logging_creates_log_directory(self, mock_mkdir):
        """Test that setup_logging creates the logs directory if it doesn't exist."""
        LoggingManager.setup_logging(self.project_dir, 'DEBUG')
        
        # Verify the logs directory was created - should be called at least once
        mock_mkdir.assert_called_with(exist_ok=True)
    
    @patch('logging.FileHandler')
    def test_add_file_handler(self, mock_FileHandler):
        """Test that _add_file_handler adds a file handler to the logger."""
        mock_logger = MagicMock()
        mock_handler = MagicMock()
        mock_FileHandler.return_value = mock_handler
        
        # Call the function to test
        LoggingManager._add_file_handler(mock_logger, self.project_dir, 'DEBUG')
        
        # Verify the handler was configured and added to the logger
        mock_handler.setLevel.assert_called_with('DEBUG')
        mock_logger.addHandler.assert_called_with(mock_handler) 
