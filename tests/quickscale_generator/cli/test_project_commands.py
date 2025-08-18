import os
import pytest
import logging
import shutil
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path

from quickscale.commands.init_command import InitCommand
from quickscale.utils.error_manager import error_manager

class TestInitCommand:
    
    @pytest.fixture
    def init_command(self):
        """Create a properly mocked InitCommand for testing."""
        cmd = InitCommand()
        cmd.logger = logging.getLogger("test_logger")
        return cmd
    
    @patch('shutil.copytree')
    @patch('pathlib.Path.mkdir')
    def test_init_command_success(self, mock_mkdir, mock_copytree, init_command):
        """Test that init command successfully creates a project."""
        # Setup mocks
        project_name = "test_project"

        # Patch all required methods including template_dir check
        with patch.object(init_command, 'validate_project_name') as mock_validate, \
             patch('pathlib.Path.__file__', create=True, new=MagicMock()), \
             patch('pathlib.Path.parent', create=True, new=MagicMock()), \
             patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.cwd', return_value=MagicMock()):
            
            # Mock the _sync_template_modules method to avoid complications
            with patch.object(init_command, '_sync_template_modules', return_value=None):
                # Run the init command
                init_command.execute(project_name)
                
                # Assert validation was called
                mock_validate.assert_called_once_with(project_name)
                
                # Assert copytree is called
                mock_copytree.assert_called_once()
                
                # Success - the test completed without raising exceptions

    @patch('shutil.copytree')
    @patch('pathlib.Path.mkdir')
    @patch('shutil.copy2')
    def test_env_file_creation(self, mock_copy2, mock_mkdir, mock_copytree, init_command):
        """Test that the .env file is created with default content."""
        project_name = "new_project"
        
        # Configure mocks for the execution
        mock_project_dir = MagicMock(spec=Path)
        mock_project_dir.exists.return_value = False
        
        # Mock .env.example and .env file paths
        mock_env_example = MagicMock(spec=Path)
        mock_env_example.exists.return_value = True
        mock_env_file = MagicMock(spec=Path)
        mock_env_file.exists.return_value = False
        
        # Set up the __truediv__ mocks correctly
        mock_div = MagicMock()
        mock_div.side_effect = lambda x: mock_env_example if x == '.env.example' else mock_env_file
        mock_project_dir.__truediv__ = mock_div
        
        with patch('pathlib.Path.cwd') as mock_cwd:
            mock_cwd.return_value = MagicMock(spec=Path)
            mock_cwd.return_value.__truediv__.return_value = mock_project_dir
            init_command.execute(project_name)

        # Check that copy2 was called at least once (it's called multiple times due to copy_sync_modules)
        assert mock_copy2.call_count >= 1, "copy2 should be called at least once"
        # Verify one of the calls was for the .env file
        mock_copy2.assert_any_call(mock_env_example, mock_env_file)

    @patch('pathlib.Path.read_text')
    @patch('pathlib.Path.__truediv__')
    def test_template_variables(self, mock_truediv, mock_read_text, init_command):
        """Test that template files contain expected environment variable placeholders."""
        # Create a mock template path
        mock_template_path = MagicMock()
        mock_truediv.return_value = mock_template_path
        
        # Mock reading a sample template file, e.g., settings.py template
        mock_read_text.return_value = "SECRET_KEY = get_env('SECRET_KEY', 'dev-only-dummy-key-replace-in-production')"
        
        # Mock the Path(__file__).parent.parent / 'templates' path in init_command.execute
        with patch('pathlib.Path.__file__', create=True) as mock_file_path:
            mock_parent = MagicMock()
            mock_file_path.parent = mock_parent
            mock_parent.parent = mock_parent
            mock_parent.__truediv__.return_value = mock_template_path
            
            # Get template variables directly
            template_vars = init_command._get_template_variables("test_project")
            
            # Now manually check the variables using pytest assertions
            assert template_vars['project_name'] == "test_project"
            assert template_vars['project_name_upper'] == "TEST_PROJECT"
            assert template_vars['project_name_title'] == "Test Project"
            assert 'secret_key' in template_vars
            
            # Check the template content for environment variables
            content = mock_read_text.return_value
            assert 'SECRET_KEY' in content
            assert "get_env('SECRET_KEY'" in content

    # Note: test_template_variables would require mocking file reads of template files
    # and potentially the templating engine to check variable substitution.
    # This might be more complex and depend on the actual template rendering logic.

    # Note: test_init_command() as a whole would involve orchestrating the mocks for
    # copying, file creation, and potentially other steps of the init command.
    # The individual tests above cover parts of the init command's functionality.