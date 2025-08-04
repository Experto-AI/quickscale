"""Additional unit tests for the ProjectManager class to increase coverage."""
import json
import os
import sys
import subprocess
from pathlib import Path
import tempfile
from unittest.mock import patch, MagicMock, mock_open
import pytest

from quickscale.commands.project_manager import ProjectManager


class TestProjectManagerAdditional:
    """Additional tests for the ProjectManager class to increase coverage."""
    
    def test_check_running_containers_with_no_directory(self):
        """Test check_running_containers when the project directory doesn't exist."""
        mock_result = MagicMock()
        mock_result.stdout = "test-web\ntest-db"
        
        with patch('subprocess.run', return_value=mock_result), \
             patch('pathlib.Path.exists', return_value=False):
            
            result = ProjectManager.check_running_containers()
            
            assert result is not None
            assert result['project_name'] == 'test'
            assert 'test-web' in result['containers']
            assert 'test-db' in result['containers']
            assert result['has_directory'] is False
    
    def test_check_running_containers_with_empty_output(self):
        """Test check_running_containers with empty output."""
        mock_result = MagicMock()
        mock_result.stdout = ""
        
        with patch('subprocess.run', return_value=mock_result):
            result = ProjectManager.check_running_containers()
            assert result is None
    
    def test_stop_containers_with_exception(self):
        """Test stop_containers when subprocess.run raises an exception."""
        with patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'docker compose down')):
            # It should propagate the exception
            with pytest.raises(subprocess.CalledProcessError):
                ProjectManager.stop_containers('test-project')
    
    def test_get_project_state_with_containers(self):
        """Test get_project_state when containers are running."""
        mock_containers = {
            'project_name': 'test',
            'containers': ['test-web', 'test-db'],
            'has_directory': True
        }
        
        with patch.object(ProjectManager, 'check_project_exists', return_value=True), \
             patch.object(ProjectManager, 'check_running_containers', return_value=mock_containers), \
             patch('pathlib.Path.cwd', return_value=Path('/path/to/myproject')):
            
            state = ProjectManager.get_project_state()
            
            assert state['has_project'] is True
            assert state['project_dir'] == Path('/path/to/myproject')
            assert state['project_name'] == 'myproject'
            assert state['containers'] == mock_containers
    
    def test_write_tracking_file_real_file(self):
        """Test write_tracking_file with a real temporary file."""
        data = {"project_name": "myproject", "key": "value"}
        
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
            try:
                result = ProjectManager.write_tracking_file(temp_file.name, data)
                assert result is True
                
                # Verify file contents
                with open(temp_file.name, 'r') as f:
                    read_data = json.load(f)
                    assert read_data == data
            finally:
                # Clean up the file
                os.unlink(temp_file.name)
    
    def test_read_tracking_file_malformed_json(self):
        """Test read_tracking_file with malformed JSON."""
        mock_file = mock_open(read_data="this is not valid json")
        
        with patch('builtins.open', mock_file), \
             patch('sys.stderr.write') as mock_write:
            
            result = ProjectManager.read_tracking_file('test.json')
            
            assert result is None
            # Check that an error was written to stderr
            mock_write.assert_called_once()
            # Since we can't easily predict the exact error message, just check it was called
    
    def test_get_tracking_param_non_string(self):
        """Test get_tracking_param with a non-string value."""
        mock_data = {"int_param": 123, "bool_param": True, "list_param": [1, 2, 3]}
        
        with patch.object(ProjectManager, 'read_tracking_file', return_value=mock_data):
            # Non-string values should be converted to strings
            assert ProjectManager.get_tracking_param('test.json', 'int_param') == "123"
            assert ProjectManager.get_tracking_param('test.json', 'bool_param') == "True"
            assert ProjectManager.get_tracking_param('test.json', 'list_param') == "[1, 2, 3]"
    
    def test_get_project_name_with_empty_file(self):
        """Test get_project_name with an empty tracking file."""
        with patch.object(ProjectManager, 'read_tracking_file', return_value={}):
            result = ProjectManager.get_project_name('test.json')
            assert result is None
    
    def test_write_tracking_file_permission_error(self):
        """Test write_tracking_file with permission error."""
        data = {"key": "value"}
        
        with patch('builtins.open', side_effect=PermissionError("Permission denied")), \
             patch('sys.stderr.write') as mock_write:
            
            result = ProjectManager.write_tracking_file('test.json', data)
            
            assert result is False
            mock_write.assert_called_once_with('Error saving project data: Permission denied\n')
    
    def test_read_tracking_file_with_permission_error(self):
        """Test read_tracking_file with permission error."""
        with patch('builtins.open', side_effect=PermissionError("Permission denied")), \
             patch('sys.stderr.write') as mock_write:
            
            result = ProjectManager.read_tracking_file('test.json')
            
            assert result is None
            mock_write.assert_called_once_with('Error reading project data: Permission denied\n')
    
    def test_read_tracking_file_with_unicode_decode_error(self):
        """Test read_tracking_file with UnicodeDecodeError."""
        with patch('builtins.open', side_effect=UnicodeDecodeError('utf-8', b'test', 0, 1, 'invalid')), \
             patch('sys.stderr.write') as mock_write:
            
            result = ProjectManager.read_tracking_file('test.json')
            
            assert result is None
            mock_write.assert_called_once()  # Can't check exact message due to complexity of UnicodeDecodeError str 