"""Unit tests for project commands."""
import os
import sys
import shutil
import socket
import secrets
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import pytest
import subprocess

from quickscale.commands.project_commands import DestroyProjectCommand
from quickscale.commands.init_command import InitCommand
from quickscale.commands.command_utils import copy_with_vars, find_available_port
from quickscale.commands.system_commands import CheckCommand


@pytest.fixture
def mock_init_command():
    """Fixture for a mocked InitCommand."""
    cmd = InitCommand()
    # Mock logger
    cmd.logger = MagicMock()
    
    # Set project_dir to a non-None value for log scanning tests
    cmd.project_dir = Path("/mock/project/path")
    
    return cmd


@pytest.fixture
def mock_templates_dir(tmp_path):
    """Create a mock templates directory with required files."""
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    
    # Copy fixture files to mock templates dir
    fixtures_dir = Path(__file__).parent / "fixtures"
    for fixture_file in ['docker-compose.yml', '.env.example']:
        fixture_path = fixtures_dir / fixture_file
        if fixture_path.exists():
            target_path = templates_dir / fixture_file
            target_path.write_text(fixture_path.read_text())
    
    # Create directories needed for template files
    (templates_dir / "core").mkdir()
    (templates_dir / "public").mkdir()
    (templates_dir / "templates").mkdir()
    (templates_dir / "templates" / "base").mkdir()
    
    return templates_dir


@pytest.fixture
def mock_destroy_command():
    """Fixture for a mocked DestroyProjectCommand."""
    cmd = DestroyProjectCommand()
    # Mock logger
    cmd.logger = MagicMock()
    return cmd


def test_init_command_project_creation(mock_init_command, tmp_path, monkeypatch):
    """Test that the init command properly creates a new project."""
    # Mock logging setup to avoid side effects
    monkeypatch.setattr('quickscale.utils.logging_manager.LoggingManager.setup_logging', lambda project_dir, log_level: MagicMock())
    
    # Set up mock for validate_project_name to avoid errors
    monkeypatch.setattr(mock_init_command, 'validate_project_name', MagicMock())
    
    # Mock template directory exists
    monkeypatch.setattr('pathlib.Path.exists', lambda self: True)
    monkeypatch.setattr('pathlib.Path.is_dir', lambda self: True)
    
    # Mock copytree to avoid actual file operations
    mock_copytree = MagicMock()
    monkeypatch.setattr('shutil.copytree', mock_copytree)
    
    # Change to temp directory and test
    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        result = mock_init_command.execute("test_project")
        
        # Verify validation was called
        mock_init_command.validate_project_name.assert_called_once_with("test_project")
        
        # Verify copy was attempted
        assert mock_copytree.call_count > 0


# Test for creating Django project removed - this functionality is now in InitCommand


# Test for creating Django app removed - this functionality is now in InitCommand


# Test for app validation removed - this functionality is now in InitCommand


# Test for static directories setup removed - this functionality is now in InitCommand


# Test for global templates setup removed - this functionality is now in InitCommand



# Test for build project execution removed - this functionality is now in InitCommand


def test_copy_with_vars_function(tmp_path):
    """Test the copy_with_vars utility function."""
    # Create source file with variables
    source_file = tmp_path / "source.txt"
    source_file.write_text("Project: ${project_name}, Port: ${port}")
    
    # Target file
    target_file = tmp_path / "target.txt"
    
    # Create a logger mock
    logger = MagicMock()
    
    # Call the function
    copy_with_vars(source_file, target_file, logger, project_name="test_project", port=8000)
    
    # Verify the file was created
    assert target_file.exists()
    
    # Verify variables were substituted
    content = target_file.read_text()
    assert "Project: test_project" in content
    assert "Port: 8000" in content


@patch('socket.socket')
def test_find_available_port_function(mock_socket):
    """Test the find_available_port function use within project commands module."""
    # Import the function that's actually used in project commands
    from quickscale.commands.command_utils import find_available_port
    
    # Setup minimal test to verify it's properly imported and functioning
    socket_instance = MagicMock()
    mock_socket.return_value.__enter__.return_value = socket_instance
    
    # Test that the function returns the start port when it's available
    socket_instance.bind.side_effect = None  # No error means port is available
    
    # Use a very small max_attempts value to ensure the test completes quickly
    port = find_available_port(8000, max_attempts=1)
    assert port == 8000
    assert socket_instance.bind.call_count <= 2
    
    # Note: Comprehensive testing is done in test_command_utils.py


def test_destroy_project_command(mock_destroy_command, tmp_path, monkeypatch):
    """Test the destroy project command execution."""
    # Create a project directory for testing
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    
    # Create some files in the project directory
    (project_dir / "docker-compose.yml").write_text("version: '3'\nservices:\n  web:\n    image: test")
    (project_dir / ".env").write_text("PORT=8000")
    
    # Mock project state
    project_state = {
        'has_project': True,
        'project_name': 'test_project',
        'project_dir': str(project_dir),
        'containers': None
    }
    
    # Mock confirm destruction to return True (yes)
    with patch.object(mock_destroy_command, '_confirm_destruction', return_value=True):
        # Mock ProjectManager
        with patch('quickscale.commands.project_commands.ProjectManager') as mock_pm:
            # Setup project state
            mock_pm.get_project_state.return_value = project_state
            with patch('shutil.rmtree') as mock_rmtree:
                # Default: should NOT delete images
                result = mock_destroy_command.execute()
                mock_pm.get_project_state.assert_called()
                mock_pm.stop_containers.assert_called_with('test_project', delete_images=False)
                assert result['success'] is True
                assert result['project'] == 'test_project'
                assert result['images_deleted'] is False

                # With delete_images True
                mock_pm.stop_containers.reset_mock()
                result2 = mock_destroy_command.execute(True)
                mock_pm.stop_containers.assert_called_with('test_project', delete_images=True)
                assert result2['success'] is True
                assert result2['project'] == 'test_project'
                assert result2['images_deleted'] is True


def test_destroy_project_cancelled(mock_destroy_command):
    """Test destroy command when user cancels the operation."""
    # Mock project state
    project_state = {
        'has_project': True,
        'project_name': 'test_project',
        'project_dir': '/mock/path',
        'containers': None
    }
    
    # Mock confirm destruction to return False (no)
    with patch.object(mock_destroy_command, '_confirm_destruction', return_value=False):
        # Mock ProjectManager
        with patch('quickscale.commands.project_commands.ProjectManager') as mock_pm:
            # Setup project state
            mock_pm.get_project_state.return_value = project_state
            
            # Execute
            result = mock_destroy_command.execute()
            
            # Verify result
            assert result['success'] is False
            assert result['reason'] == 'cancelled'


def test_destroy_project_no_project(mock_destroy_command):
    """Test destroy command when no project exists."""
    # Mock project state with no project
    project_state = {
        'has_project': False,
        'project_name': None,
        'project_dir': None,
        'containers': None
    }
    
    # Mock ProjectManager
    with patch('quickscale.commands.project_commands.ProjectManager') as mock_pm:
        # Setup project state
        mock_pm.get_project_state.return_value = project_state
        mock_pm.PROJECT_NOT_FOUND_MESSAGE = "No project found"
        
        # Execute
        result = mock_destroy_command.execute()
        
        # Verify result
        assert result['success'] is False
        assert result['reason'] == 'no_project'


# Test for database setup success removed - this functionality is now in InitCommand


# Test for database setup wait failure removed - this functionality is now in InitCommand


# Test for database setup migration error removed - this functionality is now in InitCommand


# Test for migration methods removed - this functionality is now in InitCommand


@pytest.fixture
def mock_verification_command():
    """Fixture for testing verification methods."""
    cmd = InitCommand()
    cmd.logger = MagicMock()
    cmd.port = 8000 if hasattr(cmd, 'port') else None
    cmd.pg_port = 5432 if hasattr(cmd, 'pg_port') else None
    cmd.variables = {
        'project_name': 'test_project',
        'pg_user': 'admin',
        'pg_password': 'adminpasswd',
        'pg_email': 'admin@test.com',
    }
    return cmd


def test_verify_container_status(mock_verification_command, monkeypatch):
    """Test verification of container status."""
    with patch('subprocess.run') as mock_run:
        # Mock successful container status and health checks for all subprocess.run calls
        mock_responses = [
            MagicMock(stdout="container_id\n", returncode=0),  # Web running
            MagicMock(stdout="container_id\n", returncode=0),  # DB running
            MagicMock(stdout="healthy\n", returncode=0),       # Web healthy
            MagicMock(stdout="server is running", returncode=0)  # DB healthy
        ]
        mock_run.side_effect = mock_responses

        # Execute the verification
        result = mock_verification_command._verify_container_status()

        # Verify the result
        assert result['web']['running'] is True
        assert result['web']['healthy'] is True
        assert result['db']['running'] is True
        assert result['db']['healthy'] is True
        assert result['success'] is True


def test_verify_container_status_failure(mock_verification_command, monkeypatch):
    """Test verification of container status with failures."""
    with patch('subprocess.run') as mock_run:
        # Mock responses for different container status scenarios
        mock_responses = [
            MagicMock(stdout="", returncode=1),               # Web not running
            MagicMock(stdout="container_id\n", returncode=0)  # DB running
            # No health checks will be executed because web container is not running
        ]
        mock_run.side_effect = mock_responses

        # Execute the verification
        result = mock_verification_command._verify_container_status()

        # Verify the result - since web is not running, we won't check health
        assert result['web']['running'] is False
        assert result['web']['healthy'] is False  # Should be false when not running
        assert result['db']['running'] is True
        assert result['db']['healthy'] is False  # Should be false since health check isn't run
        assert result['success'] is False


def test_verify_database_connectivity(mock_verification_command, monkeypatch):
    """Test verification of database connectivity."""
    # Mock project name directly for the test
    project_name = "test_project"
    # Ensure all necessary variables are set for the method call
    mock_verification_command.variables = {
        'project_name': project_name,
        'pg_user': 'test_user', 
        'pg_password': 'test_password',
        'pg_email': 'test@example.com'
    }

    with patch('subprocess.run') as mock_run:
        # Mock successful database connectivity checks
        mock_responses = [
            MagicMock(returncode=0),  # Database connection successful
            MagicMock(stdout="[X] auth.0001_initial\n[X] admin.0001_initial", returncode=0),  # Migrations applied
            MagicMock(stdout="Admin user exists: True\nRegular user exists: True", returncode=0)  # Users created
        ]
        mock_run.side_effect = mock_responses

        # Execute the verification, passing the project_name
        result = mock_verification_command._verify_database_connectivity(project_name)

        # Verify the result is True (method returns boolean)
        assert result is True


def test_verify_database_connectivity_failure(mock_verification_command, monkeypatch):
    """Test verification of database connectivity with failures."""
    # Mock project name directly for the test
    project_name = "test_project_fail"
    # Ensure all necessary variables are set for the method call
    mock_verification_command.variables = {
        'project_name': project_name,
        'pg_user': 'test_user_fail',
        'pg_password': 'test_password_fail',
        'pg_email': 'test_fail@example.com'
    }

    with patch('subprocess.run') as mock_run:
        # Mock subprocess.run to raise CalledProcessError for the db check command
        def side_effect(*args, **kwargs):
            command_args = args[0]
            # Correctly check if it's the docker exec command for the python script
            if (len(command_args) >= 7 and  # Need at least 7 elements
                command_args[0].endswith('docker-compose') and
                command_args[1] == 'exec' and
                command_args[3] == 'web' and  # Service name is at index 3
                command_args[4] == 'python' and # Command is at index 4
                command_args[5] == '-c' and    # Script flag is at index 5
                'psycopg2' in command_args[6]): # Script content is at index 6
                raise subprocess.CalledProcessError(1, command_args, stderr="Connection failed")
            # For any other subprocess calls, return a default MagicMock
            return MagicMock(returncode=0, stdout="", stderr="")
        mock_run.side_effect = side_effect

        # Execute the verification, passing the project_name
        result = mock_verification_command._verify_database_connectivity(project_name)

        # Verify the result is False (method returns boolean)
        assert result is False


def test_verify_web_service(mock_verification_command, monkeypatch):
    """Test verification of web service."""
    # Mock socket connection
    mock_socket = MagicMock()
    monkeypatch.setattr('socket.socket', lambda *args, **kwargs: mock_socket)

    # Mock urllib for static file check
    mock_response = MagicMock()
    mock_response.status = 200
    monkeypatch.setattr('urllib.request.urlopen', lambda *args, **kwargs: mock_response)
    monkeypatch.setattr('time.sleep', lambda x: None)  # Skip sleep

    # Execute the verification
    result = mock_verification_command._verify_web_service()

    # Verify the result
    assert result['responds'] is True
    assert result['static_files'] is True
    # The success field should depend only on 'responds', not on 'static_files'
    assert result['success'] is True


def test_verify_web_service_failure(mock_verification_command, monkeypatch):
    """Test verification of web service with failures."""
    # Mock socket connection that raises ConnectionRefusedError
    mock_socket = MagicMock()
    mock_socket.connect.side_effect = ConnectionRefusedError()
    monkeypatch.setattr('socket.socket', lambda *args, **kwargs: mock_socket)
    monkeypatch.setattr('time.sleep', lambda x: None)  # Skip sleep

    # Execute the verification
    result = mock_verification_command._verify_web_service()

    # Verify the result
    assert result['responds'] is False
    # Static files should be false because the web service doesn't respond
    assert result['static_files'] is False
    # Success should be false because 'responds' is false
    assert result['success'] is False


def test_verify_web_service_static_files_none(mock_verification_command, monkeypatch):
    """Test verification of web service with static files check skipped."""
    # Mock socket connection to simulate successful connection
    mock_socket = MagicMock()
    mock_socket_instance = MagicMock()
    mock_socket.return_value = mock_socket_instance
    monkeypatch.setattr('socket.socket', lambda *args, **kwargs: mock_socket)
    
    # Mock sock.connect to not raise an exception
    mock_socket_instance.connect = MagicMock()
    
    # Mock urllib to raise an exception for static file check
    def mock_urlopen(*args, **kwargs):
        raise Exception("Test exception")
        
    monkeypatch.setattr('urllib.request.urlopen', mock_urlopen)
    monkeypatch.setattr('time.sleep', lambda x: None)  # Skip sleep

    # Execute the verification
    result = mock_verification_command._verify_web_service()

    # Verify the result
    assert result['responds'] is True
    # Static files should be False because the check failed with an exception
    assert result['static_files'] is False
    # Success should be true because 'responds' is true, even if static_files is False
    assert result['success'] is True


# Test for scan build logs removed - this functionality is now in InitCommand


# Test for scan build logs error handling removed - this functionality is now in InitCommand


# Test for scan build logs with no logs accessed removed - this functionality is now in InitCommand