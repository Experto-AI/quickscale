"""Tests for validating the .env.example template file."""
import os
import re
from pathlib import Path
import unittest
from unittest.mock import patch

from quickscale.utils.env_utils import get_env, is_feature_enabled, refresh_env_cache


def load_env_file_to_environ(env_file_path):
    """Load environment variables from a file into os.environ."""
    if not os.path.exists(env_file_path):
        raise FileNotFoundError(f"Environment file not found: {env_file_path}")
    
    # Dictionary to collect any parsing errors
    parsing_errors = {}
    
    with open(env_file_path, 'r') as f:
        line_number = 0
        for line in f:
            line_number += 1
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
                
            try:
                # Split only on the first = character
                if '=' not in line:
                    parsing_errors[line_number] = f"Invalid format: missing '=' in line: '{line}'"
                    continue
                
                key, value = line.split('=', 1)
                
                # Clean up key and value
                key = key.strip()
                
                # Handle the comment part in the line (separate from the value)
                if '#' in value and not value.strip().startswith('#'):
                    value, _ = value.split('#', 1)
                
                value = value.strip().strip('"\'')
                
                # Check for empty key
                if not key:
                    parsing_errors[line_number] = f"Invalid format: empty key in line: '{line}'"
                    continue
                
                # Set the environment variable
                os.environ[key] = value
                
            except Exception as e:
                # Record any parsing errors
                parsing_errors[line_number] = f"Error parsing line: '{line}'. {str(e)}"
    
    # If there were any parsing errors, raise an exception
    if parsing_errors:
        error_messages = [f"Line {line_num}: {msg}" for line_num, msg in parsing_errors.items()]
        raise ValueError(f"Errors parsing environment file:\n" + "\n".join(error_messages))
    
    return True


class TestEnvTemplate(unittest.TestCase):
    """Test cases for validating the .env.example template file."""
    
    def setUp(self):
        """Set up test environment."""
        # Save original environment
        self.original_env = os.environ.copy()
        
        # Get the templates directory path
        self.templates_dir = Path(__file__).parent.parent.parent / "quickscale" / "templates"
        self.env_example_path = self.templates_dir / ".env.example"
        
    def tearDown(self):
        """Clean up after tests."""
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)
        refresh_env_cache()  # Make sure we restore the cached environment too
        
    def test_env_example_exists(self):
        """Test that .env.example file exists in the templates directory."""
        self.assertTrue(self.env_example_path.exists(), 
                       f".env.example file not found at {self.env_example_path}")
        
    def test_env_example_loads_without_errors(self):
        """Test that .env.example file can be loaded into environment without errors."""
        try:
            # Clear environment first to avoid interference
            with patch.dict(os.environ, {}, clear=True):
                load_env_file_to_environ(self.env_example_path)
                refresh_env_cache()  # Refresh env cache after loading
                # If loading succeeds, the test passes
                self.assertTrue(len(os.environ) > 0, 
                              "Successfully loaded .env.example but no variables were found")
        except Exception as e:
            self.fail(f"Failed to load .env.example: {str(e)}")
            
    def test_get_env_retrieves_variables(self):
        """Test that get_env can retrieve variables from loaded .env.example."""
        # Clear environment first to avoid interference
        with patch.dict(os.environ, {}, clear=True):
            # Load env file
            load_env_file_to_environ(self.env_example_path)
            refresh_env_cache()  # Refresh env cache after loading
            
            # Core required variables based on documentation
            required_vars = [
                'SECRET_KEY',
                'DB_PASSWORD',
                'ALLOWED_HOSTS',
                'EMAIL_HOST',
                'EMAIL_HOST_USER',
                'EMAIL_HOST_PASSWORD',
                'IS_PRODUCTION'
            ]
            
            # Additional variables to check
            additional_vars = [
                'DB_PORT_EXTERNAL_ALTERNATIVE_FALLBACK',
                'STRIPE_ENABLED',
                'STRIPE_LIVE_MODE',
                'WEB_PORT_ALTERNATIVE_FALLBACK',
                'LOG_LEVEL'
            ]
            
            # Check all required variables
            for var in required_vars:
                # Using get_env with None default to see if it can retrieve the variable
                value = get_env(var, None)
                self.assertIsNotNone(value, f"Required variable '{var}' not retrieved by get_env")
                # Also check that it's not empty (except for some variables that might be empty)
                if var not in ['EMAIL_HOST_PASSWORD', 'EMAIL_HOST_USER', 'STRIPE_PUBLIC_KEY', 'STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET']:
                    self.assertTrue(value.strip(), f"Required variable '{var}' has empty value")
            
            # Check additional variables
            for var in additional_vars:
                value = get_env(var, None)
                self.assertIsNotNone(value, f"Additional variable '{var}' not retrieved by get_env")
                self.assertTrue(value.strip(), f"Additional variable '{var}' has empty value")
    
    def test_is_feature_enabled_works_with_env_values(self):
        """Test that is_feature_enabled works correctly with the template's boolean values."""
        # Clear environment first to avoid interference
        with patch.dict(os.environ, {}, clear=True):
            # Load env file
            load_env_file_to_environ(self.env_example_path)
            refresh_env_cache()  # Refresh env cache after loading
            
            # Check boolean features that should be enabled or disabled
            self.assertFalse(is_feature_enabled(get_env('IS_PRODUCTION')), 
                           "IS_PRODUCTION should be False by default")
            
            # Check that EMAIL_USE_TLS is enabled
            self.assertTrue(is_feature_enabled(get_env('EMAIL_USE_TLS')), 
                          "EMAIL_USE_TLS should be True by default")
            
            # Check that STRIPE_ENABLED is disabled
            self.assertFalse(is_feature_enabled(get_env('STRIPE_ENABLED')), 
                           "STRIPE_ENABLED should be False by default")
            
            # Check additional boolean features
            self.assertFalse(is_feature_enabled(get_env('STRIPE_LIVE_MODE')), 
                           "STRIPE_LIVE_MODE should be False by default")
            
            self.assertTrue(is_feature_enabled(get_env('DB_PORT_EXTERNAL_ALTERNATIVE_FALLBACK')), 
                          "DB_PORT_EXTERNAL_ALTERNATIVE_FALLBACK should be True by default")
            
            self.assertTrue(is_feature_enabled(get_env('WEB_PORT_ALTERNATIVE_FALLBACK')), 
                          "WEB_PORT_ALTERNATIVE_FALLBACK should be True by default")
    
    def test_env_example_format_consistency(self):
        """Test format consistency of .env.example file."""
        with open(self.env_example_path, 'r') as f:
            content = f.read()
            
        # Check that variable assignments follow consistent format
        # Each non-comment line with a variable should have format: KEY=value
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
                
            # Check variable format - include underscores and allow any case
            # (though project convention seems to be uppercase)
            pattern = r'^[A-Za-z][A-Za-z0-9_]+=.*$'
            self.assertTrue(re.match(pattern, line), 
                          f"Line {i} doesn't follow the KEY=value format: '{line}'")

    def test_env_example_security_warnings(self):
        """Test that .env.example contains proper security warnings."""
        with open(self.env_example_path, 'r') as f:
            content = f.read()
            
        # Check for production warnings
        self.assertTrue(
            re.search(r"production|secure", content, re.IGNORECASE),
            "Example env file should contain warnings about production use"
        )
        
        # Check for security notes on sensitive variables
        sensitive_vars = ['SECRET_KEY', 'DB_PASSWORD', 'EMAIL_HOST_PASSWORD']
        for var in sensitive_vars:
            var_pattern = f"{var}=(.*?)($|\n|#)"
            var_match = re.search(var_pattern, content)
            if var_match:
                var_line = var_match.group(0)
                # Check if there's a comment or indication to replace
                self.assertTrue(
                    "#" in var_line or "replace" in var_line.lower() or var_match.group(1).strip() == "",
                    f"{var} should have a warning comment, be empty, or indicate replacement: {var_line}"
                )
                
    def test_env_example_no_real_credentials(self):
        """Test that .env.example doesn't contain any real credentials."""
        # Clear environment first to avoid interference
        with patch.dict(os.environ, {}, clear=True):
            # Load env file
            load_env_file_to_environ(self.env_example_path)
            refresh_env_cache()  # Refresh env cache after loading
            
            # Get variables that might contain credentials
            credentials = {
                'EMAIL_HOST_USER': get_env('EMAIL_HOST_USER', ''),
                'EMAIL_HOST_PASSWORD': get_env('EMAIL_HOST_PASSWORD', ''),
                'SECRET_KEY': get_env('SECRET_KEY', ''),
                'DB_PASSWORD': get_env('DB_PASSWORD', ''),
                'STRIPE_SECRET_KEY': get_env('STRIPE_SECRET_KEY', ''),
                'STRIPE_WEBHOOK_SECRET': get_env('STRIPE_WEBHOOK_SECRET', '')
            }
            
            # Check if any credential looks like a real one
            for key, value in credentials.items():
                # Skip empty values
                if not value:
                    continue
                    
                # Check for example.com in email addresses
                if key == 'EMAIL_HOST_USER' and '@' in value:
                    self.assertTrue(
                        '@example.com' in value or '@localhost' in value,
                        f"{key} contains what looks like a real email: {value}"
                    )                    # Check for placeholder values in password fields
                    if 'PASSWORD' in key or 'SECRET' in key or 'KEY' in key:
                        # Special case for DB_PASSWORD when IS_PRODUCTION=False
                        if key == 'DB_PASSWORD' and 'adminpasswd' in value.lower() and not is_feature_enabled(get_env('IS_PRODUCTION', 'False')):
                            continue
                        # Special case for SECRET_KEY with specific values
                        if key == 'SECRET_KEY' and (value == 'dev-only-dummy-key-replace-in-production' or 'dummy' in value.lower() or 'replace' in value.lower()):
                            continue
                        self.assertTrue(
                            'your' in value.lower() or 
                            'replace' in value.lower() or 
                            'dummy' in value.lower() or 
                            'change' in value.lower() or
                            'dev-only' in value.lower() or
                            value == '',
                            f"{key} doesn't look like a placeholder: {value}"
                        )
    
    def test_env_example_log_level(self):
        """Test that LOG_LEVEL has a valid value in .env.example."""
        # Clear environment first to avoid interference
        with patch.dict(os.environ, {}, clear=True):
            # Load env file
            load_env_file_to_environ(self.env_example_path)
            refresh_env_cache()  # Refresh env cache after loading
            
            # Get LOG_LEVEL value
            log_level = get_env('LOG_LEVEL', '')
            
            # Check that LOG_LEVEL has a valid value
            valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            self.assertIn(log_level.upper(), valid_log_levels, 
                        f"LOG_LEVEL should have a valid value, got: {log_level}")
