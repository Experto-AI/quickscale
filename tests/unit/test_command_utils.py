"""Tests for command utility functions."""
import os
import socket
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from quickscale.commands.command_utils import (
    get_current_uid_gid,
    copy_with_vars,
    copy_files_recursive,
    wait_for_postgres,
    find_available_port,
    is_binary_file,
    fix_permissions,
    generate_secret_key,
    DOCKER_COMPOSE_COMMAND
)


def test_get_current_uid_gid():
    """Test getting current user and group ID."""
    uid, gid = get_current_uid_gid()
    
    # Basic validation
    assert isinstance(uid, int)
    assert isinstance(gid, int)
    assert uid > 0
    assert gid > 0


def test_generate_secret_key():
    """Test generating a secret key."""
    # Generate keys of different lengths
    key1 = generate_secret_key(20)
    key2 = generate_secret_key(30)
    key3 = generate_secret_key()  # default length
    
    # Verify lengths
    assert len(key1) == 20
    assert len(key2) == 30
    assert len(key3) == 50
    
    # Verify uniqueness
    assert key1 != key2
    assert key2 != key3
    assert key1 != key3


def test_is_binary_file(tmp_path):
    """Test binary file detection."""
    # Create a text file
    text_file = tmp_path / "text.txt"
    text_file.write_text("This is a text file")
    
    # Create a binary file
    binary_file = tmp_path / "binary.bin"
    binary_file.write_bytes(b'\x00\x01\x02\x03')
    
    # Test detection
    assert is_binary_file(binary_file) is True
    assert is_binary_file(text_file) is False


def test_copy_with_vars(tmp_path):
    """Test copying files with variable substitution."""
    # Create source file with variables
    source_file = tmp_path / "source.txt"
    source_file.write_text("Project: ${project_name}, Port: ${port}, User: ${user}")
    
    # Target file
    target_file = tmp_path / "target.txt"
    
    # Create a logger mock
    logger = MagicMock()
    
    # Variables to substitute
    variables = {
        'project_name': 'test_project',
        'port': 8000,
        'user': 'admin'
    }
    
    # Call the function
    copy_with_vars(source_file, target_file, logger, **variables)
    
    # Verify the file was created
    assert target_file.exists()
    
    # Verify content with variables substituted
    content = target_file.read_text()
    assert "Project: test_project" in content
    assert "Port: 8000" in content
    assert "User: admin" in content
    
    # Test with non-existent source file
    nonexistent_file = tmp_path / "nonexistent.txt"
    
    # Should raise an error
    with pytest.raises(FileNotFoundError):
        copy_with_vars(nonexistent_file, target_file, logger)


def test_copy_files_recursive(tmp_path):
    """Test recursive file copying."""
    # Create source directory structure
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    
    # Create subdirectories
    (source_dir / "subdir1").mkdir()
    (source_dir / "subdir2").mkdir()
    
    # Create test files
    (source_dir / "file1.txt").write_text("File 1 content ${var}")
    (source_dir / "subdir1" / "file2.txt").write_text("File 2 content ${var}")
    (source_dir / "subdir2" / "file3.txt").write_text("File 3 content ${var}")
    
    # Target directory
    target_dir = tmp_path / "target"
    
    # Create a logger mock
    logger = MagicMock()
    
    # Call the function
    copy_files_recursive(source_dir, target_dir, logger, var="replaced")
    
    # Verify directories were created
    assert target_dir.exists()
    assert (target_dir / "subdir1").exists()
    assert (target_dir / "subdir2").exists()
    
    # Verify files were copied
    assert (target_dir / "file1.txt").exists()
    assert (target_dir / "subdir1" / "file2.txt").exists()
    assert (target_dir / "subdir2" / "file3.txt").exists()
    
    # Verify file contents with variable substitution
    assert (target_dir / "file1.txt").read_text() == "File 1 content replaced"
    assert (target_dir / "subdir1" / "file2.txt").read_text() == "File 2 content replaced"
    assert (target_dir / "subdir2" / "file3.txt").read_text() == "File 3 content replaced"


@patch('time.sleep')
@patch('subprocess.run')
def test_wait_for_postgres_success(mock_run, mock_sleep):
    """Test waiting for PostgreSQL to be ready (success case)."""
    # Mock successful connection after a few attempts
    mock_process1 = MagicMock()
    mock_process1.returncode = 1
    
    mock_process2 = MagicMock()
    mock_process2.returncode = 1
    
    mock_process3 = MagicMock()
    mock_process3.returncode = 0
    
    mock_run.side_effect = [mock_process1, mock_process2, mock_process3]
    
    # Create a logger mock
    logger = MagicMock()
    
    # Call the function (should retry and succeed)
    result = wait_for_postgres("testuser", logger, max_attempts=5, delay=1)
    
    # Verify function calls
    assert mock_run.call_count == 3
    # Sleep is called between attempts (one before each retry)
    assert mock_sleep.call_count == 2
    assert result is True


@patch('time.sleep')
@patch('subprocess.run')
def test_wait_for_postgres_timeout(mock_run, mock_sleep):
    """Test waiting for PostgreSQL to be ready (timeout case)."""
    # All attempts fail
    mock_process = MagicMock()
    mock_process.returncode = 1
    
    # Setup mocks - sleep is called after every attempt
    mock_run.side_effect = [mock_process, mock_process]
    
    # Create a logger mock
    logger = MagicMock()
    
    # Call with max_attempts=2
    result = wait_for_postgres("testuser", logger, max_attempts=2, delay=1)
    
    # Verify function calls
    assert mock_run.call_count == 2
    # With 2 attempts, sleep is called after each attempt, so it's called 2 times
    assert mock_sleep.call_count == 2
    assert result is False


@patch('socket.socket')
def test_find_available_port(mock_socket):
    """Test finding an available port."""
    # Setup the socket mock to simulate a port being in use and then available
    socket_instance = MagicMock()
    mock_socket.return_value.__enter__.return_value = socket_instance
    
    # First simulate testing port 50000, which should be available
    socket_instance.connect_ex.return_value = 1  # Non-zero means port is available
    
    # Test with start port
    start_port = 50000
    port = find_available_port(start_port, 5)
    
    # Verify port was returned and it's the start port (since it was available)
    assert port == start_port
    
    # Now test with a port that's supposed to be in use
    used_port = 12345
    # First call: port is in use (return 0)
    # Second call: next port is available (return non-zero)
    socket_instance.connect_ex.side_effect = [0, 1]
    
    # Function should find a different port (12346)
    port = find_available_port(used_port, 5)
    assert port == used_port + 1


@patch('subprocess.run')
def test_fix_permissions(mock_run, tmp_path):
    """Test fixing file permissions."""
    # Create a mock logger
    logger = MagicMock()
    
    # Create a directory that exists
    dir_path = tmp_path / "test_dir"
    dir_path.mkdir()
    
    # Mock is_dir to return True for our test directory
    with patch.object(Path, 'is_dir', return_value=True):
        # Call function with a directory that exists
        fix_permissions(dir_path, 1000, 1000, logger)
    
        # Verify run was called with correct arguments
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert any(DOCKER_COMPOSE_COMMAND in arg for arg in args)
        assert "chown" in args
        assert "1000:1000" in args
    
    # Reset the mock
    mock_run.reset_mock()
    
    # Test with non-existent directory
    nonexistent_dir = tmp_path / "nonexistent"
    
    # Mock is_dir to return False for our nonexistent directory
    with patch.object(Path, 'is_dir', return_value=False):
        # Should log a warning but not raise an exception
        fix_permissions(nonexistent_dir, 1000, 1000, logger)
        logger.warning.assert_called_once()
        mock_run.assert_not_called()
    
    # Reset mocks
    mock_run.reset_mock()
    logger.reset_mock()
    
    # Test with subprocess error
    with patch.object(Path, 'is_dir', return_value=True):
        mock_run.side_effect = subprocess.SubprocessError("Command failed")
        
        # Should raise the exception
        with pytest.raises(subprocess.SubprocessError):
            fix_permissions(dir_path, 1000, 1000, logger)
        logger.error.assert_called_once() 