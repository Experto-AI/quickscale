"""Unit tests for the ProjectManager class."""
import json
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

from quickscale.commands.project_manager import ProjectManager


class TestProjectManager:
    """Tests for the ProjectManager class."""
    
    def test_get_project_root(self):
        """Test get_project_root returns the right project root."""
        with patch('os.path.abspath', return_value='/path/to/quickscale/commands/file.py'):
            project_root = ProjectManager.get_project_root()
            assert project_root == Path('/path/to/quickscale')
    
    def test_check_project_exists_true(self):
        """Test check_project_exists when project exists."""
        with patch('pathlib.Path.is_file', return_value=True):
            # Should not print message
            assert ProjectManager.check_project_exists(print_message=False) is True
    
    def test_check_project_exists_false_with_message(self):
        """Test check_project_exists when project doesn't exist and should print message."""
        with patch('pathlib.Path.is_file', return_value=False), \
             patch('quickscale.utils.message_manager.MessageManager.error') as mock_error:
            result = ProjectManager.check_project_exists(print_message=True)
            
            assert result is False
            mock_error.assert_called_once_with(ProjectManager.PROJECT_NOT_FOUND_MESSAGE)
    
    def test_check_project_exists_false_without_message(self):
        """Test check_project_exists when project doesn't exist and should not print message."""
        with patch('pathlib.Path.is_file', return_value=False), \
             patch('builtins.print') as mock_print:
            result = ProjectManager.check_project_exists(print_message=False)
            
            assert result is False
            mock_print.assert_not_called()
    
    def test_get_project_state_with_project(self):
        """Test get_project_state when a project exists."""
        with patch.object(ProjectManager, 'check_project_exists', return_value=True), \
             patch.object(ProjectManager, 'check_running_containers', return_value=None), \
             patch('pathlib.Path.cwd', return_value=Path('/path/to/myproject')):
            
            state = ProjectManager.get_project_state()
            
            assert state['has_project'] is True
            assert state['project_dir'] == Path('/path/to/myproject')
            assert state['project_name'] == 'myproject'
            assert state['containers'] is None
    
    def test_get_project_state_without_project(self):
        """Test get_project_state when no project exists."""
        with patch.object(ProjectManager, 'check_project_exists', return_value=False), \
             patch.object(ProjectManager, 'check_running_containers', return_value=None), \
             patch('pathlib.Path.cwd', return_value=Path('/path/to/myproject')):
            
            state = ProjectManager.get_project_state()
            
            assert state['has_project'] is False
            assert state['project_dir'] is None
            assert state['project_name'] is None
            assert state['containers'] is None
    
    def test_check_test_directory_exists(self):
        """Test check_test_directory when test directory exists."""
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.is_dir', return_value=True):
            
            result = ProjectManager.check_test_directory()
            
            assert result is not None
            assert result['directory'] == Path('test')
    
    def test_check_test_directory_not_exists(self):
        """Test check_test_directory when test directory doesn't exist."""
        with patch('pathlib.Path.exists', return_value=False):
            result = ProjectManager.check_test_directory()
            assert result is None
    
    def test_check_test_directory_not_dir(self):
        """Test check_test_directory when test path is not a directory."""
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.is_dir', return_value=False):
            
            result = ProjectManager.check_test_directory()
            assert result is None
    
    def test_check_running_containers_with_containers(self):
        """Test check_running_containers when containers are running."""
        mock_result = MagicMock()
        mock_result.stdout = "test-web\ntest-db\nother-container"
        
        with patch('subprocess.run', return_value=mock_result), \
             patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.is_dir', return_value=True):
            
            result = ProjectManager.check_running_containers()
            
            assert result is not None
            assert result['project_name'] == 'test'
            assert 'test-web' in result['containers']
            assert 'test-db' in result['containers']
            assert result['has_directory'] is True
    
    def test_check_running_containers_without_containers(self):
        """Test check_running_containers when no test containers are running."""
        mock_result = MagicMock()
        mock_result.stdout = "other-container\nanother-container"
        
        with patch('subprocess.run', return_value=mock_result):
            result = ProjectManager.check_running_containers()
            assert result is None
    
    def test_check_running_containers_with_empty_stdout(self):
        """Test check_running_containers when stdout is empty."""
        mock_result = MagicMock()
        mock_result.stdout = ""
        
        with patch('subprocess.run', return_value=mock_result):
            result = ProjectManager.check_running_containers()
            assert result is None
    
    def test_stop_containers(self):
        """Test stop_containers runs the correct command."""
        with patch('subprocess.run') as mock_run:
            ProjectManager.stop_containers('test-project')
            
            mock_run.assert_called_once_with(
                ["docker", "compose", "-p", "test-project", "down", "-v", "--rmi", "all"], 
                check=True
            )
    
    def test_read_tracking_file_success(self):
        """Test read_tracking_file with a valid file."""
        mock_data = {"project_name": "myproject", "key": "value"}
        mock_file = mock_open(read_data=json.dumps(mock_data))
        
        with patch('builtins.open', mock_file), \
             patch.object(ProjectManager, 'get_project_root', return_value=Path('/path/to/quickscale')):
            
            result = ProjectManager.read_tracking_file('test.json')
            
            assert result is not None
            assert result['key'] == 'value'
            assert result['project_name'] == '/path/to/quickscale/myproject'
    
    def test_read_tracking_file_no_project_name(self):
        """Test read_tracking_file with a file not containing project_name."""
        mock_data = {"key": "value"}
        mock_file = mock_open(read_data=json.dumps(mock_data))
        
        with patch('builtins.open', mock_file):
            result = ProjectManager.read_tracking_file('test.json')
            
            assert result is not None
            assert result['key'] == 'value'
            assert 'project_name' not in result
    
    def test_read_tracking_file_not_found(self):
        """Test read_tracking_file when file is not found."""
        with patch('builtins.open', side_effect=FileNotFoundError()):
            result = ProjectManager.read_tracking_file('nonexistent.json')
            assert result is None
    
    def test_read_tracking_file_other_exception(self):
        """Test read_tracking_file when other exception occurs."""
        with patch('builtins.open', side_effect=Exception('Unknown error')), \
             patch('sys.stderr.write') as mock_write:
            
            result = ProjectManager.read_tracking_file('test.json')
            
            assert result is None
            mock_write.assert_called_once_with('Error reading project data: Unknown error\n')
    
    def test_write_tracking_file_success(self):
        """Test write_tracking_file with successful write."""
        data = {"project_name": "myproject", "key": "value"}
        mock_file = mock_open()
        
        with patch('builtins.open', mock_file):
            result = ProjectManager.write_tracking_file('test.json', data)
            
            assert result is True
            mock_file.assert_called_once_with('test.json', 'w')
            mock_file().write.assert_called()
    
    def test_write_tracking_file_exception(self):
        """Test write_tracking_file when exception occurs."""
        data = {"key": "value"}
        
        with patch('builtins.open', side_effect=Exception('Write error')), \
             patch('sys.stderr.write') as mock_write:
            
            result = ProjectManager.write_tracking_file('test.json', data)
            
            assert result is False
            mock_write.assert_called_once_with('Error saving project data: Write error\n')
    
    def test_get_tracking_param_exists(self):
        """Test get_tracking_param when parameter exists."""
        mock_data = {"param1": "value1", "param2": "value2"}
        
        with patch.object(ProjectManager, 'read_tracking_file', return_value=mock_data):
            result = ProjectManager.get_tracking_param('test.json', 'param1')
            assert result == "value1"
    
    def test_get_tracking_param_not_exists(self):
        """Test get_tracking_param when parameter doesn't exist."""
        mock_data = {"param1": "value1"}
        
        with patch.object(ProjectManager, 'read_tracking_file', return_value=mock_data):
            result = ProjectManager.get_tracking_param('test.json', 'param2')
            assert result is None
    
    def test_get_tracking_param_file_not_found(self):
        """Test get_tracking_param when file doesn't exist."""
        with patch.object(ProjectManager, 'read_tracking_file', return_value=None):
            result = ProjectManager.get_tracking_param('nonexistent.json', 'param')
            assert result is None
    
    def test_get_project_name(self):
        """Test get_project_name which is a wrapper around get_tracking_param."""
        with patch.object(ProjectManager, 'get_tracking_param', return_value="test-project"):
            result = ProjectManager.get_project_name('test.json')
            assert result == "test-project"
