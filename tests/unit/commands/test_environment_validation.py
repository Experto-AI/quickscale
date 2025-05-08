import pytest
import logging
from unittest.mock import patch, MagicMock
from pathlib import Path
import os

from quickscale.commands.init_command import InitCommand
from quickscale.utils.error_manager import ProjectError, ValidationError

class TestEnvironmentValidation:
    """Tests for the environment validation functionality"""
        
    @pytest.fixture
    def init_command(self):
        """Setup an InitCommand fixture for testing"""
        cmd = InitCommand()
        cmd.logger = logging.getLogger("test_logger")
        return cmd
    
    def test_validation_functionality_placeholder(self):
        """Placeholder for environment validation tests.
        
        This test serves as a reminder that environment validation
        functionality is expected to be implemented in the future.
        The original tests were removed as they depended on a 
        'validate_environment' method that doesn't exist in InitCommand.
        """
        pass

class TestInitCommandValidation:
    """Tests for InitCommand validation functionality"""
    
    @pytest.fixture
    def init_command(self):
        """Setup an InitCommand fixture for testing"""
        cmd = InitCommand()
        cmd.logger = logging.getLogger("test_logger")
        return cmd
    
    def test_validate_project_name_valid(self, init_command):
        """Test that valid project names are accepted"""
        # Test valid project names
        valid_names = ["project", "my_project", "project123", "Project_123"]
        
        for name in valid_names:
            with patch('pathlib.Path.exists', return_value=False):
                # Should not raise any exceptions
                init_command.validate_project_name(name)
    
    def test_validate_project_name_invalid(self, init_command):
        """Test that invalid project names are rejected"""
        # Test invalid project names
        invalid_names = ["123project", "project-name", "project.name", "project name"]
        
        for name in invalid_names:
            with pytest.raises(ValidationError):
                init_command.validate_project_name(name)
    
    def test_validate_project_dir_exists(self, init_command):
        """Test that validation fails when project directory already exists"""
        with patch('pathlib.Path.exists', return_value=True):
            with pytest.raises(ProjectError):
                init_command.validate_project_name("existing_project")
    
    @patch('shutil.copytree')
    @patch('pathlib.Path.exists')
    def test_init_command_template_missing(self, mock_exists, mock_copytree, init_command):
        """Test that init command fails when template directory is missing"""
        # Setup so template directory doesn't exist
        mock_exists.return_value = False
        
        with pytest.raises(ProjectError, match="Template directory not found"):
            init_command.execute("test_project")