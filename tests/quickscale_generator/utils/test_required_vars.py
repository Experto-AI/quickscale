import unittest
from unittest.mock import patch
import os

from quickscale.utils.env_utils import env_manager
from quickscale.config.settings import REQUIRED_VARS
from quickscale.config.generator_config import generator_config


class TestRequiredVarsValidation(unittest.TestCase):
    """Tests for a simulated validate_required_vars function."""
    
    def setUp(self):
        """Set up environment for each test."""
        self.original_env = os.environ.copy()
    
    def tearDown(self):
        """Restore original environment after each test."""
        os.environ.clear()
        os.environ.update(self.original_env)
        env_manager.refresh_env_cache()
    
    # Define validate_required_vars function for testing
    def validate_required_vars(self, component):
        """Validate required variables for a component."""
        missing = []
        for var in REQUIRED_VARS.get(component, []):
            if not generator_config.get_env(var):
                missing.append(var)
        if missing:
            raise ValueError(f"Missing required variables for {component}: {', '.join(missing)}")
    
    def test_validate_required_vars_all_present(self):
        """Test that validate_required_vars passes when all required variables are present."""
        # Set up environment with all required variables for the web component
        with patch('quickscale.config.generator_config.generator_config.get_env', return_value='test-value'):
            try:
                self.validate_required_vars('web')
            except ValueError as e:
                self.fail(f"validate_required_vars raised ValueError unexpectedly: {e}")
    
    def test_validate_required_vars_all_missing(self):
        """Test that validate_required_vars raises error when all required variables are missing."""
        # Mock get_env to return an empty string (falsey value)
        with patch('quickscale.config.generator_config.generator_config.get_env', return_value=''):
            with self.assertRaises(ValueError):
                self.validate_required_vars('web')
    
    def test_validate_required_vars_some_missing(self):
        """Test that validate_required_vars raises error when some required variables are missing."""
        # Set up environment with only WEB_PORT - missing SECRET_KEY
        def mock_get_env(key, *args):
            return 'test-value' if key == 'WEB_PORT' else ''
        
        with patch('quickscale.config.generator_config.generator_config.get_env', side_effect=mock_get_env):
            with self.assertRaises(ValueError) as context:
                self.validate_required_vars('web')
            
            # Check that the error message contains only the missing variables
            error_message = str(context.exception)
            self.assertIn('SECRET_KEY', error_message)
            self.assertNotIn('WEB_PORT', error_message)
    
    def test_validate_required_vars_unknown_component(self):
        """Test that validate_required_vars doesn't raise error for unknown components."""
        with patch('quickscale.config.generator_config.generator_config.get_env', return_value=''):
            try:
                self.validate_required_vars('unknown_component')
            except ValueError as e:
                self.fail(f"validate_required_vars should not raise error for unknown components: {e}")
    
    def test_validate_required_vars_all_components(self):
        """Test validate_required_vars for all defined components."""
        # Test with all variables present for all components
        with patch('quickscale.config.generator_config.generator_config.get_env', return_value='test-value'):
            for component in REQUIRED_VARS:
                try:
                    self.validate_required_vars(component)
                except ValueError as e:
                    self.fail(f"validate_required_vars raised ValueError for {component}: {e}")
    
    def test_validate_required_vars_empty_component(self):
        """Test validate_required_vars with an empty component name."""
        with patch('quickscale.config.generator_config.generator_config.get_env', return_value=''):
            try:
                self.validate_required_vars('')
            except ValueError as e:
                self.fail(f"validate_required_vars should not raise error for empty component: {e}")
    
    def test_required_vars_structure_and_completeness(self):
        """Test that REQUIRED_VARS contains all expected components and variables."""
        # Test that it's a dictionary
        self.assertIsInstance(REQUIRED_VARS, dict)
        
        # Test all expected components are present
        expected_components = ['web', 'db', 'email', 'stripe']
        for component in expected_components:
            self.assertIn(component, REQUIRED_VARS)
            self.assertIsInstance(REQUIRED_VARS[component], list)
        
        # Check for expected variables in each component
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


if __name__ == '__main__':
    unittest.main() 