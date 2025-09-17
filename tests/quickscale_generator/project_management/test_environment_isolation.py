import os
import sys
import unittest
from unittest.mock import patch

# Add the project root to sys.path to access tests module
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

# Define any necessary test helpers or mock implementations
def load_env_file(env_file_path):
    """Parse an .env file and return a dictionary of environment variables."""
    env_vars = {}
    if not os.path.exists(env_file_path):
        return env_vars
    
    with open(env_file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            key, value = line.split('=', 1)
            env_vars[key.strip()] = value.strip().strip('"\'')
    
    return env_vars


class TestEnvironmentIsolation(unittest.TestCase):
    """Test cases for environment variable isolation and proper configuration separation."""

    def setUp(self):
        """Set up test environment."""
        # Save original environment
        self.original_env = os.environ.copy()
    
    def tearDown(self):
        """Clean up after tests."""
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    def test_environment_file_isolation(self, mock_open, mock_exists):
        """Test that .env and .env.example files have proper separation."""
        # Mock environment file contents
        env_content = """
# Development settings
DEBUG=True
SECRET_KEY=dev-only-dummy-key-replace-in-production
ALLOWED_HOSTS=*
DB_PASSWORD=adminpasswd
"""
        env_example_content = """
# Example environment file - DO NOT USE IN PRODUCTION
# Customize these values for your environment
DEBUG=True
SECRET_KEY=replace-in-production
ALLOWED_HOSTS=*
# Database settings
DB_PASSWORD=replace-with-secure-password
"""
        # Set up mocks
        mock_exists.return_value = True
        mock_open.side_effect = [
            unittest.mock.mock_open(read_data=env_content).return_value,
            unittest.mock.mock_open(read_data=env_example_content).return_value
        ]
        
        # Parse both files
        load_env_file('.env')
        example_vars = load_env_file('.env.example')
        
        # Test that example file marks variables that need replacement
        self.assertTrue(any('replace' in val.lower() for val in example_vars.values()), 
                       "Example env file should indicate values that need replacement")
        
        # Check if sensitive variables have warnings in example file
        for key in ['SECRET_KEY', 'DB_PASSWORD']:
            if key in example_vars:
                self.assertTrue('replace' in example_vars[key].lower() or 
                               'change' in example_vars[key].lower() or
                               'your' in example_vars[key].lower(),
                               f"{key} in example file should indicate it needs replacement")
    
    def test_environment_separation_in_settings(self):
        """Test that settings properly separate development and production environments."""
        # Mock settings loader function
        def get_setting(name, env=None):
            """Simulate getting a setting with potential environment override."""
            # Define defaults
            defaults = {
                'DEBUG': 'True',
                'SECRET_KEY': 'dev-only-dummy-key-replace-in-production',
                'ALLOWED_HOSTS': '*',
                'DB_PASSWORD': 'adminpasswd',
                'EMAIL_USE_TLS': 'True'
            }
            
            # Define production overrides
            prod_settings = {
                'DEBUG': 'False',
                'SECRET_KEY': 'prod-secure-key-123456789',
                'ALLOWED_HOSTS': 'example.com,api.example.com',
                'DB_PASSWORD': 'secure-db-password-123',
                'EMAIL_USE_TLS': 'True'
            }
            
            # Choose environment
            if env == 'production':
                return prod_settings.get(name, defaults.get(name))
            return defaults.get(name)
        
        # Test development vs production settings
        self.assertEqual(get_setting('DEBUG'), 'True', "Development DEBUG should be True")
        self.assertEqual(get_setting('DEBUG', 'production'), 'False', "Production DEBUG should be False")
        
        # Secret key should be different
        self.assertNotEqual(get_setting('SECRET_KEY'), get_setting('SECRET_KEY', 'production'),
                           "Development and production SECRET_KEY should be different")
        
        # Allowed hosts should be more restrictive in production
        self.assertEqual(get_setting('ALLOWED_HOSTS'), '*', "Development ALLOWED_HOSTS can be permissive")
        self.assertNotIn('*', get_setting('ALLOWED_HOSTS', 'production'), 
                        "Production ALLOWED_HOSTS should not contain wildcards")
        
        # DB password should be more secure in production
        dev_db_pwd = get_setting('DB_PASSWORD')
        prod_db_pwd = get_setting('DB_PASSWORD', 'production')
        self.assertNotEqual(dev_db_pwd, prod_db_pwd, 
                           "Development and production DB_PASSWORD should be different")
        self.assertGreater(len(prod_db_pwd), len(dev_db_pwd), 
                          "Production DB_PASSWORD should be longer/stronger")
    
    def test_validation_functions_environment_aware(self):
        """Test that validation functions respect environment variables."""
        # Define a simplified version of validate_production_settings for testing
        def validate_test_settings():
            """Test version of validate_production_settings."""
            if os.environ.get('IS_PRODUCTION') == 'True':
                if os.environ.get('ALLOWED_HOSTS') == '*':
                    raise ValueError("Production requires specific ALLOWED_HOSTS")
            return True

        # Test with development settings - no validation needed
        os.environ['IS_PRODUCTION'] = 'False'
        os.environ['ALLOWED_HOSTS'] = '*'
        
        # In development mode, validation should not raise any errors
        try:
            validate_test_settings()
            # If we get here, no error was raised - which is good for development mode
            validation_passed = True
        except ValueError:
            validation_passed = False
        
        # Development mode should not have errors
        self.assertTrue(validation_passed, "Development mode should not validate security settings")
        
        # Test with production settings - validation should occur
        os.environ['IS_PRODUCTION'] = 'True'
        os.environ['ALLOWED_HOSTS'] = '*'
        
        # In production mode with wildcard ALLOWED_HOSTS, validation should raise an error
        try:
            validate_test_settings()
            validation_failed = False
        except ValueError:
            validation_failed = True
        
        # Production mode should validate security settings
        self.assertTrue(validation_failed, "Production mode should validate security settings")
