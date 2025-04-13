import os
import pytest
import logging
import shutil
import builtins
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open, call

from quickscale.commands.project_commands import BuildProjectCommand
from quickscale.commands.command_utils import copy_with_vars

class TestStaticAssetsCopying:
    
    @pytest.fixture
    def build_command(self):
        cmd = BuildProjectCommand()
        cmd.logger = logging.getLogger("test_logger")
        cmd.templates_dir = Path("templates")  # Set templates_dir to avoid NoneType error
        cmd.variables = {
            'project_name': 'test_project',
            'pg_user': 'admin',
            'pg_password': 'adminpasswd'
        }
        return cmd
    
    @patch('pathlib.Path.mkdir')
    @patch('quickscale.commands.project_commands.copy_with_vars')
    def test_static_assets_are_copied(self, mock_copy, mock_mkdir, build_command):
        # Create a more complete mock structure
        with patch('pathlib.Path.is_dir') as mock_is_dir:
            with patch('pathlib.Path.glob') as mock_glob:
                # Setup mocks
                mock_is_dir.return_value = True
                
                # Create mock files
                mock_file1 = MagicMock(spec=Path)
                mock_file1.is_file.return_value = True
                mock_file1.relative_to.return_value = Path('css/style.css')
                mock_file1.__str__.return_value = 'templates/static/css/style.css'
                
                mock_file2 = MagicMock(spec=Path)
                mock_file2.is_file.return_value = True
                mock_file2.relative_to.return_value = Path('js/app.js')
                mock_file2.__str__.return_value = 'templates/static/js/app.js'
                
                # Setup glob to return our mock files
                mock_glob.return_value = [mock_file1, mock_file2]
                
                # Call the method
                build_command.setup_static_dirs()
                
                # Verify the static dirs were created
                mock_mkdir.assert_called()
                
                # Verify file copying
                assert mock_copy.call_count == 2
                mock_copy.assert_has_calls([
                    call(mock_file1, Path('static/css/style.css'), build_command.logger, **build_command.variables),
                    call(mock_file2, Path('static/js/app.js'), build_command.logger, **build_command.variables)
                ], any_order=True)
    
    @patch('pathlib.Path.mkdir')
    @patch('quickscale.commands.project_commands.copy_with_vars')
    def test_no_static_files_copied_when_dir_missing(self, mock_copy, mock_mkdir, build_command):
        # Mock Path.is_dir to return False for the static dir
        with patch('pathlib.Path.is_dir') as mock_is_dir:
            mock_is_dir.return_value = False
            
            # Call the method
            build_command.setup_static_dirs()
            
            # Verify static dirs were still created
            mock_mkdir.assert_called()
            
            # Verify no files were copied
            mock_copy.assert_not_called()

# Test the copy_with_vars function directly
class TestCopyWithVars:
    
    @patch('quickscale.commands.command_utils.is_binary_file')
    @patch('pathlib.Path.is_file')
    @patch('pathlib.Path.mkdir')  # Mock mkdir since we don't need to verify it
    @patch('builtins.open', new_callable=mock_open, read_data="Hello ${name}")
    @patch('os.chmod')
    def test_text_file_variable_replacement(self, mock_chmod, mock_file, mock_mkdir, mock_is_file, mock_is_binary):
        # Setup mocks
        logger = logging.getLogger('test_logger')
        src_file = Path("templates/test.txt")
        dest_file = Path("output/test.txt")
        
        # Configure mocks
        mock_is_file.return_value = True  # Source file exists
        mock_is_binary.return_value = False  # Not a binary file
        
        # Call the function
        copy_with_vars(src_file, dest_file, logger, name="World")
        
        # Verify file was opened for reading and writing
        mock_file.assert_any_call(src_file, 'r', encoding='utf-8')
        mock_file.assert_any_call(dest_file, 'w', encoding='utf-8')
        
        # Verify variable substitution
        handle = mock_file()
        handle.write.assert_called_once_with("Hello World")
    
    @patch('quickscale.commands.command_utils.is_binary_file')
    @patch('pathlib.Path.is_file')
    @patch('pathlib.Path.mkdir')  # Mock mkdir since we don't need to verify it
    @patch('shutil.copy2')
    @patch('os.chmod')
    def test_binary_file_copy(self, mock_chmod, mock_copy2, mock_mkdir, mock_is_file, mock_is_binary):
        # Setup mocks
        logger = logging.getLogger('test_logger')
        src_file = Path("templates/image.png")
        dest_file = Path("output/image.png")
        
        # Configure mocks
        mock_is_file.return_value = True  # Source file exists
        mock_is_binary.return_value = True  # This is a binary file
        
        # Call the function
        copy_with_vars(src_file, dest_file, logger)
        
        # Verify binary copy was used
        mock_copy2.assert_called_once_with(src_file, dest_file) 