import os
import unittest
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

# Use centralized test utilities (DRY principle)
from tests.test_utilities import TestUtilities
from quickscale.utils.env_utils import env_manager

# Import directly from the module we're testing to improve test coverage
from quickscale.config.settings import validate_production_settings as actual_validate_production_settings
from quickscale.config.settings import REQUIRED_VARS as actual_REQUIRED_VARS


class TestSettingsValidation(unittest.TestCase):
    
    def setUp(self):
        """Set up environment for each test."""
        self.original_env = os.environ.copy()
    
    def tearDown(self):
        """Restore original environment after each test."""
        os.environ.clear()
        os.environ.update(self.original_env)
        TestUtilities.refresh_env_cache()  # Ensure the cache is restored after each test
        
    def test_validate_required_vars_missing(self):
        """Test validate_required_vars raises error when variables are missing."""
        # Patch the get_env function from the centralized utils module
        with patch('tests.test_utilities.TestUtilities.get_env', return_value=None):
            with self.assertRaisesRegex(ValueError, "Missing required variables for stripe"):
                TestUtilities.validate_required_vars('stripe')

    def test_validate_required_vars_non_existent_component(self):
        """Test validate_required_vars with a component that doesn't exist."""
        # This tests for a component that isn't in REQUIRED_VARS
        with patch('tests.test_utilities.TestUtilities.get_env', return_value=None):
            # Should not raise an error since there are no required vars
            TestUtilities.validate_required_vars('nonexistent')
    
    def test_validate_required_vars_partial_missing(self):
        """Test validate_required_vars with only some variables missing."""
        # Mock to return values for some vars but not others
        def mock_get_env(var):
            return 'STRIPE_PUBLIC_KEY' if var == 'STRIPE_PUBLIC_KEY' else ''  # Only return value for one var
        
        with patch('tests.test_utilities.TestUtilities.get_env', side_effect=mock_get_env):
            with self.assertRaisesRegex(ValueError, "Missing required variables for stripe"):
                TestUtilities.validate_required_vars('stripe')
                
    def test_validate_production_settings_insecure_secret_key(self):
        """Test validate_production_settings raises error with insecure SECRET_KEY in production."""
        test_env = {
            'IS_PRODUCTION': 'True', 
            'SECRET_KEY': 'dev-only-dummy-key-replace-in-production', 
            'ALLOWED_HOSTS': 'localhost'
        }
        with patch.dict(os.environ, test_env, clear=True):
            with self.assertRaisesRegex(ValueError, "Production requires a secure SECRET_KEY"):
                TestUtilities.validate_production_settings()

    def test_validate_production_settings_wildcard_allowed_hosts(self):
        """Test validate_production_settings raises error with wildcard ALLOWED_HOSTS in production."""
        test_env = {
            'IS_PRODUCTION': 'True', 
            'SECRET_KEY': 'a-secure-key', 
            'ALLOWED_HOSTS': '*'
        }
        with patch.dict(os.environ, test_env, clear=True):
            with self.assertRaisesRegex(ValueError, "Production requires specific ALLOWED_HOSTS"):
                TestUtilities.validate_production_settings()

    def test_validate_production_settings_valid(self):
        """Test validate_production_settings passes with valid settings in production."""
        test_env = {
            'IS_PRODUCTION': 'True', 
            'SECRET_KEY': 'a-secure-key', 
            'ALLOWED_HOSTS': 'example.com',
            'DB_PASSWORD': 'secure-complex-password',
            'EMAIL_USE_TLS': 'True'
        }
        with patch.dict(os.environ, test_env, clear=True):
            try:
                TestUtilities.validate_production_settings()
            except ValueError as e:
                self.fail(f"validate_production_settings raised ValueError unexpectedly: {e}")

    def test_env_defaults(self):
        """Test behavior with default values when env vars are not set."""
        # Test with empty environment
        with patch.dict(os.environ, {}, clear=True):
            # In production mode, validation should fail because of validation issues
            # Simulate 'IS_PRODUCTION=True' but with insecure settings (default SECRET_KEY)
            test_env = {
                'IS_PRODUCTION': 'True',
                'SECRET_KEY': 'dev-only-dummy-key-replace-in-production',  # This should trigger validation error
                'ALLOWED_HOSTS': '*'  # This should also trigger validation error
            }
            with patch.dict(os.environ, test_env, clear=True):
                try:
                    TestUtilities.validate_production_settings()
                    self.fail("validate_production_settings should raise an error in production mode")
                except ValueError:
                    # It should fail with some validation error - we don't need to check which one specifically
                    pass
            
            # In development mode, validation should pass
            test_env = {'IS_PRODUCTION': 'False'}
            with patch.dict(os.environ, test_env, clear=True):
                try:
                    TestUtilities.validate_production_settings()
                except ValueError as e:
                    self.fail(f"validate_production_settings should not raise error in development mode: {e}")

    def test_env_overrides(self):
        """Test behavior with overridden values when env vars are set."""
        # Test that ALLOWED_HOSTS wildcard validation works in production
        test_env = {
            'IS_PRODUCTION': 'True',
            'SECRET_KEY': 'a-secure-key',
            'ALLOWED_HOSTS': '*'
        }
        with patch.dict(os.environ, test_env, clear=True):
            # Should raise error due to wildcard
            try:
                TestUtilities.validate_production_settings()
                self.fail("validate_production_settings should raise error with wildcard ALLOWED_HOSTS in production")
            except ValueError as e:
                self.assertIn("ALLOWED_HOSTS", str(e))
        
        # Test that specific hosts validation passes in production
        test_env = {
            'IS_PRODUCTION': 'True',
            'SECRET_KEY': 'a-secure-key',
            'ALLOWED_HOSTS': 'example.com',
            'DB_PASSWORD': 'secure-complex-password',
            'EMAIL_USE_TLS': 'True'
        }
        with patch.dict(os.environ, test_env, clear=True):
            try:
                TestUtilities.validate_production_settings()
            except ValueError as e:
                self.fail(f"validate_production_settings should not raise error with specific hosts: {e}")
                
    def test_validate_production_settings_insecure_db_password(self):
        """Test validate_production_settings raises error with insecure DB_PASSWORD in production."""
        for insecure_password in ['postgres', 'admin', 'adminpasswd', 'password', 'root']:
            test_env = {
                'IS_PRODUCTION': 'True', 
                'SECRET_KEY': 'a-secure-key', 
                'ALLOWED_HOSTS': 'example.com',
                'DB_PASSWORD': insecure_password
            }
            with patch.dict(os.environ, test_env, clear=True):
                with self.assertRaisesRegex(ValueError, "Production requires a secure database password"):
                    TestUtilities.validate_production_settings()
    
    def test_validate_production_settings_without_email_tls(self):
        """Test validate_production_settings raises error when EMAIL_USE_TLS is disabled in production."""
        test_env = {
            'IS_PRODUCTION': 'True', 
            'SECRET_KEY': 'a-secure-key', 
            'ALLOWED_HOSTS': 'example.com',
            'DB_PASSWORD': 'secure-complex-password',
            'EMAIL_USE_TLS': 'False'
        }
        with patch.dict(os.environ, test_env, clear=True):
            with self.assertRaisesRegex(ValueError, "Production requires TLS for email"):
                TestUtilities.validate_production_settings()
    
    def test_required_vars_by_component(self):
        """Test that REQUIRED_VARS dictionary has expected components and variables."""
        self.assertIn('web', actual_REQUIRED_VARS)
        self.assertIn('db', actual_REQUIRED_VARS)
        self.assertIn('email', actual_REQUIRED_VARS)
        self.assertIn('stripe', actual_REQUIRED_VARS)
        
        self.assertIn('WEB_PORT', actual_REQUIRED_VARS['web'])
        self.assertIn('SECRET_KEY', actual_REQUIRED_VARS['web'])
        
        self.assertIn('DB_USER', actual_REQUIRED_VARS['db'])
        self.assertIn('DB_PASSWORD', actual_REQUIRED_VARS['db'])
        self.assertIn('DB_NAME', actual_REQUIRED_VARS['db'])
        
        self.assertIn('EMAIL_HOST', actual_REQUIRED_VARS['email'])
        self.assertIn('EMAIL_HOST_USER', actual_REQUIRED_VARS['email'])
        self.assertIn('EMAIL_HOST_PASSWORD', actual_REQUIRED_VARS['email'])
        
        self.assertIn('STRIPE_PUBLIC_KEY', actual_REQUIRED_VARS['stripe'])
        self.assertIn('STRIPE_SECRET_KEY', actual_REQUIRED_VARS['stripe'])
        self.assertIn('STRIPE_WEBHOOK_SECRET', actual_REQUIRED_VARS['stripe'])
    
    def test_actual_module_validate_production_settings(self):
        """Test the actual module's validate_production_settings function."""
        test_env = {
            'IS_PRODUCTION': 'True', 
            'SECRET_KEY': 'a-secure-key', 
            'ALLOWED_HOSTS': 'example.com',
            'DB_PASSWORD': 'secure-complex-password',
            'EMAIL_USE_TLS': 'True'
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            try:
                actual_validate_production_settings()
            except ValueError as e:
                self.fail(f"validate_production_settings raised ValueError unexpectedly: {e}")
    
    def test_actual_module_REQUIRED_VARS(self):
        """Test that the actual module's REQUIRED_VARS is correctly defined."""
        # Test that the imported REQUIRED_VARS has expected structure
        expected_components = ['web', 'db', 'email', 'stripe']
        self.assertEqual(set(actual_REQUIRED_VARS.keys()), set(expected_components))
        
        # Test specific components have expected variables
        for component in actual_REQUIRED_VARS:
            self.assertIsInstance(actual_REQUIRED_VARS[component], list)
            self.assertGreater(len(actual_REQUIRED_VARS[component]), 0)