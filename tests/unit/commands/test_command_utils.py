import os
import pytest
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from quickscale.commands.command_utils import wait_for_postgres, fix_permissions

# Setup logger for tests
logger = logging.getLogger("test_logger")

class TestCommandUtils:
    
    @patch("subprocess.run")
    def test_wait_for_postgres_with_valid_user(self, mock_run):
        # Setup mock for successful connection
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_run.return_value = mock_process
        
        # Test with valid user
        result = wait_for_postgres("validuser", logger, max_attempts=1)
        
        # Assertions
        assert result is True
        mock_run.assert_called_once()
    
    @patch("subprocess.run")
    def test_wait_for_postgres_with_empty_user(self, mock_run):
        # Test with empty user
        result = wait_for_postgres("", logger, max_attempts=1)
        
        # Assertions
        assert result is False
        mock_run.assert_not_called()
    
    @patch("subprocess.run")
    def test_wait_for_postgres_with_root_user(self, mock_run):
        # Test with root user
        result = wait_for_postgres("root", logger, max_attempts=1)
        
        # Assertions
        assert result is False
        mock_run.assert_not_called()
    
    @patch("subprocess.run")
    def test_fix_permissions_with_valid_user(self, mock_run):
        # Setup
        mock_dir = MagicMock()
        mock_dir.is_dir.return_value = True
        
        # Test with valid user
        fix_permissions(mock_dir, 1000, 1000, logger, pg_user="validuser")
        
        # Assertions
        mock_run.assert_called_once()
    
    @patch("subprocess.run")
    def test_fix_permissions_with_empty_user(self, mock_run):
        # Setup
        mock_dir = MagicMock()
        mock_dir.is_dir.return_value = True
        
        # Test with empty user
        with pytest.raises(ValueError, match="PostgreSQL user not specified"):
            fix_permissions(mock_dir, 1000, 1000, logger, pg_user="")
        
        # Assertions
        mock_run.assert_not_called()
    
    @patch("subprocess.run")
    def test_fix_permissions_with_root_user(self, mock_run):
        # Setup
        mock_dir = MagicMock()
        mock_dir.is_dir.return_value = True
        
        # Test with root user
        with pytest.raises(ValueError, match="Invalid PostgreSQL user: root"):
            fix_permissions(mock_dir, 1000, 1000, logger, pg_user="root")
        
        # Assertions
        mock_run.assert_not_called()
    
    @patch("subprocess.run")
    def test_fix_permissions_with_no_user(self, mock_run):
        # Setup
        mock_dir = MagicMock()
        mock_dir.is_dir.return_value = True
        
        # Test with no user parameter
        with pytest.raises(ValueError, match="PostgreSQL user not specified"):
            fix_permissions(mock_dir, 1000, 1000, logger)
        
        # Assertions
        mock_run.assert_not_called() 