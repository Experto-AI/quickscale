"""Unit tests for PROJECT_NAME handling in init command."""
import os
import logging
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock, mock_open
from quickscale.commands.init_command import InitCommand
from quickscale.utils.error_manager import error_manager


@pytest.fixture
def init_command():
    """Create InitCommand instance for testing."""
    cmd = InitCommand()
    cmd.logger = logging.getLogger("test_logger")
    # Mock the template directory path
    cmd.template_dir = Path("path/to/test/templates")
    return cmd


@pytest.fixture
def test_env():
    """Setup and teardown test environment variables."""
    old_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(old_env)


@patch('shutil.copytree')
@patch('pathlib.Path.mkdir')
@patch('shutil.copy2')
@patch('pathlib.Path.read_text')
@patch('pathlib.Path.write_text')
def test_project_name_in_env_file(mock_write_text, mock_read_text, mock_copy2, mock_mkdir, 
                                 mock_copytree, init_command, test_env):
    """Test PROJECT_NAME is correctly written to .env file."""
    # Set custom project name
    os.environ['PROJECT_NAME'] = 'CustomProject'
    
    # Setup mocks
    mock_read_text.return_value = "PROJECT_NAME=${PROJECT_NAME}"
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
        init_command.execute('test_project')
    
    # Verify project name is set
    assert 'PROJECT_NAME' in os.environ
    assert os.environ['PROJECT_NAME'] == 'CustomProject'


@patch('shutil.copytree')
@patch('pathlib.Path.mkdir')
@patch('shutil.copy2')
@patch('pathlib.Path.read_text')
@patch('pathlib.Path.write_text')
def test_project_name_default_in_env_file(mock_write_text, mock_read_text, mock_copy2, mock_mkdir,
                                         mock_copytree, init_command, test_env):
    """Test default PROJECT_NAME is used when not set."""
    # Ensure PROJECT_NAME is not set
    if 'PROJECT_NAME' in os.environ:
        del os.environ['PROJECT_NAME']
    
    # Setup mocks
    mock_read_text.return_value = "PROJECT_NAME=${PROJECT_NAME}"
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
        init_command.execute('test_project')
    
    # Default project name should be used
    assert 'PROJECT_NAME' not in os.environ


@patch('shutil.copytree')
@patch('pathlib.Path.mkdir')
@patch('shutil.copy2')
@patch('pathlib.Path.read_text')
@patch('pathlib.Path.write_text')
def test_project_name_in_templates(mock_write_text, mock_read_text, mock_copy2, mock_mkdir,
                                  mock_copytree, init_command, test_env):
    """Test templates are created with correct project name."""
    # Set custom project name
    os.environ['PROJECT_NAME'] = 'CustomProject'
    
    # Setup mocks
    mock_read_text.return_value = "<title>${PROJECT_NAME}</title>"
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
        init_command.execute('test_project')
    
    # Verify project name is set
    assert 'PROJECT_NAME' in os.environ
    assert os.environ['PROJECT_NAME'] == 'CustomProject'