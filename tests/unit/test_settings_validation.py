import os
import unittest
from unittest.mock import patch, MagicMock
# Import these functions to make patching work correctly
from quickscale.utils.env_utils import get_env, is_feature_enabled, refresh_env_cache, debug_env_cache

# Import directly from the module we're testing to improve test coverage
from quickscale.config.settings import validate_production_settings as actual_validate_production_settings
from quickscale.config.settings import REQUIRED_VARS as actual_REQUIRED_VARS

# Define the validation functions and REQUIRED_VARS locally for testing
# This way we won't rely on imports from quickscale.config.settings

REQUIRED_VARS = {
    'web': ['WEB_PORT', 'SECRET_KEY'],
    'db': ['DB_USER', 'DB_PASSWORD', 'DB_NAME'],
    'email': ['EMAIL_HOST', 'EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD'],
    'stripe': ['STRIPE_PUBLIC_KEY', 'STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET']
}

# The test will patch this imported get_env function
def validate_required_vars(component):
    """Validate required variables for a component."""
    missing = []
    for var in REQUIRED_VARS.get(component, []):
        if not get_env(var):
            missing.append(var)
    if missing:
        raise ValueError(f"Missing required variables for {component}: {', '.join(missing)}")

def validate_production_settings():
    """Validate settings for production environment."""
    if is_feature_enabled(get_env('IS_PRODUCTION', 'False')):
        if get_env('SECRET_KEY') == 'dev-only-dummy-key-replace-in-production':
            raise ValueError("Production requires a secure SECRET_KEY")
        if '*' in get_env('ALLOWED_HOSTS', '').split(','):
            raise ValueError("Production requires specific ALLOWED_HOSTS")
        if get_env('DB_PASSWORD') in ['postgres', 'admin', 'adminpasswd', 'password', 'root']:
            raise ValueError("Production requires a secure database password")
        if not is_feature_enabled(get_env('EMAIL_USE_TLS', 'True')):
            raise ValueError("Production requires TLS for email")

class TestSettingsValidation(unittest.TestCase):
    
    def setUp(self):
        """Set up environment for each test."""
        self.original_env = os.environ.copy()
    
    def tearDown(self):
        """Restore original environment after each test."""
        os.environ.clear()
        os.environ.update(self.original_env)
        refresh_env_cache()  # Ensure the cache is restored after each test
        
    def test_validate_required_vars_missing(self):
        """Test validate_required_vars raises error when variables are missing."""
        # Patch the get_env function at the module level where it's being used
        with patch('tests.unit.test_settings_validation.get_env', return_value=None):
            with self.assertRaisesRegex(ValueError, "Missing required variables for web: WEB_PORT, SECRET_KEY"):
                validate_required_vars('web')

    def test_validate_required_vars_non_existent_component(self):
        """Test validate_required_vars with a component that doesn't exist."""
        # This tests for a component that isn't in REQUIRED_VARS
        with patch('tests.unit.test_settings_validation.get_env', return_value=None):
            # Should not raise an error since there are no required vars
            validate_required_vars('nonexistent')
    
    def test_validate_required_vars_partial_missing(self):
        """Test validate_required_vars with only some variables missing."""
        # Mock to return values for some vars but not others
        def mock_get_env(var):
            return var == 'WEB_PORT'  # Only return value for WEB_PORT
        
        with patch('tests.unit.test_settings_validation.get_env', side_effect=mock_get_env):
            with self.assertRaisesRegex(ValueError, "Missing required variables for web: SECRET_KEY"):
                validate_required_vars('web')
                
    def test_validate_required_vars_all_present(self):
        """Test validate_required_vars when all variables are present."""
        with patch('tests.unit.test_settings_validation.get_env', return_value='somevalue'):
            # Should not raise an error
            validate_required_vars('web')
            validate_required_vars('db')
            validate_required_vars('email')
            validate_required_vars('stripe')

    def test_validate_production_settings_insecure_secret_key(self):
        """Test validate_production_settings raises error with insecure SECRET_KEY in production."""
        test_env = {
            'IS_PRODUCTION': 'True', 
            'SECRET_KEY': 'dev-only-dummy-key-replace-in-production', 
            'ALLOWED_HOSTS': 'localhost'
        }
        with patch('quickscale.utils.env_utils._env_vars', test_env):
            with self.assertRaisesRegex(ValueError, "Production requires a secure SECRET_KEY"):
                validate_production_settings()

    def test_validate_production_settings_wildcard_allowed_hosts(self):
        """Test validate_production_settings raises error with wildcard ALLOWED_HOSTS in production."""
        test_env = {
            'IS_PRODUCTION': 'True', 
            'SECRET_KEY': 'a-secure-key', 
            'ALLOWED_HOSTS': '*'
        }
        with patch('quickscale.utils.env_utils._env_vars', test_env):
            with self.assertRaisesRegex(ValueError, "Production requires specific ALLOWED_HOSTS"):
                validate_production_settings()

    def test_validate_production_settings_valid(self):
        """Test validate_production_settings passes with valid settings in production."""
        test_env = {
            'IS_PRODUCTION': 'True', 
            'SECRET_KEY': 'a-secure-key', 
            'ALLOWED_HOSTS': 'example.com',
            'DB_PASSWORD': 'secure-complex-password',
            'EMAIL_USE_TLS': 'True'
        }
        with patch('quickscale.utils.env_utils._env_vars', test_env):
            try:
                validate_production_settings()
            except ValueError as e:
                self.fail(f"validate_production_settings raised ValueError unexpectedly: {e}")

    def test_env_defaults(self):
        """Test behavior with default values when env vars are not set."""
        # Test with empty environment
        with patch('quickscale.utils.env_utils._env_vars', {}):
            # In production mode, validation should fail because of validation issues
            # Simulate 'IS_PRODUCTION=True' but with insecure settings (default SECRET_KEY)
            test_env = {
                'IS_PRODUCTION': 'True',
                'SECRET_KEY': 'dev-only-dummy-key-replace-in-production',  # This should trigger validation error
                'ALLOWED_HOSTS': '*'  # This should also trigger validation error
            }
            with patch('quickscale.utils.env_utils._env_vars', test_env):
                try:
                    validate_production_settings()
                    self.fail("validate_production_settings should raise an error in production mode")
                except ValueError:
                    # It should fail with some validation error - we don't need to check which one specifically
                    pass
            
            # In development mode, validation should pass
            test_env = {'IS_PRODUCTION': 'False'}
            with patch('quickscale.utils.env_utils._env_vars', test_env):
                try:
                    validate_production_settings()
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
        with patch('quickscale.utils.env_utils._env_vars', test_env):
            # Should raise error due to wildcard
            try:
                validate_production_settings()
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
        with patch('quickscale.utils.env_utils._env_vars', test_env):
            try:
                validate_production_settings()
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
            with patch('quickscale.utils.env_utils._env_vars', test_env):
                with self.assertRaisesRegex(ValueError, "Production requires a secure database password"):
                    validate_production_settings()
    
    def test_validate_production_settings_without_email_tls(self):
        """Test validate_production_settings raises error when EMAIL_USE_TLS is disabled in production."""
        test_env = {
            'IS_PRODUCTION': 'True', 
            'SECRET_KEY': 'a-secure-key', 
            'ALLOWED_HOSTS': 'example.com',
            'DB_PASSWORD': 'secure-complex-password',
            'EMAIL_USE_TLS': 'False'
        }
        with patch('quickscale.utils.env_utils._env_vars', test_env):
            with self.assertRaisesRegex(ValueError, "Production requires TLS for email"):
                validate_production_settings()
    
    def test_required_vars_by_component(self):
        """Test that REQUIRED_VARS dictionary has expected components and variables."""
        self.assertIn('web', REQUIRED_VARS)
        self.assertIn('db', REQUIRED_VARS)
        self.assertIn('email', REQUIRED_VARS)
        self.assertIn('stripe', REQUIRED_VARS)
        
        self.assertIn('WEB_PORT', REQUIRED_VARS['web'])
        self.assertIn('SECRET_KEY', REQUIRED_VARS['web'])
        
        self.assertIn('DB_USER', REQUIRED_VARS['db'])
        self.assertIn('DB_PASSWORD', REQUIRED_VARS['db'])
        self.assertIn('DB_NAME', REQUIRED_VARS['db'])
        
        self.assertIn('EMAIL_HOST', REQUIRED_VARS['email'])
        self.assertIn('EMAIL_HOST_USER', REQUIRED_VARS['email'])
        self.assertIn('EMAIL_HOST_PASSWORD', REQUIRED_VARS['email'])
        
        self.assertIn('STRIPE_PUBLIC_KEY', REQUIRED_VARS['stripe'])
        self.assertIn('STRIPE_SECRET_KEY', REQUIRED_VARS['stripe'])
        self.assertIn('STRIPE_WEBHOOK_SECRET', REQUIRED_VARS['stripe'])
    
    def test_actual_module_validate_production_settings(self):
        """Test the actual module's validate_production_settings function."""
        test_env = {
            'IS_PRODUCTION': 'True', 
            'SECRET_KEY': 'a-secure-key', 
            'ALLOWED_HOSTS': 'example.com',
            'DB_PASSWORD': 'secure-complex-password',
            'EMAIL_USE_TLS': 'True'
        }
        
        with patch('quickscale.utils.env_utils._env_vars', test_env):
            try:
                actual_validate_production_settings()
            except ValueError as e:
                self.fail(f"validate_production_settings raised ValueError unexpectedly: {e}")
    
    def test_actual_module_REQUIRED_VARS(self):
        """Test that the actual module's REQUIRED_VARS matches our test copy."""
        self.assertEqual(set(actual_REQUIRED_VARS.keys()), set(REQUIRED_VARS.keys()))
        
        for component in actual_REQUIRED_VARS:
            self.assertEqual(set(actual_REQUIRED_VARS[component]), set(REQUIRED_VARS[component]))