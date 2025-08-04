"""Comprehensive tests for command_utils with full coverage."""
import os
import shutil
import tempfile
import pytest
import subprocess
import socket
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock, call, mock_open
import string
import secrets

from quickscale.commands.command_utils import (
    get_current_uid_gid,
    generate_secret_key,
    is_binary_file,
    copy_with_vars,
    _copy_binary_file,
    _copy_text_file,
    copy_files_recursive,
    find_available_port,
    wait_for_postgres,
    fix_permissions,
    DOCKER_COMPOSE_COMMAND
)


class TestDockerComposeCommand:
    """Test Docker Compose command detection."""

    def test_docker_compose_command_exists(self):
        """Test that DOCKER_COMPOSE_COMMAND is defined."""
        assert DOCKER_COMPOSE_COMMAND is not None
        assert isinstance(DOCKER_COMPOSE_COMMAND, list)
        assert len(DOCKER_COMPOSE_COMMAND) > 0
        assert "docker" in " ".join(DOCKER_COMPOSE_COMMAND).lower()


class TestGetCurrentUidGid:
    """Test UID/GID retrieval functions."""

    @patch('os.getuid')
    @patch('os.getgid')
    def test_get_current_uid_gid(self, mock_getgid, mock_getuid):
        """Test getting current UID and GID."""
        mock_getuid.return_value = 1000
        mock_getgid.return_value = 1000
        
        uid, gid = get_current_uid_gid()
        assert uid == 1000
        assert gid == 1000


class TestGenerateSecretKey:
    """Test secret key generation."""

    def test_generate_secret_key_default_length(self):
        """Test secret key generation with default length."""
        key = generate_secret_key()
        assert len(key) == 50
        assert all(c in string.ascii_letters + string.digits + "!@#$%^&*(-_=+)" for c in key)

    def test_generate_secret_key_custom_length(self):
        """Test secret key generation with custom length."""
        key = generate_secret_key(32)
        assert len(key) == 32

    def test_generate_secret_key_zero_length(self):
        """Test secret key generation with zero length."""
        key = generate_secret_key(0)
        assert len(key) == 0
        assert key == ""

    def test_generate_secret_key_uniqueness(self):
        """Test that generated keys are unique."""
        key1 = generate_secret_key()
        key2 = generate_secret_key()
        assert key1 != key2

    def test_generate_secret_key_long_length(self):
        """Test secret key generation with very long length."""
        key = generate_secret_key(1000)
        assert len(key) == 1000


class TestIsBinaryFile:
    """Test binary file detection."""

    def setup_method(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_is_binary_file_text(self):
        """Test detection of text file."""
        text_file = Path(self.test_dir) / "test.txt"
        text_file.write_text("This is a text file", encoding="utf-8")
        
        assert not is_binary_file(text_file)

    def test_is_binary_file_binary(self):
        """Test detection of binary file with null bytes."""
        binary_file = Path(self.test_dir) / "test.bin"
        binary_file.write_bytes(b"This is \x00 binary file")
        
        assert is_binary_file(binary_file)

    def test_is_binary_file_unicode_decode_error(self):
        """Test detection when file can't be decoded as UTF-8."""
        binary_file = Path(self.test_dir) / "test.bin"
        binary_file.write_bytes(b"\xff\xfe\x00\x00")  # Invalid UTF-8
        
        assert is_binary_file(binary_file)

    def test_is_binary_file_io_error(self):
        """Test detection when file can't be opened."""
        non_existent_file = Path(self.test_dir) / "nonexistent.txt"
        
        assert is_binary_file(non_existent_file)

    def test_is_binary_file_empty(self):
        """Test detection of empty file."""
        empty_file = Path(self.test_dir) / "empty.txt"
        empty_file.touch()
        
        assert not is_binary_file(empty_file)

    def test_is_binary_file_large_text(self):
        """Test detection of large text file."""
        large_text_file = Path(self.test_dir) / "large.txt"
        large_content = "A" * 10000  # Larger than chunk size
        large_text_file.write_text(large_content, encoding="utf-8")
        
        assert not is_binary_file(large_text_file)


class TestCopyWithVars:
    """Test file copying with variable substitution."""

    def setup_method(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.src_dir = Path(self.test_dir) / "src"
        self.dest_dir = Path(self.test_dir) / "dest"
        self.src_dir.mkdir()
        self.dest_dir.mkdir()

    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_copy_with_vars_text_file(self):
        """Test copying text file with variable substitution."""
        src_file = self.src_dir / "template.txt"
        dest_file = self.dest_dir / "output.txt"
        src_file.write_text("Hello ${NAME}, your key is ${SECRET_KEY}", encoding="utf-8")
        
        logger = Mock()
        
        copy_with_vars(src_file, dest_file, logger, NAME="World", SECRET_KEY="test123")
        
        content = dest_file.read_text(encoding="utf-8")
        assert "Hello World" in content
        assert "test123" in content

    def test_copy_with_vars_binary_file(self):
        """Test copying binary file."""
        src_file = self.src_dir / "binary.bin"
        dest_file = self.dest_dir / "output.bin"
        binary_content = b"Binary \x00 content"
        src_file.write_bytes(binary_content)
        
        logger = Mock()
        
        copy_with_vars(src_file, dest_file, logger)
        
        assert dest_file.read_bytes() == binary_content

    def test_copy_with_vars_file_not_found(self):
        """Test copying non-existent file."""
        src_file = self.src_dir / "nonexistent.txt"
        dest_file = self.dest_dir / "output.txt"
        logger = Mock()
        
        with pytest.raises(FileNotFoundError):
            copy_with_vars(src_file, dest_file, logger)

    def test_copy_with_vars_creates_parent_dirs(self):
        """Test that parent directories are created."""
        src_file = self.src_dir / "template.txt"
        dest_file = self.dest_dir / "subdir" / "deep" / "output.txt"
        src_file.write_text("Content", encoding="utf-8")
        
        logger = Mock()
        
        copy_with_vars(src_file, dest_file, logger)
        
        assert dest_file.exists()
        assert dest_file.parent.exists()

    def test_copy_with_vars_auto_secret_key(self):
        """Test that SECRET_KEY is auto-generated if not provided."""
        src_file = self.src_dir / "template.txt"
        dest_file = self.dest_dir / "output.txt"
        src_file.write_text("Key: ${SECRET_KEY}", encoding="utf-8")
        
        logger = Mock()
        
        copy_with_vars(src_file, dest_file, logger)
        
        content = dest_file.read_text(encoding="utf-8")
        assert "Key: " in content
        assert "${SECRET_KEY}" not in content

    @patch('quickscale.commands.command_utils.is_binary_file')
    def test_copy_with_vars_exception_handling(self, mock_is_binary):
        """Test exception handling during copy."""
        src_file = self.src_dir / "template.txt"
        dest_file = self.dest_dir / "output.txt"
        src_file.write_text("Content", encoding="utf-8")
        
        mock_is_binary.side_effect = Exception("Test error")
        logger = Mock()
        
        with pytest.raises(Exception, match="Test error"):
            copy_with_vars(src_file, dest_file, logger)


class TestCopyBinaryFile:
    """Test binary file copying."""

    def setup_method(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch('shutil.copy2')
    @patch('os.chmod')
    def test_copy_binary_file(self, mock_chmod, mock_copy2):
        """Test binary file copying."""
        src_file = Path(self.test_dir) / "src.bin"
        dest_file = Path(self.test_dir) / "subdir" / "dest.bin"
        logger = Mock()
        
        _copy_binary_file(src_file, dest_file, logger)
        
        # Verify parent directory creation
        assert dest_file.parent.exists()
        # Verify file copy
        mock_copy2.assert_called_once_with(src_file, dest_file)
        # Verify permissions
        mock_chmod.assert_called_once_with(dest_file, 0o644)


class TestCopyTextFile:
    """Test text file copying with variable substitution."""

    def setup_method(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_copy_text_file_with_substitution(self):
        """Test text file copying with variable substitution."""
        src_file = Path(self.test_dir) / "template.txt"
        dest_file = Path(self.test_dir) / "output.txt"
        src_file.write_text("Hello ${NAME}, value is ${VALUE}", encoding="utf-8")
        
        logger = Mock()
        
        _copy_text_file(src_file, dest_file, logger, NAME="Test", VALUE="123")
        
        content = dest_file.read_text(encoding="utf-8")
        assert content == "Hello Test, value is 123"

    def test_copy_text_file_auto_secret_key(self):
        """Test automatic SECRET_KEY generation."""
        src_file = Path(self.test_dir) / "template.txt"
        dest_file = Path(self.test_dir) / "output.txt"
        src_file.write_text("Secret: ${SECRET_KEY}", encoding="utf-8")
        
        logger = Mock()
        
        _copy_text_file(src_file, dest_file, logger)
        
        content = dest_file.read_text(encoding="utf-8")
        assert content.startswith("Secret: ")
        assert len(content.split(": ")[1]) == 50  # Default secret key length

    def test_copy_text_file_override_secret_key(self):
        """Test overriding SECRET_KEY."""
        src_file = Path(self.test_dir) / "template.txt"
        dest_file = Path(self.test_dir) / "output.txt"
        src_file.write_text("Secret: ${SECRET_KEY}", encoding="utf-8")
        
        logger = Mock()
        
        _copy_text_file(src_file, dest_file, logger, SECRET_KEY="custom_key")
        
        content = dest_file.read_text(encoding="utf-8")
        assert content == "Secret: custom_key"

    @patch('os.chmod')
    def test_copy_text_file_permissions(self, mock_chmod):
        """Test file permissions are set correctly."""
        src_file = Path(self.test_dir) / "template.txt"
        dest_file = Path(self.test_dir) / "subdir" / "output.txt"
        src_file.write_text("Content", encoding="utf-8")
        
        logger = Mock()
        
        _copy_text_file(src_file, dest_file, logger)
        
        mock_chmod.assert_called_once_with(dest_file, 0o644)


class TestCopyFilesRecursive:
    """Test recursive file copying."""

    def setup_method(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.src_dir = Path(self.test_dir) / "src"
        self.dest_dir = Path(self.test_dir) / "dest"

    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_copy_files_recursive_simple(self):
        """Test simple recursive copying."""
        # Create source structure
        self.src_dir.mkdir()
        (self.src_dir / "file1.txt").write_text("Content 1")
        (self.src_dir / "subdir").mkdir()
        (self.src_dir / "subdir" / "file2.txt").write_text("Content 2")
        
        logger = Mock()
        
        copy_files_recursive(self.src_dir, self.dest_dir, logger)
        
        # Verify files were copied
        assert (self.dest_dir / "file1.txt").exists()
        assert (self.dest_dir / "subdir" / "file2.txt").exists()
        assert (self.dest_dir / "file1.txt").read_text() == "Content 1"
        assert (self.dest_dir / "subdir" / "file2.txt").read_text() == "Content 2"

    def test_copy_files_recursive_with_variables(self):
        """Test recursive copying with variable substitution."""
        # Create source structure
        self.src_dir.mkdir()
        (self.src_dir / "template.txt").write_text("Hello ${NAME}")
        
        logger = Mock()
        
        copy_files_recursive(self.src_dir, self.dest_dir, logger, NAME="World")
        
        # Verify variable substitution
        content = (self.dest_dir / "template.txt").read_text()
        assert content == "Hello World"

    def test_copy_files_recursive_mixed_files(self):
        """Test recursive copying with mixed binary and text files."""
        # Create source structure
        self.src_dir.mkdir()
        (self.src_dir / "text.txt").write_text("Text file")
        (self.src_dir / "binary.bin").write_bytes(b"Binary \x00 file")
        
        logger = Mock()
        
        copy_files_recursive(self.src_dir, self.dest_dir, logger)
        
        # Verify files were copied correctly
        assert (self.dest_dir / "text.txt").read_text() == "Text file"
        assert (self.dest_dir / "binary.bin").read_bytes() == b"Binary \x00 file"

    def test_copy_files_recursive_creates_dest_dir(self):
        """Test that destination directory is created."""
        self.src_dir.mkdir()
        (self.src_dir / "file.txt").write_text("Content")
        
        logger = Mock()
        
        # Destination doesn't exist
        assert not self.dest_dir.exists()
        
        copy_files_recursive(self.src_dir, self.dest_dir, logger)
        
        # Destination should be created
        assert self.dest_dir.exists()
        assert (self.dest_dir / "file.txt").exists()

    def test_copy_files_recursive_empty_directory(self):
        """Test recursive copying of empty directory."""
        self.src_dir.mkdir()
        logger = Mock()
        
        copy_files_recursive(self.src_dir, self.dest_dir, logger)
        
        # Destination should be created even if source is empty
        assert self.dest_dir.exists()


class TestFindAvailablePort:
    """Test port availability checking."""

    @patch('socket.socket')
    def test_find_available_port_first_available(self, mock_socket_class):
        """Test finding port when first one is available."""
        mock_socket = MagicMock()
        mock_socket_class.return_value.__enter__.return_value = mock_socket
        
        port = find_available_port(8000)
        assert port == 8000
        mock_socket.bind.assert_called_once_with(('127.0.0.1', 8000))

    @patch('socket.socket')
    def test_find_available_port_second_available(self, mock_socket_class):
        """Test finding port when first is occupied."""
        mock_socket = MagicMock()
        mock_socket_class.return_value.__enter__.return_value = mock_socket
        
        def bind_side_effect(addr):
            if addr[1] == 8000:
                raise OSError("Port in use")
            # Second port (8001) is available
        
        mock_socket.bind.side_effect = bind_side_effect
        
        port = find_available_port(8000)
        assert port == 8001

    @patch('socket.socket')
    def test_find_available_port_max_attempts(self, mock_socket_class):
        """Test port finding with maximum attempts - should fallback to random port."""
        mock_socket = MagicMock()
        mock_socket_class.return_value.__enter__.return_value = mock_socket
        mock_socket.bind.side_effect = OSError("All ports in use")
        
        # Function should return a fallback port rather than raising an error
        port = find_available_port(8000, max_attempts=5)
        assert isinstance(port, int)
        assert 20000 <= port <= 65000  # Fallback range

    @patch('socket.socket')
    def test_find_available_port_socket_error(self, mock_socket_class):
        """Test port finding with socket errors."""
        mock_socket = MagicMock()
        mock_socket_class.return_value.__enter__.return_value = mock_socket
        
        def bind_side_effect(addr):
            if addr[1] == 8000:
                raise socket.timeout("Timeout")
            # Second port works
        
        mock_socket.bind.side_effect = bind_side_effect
        
        port = find_available_port(8000)
        assert port == 8001


class TestWaitForPostgres:
    """Test PostgreSQL connection waiting."""

    @patch('subprocess.run')
    def test_wait_for_postgres_success(self, mock_run):
        """Test successful PostgreSQL connection."""
        mock_run.return_value = Mock(returncode=0)
        logger = Mock()
        
        wait_for_postgres("testuser", logger)
        
        mock_run.assert_called()
        args = mock_run.call_args[0][0]
        assert "pg_isready" in args
        assert "-U" in args
        assert "testuser" in args

    @patch('subprocess.run')
    def test_wait_for_postgres_empty_user(self, mock_run):
        """Test with empty PostgreSQL user."""
        logger = Mock()
        
        wait_for_postgres("", logger)
        
        # Should log error and return without attempting connection
        logger.error.assert_called()
        mock_run.assert_not_called()

    @patch('subprocess.run')
    def test_wait_for_postgres_root_user(self, mock_run):
        """Test with root user (not allowed)."""
        logger = Mock()
        
        wait_for_postgres("root", logger)
        
        # Should log error and return without attempting connection
        logger.error.assert_called()
        mock_run.assert_not_called()

    @patch('subprocess.run')
    @patch('time.sleep')
    def test_wait_for_postgres_retry(self, mock_sleep, mock_run):
        """Test PostgreSQL connection with retries."""
        # First few attempts fail, then succeed
        mock_run.side_effect = [
            Mock(returncode=1),  # First attempt fails
            Mock(returncode=1),  # Second attempt fails
            Mock(returncode=0),  # Third attempt succeeds
        ]
        logger = Mock()
        
        wait_for_postgres("testuser", logger, max_attempts=5, delay=0.1)
        
        assert mock_run.call_count == 3
        assert mock_sleep.call_count == 2

    @patch('subprocess.run')
    @patch('time.sleep')
    def test_wait_for_postgres_max_retries(self, mock_sleep, mock_run):
        """Test PostgreSQL connection exceeding max retries."""
        mock_run.return_value = Mock(returncode=1)  # Always fail
        logger = Mock()
        
        wait_for_postgres("testuser", logger, max_attempts=3, delay=0.1)
        
        assert mock_run.call_count == 3
        assert mock_sleep.call_count == 2  # Sleep between retries, not after last
        logger.error.assert_called()

    @patch('subprocess.run')
    def test_wait_for_postgres_subprocess_exception(self, mock_run):
        """Test PostgreSQL connection with subprocess exception."""
        mock_run.side_effect = subprocess.SubprocessError("Connection failed")
        logger = Mock()
        
        wait_for_postgres("testuser", logger, max_attempts=1)
        
        # Should handle exception and log error
        logger.error.assert_called()

    @patch('subprocess.run')
    def test_wait_for_postgres_default_values(self, mock_run):
        """Test PostgreSQL connection with default parameter values."""
        mock_run.return_value = Mock(returncode=0)
        logger = Mock()
        
        wait_for_postgres("testuser", logger)
        
        mock_run.assert_called()
        # Verify default timeout is used
        call_kwargs = mock_run.call_args[1]
        assert 'timeout' in call_kwargs


class TestFixPermissions:
    """Test permission fixing functionality."""

    @patch('subprocess.run')
    def test_fix_permissions_success(self, mock_run):
        """Test successful permission fixing."""
        mock_run.return_value = Mock(returncode=0)
        logger = Mock()
        directory = Path("/test/dir")
        
        # Mock directory.is_dir() to return True
        with patch.object(Path, 'is_dir', return_value=True):
            fix_permissions(directory, 1000, 1000, logger, "testuser")
        
        mock_run.assert_called()
        args = mock_run.call_args[0][0]
        assert "chown" in " ".join(args)

    @patch('subprocess.run')
    def test_fix_permissions_empty_user(self, mock_run):
        """Test permission fixing with empty user."""
        logger = Mock()
        directory = Path("/test/dir")
        
        # Mock directory.is_dir() to return True
        with patch.object(Path, 'is_dir', return_value=True):
            with pytest.raises(ValueError, match="PostgreSQL user not specified"):
                fix_permissions(directory, 1000, 1000, logger, "")
        
        # Should log error and not call subprocess
        logger.error.assert_called()
        mock_run.assert_not_called()

    @patch('subprocess.run')
    def test_fix_permissions_root_user(self, mock_run):
        """Test permission fixing with root user (not allowed)."""
        logger = Mock()
        directory = Path("/test/dir")
        
        # Mock directory.is_dir() to return True
        with patch.object(Path, 'is_dir', return_value=True):
            with pytest.raises(ValueError, match="Invalid PostgreSQL user: root"):
                fix_permissions(directory, 1000, 1000, logger, "root")
        
        # Should log error and not call subprocess
        logger.error.assert_called()
        mock_run.assert_not_called()

    @patch('subprocess.run')
    def test_fix_permissions_no_user(self, mock_run):
        """Test permission fixing with None user."""
        logger = Mock()
        directory = Path("/test/dir")
        
        # Mock directory.is_dir() to return True
        with patch.object(Path, 'is_dir', return_value=True):
            with pytest.raises(ValueError, match="PostgreSQL user not specified"):
                fix_permissions(directory, 1000, 1000, logger, None)
        
        # Should log error and not call subprocess
        logger.error.assert_called()
        mock_run.assert_not_called()

    @patch('subprocess.run')
    def test_fix_permissions_subprocess_error(self, mock_run):
        """Test permission fixing with subprocess error."""
        mock_run.side_effect = subprocess.SubprocessError("Permission denied")
        logger = Mock()
        directory = Path("/test/dir")
        
        # Mock directory.is_dir() to return True
        with patch.object(Path, 'is_dir', return_value=True):
            with pytest.raises(subprocess.SubprocessError):
                fix_permissions(directory, 1000, 1000, logger, "testuser")
        
        # Should handle exception and log error
        logger.error.assert_called()

    @patch('subprocess.run')
    def test_fix_permissions_called_process_error(self, mock_run):
        """Test permission fixing with called process error."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "chown")
        logger = Mock()
        directory = Path("/test/dir")
        
        # Mock directory.is_dir() to return True
        with patch.object(Path, 'is_dir', return_value=True):
            with pytest.raises(subprocess.CalledProcessError):
                fix_permissions(directory, 1000, 1000, logger, "testuser")
        
        # Should handle exception and log error
        logger.error.assert_called()


class TestUtilityFunctionsIntegration:
    """Integration tests for utility functions."""

    def setup_method(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_full_template_processing_workflow(self):
        """Test complete workflow of template processing."""
        # Create source structure
        src_dir = Path(self.test_dir) / "templates"
        dest_dir = Path(self.test_dir) / "project"
        src_dir.mkdir()
        
        # Create template files
        (src_dir / "config.txt").write_text("Name: ${PROJECT_NAME}\nSecret: ${SECRET_KEY}")
        (src_dir / "binary.dat").write_bytes(b"Binary data \x00 here")
        (src_dir / "subdir").mkdir()
        (src_dir / "subdir" / "nested.txt").write_text("Project: ${PROJECT_NAME}")
        
        logger = Mock()
        
        # Process templates
        copy_files_recursive(
            src_dir, dest_dir, logger,
            PROJECT_NAME="TestProject",
            SECRET_KEY="test_secret_123"
        )
        
        # Verify results
        config_content = (dest_dir / "config.txt").read_text()
        assert "Name: TestProject" in config_content
        assert "Secret: test_secret_123" in config_content
        
        binary_content = (dest_dir / "binary.dat").read_bytes()
        assert binary_content == b"Binary data \x00 here"
        
        nested_content = (dest_dir / "subdir" / "nested.txt").read_text()
        assert "Project: TestProject" in nested_content
