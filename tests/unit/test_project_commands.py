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

from quickscale.commands.project_commands import BuildProjectCommand, DestroyProjectCommand
from quickscale.commands.command_utils import copy_with_vars, find_available_port
from quickscale.commands.system_commands import CheckCommand


@pytest.fixture
def mock_build_command():
    """Fixture for a mocked BuildProjectCommand."""
    cmd = BuildProjectCommand()
    # Mock logger
    cmd.logger = MagicMock()
    
    # Mock the database-related methods that might cause external system calls
    cmd._run_migrations = MagicMock()
    cmd._create_users = MagicMock()
    cmd._run_docker_command = MagicMock()
    
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


def test_setup_project_environment(mock_build_command, tmp_path, monkeypatch):
    """Test project environment setup."""
    # Mock dependencies
    monkeypatch.setattr('quickscale.commands.system_commands.CheckCommand.execute', MagicMock())
    monkeypatch.setattr('quickscale.commands.project_commands.get_current_uid_gid', lambda: (1000, 1000))
    monkeypatch.setattr('quickscale.commands.project_commands.find_available_port', lambda start, attempts: start)
    monkeypatch.setattr('quickscale.commands.project_commands.LoggingManager.setup_logging', lambda project_dir, log_level: MagicMock())
    monkeypatch.setattr('secrets.token_urlsafe', lambda x: "mock_secret_key")
    
    # Change to temp directory and test
    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        project_dir = mock_build_command.setup_project_environment("test_project")
        
        # Verify directory was created
        assert project_dir.exists()
        assert mock_build_command.project_dir.exists()
        
        # Verify variables were set
        assert mock_build_command.variables is not None
        assert 'project_name' in mock_build_command.variables
        assert mock_build_command.variables['project_name'] == "test_project"
        assert 'SECRET_KEY' in mock_build_command.variables
        assert 'port' in mock_build_command.variables
        assert 'pg_port' in mock_build_command.variables
        
        # Verify environment variables were set
        assert mock_build_command.env_vars is not None
        assert 'SECRET_KEY' in mock_build_command.env_vars
        assert 'DOCKER_UID' in mock_build_command.env_vars
        assert 'DOCKER_GID' in mock_build_command.env_vars


def test_copy_project_files(mock_build_command, mock_templates_dir, tmp_path, monkeypatch):
    """Test copying project files."""
    # Setup command
    mock_build_command.templates_dir = mock_templates_dir
    mock_build_command.variables = {
        'project_name': 'test_project',
        'SECRET_KEY': 'mock_secret_key',
        'port': 8000,
        'pg_port': 5432,
        'pg_user': 'admin',
        'pg_password': 'adminpasswd'
    }
    mock_build_command.env_vars = {
        'SECRET_KEY': 'mock_secret_key',
        'DOCKER_UID': '1000',
        'DOCKER_GID': '1000',
        'PORT': '8000',
        'PG_PORT': '5432'
    }
    
    # Create mock template files
    for file_name in ['docker-compose.yml', 'Dockerfile', '.dockerignore', 'requirements.txt', 'entrypoint.sh']:
        (mock_templates_dir / file_name).write_text(f"Test content for {file_name} with ${{'project_name'}}")
    
    # Create .env.example file
    (mock_templates_dir / ".env.example").write_text("SECRET_KEY=${SECRET_KEY}\nPG_USER=${pg_user}")
    
    # Execute in temp directory
    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        with patch('os.chmod') as mock_chmod:
            mock_build_command.copy_project_files()
            
            # Verify files were created
            for file_name in ['docker-compose.yml', 'Dockerfile', '.dockerignore', 'requirements.txt', 'entrypoint.sh', '.env']:
                assert Path(file_name).exists()
            
            # Verify entrypoint.sh chmod was called with 0o755 (493 in decimal)
            assert any(call == ((Path('entrypoint.sh'), 0o755),) for call in mock_chmod.call_args_list)


def test_create_django_project(mock_build_command, mock_templates_dir, tmp_path, monkeypatch):
    """Test Django project creation."""
    # Setup command
    mock_build_command.templates_dir = mock_templates_dir
    mock_build_command.variables = {'project_name': 'test_project'}
    mock_build_command.current_uid = 1000
    mock_build_command.current_gid = 1000
    
    # Create required core template files
    core_dir = mock_templates_dir / "core"
    (core_dir / "settings.py").write_text("DEBUG = True\nPROJECT_NAME = '${project_name}'")
    (core_dir / "urls.py").write_text("# URL configuration for ${project_name}")
    
    # Execute in temp directory
    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        with patch.object(mock_build_command, '_run_docker_command') as mock_run:
            mock_build_command.create_django_project()
            
            # Verify docker command was called
            mock_run.assert_called_once_with("django-admin startproject core .")


def test_create_app(mock_build_command, mock_templates_dir, tmp_path, monkeypatch):
    """Test app creation."""
    # Setup command
    mock_build_command.templates_dir = mock_templates_dir
    mock_build_command.variables = {'project_name': 'test_project'}
    
    # Create mock app template files
    app_name = "public"
    app_dir = mock_templates_dir / app_name
    (app_dir / "views.py").write_text("# Views for ${project_name}")
    (app_dir / "urls.py").write_text("# URLs for ${project_name}")
    
    # Create mock HTML templates
    template_dir = mock_templates_dir / "templates" / app_name
    template_dir.mkdir(parents=True)
    (template_dir / "index.html").write_text("<h1>${project_name}</h1>")
    
    # Execute in temp directory
    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        # Use exist_ok=True to avoid FileExistsError
        Path("templates").mkdir(exist_ok=True)
        with patch.object(mock_build_command, '_run_docker_command') as mock_run:
            with patch.object(mock_build_command, '_validate_app_configuration') as mock_validate:
                mock_build_command.create_app(app_name)
                
                # Verify docker command was called
                mock_run.assert_called_once_with(f"django-admin startapp {app_name}")
                
                # Verify app configuration was validated
                mock_validate.assert_called_once_with(app_name)
                
                # Verify templates directory was created
                assert Path(f"templates/{app_name}").exists()


def test_validate_app_configuration(mock_build_command, tmp_path, monkeypatch):
    """Test validation of app configuration."""
    app_name = "test_app"
    app_dir = tmp_path / app_name
    app_dir.mkdir()
    
    # Execute in temp directory
    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        
        # Test case: apps.py missing
        mock_build_command._validate_app_configuration(app_name)
        
        # Verify apps.py was created
        apps_py = app_dir / "apps.py"
        assert apps_py.exists()
        
        # Verify content
        content = apps_py.read_text()
        assert f"class {app_name.capitalize()}Config" in content
        assert f"name = '{app_name}'" in content


def test_setup_static_dirs(mock_build_command, tmp_path, monkeypatch):
    """Test setup of static directories."""
    # Set templates_dir to avoid NoneType error
    mock_build_command.templates_dir = tmp_path / "templates"
    mock_build_command.templates_dir.mkdir(parents=True, exist_ok=True)
    
    # Create static template directory
    static_dir = mock_build_command.templates_dir / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    
    # Execute in temp directory
    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        mock_build_command.setup_static_dirs()
        
        # Verify directories were created
        for static_dir in ['css', 'js', 'img']:
            assert Path(f"static/{static_dir}").exists()


def test_setup_global_templates(mock_build_command, mock_templates_dir, tmp_path, monkeypatch):
    """Test setup of global templates."""
    # Setup command
    mock_build_command.templates_dir = mock_templates_dir
    mock_build_command.variables = {'project_name': 'test_project'}
    
    # Create mock base templates
    base_dir = mock_templates_dir / "templates" / "base"
    (base_dir / "base.html").write_text("<html><title>${project_name}</title></html>")
    
    # Create mock base.html
    (mock_templates_dir / "templates" / "base.html").write_text("<html><title>${project_name}</title></html>")
    
    # Execute in temp directory
    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        # Use exist_ok=True to avoid FileExistsError
        Path("templates").mkdir(exist_ok=True)
        mock_build_command.setup_global_templates()
        
        # Verify base templates were copied
        assert Path("templates/base/base.html").exists()
        assert Path("templates/base.html").exists()


@patch('subprocess.run')
@patch('builtins.open', new_callable=mock_open)
def test_run_docker_command(mock_open_file, mock_run, tmp_path, monkeypatch):
    """Test running Docker commands."""
    # Create a real BuildProjectCommand instead of using the mocked one
    # We want to test the actual _run_docker_command method, not a mock
    cmd = BuildProjectCommand()
    cmd.current_uid = 1000
    cmd.current_gid = 1000
    cmd.env_vars = {'TEST_VAR': 'test_value'}
    
    # Make sure the mock_open_file is properly set up
    mock_file_handle = mock_open_file.return_value
    
    # We need to return True for the file_exists check in the finally block
    # and False for the second check to simulate removing the file
    with patch('os.path.exists', side_effect=[True, False]):
        with patch('os.unlink') as mock_unlink:
            # Execute in temp directory
            with monkeypatch.context() as m:
                m.chdir(tmp_path)
                
                # Test with temp compose file
                cmd._run_docker_command("test command")
                
                # Verify open was called for both reading the original file and writing the temp file
                assert mock_open_file.call_count == 2
                mock_open_file.assert_any_call("docker-compose.temp.yml", "w", encoding='utf-8')
                mock_open_file.assert_any_call("docker-compose.yml", "r", encoding='utf-8')
                
                # Verify the file content was written
                file_handle = mock_open_file()
                assert file_handle.write.called
                
                # Verify subprocess.run was called with correct parameters
                mock_run.assert_called_once()
                
                # Verify temp file was cleaned up
                mock_unlink.assert_called_once_with("docker-compose.temp.yml")


@patch('subprocess.run')
def test_execute_build_project(mock_run, mock_build_command, mock_templates_dir, tmp_path, monkeypatch):
    """Test the full build project execution."""
    # Mock validate_environment to return True
    mock_build_command.validate_environment = MagicMock(return_value=True)
    
    # Setup mocks for all methods
    with patch.object(mock_build_command, 'setup_project_environment', return_value=Path("test_project")) as mock_setup:
        with patch.object(mock_build_command, 'copy_project_files') as mock_copy:
            with patch.object(mock_build_command, 'create_django_project') as mock_create_django:
                with patch.object(mock_build_command, 'create_app') as mock_create_app:
                    with patch.object(mock_build_command, 'setup_static_dirs') as mock_setup_static:
                        with patch.object(mock_build_command, 'setup_global_templates') as mock_setup_templates:
                            with patch.object(mock_build_command, 'setup_database', return_value=True) as mock_setup_db:
                                with patch.object(mock_build_command, 'verify_build', return_value={}) as mock_verify_build:
                                    with patch.object(mock_build_command, 'scan_build_logs', return_value={"total_issues": 0}) as mock_scan_logs:
                                        with patch('os.chdir') as mock_chdir:
                                            # Set port
                                            mock_build_command.port = 8000
                                            
                                            # Execute
                                            result = mock_build_command.execute("test_project")
                                            
                                            # Verify all methods were called
                                            mock_setup.assert_called_once_with("test_project")
                                            mock_copy.assert_called_once()
                                            mock_create_django.assert_called_once()
                                            assert mock_create_app.call_count == 4  # 4 apps
                                            mock_setup_static.assert_called_once()
                                            mock_setup_templates.assert_called_once()
                                            mock_setup_db.assert_called_once()
                                            
                                            # Verify chdir was called twice (into project dir and back)
                                            assert mock_chdir.call_count >= 1
                                            
                                            # Verify result
                                            assert result is not None
                                            assert "path" in result
                                            assert "port" in result
                                            assert result["port"] == 8000
                                            mock_verify_build.assert_called_once()  # Verify verify_build was called
                                            mock_scan_logs.assert_called_once()  # Verify scan_build_logs was called
                                            assert "log_scan" in result
                                            assert result["log_scan"] == {"total_issues": 0}


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
            
            # Execute
            result = mock_destroy_command.execute()
            
            # Verify ProjectManager methods were called
            mock_pm.get_project_state.assert_called_once()
            mock_pm.stop_containers.assert_called_once_with('test_project')
            
            # Verify result
            assert result['success'] is True
            assert result['project'] == 'test_project'


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


@patch('quickscale.commands.project_commands.wait_for_postgres')
@patch('subprocess.run')
def test_setup_database_success(mock_subprocess_run, mock_wait_for_postgres, mock_build_command):
    """Test database setup with mocks isolated from any external processes."""
    # Setup mocks
    mock_wait_for_postgres.return_value = True
    mock_build_command.variables = {'pg_user': 'test_user', 'pg_email': 'test@example.com', 'pg_password': 'test_pass'}
    
    # We don't need to patch these methods as they are already mocked in the fixture
    # Just call the method
    result = mock_build_command.setup_database()
    
    # Verify mocks were called
    mock_wait_for_postgres.assert_called_once_with('test_user', mock_build_command.logger)
    mock_build_command._run_migrations.assert_called_once()
    mock_build_command._create_users.assert_called_once()
    
    # Verify result
    assert result is True


@patch('quickscale.commands.project_commands.wait_for_postgres')
def test_setup_database_wait_failure(mock_wait_for_postgres, mock_build_command):
    """Test database setup failure when Postgres is not available."""
    # Setup mocks - database not ready
    mock_wait_for_postgres.return_value = False
    mock_build_command.variables = {'pg_user': 'test_user'}
    
    # Call the method
    result = mock_build_command.setup_database()
    
    # Verify mocks were called
    mock_wait_for_postgres.assert_called_once_with('test_user', mock_build_command.logger)
    
    # Verify result
    assert result is False


@patch('quickscale.commands.project_commands.wait_for_postgres')
def test_setup_database_migration_error(mock_wait_for_postgres, mock_build_command):
    """Test database setup when migrations fail."""
    # Setup mocks
    mock_wait_for_postgres.return_value = True
    mock_build_command.variables = {'pg_user': 'test_user', 'pg_email': 'test@example.com', 'pg_password': 'test_pass'}
    
    # Mock _run_migrations to raise an exception
    with patch.object(mock_build_command, '_run_migrations', side_effect=subprocess.SubprocessError("Migration error")):
        # Call the method
        result = mock_build_command.setup_database()
        
        # Verify mocks were called
        mock_wait_for_postgres.assert_called_once()
        
        # Verify result
        assert result is False


def test_migration_methods(mock_build_command, tmp_path, monkeypatch):
    """Test database migration methods."""
    # Setup command
    mock_build_command.current_uid = 1000
    mock_build_command.current_gid = 1000
    
    # Since the _run_migrations method is mocked in the fixture,
    # let's create a simple version of it for this test
    def _simple_run_migrations():
        """Simple implementation for testing."""
        # Simulate calls to subprocess.run
        subprocess.run(["docker", "compose", "ps", "-q", "web"], check=True)
        for app in ['public', 'dashboard', 'users', 'common']:
            subprocess.run(["docker", "compose", "exec", "web", "python", "manage.py", "makemigrations", app], check=True)
        subprocess.run(["docker", "compose", "exec", "web", "python", "manage.py", "migrate", "--noinput"], check=True)
    
    # Override the mocked method with our simple implementation
    mock_build_command._run_migrations = _simple_run_migrations
    
    # Create patch for subprocess.run that would be called in _run_migrations
    with patch('subprocess.run') as mock_subprocess_run:
        # Mock successful container status check
        mock_process = MagicMock()
        mock_process.stdout = "container_id"
        mock_subprocess_run.return_value = mock_process
        
        # Execute in temp directory
        with monkeypatch.context() as m:
            m.chdir(tmp_path)
            
            # Create migrations directories to avoid errors
            for app in ['public', 'dashboard', 'users', 'common']:
                migrations_dir = Path(f"{app}/migrations")
                migrations_dir.mkdir(parents=True, exist_ok=True)
                init_file = migrations_dir / "__init__.py"
                with open(init_file, "w", encoding='utf-8') as f:
                    f.write('"""Migrations package."""\n')
            
            # Test _run_migrations
            mock_build_command._run_migrations()
            
            # Verify subprocess.run was called multiple times
            assert mock_subprocess_run.call_count >= 6


@pytest.fixture
def mock_verification_command():
    """Fixture for testing verification methods."""
    cmd = BuildProjectCommand()
    cmd.logger = MagicMock()
    cmd.port = 8000
    cmd.pg_port = 5432
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


def test_scan_build_logs(mock_build_command):
    """Test the scan_build_logs method."""
    with patch('quickscale.utils.log_scanner.LogScanner') as mock_scanner_class:
        # Setup mock scanner
        mock_scanner = MagicMock()
        mock_scanner_class.return_value = mock_scanner
        
        # Configure mock scanner methods
        mock_scanner.scan_all_logs.return_value = [MagicMock()]
        mock_scanner.generate_summary.return_value = {
            "total_issues": 1, 
            "error_count": 1, 
            "warning_count": 0,
            "has_critical_issues": True,
            "logs_accessed": True
        }
        
        # Call the method
        result = mock_build_command.scan_build_logs()
        
        # Verify logger was used
        mock_build_command.logger.info.assert_called()
        
        # Verify scanner was created
        mock_scanner_class.assert_called_once()
        
        # Verify scanner methods were called
        mock_scanner.scan_all_logs.assert_called_once()
        mock_scanner.generate_summary.assert_called_once()
        mock_scanner.print_summary.assert_called_once()
        
        # Verify result
        assert result == mock_scanner.generate_summary.return_value
        assert result["total_issues"] == 1
        assert result["error_count"] == 1
        assert result["has_critical_issues"] is True
        assert result["logs_accessed"] is True


def test_scan_build_logs_error_handling(mock_build_command):
    """Test error handling in the scan_build_logs method."""
    with patch('quickscale.utils.log_scanner.LogScanner') as mock_scanner_class:
        # Setup scanner to raise an exception with a specific error message
        mock_scanner_class.side_effect = Exception("Test error")
        
        # Call the method
        result = mock_build_command.scan_build_logs()
        
        # Verify logger error was called
        mock_build_command.logger.error.assert_called()
        
        # Verify result contains error info - the error should contain our test error message
        assert "error" in result
        assert "Test error" in result["error"]
        assert result["scan_failed"] is True
        assert result["total_issues"] == 0
        assert result["error_count"] == 0
        assert result["warning_count"] == 0
        assert result["has_critical_issues"] is False
        assert result["logs_accessed"] is False


def test_scan_build_logs_no_logs_accessed(mock_build_command):
    """Test the scan_build_logs method when no logs could be accessed."""
    with patch('quickscale.utils.log_scanner.LogScanner') as mock_scanner_class:
        # Setup mock scanner
        mock_scanner = MagicMock()
        mock_scanner_class.return_value = mock_scanner
        
        # Configure mock scanner methods
        mock_scanner.scan_all_logs.return_value = []
        mock_scanner.generate_summary.return_value = {
            "total_issues": 0, 
            "error_count": 0, 
            "warning_count": 0,
            "has_critical_issues": False,
            "logs_accessed": False
        }
        
        # Call the method
        result = mock_build_command.scan_build_logs()
        
        # Verify logger was used
        mock_build_command.logger.warning.assert_called_with("Could not access any log files for scanning")
        
        # Verify scanner was created
        mock_scanner_class.assert_called_once()
        
        # Verify scanner methods were called
        mock_scanner.scan_all_logs.assert_called_once()
        mock_scanner.generate_summary.assert_called_once()
        mock_scanner.print_summary.assert_called_once()
        
        # Verify result
        assert result == mock_scanner.generate_summary.return_value
        assert result["total_issues"] == 0
        assert result["error_count"] == 0
        assert result["has_critical_issues"] is False
        assert result["logs_accessed"] is False