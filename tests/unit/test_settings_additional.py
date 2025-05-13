import unittest
from unittest.mock import patch
import os

from quickscale.utils.env_utils import refresh_env_cache
from quickscale.config.settings import validate_production_settings, REQUIRED_VARS


class TestSettingsAdditional(unittest.TestCase):
    """Additional tests for settings.py to increase coverage."""
    
    def setUp(self):
        """Set up environment for each test."""
        self.original_env = os.environ.copy()
    
    def tearDown(self):
        """Restore original environment after each test."""
        os.environ.clear()
        os.environ.update(self.original_env)
        refresh_env_cache()  # Ensure the cache is restored after each test
    
    def test_production_validation_with_is_production_undefined(self):
        """Test validation when IS_PRODUCTION is not defined (should default to False)."""
        # Ensure IS_PRODUCTION is not in the environment
        test_env = {'SECRET_KEY': 'dev-only-dummy-key-replace-in-production'}
        
        with patch('quickscale.utils.env_utils._env_vars', test_env):
            try:
                validate_production_settings()
            except ValueError as e:
                self.fail(f"validate_production_settings should not raise error when IS_PRODUCTION is undefined: {e}")
    
    def test_production_validation_with_various_is_production_values(self):
        """Test validation with different truthy/falsy values for IS_PRODUCTION."""
        secure_settings = {
            'SECRET_KEY': 'a-secure-key',
            'ALLOWED_HOSTS': 'example.com',
            'DB_PASSWORD': 'secure-complex-password',
            'EMAIL_USE_TLS': 'True'
        }
        
        # Test with various truthy values
        truthy_values = ['true', 'True', 'yes', 'Yes', 'y', 'Y', '1', 'on', 'ON']
        for value in truthy_values:
            test_env = {**secure_settings, 'IS_PRODUCTION': value}
            with patch('quickscale.utils.env_utils._env_vars', test_env):
                try:
                    validate_production_settings()
                except ValueError as e:
                    self.fail(f"validate_production_settings failed with IS_PRODUCTION={value}: {e}")
        
        # Test with various falsy values with insecure settings
        # (Should not raise errors since we're not in production)
        falsy_values = ['false', 'False', 'no', 'No', 'n', 'N', '0', 'off', 'OFF']
        insecure_settings = {
            'SECRET_KEY': 'dev-only-dummy-key-replace-in-production',
            'ALLOWED_HOSTS': '*',
            'DB_PASSWORD': 'admin',
            'EMAIL_USE_TLS': 'False'
        }
        
        for value in falsy_values:
            test_env = {**insecure_settings, 'IS_PRODUCTION': value}
            with patch('quickscale.utils.env_utils._env_vars', test_env):
                try:
                    validate_production_settings()
                except ValueError as e:
                    self.fail(f"validate_production_settings should not raise error with IS_PRODUCTION={value}: {e}")
    
    def test_required_vars_structure(self):
        """Test that REQUIRED_VARS has the correct structure and all expected components."""
        # Test that it's a dictionary
        self.assertIsInstance(REQUIRED_VARS, dict)
        
        # Test all expected components are present
        expected_components = ['web', 'db', 'email', 'stripe']
        for component in expected_components:
            self.assertIn(component, REQUIRED_VARS)
            self.assertIsInstance(REQUIRED_VARS[component], list)
    
    def test_validate_production_settings_with_mixed_case_is_production(self):
        """Test validation with mixed case IS_PRODUCTION value."""
        # Test with mixed case 'True'
        test_env = {
            'IS_PRODUCTION': 'TrUe',  # Mixed case
            'SECRET_KEY': 'dev-only-dummy-key-replace-in-production',
            'ALLOWED_HOSTS': '*'
        }
        
        with patch('quickscale.utils.env_utils._env_vars', test_env):
            with self.assertRaises(ValueError):
                validate_production_settings()
    
    def test_validate_production_settings_with_whitespace_in_is_production(self):
        """Test validation with whitespace in IS_PRODUCTION value."""
        # Test with whitespace around 'True'
        test_env = {
            'IS_PRODUCTION': '  True  ',  # Whitespace
            'SECRET_KEY': 'dev-only-dummy-key-replace-in-production',
            'ALLOWED_HOSTS': '*'
        }
        
        with patch('quickscale.utils.env_utils._env_vars', test_env):
            with self.assertRaises(ValueError):
                validate_production_settings()
    
    def test_multiple_hosts_in_allowed_hosts(self):
        """Test validation with multiple hosts in ALLOWED_HOSTS."""
        # Multiple valid hosts
        test_env = {
            'IS_PRODUCTION': 'True',
            'SECRET_KEY': 'a-secure-key',
            'ALLOWED_HOSTS': 'example.com,api.example.com,admin.example.com',
            'DB_PASSWORD': 'secure-complex-password',
            'EMAIL_USE_TLS': 'True'
        }
        
        with patch('quickscale.utils.env_utils._env_vars', test_env):
            try:
                validate_production_settings()
            except ValueError as e:
                self.fail(f"validate_production_settings should not raise error with multiple hosts: {e}")
        
        # Multiple hosts including wildcard (should fail)
        test_env = {
            'IS_PRODUCTION': 'True',
            'SECRET_KEY': 'a-secure-key',
            'ALLOWED_HOSTS': 'example.com,*,admin.example.com',
            'DB_PASSWORD': 'secure-complex-password',
            'EMAIL_USE_TLS': 'True'
        }
        
        with patch('quickscale.utils.env_utils._env_vars', test_env):
            with self.assertRaises(ValueError):
                validate_production_settings()


if __name__ == '__main__':
    unittest.main() 