"""Comprehensive unit tests for InitCommand."""
import os
import shutil
import tempfile
import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path

from quickscale.commands.init_command import InitCommand
from quickscale.utils.error_manager import ProjectError, ValidationError
from tests.base_test_classes import CommandTestMixin


class TestInitCommand(CommandTestMixin):
    """Tests for InitCommand class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.command = InitCommand()
        self.test_project_name = "test_project"
    
    def test_initialization(self):
        """Test InitCommand initialization."""
        self.assert_command_initialized(self.command)
    
    def test_validate_project_name_directory_exists(self):
        """Test project name validation when directory already exists."""
        with patch('pathlib.Path.exists', return_value=True):
            with pytest.raises(ProjectError, match="already exists"):
                self.command.validate_project_name("existing_project")
    
    def test_check_directory_exists_empty(self):
        """Test directory check when directory doesn't exist."""
        with patch('pathlib.Path.exists', return_value=False):
            # Should not raise exception
            self.command._check_directory_exists(self.test_project_name)
    
    def test_check_directory_exists_empty_dir(self):
        """Test directory check when directory exists but is empty."""
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.iterdir', return_value=[]):
                # Should not raise exception
                self.command._check_directory_exists(self.test_project_name)
    
    def test_check_directory_exists_non_empty(self):
        """Test check_directory_exists when directory exists and is not empty."""
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.iterdir', return_value=['file1.txt']):
                with pytest.raises(ProjectError, match="already exists and is not empty"):
                    self.command._check_directory_exists(self.test_project_name)
    
    def test_check_directory_exists_permission_error(self):
        """Test check_directory_exists with permission error."""
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.iterdir', side_effect=PermissionError("Permission denied")):
                with pytest.raises(ProjectError, match="Permission denied"):
                    self.command._check_directory_exists(self.test_project_name)
    
    def test_generate_secret_key(self):
        """Test secret key generation."""
        key = self.command._generate_secret_key()
        
        assert len(key) == 50
        assert all(c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*(-_=+)' for c in key)
    
    def test_generate_secret_key_uniqueness(self):
        """Test that generated secret keys are unique."""
        keys = [self.command._generate_secret_key() for _ in range(10)]
        
        # All keys should be different
        assert len(set(keys)) == 10
    
    @patch('secrets.choice')
    def test_generate_secret_key_with_mock(self, mock_choice):
        """Test secret key generation with mocked randomness."""
        mock_choice.side_effect = ['a'] * 50  # Return 'a' 50 times
        
        key = self.command._generate_secret_key()
        
        assert key == 'a' * 50
        assert mock_choice.call_count == 50
    
    def test_generate_random_password(self):
        """Test random password generation."""
        password = self.command._generate_random_password()
        
        assert len(password) == 16
        assert all(c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789' for c in password)
    
    def test_generate_random_password_custom_length(self):
        """Test random password generation with custom length."""
        password = self.command._generate_random_password(24)
        
        assert len(password) == 24
    
    def test_get_template_variables(self):
        """Test template variables generation."""
        variables = self.command._get_template_variables(self.test_project_name)
        
        assert variables['project_name'] == self.test_project_name
        assert variables['project_name_upper'] == self.test_project_name.upper()
        assert variables['project_name_title'] == "Test Project"
        assert 'secret_key' in variables
        assert len(variables['secret_key']) == 50
    
    @patch('shutil.copytree')
    @patch('quickscale.commands.init_command.InitCommand._sync_template_modules')
    @patch('quickscale.commands.init_command.InitCommand.validate_project_name')
    def test_execute_success(self, mock_validate, mock_sync, mock_copytree):
        """Test successful project initialization."""
        # Mock validation to pass
        mock_validate.return_value = None
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('pathlib.Path.cwd', return_value=Path(temp_dir)):
                # Mock template directory exists
                with patch('pathlib.Path.exists', return_value=True):
                    self.command.execute(self.test_project_name)
                    
                    # Verify methods were called
                    mock_validate.assert_called_once_with(self.test_project_name)
                    mock_copytree.assert_called_once()
                    mock_sync.assert_called_once()
    
    def test_execute_validation_error(self):
        """Test project initialization with validation error."""
        with pytest.raises(ValidationError):
            self.command.execute("123invalid")  # Invalid name
    
    @patch('pathlib.Path.exists', return_value=True)
    def test_execute_directory_error(self, mock_exists):
        """Test project initialization with directory error."""
        # Mock that project directory already exists
        with pytest.raises(ProjectError, match="already exists"):
            self.command.execute(self.test_project_name)
    
    @patch('pathlib.Path.exists')
    @patch('shutil.copytree')
    def test_execute_mkdir_error(self, mock_copytree, mock_exists):
        """Test project initialization with template directory missing."""
        # Mock template directory doesn't exist
        mock_exists.return_value = False
        
        with pytest.raises(ProjectError, match="Template directory not found"):
            self.command.execute(self.test_project_name)


class TestInitCommandIntegration:
    """Integration tests for InitCommand."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.command = InitCommand()
    
    @patch('shutil.copytree')
    @patch('quickscale.commands.init_command.InitCommand._sync_template_modules')
    @patch('quickscale.commands.init_command.InitCommand.validate_project_name')
    def test_complete_project_initialization(self, mock_validate, mock_sync, mock_copytree):
        """Test complete project initialization flow."""
        # Mock validation to pass
        mock_validate.return_value = None
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('pathlib.Path.cwd', return_value=Path(temp_dir)):
                # Mock template directory exists
                with patch('pathlib.Path.exists', return_value=True):
                    project_name = "test_integration_project"
                    self.command.execute(project_name)
                    
                    # Verify template processing was called
                    mock_validate.assert_called_once_with(project_name)
                    mock_copytree.assert_called_once()
                    mock_sync.assert_called_once()
    
    @patch('shutil.copytree')
    @patch('quickscale.commands.init_command.InitCommand._sync_template_modules')
    @patch('quickscale.commands.init_command.InitCommand.validate_project_name')
    def test_error_cleanup(self, mock_validate, mock_sync, mock_copytree):
        """Test that template processing error is properly handled."""
        # Mock validation to pass
        mock_validate.return_value = None
        mock_copytree.side_effect = OSError("Template copy failed")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('pathlib.Path.cwd', return_value=Path(temp_dir)):
                # Mock template directory exists
                with patch('pathlib.Path.exists', return_value=True):
                    project_name = "test_cleanup_project"
                    
                    with pytest.raises(ProjectError, match="Failed to create project"):
                        self.command.execute(project_name)
