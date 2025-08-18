"""Unit tests for env_utils.py module."""
import os
import pytest
from unittest.mock import patch, MagicMock

from quickscale.utils.env_utils import EnvironmentManager, env_manager


class TestEnvironmentManagerClass:
    """Unit tests for EnvironmentManager class - the PROPER way to test consolidated functionality."""

    def test_manager_initialization(self):
        """Test that EnvironmentManager initializes correctly."""
        manager = EnvironmentManager()
        assert manager.dotenv_path is not None
        assert hasattr(manager, '_env_vars')
        assert hasattr(manager, '_env_vars_from_file')
        assert len(manager.REQUIRED_VARS) == 4  # web, db, email, stripe

    @patch('quickscale.utils.env_utils.os.path.exists')
    @patch('quickscale.utils.env_utils.load_dotenv')
    @patch('quickscale.utils.env_utils.dotenv_values')
    def test_manager_refresh_env_cache(self, mock_dotenv_values, mock_load_dotenv, mock_exists):
        """Test EnvironmentManager.refresh_env_cache() method directly."""
        # Setup
        mock_exists.return_value = True
        mock_dotenv_values.return_value = {'TEST_KEY': 'test_value'}
        
        # Create manager and test
        manager = EnvironmentManager()
        manager.refresh_env_cache()
        
        # Verify
        assert manager._env_vars_from_file == {'TEST_KEY': 'test_value'}
        mock_load_dotenv.assert_called()

    def test_manager_validate_required_vars_success(self):
        """Test EnvironmentManager.validate_required_vars() with valid config."""
        manager = EnvironmentManager()
        
        with patch('quickscale.config.generator_config.generator_config.get_env') as mock_get_env:
            mock_get_env.return_value = 'valid_value'
            
            # Should not raise exception
            manager.validate_required_vars('web')

    def test_manager_validate_required_vars_missing(self):
        """Test EnvironmentManager.validate_required_vars() with missing config."""
        manager = EnvironmentManager()
        
        with patch('quickscale.config.generator_config.generator_config.get_env') as mock_get_env:
            mock_get_env.return_value = None
            
            # Should raise exception
            with pytest.raises(ValueError, match="Missing required variables for web"):
                manager.validate_required_vars('web')

    @patch('quickscale.utils.env_utils.logger')
    def test_manager_debug_env_cache(self, mock_logger):
        """Test EnvironmentManager.debug_env_cache() method directly."""
        manager = EnvironmentManager()
        manager._env_vars = {'TEST_DYNAMIC_VAR': 'test_value'}
        manager._env_vars_from_file = {'TEST_DYNAMIC_VAR': 'file_value'}
        
        with patch('quickscale.config.generator_config.generator_config.get_env') as mock_get_env:
            mock_get_env.side_effect = lambda key, default='???': {
                'PROJECT_NAME': 'test_project',
                'LOG_LEVEL': 'DEBUG',
                'TEST_DYNAMIC_VAR': 'test_value'
            }.get(key, default)
            
            manager.debug_env_cache()
            
            # Verify debug logging was called
            assert mock_logger.debug.call_count >= 7


# Legacy wrapper function tests converted to use env_manager
class TestRefreshEnvCache:
    """Unit tests for env_manager.refresh_env_cache method - migrated from legacy wrapper."""

    @patch('quickscale.utils.env_utils.env_manager._update_dotenv_path')
    @patch('quickscale.utils.env_utils.env_manager._load_env_file')
    @patch('quickscale.utils.env_utils.load_dotenv')
    @patch('quickscale.utils.env_utils.env_manager._apply_env_vars_to_environ')
    @patch('quickscale.utils.env_utils.env_manager._log_loaded_env_vars')
    @patch('quickscale.utils.env_utils.env_manager._handle_test_environment')
    @patch('quickscale.utils.env_utils.env_manager.debug_env_cache')
    def test_refresh_env_cache_success(
            self, mock_debug, mock_handle_test, mock_log, mock_apply, 
            mock_load_dotenv, mock_load_file, mock_update_path):
        """Test successful refresh of environment variable cache."""
        # Setup mocks
        mock_update_path.return_value = '/fake/path/.env'
        mock_load_file.return_value = {'TEST_KEY': 'test_value'}
        mock_handle_test.return_value = {'TEST_KEY': 'test_value'}
        
        # Execute
        env_manager.refresh_env_cache()
        
        # Verify
        mock_update_path.assert_called_once()
        mock_load_file.assert_called_once_with('/fake/path/.env')
        mock_load_dotenv.assert_called_once_with(dotenv_path='/fake/path/.env', override=True)
        mock_apply.assert_called_once_with({'TEST_KEY': 'test_value'})
        mock_log.assert_called_once_with({'TEST_KEY': 'test_value'})
        mock_handle_test.assert_called_once()

    @patch('quickscale.utils.env_utils.env_manager._update_dotenv_path')
    @patch('quickscale.utils.env_utils.env_manager._load_env_file')
    @patch('quickscale.utils.env_utils.logger')
    def test_refresh_env_cache_empty_file(self, mock_logger, mock_load_file, mock_update_path):
        """Test refresh when .env file is empty or doesn't exist."""
        # Setup mocks
        mock_update_path.return_value = '/fake/path/.env'
        mock_load_file.return_value = {}
        
        # Execute
        env_manager.refresh_env_cache()
        
        # Verify
        mock_update_path.assert_called_once()
        mock_load_file.assert_called_once_with('/fake/path/.env')
        # Should return early if file is empty
        mock_logger.error.assert_not_called()

    @patch('quickscale.utils.env_utils.env_manager._update_dotenv_path')
    @patch('quickscale.utils.env_utils.env_manager._load_env_file')
    @patch('quickscale.utils.env_utils.env_manager.logger')
    def test_refresh_env_cache_exception(self, mock_logger, mock_load_file, mock_update_path):
        """Test refresh handling when an exception occurs."""
        # Setup mocks
        mock_update_path.return_value = '/fake/path/.env'
        mock_load_file.side_effect = Exception("Test error")
        
        # Execute
        env_manager.refresh_env_cache()
        
        # Verify
        mock_update_path.assert_called_once()
        mock_load_file.assert_called_once_with('/fake/path/.env')
        mock_logger.error.assert_called_once()
        assert "Test error" in mock_logger.error.call_args[0][0]


class TestHelperFunctions:
    """Unit tests for helper functions in env_utils - migrated to use env_manager."""

    def test_update_dotenv_path(self):
        """Test that env_manager._update_dotenv_path correctly builds the path."""
        with patch('os.getcwd', return_value='/fake/cwd'):
            assert env_manager._update_dotenv_path() == '/fake/cwd/.env'

    def test_load_env_file_success(self):
        """Test loading environment variables from a file."""
        mock_file_values = {'TEST_KEY': 'test_value'}
        with patch('os.path.exists', return_value=True):
            with patch('quickscale.utils.env_utils.dotenv_values', return_value=mock_file_values):
                with patch('quickscale.utils.env_utils.env_manager.logger') as mock_logger:
                    result = env_manager._load_env_file('/fake/path/.env')
                    assert result == mock_file_values
                    mock_logger.debug.assert_called()

    def test_load_env_file_not_exists(self):
        """Test loading from a non-existent file."""
        with patch('os.path.exists', return_value=False):
            with patch('quickscale.utils.env_utils.env_manager.logger') as mock_logger:
                result = env_manager._load_env_file('/fake/path/.env')
                assert result == {}
                mock_logger.warning.assert_called_once()

    def test_apply_env_vars_to_environ(self):
        """Test applying environment variables to os.environ."""
        test_vars = {'TEST_KEY1': 'value1', 'TEST_KEY2': 'value2'}
        with patch.dict('os.environ', {}, clear=True):
            with patch('quickscale.utils.env_utils.env_manager.logger') as mock_logger:
                env_manager._apply_env_vars_to_environ(test_vars)
                assert os.environ['TEST_KEY1'] == 'value1'
                assert os.environ['TEST_KEY2'] == 'value2'
                assert mock_logger.debug.call_count >= 2

    def test_log_loaded_env_vars(self):
        """Test logging of loaded environment variables."""
        test_vars = {'TEST_KEY': 'test_value', 'TEST_DYNAMIC_VAR': 'dynamic_value'}
        with patch('quickscale.utils.env_utils.env_manager.logger') as mock_logger:
            with patch.dict('quickscale.utils.env_utils.env_manager._env_vars', {'TEST_DYNAMIC_VAR': 'cache_value'}):
                with patch.dict('os.environ', {'TEST_DYNAMIC_VAR': 'environ_value'}):
                    env_manager._log_loaded_env_vars(test_vars)
                    # Verify that debug logging was called for each key
                    assert mock_logger.debug.call_count >= 5

    def test_handle_test_environment(self):
        """Test handling of test environment special cases."""
        # Test case where LOG_LEVEL should be removed
        env_file = {'TEST_VAR': 'test_value'}
        env_vars = {'LOG_LEVEL': 'DEBUG', 'TEST_VAR': 'test_value'}
        result = env_manager._handle_test_environment(env_file, env_vars)
        assert 'LOG_LEVEL' not in result
        
        # Test case where LOG_LEVEL should be kept
        env_file = {'LOG_LEVEL': 'DEBUG', 'TEST_VAR': 'test_value'}
        env_vars = {'LOG_LEVEL': 'DEBUG', 'TEST_VAR': 'test_value'}
        result = env_manager._handle_test_environment(env_file, env_vars)
        assert 'LOG_LEVEL' in result
        assert result['LOG_LEVEL'] == 'DEBUG'
        
        # Test case where TEST_VAR is not present (not a test environment)
        env_file = {'OTHER_VAR': 'value'}
        env_vars = {'LOG_LEVEL': 'DEBUG', 'OTHER_VAR': 'value'}
        result = env_manager._handle_test_environment(env_file, env_vars)
        assert 'LOG_LEVEL' in result
        assert result['LOG_LEVEL'] == 'DEBUG'


class TestDebugEnvCache:
    """Unit tests for env_manager.debug_env_cache method - migrated from legacy wrapper."""

    @patch('quickscale.utils.env_utils.generator_config')
    @patch('quickscale.utils.env_utils.logger')
    def test_debug_env_cache(self, mock_logger, mock_generator_config):
        """Test debug logging of environment cache."""
        mock_generator_config.get_env.side_effect = lambda key, default=None: {
            'PROJECT_NAME': 'test_project',
            'LOG_LEVEL': 'DEBUG',
            'TEST_DYNAMIC_VAR': 'test_value'
        }.get(key, default)
        
        with patch.dict('quickscale.utils.env_utils.env_manager._env_vars', 
                        {'TEST_DYNAMIC_VAR': 'env_vars_value', 'OTHER_KEY': 'other_value'}):
            with patch.dict('quickscale.utils.env_utils.env_manager._env_vars_from_file', 
                           {'TEST_DYNAMIC_VAR': 'file_value'}):
                env_manager.debug_env_cache()
                
                # Verify that debug logging was called with appropriate information
                assert mock_logger.debug.call_count >= 7
                mock_logger.debug.assert_any_call("--- Environment Debug Info ---")
                mock_logger.debug.assert_any_call("Project Name: test_project")
                mock_logger.debug.assert_any_call("Log Level: DEBUG")
                mock_logger.debug.assert_any_call("TEST_DYNAMIC_VAR: test_value") 