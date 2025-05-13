"""Unit tests for env_utils.py module."""
import os
import pytest
from unittest.mock import patch, MagicMock

from quickscale.utils.env_utils import (
    get_env,
    is_feature_enabled,
    refresh_env_cache,
    debug_env_cache,
    _update_dotenv_path,
    _load_env_file,
    _apply_env_vars_to_environ,
    _log_loaded_env_vars,
    _handle_test_environment,
    _env_vars,
    _env_vars_from_file
)


class TestGetEnv:
    """Unit tests for get_env function."""

    def test_get_env_existing_key(self):
        """Test retrieving an existing environment variable."""
        with patch.dict('quickscale.utils.env_utils._env_vars', {'TEST_KEY': 'test_value'}):
            assert get_env('TEST_KEY') == 'test_value'

    def test_get_env_default_value(self):
        """Test retrieving a non-existent key with default value."""
        with patch.dict('quickscale.utils.env_utils._env_vars', {}, clear=True):
            assert get_env('NON_EXISTENT', default='default_value') == 'default_value'

    def test_get_env_from_file(self):
        """Test retrieving a value from the .env file cache."""
        with patch.dict('quickscale.utils.env_utils._env_vars_from_file', {'FILE_KEY': 'file_value'}):
            assert get_env('FILE_KEY', from_env_file=True) == 'file_value'

    def test_get_env_direct_from_environ(self):
        """Test getting a value directly from os.environ when not in cache."""
        # Clear both the internal cache _env_vars and ensure DIRECT_KEY is only in os.environ
        with patch.dict('quickscale.utils.env_utils._env_vars', {}, clear=True):
            # Need to use mock_environ as a context manager to modify os.environ temporarily
            mock_environ = {'DIRECT_KEY': 'direct_value'}
            with patch.dict('os.environ', mock_environ, clear=False):
                # Call get_env and verify the correct value is returned from os.environ
                assert get_env('DIRECT_KEY') == 'direct_value'
                # Verify that _env_vars was updated with the value from os.environ
                from quickscale.utils.env_utils import _env_vars
                assert 'DIRECT_KEY' in _env_vars
                assert _env_vars['DIRECT_KEY'] == 'direct_value'

    def test_get_env_with_comment(self):
        """Test that comments are stripped from environment variable values."""
        with patch.dict('quickscale.utils.env_utils._env_vars', {'COMMENTED_KEY': 'value # comment'}):
            assert get_env('COMMENTED_KEY') == 'value'


class TestIsFeatureEnabled:
    """Unit tests for is_feature_enabled function."""

    @pytest.mark.parametrize('value, expected', [
        ('true', True),
        ('TRUE', True),
        ('yes', True),
        ('YES', True),
        ('1', True),
        ('on', True),
        ('enabled', True),
        ('t', True),
        ('y', True),
        ('false', False),
        ('FALSE', False),
        ('no', False),
        ('NO', False),
        ('0', False),
        ('off', False),
        ('disabled', False),
        ('', False),
        ('anything_else', False),
        ('true # with comment', True),
        ('yes # with comment', True),
        ('no # with comment', False),
    ])
    def test_is_feature_enabled_values(self, value, expected):
        """Test that is_feature_enabled correctly interprets various values."""
        assert is_feature_enabled(value) is expected

    def test_is_feature_enabled_none(self):
        """Test that is_feature_enabled handles None values."""
        assert is_feature_enabled(None) is False

    def test_is_feature_enabled_non_string(self):
        """Test that is_feature_enabled handles non-string values."""
        assert is_feature_enabled(123) is False
        assert is_feature_enabled(True) is False  # It should only work with string values
        assert is_feature_enabled(False) is False


class TestRefreshEnvCache:
    """Unit tests for refresh_env_cache function."""

    @patch('quickscale.utils.env_utils._update_dotenv_path')
    @patch('quickscale.utils.env_utils._load_env_file')
    @patch('quickscale.utils.env_utils.load_dotenv')
    @patch('quickscale.utils.env_utils._apply_env_vars_to_environ')
    @patch('quickscale.utils.env_utils._log_loaded_env_vars')
    @patch('quickscale.utils.env_utils._handle_test_environment')
    @patch('quickscale.utils.env_utils.debug_env_cache')
    def test_refresh_env_cache_success(
            self, mock_debug, mock_handle_test, mock_log, mock_apply, 
            mock_load_dotenv, mock_load_file, mock_update_path):
        """Test successful refresh of environment variable cache."""
        # Setup mocks
        mock_update_path.return_value = '/fake/path/.env'
        mock_load_file.return_value = {'TEST_KEY': 'test_value'}
        mock_handle_test.return_value = {'TEST_KEY': 'test_value'}
        
        # Execute
        refresh_env_cache()
        
        # Verify
        mock_update_path.assert_called_once()
        mock_load_file.assert_called_once_with('/fake/path/.env')
        mock_load_dotenv.assert_called_once_with(dotenv_path='/fake/path/.env', override=True)
        mock_apply.assert_called_once_with({'TEST_KEY': 'test_value'})
        mock_log.assert_called_once_with({'TEST_KEY': 'test_value'})
        mock_handle_test.assert_called_once()

    @patch('quickscale.utils.env_utils._update_dotenv_path')
    @patch('quickscale.utils.env_utils._load_env_file')
    @patch('quickscale.utils.env_utils.logger')
    def test_refresh_env_cache_empty_file(self, mock_logger, mock_load_file, mock_update_path):
        """Test refresh when .env file is empty or doesn't exist."""
        # Setup mocks
        mock_update_path.return_value = '/fake/path/.env'
        mock_load_file.return_value = {}
        
        # Execute
        refresh_env_cache()
        
        # Verify
        mock_update_path.assert_called_once()
        mock_load_file.assert_called_once_with('/fake/path/.env')
        # Should return early if file is empty
        mock_logger.error.assert_not_called()

    @patch('quickscale.utils.env_utils._update_dotenv_path')
    @patch('quickscale.utils.env_utils._load_env_file')
    @patch('quickscale.utils.env_utils.logger')
    def test_refresh_env_cache_exception(self, mock_logger, mock_load_file, mock_update_path):
        """Test refresh handling when an exception occurs."""
        # Setup mocks
        mock_update_path.return_value = '/fake/path/.env'
        mock_load_file.side_effect = Exception("Test error")
        
        # Execute
        refresh_env_cache()
        
        # Verify
        mock_update_path.assert_called_once()
        mock_load_file.assert_called_once_with('/fake/path/.env')
        mock_logger.error.assert_called_once()
        assert "Test error" in mock_logger.error.call_args[0][0]


class TestHelperFunctions:
    """Unit tests for helper functions in env_utils."""

    def test_update_dotenv_path(self):
        """Test that _update_dotenv_path correctly builds the path."""
        with patch('os.getcwd', return_value='/fake/cwd'):
            assert _update_dotenv_path() == '/fake/cwd/.env'

    def test_load_env_file_success(self):
        """Test loading environment variables from a file."""
        mock_file_values = {'TEST_KEY': 'test_value'}
        with patch('os.path.exists', return_value=True):
            with patch('quickscale.utils.env_utils.dotenv_values', return_value=mock_file_values):
                with patch('quickscale.utils.env_utils.logger') as mock_logger:
                    result = _load_env_file('/fake/path/.env')
                    assert result == mock_file_values
                    mock_logger.debug.assert_called()

    def test_load_env_file_not_exists(self):
        """Test loading from a non-existent file."""
        with patch('os.path.exists', return_value=False):
            with patch('quickscale.utils.env_utils.logger') as mock_logger:
                result = _load_env_file('/fake/path/.env')
                assert result == {}
                mock_logger.warning.assert_called_once()

    def test_apply_env_vars_to_environ(self):
        """Test applying environment variables to os.environ."""
        test_vars = {'TEST_KEY1': 'value1', 'TEST_KEY2': 'value2'}
        with patch.dict('os.environ', {}, clear=True):
            with patch('quickscale.utils.env_utils.logger') as mock_logger:
                _apply_env_vars_to_environ(test_vars)
                assert os.environ['TEST_KEY1'] == 'value1'
                assert os.environ['TEST_KEY2'] == 'value2'
                assert mock_logger.debug.call_count >= 2

    def test_log_loaded_env_vars(self):
        """Test logging of loaded environment variables."""
        test_vars = {'TEST_KEY': 'test_value', 'TEST_DYNAMIC_VAR': 'dynamic_value'}
        with patch('quickscale.utils.env_utils.logger') as mock_logger:
            with patch.dict('quickscale.utils.env_utils._env_vars', {'TEST_DYNAMIC_VAR': 'cache_value'}):
                with patch.dict('os.environ', {'TEST_DYNAMIC_VAR': 'environ_value'}):
                    _log_loaded_env_vars(test_vars)
                    # Verify that debug logging was called for each key
                    assert mock_logger.debug.call_count >= 5

    def test_handle_test_environment(self):
        """Test handling of test environment special cases."""
        # Test case where LOG_LEVEL should be removed
        env_file = {'TEST_VAR': 'test_value'}
        env_vars = {'LOG_LEVEL': 'DEBUG', 'TEST_VAR': 'test_value'}
        result = _handle_test_environment(env_file, env_vars)
        assert 'LOG_LEVEL' not in result
        
        # Test case where LOG_LEVEL should be kept
        env_file = {'LOG_LEVEL': 'DEBUG', 'TEST_VAR': 'test_value'}
        env_vars = {'LOG_LEVEL': 'DEBUG', 'TEST_VAR': 'test_value'}
        result = _handle_test_environment(env_file, env_vars)
        assert 'LOG_LEVEL' in result
        assert result['LOG_LEVEL'] == 'DEBUG'
        
        # Test case where TEST_VAR is not present (not a test environment)
        env_file = {'OTHER_VAR': 'value'}
        env_vars = {'LOG_LEVEL': 'DEBUG', 'OTHER_VAR': 'value'}
        result = _handle_test_environment(env_file, env_vars)
        assert 'LOG_LEVEL' in result
        assert result['LOG_LEVEL'] == 'DEBUG'


class TestDebugEnvCache:
    """Unit tests for debug_env_cache function."""

    @patch('quickscale.utils.env_utils.get_env')
    @patch('quickscale.utils.env_utils.logger')
    def test_debug_env_cache(self, mock_logger, mock_get_env):
        """Test debug logging of environment cache."""
        mock_get_env.side_effect = lambda key, default=None: {
            'PROJECT_NAME': 'test_project',
            'LOG_LEVEL': 'DEBUG',
            'TEST_DYNAMIC_VAR': 'test_value'
        }.get(key, default)
        
        with patch.dict('quickscale.utils.env_utils._env_vars', 
                        {'TEST_DYNAMIC_VAR': 'env_vars_value', 'OTHER_KEY': 'other_value'}):
            with patch.dict('quickscale.utils.env_utils._env_vars_from_file', 
                           {'TEST_DYNAMIC_VAR': 'file_value'}):
                debug_env_cache()
                
                # Verify that debug logging was called with appropriate information
                assert mock_logger.debug.call_count >= 7
                mock_logger.debug.assert_any_call("--- Environment Debug Info ---")
                mock_logger.debug.assert_any_call("Project Name: test_project")
                mock_logger.debug.assert_any_call("Log Level: DEBUG")
                mock_logger.debug.assert_any_call("TEST_DYNAMIC_VAR: test_value") 