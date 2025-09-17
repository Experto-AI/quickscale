"""Tests for command utility functions."""
import socket
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from quickscale.commands.command_utils import (
    DOCKER_COMPOSE_COMMAND,
    copy_files_recursive,
    copy_with_vars,
    find_available_port,
    fix_permissions,
    is_binary_file,
)


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
@patch('socket.socket')
def test_find_available_ports(mock_socket, mock_subprocess_run, mock_sleep):
    """Test finding multiple available ports directly."""
    # Import the function
    from quickscale.commands.command_utils import find_available_ports
    
    # Setup mock socket behavior
    socket_instance = MagicMock()
    mock_socket.return_value.__enter__.return_value = socket_instance
    
    # Make socket.bind() always succeed (indicating ports are available)
    socket_instance.bind.side_effect = None
    
    # Test finding 2 ports
    ports = find_available_ports(count=2, start_port=8000, max_attempts=10)
    
    # Should get 2 sequential ports
    assert len(ports) == 2
    assert ports == [8000, 8001]
    
    # Reset mock for next test
    socket_instance.bind.reset_mock()
    
    # Test with a different start port
    ports = find_available_ports(count=2, start_port=9000, max_attempts=10)
    
    # Should get 2 sequential ports
    assert len(ports) == 2
    assert ports == [9000, 9001]


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
        fix_permissions(dir_path, 1000, 1000, logger, pg_user="admin")
    
        # Verify run was called with correct arguments
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        # Check if docker-compose command parts are in the args
        assert any(cmd_part in args for cmd_part in DOCKER_COMPOSE_COMMAND)
        assert "chown" in args
        assert "1000:1000" in args
    
    # Reset the mock
    mock_run.reset_mock()
    
    # Test with non-existent directory
    nonexistent_dir = tmp_path / "nonexistent"
    
    # Mock is_dir to return False for our nonexistent directory
    with patch.object(Path, 'is_dir', return_value=False):
        # Should log a warning but not raise an exception
        fix_permissions(nonexistent_dir, 1000, 1000, logger, pg_user="admin")
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
            fix_permissions(dir_path, 1000, 1000, logger, pg_user="admin")
        logger.error.assert_called_once()


@patch('socket.socket')
def test_find_available_port(mock_socket):
    """Test finding an available port."""
    # Setup mock socket behavior
    socket_instance = MagicMock()
    mock_socket.return_value.__enter__.return_value = socket_instance
    
    # Make socket.bind() succeed on the first try
    socket_instance.bind.return_value = None
    
    # Call the function
    port = find_available_port(8000)
    
    # Verify it returns the first port
    assert port == 8000
    socket_instance.bind.assert_called_once()
    socket_instance.bind.assert_called_with(('127.0.0.1', 8000))
    
    # Reset mock
    socket_instance.bind.reset_mock()
    
    # Make socket.bind() fail on first port, succeed on second
    socket_instance.bind.side_effect = [socket.error, None]
    
    # Call the function
    port = find_available_port(8000)
    
    # Verify it returns the second port
    assert port == 8001


@patch('socket.socket')
def test_check_port_availability(mock_socket):
    """Test checking if a port is available."""
    # Import the function
    from quickscale.commands.command_utils import _check_port_availability
    
    # Setup mock socket behavior
    socket_instance = MagicMock()
    mock_socket.return_value.__enter__.return_value = socket_instance
    
    # Test when port is available (bind succeeds)
    socket_instance.bind.side_effect = None
    assert _check_port_availability(8000) is True
    socket_instance.bind.assert_called_with(('127.0.0.1', 8000))
    
    # Reset mock
    socket_instance.bind.reset_mock()
    
    # Test when port is unavailable (bind fails)
    socket_instance.bind.side_effect = socket.error("Address already in use")
    assert _check_port_availability(8000) is False
    socket_instance.bind.assert_called_with(('127.0.0.1', 8000))


@patch('socket.socket')
def test_find_available_port_in_range(mock_socket):
    """Test finding an available port within a specific range."""
    # Import the function
    from quickscale.commands.command_utils import _find_available_port_in_range
    
    # Setup mock socket behavior
    socket_instance = MagicMock()
    mock_socket.return_value.__enter__.return_value = socket_instance
    
    # Make all ports unavailable except 8002
    socket_instance.bind.side_effect = [
        socket.error("Address already in use"),  # 8000
        socket.error("Address already in use"),  # 8001
        None,                                    # 8002 - available
        socket.error("Address already in use")   # 8003
    ]
    
    # Call the function
    port = _find_available_port_in_range(8000, 8003)
    
    # Verify it returns the available port
    assert port == 8002
    assert socket_instance.bind.call_count == 3  # It should stop after finding the available port
    
    # Reset mock
    socket_instance.bind.reset_mock()
    
    # Make all ports unavailable
    socket_instance.bind.side_effect = socket.error("Address already in use")
    
    # Call the function
    port = _find_available_port_in_range(8000, 8003)
    
    # Verify it returns None
    assert port is None
    assert socket_instance.bind.call_count == 4  # It should try all ports


def test_find_port_in_sequential_range():
    """Test finding ports in a sequential range."""
    # Import the function
    from quickscale.commands.command_utils import _find_port_in_sequential_range
    
    # Setup a logger mock
    logger = MagicMock()
    
    # Setup test with mocked _check_port_availability
    with patch('quickscale.commands.command_utils._check_port_availability') as mock_check:
        # Make all ports available
        mock_check.return_value = True
        
        # Call the function
        available_ports = []
        result = _find_port_in_sequential_range(8000, 2, available_ports, 10, logger)
        
        # Verify it returns a list with the expected ports
        assert result == [8000, 8001]
        assert mock_check.call_count == 2
        
        # Reset mock
        mock_check.reset_mock()
        
        # Make some ports unavailable
        mock_check.side_effect = [False, True, True]  # 8000 unavailable, 8001-8002 available
        
        # Call the function
        available_ports = []
        result = _find_port_in_sequential_range(8000, 2, available_ports, 10, logger)
        
        # Verify it returns a list with the expected ports
        assert result == [8001, 8002]
        assert mock_check.call_count == 3


def test_find_port_in_common_ranges():
    """Test finding ports in common port ranges."""
    # Import the function
    from quickscale.commands.command_utils import _find_port_in_common_ranges
    
    # Setup a logger mock
    logger = MagicMock()
    
    # Setup test with mocked _check_port_availability
    with patch('quickscale.commands.command_utils._check_port_availability') as mock_check:
        # Make all ports available
        mock_check.return_value = True
        
        # Call the function
        available_ports = []
        result, attempts = _find_port_in_common_ranges(2, available_ports, 50, 0, logger)
        
        # Verify the function found ports and tracked attempts
        assert len(result) == 2
        assert attempts > 0
        assert mock_check.call_count == 2  # Called twice to find 2 ports
        
        # Reset mock
        mock_check.reset_mock()
        
        # Make all ports unavailable
        mock_check.return_value = False
        
        # Call the function with limited attempts
        available_ports = []
        result, attempts = _find_port_in_common_ranges(2, available_ports, 10, 0, logger)
        
        # Verify it couldn't find any ports and exhausted attempts
        assert result == []
        assert attempts == 10
        assert mock_check.call_count == 10


def test_find_port_in_random_ranges():
    """Test finding ports in random port ranges."""
    # Import the function
    from quickscale.commands.command_utils import _find_port_in_random_ranges
    
    # Setup a logger mock
    logger = MagicMock()
    
    # Setup test with mocked _check_port_availability and random.randint
    with patch('quickscale.commands.command_utils._check_port_availability') as mock_check, \
         patch('random.randint') as mock_randint:
        
        # Configure random to return sequential values for testing
        mock_randint.side_effect = [8100, 8101]
        
        # Make ports available
        mock_check.return_value = True
        
        # Call the function
        available_ports = []
        result = _find_port_in_random_ranges(2, available_ports, 50, 0, logger)
        
        # Verify it returns the expected ports
        assert result == [8100, 8101]
        assert mock_check.call_count == 2
        assert mock_randint.call_count == 2
        
        # Reset mocks
        mock_check.reset_mock()
        mock_randint.reset_mock()
        
        # Configure random to return duplicates, then unique values
        mock_randint.side_effect = [8100, 8100, 8101]
        
        # Make ports available
        mock_check.return_value = True
        
        # Call the function
        available_ports = []
        result = _find_port_in_random_ranges(2, available_ports, 50, 0, logger)
        
        # Verify it handles duplicates correctly
        assert result == [8100, 8101]
        assert mock_check.call_count == 2
        assert mock_randint.call_count == 3  # Called 3 times due to duplicate


def test_add_random_high_ports():
    """Test adding random high ports when other methods fail."""
    # Import the function directly to avoid import issues
    from quickscale.commands.command_utils import _add_random_high_ports
    
    # Setup a logger mock
    logger = MagicMock()
    
    # Setup test with mocked random.randint - use a simpler approach
    with patch('random.randint') as mock_randint:
        # Just return a fixed value to avoid potential memory issues
        mock_randint.return_value = 30000
        
        # Call the function with a small count
        available_ports = []
        result = _add_random_high_ports(1, available_ports, logger)
        
        # Verify the result
        assert len(result) == 1
        assert result[0] == 30000  # Should match our mocked return value
        assert mock_randint.call_count == 1  # Should be called once
        assert logger.warning.call_count >= 1  # Should log at least one warning

    
# Test the find_available_ports function with more complex scenarios
@patch('quickscale.commands.command_utils._find_port_in_sequential_range')
@patch('quickscale.commands.command_utils._find_port_in_common_ranges')
@patch('quickscale.commands.command_utils._find_port_in_random_ranges')
@patch('quickscale.commands.command_utils._add_random_high_ports')
def test_find_available_ports_fallback_strategies(
    mock_add_random, mock_random_ranges, mock_common_ranges, mock_sequential_range
):
    """Test find_available_ports with different fallback strategies."""
    # Import the function
    from quickscale.commands.command_utils import find_available_ports
    
    # Configure mocks for different test scenarios
    
    # Scenario 1: Sequential range succeeds
    mock_sequential_range.return_value = [8000, 8001]
    mock_common_ranges.return_value = ([], 0)
    mock_random_ranges.return_value = []
    mock_add_random.return_value = []
    
    # Call the function
    ports = find_available_ports(count=2, start_port=8000)
    
    # Verify the result
    assert ports == [8000, 8001]
    mock_sequential_range.assert_called_once()
    mock_common_ranges.assert_not_called()
    mock_random_ranges.assert_not_called()
    mock_add_random.assert_not_called()
    
    # Reset mocks
    mock_sequential_range.reset_mock()
    mock_common_ranges.reset_mock()
    mock_random_ranges.reset_mock()
    mock_add_random.reset_mock()
    
    # Scenario 2: Sequential range fails, common ranges succeed
    mock_sequential_range.return_value = []
    mock_common_ranges.return_value = ([9000, 9001], 20)
    
    # Call the function
    ports = find_available_ports(count=2, start_port=8000)
    
    # Verify the result
    assert ports == [9000, 9001]
    mock_sequential_range.assert_called_once()
    mock_common_ranges.assert_called_once()
    mock_random_ranges.assert_not_called()
    mock_add_random.assert_not_called()
    
    # Reset mocks
    mock_sequential_range.reset_mock()
    mock_common_ranges.reset_mock()
    mock_random_ranges.reset_mock()
    mock_add_random.reset_mock()
    
    # Scenario 3: Sequential and common ranges fail, random ranges succeed
    mock_sequential_range.return_value = []
    mock_common_ranges.return_value = ([], 50)
    mock_random_ranges.return_value = [10000, 10001]
    
    # Call the function
    ports = find_available_ports(count=2, start_port=8000)
    
    # Verify the result
    assert ports == [10000, 10001]
    mock_sequential_range.assert_called_once()
    mock_common_ranges.assert_called_once()
    mock_random_ranges.assert_called_once()
    mock_add_random.assert_not_called()
    
    # Reset mocks
    mock_sequential_range.reset_mock()
    mock_common_ranges.reset_mock()
    mock_random_ranges.reset_mock()
    mock_add_random.reset_mock()
    
    # Scenario 4: All strategies fail except fallback
    mock_sequential_range.return_value = []
    mock_common_ranges.return_value = ([], 50)
    mock_random_ranges.return_value = []
    mock_add_random.return_value = [20000, 20001]
    
    # Call the function
    ports = find_available_ports(count=2, start_port=8000)
    
    # Verify the result
    assert ports == [20000, 20001]
    mock_sequential_range.assert_called_once()
    mock_common_ranges.assert_called_once()
    mock_random_ranges.assert_called_once()
    mock_add_random.assert_called_once() 
